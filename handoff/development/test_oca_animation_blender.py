"""Render three real frames, publish OCA plus unchanged final-frame PSD/SVG."""
import os,sys,json,traceback
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]

def run():
 import bpy
 import handoff as addon
 from pillow_loader import ensure_pillow
 ensure_pillow()
 from psd_worker import run as convert
 from psd_tools import PSDImage
 from PIL import Image
 import numpy as np
 addon.register();scene=bpy.context.scene
 for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
 scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
 scene.render.resolution_x=scene.render.resolution_y=48;scene.render.resolution_percentage=100
 scene.render.film_transparent=True;scene.frame_start=1;scene.frame_end=3;scene.render.fps=12
 camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera)
 camera.location=(0,0,10);camera.data.type='ORTHO';camera.data.ortho_scale=4;scene.camera=camera
 layers=[]
 for index,name in enumerate(('Back','Front')):
  collection=bpy.data.collections.new(name);scene.collection.children.link(collection)
  mesh=bpy.data.meshes.new(name);mesh.from_pydata([(-.5,-.5,0),(.5,-.5,0),(.5,.5,0),(-.5,.5,0)],[],[(0,1,2,3)])
  obj=bpy.data.objects.new(name,mesh);collection.objects.link(obj)
  mat=bpy.data.materials.new(name);mat.use_nodes=True;mat.node_tree.nodes.clear()
  emission=mat.node_tree.nodes.new('ShaderNodeEmission');emission.inputs['Color'].default_value=(.7,.1+index*.5,.2,1)
  output=mat.node_tree.nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(emission.outputs[0],output.inputs['Surface']);mesh.materials.append(mat)
  for frame in (1,2,3):obj.location.x=-1+frame*.4+index*.5;obj.keyframe_insert(data_path='location',frame=frame)
  view=scene.view_layers[0] if index==0 else scene.view_layers.new(name);view.name=name;layers.append(view)
 for view in layers:
  for child in view.layer_collection.children:
   if child.name in ('Back','Front'):child.exclude=child.name!=view.name
 tree=bpy.data.node_groups.new('OCA animation test','CompositorNodeTree');scene.compositing_node_group=tree
 node=tree.nodes.new('CompositorNodeOutputFile')
 while len(node.file_output_items):node.file_output_items.remove(node.file_output_items[0])
 output=Path(os.environ['LAYERED_TEST_OUTPUT']);output.mkdir(parents=True,exist_ok=True)
 scene.render.filepath=str(output/'render_')
 node.directory=str(output/'native');node.file_name='Sequence'
 for index,view in enumerate(layers):
  source=tree.nodes.new('CompositorNodeRLayers');source.scene=scene;source.layer=view.name
  node.file_output_items.new('RGBA','Parts/'+view.name);tree.links.new(source.outputs['Image'],node.inputs[index])
 for fmt in ('OCA','PSD','SVG'):
  item=node.blend_artwork_exports.add();item.format=fmt;item.oca_layout='LEGACY';item.enabled=True;item.depth='8'
  item.path=str(output/'exports');item.relative_path=False;item.use_groups=True
 manifests=[]
 with patch.object(addon,'launch_worker',side_effect=lambda scene,path,*a,**kw:manifests.append(Path(path))):
  bpy.ops.render.render(animation=True)
 assert len(manifests)==1,manifests
 data=json.loads(manifests[0].read_text());job=next(j for j in data['jobs'] if j['format']=='OCA')
 assert [j['frame'] for j in job['oca_frames']]==[1,2,3]
 assert [j['cache_frame'] for j in job['oca_frames']]==[1,2,3]
 assert all(j['frame']==3 for j in data['jobs'] if j['format']!='OCA')
 assert convert(manifests[0])==0
 doc=json.loads(Path(job['dest']).read_text());assert (doc['startTime'],doc['endTime'],doc['frameRate'])==(1,4,12)
 def leaves(nodes):
  for n in nodes:
   if n['type']=='paintlayer':yield n
   yield from leaves(n['childLayers'])
 paint=list(leaves(doc['layers']));assert len(paint)==2
 for layer in paint:
  assert layer['animated'] and [f['frameNumber'] for f in layer['frames']]==[1,2,3]
  assert all(f['duration']==1 for f in layer['frames'])
  images=[np.asarray(Image.open(Path(job['dest']).parent/f['fileName'])) for f in layer['frames']]
  for cel,im in zip(layer['frames'],images):
   captured=next(f for f in job['oca_frames'] if f['frame']==cel['frameNumber'])
   entry=next(e for e in captured['manifest'] if e['name']==layer['meta']['handoff']['sourceName'])
   cached=next(p for p in Path(captured['dir']).glob(entry['slug']+'*.png') if p.stem==entry['slug']+str(cel['frameNumber']).zfill(4))
   box=Image.open(cached).getchannel('A').getbbox()
   assert im.shape==(box[3]-box[1]+2,box[2]-box[0]+2,4) and im[...,3].max()>0
   assert cel['position']==[(box[0]+box[2])/2,(box[1]+box[3])/2]
  assert not np.array_equal(images[0],images[-1])
 assert PSDImage.open(output/'exports/Sequence.psd').size==(48,48)
 from xml.etree import ElementTree as E
 assert E.parse(output/'exports/Sequence.svg').getroot().tag.endswith('svg')
 assert not addon.SESSIONS
 addon.unregister()
 print('OCA_ANIMATION_NATIVE_PASS: 3 frames, 2 layered sequences, assets/alpha/fps/hierarchy, final-frame PSD/SVG',flush=True)

if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();raise
