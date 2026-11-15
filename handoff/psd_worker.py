"""Offline layered artwork writer (PSD/PSB/OCA) for Blender 5.2/5.3.

The native File Output node writes cached PNG8/PNG16/EXR32 layers. This
background Blender worker reads that cache and builds all destinations.
All original render outputs are independent of this worker.
"""

import json
import os
import re
import shutil
import sys
import traceback
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'vendor'))
# Blender's --python executes this file without putting its directory on
# sys.path. Bootstrap sibling imports before loading any add-on helpers.
try:
    from .runtime_paths import PRIVATE_PREFIX
    from .branding import LOG_PREFIX
except ImportError:
    from runtime_paths import PRIVATE_PREFIX
    from branding import LOG_PREFIX
from pillow_loader import ensure_pillow
from layer_stack import prepared_entries, build_stack, leaf_names, psd_group_name, strip_tags, tags
from group_blends import promoted_blend, effective_layer_mode
from merge_groups import collapse_merged_groups
from png16_pixels import read_png16_rgba
from psd_color_profiles import attach_document_profile
from tag_registry import effective_profile, translate_label, check as check_tag_registry
from disabled_layers import transparent_cache, notice, last_render
from export_performance import stage, timed, profile_export
from raster_bounds import crop_rgba

BLENDS = {
    'normal': 'NORMAL', 'multiply': 'MULTIPLY', 'screen': 'SCREEN',
    'add': 'LINEAR_DODGE', 'additive': 'LINEAR_DODGE',
    'linear_dodge': 'LINEAR_DODGE', 'linear-dodge': 'LINEAR_DODGE',
    'overlay': 'OVERLAY', 'darken': 'DARKEN', 'lighten': 'LIGHTEN',
}
OCA_BLENDS = {
    'normal': 'normal', 'multiply': 'multiply', 'screen': 'screen',
    'add': 'add', 'additive': 'add', 'linear_dodge': 'add',
    'linear-dodge': 'add', 'overlay': 'overlay', 'darken': 'darken',
    'lighten': 'lighten',
}
SUFFIX = re.compile(r'(?:__|\.)(normal|multiply|screen|additive|add|linear_dodge|linear-dodge|overlay|darken|lighten)$', re.I)


def parse_layer(entry, groups):
    original = entry['name']
    m = SUFFIX.search(original)
    blend = m.group(1).lower() if m else 'normal'
    clean = SUFFIX.sub('', original)
    parts = [x.strip() for x in clean.replace('\\', '/').split('/') if x.strip() and x.strip() not in ('.', '..')]
    if not parts:
        parts = ['Layer']
    auto = entry.get('collection_path', '')
    if groups and len(parts) == 1 and auto:
        ancestors = [x.strip() for x in auto.split('/') if x.strip() and x.strip() not in ('.', '..')]
        parts = ancestors + parts
    if not groups:
        parts = [' / '.join(parts)]
    return parts, blend


@timed('resolve_inputs')
def find_inputs(job):
    folder = Path(job['dir'])
    extension = job.get('extension', '.png')
    out = []
    size = job.get('canvas_size')
    found_size = not any(entry.get('render_disabled') for entry in job['manifest'])
    # Validate all enabled sources first. A disabled source must never conceal
    # an incomplete render, bad path or corrupt cache for an enabled layer.
    resolved = []
    for entry in job['manifest']:
        if entry.get('render_disabled'):
            resolved.append((entry, None))
            continue
        matches = sorted(folder.glob(entry['slug'] + '*' + extension))
        if 'cache_frame' in job:
            matches=[path for path in matches if (match:=re.fullmatch(
                re.escape(entry['slug'])+r'(-?\d+)_?',path.stem)) and int(match[1])==int(job['cache_frame'])]
        if not matches:
            raise FileNotFoundError('Missing ' + extension + ' image for ' + entry['name'] + ' in ' + str(folder))
        resolved.append((entry, matches[-1]))
        if not found_size:
            pixels = read_rgba(matches[-1], source_depth=16 if job.get('cache_kind') == 'PNG16' else 8)
            size = [pixels.shape[1], pixels.shape[0]]
            found_size = True
    for index, (entry, path) in enumerate(resolved):
        if entry.get('render_disabled'):
            if size is None:
                raise ValueError('Disabled layers require saved canvas dimensions; use Retry Export from the open project')
            reused = last_render(job, entry, size)
            if reused is not None:
                out.append((dict(entry, vector_svg='', render_placeholder=False), reused))
                continue
            entry = dict(entry, vector_svg='', render_placeholder=True)
            notice(job, entry['name'] + ': no compatible previous render; blank placeholder used')
            path = folder / ('.handoff-disabled-' + str(index) + extension)
            if extension == '.png':
                transparent_cache(path, size, 16 if job.get('cache_kind') == 'PNG16' or job.get('depth') == 16 else 8)
            else:
                import numpy as np
                write_blender_image(path, np.zeros((size[1], size[0], 4), np.float32), 32, fmt='EXR')
        out.append((entry, path))
    if not out:
        raise ValueError('No exported image layers')
    return out


