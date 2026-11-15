"""Native 5.3 source reuse, setting isolation and resolved vector validation."""
import os,sys,tempfile,traceback,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT)]

def run():
 import bpy
 import handoff as addon
 from svg_hybrid import resolve_hybrid_source
 addon.register();scene=bpy.context.scene
 for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
 scene.render.film_transparent=True;scene.render.resolution_x=scene.render.resolution_y=64;scene.render.resolution_percentage=100
 camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera)
 camera.location=(0,0,10);camera.data.type='ORTHO';camera.data.ortho_scale=4;scene.camera=camera
 data=bpy.data.grease_pencils.new('Drawing');obj=bpy.data.objects.new('Drawing',data);scene.collection.objects.link(obj)
 obj.use_grease_pencil_lights=False
 mat=bpy.data.materials.new('Paint');bpy.data.materials.create_gpencil_data(mat);data.materials.append(mat)
 mat.grease_pencil.fill_color=(.2,.4,.6,1)
 layer=data.layers.new('Ink',set_active=True);layer.use_lights=False;drawing=layer.frames.new(1).drawing
 drawing.add_strokes([4]);drawing.set_types(type='POLY');stroke=drawing.strokes[0];stroke.cyclic=True;stroke.fill_id=1;stroke.hide_stroke=True
 for point,co in zip(stroke.points,((-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0))):point.position=co;point.opacity=1
 scene.frame_set(1)
 tree=bpy.data.node_groups.new('Shared source fixture','CompositorNodeTree');scene.compositing_node_group=tree
 source=tree.nodes.new('CompositorNodeRLayers');source.scene=scene;source.layer=scene.view_layers[0].name
 output=tree.nodes.new('CompositorNodeOutputFile')
 while len(output.file_output_items):output.file_output_items.remove(output.file_output_items[0])
 output.file_output_items.new('RGBA','Drawing');tree.links.new(source.outputs['Image'],output.inputs[0])
 with tempfile.TemporaryDirectory(prefix='handoff-shared-vector-') as folder:
  output.directory=folder
  for fmt,depth in [('PSD','8'),('PSD','16'),('SVG','8')]:
   item=output.blend_artwork_exports.add();item.format=fmt;item.depth=depth;item.path=folder;item.relative_path=False
  addon.prepare(scene);session=addon.SESSIONS[scene.as_pointer()]
  paths=[j['manifest'][0]['vector_svg'] for j in session['jobs']]
  assert all(paths) and len(set(paths))==1
  assert len(list((Path(session['root'])/'vectors').glob('*.blend')))==1
  output.blend_artwork_exports[2].svg_flat_text_material=True
  addon.cleanup(scene)
  addon.prepare(scene);session=addon.SESSIONS[scene.as_pointer()]
  paths=[j['manifest'][0]['vector_svg'] for j in session['jobs']]
  assert paths[0]==paths[1] and paths[2]!=paths[0]
  assert len(list((Path(session['root'])/'vectors').glob('*.blend')))==2
  # Resolving a shared source is idempotent; all destinations consume a
  # complete detached model rather than repeatedly evaluating the scene.
  first=Path(paths[0]);addon.cleanup(scene,discard=False)
  assert resolve_hybrid_source(first)
  before=first.read_bytes();assert resolve_hybrid_source(first);assert before==first.read_bytes()
  model=json.loads(first.with_suffix('.vectors.json').read_text());assert len(model['objects'])==1
 print('SHARED_VECTOR_PREPARATION_PASS',flush=True)

if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
 sys.stdout.flush();sys.stderr.flush();os._exit(0)
