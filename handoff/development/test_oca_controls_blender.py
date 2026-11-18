"""Actual Blender 5.3 rendering and OCA control/animation/retry integration."""
import os,sys,json,traceback,copy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]

def run():
 import bpy
 import handoff as addon
 from pillow_loader import ensure_pillow
 ensure_pillow()
 from psd_worker import assemble,run as convert
 from PIL import Image
 import numpy as np
 from oca_companions import composite,leaves
 def original(n):return n.get('meta',{}).get('handoff',{}).get('sourceName',n['name'])
 addon.register();scene=bpy.context.scene
 for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
 scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
 scene.render.resolution_x=64;scene.render.resolution_y=48;scene.render.resolution_percentage=100
 scene.render.film_transparent=True;scene.frame_start=1;scene.frame_end=3;scene.render.fps=12
 scene.view_settings.view_transform='AgX'
 camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera)
 camera.location=(0,0,10);camera.data.type='ORTHO';camera.data.ortho_scale=4;scene.camera=camera
 views=[];owners=[]
 for index,(name,color,xy) in enumerate((('Foreground',(1,.1,.2,1),(-.8,.3)),('HiddenArt',(.1,1,.2,1),(.8,.5)),('Backdrop',(.1,.2,1,1),(0,-.5)),('Combined',(1,.8,.1,1),(-.8,-.6)))):
  parent=scene.collection
  if name=='HiddenArt':
   parent=bpy.data.collections.new('HiddenGroup');parent.color_tag='COLOR_01';scene.collection.children.link(parent)
   parent.hide_viewport=True
  collection=bpy.data.collections.new(name);collection.color_tag='COLOR_05';parent.children.link(collection);owners.append(parent.name if name=='HiddenArt' else name)
  mesh=bpy.data.meshes.new(name);mesh.from_pydata([(-.3,-.3,0),(.3,-.3,0),(.3,.3,0),(-.3,.3,0)],[],[(0,1,2,3)])
  obj=bpy.data.objects.new(name,mesh);collection.objects.link(obj);obj.location=(*xy,0)
  mat=bpy.data.materials.new(name);mat.use_nodes=True;mat.node_tree.nodes.clear()
  emission=mat.node_tree.nodes.new('ShaderNodeEmission');emission.inputs['Color'].default_value=color
  output=mat.node_tree.nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(emission.outputs[0],output.inputs['Surface']);mesh.materials.append(mat)
  if name=='Foreground':
   for frame in (1,2,3):
    obj.location.x=-1+frame*.35;obj.scale=(.7+frame*.2,)*3;obj.hide_render=frame==2
    obj.keyframe_insert(data_path='location',frame=frame);obj.keyframe_insert(data_path='scale',frame=frame);obj.keyframe_insert(data_path='hide_render',frame=frame)
  view=scene.view_layers[0] if index==0 else scene.view_layers.new(name);view.name=name;views.append(view)
  if name=='Backdrop':view['handoff_oca_background']=True
 for view,owner in zip(views,owners):
  for child in view.layer_collection.children:
   if child.name in owners:child.exclude=child.name!=owner
 tree=bpy.data.node_groups.new('OCA controls integration','CompositorNodeTree');scene.compositing_node_group=tree
 node=tree.nodes.new('CompositorNodeOutputFile')
 while len(node.file_output_items):node.file_output_items.remove(node.file_output_items[0])
 out=Path(os.environ['LAYERED_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
 scene.render.filepath=str(out/'native/render_');node.directory=str(out/'native/cache');node.file_name='Controls'
 for index,view in enumerate(views):
  render=tree.nodes.new('CompositorNodeRLayers');render.scene=scene;render.layer=view.name
  node.file_output_items.new('RGBA',view.name);tree.links.new(render.outputs['Image'],node.inputs[index])
 item=node.blend_artwork_exports.add();item.format='OCA';item.oca_layout='LEGACY';item.enabled=True;item.depth='8';item.use_groups=True;item.path=str(out/'exports');item.relative_path=False
 item.oca_write_json=True;item.oca_write_template=True;item.oca_ignore_background=False
 # A second output checks that OCA filtering/settings do not alter PSD inputs.
 psd=node.blend_artwork_exports.add();psd.format='PSD';psd.enabled=True;psd.depth='8';psd.use_groups=True;psd.path=str(out/'exports');psd.relative_path=False;psd.bake_svg_png=True
 raw_item=node.blend_artwork_exports.add();raw_item.format='OCA';raw_item.oca_layout='LEGACY';raw_item.enabled=True;raw_item.depth='8';raw_item.use_groups=True
 raw_item.path=str(out/'exports');raw_item.relative_path=False;raw_item.use_custom_name=True;raw_item.custom_name='ControlsRaw';raw_item.save_as_render=False
 raw_item.oca_write_json=False;raw_item.oca_write_template=False;raw_item.oca_ignore_background=False
 expected={'Ignore hidden layers','Ignore background layer','Trim whitespace','Write Spine JSON','Write template image','Scale','Padding'}
 from handoff.oca_controls import PROPERTIES
 assert {item.bl_rna.properties[prop].name for prop in PROPERTIES.values()}==expected
 manifests=[]
 with patch.object(addon,'launch_worker',side_effect=lambda scene,path,*a,**k:manifests.append(Path(path))):bpy.ops.render.render(animation=True)
 assert len(manifests)==1,manifests
 data=json.loads(manifests[0].read_text());job=next(j for j in data['jobs'] if j['format']=='OCA')
 assert [f['frame'] for f in job['oca_frames']]==[1,2,3]
 hidden=next(e for e in job['manifest'] if e['name']=='HiddenArt')
 assert hidden['oca_group_visibility']['HiddenGroup'] is False,hidden
 assert next(e for e in job['manifest'] if e['name']=='Backdrop')['oca_background']
 assert not next(e for e in job['manifest'] if e['name']=='Combined')['oca_background']
 hidden_cache=next(Path(job['oca_frames'][0]['dir']).glob(hidden['slug']+'*.png'))
 assert Image.open(hidden_cache).getchannel('A').getbbox(), 'Viewport-hidden artwork must still be captured'
 assert convert(manifests[0])==0
 document=json.loads(Path(job['dest']).read_text());paint=list(leaves(document['layers']))
 assert len(paint)==4
 foreground=next(n for n,_ in paint if original(n)=='Foreground');assert foreground['animated']
 assert foreground['frames'][1]['name']=='_blank' and foreground['frames'][1]['fileName']==''
 assert foreground['frames'][0]['position']!=foreground['frames'][2]['position']
 assert not next(shown for n,shown in paint if original(n)=='HiddenArt')
 from psd_tools import PSDImage
 assert len(list(PSDImage.open(out/'exports/Controls.psd').descendants()))>=8
 # Save as Render changes RGB, while trim and positioning remain alpha-driven.
 raw_job=next(j for j in data['jobs'] if j['format']=='OCA' and j['dest'].endswith('ControlsRaw.oca'))
 raw_doc=json.loads(Path(raw_job['dest']).read_text())
 original_layers=list(leaves(document['layers']));raw_layers=list(leaves(raw_doc['layers']))
 colour_changed=False
 for (left,_),(right,_) in zip(original_layers,raw_layers):
  for cel,raw_cel in zip(left['frames'],right['frames']):
   assert (cel['width'],cel['height'],cel['position'])==(raw_cel['width'],raw_cel['height'],raw_cel['position'])
   if not cel['fileName']:continue
   shown_pixels=np.asarray(Image.open(Path(job['dest']).parent/cel['fileName']))
   raw_pixels=np.asarray(Image.open(Path(raw_job['dest']).parent/raw_cel['fileName']))
   np.testing.assert_array_equal(shown_pixels[...,3],raw_pixels[...,3])
   colour_changed |= not np.array_equal(shown_pixels[...,:3],raw_pixels[...,:3])
 assert colour_changed,'Colour-management fixture must exercise different RGB outputs'
 assert not (Path(raw_job['dest']).with_suffix('')/'_companions').exists()
 baseline_structure=[(n['name'],n['type'],n['label'],n['blendingMode'],shown) for n,shown in original_layers]
 assert (out/'exports/Controls/_companions/Controls.spine.json').is_file()
 assert Image.open(out/'exports/Controls/_companions/Controls.template.png').size==(64,48)
 # Reuse actual native frame pixels for every scale, padding and trim setting.
 checks=[];render_number=scene.frame_current
 for scale in (50,100,200):
  for padding in (0,1,4):
   reconstructions=[]
   for trim in (False,True):
    item.oca_scale=scale;item.oca_padding=padding;item.trim_empty_pixels=trim
    # Per-frame snapshots deliberately retain settings from the first render.
    refreshed=addon.refresh_cached_jobs(scene,data)
    retry=next(j for j in refreshed['jobs'] if j['format']=='OCA')
    item.oca_write_json=False;item.oca_write_template=False
    retry['oca_options']['writeJson']=False;retry['oca_options']['writeTemplate']=False
    assemble(retry);doc=json.loads(Path(retry['dest']).read_text())
    assert (doc['width'],doc['height'])==(64*scale//100,48*scale//100)
    assert not (Path(retry['dest']).with_suffix('')/'_companions').exists()
    assert [(n['name'],n['type'],n['label'],n['blendingMode'],shown) for n,shown in leaves(doc['layers'])]==baseline_structure
    for layer,shown in leaves(doc['layers']):
     for cel in layer['frames']:
      if not cel['fileName']:continue
      raw=next(e for e in retry['manifest'] if e['name']==original(layer))
      captured=next(f for f in retry['oca_frames'] if f['frame']==cel['frameNumber'])
      path=next(p for p in Path(captured['dir']).glob(raw['slug']+'*.png') if p.stem==raw['slug']+str(cel['frameNumber']).zfill(4))
      source_image=Image.open(path);box=source_image.getchannel('A').getbbox() if trim else (0,0,64,48)
      assert box is not None
      w,h=box[2]-box[0],box[3]-box[1]
      expected=(int(np.floor(w*scale/100+.5))+2*padding,int(np.floor(h*scale/100+.5))+2*padding)
      asset=Image.open(Path(retry['dest']).parent/cel['fileName'])
      assert asset.size==expected,(layer['name'],asset.size,expected)
      np.testing.assert_allclose(cel['position'],[(box[0]+w/2)*scale/100,(box[1]+h/2)*scale/100])
    reconstructions.append(composite(doc,Path(retry['dest']).with_suffix(''),3))
    checks.append(dict(scale=scale,padding=padding,trim=trim))
   if scale==100:np.testing.assert_array_equal(*reconstructions)
 # Native false/true background and group visibility filtering, through current UI retry.
 item.oca_ignore_hidden_layers=True;item.oca_ignore_background=True
 retry=next(j for j in addon.refresh_cached_jobs(scene,data)['jobs'] if j['format']=='OCA');assemble(retry)
 filtered=json.loads(Path(retry['dest']).read_text());names=[original(n) for n,_ in leaves(filtered['layers'])]
 assert names==['Combined','Foreground'],names
 item.oca_ignore_hidden_layers=False;item.oca_ignore_background=False
 item.oca_write_json=True;item.oca_write_template=True;item.oca_scale=100;item.oca_padding=1
 final=next(j for j in addon.refresh_cached_jobs(scene,data)['jobs'] if j['format']=='OCA');assemble(final)
 doc=json.loads(Path(final['dest']).read_text());comp=json.loads((Path(final['dest']).with_suffix('')/'_companions/Controls.spine.json').read_text())
 assert [s['name'] for s in comp['slots']]==[original(n) for n,_ in leaves(doc['layers'])]
 assert next(s for s in comp['slots'] if s['name']=='HiddenArt')['color']=='ffffff00'
 assert comp['animations']['oca']['slots']['Foreground']['attachment'][1]['name'] is None
 template=Image.open(Path(final['dest']).with_suffix('')/'_companions/Controls.template.png')
 hidden_pixels=np.asarray(Image.open(hidden_cache));ys,xs=np.where(hidden_pixels[...,3]>200)
 assert template.getpixel((int(np.median(xs)),int(np.median(ys))))[3]==0,'Template must not reveal native hidden artwork'
 assert np.asarray(template)[...,3].max()>0,'Template must retain visible artwork'
 assert scene.frame_current==render_number and not addon.SESSIONS
 assert all(not e.get('oca_background') for j in data['jobs'] if j['format']=='PSD' for e in j['manifest'])
 report=dict(blender=bpy.app.version_string,frames=3,layers=4,combinations=checks,
             registration=True,hidden_render_pixels=True,background_explicit=True,
             moving_and_blank_frames=True,trim_reconstruction_100_percent=True,
             current_retry_controls=True,json=True,template=True,psd_smoke=True,save_as_render_independent_of_trim=True,companions_toggle_off=True,layer_metadata_stable=True)
 (out/'native-results.json').write_text(json.dumps(report,indent=2))
 addon.unregister();print('OCA_SEVEN_CONTROLS_NATIVE_PASS',json.dumps(report),flush=True)

if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();raise
