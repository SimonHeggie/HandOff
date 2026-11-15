"""Blender 5.3 rendered material-gradient fixtures, without user project data.

Run with --factory-startup --disable-autoexec. Set COMP_IO_TEST_OUTPUT to a
private writable directory. Compare exported SVGs in an independent renderer.
"""
import os
import sys
import traceback
import tempfile
from pathlib import Path
from math import radians
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(folder):
    import bpy
    from pillow_loader import ensure_pillow
    ensure_pillow()
    from svg_hybrid import export_hybrid_svg
    from render_temp import ensure_render_tempdir
    assert bpy.app.version[:2] == (5, 3)
    scene = bpy.context.scene
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.use_compositing = False
    scene.render.dither_intensity = 0
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    settings = scene.render.image_settings
    settings.file_format = 'PNG'; settings.color_mode = 'RGBA'; settings.color_depth = '16'
    camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    camera.location = (0, 0, 10)
    camera.data.type = 'ORTHO'; camera.data.ortho_scale = 4
    scene.camera = camera
    gp = bpy.data.grease_pencils.new('Data')
    obj = bpy.data.objects.new('Gradient', gp)
    scene.collection.objects.link(obj)
    obj.use_grease_pencil_lights = False
    mat = bpy.data.materials.new('Ramp')
    bpy.data.materials.create_gpencil_data(mat)
    gp.materials.append(mat)
    style = mat.grease_pencil
    style.fill_style = 'GRADIENT'; style.fill_color = (.2, .6, .9, .2); style.color = (0, 0, 0, 0)
    style.texture_scale = (1.8, 1.4); style.texture_offset = (-1, -1)
    layer = gp.layers.new('Paint', set_active=True)
    layer.use_lights = False
    drawing = layer.frames.new(0).drawing
    drawing.add_strokes([4]); drawing.set_types(type='POLY')
    stroke = drawing.strokes[0]
    stroke.cyclic = True; stroke.fill_id = 1; stroke.hide_stroke = True
    for p, co in zip(stroke.points, ((-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0))):
        p.position = co; p.opacity = 1
    ramp = style.gradient
    ramp.elements[0].color = (.05, .4, 1, .15)
    ramp.elements[-1].color = (1, .05, .1, .9)
    ramp.elements.new(.37).color = (.8, .4, .05, .5)
    scene.frame_set(0)
    view = bpy.context.view_layer
    ids = (len(bpy.data.scenes), len(bpy.data.objects), len(bpy.data.images))
    for name, kind, interpolation in (('linear', 'LINEAR', 'LINEAR'),
                                       ('radial', 'RADIAL', 'EASE'),
                                       ('constant', 'RADIAL', 'CONSTANT'),
                                       ('uv', 'RADIAL', 'B_SPLINE')):
        style.gradient_type = kind; ramp.interpolation = interpolation
        if name == 'uv':
            style.texture_angle = .4
            drawing.attributes.new('uv_rotation', 'FLOAT', 'CURVE').data[0].value = .2
            drawing.attributes.new('uv_translation', 'FLOAT2', 'CURVE').data[0].vector = (.15, -.1)
            drawing.attributes.new('uv_scale', 'FLOAT2', 'CURVE').data[0].vector = (1.1, .8)
            drawing.tag_positions_changed()
            obj.rotation_euler.z = radians(12)
        view.update()
        path = folder/(name+'.svg')
        ok, reason = export_hybrid_svg(scene, view, path)
        assert ok, reason
        root = ET.parse(path).getroot()
        assert not list(root.iter('{http://www.w3.org/2000/svg}image'))
        stops = list(root.iter('{http://www.w3.org/2000/svg}stop'))
        assert len(stops) == len(ramp.elements) == 3
        assert [round(float(s.get('offset')), 5) for s in stops] == [round(e.position, 5) for e in ramp.elements]
        assert [round(float(s.get('stop-opacity')), 5) for s in stops] == [round(e.color[3], 5) for e in ramp.elements]
        assert ids == (len(bpy.data.scenes), len(bpy.data.objects), len(bpy.data.images))
        ensure_render_tempdir(bpy.app.tempdir)
        bpy.ops.render.render(scene=scene.name, layer=view.name)
        bpy.data.images['Render Result'].save_render(str(folder/(name+'-native.png')), scene=scene)
        ids = (len(bpy.data.scenes), len(bpy.data.objects), len(bpy.data.images))
    style.use_fill_holdout = True
    view.update()
    ok, reason = export_hybrid_svg(scene, view, folder/'holdout.svg')
    assert not ok and 'Holdout' in reason and 'Color Ramp stop alpha' in reason, reason
    ensure_render_tempdir(bpy.app.tempdir)
    bpy.ops.render.render(scene=scene.name, layer=view.name)
    image = bpy.data.images['Render Result']
    image.save_render(str(folder/'holdout-native.png'), scene=scene)
    from png16_pixels import read_png16_rgba
    assert not read_png16_rgba(folder/'holdout-native.png')[..., 3].any()
    # A holdout-only object next to vector paint must keep a transparent
    # fallback and tell the user why, without inventing visible paint.
    neighbor = obj.copy(); neighbor.data = gp.copy(); neighbor.name = 'Paint neighbor'
    neighbor.data.materials.clear()
    paint_material = mat.copy(); paint_material.grease_pencil.use_fill_holdout = False
    neighbor.data.materials.append(paint_material)
    scene.collection.objects.link(neighbor); neighbor.location.x = 1
    view.update()
    with tempfile.TemporaryDirectory(prefix='mixed-', dir=folder) as directory:
        path = Path(directory)/'mixed.svg'
        ok, reason = export_hybrid_svg(scene, view, path)
        assert ok, reason
        from svg_hybrid import resolve_hybrid_source
        messages = []
        assert resolve_hybrid_source(path, logger=lambda *args: messages.append(' '.join(map(str, args))))
        assert any('SVG EMPTY RASTER GROUP' in msg and 'Holdout' in msg for msg in messages), messages
    print('GRADIENT_NATIVE_PASS', folder, flush=True)


if __name__ == '__main__':
    try:
        folder = Path(os.environ['COMP_IO_TEST_OUTPUT']); folder.mkdir(parents=True, exist_ok=True)
        run(folder)
    except BaseException:
        traceback.print_exc(); sys.stdout.flush(); sys.stderr.flush(); os._exit(1)
    sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
