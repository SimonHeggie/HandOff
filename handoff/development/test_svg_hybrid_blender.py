"""Blender 5.3 integration test; creates only temporary fixtures and outputs.

Run with --factory-startup --disable-autoexec --python this_file.py.
No existing blend file is opened or saved. The worker snapshot is deliberately
reopened to exercise the same isolated-render path used during export.
"""
import base64
import io
import os
import sys
import tempfile
import traceback
from pathlib import Path
from xml.etree import ElementTree as ET
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    import bpy
    assert bpy.app.version[:2] == (5, 3), bpy.app.version_string
    from svg_export import export_view_layer_svg
    import svg_hybrid
    from svg_hybrid import resolve_hybrid_source, retained_hybrid, DEFERRED
    from pillow_loader import ensure_pillow
    ensure_pillow()
    from PIL import Image

    scene = bpy.context.scene
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 1
    scene.render.resolution_x = scene.render.resolution_y = 64
    scene.render.resolution_percentage = int(os.environ.get('HANDOFF_TEST_SCALE', '100'))
    expected_size = (64 * scene.render.resolution_percentage // 100,) * 2
    scene.render.film_transparent = True
    save_as_render = os.environ.get('HANDOFF_TEST_SAVE_AS_RENDER', '1') != '0'
    scene.view_settings.view_transform = 'Standard' if save_as_render else 'Filmic'
    scene.view_settings.look = 'None'
    camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    camera.location = (0, 0, 10)
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 6
    scene.camera = camera
    material = bpy.data.materials.new('Flat paint')
    bpy.data.materials.create_gpencil_data(material)
    material.grease_pencil.color = (.8, .1, .2, 1)
    material.grease_pencil.fill_color = (.2, .7, .4, 1)

    for index, name in enumerate(('Editable', 'Variable opacity', 'Mirror')):
        data = bpy.data.grease_pencils.new(name)
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location.x = (index - 1) * 1.8
        obj.use_grease_pencil_lights = False
        data.materials.append(material)
        layer = data.layers.new('Drawing', set_active=True)
        layer.use_lights = False
        drawing = layer.frames.new(0).drawing
        drawing.add_strokes([3])
        drawing.set_types(type='POLY')
        stroke = drawing.strokes[0]
        stroke.cyclic = True
        stroke.fill_id = 1
        for point, position in zip(stroke.points, ((-.6,-.6,0),(-.2,.6,0),(.2,-.6,0))):
            point.position = position
            point.radius = .05
            point.opacity = 1
        if name == 'Variable opacity':
            stroke.points[0].opacity = .2
        if name == 'Mirror':
            obj.modifiers.new('Mirror', 'GREASE_PENCIL_MIRROR')
        if name == 'Editable':
            foreground=data.layers.new('Foreground',set_active=True)
            foreground.use_lights=True
            foreground.opacity=.45
            drawing=foreground.frames.new(0).drawing
            drawing.add_strokes([3]);drawing.set_types(type='POLY')
            stroke=drawing.strokes[0];stroke.cyclic=True;stroke.fill_id=1
            for point,position in zip(stroke.points,((-.1,-.3,0),(.3,.4,0),(.6,-.3,0))):
                point.position=position;point.radius=.05;point.opacity=1
    scene.frame_set(0)
    view = bpy.context.view_layer
    view.update()
    # A newly added drawing layer defaults to using lights. Reproduce the
    # exact blocker, then verify that object-wide unlit mode covers all layers.
    editable=bpy.data.objects['Editable']
    editable.use_grease_pencil_lights=True;view.update()
    try:
        svg_hybrid._evaluated_artwork(scene,view,editable,view.depsgraph)
    except svg_hybrid.vectors.VectorFallback as exc:
        assert 'Foreground' in str(exc) and 'lighting is enabled' in str(exc),exc
    else:
        raise AssertionError('Lighting on an additional drawing layer was ignored')
    editable.use_grease_pencil_lights=False;view.update()
    depth = int(os.environ.get('HANDOFF_TEST_DEPTH', '8'))
    with tempfile.TemporaryDirectory(prefix='handoff-hybrid-test-') as directory:
        path = Path(directory)/'source.svg'
        original_path = bpy.data.filepath
        original_view = scene.view_settings.view_transform
        original_format = (scene.render.image_settings.file_format,
                           scene.render.image_settings.color_depth,
                           scene.render.image_settings.color_mode)
        original_ids = (len(bpy.data.scenes), len(bpy.data.images))
        variable = bpy.data.objects['Variable opacity']
        variable.hide_render = True
        view.update()
        pure = Path(directory)/'pure.svg'
        ok, reason = export_view_layer_svg(scene, view, pure, hybrid=True, allow_raster=False,
                                           save_as_render=save_as_render)
        assert ok, reason
        assert not retained_hybrid(pure), 'Pure vectors must remain refreshable on retry'
        variable.hide_render = False
        view.update()
        # F12 must queue a snapshot without evaluating GP or creating/deleting
        # palette scenes while the viewport and render threads are active.
        with patch.object(svg_hybrid, '_scene_colors', side_effect=AssertionError('render_pre palette')), \
                patch.object(svg_hybrid, '_evaluated_artwork', side_effect=AssertionError('render_pre evaluation')):
            ok, reason = export_view_layer_svg(scene, view, path, hybrid=True,
                                               save_as_render=save_as_render, deferred=True)
        assert ok, reason
        assert bpy.data.filepath == original_path, 'Snapshot changed the source file path'
        assert scene.view_settings.view_transform == original_view
        assert original_format == (scene.render.image_settings.file_format,
                                   scene.render.image_settings.color_depth,
                                   scene.render.image_settings.color_mode)
        assert original_ids == (len(bpy.data.scenes), len(bpy.data.images)), 'Palette IDs leaked'
        assert not any(o.hide_render for o in scene.objects), 'Source visibility changed'
        root = ET.parse(path).getroot()
        assert root.get(DEFERRED), 'F12 evaluated the source instead of deferring it'
        assert not list(root.iter('{http://www.w3.org/2000/svg}path'))
        assert resolve_hybrid_source(path, depth=depth)
        root = ET.parse(path).getroot()
        assert root.get(DEFERRED) is None
        objects = [n.get('data-handoff-object') for n in root.iter() if n.get('data-handoff-object')]
        assert sorted(objects) == ['Editable', 'Mirror'], objects
        group=next(n for n in root.iter() if n.get('data-handoff-object')=='Editable')
        assert [n.get('data-handoff-layer') for n in group]==['Drawing','Foreground']
        assert abs(float(group[1].get('opacity'))-.45)<.00001
        assert all(list(n.iter('{http://www.w3.org/2000/svg}path')) for n in group)
        resolve_hybrid_source(path, depth=depth)
        assert retained_hybrid(path)
        root = ET.parse(path).getroot()
        images = list(root.iter('{http://www.w3.org/2000/svg}image'))
        assert len(images) == 1
        data = base64.b64decode(images[0].get('href').split(',',1)[1])
        assert data[24] == depth, 'Raster fallback precision changed'
        with Image.open(io.BytesIO(data)) as image:
            assert image.size == expected_size, (image.size, expected_size)
            assert image.getchannel('A').getextrema()[1] > 0
        assert len(list(root.iter('{http://www.w3.org/2000/svg}path'))) >= 2
        # A completed source is self-contained; retry needs no scene or render.
        resolve_hybrid_source(path)
        # A deferred source containing no supported vector must fall back to
        # the full cache and leave Retry usable, rather than an empty SVG plan.
        scene = bpy.context.scene
        for obj in scene.objects:
            if obj.type == 'GREASEPENCIL':
                obj.hide_render = obj.name != 'Variable opacity'
        raster_only = Path(directory)/'raster-only.svg'
        ok, reason = export_view_layer_svg(scene, bpy.context.view_layer, raster_only,
                                           hybrid=True, deferred=True)
        assert ok, reason
        assert not resolve_hybrid_source(raster_only, depth=depth)
        assert not raster_only.exists()
        assert not retained_hybrid(raster_only)
        # Pure vector sources still resolve without requesting raster renders.
        scene = bpy.context.scene
        for obj in scene.objects:
            if obj.type == 'GREASEPENCIL':
                obj.hide_render = obj.name == 'Variable opacity'
        pure_deferred = Path(directory)/'pure-deferred.svg'
        ok, reason = export_view_layer_svg(scene, bpy.context.view_layer, pure_deferred,
                                           hybrid=True, deferred=True)
        assert ok, reason
        assert resolve_hybrid_source(pure_deferred, depth=depth)
        assert not retained_hybrid(pure_deferred)
        pure_root = ET.parse(pure_deferred).getroot()
        assert len(list(pure_root.iter('{http://www.w3.org/2000/svg}path'))) >= 2
        assert not list(pure_root.iter('{http://www.w3.org/2000/svg}image'))
    print('PASS: deferred preparation, editable neighbour, evaluated modifier, isolated fallback and retained retry', flush=True)


if __name__ == '__main__':
    try:
        run()
    except BaseException:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
