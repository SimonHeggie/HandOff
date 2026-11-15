"""Editable pressure geometry, independent alpha and imported resource IDs."""
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from svg_export import encode_svg,VectorFallback
from svg_pressure import prepare

SVG='{http://www.w3.org/2000/svg}'
INK='{http://www.inkscape.org/namespaces/inkscape}'


def stroke():
    return dict(type='BEZIER',cyclic=False,fill_id=0,stroke='#408060',width=2,
                stroke_opacity=.6,points=[dict(co=(0,0),left=(-1,0),right=(3,0)),
                                         dict(co=(10,2),left=(7,2),right=(11,2))],
                pressure=dict(widths=[2,6],opacities=[.2,.8]))


class PressureTests(unittest.TestCase):
    def test_live_cubic_width_and_independent_editable_opacity_gradient(self):
        s=stroke();prepare(s)
        root=ET.fromstring(encode_svg(20,20,[dict(name='Pressure',layers=[dict(name='Ink',opacity=.5,strokes=[s])])]))
        effect=root.find('.//'+INK+'path-effect');self.assertEqual(effect.get('effect'),'powerstroke')
        self.assertEqual(effect.get('offset_points'),'0,1 | 1,3')
        path=root.find('.//'+SVG+'path')
        self.assertIn('C ',path.get(INK+'original-d'))
        self.assertEqual(path.get('fill-opacity'),'0.6')
        self.assertEqual(root[0].get('opacity'),'0.5')
        stops=list(root.iter(SVG+'stop'))
        self.assertEqual([n.get('stop-opacity') for n in stops],['0.2','0.8'])
        self.assertNotEqual(path.get('d'),path.get(INK+'original-d'))

    def test_closed_pressure_and_reversing_alpha_retain_explicit_fallback(self):
        s=stroke();s['cyclic']=True
        with self.assertRaisesRegex(VectorFallback,'open visible'):prepare(s)
        s=stroke();s['type']='POLY';s['pressure']={'opacities':[0,.5,1]}
        s['points']=[dict(co=p) for p in ((0,0),(10,0),(5,0))]
        with self.assertRaisesRegex(VectorFallback,'reversing'):prepare(s)

    def test_import_prefixes_effect_gradient_and_all_references_for_two_sources(self):
        from svg_document import write_svg_document
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);s=stroke();prepare(s)
            source=folder/'pressure.svg';source.write_text(encode_svg(20,20,[dict(name='Pressure',layers=[dict(name='Ink',strokes=[s])])]))
            cache=folder/'pixels.png';Image.new('RGBA',(20,20)).save(cache)
            dest=folder/'document.svg'
            write_svg_document(dict(dest=str(dest),depth=8,hierarchy='FLAT'),
                               [(dict(name=name,vector_svg=str(source)),cache) for name in ('Front','Back')],logger=lambda *a:None)
            root=ET.parse(dest).getroot();ids=[n.get('id') for n in root.iter() if n.get('id')]
            self.assertEqual(len(ids),len(set(ids)))
            paths=[n for n in root.iter(SVG+'path') if n.get(INK+'path-effect')]
            self.assertEqual(len(paths),2)
            for path in paths:
                self.assertIn(path.get(INK+'path-effect')[1:],ids)
                self.assertIn(path.get('fill')[5:-1],ids)
            self.assertNotEqual(paths[0].get('fill'),paths[1].get('fill'))


if __name__=='__main__':unittest.main()
