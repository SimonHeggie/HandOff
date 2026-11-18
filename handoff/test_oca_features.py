"""Real OCA files: explicit authoring, reference publication and composition."""
import copy,json,shutil,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
from psd_worker import assemble
from oca_project import nodes
from oca_validation import validate
from oca_companions import composite

class Features(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.cache=self.root/'cache';self.cache.mkdir()
  Image.new('RGBA',(9,7),'red').save(self.cache/'A_0001.png');Image.new('RGBA',(9,7),'green').save(self.cache/'B_0001.png')
 def job(self,name='Art'):
  return dict(format='OCA',dest=str(self.root/(name+'.oca')),oca_layout='PROJECT',dir=str(self.cache),extension='.png',depth=8,frame=1,cache_frame=1,frame_rate=24,canvas_size=[9,7],hierarchy='GROUPS',overwrite=True,
   oca_options=dict(writeJson=False,writeTemplate=False,padding=0),manifest=[dict(name='Green',slug='B_',oca_source_id='B',source_view_layer='Green',collection_path='Group'),dict(name='Red',slug='A_',oca_source_id='A',source_view_layer='Red',collection_path='Group')])
 def export(self,job):
  path=Path(assemble(job));return path,json.loads(path.read_text())
 def test_opacity_inherit_alpha_isolation_and_background(self):
  job=self.job();Image.new('RGBA',(9,7),(0,255,0,255)).save(self.cache/'B_0001.png')
  job['manifest'][1]['oca_authored']=dict(opacity=.4)
  job['manifest'][0]['oca_authored']=dict(frameOpacity=.5,inheritAlpha=True)
  for entry in job['manifest']:entry['oca_authored_groups']={'Group':dict(opacity=.5)}
  job['oca_background_color']=[0,0,1,.2];job['oca_options']['writeTemplate']=True
  path,doc=self.export(job);group=doc['layers'][0];self.assertFalse(group['passThrough']);self.assertEqual(group['opacity'],.5)
  # Child red alpha=.4, clipped green alpha=.5*.4=.2 -> alpha=.52;
  # isolated group opacity .5 -> .26; blue background .2 -> total .408.
  actual=composite(doc,path.parent,1)[3,4]
  np.testing.assert_allclose(actual,[.16/.408,.1/.408,.148/.408,.408],atol=1e-6)
  template=Image.open(path.parent/'_companions/Art.template.png');self.assertEqual(template.size,(9,7))
 def test_explicit_clone_uses_source_identity_and_pixels(self):
  job=self.job();job['manifest'][0]['oca_authored']=dict(sourceLayer='Red',timeOffset=0)
  job['oca_options'].update(writeTemplate=True,writeJson=True)
  path,doc=self.export(job);items=list(nodes(doc['layers']));clone=next(n for n in items if n['type']=='clonelayer');source=next(n for n in items if n['id']==clone['source']['id'])
  self.assertEqual(source['meta']['handoff']['sourceViewLayer'],'Red');validate(doc,path.parent)
  np.testing.assert_allclose(composite(doc,path.parent,1)[3,4],[1,0,0,1])
  self.assertTrue((path.parent/'_companions/Art.spine.json').is_file())
 def test_nested_graph_is_portable_and_scales(self):
  child_path,child=self.export(self.job('Child'))
  for scale in (50,100,200):
   job=self.job('Parent'+str(scale));job['manifest']=job['manifest'][:1]
   job['manifest'][0]['oca_authored']=dict(external=str(child_path),timeOffset=0)
   job['oca_options']['scale']=scale;path,doc=self.export(job)
   nested=next(n for n in nodes(doc['layers']) if n['type']=='ocalayer');copied=path.parent/nested['source']['relFileName']
   self.assertTrue(copied.is_file());actual=json.loads(copied.read_text())
   self.assertEqual(actual['width'],max(1,int(9*scale/100+.5)));validate(doc,path.parent)
   from oca_render import expanded
   view=expanded(actual,copied.parent)
   centres=[cel['position'] for n in nodes(view['layers']) for cel in n['frames'] if cel['fileName']]
   np.testing.assert_allclose(centres[0],[4.5*scale/100,3.5*scale/100])
   self.assertTrue(any(Image.open(copied.parent/cel['fileName']).size==(actual['width'],actual['height']) for n in nodes(actual['layers']) for cel in n['frames'] if cel['fileName']))
  moved=self.root/'Moved.oca';shutil.move(path.parent,moved);shutil.rmtree(child_path.parent)
  validate(doc,moved,document_path=moved/path.name)
 def test_missing_or_cyclic_explicit_sources_leave_old_output(self):
  job=self.job();path,_=self.export(job);before=path.read_bytes()
  job['manifest'][0]['oca_authored']=dict(sourceLayer='Missing')
  with self.assertRaisesRegex(ValueError,'exactly one'):self.export(job)
  self.assertEqual(before,path.read_bytes())
  job['manifest'][0]['oca_authored']=dict(sourceLayer='Red');job['manifest'][1]['oca_authored']=dict(sourceLayer='Green')
  with self.assertRaisesRegex(ValueError,'cyclic|Cyclic'):self.export(job)
  self.assertEqual(before,path.read_bytes())
 def test_unknown_template_blend_preserves_valid_oca_and_reports_omission(self):
  job=self.job();job['manifest'][0]['oca_authored']=dict(blend='burn');job['oca_options']['writeTemplate']=True
  path,doc=self.export(job);validate(doc,path.parent)
  self.assertFalse((path.parent/'_companions/Art.template.png').exists())
  self.assertTrue(any('template omitted' in note for note in job['_notices']))
 def test_explicit_blend_replaces_automatic_group_promotion(self):
  job=self.job();job['manifest'][0]['name']='Green.add';job['manifest'][1]['name']='Red.add'
  job['manifest'][0]['oca_authored']=dict(blend='multiply')
  path,doc=self.export(job);group=doc['layers'][0]
  self.assertTrue(group['passThrough']);self.assertEqual(group['blendingMode'],'normal')
  modes={n['meta']['handoff']['sourceName']:n['blendingMode'] for n in nodes(doc['layers']) if n['frames']}
  self.assertEqual(modes,{'Green.add':'multiply','Red.add':'add'})
 def test_frame_opacity_uses_each_captured_frame(self):
  job=self.job();captures=[]
  for frame,opacity in ((1,.25),(2,.75)):
   for slug in ('A','B'):shutil.copy2(self.cache/(slug+'_0001.png'),self.cache/(slug+'_0002.png'))
   captured=copy.deepcopy(job);captured.update(frame=frame,cache_frame=frame)
   for entry in captured['manifest']:entry['oca_authored']=dict(frameOpacity=opacity)
   captures.append(captured)
  job.update(oca_frames=captures,oca_range=[1,2,1]);path,doc=self.export(job)
  for n in nodes(doc['layers']):
   if n['frames']:self.assertEqual([f['opacity'] for f in n['frames']],[.25,.75])

if __name__=='__main__':unittest.main()
