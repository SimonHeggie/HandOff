"""Native OCA cropped-frame transforms, texture/opacity timing, blank and reopen."""
import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor'),str(ROOT.parent)]
import bpy,numpy as np
from pillow_loader import ensure_pillow
ensure_pillow()
from PIL import Image
if os.environ.get('BLUIK_SOURCE'):sys.path.insert(0,str(Path(os.environ['BLUIK_SOURCE']).parent))
import bluik_plus
if os.environ.get('BLUIK_SOURCE'):assert Path(bluik_plus.__file__).parent.samefile(os.environ['BLUIK_SOURCE'])
print('BLUIK_PACKAGE',bluik_plus.__file__,flush=True)
from psd_worker import read_blender_pixels
out=Path(os.environ['HANDOFF_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
bluik_plus.register();scene=bpy.context.scene
if not os.environ.get('BLUIK_REOPEN_BLEND'):
 for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
 def asset(name,rgba,size=(32,32)):
  Image.fromarray(np.tile(np.array(rgba,np.uint8),(size[1],size[0],1))).save(out/name)
 asset('Back.png',[64,153,204,255]);asset('Top.png',[128,204,153,255])
 asset('F0.png',[204,64,102,153],(16,16));asset('F1.png',[64,204,64,153],(20,12))
 def cel(name,file,frame,w=32,h=32,pos=(16,16),alpha=1):
  return dict(name=name,id=name+str(frame),fileName=file,frameNumber=frame,duration=1,position=list(pos),width=w,height=h,opacity=alpha)
 def layer(name,mode,frames):
  return dict(name=name,id=name,type='paintlayer',animated=True,fileType='png',width=32,height=32,position=[16,16],opacity=1.,visible=True,reference=False,blendingMode=mode,inheritAlpha=False,label=0,meta={},frames=frames)
 doc=dict(name='Timing',ocaVersion='1.3.0',width=32,height=32,frameRate=24,startTime=0,endTime=3,colorDepth='U8',backgroundColor=[0,0,0,0],layers=[
  layer('Back','normal',[dict(cel('Back','Back.png',0),duration=3)]),
  layer('Moving','overlay',[cel('F0','F0.png',0,16,16,(12,14),.4),cel('F1','F1.png',1,20,12,(16,16),.9),cel('_blank','',2,0,0,(0,0))]),
  layer('Top','multiply',[dict(cel('Top','Top.png',0),duration=3)])])
 path=out/'Timing.oca';path.write_text(json.dumps(doc))
 assert getattr(bpy.ops.import_oca,'import')('EXEC_DEFAULT',filepath=str(path),directory=str(out),shader='EMISSION',render_settings='RENDER',color_management='AUTO',update_timeline=True)=={'FINISHED'}
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=256;scene.cycles.use_denoising=False;scene.cycles.transparent_max_bounces=64
scene.render.resolution_percentage=100;scene.render.use_compositing=False;scene.render.use_sequencer=False;scene.render.use_motion_blur=False
scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_depth='32';scene.render.image_settings.color_mode='RGBA'
scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
def lin(values):
 v=np.array(values,dtype=float)/255.;return np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
back=lin([64,153,204]);top=lin([128,204,153]);checks=[]
for frame in range(3):
 scene.frame_set(frame)
 moving=next(o for o in scene.objects if o.get('oca_layer_id')=='Moving')
 assert moving.hide_render==(frame==2)
 base=back.copy()
 if frame<2:
  front=lin([204,64,102] if frame==0 else [64,204,64]);alpha=.6*(.4 if frame==0 else .9)
  base=base*(1-alpha)+np.where(base<=.5,2*base*front,1-2*(1-base)*(1-front))*alpha
 expected=np.r_[base*top,1.]
 scene.render.filepath=str(out/f'render-{frame}.exr');bpy.ops.render.render(write_still=True)
 actual=read_blender_pixels(scene.render.filepath)[13:19,13:19].mean(axis=(0,1));error=float(abs(actual-expected).max())
 assert error<.008,(frame,actual,expected,error)
 checks.append(dict(frame=frame,max_error=error,actual=actual.tolist(),expected=expected.tolist()))
if not os.environ.get('BLUIK_REOPEN_BLEND'):bpy.ops.wm.save_as_mainfile(filepath=str(out/'timing.blend'))
(out/'result.json').write_text(json.dumps(checks,indent=2));bluik_plus.unregister()
print('BLUIK_PAINT_ANIMATION_PASS',json.dumps(checks),flush=True)