@timed('decode_pixels')
def read_rgba(path, source_depth=8):
    """Read 8-bit PNG or Blender-generated 32-bit OpenEXR as float RGBA.

    EXR is decoded with Blender itself, avoiding another binary dependency.
    The pixels are linear floats and preserve HDR values and fractional alpha.
    """
    ensure_pillow()
    import numpy as np
    if path.suffix.lower() == '.png' and source_depth == 16:
        return read_png16_rgba(path)
    if path.suffix.lower() == '.png':
        from PIL import Image
        with Image.open(path) as im:
            if im.mode not in ('RGBA', 'RGB'):
                im = im.convert('RGBA')
            pix = np.asarray(im, dtype=np.float32).copy()
            if im.mode == 'RGB':
                alpha = np.ones((*pix.shape[:2], 1), dtype=np.float32) * 255
                pix = np.concatenate([pix, alpha], axis=-1)
            pix /= 255.0
        return pix
    if path.suffix.lower() == '.exr':
        data = read_blender_pixels(path)
        # File Output EXR carries associated alpha; layer writers need straight.
        alpha = data[..., 3:4]
        data[..., :3] = np.where(alpha > 1e-6, data[..., :3] / np.maximum(alpha, 1e-6), 0)
        return data
    raise ValueError('Unsupported cache image: ' + str(path))


def read_blender_pixels(path):
    """Blender reads floating-point EXR and native 16-bit PNG channels."""
    import bpy
    import numpy as np
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        width, height = map(int, image.size)
        count = int(image.channels)
        data = np.empty(width * height * count, dtype=np.float32)
        image.pixels.foreach_get(data)
        # Blender's Image.pixels uses bottom-left origin. PSD, PNG and
        # NumPy's normal image convention use the top-left origin.
        # The 8-bit Pillow reader already returns top-left-first rows.
        data = np.flip(data.reshape((height, width, count)), axis=0).copy()
        if count == 4:
            return data.copy()
        if count == 3:
            return np.concatenate([data, np.ones((height, width, 1), np.float32)], axis=2)
        raise ValueError(f'Image channel count {count} is not RGB/RGBA')
    finally:
        bpy.data.images.remove(image)


def write_blender_image(path, rgba, depth, fmt=None):
    """Export HDR/16-bit intermediate via Blender; no Pillow quantisation."""
    import bpy
    import numpy as np
    height, width = rgba.shape[:2]
    scene = bpy.data.scenes.new(PRIVATE_PREFIX + 'Export_Staging')
    image = bpy.data.images.new(PRIVATE_PREFIX + 'Export_Pixels', width=width, height=height,
                                alpha=True, float_buffer=True)
    try:
        fmt = fmt or ('EXR' if depth == 32 else 'PNG')
        scene.render.image_settings.file_format = {'EXR':'OPEN_EXR','PNG':'PNG','TIFF':'TIFF','JPEG':'JPEG'}[fmt]
        scene.render.image_settings.color_mode = 'RGB' if fmt == 'JPEG' else 'RGBA'
        scene.render.image_settings.color_depth = str(depth)
        if fmt == 'EXR':
            scene.render.image_settings.color_depth = str(depth)
        if fmt == 'EXR':
            scene.render.image_settings.exr_codec = 'ZIP'
        try:
            scene.view_settings.view_transform = 'Standard'
        except Exception:
            pass
        image.alpha_mode = 'PREMUL' if fmt == 'EXR' else 'STRAIGHT'
        pixels = np.ascontiguousarray(rgba, np.float32).copy()
        if fmt == 'EXR':
            pixels[..., :3] *= np.clip(pixels[..., 3:4], 0, 1)
        # Inverse conversion when writing arrays back through Blender.
        # Keep a single top-left-first convention throughout the worker.
        image.pixels.foreach_set(np.ascontiguousarray(pixels[::-1]).ravel())
        image.update()
        image.save_render(str(path), scene=scene)
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError('High-depth flattened image was not written: ' + str(path))
    finally:
        bpy.data.images.remove(image)
        bpy.data.scenes.remove(scene)


@timed('flatten_pixels')
def merge_layers(inputs, depth=8):
    """Blender-style over for supported paint blends. Stays float32 HDR.

    This is a practical flattening compositor for independent layers, not a
    byte-for-byte reproduction of Photoshop's colour-management pipeline.
    """
    import numpy as np
    from merge_groups import over
    # Hidden .ref image layers must not contaminate a flattened preview.
    inputs = [(entry, path) for entry, path in inputs
              if not ('ref' in prepared_entries([(entry, path)], False)[0]['flags']
                      or 'reference' in prepared_entries([(entry, path)], False)[0]['flags'])]
    if not inputs:
        raise ValueError('No visible image layers to flatten (.ref layers are hidden)')
    out = None
    # Native File Output order is top-to-bottom; composite bottom-to-top.
    for entry, path in reversed(inputs):
        foreground = read_rgba(path, source_depth=depth)
        if out is None:
            out = np.zeros(foreground.shape, dtype=np.float32)
        elif foreground.shape != out.shape:
            raise ValueError('Layer dimensions mismatch in Flatten Image')
        if entry.get('render_placeholder'):
            continue
        _, mode = parse_layer(entry, groups=False)
        out = over(out, foreground, mode)
        del foreground
    return out


