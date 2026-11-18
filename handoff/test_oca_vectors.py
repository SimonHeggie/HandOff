import json,tempfile,unittest
from pathlib import Path
from PIL import Image
from psd_worker import assemble


class OCAVectors(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  pixels=Image.new('RGBA',(16,12));pixels.paste((30,180,50,255),(4,2,12,8));pixels.save(self.root/'L_0001.png')
  self.svg=self.root/'source.svg';self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 12"><path fill="green" d="M4 2H12V8H4Z"/></svg>')
 def job(self):
  return dict(format='OCA',dest=str(self.root/'Art.oca'),dir=str(self.root),depth=8,extension='.png',
              frame=1,cache_frame=1,canvas_size=[16,12],hierarchy='GROUPS',overwrite=True,
              oca_options=dict(writeJson=False,writeTemplate=False,padding=1),
              manifest=[dict(name='Paint',slug='L_',collection_path='Art',collection_colors=['BLUE'],vector_svg=str(self.svg))])
 def leaf(self,doc):
  from oca_companions import leaves
  return list(leaves(doc['layers']))[0][0]
 def test_svg_and_rendered_png_are_one_visible_layer(self):
  job=self.job();job['oca_keep_png']=True;assemble(job);doc=json.loads(Path(job['dest']).read_text());layer=self.leaf(doc)
  self.assertEqual((layer['type'],layer['fileType'],layer['label']),('vectorlayer','svg',5))
  cel=layer['frames'][0];self.assertEqual((cel['width'],cel['height'],cel['position']),(10,8,[8,5]))
  self.assertEqual(Path(cel['fileName']).name,'Paint_00001.svg')
  self.assertTrue((self.root/cel['fileName']).is_file())
  alt=cel['meta']['handoff']['raster'];self.assertEqual(Image.open(self.root/alt['fileName']).size,(10,8))
  self.assertEqual(alt['position'],cel['position'])
 def test_vector_only_leaves_no_raster_asset(self):
  job=self.job();assemble(job)
  self.assertEqual(list((self.root/'Art').rglob('*.png')),[])
 def test_rasterise_retains_svg_source(self):
  job=self.job();job['bake_svg_png']=True;job['oca_keep_png']=True;assemble(job);layer=self.leaf(json.loads(Path(job['dest']).read_text()))
  self.assertEqual(layer['type'],'paintlayer');cel=layer['frames'][0]
  self.assertTrue((self.root/cel['fileName']).is_file())
  self.assertTrue((self.root/cel['meta']['handoff']['editableSource']['fileName']).is_file())
 def test_companions_use_native_pixels_for_svg(self):
  job=self.job();job['oca_options'].update(writeJson=True,writeTemplate=True);assemble(job)
  companion=json.loads((self.root/'Art/_companions/Art.spine.json').read_text())
  region=next(iter(companion['skins'][0]['attachments']['Paint'].values()))
  self.assertTrue(region['path'].startswith('_companions/images/'))
  self.assertFalse((self.root/'Art/_raster').exists())
  cel=self.leaf(json.loads(Path(job['dest']).read_text()))['frames'][0]
  self.assertNotIn('raster',cel['meta']['handoff'])
  self.assertTrue((self.root/'Art'/region['path']).with_suffix('.png').is_file())
  self.assertIsNotNone(Image.open(self.root/'Art/_companions/Art.template.png').getchannel('A').getbbox())
 def test_raster_mode_without_alternative_delivers_only_png(self):
  job=self.job();job['bake_svg_png']=True;assemble(job)
  doc=json.loads(Path(job['dest']).read_text());cel=self.leaf(doc)['frames'][0]
  self.assertEqual(self.leaf(doc)['type'],'paintlayer')
  self.assertEqual(list((self.root/'Art').rglob('*.svg')),[])
  self.assertNotIn('editableSource',cel['meta'].get('handoff',{}))
  self.assertFalse((self.root/'Art/_vectors').exists())
 def test_template_only_uses_private_preview_without_publishing_duplicate(self):
  job=self.job();job['oca_options']['writeTemplate']=True;assemble(job)
  doc=json.loads(Path(job['dest']).read_text());cel=self.leaf(doc)['frames'][0]
  self.assertNotIn('raster',cel['meta']['handoff'])
  self.assertEqual([p.name for p in (self.root/'Art').rglob('*.png')],['Art.template.png'])
  self.assertFalse((self.root/'Art/_raster').exists())
 def test_ordinary_raster_selection_is_not_a_warning(self):
  job=self.job();job['manifest'][0].pop('vector_svg');job['manifest'][0]['vector_reason']='Compositor processing requires rendered PNG'
  assemble(job)
  self.assertFalse(any('raster fallback' in n or 'Compositor processing' in n for n in job.get('_notices',[])))
 def test_clean_defaults_have_no_unrequested_companions(self):
  from oca_controls import options
  self.assertFalse(options({})['writeJson'])
  job=self.job();job.pop('oca_options');assemble(job)
  self.assertFalse((self.root/'Art/_companions').exists())
  self.assertFalse((self.root/'Art/_raster').exists())
  self.assertEqual(len(list((self.root/'Art').rglob('*.svg'))),1)
 def test_names_collide_safely_without_order_numbers(self):
  job=self.job();entry=job['manifest'][0];entry.pop('vector_svg')
  job['manifest']=[dict(entry,name='Eyes.add'),dict(entry,name='Eyes.multiply')]
  assemble(job);from oca_companions import leaves
  names=[Path(n['frames'][0]['fileName']).name for n,_ in leaves(json.loads(Path(job['dest']).read_text())['layers'])]
  self.assertEqual(names,['Eyes_00001.png','Eyes-2_00001.png'])
 def test_unsupported_svg_uses_cached_raster(self):
  self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 12"><image href="unsupported.png"/></svg>')
  job=self.job();assemble(job);self.assertEqual(self.leaf(json.loads(Path(job['dest']).read_text()))['type'],'paintlayer')
 def test_empty_raster_does_not_masquerade_as_valid_vector_fallback(self):
  Image.new('RGBA',(16,12)).save(self.root/'L_0001.png')
  with self.assertRaisesRegex(ValueError,'empty Blender raster cache'):assemble(self.job())


if __name__=='__main__':unittest.main()
