"""Real OCA files: compliance, portable publication and failure protection."""
import copy,json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from psd_worker import assemble
from oca_project import nodes,publish
from oca_validation import validate,OCAValidationError


class Compliance(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.cache=self.root/'cache';self.cache.mkdir()
  for i,color in enumerate(('red','green','blue')):Image.new('RGBA',(9,7),color).save(self.cache/f'L{i}_0001.png')
 def job(self,layout='PROJECT'):
  return dict(format='OCA',dest=str(self.root/'Character.oca'),oca_layout=layout,dir=str(self.cache),
   extension='.png',depth=8,frame=1,cache_frame=1,frame_rate=23.976,canvas_size=[9,7],
   hierarchy='GROUPS',overwrite=True,oca_options=dict(writeJson=False,writeTemplate=False,padding=0),
   origin_app_version='5.3.0',manifest=[dict(name='Eyes.add',slug='L0_',collection_path='Eyes',oca_source_id='socket-A'),
                                     dict(name='Eyes.multiply',slug='L1_',collection_path='Eyes',oca_source_id='socket-B')])
 def export(self,job):
  path=Path(assemble(job));return path,json.loads(path.read_text())
 def test_canonical_project_metadata_and_relocation(self):
  job=self.job();job['oca_metadata']=dict(author='Explicit Artist',license='CC0-1.0')
  path,doc=self.export(job)
  self.assertEqual(path,self.root/'Character.oca/Character.oca')
  self.assertEqual(list(path.parent.glob('*.oca')),[path]);self.assertNotIn('meta',doc)
  meta=json.loads(path.with_name('Character_meta.json').read_text())
  self.assertEqual((meta['exportedBy'],meta['originApp'],meta['originAppVersion']),('HandOff','Blender','5.3.0'))
  self.assertEqual(meta['author'],'Explicit Artist');self.assertNotIn('copyright',meta)
  moved=self.root/'Moved.oca';shutil.move(path.parent,moved)
  validate(doc,moved,document_path=moved/path.name)
 def test_legacy_layout_and_metadata_preservation(self):
  job=self.job('LEGACY');path,doc=self.export(job)
  self.assertEqual(path,self.root/'Character.oca');self.assertTrue((self.root/'Character').is_dir())
  meta=path.with_name('Character_meta.json');data=json.loads(meta.read_text());data.update(copyright='Artist-owned',license='Custom licence');meta.write_text(json.dumps(data))
  self.export(job);after=json.loads(meta.read_text());self.assertEqual(after['copyright'],'Artist-owned');self.assertEqual(after['license'],'Custom licence')
 def test_unique_names_ids_and_stable_identity_after_reorder(self):
  job=self.job();path,before=self.export(job)
  layers=list(nodes(before['layers']));self.assertEqual(len({n['name'] for n in layers}),len(layers))
  ids=[n['id'] for n in layers]+[c['id'] for n in layers for c in n['frames']]
  self.assertEqual(len(ids),len(set(ids)))
  identity=lambda doc:{n['meta']['handoff']['sourceIdentity']:(n['id'],n['name']) for n in nodes(doc['layers'])}
  job['manifest'].reverse();_,after=self.export(job)
  self.assertEqual(identity(before),identity(after))
  self.assertNotEqual([n['id'] for n in layers[0]['childLayers']],[n['id'] for n in after['layers'][0]['childLayers']])
 def test_portable_names_case_unicode_and_reserved_components(self):
  job=self.job();job['manifest']=[dict(name='CON',slug='L0_',collection_path='Éyes'),dict(name='AUX',slug='L1_',collection_path='éyes'),dict(name='表情',slug='L2_',collection_path='Ｅyes')]
  path,doc=self.export(job);files=[c['fileName'] for n in nodes(doc['layers']) for c in n['frames']]
  self.assertEqual(len(files),len({s.casefold() for s in files}))
  self.assertTrue(any('CON_' in s for s in files));self.assertTrue(any('表情' in s for s in files))
  validate(doc,path.parent)
 def test_normalization_collision_keeps_extension_and_frame_number(self):
  from oca_project import _portable_assets
  source=self.root/'Old';source.mkdir();ready=self.root/'Ready';ready.mkdir()
  names=['é_00001.png','e\u0301_00001.png']
  for name in names:Image.new('RGBA',(3,3),'red').save(source/name)
  doc=dict(layers=[dict(frames=[dict(fileName='Old/'+name) for name in names])])
  _portable_assets(doc,source,ready,'')
  files=[c['fileName'] for c in doc['layers'][0]['frames']]
  self.assertEqual(len(set(name.casefold() for name in files)),2)
  self.assertTrue(all(name.endswith('_00001.png') for name in files))
  self.assertTrue(all((ready/name).is_file() for name in files))
 def test_long_asset_names_keep_format_extension(self):
  job=self.job();job['manifest'][0]['name']='非常に長い名前'*20
  path,doc=self.export(job)
  files=[c['fileName'] for n in nodes(doc['layers']) for c in n['frames']]
  self.assertTrue(all(Path(name).suffix=='.png' for name in files))
  self.assertTrue(all(len(Path(name).name.encode('utf-8'))<=240 for name in files))
  self.assertTrue(all(Path(name).name.endswith('_00001.png') for name in files))
  validate(doc,path.parent)
 def test_failed_validation_preserves_previous_project(self):
  job=self.job();path,doc=self.export(job);old={p.relative_to(path.parent):p.read_bytes() for p in path.parent.rglob('*') if p.is_file()}
  def broken(internal):
   result=Path(assemble(internal));data=json.loads(result.read_text());first=next(n for n in nodes(data['layers']) if n['frames'])['frames'][0]
   (result.parent/first['fileName']).unlink();return str(result)
  with self.assertRaisesRegex(ValueError,'missing artwork'):publish(job,broken)
  self.assertEqual(old,{p.relative_to(path.parent):p.read_bytes() for p in path.parent.rglob('*') if p.is_file()})
 def test_failed_commit_rolls_back_old_project(self):
  job=self.job();path,doc=self.export(job);before=path.read_bytes();original=Path.replace
  def fail_install(source,destination):
   if source.name=='ready':raise OSError('injected install failure')
   return original(source,destination)
  with patch.object(Path,'replace',fail_install),self.assertRaisesRegex(OSError,'injected'):self.export(job)
  self.assertEqual(before,path.read_bytes());validate(json.loads(before),path.parent)
  self.assertFalse(list(self.root.glob('.*.oca-backup-*')))
 def test_exact_validation_diagnostics(self):
  path,doc=self.export(self.job())
  cases=[('ocaVersion',lambda d:d.update(ocaVersion='0.0.0')),('width',lambda d:d.update(width=0)),
         ('frameRate',lambda d:d.update(frameRate=0)),('endTime',lambda d:d.update(endTime=d['startTime'])),
         ('schema',lambda d:d.update(originApp='wrong root')),
         ('name',lambda d:d['layers'].append(copy.deepcopy(d['layers'][0])))]
  for expected,change in cases:
   bad=copy.deepcopy(doc);change(bad)
   with self.subTest(expected=expected),self.assertRaisesRegex(OCAValidationError,expected):validate(bad,path.parent)
  leaf=next(n for n in nodes(doc['layers']) if n['frames']);cel=leaf['frames'][0]
  for key,value in [('fileName','../escape.png'),('width',99),('duration',0),('position',[float('nan'),1]),('id',leaf['id'])]:
   bad=copy.deepcopy(doc);next(n for n in nodes(bad['layers']) if n['frames'])['frames'][0][key]=value
   with self.subTest(property=key),self.assertRaises(OCAValidationError):validate(bad,path.parent)
 def test_clone_references_and_nested_documents_are_validated(self):
  path,doc=self.export(self.job());source=next(n for n in nodes(doc['layers']) if n['frames'])
  clone=dict(name='Linked instance',id='clone-1',type='clonelayer',source=dict(id=source['id'],timeOffset=0),position=[12,8])
  doc['layers'].append(clone);validate(doc,path.parent)
  clone['source']['id']='missing'
  with self.assertRaisesRegex(OCAValidationError,'source.id'):validate(doc,path.parent)
  clone['source']['id']=clone['id']
  with self.assertRaisesRegex(OCAValidationError,'cyclic'):validate(doc,path.parent)
  doc['layers'].pop()
  nested=dict(name='External document',id='external-1',type='ocalayer',source=dict(id='',relFileName='../Character.oca/Character.oca',absFileName='/does/not/exist.oca',timeOffset=-2))
  parent=copy.deepcopy(doc);parent['layers']=[nested];parent_dir=self.root/'Parent.oca';parent_dir.mkdir()
  validate(parent,parent_dir,document_path=parent_dir/'Parent.oca')
  nested['source']['relFileName']='missing.oca'
  with self.assertRaisesRegex(OCAValidationError,'missing nested'):validate(parent,parent_dir)
 def test_invalid_metadata_preserves_existing_project(self):
  job=self.job();path,doc=self.export(job);before=path.read_bytes()
  sidecar=path.with_name('Character_meta.json');data=json.loads(sidecar.read_text());data['author']=42
  sidecar.write_text(json.dumps(data))
  with self.assertRaisesRegex(OCAValidationError,'metadata.author'):self.export(job)
  self.assertEqual(before,path.read_bytes())
 def test_merged_identity_survives_input_reordering(self):
  job=self.job();job['manifest']=[dict(name='One',slug='L0_',collection_path='A/Merge.merge'),dict(name='Two',slug='L1_',collection_path='B/Merge.merge')]
  _,before=self.export(job);job['manifest'].reverse();_,after=self.export(job)
  identity=lambda d:{n['meta']['handoff']['sourceIdentity']:n['id'] for n in nodes(d['layers'])}
  self.assertEqual(identity(before),identity(after))
 def test_reference_flag_blank_frames_and_outside_positions(self):
  job=self.job();job['manifest'][0]['name']='Reference.ref';path,doc=self.export(job)
  ref=next(n for n in nodes(doc['layers']) if n.get('reference'))
  self.assertFalse(ref['visible']);self.assertTrue(ref['reference'])
  ref['frames'][0]['position']=[-200.5,500];validate(doc,path.parent)
  ref['frames'][0].update(name='_blank',fileName='',width=0,height=0,position=[0,0]);validate(doc,path.parent)


if __name__=='__main__':unittest.main()
