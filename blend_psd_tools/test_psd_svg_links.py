import io,json,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
from PIL import Image
from psd_tools import PSDImage
from psd_tools.constants import Tag
from psd_svg_links import svg_sidecar,preview,create_link_prototype
from test_svg_instances import artwork

class LinkedSvgRecords(unittest.TestCase):
    def test_explicit_raster_and_flatten_options_do_not_create_links(self):
        from psd_worker import assemble_psd
        from svg_export import encode_svg
        for option in ('bake_svg_png','flatten'):
            with self.subTest(option=option),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);source=root/'source.svg';obj=artwork(gradient=True)
                source.write_text(encode_svg(64,64,[obj]))
                source.with_suffix('.vectors.json').write_text(json.dumps(dict(width=64,height=64,objects=[obj])))
                png=root/'cached.png';Image.new('RGBA',(64,64),(20,40,60,128)).save(png)
                job=dict(dest=str(root/'art.psd'),format='PSD',depth=8,extension='.png',hierarchy='FLAT',overwrite=True)
                job[option]=True
                assemble_psd(job,[(dict(name='Sprites',vector_svg=str(source)),png)])
                doc=PSDImage.open(job['dest']);self.assertEqual(doc[0].kind,'pixel')
                self.assertFalse(doc.tagged_blocks.get_data(Tag.LINKED_LAYER_EXTERNAL))

    def test_automatic_links_ignore_legacy_editor_and_toggle_and_keep_cached_preview(self):
        from psd_worker import assemble_psd
        from svg_export import encode_svg
        for target in ('PHOTOSHOP','PHOTOCRAFT'):
            for depth in (8,16):
                with self.subTest(target=target,depth=depth),tempfile.TemporaryDirectory() as folder:
                    root=Path(folder);obj=artwork(gradient=True);source=root/'source.svg'
                    source.write_text(encode_svg(64,64,[obj]))
                    source.with_suffix('.vectors.json').write_text(json.dumps(dict(width=64,height=64,objects=[obj])))
                    png=root/'cached.png'
                    if depth==8:Image.new('RGBA',(64,64),(24,96,160,255)).save(png)
                    else:
                        from test_color_management import filtered_png16
                        data=np.empty((64,64,4),np.uint16);data[:]=[1234,23456,54321,65535]
                        filtered_png16(png,data,0)
                    job=dict(dest=str(root/'art.psd'),format='PSD',depth=depth,extension='.png',hierarchy='FLAT',
                        overwrite=True,psd_link_svg_fallbacks=False,psd_target=target)
                    assemble_psd(job,[(dict(name='Sprites',vector_svg=str(source)),png)])
                    doc=PSDImage.open(job['dest']);self.assertEqual(doc[0].kind,'smartobject')
                    if depth==8:self.assertEqual(doc[0].topil().getpixel((0,0)),(24,96,160,255))
                    else:np.testing.assert_array_equal(np.rint(doc[0].numpy()[0,0]*65535).astype(np.uint16),data[0,0])
                    self.assertEqual(job['_publication'][0]['target'],'PSD')
                    source_link=doc.tagged_blocks.get_data(Tag.LINKED_LAYER_EXTERNAL)[0]
                    self.assertTrue((root/source_link.linked_file[b'relPath'].value).is_file())

    def test_link_write_failure_keeps_visible_pixels_and_preserved_source(self):
        from psd_worker import assemble_psd
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);obj=artwork(gradient=True);source=root/'source.svg';source.write_text('<svg/>')
            source.with_suffix('.vectors.json').write_text(json.dumps(dict(width=64,height=64,objects=[obj])))
            png=root/'empty.png';Image.new('RGBA',(64,64)).save(png)
            job=dict(dest=str(root/'art.psd'),format='PSD',depth=8,extension='.png',hierarchy='FLAT',overwrite=True)
            with patch('psd_svg_links.attach_svg_link',side_effect=ValueError('fixture link write error')):
                assemble_psd(job,[(dict(name='Sprites',vector_svg=str(source)),png)])
            doc=PSDImage.open(job['dest']);pixels=[n for n in doc.descendants() if n.kind=='pixel']
            self.assertTrue(pixels);self.assertGreater(float(pixels[0].numpy()[...,3].max()),0)
            self.assertFalse(doc.tagged_blocks.get_data(Tag.LINKED_LAYER_EXTERNAL))
            self.assertTrue(any('link write error' in n for n in job['_notices']))
            self.assertTrue(Path(job['_publication'][0]['source_svg']).is_file())

    def test_shared_source_cannot_silently_point_to_a_different_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);dest=root/'art.psd'
            first=root/'first.svg';first.write_text('<svg><rect width="4" height="4"/></svg>')
            second=root/'second.svg';second.write_text('<svg><rect width="4" height="4"/></svg>')
            doc=PSDImage.new('RGB',(4,4));pixels=np.ones((4,4,4),np.float32)
            create_link_prototype(doc,pixels,first,dest,(4,4),source_id='shared')
            with self.assertRaisesRegex(ValueError,'different SVG files'):
                create_link_prototype(doc,pixels,second,dest,(4,4),source_id='shared')
            self.assertEqual(len(doc),1)

    def test_external_source_survives_save_move_and_shared_edit_at_every_depth(self):
        for depth in (8,16,32):
            with self.subTest(depth=depth),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);dest=root/'before'/'art.psd';dest.parent.mkdir()
                obj=artwork(gradient=True)
                for layer in obj['layers']:
                    for s in layer['strokes']:
                        for stop in s['fill_gradient']['stops']:stop['linear']=[.2,.4,.6]
                sidecar=svg_sidecar(dict(dest=str(dest)),'Sprites',[obj],(64,64))
                pixels=preview([obj],(64,64),depth);self.assertGreater(float(pixels[...,3].max()),0)
                doc=PSDImage.new('RGB',(64,64),depth=depth)
                first=create_link_prototype(doc,pixels,sidecar,dest,(64,64),source_id='cfa34314-c151-4be1-8c53-a6cd5c904f34')
                second=create_link_prototype(doc,pixels,sidecar,dest,(64,64),source_id='cfa34314-c151-4be1-8c53-a6cd5c904f34',
                    transform=[4,0,68,0,68,64,4,64])
                doc.save(dest);loaded=PSDImage.open(dest)
                self.assertEqual([l.kind for l in loaded],['smartobject','smartobject'])
                self.assertEqual(loaded[0].smart_object.kind,'external')
                self.assertEqual(loaded[0].smart_object.unique_id,loaded[1].smart_object.unique_id)
                self.assertEqual(len(loaded.tagged_blocks.get_data(Tag.LINKED_LAYER_EXTERNAL)),1)
                self.assertNotEqual(loaded[0].tagged_blocks.get_data(Tag.SMART_OBJECT_LAYER_DATA2).data[b'placed'].value,
                    loaded[1].tagged_blocks.get_data(Tag.SMART_OBJECT_LAYER_DATA2).data[b'placed'].value)
                moved=root/'after';dest.parent.rename(moved);reopened=PSDImage.open(moved/'art.psd')
                source=moved/sidecar.relative_to(dest.parent)
                source.write_text(source.read_text().replace('Source gradient','Edited gradient')+'\n<!-- edited shared SVG -->')
                for layer in reopened:
                    with layer.smart_object.open(external_dir=moved) as f:self.assertIn(b'edited shared SVG',f.read())
                reopened.save(moved/'again.psd')
                final=PSDImage.open(moved/'again.psd');self.assertEqual(final.depth,depth)
                self.assertEqual(final[1].tagged_blocks.get_data(Tag.SMART_OBJECT_LAYER_DATA2).data[b'Trnf'][0].value,4)

    def test_partial_gradient_fallback_keeps_native_neighbour_and_source(self):
        from psd_worker import assemble_psd
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.svg';source.write_text('<svg/>')
            obj=artwork(gradient=True);solid=artwork('Native',(1,0,0,1,50,0),'separate')
            source.with_suffix('.vectors.json').write_text(json.dumps(dict(width=160,height=100,objects=[obj,solid])))
            png=root/'empty.png';Image.new('RGBA',(160,100)).save(png)
            job=dict(dest=str(root/'art.psd'),format='PSD',depth=8,extension='.png',hierarchy='FLAT',overwrite=True,
                psd_link_svg_fallbacks=False,psd_target='PHOTOCRAFT')
            assemble_psd(job,[(dict(name='Sprites',vector_svg=str(source)),png)])
            doc=PSDImage.open(job['dest']);kinds=[n.kind for n in doc.descendants()]
            self.assertIn('shape',kinds);self.assertIn('smartobject',kinds);self.assertNotIn('pixel',kinds)
            self.assertTrue(any(n.get('representation')=='LINKED_SMART_OBJECT' for n in job['_publication']))
            self.assertTrue(any('automatically' in note for note in job['_notices']))
            self.assertTrue(list((root/'art.assets').glob('*.svg')))
