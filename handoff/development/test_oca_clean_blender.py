"""Fresh native animation caches -> one selected OCA representation per layer.

Generated outputs stay in HANDOFF_TEST_OUTPUT outside the installed package.
"""
import copy,json,os,sys,traceback
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor'),str(ROOT/'development')]

def run():
 import bpy
 import handoff as addon
 from test_oca_vectors_blender import fixture
 from pillow_loader import ensure_pillow
 ensure_pillow()
 from psd_worker import assemble
 from oca_project import nodes
 from oca_validation import validate
 out=Path(os.environ['HANDOFF_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
 addon.register();scene,tree,node=fixture(bpy)
 scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
 linked=bool(os.environ.get('HANDOFF_TEST_LINKED_GP'))
 if linked:
  bpy.data.objects['Second'].data=bpy.data.objects['First'].data
  # Exact 16-pixel translation: fractional-pixel crops are intentionally not
  # claimed equivalent by the conservative OCA clone conversion.
  for name,x in [('First',-1),('Second',.25)]:
   obj=bpy.data.objects[name];obj.animation_data_clear()
   for frame in range(3):
    obj.location=(x,frame*.2,0);obj.keyframe_insert(data_path='location',frame=frame)
 scene.view_settings.view_transform='Standard'
 scene.render.filepath=str(out/'native/render_');node.directory=str(out/'native');node.file_name='Clean'
 item=node.blend_artwork_exports.add();item.format='OCA';item.enabled=True;item.depth='8'
 item.path=str(out/'exports');item.relative_path=False;item.use_groups=True;item.oca_layout='PROJECT'
 assert not item.oca_write_json and not item.oca_keep_png
 captures=[]
 with patch.object(addon,'launch_worker',side_effect=lambda scene,path,*a,**k:captures.append(Path(path))):
  bpy.ops.render.render(animation=True)
 assert len(captures)==1
 addon.unregister()
 original=next(j for j in json.loads(captures[0].read_text())['jobs'] if j['format']=='OCA')
 reports=[]
 for name,raster,json_output,template in [('Vector',False,False,False),('Raster',True,False,False),('Template',False,False,True),('JSON',False,True,False)]:
  job=copy.deepcopy(original);job.update(dest=str(out/'exports'/(name+'.oca')),bake_svg_png=raster,oca_keep_png=False)
  job['oca_options'].update(writeJson=json_output,writeTemplate=template)
  # Deliberately stale snapshots verify the CURRENT retry choices win.
  for snapshot in job['oca_frames']:
   snapshot['oca_options'].update(writeJson=True,writeTemplate=True)
   snapshot['oca_keep_png']=True;snapshot['bake_svg_png']=not raster
  path=Path(assemble(job));doc=json.loads(path.read_text());validate(doc,path.parent,document_path=path)
  artwork=[n for n in nodes(doc['layers']) if n['type']!='grouplayer']
  clones=int(linked and not raster)
  assert len(artwork)==3 and all(len(n['frames'])==3 for n in artwork if n['type']!='clonelayer')
  assert sum(n['type']=='vectorlayer' for n in artwork)==(0 if raster else 2-clones)
  assert sum(n['type']=='clonelayer' for n in artwork)==clones
  for node in artwork:
   for cel in node['frames']:
    assert not any(key in cel.get('meta',{}).get('handoff',{}) for key in ('raster','editableSource'))
  assert not (path.parent/'_raster').exists() and not (path.parent/'_vectors').exists()
  assert (path.parent/'_companions').exists()==(json_output or template)
  files={str(p.relative_to(path.parent)) for p in path.parent.rglob('*') if p.is_file() and p.suffix in ('.png','.svg') and '_companions' not in p.parts}
  refs={f['fileName'] for n in artwork for f in n['frames'] if f['fileName']}
  assert files==refs,(files-refs,refs-files)
  if json_output:
   data=json.loads((path.parent/'_companions'/f'{name}.spine.json').read_text())
   for skin in data['skins']:
    for attachments in skin['attachments'].values():
     for region in attachments.values():assert (path.parent/(region['path']+'.png')).is_file()
  if template:
   from PIL import Image
   with Image.open(path.parent/'_companions'/f'{name}.template.png') as im:assert im.getchannel('A').getbbox()
   assert not (path.parent/'_companions/images').exists()
  assert not any('OCA raster fallback' in n for n in job['_notices'])
  reports.append(dict(document=str(path),artwork_layers=len(artwork),frames_per_layer=3,assets=len(files),raster=raster,json=json_output,template=template))
 (out/'result.json').write_text(json.dumps(reports,indent=2))
 print('OCA_CLEAN_NATIVE_PASS',flush=True)

if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();raise
