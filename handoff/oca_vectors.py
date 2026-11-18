"""Standard OCA SVG cels with documented, non-displaying raster alternatives.

Every source belongs to a traced compositor input, never a guessed Collection.
SVG extraction is the existing isolated-worker implementation.
"""
import copy
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

SVG = '{http://www.w3.org/2000/svg}'
DEFERRED = 'data-compio-source-plan'  # Legacy internal snapshot key.


def capture_frame_sources(manifest, frame):
    result = [dict(entry) for entry in manifest]
    for entry in result:
        path = Path(entry.get('vector_svg') or '')
        if not path.is_file(): continue
        root = ET.parse(path).getroot()
        if not root.get(DEFERRED): continue
        plan = json.loads(root.get(DEFERRED)); plan['frame'] = int(frame)
        root.set(DEFERRED, json.dumps(plan))
        target = path.with_name(path.stem+'-frame'+str(frame)+'.svg')
        ET.ElementTree(root).write(target, encoding='utf-8', xml_declaration=True)
        entry['vector_svg'] = str(target)
    return result


def candidate(entry, job):
    from svg_hybrid import resolve_hybrid_source
    from disabled_layers import notice
    path = Path(entry.get('vector_svg') or '')
    if not path.is_file(): return None
    if not resolve_hybrid_source(path, depth=16 if int(job.get('depth', 8))>8 else 8):
        notice(job, entry['name']+': OCA uses rendered pixels; source has no supported vector artwork')
        return None
    root = ET.parse(path).getroot()
    if any(node.tag == SVG+'image' for node in root.iter()):
        notice(job, entry['name']+': OCA uses rendered pixels; SVG contains unsupported raster components')
        return None
    return root


def raster_frame(cel):
    """Companion consumers select real rendered pixels, never decode SVG as PNG."""
    alternate = cel.get('meta', {}).get('handoff', {}).get('raster')
    return dict(cel, **alternate) if alternate else cel


def publish(job, entry, layer, target, staging, processed, centre, source_size):
    from oca_controls import options
    from oca_images import save
    from disabled_layers import notice
    rasterise = job.get('bake_svg_png') or entry.get('slug') in job.get('_oca_raster_slugs', [])
    if rasterise and not job.get('oca_keep_png', False): return
    root = candidate(entry, job)
    if root is None: return
    if processed is None:
        if entry.get('gp_native_blank'):
            if not job.get('bake_svg_png'):layer.update(type='vectorlayer',fileType='svg')
            return
        if any(n.tag in (SVG+'path', SVG+'use', SVG+'text') for n in root.iter()):
            raise ValueError(entry['name']+': valid vector source has an empty Blender raster cache; '
                             'check the source Render Layers pass and render again')
        return
    original = list(map(float, root.get('viewBox', '').split()))
    if original != [0, 0, *source_size]:
        notice(job, entry['name']+': SVG/cache dimensions disagree; rendered pixels retained')
        return
    cel = layer['frames'][0]; settings = options(job)
    width, height = cel['width'], cel['height']; factor = settings['scale']/100
    root = copy.deepcopy(root)
    root.set('width', str(width));root.set('height', str(height))
    root.set('viewBox', ' '.join(map(str, ((centre[0]-width/2)/factor,
                        (centre[1]-height/2)/factor, width/factor, height/factor))))
    root.set('preserveAspectRatio', 'none')
    relative = target.relative_to(staging)
    vector = staging / ('_vectors' if rasterise else '') / relative.with_suffix('.svg')
    vector.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(vector, encoding='utf-8', xml_declaration=True)
    assets = Path(job['dest']).stem
    metadata = cel['meta'].setdefault('handoff', {})
    if rasterise:
        metadata['editableSource'] = dict(fileName=(Path(assets)/vector.relative_to(staging)).as_posix(),
                                         width=width,height=height,position=list(centre))
        return
    keep = job.get('oca_keep_png', False)
    previews = job.get('_oca_preview_dir')
    if keep or (previews and (settings['writeJson'] or settings['writeTemplate'])):
        fallback = (staging/'_raster'/relative.with_suffix('.png') if keep else
                    Path(previews)/(cel['id']+'.png'))
        fallback.parent.mkdir(parents=True, exist_ok=True)
        depth = int(job.get('depth', 8))
        if depth == 32:
            from psd_worker import write_blender_image
            write_blender_image(fallback, processed, 16, fmt='PNG')
            notice(job, entry['name']+': SVG fallback PNG is a 16-bit display preview of floating-point cache')
        else:
            shutil.copyfile(target, fallback)
        descriptor = dict(fileName=(Path(assets)/fallback.relative_to(staging)).as_posix() if keep else str(fallback.resolve()),
                          width=width,height=height,position=list(centre),
                          colorDepth='U16' if depth>8 else 'U8')
        if keep: metadata['raster'] = descriptor
        else: job.setdefault('_oca_preview_rasters', {})[cel['id']] = descriptor
    target.unlink()
    cel['fileName'] = (Path(assets)/vector.relative_to(staging)).as_posix()
    layer.update(type='vectorlayer', fileType='svg')
