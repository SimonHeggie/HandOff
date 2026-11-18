"""Blender 5.3 regression: opt-in blends through deferred hybrid SVG export.

Use --factory-startup --disable-autoexec. All artwork and snapshots are private
fixtures. COMP_IO_TEST_OUTPUT may retain files for testing in an SVG reader.
"""
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(folder):
    import bpy
    import svg_hybrid as hybrid
    from svg_export import export_view_layer_svg, VectorFallback
    from pillow_loader import ensure_pillow
    ensure_pillow()
    assert bpy.app.version[:2] == (5,3), bpy.app.version_string
    scene = bpy.context.scene
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj,do_unlink=True)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 4
    scene.cycles.device = 'CPU'
    scene.cycles.use_denoising = False
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.use_compositing = False
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    camera = bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    camera.location = (0,0,10)
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 6
    scene.camera = camera
    case = bpy.data.collections.new('25 - Layer blends')
    scene.collection.children.link(case)
    data = bpy.data.grease_pencils.new('Paint data')
    obj = bpy.data.objects.new('Blended paint',data)
    case.objects.link(obj)
    obj.use_grease_pencil_lights = False
    for index,color in enumerate(((.35,.55,.2,1),(.6,.2,.8,.7))):
        mat = bpy.data.materials.new('Paint '+str(index))
        bpy.data.materials.create_gpencil_data(mat)
        mat.grease_pencil.color = (0,0,0,0)
        mat.grease_pencil.fill_color = color
        data.materials.append(mat)
        layer = data.layers.new('Base' if index==0 else 'Blend layer',set_active=True)
        layer.use_lights = False
        drawing = layer.frames.new(0).drawing
        drawing.add_strokes([4])
        drawing.set_types(type='POLY')
        stroke = drawing.strokes[0]
        stroke.cyclic = True
        stroke.fill_id = 1
        stroke.hide_stroke = True
        stroke.material_index = index
        for pt,co in zip(stroke.points,((-.8,-.8,0),(.8,-.8,0),(.8,.8,0),(-.8,.8,0))):
            pt.position = (co[0]+(-.5 if index==0 else .5),co[1],co[2])
            pt.radius = .02
            pt.opacity = 1
    view = bpy.context.view_layer
    scene.frame_set(0)
    view.update()
    layer = data.layers[1]
    modes = [item.identifier for item in layer.bl_rna.properties['blend_mode'].enum_items]
    assert set(modes)=={'REGULAR','HARDLIGHT','ADD','SUBTRACT','MULTIPLY','DIVIDE'},modes
    ids = (len(bpy.data.scenes),len(bpy.data.objects),len(bpy.data.images))
    original_path = bpy.data.filepath
    for mode in ('MULTIPLY','HARDLIGHT','ADD','SUBTRACT','DIVIDE'):
        layer.blend_mode = mode
        view.update()
        try:
            hybrid._evaluated_artwork(scene,view,obj,view.depsgraph)
        except VectorFallback as exc:
            assert 'retain Blender appearance' in str(exc),exc
        else:
            raise AssertionError('Default blend export silently changed appearance')
        path = folder/(mode+'.svg')
        ok,reason = export_view_layer_svg(scene,view,path,hybrid=True,allow_raster=False,
                                          editable_layer_blends=True)
        assert ok,reason
        root = ET.parse(path).getroot()
        assert root.get(hybrid.LAYER_BLENDS)=='1'
        group = next(n for n in root.iter() if n.get('data-compio-object')==obj.name)
        assert group.get('style')=='isolation:isolate'
        assert [n.get('data-compio-layer') for n in group]==['Base','Blend layer']
        assert group[1].get('data-compio-gp-blend')==mode
        assert group[1].get('style')=='mix-blend-mode:'+{'MULTIPLY':'multiply','HARDLIGHT':'hard-light','ADD':'screen','SUBTRACT':'difference','DIVIDE':'color-dodge'}[mode]
        assert not list(root.iter(hybrid.SVG+'image'))
        assert any(n.get(hybrid.INK+'label')==case.name for n in root.iter())
        assert ids==(len(bpy.data.scenes),len(bpy.data.objects),len(bpy.data.images))
        assert bpy.data.filepath==original_path
    layer.blend_mode = 'MULTIPLY'
    # A neighbouring unsupported object exercises worker fallback and Retry.
    fallback = obj.copy()
    fallback.data = data.copy()
    fallback.name = 'Varying point opacity'
    fallback.location.y = -2
    fallback.data.layers.remove(fallback.data.layers[1])
    fallback.data.layers[0].frames[0].drawing.strokes[0].points[0].opacity = .2
    case.objects.link(fallback)
    view.update()
    path = folder/'deferred.svg'
    ok,reason = export_view_layer_svg(scene,view,path,hybrid=True,deferred=True,
                                      editable_layer_blends=True)
    assert ok,reason
    plan = json.loads(ET.parse(path).getroot().get(hybrid.DEFERRED))
    assert plan['editable_layer_blends'] is True
    assert bpy.data.filepath==original_path
    assert layer.blend_mode=='MULTIPLY'
    assert hybrid.resolve_hybrid_source(path)
    root = ET.parse(path).getroot()
    assert root.get(hybrid.LAYER_BLENDS)=='1'
    assert len([n for n in root.iter() if n.get('data-compio-gp-blend')=='MULTIPLY'])==1
    assert len(list(root.iter(hybrid.SVG+'image')))==1
    assert hybrid.retained_hybrid(path,editable_layer_blends=True)
    try:
        hybrid.retained_hybrid(path,editable_layer_blends=False)
    except ValueError as exc:
        assert 'F12' in str(exc),exc
    else:
        raise AssertionError('Changed blend setting reused old raster/vector cache')
    assert hybrid.resolve_hybrid_source(path), 'Completed Retry should need no new render'
    print('GP_BLEND_TEST_PASS',folder,flush=True)


try:
    if os.environ.get('COMP_IO_TEST_OUTPUT'):
        folder = Path(os.environ['COMP_IO_TEST_OUTPUT'])
        folder.mkdir(parents=True,exist_ok=True)
        run(folder)
    else:
        with tempfile.TemporaryDirectory(prefix='compio-blend-test-') as directory:
            run(Path(directory))
except BaseException:
    traceback.print_exc()
    sys.stdout.flush();sys.stderr.flush();os._exit(1)
sys.stdout.flush();sys.stderr.flush();os._exit(0)
