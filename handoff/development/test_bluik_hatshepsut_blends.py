"""Import repaired Hatshepsut OCA, assert names/visibility/wiring, render both engines."""
import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
import bpy
import bluik_plus
out=Path(os.environ['HANDOFF_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
path=Path(os.environ['BLUIK_TEST_DOCUMENT'])
bluik_plus.register()
for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
scene=bpy.context.scene
result=getattr(bpy.ops.import_oca,'import')('EXEC_DEFAULT',filepath=str(path),directory=str(path.parent),shader='EMISSION',render_settings='REALTIME',color_management='AUTO',update_timeline=True)
assert result=={'FINISHED'},result
assert scene.render.engine=='BLENDER_EEVEE'
objects={o.name:o for o in scene.objects if o.get('oca_layer_id')}
assert len(objects)==21,len(objects)
for name,mode in [('Eyes_Shade','multiply'),('Eyes_Reflect','add'),('Shine','overlay')]:
 obj=objects[name]
 assert not obj.hide_render and not obj.hide_viewport,(name,'Unexpectedly hidden')
 assert obj.active_material.get('oca_effective_blending_mode')==mode
 assert any(n.name=='OCA Backdrop' for n in obj.active_material.node_tree.nodes)
for name in ('ForeArm_R','ForeArm_L','UpperLashes','Sceptres_R','Sceptres_L','Shine'):
 assert name in objects and bpy.data.collections.get(name),name
assert not any(' (2)' in name for name in objects),list(objects)
scene.render.resolution_percentage=12;scene.render.use_compositing=False;scene.render.use_sequencer=False;scene.render.use_motion_blur=False
scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='8'
scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=False;scene.cycles.transparent_max_bounces=64
for engine in ['CYCLES','BLENDER_EEVEE']:
 scene.render.engine=engine
 if engine=='BLENDER_EEVEE':scene.eevee.taa_render_samples=64
 scene.render.filepath=str(out/(engine+'.png'));bpy.ops.render.render(write_still=True)
 im=bpy.data.images.load(scene.render.filepath,check_existing=False);assert max(list(im.pixels)[3::4])>0;bpy.data.images.remove(im)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Hatshepsut-imported.blend'))
(out/'result.json').write_text(json.dumps(dict(document=str(path),layers=len(objects),names_restored=True,eye_effects_visible=True,modes={n:objects[n].get('oca_effective_blending_mode') for n in ('Eyes_Shade','Eyes_Reflect','Shine')},engines=['CYCLES','BLENDER_EEVEE']),indent=2))
bluik_plus.unregister()
print('BLUIK_HATSHEPSUT_BLENDS_PASS',flush=True)
