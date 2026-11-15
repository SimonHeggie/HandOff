"""Whole-object SVG extraction and ordered, isolated GP raster fallbacks.

Render preparation only checks source eligibility and writes a snapshot.
Evaluated geometry, colour conversion and isolated renders run in the worker,
away from the interactive render/viewport threads. Source projects are never
saved. A resolved sidecar is self-contained and reusable without a render.
"""

try:
    from .svg_compat import normalize_metadata
except ImportError:
    try:
        from svg_compat import normalize_metadata
    except ImportError:
        # Standalone test fixtures may deliberately copy only core helper modules.
        def normalize_metadata(root):
            return root

try:
    from .branding import LOG_PREFIX
except ImportError:
    from branding import LOG_PREFIX
import base64
import json
import tempfile
import uuid
from pathlib import Path
try:
    from .export_performance import timed
except ImportError:
    from export_performance import timed
from xml.etree import ElementTree as ET
try:
    from .runtime_paths import SNAPSHOT_SUFFIX, SNAPSHOT_KIND
except ImportError:
    from runtime_paths import SNAPSHOT_SUFFIX, SNAPSHOT_KIND

try:
    from . import svg_export as vectors
    from .png16_pixels import read_png16_rgba
except ImportError:
    import svg_export as vectors
    from png16_pixels import read_png16_rgba

SVG = '{http://www.w3.org/2000/svg}'
INK = '{http://www.inkscape.org/namespaces/inkscape}'
HYBRID = 'data-handoff-hybrid'
RESOLVED = 'data-handoff-raster-resolved'
PLAN = 'data-handoff-raster-plan'
REQUEST = 'data-handoff-raster-request'
DEFERRED = 'data-handoff-source-plan'
HYBRID_API_VERSION = 13
LAYER_BLENDS = 'data-handoff-svg-layer-blends'
BLEND_VERSION = 'data-handoff-blend-version'

# Native fixtures exercise these modifiers. Other evaluated GP geometry is
# accepted only when the same geometry/paint checks succeed.
EVALUATED_MODIFIERS = frozenset({
    'GREASE_PENCIL_NOISE', 'GREASE_PENCIL_THICKNESS', 'GREASE_PENCIL_OPACITY',
    'GREASE_PENCIL_TINT', 'GREASE_PENCIL_SUBDIV', 'GREASE_PENCIL_SMOOTH',
    'GREASE_PENCIL_MIRROR', 'GREASE_PENCIL_OFFSET', 'GREASE_PENCIL_DASH',
    'GREASE_PENCIL_OUTLINE', 'GREASE_PENCIL_LENGTH', 'GREASE_PENCIL_SIMPLIFY',
})


def ordered_components(rows):
    """Batch only consecutive raster objects; never cross a vector boundary."""
    components, requests = [], []
    for row in rows:
        if row['kind'] == 'vector':
            components.append(row['artwork'])
            continue
        if (not components or components[-1].get('svg_kind') != 'RASTER' or
                components[-1].get('collection_parts', []) != row.get('collection_parts', [])):
            requests.append([])
            components.append(dict(svg_kind='RASTER', request=len(requests)-1,
                                   name='Rendered artwork', collection_parts=row.get('collection_parts', [])))
        requests[-1].append(dict(name=row['name'], reason=row['reason']))
        names = requests[-1]
        components[-1]['name'] = (names[0]['name'] if len(names) == 1 else
                                  f'Rendered artwork ({len(names)} objects)')
    return components, requests


try:
    from .vector_artwork import scene_colors as _scene_colors
except ImportError:
    from vector_artwork import scene_colors as _scene_colors



def _evaluated_artwork(scene, view_layer, obj, depsgraph, camera=None, *,
                       editable_layer_blends=False):
    try:
        from .vector_artwork import evaluated_artwork
    except ImportError:
        from vector_artwork import evaluated_artwork
    return evaluated_artwork(scene,view_layer,obj,depsgraph,camera=camera,
                             editable_layer_blends=editable_layer_blends)


