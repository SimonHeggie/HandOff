"""Material ramps retain vector geometry and survive document resource import."""
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from svg_export import encode_svg
from test_svg_export import point

SVG = '{http://www.w3.org/2000/svg}'


def artwork():
    gradient = dict(kind='RADIAL', matrix=(30, 4, 8, 25, 2, 3), stops=[
        dict(position=0, color='#ffffff', opacity=1),
        dict(position=.4, color='#80c0ff', opacity=.5),
        dict(position=1, color='#ffffff', opacity=0)])
    stroke = dict(type='BEZIER', cyclic=True, fill_id=1, fill='#ffffff', fill_opacity=.7,
                  stroke='', width=0, fill_gradient=gradient,
                  points=[point(3, 3, (3, 3), (8, 1)), point(30, 3, (25, 1), (30, 8)),
                          point(30, 30, (30, 25), (25, 30)), point(3, 30, (8, 30), (3, 25))])
    return dict(name='Shine', layers=[dict(name='Glow', opacity=.8, strokes=[stroke])])


class GradientTests(unittest.TestCase):
    def test_ramp_has_its_transform_alpha_and_original_cubic_path(self):
        root = ET.fromstring(encode_svg(40, 40, [artwork()]))
        gradient = root.find('.//' + SVG + 'radialGradient')
        self.assertEqual(gradient.get('gradientTransform'), 'matrix(30 4 8 25 2 3)')
        self.assertEqual(gradient.get('gradientUnits'), 'userSpaceOnUse')
        self.assertEqual([s.get('stop-opacity') for s in gradient], ['1', '0.5', '0'])
        path = root.find('.//' + SVG + 'path')
        self.assertEqual(path.get('fill'), 'url(#' + gradient.get('id') + ')')
        self.assertIn('C 8 1 25 1 30 3', path.get('d'))
        self.assertFalse(list(root.iter(SVG + 'image')))

    def test_document_import_prefixes_two_independent_material_gradients(self):
        from PIL import Image
        from svg_document import write_svg_document
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder/'source.svg'
            source.write_text(encode_svg(40, 40, [artwork()]))
            cache = folder/'cache.png'
            Image.new('RGBA', (40, 40)).save(cache)
            dest = folder/'document.svg'
            write_svg_document(dict(dest=str(dest), depth=8, hierarchy='FLAT'),
                [(dict(name=n, vector_svg=str(source)), cache) for n in ('A', 'B')], logger=lambda *a: None)
            root = ET.parse(dest).getroot()
            gradients = list(root.iter(SVG+'radialGradient'))
            self.assertEqual(len(gradients), 2)
            ids = [g.get('id') for g in gradients]
            self.assertEqual(len(set(ids)), 2)
            self.assertEqual({p.get('fill') for p in root.iter(SVG+'path')},
                             {'url(#' + i + ')' for i in ids})

    def test_psd_gradient_keeps_native_render_without_partial_shapes(self):
        import json
        from PIL import Image
        from psd_tools import PSDImage
        from psd_worker import assemble_psd
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder/'source.svg'
            source.write_text(encode_svg(40, 40, [artwork()]))
            source.with_suffix('.vectors.json').write_text(json.dumps(dict(width=40, height=40, objects=[artwork()])))
            cache = folder/'cache.png'
            Image.new('RGBA', (40, 40), (240, 200, 100, 128)).save(cache)
            dest = folder/'document.psd'
            assemble_psd(dict(dest=str(dest), format='PSD', depth=8, extension='.png', overwrite=True,
                tag_profile='PASSTHROUGH', hierarchy='GROUPS', flatten=False),
                [(dict(name='Shine', vector_svg=str(source)), cache)])
            doc = PSDImage.open(dest)
            self.assertEqual(len(doc), 1)
            self.assertEqual(doc[0].kind, 'smartobject')
            self.assertEqual(doc[0].composite().getpixel((10, 10)), (240, 200, 100, 128))


if __name__ == '__main__':
    unittest.main()
