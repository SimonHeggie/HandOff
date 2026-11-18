"""Actual SVG assets: only proven, deliberately linked data becomes OCA clones."""
import json,math,tempfile,unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from oca_references import link_vector_clones
from oca_render import expanded

class References(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
 def asset(self,name,x=0,family='shared',rotation=0,gradient=False):
  cs,sn=math.cos(rotation),math.sin(rotation)
  basis=[cs,sn,-sn,cs,x,0]
  coords=[(x,0),(x+4*cs,4*sn),(x+4*cs-4*sn,4*sn+4*cs)]
  d='M '+str(coords[0][0])+' '+str(coords[0][1])+' L '+str(coords[1][0])+' '+str(coords[1][1])+' L '+str(coords[2][0])+' '+str(coords[2][1])+' Z'
  defs=f'<defs><linearGradient id="grad-{name}" gradientTransform="matrix(1 0 0 1 {x} 0)"><stop offset="0" stop-color="red"/><stop offset="1" stop-color="blue"/></linearGradient></defs>' if gradient else ''
  paint=f'url(#grad-{name})' if gradient else 'red'
  xml=f'<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="{x} 0 8 8">{defs}<g id="{name}" data-layered-instance-key="{family}" data-layered-instance-config="paint" data-layered-instance-basis=\'{json.dumps(basis)}\'><path d="{d}" fill="{paint}"/></g></svg>'
  (self.root/(name+'.svg')).write_text(xml)
  return dict(name=name,id=name,type='vectorlayer',width=32,height=32,position=[16,16],childLayers=[],meta=dict(handoff=dict(sourceIdentity=name)),frames=[dict(name=name,fileName=name+'.svg',frameNumber=0,duration=1,opacity=1,position=[x+4,4],width=8,height=8)])
 def test_linked_gradient_translation_is_retained(self):
  a=self.asset('a',gradient=True);b=self.asset('b',x=8,gradient=True);doc=dict(layers=[b,a])
  self.assertEqual(link_vector_clones(doc,self.root),1);self.assertEqual(b['type'],'clonelayer');self.assertEqual(b['source']['id'],'a');self.assertEqual(b['position'],[24,16])
 def test_identical_independent_drawings_do_not_become_clones(self):
  a=self.asset('a',family='data-A');b=self.asset('b',x=8,family='data-B')
  self.assertEqual(link_vector_clones(dict(layers=[a,b]),self.root),0)
 def test_unsupported_rotation_remains_independent(self):
  a=self.asset('a');b=self.asset('b',x=8,rotation=.1)
  self.assertEqual(link_vector_clones(dict(layers=[a,b]),self.root),0)
 def test_crop_disagreement_remains_independent(self):
  a=self.asset('a');b=self.asset('b',x=8)
  tree=ET.parse(self.root/'b.svg');tree.getroot().set('viewBox','7 0 8 8');tree.write(self.root/'b.svg')
  self.assertEqual(link_vector_clones(dict(layers=[a,b]),self.root),0)
 def test_clone_chain_and_time_offsets_expand(self):
  a=self.asset('a');a['type']='paintlayer';a['fileType']='png';a['frames'][0]['fileName']='a.png'
  b=dict(name='b',id='b',type='clonelayer',position=[24,16],source=dict(id='a',timeOffset=1))
  c=dict(name='c',id='c',type='clonelayer',position=[8,16],source=dict(id='b',timeOffset=1))
  document=dict(name='Test',width=32,height=32,startTime=0,endTime=4,colorDepth='U8',layers=[c,b,a])
  view=expanded(document,self.root);self.assertEqual(view['layers'][0]['frames'][0]['frameNumber'],2)
  self.assertEqual(view['layers'][0]['frames'][0]['position'],[-4,4])

if __name__=='__main__':unittest.main()
