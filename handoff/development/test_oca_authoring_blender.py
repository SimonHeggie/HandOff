"""Real OCA authoring: opacity animation, alpha inheritance, explicit references."""
import os,sys,json,traceback,copy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor'),str(ROOT/'development')]

def run():
 import bpy
 import handoff as addon
 from test_oca_vectors_blender import fixture
 from pillow_loader import ensure_pillow
 ensure_pillow()
 from oca_project import nodes
 addon.register();scene,tree,node=fixture(bpy)
 scene.cycles.samples=1;scene.cycles.device='CPU';scene.cycles.use_denoising=False
 scene.view_settings.view_transform='Standard'
 first=scene.view_layers['First'];first.handoff_oca_opacity=.8
 for frame,opacity in ((0,.25),(1,.5),(2,.75)):
  first.handoff_oca_frame_opacity=opacity;first.keyframe_insert(data_path='handoff_oca_frame_opacity',frame=frame)
 group=bpy.data.collections['First'];group.handoff_oca_opacity=.5;group.handoff_oca_isolate=True
 scene.view_layers['Second'].handoff_oca_inherit_alpha=True
 scene.handoff_oca_background_color=(.02,.04,.08,.25)
 source=Path(os.environ['HANDOFF_NESTED_SOURCE']).resolve()
 for name in ('Nested','Clone'):
  view=scene.view_layers.new(name)
  for child in view.layer_collection.children:
   if child.name in ('First','Second'):child.exclude=True
  if name=='Nested':view.handoff_oca_external_document=str(source);view.handoff_oca_time_offset=-1
  else:view.handoff_oca_source_layer='First';view.handoff_oca_time_offset=1;view.handoff_oca_offset=(20,0)
  render=tree.nodes.new('CompositorNodeRLayers');render.scene=scene;render.layer=name
  node.file_output_items.new('RGBA',name);tree.links.new(render.outputs['Image'],node.inputs[len(node.file_output_items)-1])
 out=Path(os.environ['HANDOFF_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
 node.directory=str(out/'native');node.file_name='Authored';scene.render.filepath=str(out/'native/render_')
 item=node.blend_artwork_exports.add();item.format='OCA';item.enabled=True;item.depth='8';item.path=str(out/'exports');item.relative_path=False;item.use_groups=True
 item.oca_keep_png=True;item.oca_write_json=True;item.oca_write_template=True
 captures=[]
 with patch.object(addon,'launch_worker',side_effect=lambda scene,path,*a,**k:captures.append(Path(path))):bpy.ops.render.render(animation=True)
 assert len(captures)==1
 payload=json.loads(captures[0].read_text());job=payload['jobs'][0]
 assert [next(e for e in f['manifest'] if e['name']=='First')['oca_authored']['frameOpacity'] for f in job['oca_frames']]==[.25,.5,.75]
 # Change independently authored frame metadata after rendering, then retry
 # against exactly the same PNG/SVG cache without another render call.
 for frame,opacity in ((0,.15),(1,.45),(2,.95)):
  first.handoff_oca_frame_opacity=opacity;first.keyframe_insert(data_path='handoff_oca_frame_opacity',frame=frame)
 before=scene.frame_current
 refreshed=addon.refresh_cached_jobs(scene,payload,allow_pending_vectors=True)
 assert scene.frame_current==before
 retry_job=refreshed['jobs'][0];retry_job['dest']=str(out/'exports/AuthoredRetry.oca')
 retry_file=out/'retry.json';retry_file.write_text(json.dumps(refreshed))
 addon.unregister()
 from psd_worker import run as convert
 assert convert(captures[0])==0
 path=out/'exports/Authored.oca/Authored.oca';document=json.loads(path.read_text());all_layers=list(nodes(document['layers']))
 first=next(n for n in all_layers if n.get('meta',{}).get('handoff',{}).get('sourceName')=='First')
 assert abs(first['opacity']-.8)<1e-6
 assert [f['opacity'] for f in first['frames']]==[.25,.5,.75]
 groups=[n for n in all_layers if n['type']=='grouplayer'];assert any(abs(n['opacity']-.5)<1e-6 and not n['passThrough'] for n in groups)
 assert any(n['inheritAlpha'] for n in all_layers)
 clone=next(n for n in all_layers if n['type']=='clonelayer');assert clone['source']['id']==first['id'] and clone['source']['timeOffset']==1
 assert clone['position']==[52,32]
 nested=next(n for n in all_layers if n['type']=='ocalayer');assert nested['source']['timeOffset']==-1
 assert (path.parent/nested['source']['relFileName']).is_file()
 assert abs(document['backgroundColor'][3]-.25)<1e-6
 from oca_validation import validate
 validate(document,path.parent,document_path=path)
 from PIL import Image
 template=Image.open(path.parent/'_companions/Authored.template.png');assert template.size==(64,64) and template.getchannel('A').getbbox()
 assert (path.parent/'_companions/Authored.spine.json').is_file()
 assert convert(retry_file)==0
 retried=json.loads((out/'exports/AuthoredRetry.oca/AuthoredRetry.oca').read_text())
 retry_first=next(n for n in nodes(retried['layers']) if n.get('meta',{}).get('handoff',{}).get('sourceName')=='First')
 import numpy as np
 np.testing.assert_allclose([f['opacity'] for f in retry_first['frames']],[.15,.45,.95],atol=1e-6)
 (out/'result.json').write_text(json.dumps(dict(document=str(path),animated_frame_opacity=True,independent_opacity=True,inherit_alpha=True,isolated_group=True,coloured_background=True,explicit_clone=True,portable_nested_document=True,template=True,current_authoring_retry=True),indent=2))
 print('OCA_AUTHORING_NATIVE_PASS',str(path),flush=True)
if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();raise
