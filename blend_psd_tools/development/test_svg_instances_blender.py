"""Native linked GP data, independent copies and SVG clone render fixtures."""
import os,sys,json,math,traceback
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT)]

def run():
 import bpy
 from svg_hybrid import export_hybrid_svg
 from svg_export import encode_svg
 from svg_instances import SVG, INK, XLINK, KEY
 output=Path(os.environ['LAYERED_TEST_OUTPUT']);output.mkdir(parents=True,exist_ok=True)
 scene=bpy.context.scene
 for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
 scene.render.resolution_x=scene.render.resolution_y=512;scene.render.resolution_percentage=100;scene.render.film_transparent=True
 scene.view_settings.view_transform='Standard'
 camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera)
 camera.location=(0,0,10);camera.data.type='ORTHO';camera.data.ortho_scale=10;scene.camera=camera
 collection=bpy.data.collections.new('Tagged Sprites');collection.color_tag='COLOR_04';scene.collection.children.link(collection)
 gp=bpy.data.grease_pencils.new('Shared Circle');original=bpy.data.objects.new('Original',gp);collection.objects.link(original)
 original.use_grease_pencil_lights=False
 material=bpy.data.materials.new('Shared Gradient');bpy.data.materials.create_gpencil_data(material);gp.materials.append(material)
 style=material.grease_pencil;style.fill_style='GRADIENT';style.gradient_type='RADIAL'
 style.texture_scale=(1.8,1.4);style.texture_offset=(-1,-1);style.color=(0,0,0,0)
 style.gradient.elements[0].color=(1,.8,.1,.95);style.gradient.elements[-1].color=(.1,.2,1,.2)
 layer=gp.layers.new('Circle paint',set_active=True);layer.use_lights=False;layer.opacity=.72
 drawing=layer.frames.new(1).drawing;drawing.add_strokes([64]);drawing.set_types(type='POLY')
 stroke=drawing.strokes[0];stroke.cyclic=True;stroke.fill_id=1;stroke.hide_stroke=True
 for i,point in enumerate(stroke.points):point.position=(math.cos(i*math.tau/64),math.sin(i*math.tau/64),0);point.opacity=1
 original.location=(-2,2,0)
 def linked(name,location,scale,rotation):
  obj=original.copy();obj.name=name;collection.objects.link(obj);obj.location=location;obj.scale=scale;obj.rotation_euler.z=rotation;return obj
 linked('Linked rotated',(2,2,0),(1.2,1.2,1.2),.4)
 linked('Linked stretched',(-2,-2,0),(1.4,.65,1),-.3)
 independent=linked('Independent copy',(2,-2,0),(1,1,1),0);independent.data=gp.copy()
 tinted=linked('Different material',(0,0,0),(.7,.7,.7),0)
 red=material.copy();red.name='Object paint';red.grease_pencil.fill_style='SOLID';red.grease_pencil.fill_color=(1,0,0,1)
 tinted.material_slots[0].link='OBJECT';tinted.material_slots[0].material=red
 scene.frame_set(1);view=scene.view_layers[0];view.update()
 before={obj.name:(obj.data.as_pointer(),tuple(obj.location),tuple(obj.scale)) for obj in collection.objects}
 path=output/'linked-circles.svg';ok,reason=export_hybrid_svg(scene,view,path,allow_raster=False)
 assert ok,reason
 root=ET.parse(path).getroot();clones=list(root.iter(SVG+'use'))
 print('CLONES',[(c.get(INK+'label'),c.get('href'),c.get('transform')) for c in clones],flush=True)
 assert len(clones)==2
 assert not list(root.iter(SVG+'image'))
 assert all(c.get('href')==c.get(XLINK+'href') for c in clones)
 assert not any(c.get(INK+'label') in ('Independent copy','Different material') for c in clones)
 colors=[e.get(INK+'highlight-color') for e in root.iter() if e.get(INK+'highlight-color')]
 assert colors and all(len(color)==7 for color in colors)
 model=json.loads(path.with_suffix('.vectors.json').read_text())
 from pillow_loader import ensure_pillow
 ensure_pillow()
 from PIL import Image
 from svg_document import write_svg_document
 Image.new('RGBA',(512,512)).save(output/'blank.png')
 write_svg_document(dict(dest=str(output/'layered-circles.svg'),depth=8,hierarchy='GROUPS'),
   [(dict(name='Sprites',collection_path='Artwork',collection_colors=['GREEN'],vector_svg=str(path)),output/'blank.png')])
 imported=ET.parse(output/'layered-circles.svg').getroot();ids={e.get('id') for e in imported.iter() if e.get('id')}
 assert len(list(imported.iter(SVG+'use')))==2
 for use in imported.iter(SVG+'use'):
  assert use.get('href')[1:] in ids and use.get('data-layered-instance-source') in ids
 assert all(e.get(INK+'highlight-color') for e in imported.iter(SVG+'path'))
 for obj in model['objects']:obj.pop('svg_instance',None)
 (output/'independent-circles.svg').write_text(encode_svg(512,512,model['objects']))
 # Edit only the original's paint geometry in the serialized SVG. Both clones
 # must update when an independent renderer opens the modified document.
 master=next(e for e in root.iter() if e.get('id')==clones[0].get('href')[1:])
 for element in master.iter(SVG+'path'):
  element.set('fill','#00ff00');element.set('fill-opacity','1')
 ET.ElementTree(root).write(output/'linked-circles-edited.svg',encoding='utf-8',xml_declaration=True)
 assert before=={obj.name:(obj.data.as_pointer(),tuple(obj.location),tuple(obj.scale)) for obj in collection.objects}
 # Exercise the installed 5.3 Bezier-handle API and visible outline rules.
 for data in (gp,independent.data):
  draw=data.layers[0].frames[0].drawing;draw.set_types(type='BEZIER')
  step=math.tau/64;handle=4/3*math.tan(step/4)
  for i,point in enumerate(draw.strokes[0].points):
   angle=i*step;x=math.cos(angle);y=math.sin(angle)
   point.handle_left.position=(x+handle*y,y-handle*x,0)
   point.handle_right.position=(x-handle*y,y+handle*x,0)
   point.radius=.025
  draw.tag_positions_changed()
 view.update()
 ok,reason=export_hybrid_svg(scene,view,output/'linked-bezier.svg',allow_raster=False);assert ok,reason
 bezier=ET.parse(output/'linked-bezier.svg').getroot()
 assert len(list(bezier.iter(SVG+'use')))==2
 assert any('C ' in path.get('d','') for path in bezier.iter(SVG+'path'))
 style.show_stroke=True;style.color=(.1,.2,.3,1)
 for data in (gp,independent.data):data.layers[0].frames[0].drawing.strokes[0].hide_stroke=False
 view.update()
 ok,reason=export_hybrid_svg(scene,view,output/'linked-outlined.svg',allow_raster=False);assert ok,reason
 outlined=ET.parse(output/'linked-outlined.svg').getroot()
 outline_clones=list(outlined.iter(SVG+'use'))
 assert len(outline_clones)==1,[(node.get(INK+'label'),node.get('transform')) for node in outline_clones]
 assert outline_clones[0].get(INK+'label')=='Linked rotated'
 assert not list(outlined.iter(SVG+'image'))
 print('NATIVE_GP_CLONES_PASS',reason,flush=True)

if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
 sys.stdout.flush();sys.stderr.flush();os._exit(0)
