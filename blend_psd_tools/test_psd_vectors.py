"""Native PSD records, independently reopened and edited after serialization."""
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).parent/'vendor'))
from pillow_loader import ensure_pillow
ensure_pillow()
import numpy as np
from psd_tools import PSDImage
from psd_tools.constants import Tag,Resource,BlendMode
from psd_tools.psd.descriptor import Double
from psd_vectors import shape_layer,text_layer,append_artwork


def rectangle(x,y,w,h):
    return dict(type='POLY',cyclic=True,points=[dict(co=p) for p in
                ((x,y),(x+w,y),(x+w,y+h),(x,y+h))])


def reopen(document):
    stream=io.BytesIO();document.save(stream);stream.seek(0)
    return PSDImage.open(stream)


class PhotoshopVectorTests(unittest.TestCase):
    def test_missing_fallback_pixels_omit_only_failed_source_and_report_partial(self):
        import json,tempfile
        from PIL import Image
        from psd_worker import assemble_psd
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);svg=root/'unsupported.svg'
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>Missing font</text></svg>')
            svg.with_suffix('.vectors.json').write_text(json.dumps(dict(width=16,height=16,
                objects=[dict(name='Missing',svg_kind='FONT',body='Missing',font_file='')])) )
            empty=root/'empty.png';good=root/'good.png'
            Image.new('RGBA',(16,16)).save(empty);Image.new('RGBA',(16,16),'red').save(good)
            job=dict(dest=str(root/'partial.psd'),format='PSD',depth=8,extension='.png',hierarchy='FLAT',overwrite=True)
            assemble_psd(job,[(dict(name='Missing',vector_svg=str(svg)),empty),(dict(name='Good'),good)])
            doc=PSDImage.open(job['dest']);self.assertEqual([layer.name for layer in doc],['Good'])
            self.assertTrue(job['_partial'])
            self.assertTrue(any(row['representation']=='FAILED' for row in job['_publication']))
            self.assertTrue(list((root/'partial.assets').glob('*.svg')))

    def test_psd_xmp_binds_native_layers_to_source_uuid(self):
        import json,tempfile
        from psd_worker import assemble_psd
        from PIL import Image
        from test_svg_instances import artwork
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.svg';source.write_text('<svg/>')
            obj=artwork();obj['source_metadata']=dict(object_id='stable-object',data_id='stable-data',object_name='Original')
            source.with_suffix('.vectors.json').write_text(json.dumps(dict(width=160,height=100,objects=[obj])))
            png=root/'pixels.png';Image.new('RGBA',(160,100)).save(png)
            job=dict(dest=str(root/'native.psd'),format='PSD',depth=8,extension='.png',hierarchy='FLAT',overwrite=True)
            assemble_psd(job,[(dict(name='Artwork',vector_svg=str(source)),png)])
            doc=PSDImage.open(job['dest']);xmp=doc.image_resources.get_data(Resource.XMP_METADATA)
            self.assertIn(b'stable-object',xmp);self.assertIn(b'stable-data',xmp)
            native=[layer for layer in doc.descendants() if layer.kind=='shape'];self.assertEqual(len(native),1)
            self.assertGreater(native[0].layer_id,0);self.assertIn(str(native[0].layer_id).encode(),xmp)
    def test_empty_gradient_fallback_rebuilds_visible_preview_and_preserves_svg(self):
        import json,tempfile
        from PIL import Image
        from svg_export import encode_svg
        from psd_worker import assemble_psd
        from test_svg_instances import artwork
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=folder/'gradient.svg'
            objects=[artwork(gradient=True),artwork('Clone',(1,0,0,1,60,0),gradient=True)]
            svg=encode_svg(160,100,objects);source.write_text(svg)
            source.with_suffix('.vectors.json').write_text(json.dumps(dict(width=160,height=100,objects=objects)))
            png=folder/'empty.png';Image.new('RGBA',(160,100)).save(png)
            job=dict(dest=str(folder/'art.psd'),format='PSD',depth=8,extension='.png',hierarchy='FLAT',overwrite=True)
            assemble_psd(job,[(dict(name='Shine',vector_svg=str(source)),png)])
            self.assertTrue(any('SVG linked automatically' in note for note in job['_notices']))
            self.assertEqual(source.read_text(),svg)
            doc=PSDImage.open(job['dest']);self.assertEqual(sum(layer.kind=='smartobject' for layer in doc.descendants()),1)
            self.assertFalse(any(layer.kind=='pixel' for layer in doc.descendants()))
            links=doc.tagged_blocks.get_data(Tag.LINKED_LAYER_EXTERNAL)
            self.assertEqual(len(links),1)
            delivered=folder/links[0].linked_file[b'relPath'].value
            from xml.etree import ElementTree as ET
            self.assertEqual(len(list(ET.parse(delivered).getroot().iter('{http://www.w3.org/2000/svg}use'))),1)
            self.assertGreater(np.asarray(doc.composite(force=True))[...,3].max(),0)

    def test_svg_clones_do_not_remove_native_psd_shape_instances(self):
        import json,tempfile
        from PIL import Image
        from svg_export import encode_svg
        from psd_worker import assemble_psd
        from test_svg_instances import artwork
        from xml.etree import ElementTree as ET
        objects=[artwork(),artwork('Linked copy',(1,0,0,1,60,0))]
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=folder/'shared.svg'
            source.write_text(encode_svg(160,100,objects))
            self.assertEqual(len(list(ET.parse(source).getroot().iter('{http://www.w3.org/2000/svg}use'))),1)
            source.with_suffix('.vectors.json').write_text(json.dumps(dict(width=160,height=100,objects=objects)))
            png=folder/'pixels.png';Image.new('RGBA',(160,100)).save(png)
            job=dict(dest=str(folder/'art.psd'),format='PSD',depth=8,extension='.png',
                hierarchy='GROUPS',overwrite=True,psd_compression='AUTO')
            assemble_psd(job,[(dict(name='Sprites',vector_svg=str(source)),png)])
            doc=PSDImage.open(job['dest']);shapes=[layer for layer in doc.descendants() if layer.kind=='shape']
            self.assertEqual(len(shapes),2)
            self.assertEqual(sorted(round(layer.vector_mask.paths[0][0].anchor[1]*160) for layer in shapes),[10,70])

    def test_hole_and_bezier_handles_survive_and_fill_edit_rerenders(self):
        doc=PSDImage.new('RGB',(64,64))
        outer=rectangle(4,4,56,56);outer['type']='BEZIER'
        for point in outer['points']:
            point['left']=point['co'];point['right']=point['co']
        outer['points'][0]['right']=(17,2)
        shape_layer(doc,dict(kind='fill',contours=[outer,rectangle(24,24,16,16)],
                    color='#ff0000'), 'Cutout',(64,64),8)
        result=reopen(doc);layer=result[0]
        self.assertEqual(layer.kind,'shape')
        self.assertEqual(len(layer.vector_mask.paths),2)
        knot=layer.vector_mask.paths[0][0]
        self.assertAlmostEqual(knot.leaving[0]*64,2,places=4)
        self.assertAlmostEqual(knot.leaving[1]*64,17,places=4)
        before=np.asarray(result.composite(force=True))
        self.assertEqual(before[30,30,3],0)
        paint=layer.tagged_blocks.get_data(Tag.SOLID_COLOR_SHEET_SETTING)[b'Clr ']
        paint[b'Rd  ']=Double(0);paint[b'Grn ']=Double(255)
        after=np.asarray(result.composite(force=True))
        self.assertGreater(before[12,12,0],200)
        self.assertGreater(after[12,12,1],200)
        self.assertLess(after[12,12,0],10)

    def test_native_stroke_and_alpha_gradient_descriptors_at_every_depth(self):
        for depth in (8,16,32):
            with self.subTest(depth=depth):
                doc=PSDImage.new('RGB',(64,64),depth=depth)
                contour=dict(type='BEZIER',cyclic=False,points=[
                    dict(co=(4,30),left=(4,30),right=(20,4)),
                    dict(co=(60,30),left=(44,56),right=(60,30))])
                pressure=dict(gradient=dict(axis=0,start=4,end=60,stops=[0,.5,1]),opacities=[.2,1,.5])
                shape_layer(doc,dict(kind='stroke',contours=[contour],color='#4070a0',linear=(.1,.2,.3),
                    width=6,opacity=.75,pressure=pressure),'Editable stroke',(64,64),depth)
                result=reopen(doc);layer=result[0]
                self.assertEqual(result.depth,depth)
                self.assertEqual(layer.kind,'shape')
                self.assertIn(Tag.VECTOR_MASK_SETTING2,layer.tagged_blocks)
                style=layer.tagged_blocks.get_data(Tag.VECTOR_STROKE_DATA)
                self.assertEqual(style[b'strokeStyleLineWidth'].value,6)
                ramp=style[b'strokeStyleContent'][b'Grad'][b'Trns']
                self.assertEqual([int(stop[b'Lctn'].value) for stop in ramp],[0,2048,4096])
                self.assertEqual(layer.opacity,191)
                pixels=layer.numpy()
                self.assertGreater(pixels[...,-1].max(),.9)
                if depth==32:self.assertAlmostEqual(float(pixels[10,10,0]),.1,places=5)

    def test_real_type_font_and_source_paths_survive_round_trip(self):
        doc=PSDImage.new('RGB',(160,64))
        info=dict(svg_kind='FONT',name='Label',body='Bfont',font_file=str(Path(__file__).parent/'vendor/fonts/Bfont-Regular.otf'),
                  font_postscript='Bfont-Regular',family='Bfont',size=20,matrix=[1,0,0,1,5,30],fill='#000000')
        text_layer(doc,info,(160,64),8)
        result=reopen(doc);layer=result[0]
        self.assertEqual(layer.kind,'type')
        self.assertEqual(layer.text,'Bfont\r')
        self.assertEqual(layer.resource_dict['FontSet'][0]['Name'].value,'Bfont-Regular')
        drawing=dict(name='Ink',opacity=1,blend_mode='MULTIPLY',strokes=[dict(rectangle(40,5,20,20),
            fill_id=1,fill='#4080a0',fill_opacity=1,stroke='none',width=0)])
        model=dict(width=160,height=64,objects=[dict(svg_kind='GP',name='Modified',layers=[drawing],
            modifiers=[dict(type='GREASE_PENCIL_MIRROR',render_enabled=True,settings=dict(use_axis_x=True))],
            source_geometry=[drawing])])
        append_artwork(doc,model,8)
        result=reopen(doc)
        self.assertEqual(result[1][0].blend_mode,BlendMode.MULTIPLY)
        saved=[r for key,r in result.image_resources.items() if 2000<=key<2998]
        self.assertEqual(len(saved),1)
        self.assertIn('original',saved[0].name)
        xmp=result.image_resources.get_data(Resource.XMP_METADATA)
        self.assertIn(b'GREASE_PENCIL_MIRROR',xmp)
        self.assertNotIn(b'.blend',xmp)

    def test_unsupported_text_keeps_source_pixels_without_partial_vector_groups(self):
        import json,tempfile
        from PIL import Image
        from psd_worker import assemble_psd
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=folder/'source.svg';source.write_text('<svg/>')
            from test_svg_instances import artwork
            model=dict(width=16,height=16,objects=[artwork(),dict(svg_kind='FONT',name='Paragraph',body='Two\nlines',
                font_file=str(Path(__file__).parent/'vendor/fonts/Bfont-Regular.otf'))])
            source.with_suffix('.vectors.json').write_text(json.dumps(model))
            png=folder/'cache.png';Image.new('RGBA',(16,16),(10,20,30,255)).save(png)
            dest=folder/'test.psd'
            job=dict(dest=str(dest),format='PSD',depth=8,extension='.png',overwrite=True,
                tag_profile='PASSTHROUGH',hierarchy='GROUPS',flatten=False)
            assemble_psd(job,
                [(dict(name='Source',vector_svg=str(source)),png)])
            result=PSDImage.open(dest)
            self.assertEqual(len(result),1)
            self.assertEqual(result[0].kind,'pixel')
            self.assertEqual(result[0].name,'Source')
            self.assertEqual(result[0].topil().getpixel((0,0)),(10,20,30,255))
            self.assertEqual([row['representation'] for row in job['_publication']],['RASTER_WITH_SOURCE'])
            self.assertTrue(Path(job['_publication'][0]['source_svg']).is_file())

    def test_worker_uses_shared_paths_preserving_source_blend_profile_and_depth(self):
        import json,tempfile
        from test_color_management import filtered_png16
        from psd_worker import assemble_psd
        from psd_tools.constants import SheetColorType
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=folder/'source.svg';source.write_text('<svg/>')
            stroke=dict(rectangle(2,2,8,8),fill_id=1,fill='#4080c0',fill_opacity=.8,stroke='',width=0)
            model=dict(width=16,height=16,objects=[dict(name='Ink',collection_parts=['Case.ref'],
                layers=[dict(name='Drawing',opacity=.7,strokes=[stroke])])])
            source.with_suffix('.vectors.json').write_text(json.dumps(model))
            png=folder/'cache.png';filtered_png16(png,np.zeros((16,16,4),dtype=np.uint16),0)
            dest=folder/'test.psd'
            assemble_psd(dict(dest=str(dest),format='PSD',depth=16,extension='.png',overwrite=True,
                tag_profile='PASSTHROUGH',hierarchy='GROUPS',flatten=False),
                [(dict(name='Source.multiply',vector_svg=str(source),collection_path='Art',collection_colors=['BLUE']),png)])
            result=PSDImage.open(dest)
            self.assertEqual(result.depth,16)
            self.assertTrue(result.image_resources.get_data(Resource.ICC_PROFILE))
            self.assertEqual(result[0].name,'Art')
            self.assertEqual(result[0].blend_mode,BlendMode.MULTIPLY)
            self.assertEqual(result[0][0].blend_mode,BlendMode.NORMAL)
            self.assertEqual(result[0][0].sheet_color,SheetColorType.BLUE)
            case=result[0][0][0]
            self.assertEqual(case.name,'Case')
            self.assertFalse(case.visible)
            self.assertEqual(case[0][0].kind,'shape')
            self.assertEqual(case[0].opacity,178)


if __name__=='__main__':unittest.main()
