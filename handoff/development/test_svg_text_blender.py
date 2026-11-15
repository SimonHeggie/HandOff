"""Real Blender 5.3 GP/live-text isolation, material and naming integration."""
import base64
import io
import os
from pathlib import Path
import sys
import tempfile
import traceback
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SVG = '{http://www.w3.org/2000/svg}'
INK = '{http://www.inkscape.org/namespaces/inkscape}'


def run():
    import bpy
    from pillow_loader import ensure_pillow
    ensure_pillow()
    from PIL import Image
    from svg_export import export_view_layer_svg
    from svg_hybrid import resolve_hybrid_source
    assert bpy.app.version[:2] == (5,3)
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
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    camera.location = (0,0,10)
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 8
    scene.camera = camera

    def shader_material(name, node_type, color):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
        shader = mat.node_tree.nodes.new(node_type)
        if node_type == 'ShaderNodeEmission':
            # A linked constant colour must be read from the actual graph.
            rgb = mat.node_tree.nodes.new('ShaderNodeRGB')
            rgb.outputs['Color'].default_value = color
            mat.node_tree.links.new(rgb.outputs['Color'], shader.inputs['Color'])
            shader.inputs['Strength'].default_value = 1
        else:
            shader.inputs['Base Color'].default_value = color
            shader.inputs['Alpha'].default_value = .65
        mat.node_tree.links.new(shader.outputs[0], output.inputs['Surface'])
        mat.diffuse_color = (1,0,1,1)  # Deliberately differs from the shader colour.
        return mat

    emission = shader_material('Emission paint', 'ShaderNodeEmission', (.2,.7,.1,.2))
    principled = shader_material('Principled paint', 'ShaderNodeBsdfPrincipled', (.1,.2,.8,1))
    for name, y, mat in (('Live emission',2.2,emission),
                         ('Principled label',.5,principled),
                         ('Extruded label',-1.2,emission)):
        data = bpy.data.curves.new(name, 'FONT')
        data.body = name
        data.size = .48
        data.materials.append(mat)
        if name == 'Extruded label':
            data.extrude = .1
        if name == 'Live emission':
            # An unused Principled slot must not reject an Emission-only body.
            data.materials.append(principled)
        obj = bpy.data.objects.new(name, data)
        obj.location = (.3,y,0)
        scene.collection.objects.link(obj)

    gp_mat = bpy.data.materials.new('GP flat')
    bpy.data.materials.create_gpencil_data(gp_mat)
    gp_mat.grease_pencil.color = (1,.1,.1,1)
    for name, y in (('Editable GP',1),('Variable GP',-1.4)):
        data = bpy.data.grease_pencils.new(name)
        data.materials.append(gp_mat)
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = (-2.3,y,0)
        obj.use_grease_pencil_lights = False
        layer = data.layers.new('Ink', set_active=True)
        layer.use_lights = False
        drawing = layer.frames.new(0).drawing
        drawing.add_strokes([3])
        drawing.set_types(type='POLY')
        for pt, co in zip(drawing.strokes[0].points, ((-.5,-.5,0),(0,.5,0),(.5,-.5,0))):
            pt.position = co
            pt.radius = .05
            pt.opacity = 1
        if name == 'Variable GP':
            drawing.strokes[0].points[0].opacity = .2
    scene.frame_set(0)
    directory = Path(os.environ.get('HANDOFF_TEST_OUT') or tempfile.mkdtemp(prefix='handoff-live-text-'))
    directory.mkdir(parents=True, exist_ok=True)
    print('TEXT_TEST_OUTPUT', directory, flush=True)

    for flat in (False, True):
        scene = bpy.context.scene
        for obj in scene.objects:
            obj.hide_render = False
        bpy.context.view_layer.update()
        path = directory/('flat.svg' if flat else 'emission.svg')
        original_path = bpy.data.filepath
        ok, reason = export_view_layer_svg(scene, bpy.context.view_layer, path,
                                           hybrid=True, deferred=True, flat_text_material=flat)
        assert ok, reason
        assert bpy.data.filepath == original_path
        raster_groups = []
        def logger(*args):
            print(*args, flush=True)
            if args[0] == '[HandOff] SVG RASTER GROUP:':
                visible = {o.name for o in bpy.context.scene.objects if not o.hide_render}
                assert 'Editable GP' not in visible, 'GP vectors duplicated in fallback PNG'
                assert 'Live emission' not in visible, 'Live text duplicated in fallback PNG'
                if flat:
                    assert 'Principled label' not in visible, 'Flat override text duplicated in PNG'
                raster_groups.append(visible)
        assert resolve_hybrid_source(path, logger=logger)
        root = ET.parse(path).getroot()
        texts = list(root.iter(SVG+'text'))
        expected = {'Live emission','Principled label'} if flat else {'Live emission'}
        assert {t.get(INK+'label') for t in texts} == expected
        live = next(t for t in texts if t.get(INK+'label') == 'Live emission')
        assert ''.join(live.itertext()) == 'Live emission'
        assert live.get('fill-opacity') == '1', 'Emission colour alpha wrongly made text transparent'
        assert live.get('fill') not in ('#ffffff','#ff00ff'), 'Shader colour was ignored'
        if flat:
            text = next(t for t in texts if t.get(INK+'label') == 'Principled label')
            assert abs(float(text.get('fill-opacity')) - .65) < .00001
        gp = next(g for g in root.iter(SVG+'g') if g.get('data-handoff-object') == 'Editable GP')
        assert gp.get(INK+'label') == 'Editable GP'
        assert gp.find(SVG+'path').get(INK+'label') == 'Ink'
        assert not gp.findall(SVG+'g'), 'Redundant single-layer container survived'
        images = list(root.iter(SVG+'image'))
        assert raster_groups and images
        for image in images:
            data = base64.b64decode(image.get('href').split(',',1)[1])
            with Image.open(io.BytesIO(data)) as pixels:
                assert pixels.size == (256,256)
                assert pixels.getchannel('A').getextrema()[1] > 0
        mat = bpy.data.materials['Principled paint']
        shader = next(n for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
        assert abs(shader.inputs['Base Color'].default_value[2] - .8) < .00001
    print('PASS: GP naming, editable Emission text, Principled override, per-object fallback and no duplicate text in PNGs', flush=True)


if __name__ == '__main__':
    try:
        run()
    except BaseException:
        traceback.print_exc()
        sys.stdout.flush(); sys.stderr.flush(); os._exit(1)
    sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
