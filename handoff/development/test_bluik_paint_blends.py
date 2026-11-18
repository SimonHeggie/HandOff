"""Native Blender shader/render regression for standard OCA image-plane blends."""
import os,sys,json,traceback,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor'),str(ROOT.parent)]
import bpy,numpy as np
from pillow_loader import ensure_pillow
ensure_pillow()
from PIL import Image
if os.environ.get('BLUIK_SOURCE'):sys.path.insert(0,str(Path(os.environ['BLUIK_SOURCE']).parent))
import bluik_plus
if os.environ.get('BLUIK_SOURCE'):assert Path(bluik_plus.__file__).parent.samefile(os.environ['BLUIK_SOURCE'])
print('BLUIK_PACKAGE',bluik_plus.__file__,flush=True)
from oca_validation import validate
out=Path(os.environ['HANDOFF_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
bluik_plus.register()
scene=bpy.context.scene
scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
scene.view_settings.exposure=0;scene.view_settings.gamma=1
back=np.array([64,153,204,255],np.uint8);front=np.array([204,64,102,153],np.uint8)
def linear(v):
 v=v/255.;return np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
b,f=linear(back[:3].astype(float)),linear(front[:3].astype(float));alpha=front[3]/255

def expected(mode,ba=1.):
 if mode=='multiply':blend=b*f
 elif mode=='add':blend=b+f
 elif mode=='screen':blend=1-(1-b)*(1-f)
 elif mode=='overlay':blend=np.where(b<.5,2*b*f,1-2*(1-b)*(1-f))
 else:blend=f
 return np.r_[f*alpha*(1-ba)+b*ba*(1-alpha)+blend*alpha*ba,alpha+ba*(1-alpha)]

def layer(name,id,filename,mode='normal',visible=True):
 return dict(name=name,id=id,type='paintlayer',animated=False,fileType='png',frames=[dict(name=name,id=id+'-frame',fileName=filename,frameNumber=0,duration=1,width=32,height=32,position=[16,16],opacity=1)],width=32,height=32,position=[16,16],opacity=1.,visible=visible,reference=False,blendingMode=mode,inheritAlpha=False,label=0,meta={})
reports=[]
for case in ['normal','multiply','add','screen','overlay','isolated-overlay','multiply-partial','overlay-partial']:
 mode=case.replace('-partial','');partial=case.endswith('-partial')
 for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
 for coll in list(bpy.data.collections):bpy.data.collections.remove(coll)
 folder=out/case;folder.mkdir(exist_ok=True)
 back_rgba=back.copy()
 if partial:back_rgba[3]=102
 Image.fromarray(np.tile(back_rgba,(32,32,1))).save(folder/'Back.png');Image.fromarray(np.tile(front,(32,32,1))).save(folder/'Front.png')
 base=layer('Back','back','Back.png');top=layer('Front (2)','front','Front.png',mode if mode!='isolated-overlay' else 'normal')
 top['meta']=dict(handoff=dict(originalName='Front'))
 group=dict(name='Front',id='group',type='grouplayer',animated=False,fileType='png',frames=[],childLayers=[top],width=32,height=32,position=[16,16],opacity=1.,visible=True,reference=False,blendingMode='overlay' if mode=='isolated-overlay' else 'normal',passThrough=mode!='isolated-overlay',inheritAlpha=False,label=0,meta={})
 doc=dict(name='Fixture',ocaVersion='1.3.0',frameRate=24,width=32,height=32,startTime=0,endTime=1,colorDepth='U8',backgroundColor=[0,0,0,0],layers=[base,group])
 path=folder/'Fixture.oca';path.write_text(json.dumps(doc));validate(doc,folder,document_path=path)
 result=getattr(bpy.ops.import_oca,'import')('EXEC_DEFAULT',filepath=str(path),directory=str(folder),shader='EMISSION',render_settings='REALTIME',color_management='DEFAULT',update_timeline=True)
 assert result=={'FINISHED'},result
 assert scene.render.engine=='BLENDER_EEVEE'
 obj=next(o for o in scene.objects if o.get('oca_layer_id')=='front')
 assert obj.name=='Front' and bpy.data.collections.get('Front')
 assert not obj.hide_render
 if mode!='normal':assert obj.active_material.get('oca_effective_blending_mode')==mode.replace('isolated-','')
 scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=2048;scene.cycles.use_denoising=False
 scene.cycles.transparent_max_bounces=64
 scene.render.resolution_percentage=100;scene.render.use_compositing=False;scene.render.use_sequencer=False
 scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_depth='32';scene.render.image_settings.color_mode='RGBA'
 from psd_worker import read_blender_pixels
 # Establish independently rendered texture inputs. Blender's byte-PNG alpha
 # association can quantise the sampled RGB; that is not paint-blend error.
 # Force BOTH Color and Alpha to be evaluated, matching the actual materials.
 def sampled(target,a):
  objects=[o for o in scene.objects if o.get('oca_layer_id')]
  visibility={o:o.visible_camera for o in objects}
  for o in objects:o.visible_camera=o==target
  nt=target.active_material.node_tree
  art=nt.nodes['OCA Artwork'] if 'OCA Artwork' in nt.nodes else None
  if art is None:
   texture=next(n for n in nt.nodes if n.type=='TEX_IMAGE');color,opacity=texture.outputs['Color'],texture.outputs['Alpha']
  else:color,opacity=art.outputs['Color'],art.outputs['Alpha']
  emission=next(n for n in nt.nodes if n.type=='EMISSION');output=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL')
  old_color=emission.inputs['Color'].links[0].from_socket;old_surface=output.inputs['Surface'].links[0].from_socket
  gain=nt.nodes.new('ShaderNodeMath');gain.operation='ADD';gain.inputs[1].default_value=1.
  nt.links.new(opacity,gain.inputs[0]);nt.links.new(gain.outputs[0],emission.inputs['Strength'])
  nt.links.new(color,emission.inputs['Color']);nt.links.new(emission.outputs[0],output.inputs['Surface'])
  scene.render.filepath=str(folder/(target.name+'-input.exr'));bpy.ops.render.render(write_still=True)
  value=read_blender_pixels(scene.render.filepath)[8:24,8:24,:3].mean(axis=(0,1))/(1+a)
  nt.links.new(old_color,emission.inputs['Color']);nt.links.new(old_surface,output.inputs['Surface']);nt.nodes.remove(gain);emission.inputs['Strength'].default_value=1.
  for o,shown in visibility.items():o.visible_camera=shown
  return value
 b=sampled(next(o for o in scene.objects if o.get('oca_layer_id')=='back'),.4 if partial else 1.)
 f=sampled(obj,alpha)
 scene.render.filepath=str(folder/'render.exr');bpy.ops.render.render(write_still=True)
 pixels=read_blender_pixels(folder/'render.exr');actual=pixels[8:24,8:24].mean(axis=(0,1))
 reference=expected(mode.replace('isolated-',''),ba=.4 if partial else 1.);error=float(abs(actual-reference).max())
 assert error<.00003,(mode,actual,reference,error)
 reports.append(dict(mode=case,actual=actual.tolist(),expected=reference.tolist(),max_error=error))
 if case=='overlay':
  from bluik_plus.eevee_optimise import apply_render_settings
  apply_render_settings();assert scene.render.engine=='BLENDER_EEVEE';scene.eevee.taa_render_samples=128
  scene.render.use_motion_blur=False;scene.render.filepath=str(folder/'eevee.exr');bpy.ops.render.render(write_still=True)
  pixels=read_blender_pixels(folder/'eevee.exr');actual=pixels[8:24,8:24].mean(axis=(0,1));error=float(abs(actual-reference).max())
  assert error<.003,('Eevee',actual,reference,error)
  reports.append(dict(mode='overlay-eevee',max_error=error,actual=actual.tolist()))
# Import setup errors must restore Blender's prior edit-mode preference.
from unittest.mock import patch
from bluik_plus import eevee_optimise
before=bpy.context.preferences.edit.use_enter_edit_mode
try:
 bpy.context.preferences.edit.use_enter_edit_mode=True
 with patch.object(eevee_optimise,'apply_realtime_settings',side_effect=RuntimeError('intentional setup failure')):
  try:
   getattr(bpy.ops.import_oca,'import')('EXEC_DEFAULT',filepath=str(path),directory=str(folder),shader='EMISSION',render_settings='REALTIME',color_management='DEFAULT')
  except RuntimeError as exc:assert 'intentional setup failure' in str(exc)
 assert bpy.context.preferences.edit.use_enter_edit_mode is True
finally:bpy.context.preferences.edit.use_enter_edit_mode=before
(out/'result.json').write_text(json.dumps(reports,indent=2))
bluik_plus.unregister()
print('BLUIK_PAINT_BLENDS_PASS',json.dumps(reports),flush=True)
