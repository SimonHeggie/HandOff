"""Actual Bluik Plus registration/operator import, render and saved-file checks."""
import bpy,os,sys,json,traceback
from pathlib import Path
source=Path(os.environ['BLUIK_SOURCE']);sys.path.insert(0,str(source.parent))
import bluik_plus
out=Path(os.environ['BLUIK_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
path=Path(os.environ['BLUIK_TEST_DOCUMENT']).resolve()
try:
 bluik_plus.register()
 scene=bpy.context.scene
 for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
 result=getattr(bpy.ops.import_oca,'import')('EXEC_DEFAULT',filepath=str(path),directory=str(path.parent),shader='EMISSION',render_settings='DEFAULT',color_management='DEFAULT',update_timeline=True)
 assert result=={'FINISHED'},result
 root=next(c for c in bpy.data.collections if c.get('oca_document_path')==str(path))
 objects=[o for o in root.all_objects if o.get('oca_layer_id')]
 assert objects,'Import produced no artwork'
 if os.environ.get('BLUIK_ASSERT_CLONES'):
  clones=[o for o in objects if o.get('oca_source_id')]
  assert clones,'Fixture must exercise clones'
  for clone in clones:
   original=next(o for o in objects if o.get('oca_layer_id')==clone['oca_source_id'])
   assert clone.data==original.data,(clone.name,'Clone lost shared datablock')
 scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
 scene.render.use_compositing=False;scene.render.use_sequencer=False;scene.view_settings.view_transform='Standard'
 scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='8'
 if os.environ.get('BLUIK_ASSERT_HDR'):
  images=[n.image for o in objects if o.type=='MESH' for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.bl_idname=='ShaderNodeTexImage' and n.image]
  assert images and any(im.is_float and max(im.pixels)>1 for im in images),'Floating-point HDR source was quantized'
 checks=[]
 doc=json.loads(path.read_text())
 for frame in range(doc['startTime'],doc['endTime']):
  scene.frame_set(frame);scene.render.filepath=str(out/f'render_{frame}.png');bpy.ops.render.render(write_still=True)
  pixels=bpy.data.images.load(scene.render.filepath,check_existing=False)
  values=list(pixels.pixels)[3::4]
  assert values,'Rendered PNG could not be decoded'
  assert max(values)>0,'Import render is entirely transparent'
  bpy.data.images.remove(pixels)
  checks.append(dict(frame=frame,objects=[dict(name=o.name,type=o.type,hidden=o.hide_render,location=list(o.location),scale=list(o.scale),data=o.data.name if o.data else None) for o in objects]))
 if os.environ.get('BLUIK_TEST_EDIT'):
  sys.path.insert(0,str(Path(__file__).parent))
  from edit_proof import run as prove_edit
  prove_edit(scene,objects,out,doc['startTime'])
 if os.environ.get('BLUIK_TEST_TIME'):
  sys.path.insert(0,str(Path(__file__).parent))
  from edit_proof import prove_time_offset
  prove_time_offset(scene,objects,out)
 # Save before unregistering so custom property data survives, then verify it
 # separately in a fresh Blender process.
 bpy.ops.wm.save_as_mainfile(filepath=str(out/'imported.blend'))
 (out/'result.json').write_text(json.dumps(dict(source=str(source),document=str(path),blender=bpy.app.version_string,
  objects=len(objects),vectors=sum(o.type=='GREASEPENCIL' for o in objects),checks=checks,warnings=json.loads(root['oca_import_warnings'])),indent=2))
 bluik_plus.unregister()
 assert not any(fn.__module__.startswith('bluik_plus') for fn in bpy.app.handlers.frame_change_post)
 print('BLUIK_IMPORT_NATIVE_PASS',len(objects),'objects',flush=True)
except BaseException:traceback.print_exc();raise
