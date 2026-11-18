"""Read-only source diagnosis; render destinations are redirected to test output."""
import json,os,sys
from pathlib import Path
import bpy

out=Path(os.environ['HANDOFF_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
rows=[]
for scene in bpy.data.scenes:
 row=dict(scene=scene.name,frame=scene.frame_current,engine=scene.render.engine,
          size=[scene.render.resolution_x,scene.render.resolution_y],range=[scene.frame_start,scene.frame_end],
          camera=scene.camera.name if scene.camera else None,view_layers=[],gp=[])
 for view in scene.view_layers:
  row['view_layers'].append(dict(name=view.name,use=view.use,flags={p.identifier:getattr(view,p.identifier) for p in view.bl_rna.properties if 'grease' in p.identifier.lower()},
                                gp=[o.name for o in view.objects if o.type=='GREASEPENCIL']))
 for obj in scene.objects:
  if obj.type!='GREASEPENCIL':continue
  row['gp'].append(dict(name=obj.name,hide_render=obj.hide_render,hide_viewport=obj.hide_viewport,
                       location=list(obj.matrix_world.translation),data=obj.data.name,
                       layers=[dict(name=l.name,hide=l.hide,opacity=l.opacity) for l in obj.data.layers],
                       effects=[dict(name=e.name,type=e.type,show_render=e.show_render) for e in obj.shader_effects]))
 rows.append(row)
(out/'scene-inspection.json').write_text(json.dumps(rows,indent=2))
print('HANDOFF_SCENE_INSPECTED',[(r['scene'],r['frame']) for r in rows],flush=True)
if os.environ.get('HANDOFF_TEST_RENDER'):
 scene=next(s for s in bpy.data.scenes if any('Shine' in v.name for v in s.view_layers))
 view=next(v for v in scene.view_layers if 'Shine' in v.name)
 scene.render.resolution_percentage=12;scene.render.use_compositing=False;scene.render.use_sequencer=False
 scene.render.filepath=str(out/'shine-original.png');scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
 for layer in scene.view_layers:layer.use=layer==view
 tree=bpy.data.node_groups.new('GP pass inspection','CompositorNodeTree');scene.compositing_node_group=tree
 source=tree.nodes.new('CompositorNodeRLayers');source.scene=scene;source.layer=view.name
 print('HANDOFF_GP_SOCKETS',[(s.name,s.enabled) for s in source.outputs],flush=True)
 for index,socket in enumerate(source.outputs):
  if socket.name!='Image' and 'grease' not in socket.name.lower():continue
  if os.environ.get('HANDOFF_IMAGE_ONLY') and socket.name!='Image':continue
  target=tree.nodes.new('CompositorNodeOutputFile');target.directory=str(out);target.file_name='pass-'+socket.name.replace(' ','')
  target.format.media_type='IMAGE';target.format.file_format='PNG';target.format.color_mode='RGBA';target.format.color_depth='8'
  target.file_output_items.clear();target.file_output_items.new('RGBA','GP');tree.links.new(socket,target.inputs[0])
 scene.render.use_compositing=True
 bpy.ops.render.render(scene=scene.name,layer=view.name,write_still=True)
 import shutil
 shutil.copy2(out/'pass-ImageGP.png',out/'pass-Image-separated.png')
 print('HANDOFF_GP_PASS_SETTING',view.bl_rna.properties['use_pass_grease_pencil'].description,flush=True)
 view.use_pass_grease_pencil=False
 scene.render.filepath=str(out/'shine-combined.png')
 bpy.ops.render.render(scene=scene.name,layer=view.name,write_still=True)
 print('HANDOFF_GP_NATIVE_RENDER_COMPLETE',flush=True)
