"""OCA publication regression tests, supplemented by native render fixtures."""
import json,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
from psd_worker import assemble
from oca_controls import options
from oca_images import png16,load,process

class OCAControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def job(self,settings,entries=None):
        pixels=np.empty((12,16,4),np.uint8);pixels[:]=[93,71,11,0];pixels[2:8,4:12]=[20,100,180,255]
        Image.fromarray(pixels,'RGBA').save(self.root/'L0_0001.png')
        return dict(format='OCA',dest=str(self.root/'Parts.oca'),dir=str(self.root),extension='.png',depth=8,
                    cache_frame=1,frame=1,canvas_size=[16,12],hierarchy='GROUPS',overwrite=True,
                    oca_options=dict(writeJson=False,writeTemplate=False,**settings),
                    manifest=entries or [dict(name='Paint',slug='L0_',collection_path='Art',collection_colors=['BLUE'])])
    def leaf(self,doc):return next(self.leaves(doc['layers']))
    def leaves(self,nodes):
        for n in nodes:
            if n['type']=='grouplayer':yield from self.leaves(n['childLayers'])
            else:yield n
    def test_scale_padding_and_alpha_trim_dimensions_centres(self):
        for scale in (50,100,200):
            for padding in (0,1,4):
                for trim in (False,True):
                    job=self.job(dict(scale=scale,padding=padding,trimWhitespace=trim));assemble(job)
                    doc=json.loads(Path(job['dest']).read_text());layer=self.leaf(doc);cel=layer['frames'][0]
                    expected=((8 if trim else 16)*scale//100+2*padding,(6 if trim else 12)*scale//100+2*padding)
                    self.assertEqual(Image.open(self.root/cel['fileName']).size,expected)
                    self.assertEqual((cel['width'],cel['height']),expected)
                    self.assertEqual(cel['position'],[8*scale/100,(5 if trim else 6)*scale/100])
                    self.assertEqual((doc['width'],doc['height']),(16*scale//100,12*scale//100))
    def test_trim_reconstructs_identical_visible_artwork(self):
        from oca_companions import composite
        images=[]
        for trim in (False,True):
            job=self.job(dict(trimWhitespace=trim,padding=4));assemble(job)
            doc=json.loads(Path(job['dest']).read_text());images.append(composite(doc,self.root/'Parts',1))
        np.testing.assert_array_equal(images[0],images[1])
    def test_hidden_groups_keep_pixels_but_never_template_visibility(self):
        entries=[dict(name='Hidden',slug='L0_',collection_path='Art',oca_group_visibility={'Art':False})]
        job=self.job(dict(ignoreHiddenLayers=False),entries);job['oca_options']['writeTemplate']=True;assemble(job)
        doc=json.loads(Path(job['dest']).read_text());self.assertFalse(doc['layers'][0]['visible'])
        cel=self.leaf(doc)['frames'][0];self.assertIsNotNone(Image.open(self.root/cel['fileName']).getchannel('A').getbbox())
        self.assertIsNone(Image.open(self.root/'Parts/_companions/Parts.template.png').getchannel('A').getbbox())
        job['oca_options']['ignoreHiddenLayers']=True;assemble(job)
        self.assertEqual(json.loads(Path(job['dest']).read_text())['layers'],[])
    def test_background_is_explicit_not_combined_name_or_bottom_position(self):
        entries=[dict(name='Combined',slug='L0_'),dict(name='Background',slug='L0_'),dict(name='Arbitrary',slug='L0_',oca_background=True)]
        job=self.job(dict(ignoreBackground=True),entries);assemble(job)
        self.assertEqual([n['name'] for n in self.leaves(json.loads(Path(job['dest']).read_text())['layers'])],['Background','Combined'])
        job['oca_options']['ignoreBackground']=False;assemble(job)
        self.assertEqual(len(list(self.leaves(json.loads(Path(job['dest']).read_text())['layers']))),3)
    def test_blank_frame_has_native_oca_semantics(self):
        job=self.job(dict(trimWhitespace=True));Image.new('RGBA',(16,12),(99,88,77,0)).save(self.root/'L0_0001.png');assemble(job)
        cel=self.leaf(json.loads(Path(job['dest']).read_text()))['frames'][0]
        self.assertEqual((cel['name'],cel['fileName'],cel['width'],cel['height']),('_blank','',0,0))
    def test_reference_directives_are_hidden_and_can_be_excluded(self):
        entries=[dict(name='Paint.ref',slug='L0_',collection_path='Reference'),
                 dict(name='Guide',slug='L0_',collection_path='Guides.ref')]
        job=self.job(dict(ignoreHiddenLayers=False),entries);assemble(job)
        from oca_companions import leaves
        self.assertTrue(all(not shown for _,shown in leaves(json.loads(Path(job['dest']).read_text())['layers'])))
        job['oca_options']['ignoreHiddenLayers']=True;assemble(job)
        self.assertEqual(json.loads(Path(job['dest']).read_text())['layers'],[])
    def test_png16_crop_padding_preserves_exact_samples(self):
        values=np.empty((12,16,4),np.float32);values[:]=[.4,.3,.2,0];values[2:8,4:12]=[12345/65535,23456/65535,34567/65535,1/65535]
        src=self.root/'in.png';src.write_bytes(png16(values));decoded=load(src,16)
        arr,centre=process(decoded,options(dict(oca_options=dict(padding=4))))
        target=self.root/'out.png';target.write_bytes(png16(arr,src));read=load(target,16)
        np.testing.assert_array_equal(read[4:10,4:12],decoded[2:8,4:12]);self.assertEqual(centre,(8,5))
    def test_png_colour_metadata_survives_processing(self):
        from PIL.PngImagePlugin import PngInfo
        from oca_images import save,colour_chunks
        import struct
        source=self.root/'profile.png';info=PngInfo()
        info.add(b'gAMA',struct.pack('>I',45455));info.add(b'sRGB',b'\0')
        Image.new('RGBA',(3,3),(20,40,60,255)).save(source,pnginfo=info)
        pixels=load(source,8)
        for depth in (8,16):
            target=self.root/('out'+str(depth)+'.png');save(target,pixels,depth,source)
            self.assertEqual(dict(colour_chunks(target)),dict(colour_chunks(source)))
    def test_json_uses_same_assets_positions_and_draw_order(self):
        job=self.job(dict(padding=1));job['oca_options']['writeJson']=True;assemble(job)
        doc=json.loads(Path(job['dest']).read_text());comp=json.loads((self.root/'Parts/_companions/Parts.spine.json').read_text())
        self.assertEqual(comp['bones'],[dict(name='root')]);self.assertEqual(comp['slots'][0]['name'],'Paint')
        region=next(iter(comp['skins'][0]['attachments']['Paint'].values()));cel=self.leaf(doc)['frames'][0]
        self.assertEqual((region['x'],region['y']),(cel['position'][0]-doc['width']/2,doc['height']/2-cel['position'][1]))
        self.assertTrue((self.root/'Parts'/ (region['path']+'.png')).is_file())
    def test_reported_large_alpha_bounds_are_physically_cropped(self):
        pixels=np.empty((2048,1536,4),np.uint8);pixels[:]=[80,90,100,0];pixels[497:1193,73:1237]=[20,40,60,255]
        job=self.job(dict(padding=0,trimWhitespace=True));Image.fromarray(pixels,'RGBA').save(self.root/'L0_0001.png');assemble(job)
        cel=self.leaf(json.loads(Path(job['dest']).read_text()))['frames'][0]
        self.assertEqual(Image.open(self.root/cel['fileName']).size,(1164,696))
        self.assertEqual(cel['position'],[655,845])
    def test_invalid_values_fail_before_overwriting(self):
        for change in (dict(scale=0),dict(scale=401),dict(padding=-1)):
            with self.assertRaises(ValueError):options(dict(oca_options=change))
    def test_fractional_scaling_keeps_exact_source_centre(self):
        image=np.zeros((9,13,4),np.float32);image[1:6,3:10]=1
        result,centre=process(image,options(dict(oca_options=dict(scale=33.3,padding=1))))
        self.assertEqual(result.shape,(4,4,4));np.testing.assert_allclose(centre,(6.5*.333,3.5*.333))

if __name__=='__main__':unittest.main()