@timed('psd_build_and_save')
def assemble_psd(job, inputs):
    ensure_pillow()
    from PIL import Image
    from psd_tools import PSDImage
    from psd_tools.constants import BlendMode, SheetColorType, Compression, Tag
    import numpy as np

    dest = Path(job['dest'])
    depth = int(job.get('depth', 8))
    fmt = job.get('format', 'PSD')
    if depth not in (8, 16, 32):
        raise ValueError('PSD bit depth must be 8, 16 or 32')
    # For 8-bit PSD keep the proven Pillow PNG route unless flatten is on.
    if depth == 8 and job.get('extension', '.png') != '.png':
        raise ValueError('8-bit PSD requires PNG8 layer cache')
    if depth == 16 and job.get('extension') not in ('.png', '.exr'):
        raise ValueError('16-bit PSD needs a 16-bit PNG or full-float EXR cache')
    if depth == 32 and job.get('extension') != '.exr':
        raise ValueError('32-bit PSD requires a full-float EXR cache')
    if depth == 8:
        with Image.open(inputs[0][1]) as first:
            size = first.size
    else:
        rgba = read_rgba(inputs[0][1], source_depth=16 if job.get('extension')=='.png' else 8)
        size = (rgba.shape[1], rgba.shape[0])
        del rgba
    codec = job.get('psd_compression', 'RLE')
    if codec == 'AUTO':
        codec = 'ZIP'
    if codec not in ('RLE', 'ZIP', 'ZIP_WITH_PREDICTION', 'RAW'):
        raise ValueError('Unknown PSD compression: ' + str(codec))
    compression = Compression[codec]
    # Dolphin/KDE's PSD decoder accepts RAW/RLE merged previews, even when
    # individual layers use ZIP. Keep the large editable channels compressed
    # with the selected codec while retaining a portable document preview.
    psd = PSDImage.new('RGB', size, depth=depth, color=0.0, compression=Compression.RLE)
    attach_document_profile(psd, depth, job, inputs[0][1])
    profile = effective_profile(job.get('tag_profile', 'AUTO'), fmt)
    try:
        print('Tag profile:', profile, '| XML registry:', check_tag_registry(), flush=True)
    except Exception as exc:
        # The native File Output and established layered writer must survive
        # a missing/corrupt documentation registry. Export names fall back to
        # the pre-0.7.8 formatter instead of losing all image output.
        print('WARNING: Tag XML unavailable; using v0.7.7 group naming:', exc, flush=True)
        profile = 'LEGACY'
    stack = build_stack(prepared_entries(inputs, job['hierarchy'] == 'GROUPS'))
    collapse_merged_groups(stack,
                           lambda item: read_rgba(item['source'], source_depth=depth),
                           size)
    count = 0

    def add_to_psd(container, node, parent_blend=None, inherited_color=''):
        nonlocal count
        for child in reversed(node['children']):
            if child['kind'] == 'group':
                group_label, notes = (psd_group_name(child['name']), []) if profile == 'LEGACY' else \
                    translate_label(child['name'], child.get('raw', child['name']), profile, 'group')
                for note in notes: print('TAG NOTICE group:', group_label, note, flush=True)
                group = container.create_group(name=group_label)
                sheet_color = child.get('sheet_color', '')
                if sheet_color:
                    group.sheet_color = SheetColorType['GRAY' if sheet_color=='NO_COLOR' else sheet_color]
                    print('PSD group colour:', group_label, sheet_color, flush=True)
                if '.ref' in child.get('raw', '').lower() or '.reference' in child.get('raw', '').lower():
                    try: group.visible = False
                    except Exception: pass
                # Match the effective mode of an authored Collection folder.
                # A folder with a dominant non-normal direct layer mode is
                # isolated and blended once against the layers below it.
                # Nested subgroups retain their own mode boundaries.
                group_mode = promoted_blend(child)
                try:
                    group.blend_mode = (getattr(BlendMode, BLENDS[group_mode])
                                        if group_mode else BlendMode.PASS_THROUGH)
                except (AttributeError, ValueError, TypeError):
                    pass
                add_to_psd(group, child, group_mode, sheet_color or inherited_color)
                continue
            item = child['item']
            entry, path = item['entry'], item['source']
            job['_publication_view_layer']=entry.get('source_view_layer','')
            job['_publication_source_svg']=entry.get('vector_svg','')
            source_sidecar=None
            label, mode = child['name'], effective_layer_mode(item, parent_blend)
            raw_display = SUFFIX.sub('', entry['name'].replace('\\', '/').split('/')[-1])
            # A single paint-layer .merge has no container to flatten.
            # Remove the completed directive instead of re-emitting it as a tag.
            raw_display = re.sub(r'\.merge(?=\.|$)', '', raw_display, flags=re.I)
            label, notes = (label, []) if profile == 'LEGACY' else \
                translate_label(label, raw_display, profile, 'layer')
            for note in notes: print('TAG NOTICE layer:', label, note, flush=True)
            if entry.get('render_placeholder'):
                notice(job, entry['name'] + ': hidden blank PSD placeholder created')
            if (not job.get('bake_svg_png') and not item.get('merged') and entry.get('vector_svg')):
                from psd_vectors import load_artwork,append_artwork
                job['_publication_view_layer']=entry.get('source_view_layer','')
                vector_group=None
                original_resources=dict(psd.image_resources)
                original_links=psd.tagged_blocks.get(Tag.LINKED_LAYER_EXTERNAL) if psd.tagged_blocks else None
                report_start=len(job.get('_publication',[]))
                try:
                    model=load_artwork(entry['vector_svg'])
                    if model is None:
                        raise ValueError('No shared artwork cache; use F12 to refresh vectors')
                    if (model['width'],model['height'])!=size:
                        raise ValueError('Vector source dimensions differ from the rendered cache')
                    families=[o.get('svg_instance',{}).get('key') for o in model['objects'] if o.get('svg_instance')]
                    shared_source=None
                    if len(families)!=len(set(families)):
                        from psd_svg_links import svg_sidecar
                        shared_source=svg_sidecar(job,label,model['objects'],size)
                        notice(job,label+': shared SVG source saved beside the document')
                    vector_group=container.create_group(name=label)
                    # Keep supported neighbours native when a GP material
                    # needs its SVG source. Preview only the verified GP
                    # paint subset; unknown renderer features retain the
                    # established whole-source fallback below.
                    source_sidecar=shared_source;cached_visible=None
                    def object_fallback(parent,obj,reason):
                        nonlocal source_sidecar,cached_visible
                        from psd_svg_links import svg_sidecar,preview,create_linked_svg
                        from conversion_policy import record
                        if not any(stroke.get('fill_gradient') for drawing in obj.get('layers',[]) for stroke in drawing['strokes']):
                            raise ValueError(reason)
                        if source_sidecar is None:source_sidecar=svg_sidecar(job,label,model['objects'],size)
                        if cached_visible is None:
                            cached=read_rgba(path,source_depth=16 if job.get('extension')=='.png' and depth==16 else 8)
                            cached_visible=bool(np.any(cached[...,3]>0));del cached
                        if cached_visible:
                            record(job,obj,'RASTER_WITH_SOURCE',reason,source_svg=str(source_sidecar),
                                preview='original Blender render',validation='existing renderer')
                            notice(job,label+': rendered appearance retained; editable SVG source saved beside the document')
                            raise ValueError(reason)
                        pixels,left,top=preview([obj],size,depth,compact=True)
                        object_source=svg_sidecar(job,obj['name'],[obj],size)
                        try:
                            part=create_linked_svg(parent,pixels,object_source,dest,size,
                                left=left,top=top,compression=compression)
                            part.name=obj['name'];representation='LINKED_SMART_OBJECT'
                        except (OSError,ValueError,TypeError,KeyError,RuntimeError,NotImplementedError) as exc:
                            part=parent.create_pixel_layer_from_array(pixels,name=obj['name'],left=left,top=top,compression=compression)
                            representation='RASTER_WITH_SOURCE'
                            notice(job,obj['name']+': SVG link could not be written; visible pixels and SVG retained ('+str(exc)+')')
                        from psd_vectors import bind_source
                        bound=bind_source(parent,obj,[part])
                        record(job,obj,representation,reason,source_svg=str(object_source),layer_ids=bound,
                            preview='SVG-equivalent GP renderer',validation='source renderer fixtures; target editor unverified',
                            features_approximated=['SVG gradient interpolation may differ from Blender'])
                        notice(job,obj['name']+': native PSD gradient unavailable; SVG source saved and linked automatically'
                               if representation=='LINKED_SMART_OBJECT' else obj['name']+': SVG source saved beside visible pixels')
                        return 1
                    # Keep a contiguous shared GP source together when every
                    # member needs fallback. The SVG retains its clone graph;
                    # Photoshop sees one logical linked layer, not independent
                    # copies of each sprite. Nested collection boundaries keep
                    # the existing per-object conversion path.
                    from conversion_policy import automatic_eligible
                    collapse_shared=(len(families)>1 and len(families)==len(model['objects']) and
                        len(set(families))==1 and len({o['svg_instance']['config'] for o in model['objects']})==1 and
                        not any(automatic_eligible(feature) for feature in ('linear_gradient','radial_gradient')) and
                        all(not o.get('collection_parts') and o.get('svg_kind') in (None,'GP') and
                            any(s.get('fill_gradient') for drawing in o.get('layers',[]) for s in drawing['strokes'])
                            for o in model['objects']))
                    if collapse_shared:
                        try:vector_count=append_artwork(vector_group,model,depth,job=job)
                        except (ValueError,NotImplementedError) as exc:
                            for part in list(vector_group):vector_group.remove(part)
                            psd.image_resources.clear();psd.image_resources.update(original_resources)
                            del job.setdefault('_publication',[])[report_start:]
                            from psd_svg_links import preview,create_linked_svg
                            from psd_vectors import bind_source
                            from conversion_policy import record
                            cached=read_rgba(path,source_depth=16 if job.get('extension')=='.png' and depth==16 else 8)
                            if np.any(cached[...,3]>0):
                                pixels,left,top=cached,0,0;origin='original Blender render'
                            else:
                                pixels,left,top=preview(model['objects'],size,depth,compact=True)
                                origin='SVG-equivalent GP renderer'
                            del cached
                            part=create_linked_svg(vector_group,pixels,shared_source,dest,size,
                                left=left,top=top,compression=compression);part.name=label
                            members=[o.get('source_metadata',{}) for o in model['objects']]
                            identities=[o.get('source_metadata',{}).get('object_id') or o['name'] for o in model['objects']]
                            composition=dict(name=label,source_metadata=dict(schema=1,object_name=label,
                                object_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'svg-composition:'+str(identities))),members=members))
                            bound=bind_source(vector_group,composition,[part])
                            for obj in model['objects']:
                                record(job,obj,'LINKED_SMART_OBJECT',str(exc),source_svg=str(shared_source),
                                    destination_layer=label,layer_ids=bound,preview=origin,
                                    features_preserved=['SVG clone relationships','source geometry','source identities'],
                                    features_approximated=['SVG interpolation may differ from Blender'],
                                    validation='linked records and preview tested; editor editing unverified')
                            notice(job,label+': native PSD conversion unavailable; shared SVG linked automatically')
                            vector_count=1
                    else:
                        vector_count=append_artwork(vector_group,model,depth,job=job,fallback=object_fallback)
                    vector_group.blend_mode=getattr(BlendMode,BLENDS[mode])
                    paint_color=item.get('inherited_color') or inherited_color
                    if paint_color:
                        vector_group.sheet_color=SheetColorType['GRAY' if paint_color=='NO_COLOR' else paint_color]
                        for child_layer in vector_group.descendants():child_layer.sheet_color=SheetColorType['GRAY' if paint_color=='NO_COLOR' else paint_color]
                    if 'ref' in item.get('flags',set()) or 'reference' in item.get('flags',set()):vector_group.visible=False
                    count+=vector_count
                    print('PSD vector source:',label,'|',vector_count,'published parts; depth:',depth,flush=True)
                    continue
                except (OSError,ValueError,TypeError,KeyError,RuntimeError,NotImplementedError) as exc:
                    if vector_group is not None:container.remove(vector_group)
                    psd.image_resources.clear()
                    psd.image_resources.update(original_resources)
                    if psd.tagged_blocks is not None:
                        if original_links is None:psd.tagged_blocks.pop(Tag.LINKED_LAYER_EXTERNAL,None)
                        else:psd.tagged_blocks[Tag.LINKED_LAYER_EXTERNAL]=original_links
                    del job.setdefault('_publication',[])[report_start:]
                    if source_sidecar is None:
                        from psd_svg_links import preserve_source_file
                        try:source_sidecar=preserve_source_file(job,label,entry['vector_svg'])
                        except (OSError,ValueError):pass
                    print(f'{LOG_PREFIX} PSD VECTOR FALLBACK:',label,'|',exc,'| keeping rendered source pixels',flush=True)
            if depth == 8:
                if item.get('pixels') is not None:
                    rgba = Image.fromarray((np.clip(item['pixels'], 0, 1)*255+.5).astype(np.uint8), 'RGBA')
                else:
                    with Image.open(path) as image:
                        if image.size != size:
                            raise ValueError('PSD layer dimensions mismatch')
                        rgba = image.convert('RGBA').copy()
                with stage('crop_raster'):
                    cropped, left, top = crop_rgba(np.asarray(rgba))
                    rgba = Image.fromarray(cropped, 'RGBA')
                layer = container.create_pixel_layer(rgba, name=label, left=left, top=top, compression=compression)
            else:
                rgba = item.get('pixels')
                if rgba is None:
                    rgba = read_rgba(path, source_depth=16 if job.get('extension')=='.png' else 8)
                if (rgba.shape[1], rgba.shape[0]) != size:
                    raise ValueError('PSD layer dimensions mismatch')
                with stage('crop_raster'):
                    rgba, left, top = crop_rgba(rgba)
                layer = container.create_pixel_layer_from_array(rgba, name=label, left=left, top=top, compression=compression)
            if (entry.get('vector_svg') and not job.get('bake_svg_png') and not item.get('merged')
                    and not entry.get('render_placeholder')):
                maximum_alpha = (rgba.getchannel('A').getextrema()[1] if depth == 8
                                 else float(np.max(rgba[..., 3])))
                if maximum_alpha == 0:
                    notice(job, label + ': PSD rendered fallback is fully transparent (zero alpha). '
                           'The SVG vectors are separate; this cache has no visible paint. '
                           'Check the source View Layer Grease Pencil filter, render visibility, '
                           'lighting and holdout settings, then render again to refresh its pixels.')
                    from psd_svg_links import preserve_source_file
                    from conversion_policy import record
                    try:preserved=str(preserve_source_file(job,label,entry['vector_svg']))
                    except (OSError,ValueError):preserved=''
                    container.remove(layer)
                    record(job,dict(name=label),'FAILED','No verified visible raster fallback; empty substitute omitted',
                        source_svg=preserved,destination_layer=label)
                    job['_partial']=True
                    continue
                if source_sidecar:
                    from psd_svg_links import attach_svg_link
                    try:
                        attach_svg_link(layer,source_sidecar,dest,size)
                        notice(job,label+': native PSD conversion unavailable; SVG linked automatically with rendered preview')
                    except (OSError,ValueError,TypeError,KeyError,RuntimeError,NotImplementedError) as exc:
                        notice(job,label+': SVG link could not be written; visible pixels and SVG retained ('+str(exc)+')')
            layer.blend_mode = getattr(BlendMode, BLENDS[mode])
            # Blender colours the entire Collection branch in the Outliner.
            # Carry that cue down to paint layers, including .merge output.
            paint_color = item.get('inherited_color') or inherited_color
            if paint_color:
                layer.sheet_color = SheetColorType['GRAY' if paint_color=='NO_COLOR' else paint_color]
            from conversion_policy import record
            record(job,dict(name='',collection_parts=entry.get('collection_path','').split('/')),
                'SKIPPED' if entry.get('render_placeholder') else ('LINKED_SMART_OBJECT'
                    if layer.tagged_blocks.get(Tag.SMART_OBJECT_LAYER_DATA2) else
                    ('RASTER_WITH_SOURCE' if entry.get('vector_svg') else 'NATIVE_EDITABLE')),
                source_feature='raster',destination_layer=label,
                source_svg=str(source_sidecar) if source_sidecar else entry.get('vector_svg',''))
            if item.get('flags', set()) & {'ref', 'reference', 'disabled'}:
                try:
                    layer.visible = False
                except Exception:
                    pass
            count += 1
            print('PSD layer:', label, 'depth:', depth, 'blend:', mode, flush=True)

    if not job.get('flatten'):
        add_to_psd(psd, stack)
        if count == 0:
            if job.get('_partial'):raise ValueError('No verified visible artwork to publish; source and failure diagnostics retained')
            raise ValueError('Every output layer was excluded by .ignore tags')

    if job.get('flatten'):
        array = merge_layers(inputs, depth=depth)
        if depth == 8:
            from PIL import Image
            layer_pixels = Image.fromarray((np.clip(array, 0, 1) * 255 + .5).astype(np.uint8), 'RGBA')
            psd.create_pixel_layer(layer_pixels, name='Flattened Artwork', compression=compression)
        else:
            psd.create_pixel_layer_from_array(array, name='Flattened Artwork', compression=compression)
        print('Flatten Image: one raster layer at', depth, 'bit', flush=True)

    # PSD is automatically upgraded to PSB for >30k dimensions by psd-tools.
    # Also conservatively upgrade if raw layer data is likely >2GB.
    est_bytes = size[0] * size[1] * 4 * (depth // 8) * len(inputs)
    use_psb = fmt == 'PSB' or psd.version == 2 or est_bytes > 2_000_000_000
    if use_psb:
        psd._record.header.version = 2
    if use_psb and dest.suffix.lower() != '.psb':
        dest = dest.with_suffix('.psb')
    if not use_psb and dest.suffix.lower() != '.psd':
        dest = dest.with_suffix('.psd')
    if dest.exists() and not job['overwrite']:
        raise FileExistsError('Overwrite disabled for ' + str(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.with_name(dest.stem + '.writing' + dest.suffix)
    try:
        with stage('psd_save'):
            psd.save(str(staging))
        if not staging.exists() or staging.stat().st_size < 128:
            raise RuntimeError('PSD/PSB writer produced no valid file')
        with staging.open('rb') as f:
            magic = f.read(6)
        if magic[:4] != b'8BPS' or int.from_bytes(magic[4:6], 'big') != (2 if use_psb else 1):
            raise RuntimeError('PSD/PSB header validation failed')
        staging.replace(dest)
    finally:
        staging.unlink(missing_ok=True)
    print('COMPLETE:', dest, 'bytes:', dest.stat().st_size, flush=True)
    return str(dest)


def safe_component(text):
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', '_', text.strip())
    text = text.strip('. ')[:96]
    return text or 'Layer'


# OCA stores application-defined label indices, not hexadecimal colours.
# We preserve the eight conventional Blender/PSD colour names as indices 1..8;
# importers can interpret their own palettes differently (per OCA spec).
_OCA_COLOUR_LABELS = {
    'RED': 1, 'ORANGE': 2, 'YELLOW': 3, 'GREEN': 4,
    'BLUE': 5, 'VIOLET': 6, 'MAGENTA': 7, 'GRAY': 8,
}


def oca_label(colour):
    """OCA -1 is unlabelled; group and paint layers use the same mapping."""
    return _OCA_COLOUR_LABELS.get(str(colour or '').upper(), -1)


def make_oca_layer(parts, mode, path_relative, width, height, depth, frame, idx, reference=False, label=-1):
    identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, '/'.join(parts) + ':' + str(idx)))
    return {
        'name': parts[-1], 'id': identifier, 'type': 'paintlayer',
        'animated': False, 'fileType': 'exr' if depth == 32 else 'png',
        'frames': [{
            'name': safe_component(parts[-1]) + '_' + str(frame).zfill(5),
            'id': str(uuid.uuid5(uuid.NAMESPACE_URL, identifier + ':' + str(frame))),
            'fileName': path_relative, 'frameNumber': frame,
            'opacity': 1.0, 'position': [width // 2, height // 2],
            'width': width, 'height': height, 'duration': 1, 'meta': {},
        }],
        'childLayers': [], 'blendingMode': OCA_BLENDS.get(mode, 'normal'),
        'inheritAlpha': False, 'position': [width // 2, height // 2],
        'width': width, 'height': height, 'label': int(label), 'opacity': 1.0,
        'visible': not reference, 'passThrough': False, 'reference': bool(reference), 'meta': {},
    }


def assemble_oca(job, inputs):
    import numpy as np
    ensure_pillow()
    from PIL import Image
    dest = Path(job['dest'])
    if dest.suffix.lower() != '.oca':
        dest = dest.with_suffix('.oca')
    depth = int(job.get('depth', 8))
    ext = job['extension']
    if (depth in (8, 16) and ext != '.png') or (depth == 32 and ext != '.exr'):
        raise ValueError('OCA cache must be PNG for U8/U16 or EXR for F32')
    if dest.exists() and not job['overwrite']:
        raise FileExistsError('Overwrite disabled for ' + str(dest))
    if depth == 32:
        rgba = read_rgba(inputs[0][1])
        height, width = rgba.shape[:2]
        del rgba
    else:
        with Image.open(inputs[0][1]) as img:
            width, height = img.size
    frame = int(job.get('frame', 0))
    name = dest.stem
    assets = dest.parent / name
    if assets.exists() and not job['overwrite']:
        raise FileExistsError('Overwrite disabled for existing OCA assets ' + str(assets))
    staging = dest.parent / ('.' + name + '.oca-staging-' + uuid.uuid4().hex[:7])
    if job.get('flatten'):
        import numpy as np
        flat = merge_layers(inputs, depth=depth)
        staging.mkdir(parents=True, exist_ok=True)
        flatten_file = staging / ('Flattened.exr' if depth == 32 else 'Flattened.png')
        if depth == 8:
            pic = Image.fromarray((np.clip(flat, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA')
            pic.save(flatten_file)
        else:
            write_blender_image(flatten_file, flat, depth)
        inputs = [({'name': 'Flattened', 'slug': 'Flattened'}, flatten_file)]
    root_layers = []
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)
    path_taken = set()
    try:
        stack = build_stack(prepared_entries(inputs, job['hierarchy'] == 'GROUPS'))
        collapse_merged_groups(stack,
                               lambda item: read_rgba(item['source'], source_depth=depth),
                               (width, height))
        leaf_counter = 0
        def add_oca_children(branch, dest_list, current_folder=(), parent_blend=None):
            nonlocal leaf_counter
            # OCA layer arrays are bottom-to-top, including group children.
            # Reversed stack traversal preserves the authored paint order.
            for child in reversed(branch['children']):
                if child['kind'] == 'group':
                    path = current_folder + (child['name'],)
                    group_mode = promoted_blend(child)
                    obj = {
                        'name': child['name'],
                        'id': str(uuid.uuid5(uuid.NAMESPACE_URL, 'group:'+ '/'.join(path) + ':' + str(leaf_counter))),
                        'type': 'grouplayer', 'animated': False, 'fileType': 'png',
                        'frames': [], 'childLayers': [], 'blendingMode': OCA_BLENDS[group_mode] if group_mode else 'normal',
                        'passThrough': not bool(group_mode), 'inheritAlpha': False,
                        'position': [width//2, height//2],
                        'width': width, 'height': height, 'label': oca_label(child.get('sheet_color')), 'opacity': 1.,
                        'visible': not bool(tags(child['raw']) & {'ref','reference'}),
                        'reference': bool(tags(child['raw']) & {'ref','reference'}), 'meta': {},
                    }
                    dest_list.append(obj)
                    add_oca_children(child, obj['childLayers'], path, group_mode)
                    continue
                item = child['item']
                entry, source = item['entry'], item['source']
                name_base = child['name']
                leaf_counter += 1
                # OCA's JSON arrays own layer order. Only the temporal frame
                # number belongs in the filename. Disambiguate genuinely
                # colliding names, including case-insensitive file systems.
                folder = [safe_component(x) for x in current_folder]
                stem = safe_component(name_base)
                number = str(frame).zfill(5)
                duplicate = 1
                while True:
                    label = stem if duplicate == 1 else f'{stem}-{duplicate}'
                    candidate = '/'.join([*folder, f'{label}_{number}{ext}'])
                    key = candidate.casefold()
                    if key not in path_taken:
                        path_taken.add(key)
                        break
                    duplicate += 1
                target = staging / candidate
                target.parent.mkdir(parents=True, exist_ok=True)
                if item.get('pixels') is not None:
                    pixels = item['pixels']
                    if depth == 8:
                        Image.fromarray((np.clip(pixels, 0, 1)*255+.5).astype(np.uint8), 'RGBA').save(target)
                    else:
                        write_blender_image(target, pixels, depth)
                else:
                    shutil.copyfile(source, target)
                # Keep the OCA canvas/layer size intact. Frames can have
                # independent cropped bounds and centered positions.
                left = top = 0
                cropped_width, cropped_height = width, height
                if job.get('trim_empty_pixels', True):
                    if depth in (8, 16):
                        from raster_trim import crop_png_file
                        left, top, cropped_width, cropped_height = crop_png_file(target)
                    else:
                        from raster_bounds import crop_rgba
                        pixels = read_rgba(target)
                        clipped, left, top = crop_rgba(pixels)
                        cropped_height, cropped_width = clipped.shape[:2]
                        if (left, top, cropped_width, cropped_height) != (0, 0, width, height):
                            write_blender_image(target, clipped, depth)
                rel = (Path(name) / candidate).as_posix()
                parts = [*current_folder, name_base]
                is_ref = bool(item.get('flags', set()) & {'ref', 'reference'})
                if entry.get('render_placeholder'):
                    notice(job, entry['name'] + ': disabled for rendering; hidden blank OCA placeholder created')
                layer = make_oca_layer(parts, effective_layer_mode(item, parent_blend), rel,
                                       width, height, depth, frame, leaf_counter, reference=is_ref,
                                       label=oca_label(item.get('inherited_color')))
                cel = layer['frames'][0]
                cel['position'] = [left + cropped_width / 2, top + cropped_height / 2]
                cel['width'], cel['height'] = cropped_width, cropped_height
                if entry.get('render_placeholder'):
                    layer['visible'] = False
                dest_list.append(layer)
        add_oca_children(stack, root_layers)
        data = {
            'name': name, 'frameRate': float(job.get('frame_rate', 24.)),
            'width': width, 'height': height, 'startTime': frame,
            'endTime': frame+1, 'colorDepth': {8:'U8',16:'U16',32:'F32'}[depth],
            'backgroundColor': [0,0,0,0], 'layers': root_layers, 'ocaVersion': '1.3.0',
        }
        manifest = dest.with_name(dest.name + '.writing')
        manifest.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding='utf-8')
        # Validation catches out-of-sync paths before touching prior deliverables.
        test = json.loads(manifest.read_text(encoding='utf-8'))
        if not test['layers']:
            raise ValueError('OCA has no image layers')
        old_assets = assets.with_name(assets.name + '.old-' + uuid.uuid4().hex[:7])
        if assets.exists():
            assets.rename(old_assets)
        try:
            staging.rename(assets)
            manifest.replace(dest)
        except Exception:
            if assets.exists():
                shutil.rmtree(assets, ignore_errors=True)
            if old_assets.exists():
                old_assets.rename(assets)
            raise
        if old_assets.exists():
            shutil.rmtree(old_assets, ignore_errors=True)
        print('OCA COMPLETE:', dest, 'layer files:', len(path_taken), flush=True)
        return str(dest)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        manifest = dest.with_name(dest.name + '.writing')
        manifest.unlink(missing_ok=True)


@timed('still_build_and_save')
def assemble_stills(job, inputs):
    """Per-destination additional stills. Individual = one per socket;
    Flatten = one composite. Leaves ordinary native File Output untouched.
    """
    ensure_pillow()
    import numpy as np
    from PIL import Image
    fmt = job['format']
    depth = int(job.get('depth', 8))
    allowed = {'PNG':(8,16),'EXR':(16,32),'TIFF':(8,16),'JPEG':(8,)}
    if depth not in allowed[fmt]:
        raise ValueError(f'{fmt} does not support {depth}-bit output in this build')
    destination = Path(job['dest'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    if job.get('flatten'):
        entries = [('Flattened', merge_layers(inputs, depth=depth))]
    else:
        entries = [(entry['name'], read_rgba(path, source_depth=(16 if job.get('extension')=='.png' and depth == 16 else 8)))
                   if path.suffix.lower() == '.png' else (entry['name'], read_rgba(path))
                   for entry, path in inputs]
    completed = []
    from collections import Counter
    collisions = Counter()
    profile = effective_profile(job.get('tag_profile', 'PASSTHROUGH'), fmt)
    for layer_name, rgba in entries:
        if job.get('flatten'):
            path = destination
        else:
            base_label = strip_tags(layer_name)
            try:
                base_label, tag_warnings = translate_label(base_label, layer_name, profile, 'layer')
                for warning in tag_warnings:
                    print('TAG NOTICE image series:', warning, flush=True)
            except Exception as exc:
                print('TAG WARNING image series registry unavailable:', exc, flush=True)
            label = safe_component(base_label)
            collisions[label] += 1
            suffix = '' if collisions[label] == 1 else f'-{collisions[label]}'
            path = destination.with_name(destination.stem + label + suffix + destination.suffix)
        if path.exists() and not job['overwrite']:
            raise FileExistsError('Overwrite disabled for ' + str(path))
        stage = path.with_name(path.stem + '.writing' + path.suffix)
        try:
            if fmt == 'PNG' and depth == 8:
                pixels = (np.clip(rgba, 0, 1) * 255 + 0.5).astype('uint8')
                Image.fromarray(pixels, 'RGBA').save(str(stage))
            else:
                write_blender_image(stage, rgba, depth, fmt=fmt)
            if not stage.exists() or stage.stat().st_size < 16:
                raise RuntimeError('Still image writer failed: ' + str(stage))
            stage.replace(path)
            completed.append(str(path))
        finally:
            stage.unlink(missing_ok=True)
    print('STILLS COMPLETE:', len(completed), fmt, flush=True)
    return completed[0] if len(completed) == 1 else f'{len(completed)} files in {destination.parent}'


@timed('svg_build_and_save')
def assemble_svg(job, inputs):
    """Write one self-contained, grouped SVG document."""
    ensure_pillow()
    from svg_document import write_svg_document
    return write_svg_document(job, inputs)


@profile_export
def assemble(job):
    job['_notices'] = []
    job['_publication'] = []
    job['_partial'] = False
    if job.get('format') == 'FONTS':
        from font_delivery import write_font_output
        return write_font_output(job)
    if job.get('format')=='OCA' and job.get('oca_frames'):
        from oca_sequence import assemble_oca_sequence
        return assemble_oca_sequence(job,assemble)
    source_inputs = find_inputs(job)
    # Apply .ignore to the actual pixel-layer selection BEFORE every writer,
    # including flattened images and files with Use Groups disabled.
    keep = prepared_entries(source_inputs, use_groups=False)
    inputs = [(x['entry'], x['source']) for x in keep]
    if not inputs:
        raise ValueError('Every layer was excluded by .ignore; no additional output was overwritten. Change the collection tag or choose other inputs.')
    print(f'Included {len(inputs)}/{len(source_inputs)} image layers after .ignore filtering', flush=True)
    fmt = job.get('format', 'PSD')
    if fmt == 'OCA':
        return assemble_oca(job, inputs)
    if fmt in ('PSD', 'PSB'):
        return assemble_psd(job, inputs)
    if fmt == 'SVG':
        return assemble_svg(job, inputs)
    if fmt in ('PNG','EXR','TIFF','JPEG'):
        return assemble_stills(job, inputs)
    raise ValueError('No writer available for ' + fmt)


def run(jobfile):
    data = json.loads(jobfile.read_text(encoding='utf-8'))
    for path in reversed(data.get('python_paths', [])):
        if isinstance(path, str) and path and Path(path).is_dir() and path not in sys.path:
            sys.path.insert(0, path)
    succeeded = failed = 0
    details = []
    for job in data['jobs']:
        try:
            print('Assembling:', job['dest'], flush=True)
            resolved = assemble(job)
            succeeded += 1
            details.append({'dest': resolved, 'success': True, 'notices': job.get('_notices', []),
                            'partial':bool(job.get('_partial')),
                            'publication':job.get('_publication',[]),
                            'performance': job.get('_performance', {})})
        except Exception as exc:
            failed += 1
            details.append({'dest': job.get('dest'), 'success': False, 'error': str(exc), 'notices': job.get('_notices', []),
                            'publication':job.get('_publication',[]),
                            'performance': job.get('_performance', {})})
            traceback.print_exc()
    result = {'succeeded': succeeded, 'failed': failed, 'details': details,
              'render_performance': data.get('render_performance', {})}
    from job_ownership import remove_completed_snapshots
    removed = remove_completed_snapshots(jobfile.parent)
    if removed:
        print('Removed completed temporary scene snapshots:', removed, flush=True)
    (jobfile.parent / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('RETAINED JOB:', jobfile.parent, flush=True)
    partial_count=sum(bool(detail.get('partial')) for detail in details)
    message=(f'ERROR: {failed} export(s) failed.' if failed else
             f'PARTIAL: {partial_count} export(s) contain omitted artwork; inspect publication diagnostics.' if partial_count else
             'SUCCESS: All export jobs completed.')
    print(message,flush=True)
    return 0 if not failed else 1


if __name__ == '__main__':
    try:
        index = sys.argv.index('--')
        sys.exit(run(Path(sys.argv[index + 1])))
    except Exception:
        traceback.print_exc()
        sys.exit(1)
