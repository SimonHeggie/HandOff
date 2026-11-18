"""Native still-to-animation OCA 1.3 publication, IDs and mixed GP/raster.

Run in factory Blender 5.3 with HANDOFF_TEST_OUTPUT outside the package.
"""
import copy,json,os,sys,traceback
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor'),str(ROOT/'development')]

def run():
 import bpy,numpy as np
 import handoff as addon
 from test_oca_vectors_blender import fixture
 from pillow_loader import ensure_pillow
 ensure_pillow()
 from PIL import Image
 from oca_controls import input_identity
 from oca_project import nodes
 from oca_validation import validate
 os.environ['HANDOFF_TEST_START']='-2';os.environ['HANDOFF_TEST_BLANK_GP']='1'
 addon.register();scene,tree,node=fixture(bpy)
 scene.cycles.samples=1;scene.cycles.device='CPU';scene.cycles.use_denoising=False
 scene.render.fps=24;scene.render.fps_base=1.001;scene.view_settings.view_transform='Standard'
 scene['author']='Fixture Artist';scene['license']='CC0-1.0'
 out=Path(os.environ['HANDOFF_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
 node.directory=str(out/'native');node.file_name='Mixed';scene.render.filepath=str(out/'native/render_')
 for item,name in zip(node.file_output_items,('Parts/Paint.add','Parts/Paint.multiply','Processed.ref')):item.name=name
 first=bpy.data.objects['First'];first.data.layers[0].opacity=.5
 item=node.blend_artwork_exports.add();item.format='OCA'
 assert item.oca_layout=='PROJECT','New destinations should default to standard project folders'
 item.enabled=True;item.depth='8';item.path=str(out/'exports');item.relative_path=False;item.use_groups=True
 item.oca_ignore_hidden_layers=False;item.oca_keep_png=True;item.oca_write_json=False;item.oca_write_template=False
 before={s.identifier:input_identity(node,s) for s in node.inputs if s.is_linked}
 node.file_output_items.move(0,1)
 assert before=={s.identifier:input_identity(node,s) for s in node.inputs if s.is_linked}
 node.file_output_items.move(1,0)
 scene.frame_set(-2)
 saved=out/'fixture.blend';bpy.ops.wm.save_as_mainfile(filepath=str(saved))
 captures=[]
 with patch.object(addon,'launch_worker',side_effect=lambda scene,path,*a,**k:captures.append(Path(path))):
  bpy.ops.render.render()
  for frame in (-1,0):
   scene.frame_set(frame);bpy.ops.render.render()
 assert len(captures)==3,captures
 # Blender's animation-range RNA clamps start/end to zero, but frame_set and
 # its render cache support negative frames. Exercise the sequence assembler
 # with these three genuinely rendered frames rather than fake pixel files.
 captured=[json.loads(p.read_text())['jobs'][0] for p in captures]
 sequence=copy.deepcopy(captured[-1]);sequence['oca_frames']=copy.deepcopy(captured);sequence['oca_range']=[-2,0,1]
 sequence_file=out/'negative-sequence.json';sequence_file.write_text(json.dumps(dict(jobs=[sequence])))
 assert all(e.get('oca_source_id') for e in json.loads(captures[0].read_text())['jobs'][0]['manifest'])
 addon.unregister()
 from psd_worker import run as convert
 assert convert(captures[0])==0
 document_path=out/'exports/Mixed.oca/Mixed.oca'
 still=json.loads(document_path.read_text());validate(still,document_path.parent)
 assert all(not n['animated'] for n in nodes(still['layers']))
 assert convert(sequence_file)==0
 document=json.loads(document_path.read_text());validate(document,document_path.parent,document_path=document_path)
 assert (document['startTime'],document['endTime'])==(-2,1)
 assert document['frameRate']==captured[0]['frame_rate']
 assert abs(document['frameRate']-24/1.001)<2e-6
 stable=lambda d:{n['meta']['handoff']['sourceIdentity']:n['id'] for n in nodes(d['layers'])}
 assert stable(still)==stable(document)
 all_nodes=list(nodes(document['layers']));assert len({n['name'] for n in all_nodes})==len(all_nodes)
 paint=[n for n in all_nodes if n['type']!='grouplayer']
 assert len(paint)==3 and sum(n['type']=='vectorlayer' for n in paint)==2
 assert len({n['id'] for n in all_nodes}|{f['id'] for n in paint for f in n['frames']})==len(all_nodes)+9
 assert any(n['reference'] and not n['visible'] for n in paint)
 for n in paint:
  assert n['animated'] and [f['frameNumber'] for f in n['frames']]==[-2,-1,0]
  assert n['opacity']==1 and all(f['opacity']==1 for f in n['frames']), 'Baked opacity must not be applied again'
  for f in n['frames']:
   if f['name']=='_blank':continue
   assert not Path(f['fileName']).name[0].isdigit()
   assert (document_path.parent/f['fileName']).is_file()
   if n['type']=='vectorlayer':
    alt=f['meta']['handoff']['raster'];im=Image.open(document_path.parent/alt['fileName'])
    assert im.getchannel('A').getbbox() and im.size==(f['width'],f['height'])
 assert any(f['name']=='_blank' for n in paint for f in n['frames'])
 half=next(n for n in paint if n['meta']['handoff']['sourceName']=='Parts/Paint.add')
 preview=half['frames'][0]['meta']['handoff']['raster']
 alpha=np.asarray(Image.open(document_path.parent/preview['fileName']))[...,3]
 assert 110<=alpha.max()<=140,alpha.max()
 meta=json.loads(document_path.with_name('Mixed_meta.json').read_text())
 assert meta['author']=='Fixture Artist' and meta['license']=='CC0-1.0'
 assert meta['exportedBy']=='HandOff' and meta['originAppVersion']==bpy.app.version_string
 # Move the entire standard project: all raster and SVG alternatives remain local.
 import shutil
 moved=out/'relocated/Mixed.oca';moved.parent.mkdir(exist_ok=True)
 if moved.exists():shutil.rmtree(moved)
 shutil.copytree(document_path.parent,moved);validate(document,moved,document_path=moved/'Mixed.oca')
 (out/'result.json').write_text(json.dumps(dict(document=str(document_path),blender=bpy.app.version_string,
  mixed_layers=3,negative_start=-2,unique_names=True,stable_ids=True,reordered_inputs=True,
  metadata=True,relocation=True,baked_opacity_once=True,blank_frames=True),indent=2))
 print('OCA13_NATIVE_PASS',str(document_path),flush=True)

if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();raise
