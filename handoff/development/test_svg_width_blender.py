"""Blender 5.3 pressure-stroke regression; all fixtures live in a private folder.

Run with --factory-startup --disable-autoexec -b --python this_file.py.
HANDOFF_TEST_OUT can retain the native PNG and SVG for reader comparisons.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def run():
    import bpy
    from pillow_loader import ensure_pillow
    ensure_pillow()
    from svg_hybrid import export_hybrid_svg, resolve_hybrid_source
    from svg_collections import SVG
    assert bpy.app.version[:2]==(5,3)
    out=Path(os.environ.get('HANDOFF_TEST_OUT') or tempfile.mkdtemp(prefix='handoff-width-'))
    out.mkdir(parents=True,exist_ok=True)
    scene=bpy.context.scene
    for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
    scene.render.engine='CYCLES';scene.cycles.samples=1;scene.cycles.device='CPU'
    scene.render.resolution_x=scene.render.resolution_y=512;scene.render.resolution_percentage=100
    scene.render.film_transparent=True;scene.render.use_compositing=False
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
    camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera)
    camera.location=(0,0,10);camera.data.type='ORTHO';camera.data.ortho_scale=8;scene.camera=camera
    from math import sin,pi
    t=[i/39 for i in range(40)]
    shapes=(('Taper',[(-1+2*f,0,0) for f in t],[.03+.05*f for f in t],False,(-2,2,0)),
            ('Pressure',[(-1+2*f,.4*sin(2*pi*f),0) for f in t],[.03+.12*f for f in t],False,(2,2,0)),
            ('Closed',[(-.7,-.7,0),(-.7,.7,0),(.7,.7,0),(.7,-.7,0)],[.04,.12,.25,.12],True,(-2,-2,0)),
            ('Alpha',[(-1+2*f,.2*sin(pi*f),0) for f in t],[.03+.05*sin(pi*f)**2 for f in t],False,(2,-2,0)))
    for name,points,radii,cyclic,location in shapes:
        data=bpy.data.grease_pencils.new(name);obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj)
        obj.location=location;obj.use_grease_pencil_lights=False
        material=bpy.data.materials.new(name);bpy.data.materials.create_gpencil_data(material)
        material.grease_pencil.color=(.15,.6,.25,.5 if name=='Alpha' else 1)
        data.materials.append(material)
        layer=data.layers.new('Authored layer',set_active=True);layer.use_lights=False
        layer.opacity=.65 if name=='Alpha' else 1
        drawing=layer.frames.new(0).drawing;drawing.add_strokes([len(points)]);drawing.set_types(type='POLY')
        stroke=drawing.strokes[0];stroke.cyclic=cyclic;stroke.fill_id=0
        for p,co,radius in zip(stroke.points,points,radii):
            p.position=co;p.radius=radius;p.opacity=.7 if name=='Alpha' else 1
    scene.frame_set(0);view=bpy.context.view_layer;view.update()
    original_ids=(len(bpy.data.objects),len(bpy.data.grease_pencils),len(bpy.data.materials),len(bpy.data.scenes))
    original_widths={o.name:[p.radius for p in o.data.layers[0].current_frame().drawing.strokes[0].points]
                     for o in scene.objects if o.type=='GREASEPENCIL'}
    ok,reason=export_hybrid_svg(scene,view,out/'pressure.svg');assert ok,reason
    assert original_ids==(len(bpy.data.objects),len(bpy.data.grease_pencils),len(bpy.data.materials),len(bpy.data.scenes))
    assert original_widths=={o.name:[p.radius for p in o.data.layers[0].current_frame().drawing.strokes[0].points]
                            for o in scene.objects if o.type=='GREASEPENCIL'}
    root=ET.parse(out/'pressure.svg').getroot()
    assert len(list(root.iter(SVG+'image')))==1, 'Closed pressure stroke must retain its inner contour via PNG'
    parents={child:parent for parent in root.iter() for child in parent}
    expanded=[e for e in root.iter() if e.get('data-handoff-geometry')=='powerstroke']
    assert {parents[e].get('data-handoff-object') for e in expanded}=={'Taper','Pressure','Alpha'}
    assert all(json.loads(e.get('data-handoff-pressure'))['widths'] for e in expanded)
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='8'
    bpy.ops.render.render(write_still=False)
    bpy.data.images['Render Result'].save_render(str(out/'pressure-native.png'),scene=scene)
    assert resolve_hybrid_source(out/'pressure.svg')
    print('PASS: three live PowerStroke paths, portable outline geometry, closed-contour fallback, source radii and temporary ID cleanup; reader comparison assets:',out,flush=True)


if __name__=='__main__':
    try:run()
    except BaseException:
        traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
    sys.stdout.flush();sys.stderr.flush();os._exit(0)