def _source_objects(scene, view_layer):
    """Read-only eligibility checks; do not evaluate or override UI context."""
    camera = scene.camera
    if camera is None or camera.data.type != 'ORTHO':
        raise vectors.VectorFallback('SVG requires an orthographic render camera')
    if not scene.render.film_transparent:
        raise vectors.VectorFallback('Transparent film required for SVG')
    if camera.data.dof.use_dof or scene.render.use_motion_blur:
        raise vectors.VectorFallback('Depth of field or motion blur requires PNG')
    objects = [o for o in vectors._camera_visible_objects(view_layer)
               if not o.hide_render and getattr(o, 'visible_camera', True)
               and o.type not in ('CAMERA', 'LIGHT', 'LIGHT_PROBE', 'ARMATURE', 'EMPTY')]
    if any(o.type not in ('GREASEPENCIL', 'CURVE', 'FONT') for o in objects):
        raise vectors.VectorFallback('Mixed 3D geometry requires complete rendered PNG')
    if any(o.holdout_get(view_layer=view_layer) for o in objects):
        raise vectors.VectorFallback('Cross-object holdout requires complete rendered PNG')
    if not objects:
        raise vectors.VectorFallback('No independently supported vector objects; use cached PNG')
    return camera, objects


def _write_snapshot(scene, path):
    import bpy
    try:
        from .svg_metadata import source_metadata,ensure_unique_ids
    except ImportError:
        from svg_metadata import source_metadata,ensure_unique_ids
    ensure_unique_ids(scene)
    for obj in scene.objects:
        if obj.type in ('GREASEPENCIL','CURVE','FONT'):
            source_metadata(scene,obj)
    snapshot = path.with_name(path.stem + '-' + uuid.uuid4().hex[:10] + '.blend')
    bpy.data.libraries.write(str(snapshot), {scene}, path_remap='ABSOLUTE', compress=True)
    Path(str(snapshot) + SNAPSHOT_SUFFIX).write_text(json.dumps(
        dict(kind=SNAPSHOT_KIND, file=snapshot.name)))
    return snapshot


def queue_hybrid_svg(scene, view_layer, path, *, save_as_render=True, flat_text_material=False,
                     collection_root='', font_directory='', use_font_directory=True,
                     editable_layer_blends=True):
    """Capture source state without touching evaluated geometry or UI context.

    This is the F12/render_pre entry point. In particular, scene.copy/remove,
    context overrides and depsgraph updates must stay in the conversion worker.
    """
    path = Path(path)
    try:
        _source_objects(scene, view_layer)
        path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = _write_snapshot(scene, path)
        try:
            import bpy
            source_origin = bpy.data.filepath
        except ImportError:
            source_origin = ''  # Allows Blender-free preparation fixtures.
        width, height = vectors._render_size(scene)
        root = ET.Element(SVG + 'svg', {'viewBox': f'0 0 {width} {height}'})
        root.set(DEFERRED, json.dumps(dict(snapshot=str(snapshot), scene=scene.name,
                                          source_origin=source_origin,
                                          view_layer=view_layer.name, frame=scene.frame_current,
                                          save_as_render=bool(save_as_render),
                                          flat_text_material=bool(flat_text_material),
                                          editable_layer_blends=bool(editable_layer_blends),
                                          collection_root=collection_root, font_directory=font_directory,
                                          use_font_directory=bool(use_font_directory))))
        ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
        return True, 'SVG object evaluation queued in conversion worker'
    except (vectors.VectorFallback, AttributeError, ValueError, TypeError, RuntimeError) as exc:
        return False, str(exc)


