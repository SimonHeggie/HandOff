"""Native PNG16/EXR32 render cache -> cropped, padded OCA, without 8-bit intermediates."""
import os,sys,json,copy,traceback
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]

def run():
 import bpy,numpy as np
 import handoff as addon
 from pillow_loader import ensure_pillow
 ensure_pillow()
 from psd_worker import assemble
 from oca_images import load
 addon.register();scene=bpy.context.scene
 for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
 scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
 scene.render.resolution_x=33;scene.render.resolution_y=25;scene.render.resolution_percentage=100;scene.render.film_transparent=True
 camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera)
 camera.location=(0,0,10);camera.data.type='ORTHO';camera.data.ortho_scale=4;scene.camera=camera
 mesh=bpy.data.meshes.new('HDR');mesh.from_pydata([(-.8,-.5,0),(.7,-.5,0),(.7,.7,0),(-.8,.7,0)],[],[(0,1,2,3)])
 obj=bpy.data.objects.new('HDR',mesh);scene.collection.objects.link(obj)
 mat=bpy.data.materials.new('HDR');mat.use_nodes=True;mat.node_tree.nodes.clear()
 emission=mat.node_tree.nodes.new('ShaderNodeEmission');emission.inputs['Color'].default_value=(3.4,.123456,.333333,1)
 surface=mat.node_tree.nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(emission.outputs[0],surface.inputs['Surface']);mesh.materials.append(mat)
 tree=bpy.data.node_groups.new('Precision','CompositorNodeTree');scene.compositing_node_group=tree
 node=tree.nodes.new('CompositorNodeOutputFile')
 while len(node.file_output_items):node.file_output_items.remove(node.file_output_items[0])
 node.file_output_items.new('RGBA','HDR')
 source=tree.nodes.new('CompositorNodeRLayers');source.scene=scene;source.layer=scene.view_layers[0].name;tree.links.new(source.outputs['Image'],node.inputs[0])
 out=Path(os.environ['LAYERED_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True);node.directory=str(out/'native');node.file_name='Precision';scene.render.filepath=str(out/'native/render_')
 for depth in (16,32):
  item=node.blend_artwork_exports.add();item.format='OCA';item.oca_layout='LEGACY';item.depth=str(depth);item.enabled=True;item.path=str(out/str(depth));item.relative_path=False
  item.oca_write_json=False;item.oca_write_template=False;item.oca_padding=0
 captures=[]
 with patch.object(addon,'launch_worker',side_effect=lambda scene,path,*a,**kw:captures.append(Path(path))):bpy.ops.render.render()
 jobs=json.loads(captures[0].read_text())['jobs'];checks=[]
 for job in jobs:
  depth=job['depth'];entry=job['manifest'][0];cached=next(Path(job['dir']).glob(entry['slug']+'*'+job['extension']));original=load(cached,depth)
  ys,xs=np.where(original[...,3]!=0);left,right,top,bottom=int(xs.min()),int(xs.max()+1),int(ys.min()),int(ys.max()+1)
  for scale in (50,100,200):
   for padding in (0,1,4):
    candidate=copy.deepcopy(job);candidate['oca_options'].update(scale=scale,padding=padding,trimWhitespace=True)
    assemble(candidate);document=json.loads(Path(candidate['dest']).read_text());cel=document['layers'][0]['frames'][0]
    path=Path(candidate['dest']).parent/cel['fileName'];actual=load(path,depth)
    np.testing.assert_allclose(cel['position'],[(left+(right-left)/2)*scale/100,(top+(bottom-top)/2)*scale/100])
    assert document['width']==max(1,int(np.floor(33*scale/100+.5)))
    if depth==16:assert path.read_bytes()[24]==16
    if scale==100:
     cut=actual[padding:actual.shape[0]-padding if padding else None,padding:actual.shape[1]-padding if padding else None]
     np.testing.assert_allclose(cut,original[top:bottom,left:right],atol=0 if depth==16 else 1e-6)
    if depth==32:assert actual[...,:3].max()>1,'HDR clamped or quantized'
    checks.append(dict(depth=depth,scale=scale,padding=padding,dimensions=[cel['width'],cel['height']]))
  if depth==16:
   paint=original[...,3]>.99
   assert np.any(abs(original[paint,:3]*255-np.rint(original[paint,:3]*255))>.05),'Fixture has no sub-8-bit channel detail'
  if depth==32:
   from oca_validation import image_info
   assert image_info(cached)[2]=='F32','Half output must not alter full-float caches'
   item=node.blend_artwork_exports[1];item.oca_half_float=True
   current=addon.refresh_cached_jobs(scene,dict(jobs=jobs))
   half=next(j for j in current['jobs'] if j['depth']==32)
   assert half['oca_half_float'] is True
   half['dest']=str(out/'half/Precision.oca');half['oca_options'].update(scale=100,padding=4,writeJson=True,writeTemplate=True)
   assemble(half);hd=json.loads(Path(half['dest']).read_text());cel=hd['layers'][0]['frames'][0]
   hp=Path(half['dest']).parent/cel['fileName'];assert image_info(hp)[2]=='F16' and hd['colorDepth']=='F16'
   actual=load(hp,32)[4:-4,4:-4];reference=original[top:bottom,left:right]
   expected_alpha=reference[...,3].astype(np.float16).astype(np.float32)
   expected_rgb=(reference[...,:3]*reference[...,3:4]).astype(np.float16).astype(np.float32)
   np.testing.assert_array_equal(actual[...,3],expected_alpha)
   np.testing.assert_allclose(actual[...,:3]*actual[...,3:4],expected_rgb,atol=1e-6)
   assert actual[...,:3].max()>1
   assert (Path(half['dest']).with_suffix('')/'_companions/Precision.template.png').is_file()
   checks.append(dict(depth='F16',scale=100,padding=4,dimensions=[cel['width'],cel['height']]))
  candidate=copy.deepcopy(job);candidate['oca_options'].update(writeJson=True,writeTemplate=True)
  assemble(candidate)
  companions=Path(candidate['dest']).with_suffix('')/'_companions'
  from PIL import Image
  assert Image.open(companions/'Precision.template.png').size==(33,25)
  assert (companions/'Precision.spine.json').is_file()
 (out/'precision-results.json').write_text(json.dumps(checks,indent=2))
 addon.unregister();print('OCA_NATIVE_PRECISION_PASS',len(checks),'16/32-bit combinations',flush=True)

if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();raise
