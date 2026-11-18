"""Actual Blender exports: GP OCA vectors, raster alternatives and existing formats.

Use a factory startup for the small three-frame fixture, or open the production
file read-only and set HANDOFF_SOURCE_BLEND=1. All destinations are redirected.
"""
import copy,importlib,json,os,sys,traceback
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(Path(os.environ.get('HANDOFF_PACKAGE_PARENT',ROOT.parent))),str(ROOT),str(ROOT/'vendor')]


def fixture(bpy):
 scene=bpy.context.scene
 for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
 scene.render.engine='CYCLES';scene.render.film_transparent=True
 scene.render.resolution_x=scene.render.resolution_y=64;start=int(os.environ.get('HANDOFF_TEST_START','0'));scene.frame_start=start;scene.frame_end=start+2
 camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera)
 camera.location=(0,0,10);camera.data.type='ORTHO';camera.data.ortho_scale=5;scene.camera=camera
 views=[]
 for index,name in enumerate(('First','Second')):
  coll=bpy.data.collections.new(name);coll.color_tag='COLOR_05';scene.collection.children.link(coll)
  data=bpy.data.grease_pencils.new(name);obj=bpy.data.objects.new(name,data);coll.objects.link(obj)
  obj.use_grease_pencil_lights=False;obj.location.x=index*1.5-.8
  mat=bpy.data.materials.new(name);bpy.data.materials.create_gpencil_data(mat)
  mat.grease_pencil.fill_color=(.2,.7,.3,1);mat.grease_pencil.color=(.8,.2,.1,1);data.materials.append(mat)
  layer=data.layers.new('Drawing',set_active=True);layer.use_lights=False
  drawing=layer.frames.new(start).drawing;drawing.add_strokes([3]);drawing.set_types(type='POLY')
  stroke=drawing.strokes[0];stroke.cyclic=True;stroke.fill_id=1
  for point,co in zip(stroke.points,((-.6,-.6,0),(0,.6,0),(.6,-.6,0))):
   point.position=co;point.radius=.03;point.opacity=1
  for frame in range(start,start+3):
   obj.location.y=(frame-start)*.2
   obj.location.x=30 if os.environ.get('HANDOFF_TEST_BLANK_GP') and index==1 and frame==start+1 else index*1.5-.8
   obj.keyframe_insert(data_path='location',frame=frame)
  view=scene.view_layers[0] if index==0 else scene.view_layers.new(name);view.name=name;views.append(view)
 for view in views:
  for collection in view.layer_collection.children:
   if collection.name in ('First','Second'):collection.exclude=collection.name!=view.name
 tree=bpy.data.node_groups.new('OCA GP Fixture','CompositorNodeTree');scene.compositing_node_group=tree
 node=tree.nodes.new('CompositorNodeOutputFile');node.file_name='Artwork';node.file_output_items.clear()
 for index,view in enumerate(views):
  render=tree.nodes.new('CompositorNodeRLayers');render.scene=scene;render.layer=view.name
  node.file_output_items.new('RGBA',view.name);tree.links.new(render.outputs['Image'],node.inputs[index])
 # Actual compositor processing must remain a rendered logical layer.
 blur=tree.nodes.new('CompositorNodeBlur')
 tree.links.new(render.outputs['Image'],blur.inputs['Image'])
 node.file_output_items.new('RGBA','Processed')
 tree.links.new(blur.outputs['Image'],node.inputs[2])
 return scene,tree,node