def export_hybrid_svg(scene, view_layer, path, *, save_as_render=True, allow_raster=True,
                      snapshot_path=None, flat_text_material=False, collection_root='',
                      font_directory='', use_font_directory=True, editable_layer_blends=True,
                      source_origin=None):
    """Classify whole objects and save an ordered vector/raster source sidecar."""
    path = Path(path)
    try:
        camera, objects = _source_objects(scene, view_layer)
        try:
            from .svg_metadata import ensure_unique_ids
        except ImportError:
            from svg_metadata import ensure_unique_ids
        ensure_unique_ids(scene)
        try:
            from .svg_collections import collection_paths, group_svg
            from .layer_stack import tags
        except ImportError:
            from svg_collections import collection_paths, group_svg
            from layer_stack import tags
        object_paths = collection_paths(view_layer, collection_root)
        import bpy
        try:
            from .collection_colors import source_collection_colors, theme_collection_colors
        except ImportError:
            from collection_colors import source_collection_colors, theme_collection_colors
        palette = theme_collection_colors(bpy)
        root_colors = source_collection_colors(collection_root, bpy.data.collections, palette)
        if any('merge' in tags(p) for parts in object_paths.values() for p in parts):
            raise vectors.VectorFallback('Nested Collection .merge requires the complete rendered source')
        rows = []
        ignored = False
        # The explicit source layer avoids changing the window's context.
        depsgraph = view_layer.depsgraph
        depsgraph.update()
        camera = camera.evaluated_get(depsgraph)
        # Objects excluded from the active UI view layer can have stale
        # original matrices. Sort with the actual source layer's evaluation.
        ordered = sorted(objects, key=lambda o: -vectors._object_camera_depth(
            scene, camera, o.evaluated_get(depsgraph)))
        for obj in ordered:
            parts = object_paths.get(obj.name, [])
            if any('ignore' in tags(p) for p in parts):
                ignored = True
                continue
            try:
                camera=scene.camera.evaluated_get(depsgraph)
                if obj.type == 'GREASEPENCIL':
                    try:
                        artwork = _evaluated_artwork(scene, view_layer, obj, depsgraph, camera,
                                                     editable_layer_blends=editable_layer_blends)
                    except vectors.VectorFallback as exc:
                        variable_width=str(exc).startswith('Variable-width visible stroke')
                        if not variable_width and not str(exc).startswith('Varying per-point opacity'):
                            raise
                        try:
                            try:
                                from .svg_pressure import artwork as pressure_artwork
                            except ImportError:
                                from svg_pressure import artwork as pressure_artwork
                            artwork=pressure_artwork(scene,view_layer,obj,depsgraph,
                                                     editable_layer_blends=editable_layer_blends)
                        except vectors.VectorFallback:
                            if not variable_width:
                                raise
                            try:
                                from .svg_width import expanded_stroke
                            except ImportError:
                                from svg_width import expanded_stroke
                            artwork=expanded_stroke(scene,view_layer,obj,depsgraph)
                elif obj.type == 'CURVE':
                    artwork = vectors._curve_from_blender(scene, camera, obj.evaluated_get(depsgraph))
                else:
                    artwork = vectors._font_from_blender(scene, camera, obj.evaluated_get(depsgraph),
                                                         flat_material=flat_text_material,
                                                         font_directory=font_directory,
                                                         use_font_directory=use_font_directory,
                                                         font_cache=path.parent)
                if artwork is None:
                    continue  # No drawing assigned to this frame/view layer.
                try:
                    from .svg_metadata import source_metadata
                except ImportError:
                    from svg_metadata import source_metadata
                artwork['source_metadata'] = source_metadata(scene,obj)
                # Validate compound-fill ordering before accepting this
                # object, so a later object cannot invalidate its neighbours.
                vectors.encode_svg(*vectors._render_size(scene), [artwork])
                artwork['collection_parts'] = parts
                artwork['collection_colors'] = source_collection_colors(parts, bpy.data.collections, palette)
                artwork['inherited_color'] = next((c for c in reversed(root_colors + artwork['collection_colors']) if c), '')
                if obj.type == 'GREASEPENCIL':
                    try:
                        from .svg_instances import instance_metadata
                    except ImportError:
                        from svg_instances import instance_metadata
                    info = instance_metadata(artwork, obj, bpy.data.filepath if source_origin is None else source_origin, scene.frame_current)
                    if info:
                        artwork['svg_instance'] = info
                if any(stroke.get('pressure') for layer in artwork.get('layers',[])
                       for stroke in layer['strokes']):
                    print(f'{LOG_PREFIX} WARNING: SVG pressure approximated:',obj.name,
                          '| editable PowerStroke width and/or independent opacity gradient; '
                          'portable outline and gradient interpolation can differ from Blender',flush=True)
                rows.append(dict(kind='vector', name=obj.name, artwork=artwork, collection_parts=parts))
                print(f'{LOG_PREFIX} SVG OBJECT:', obj.name, '| editable vector', flush=True)
            except (vectors.VectorFallback, AttributeError, ValueError, TypeError, IndexError) as exc:
                rows.append(dict(kind='raster', name=obj.name, reason=str(exc), collection_parts=parts))
                print(f'{LOG_PREFIX} SVG OBJECT:', obj.name, '| raster:', exc, flush=True)
        count = sum(row['kind'] == 'vector' for row in rows)
        if not count and not ignored:
            reasons = list(dict.fromkeys(row['reason'] for row in rows if row['kind']=='raster'))
            raise vectors.VectorFallback('No independently supported vector objects; use cached PNG' +
                                         (': ' + '; '.join(reasons) if reasons else ''))
        gradient_count = sum(any(stroke.get('fill_gradient') for layer in row['artwork'].get('layers', [])
                                 for stroke in layer['strokes']) for row in rows if row['kind']=='vector')
        if gradient_count:
            print(f'{LOG_PREFIX} SVG GRADIENTS:', gradient_count,
                  '| Authored ramp stops preserved one for one; Bézier/polygon geometry preserved.'
                  ' SVG interpolates between these stops; Blender Ease/B-spline/HSV interpolation,'
                  ' scene colour management and overlapping transparency can differ', flush=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from .svg_bounds import artwork_bounds, text_bounds
        except ImportError:
            from svg_bounds import artwork_bounds, text_bounds
        for row in rows:
            if row['kind']=='vector':row['artwork']['bounds']=artwork_bounds(row['artwork'])
        text_bounds(scene,view_layer,rows,font_directory,use_font_directory,path.parent)
        components, requests = ordered_components(rows)
        for family in sorted({row['artwork']['family'] for row in rows if row['kind']=='vector'
                              and row['artwork'].get('svg_kind')=='FONT'
                              and row['artwork'].get('font_builtin',False)}):
            print(f'{LOG_PREFIX} FONT:',family,
                  '| original font reference; use a Fonts / Text Assets output to deliver font files',flush=True)
        if requests and not allow_raster:
            raise vectors.VectorFallback('Object fallback pixels need F12; using retained full PNG')
        _scene_colors(scene, components, path.parent, save_as_render)
        try:
            from .vector_artwork import write_artwork
        except ImportError:
            from vector_artwork import write_artwork
        write_artwork(path.with_suffix('.vectors.json'),*vectors._render_size(scene),components)
        root = ET.fromstring(vectors.encode_svg(*vectors._render_size(scene), components))
        root.set(LAYER_BLENDS, '1' if editable_layer_blends else '0')
        root.set(BLEND_VERSION, '2')
        if editable_layer_blends and any(
                layer.get('blend_mode', 'REGULAR') not in ('REGULAR', 'NORMAL')
                for row in rows if row['kind'] == 'vector'
                for layer in row['artwork'].get('layers', [])):
            modes=sorted({layer.get('blend_mode','REGULAR') for row in rows if row['kind']=='vector'
                          for layer in row['artwork'].get('layers',[])
                          if layer.get('blend_mode','REGULAR') not in ('REGULAR','NORMAL')})
            print(f'{LOG_PREFIX} WARNING: SVG layer blend appearance approximated: '+
                  ', '.join(mode+' -> '+vectors.GP_SVG_BLENDS[mode] for mode in modes)+
                  '. GP transparency and scene colour management can differ from Blender', flush=True)
        for element,artwork in zip(root,components):
            element.set('data-handoff-bounds',json.dumps(artwork.get('bounds')))
        group_svg(root, components)
        if not requests:
            try:
                from .svg_collections import consolidate_collections
            except ImportError:
                from svg_collections import consolidate_collections
            consolidate_collections(root)
        if requests:
            root.set(HYBRID, '1')
            snapshot = Path(snapshot_path) if snapshot_path is not None else _write_snapshot(scene, path)
            root.set(PLAN, json.dumps(dict(snapshot=str(snapshot), scene=scene.name,
                                          view_layer=view_layer.name, frame=scene.frame_current,
                                          save_as_render=bool(save_as_render), requests=requests)))
        ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
        raster_count = sum(len(r) for r in requests)
        return True, (f'SVG: {count} editable objects; {raster_count} raster objects '
                      f'in {len(requests)} ordered fallback groups')
    except (vectors.VectorFallback, AttributeError, ValueError, TypeError, IndexError, RuntimeError) as exc:
        return False, str(exc)


def retained_hybrid(path, *, editable_layer_blends=None):
    """Retry keeps coupled vector/raster artwork from the same retained render."""
    if not path or not Path(path).is_file():
        return False
    root = ET.parse(path).getroot()
    normalize_metadata(root)
    if root.get(DEFERRED):
        raise ValueError('SVG source preparation is incomplete; render with F12 to rebuild it')
    if root.get(HYBRID) != '1':
        return False
    if root.get(RESOLVED) != '1':
        raise ValueError('SVG object fallback cache is incomplete; render with F12 to rebuild it')
    if (editable_layer_blends is not None and
            (root.get(LAYER_BLENDS, '0') == '1') != bool(editable_layer_blends)):
        raise ValueError('Editable SVG Layer Blends changed; render with F12 to rebuild the retained SVG artwork')
    if editable_layer_blends and root.get(BLEND_VERSION) != '2':
        raise ValueError('SVG blend approximation support changed; render with F12 to rebuild retained artwork')
    return True


def _load_snapshot(path, plan):
    """Open only snapshots belonging to this retained source directory."""
    import bpy
    snapshot = Path(plan['snapshot']).resolve()
    if snapshot.parent != path.resolve().parent or not snapshot.is_file():
        raise ValueError('SVG object fallback snapshot is missing from the retained job')
    bpy.ops.wm.open_mainfile(filepath=str(snapshot), load_ui=False, use_scripts=False)
    scene = bpy.data.scenes[plan['scene']]
    view_layer = scene.view_layers[plan['view_layer']]
    bpy.context.window.scene = scene
    bpy.context.window.view_layer = view_layer
    scene.frame_set(int(plan['frame']))
    return scene, view_layer, snapshot


@timed('vector_source_resolution')
def resolve_hybrid_source(path, *, depth=8, logger=print):
    """Worker-only preparation; False explicitly requests the full cached PNG."""
    path = Path(path)
    tree = ET.parse(path)
    root = tree.getroot()
    normalize_metadata(root)
    loaded = None
    if root.get(DEFERRED):
        plan = json.loads(root.attrib[DEFERRED])
        loaded = _load_snapshot(path, plan)
        scene, view_layer, snapshot = loaded
        ok, reason = export_hybrid_svg(scene, view_layer, path,
                                       save_as_render=plan['save_as_render'],
                                       snapshot_path=snapshot,
                                       flat_text_material=plan.get('flat_text_material', False),
                                       editable_layer_blends=plan.get('editable_layer_blends', False),
                                       collection_root=plan.get('collection_root', ''),
                                       font_directory=plan.get('font_directory', ''),
                                       use_font_directory=plan.get('use_font_directory', True),
                                       source_origin=plan.get('source_origin'))
        logger(f'{LOG_PREFIX} SVG SOURCE:', plan['scene'] + '/' + plan['view_layer'],
               '| vector' if ok else '| PNG fallback', '(' + reason + ')')
        if not ok:
            # An accepted render-time candidate may prove entirely raster in
            # the worker. Do not leave an unfinished plan that blocks Retry.
            path.unlink()
            return False
        tree = ET.parse(path)
        root = tree.getroot()
        normalize_metadata(root)
    if root.get(HYBRID) != '1' or root.get(RESOLVED) == '1':
        return True
    import bpy
    plan = json.loads(root.attrib[PLAN])
    scene, view_layer, _ = loaded or _load_snapshot(path, plan)
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    for layer in scene.view_layers:
        layer.use = layer == view_layer
    # Hide supported vector text/curves too: they must not be duplicated in
    # every GP raster group. Unsupported text remains its own fallback object.
    artwork_objects = [o for o in scene.objects if o.type in ('GREASEPENCIL', 'CURVE', 'FONT')]
    original_hidden = {o.name: o.hide_render for o in artwork_objects}
    settings = scene.render.image_settings
    settings.media_type = 'IMAGE'
    settings.file_format = 'PNG'
    settings.color_mode = 'RGBA'
    settings.color_depth = '16' if depth == 16 else '8'
    settings.color_management = 'FOLLOW_SCENE'
    if not plan['save_as_render']:
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
        scene.view_settings.exposure = 0
        scene.view_settings.gamma = 1
        scene.view_settings.use_curve_mapping = False
    images = {int(n.get(REQUEST)): (n if n.tag == SVG+'image' else n.find(SVG + 'image'))
              for n in root.iter() if n.get(REQUEST) is not None}
    with tempfile.TemporaryDirectory(prefix='object-renders-', dir=str(path.parent)) as folder:
        from render_temp import ensure_render_tempdir
        for index, request in enumerate(plan['requests']):
            wanted = {row['name'] for row in request}
            if not wanted <= set(original_hidden):
                raise ValueError('SVG fallback objects are missing from the scene snapshot')
            for obj in artwork_objects:
                obj.hide_render = original_hidden[obj.name] or obj.name not in wanted
            view_layer.update()
            logger(f'{LOG_PREFIX} SVG RASTER GROUP:', index+1, '/', len(plan['requests']),
                   '|', ', '.join(sorted(wanted)))
            ensure_render_tempdir(bpy.app.tempdir, logger=logger)
            bpy.ops.render.render(scene=scene.name, layer=view_layer.name, write_still=False)
            image_path = Path(folder) / f'{index:04d}.png'
            bpy.data.images['Render Result'].save_render(str(image_path), scene=scene)
            try:
                from .svg_bounds import image_bounds
            except ImportError:
                from svg_bounds import image_bounds
            bounds = image_bounds(image_path)
            images[index].set('data-handoff-bounds',json.dumps(bounds))
            if bounds is None or bounds == [0, 0, 0, 0]:
                logger(f'{LOG_PREFIX} SVG EMPTY RASTER GROUP:', ', '.join(sorted(wanted)),
                       '| Blender rendered zero alpha. Object fallback reasons:',
                       '; '.join(dict.fromkeys(row['reason'] for row in request)))
            images[index].set('href', 'data:image/png;base64,' +
                              base64.b64encode(image_path.read_bytes()).decode('ascii'))
            images[index].set(INK + 'label', 'Raster fallback')
    root.set(RESOLVED, '1')
    del root.attrib[PLAN]
    try:
        from .svg_collections import unwrap_raster_groups, consolidate_collections
    except ImportError:
        from svg_collections import unwrap_raster_groups, consolidate_collections
    unwrap_raster_groups(root)
    merged=consolidate_collections(root)
    logger(f'{LOG_PREFIX} SVG COLLECTIONS: consolidated',merged,'non-overlapping collection segments')
    stage = path.with_name(path.name + '.writing')
    try:
        tree.write(stage, encoding='utf-8', xml_declaration=True)
        stage.replace(path)
    finally:
        stage.unlink(missing_ok=True)
    return True
