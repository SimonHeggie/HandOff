import io,unittest
import numpy as np
from psd_tools import PSDImage
from psd_tools.constants import Tag
from psd_tools.psd.descriptor import Double
from psd_vectors import shape_layer
from psd_gradients import material_gradient

def paint(kind):
    contour=dict(type='BEZIER',cyclic=True,points=[dict(co=p,left=p,right=p) for p in ((2,2),(14,2),(14,14),(2,14))])
    contour['points'][0]['right']=(6,1)
    contour['fill_gradient']=dict(kind=kind,matrix=[16,0,0,16,0,8] if kind=='LINEAR' else [16,0,0,16,0,0],
        interpolation='LINEAR',color_mode='RGB',stops=[dict(position=p,color=c,linear=[.1,.2,2.5],opacity=a)
        for p,c,a in ((0,'#ff0000',1),(.5,'#00ff00',.4),(1,'#0000ff',0))])
    return dict(kind='fill',contours=[contour],color='#ffffff',opacity=.8)

class NativeGradientRecords(unittest.TestCase):
    def test_native_stop_alpha_bezier_and_hdr_records_at_all_depths(self):
        for depth in (8,16,32):
            for kind in ('LINEAR','RADIAL'):
                with self.subTest(depth=depth,kind=kind):
                    doc=PSDImage.new('RGB',(16,16),depth=depth)
                    shape_layer(doc,paint(kind),'Gradient',(16,16),depth,native_material_gradient=True)
                    buffer=io.BytesIO();doc.save(buffer);buffer.seek(0);loaded=PSDImage.open(buffer);layer=loaded[0]
                    self.assertEqual(layer.kind,'shape');self.assertEqual(loaded.depth,depth)
                    gradient=layer.tagged_blocks.get_data(Tag.GRADIENT_FILL_SETTING)
                    self.assertEqual(gradient[b'Type'].enum,b'Lnr ' if kind=='LINEAR' else b'Rdl ')
                    self.assertEqual([s[b'Lctn'].value for s in gradient[b'Grad'][b'Clrs']],[0,2048,4096])
                    self.assertEqual([s[b'Opct'].value for s in gradient[b'Grad'][b'Trns']],[100,40,0])
                    self.assertEqual(gradient[b'Ofst'][b'Hrzn'].value,0)
                    self.assertEqual(layer.vector_mask.paths[0][0].leaving,(1/16,6/16))
                    if depth==32:self.assertGreater(float(layer.numpy()[...,2].max()),2)
                    # Editing the selected native stop survives a second file
                    # save; target-editor rendering remains a separate gate.
                    gradient[b'Grad'][b'Clrs'][1][b'Clr '][b'Grn ']=Double(123)
                    again=io.BytesIO();loaded.save(again);again.seek(0);changed=PSDImage.open(again)
                    self.assertEqual(changed[0].tagged_blocks.get_data(Tag.GRADIENT_FILL_SETTING)[b'Grad'][b'Clrs'][1][b'Clr '][b'Grn '].value,123)

    def test_unverified_transform_and_interpolation_are_rejected(self):
        for change in ('ellipse','rotated','ease','repeat'):
            p=paint('RADIAL' if change=='ellipse' else 'LINEAR');g=p['contours'][0]['fill_gradient']
            if change=='ellipse':g['matrix']=[8,0,0,4,8,8]
            elif change=='rotated':g['matrix']=[16,16,-16,16,0,0]
            elif change=='ease':g['interpolation']='EASE'
            else:g['spread']='repeat'
            with self.assertRaises(ValueError):material_gradient(p,(16,16))