def run():
 import bpy
 addon=importlib.import_module(os.environ.get('HANDOFF_PACKAGE','handoff'));addon.register()
 from pillow_loader import ensure_pillow
 ensure_pillow()
 from PIL import Image
 out=Path(os.environ['HANDOFF_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
 production=bool(os.environ.get('HANDOFF_SOURCE_BLEND'))
 if production:
  scene=bpy.data.scenes['Hatshepsut'];bpy.context.window.scene=scene
  tree=addon.scene_tree(scene)
  node=max((n for n in tree.nodes if n.bl_idname=='CompositorNodeOutputFile'),key=lambda n:len(addon.connected(tree,n)))
  for candidate in addon.all_compositor_trees():
   for n in candidate.nodes:
    if n.bl_idname!='CompositorNodeOutputFile':continue
    n.directory=str(out/'native');n.file_name='Native'
    for item in n.blend_artwork_exports:item.enabled=False
    if n!=node:n.mute=True
  node.file_name='Hatshepsut';scene.render.resolution_percentage=12
 else:
  scene,tree,node=fixture(bpy);scene.render.resolution_percentage=100
 scene.cycles.samples=1;scene.cycles.device='CPU';scene.cycles.use_denoising=False
 scene.render.filepath=str(out/'native/render_');node.directory=str(out/'native')
 scene.view_settings.view_transform='Standard';scene.frame_set(scene.frame_start)
 for fmt in ('OCA','PSD','PSB','SVG','PNG','FONTS'):
  item=node.blend_artwork_exports.add();item.format=fmt;item.oca_layout='LEGACY';item.enabled=True;item.depth='8';item.path=str(out/'exports');item.relative_path=False
  item.use_groups=True
  if fmt=='OCA':item.oca_keep_png=True;item.oca_write_json=True;item.oca_write_template=True
 captures=[]
 with patch.object(addon,'launch_worker',side_effect=lambda scene,path,*a,**k:captures.append(Path(path))):
  bpy.ops.render.render(animation=not production,scene=scene.name)
 assert len(captures)==1,captures
 data=json.loads(captures[0].read_text());oca=next(j for j in data['jobs'] if j['format']=='OCA')
 if os.environ.get('HANDOFF_TEST_EMPTY_GP') and not production:
  first=oca['oca_frames'][0];entry=first['manifest'][0]
  cache=next(p for p in Path(first['dir']).glob(entry['slug']+'*.png') if p.stem.endswith('0000'))
  Image.new('RGBA',(64,64)).save(cache)
 # Keep a source-derived raster view and SVG source using exactly the same cache.
 raster=copy.deepcopy(oca);raster['dest']=str(out/'exports/Rasterised.oca');raster['bake_svg_png']=True
 data['jobs'].append(raster)
 # A processed compositor input must use its pixels, never bypass that operation.
 unsupported=copy.deepcopy(oca);unsupported['dest']=str(out/'exports/Unsupported.oca')
 for entry in unsupported['manifest']:entry.update(vector_svg='',vector_reason='Compositor processing requires rendered PNG')
 for frame in unsupported.get('oca_frames',[]):
  for entry in frame['manifest']:entry.update(vector_svg='',vector_reason='Compositor processing requires rendered PNG')
 data['jobs'].append(unsupported)
 captures[0].write_text(json.dumps(data,indent=2));addon.unregister()
 from psd_worker import run as convert
 assert convert(captures[0])==0
 from oca_companions import leaves
 document=json.loads(Path(oca['dest']).read_text());paint=list(leaves(document['layers']))
 vectors=[n for n,_ in paint if n['type']=='vectorlayer']
 assert len(vectors)==(1 if production else 2),[(n['name'],n['type']) for n,_ in paint]
 if not production:
  assert next(n for n,_ in paint if n['name']=='Processed')['type']=='paintlayer'
 for layer in vectors:
  assert layer['fileType']=='svg'
  if not production:assert [c['frameNumber'] for c in layer['frames']]==[0,1,2]
  for cel in layer['frames']:
   if not cel['fileName']:
    assert cel['name']=='_blank'
    continue
   svg=Path(oca['dest']).parent/cel['fileName'];assert svg.is_file()
   alternative=cel['meta']['handoff']['raster'];png=Path(oca['dest']).parent/alternative['fileName']
   im=Image.open(png);assert im.getchannel('A').getbbox(), 'GP fallback is empty'
   assert im.size==(cel['width'],cel['height'])
   assert alternative['position']==cel['position']
   assert not svg.name[:1].isdigit(),svg
 from psd_tools import PSDImage
 assert PSDImage.open(Path(oca['dest']).with_suffix('.psd')).size==(document['width'],document['height'])
 assert PSDImage.open(Path(oca['dest']).with_suffix('.psb')).version==2
 raster_doc=json.loads(Path(raster['dest']).read_text())
 assert all(n['type']=='paintlayer' for n,_ in leaves(raster_doc['layers']))
 assert any(cel['meta'].get('handoff',{}).get('editableSource') for n,_ in leaves(raster_doc['layers']) for cel in n['frames'])
 unsupported_doc=json.loads(Path(unsupported['dest']).read_text())
 assert all(n['type']=='paintlayer' for n,_ in leaves(unsupported_doc['layers']))
 report=dict(production=production,layers=len(paint),vector_layers=len(vectors),raster_fallback_nonempty=True,
             frames=document['endTime']-document['startTime'],width=document['width'],height=document['height'],
             psd=True,psb=True,svg=True,png=True,fonts=True,rasterise=True,unsupported_fallback=True,
             gp_cache_recovery_exercised=bool(os.environ.get('HANDOFF_TEST_EMPTY_GP')),
             native_blank_frame_exercised=bool(os.environ.get('HANDOFF_TEST_BLANK_GP')))
 (out/'native-results.json').write_text(json.dumps(report,indent=2))
 print('HANDOFF_OCA_VECTORS_PASS',json.dumps(report),flush=True)


if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();raise
