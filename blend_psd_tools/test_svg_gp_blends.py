"""SVG blend mappings, object isolation and retained-job contracts."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from xml.etree import ElementTree as ET

import svg_export as vectors
import vector_artwork as reader
import svg_hybrid as hybrid

SVG = '{http://www.w3.org/2000/svg}'


def square():
    return dict(type='POLY', points=[dict(co=p) for p in ((0,0),(2,0),(2,2),(0,2))],
                cyclic=True, fill_id=1, fill='#ffffff', fill_opacity=.7, stroke='', width=0)


class GPBlendTests(unittest.TestCase):
    def test_layers_keep_opacity_order_and_standard_blends_inside_isolated_object(self):
        layers = [dict(name=name, opacity=.4, blend_mode=mode, strokes=[square()])
                  for name,mode in [('Base','REGULAR'),('Shadow','MULTIPLY'),('Light','HARDLIGHT')]]
        root = ET.fromstring(vectors.encode_svg(3,3,[dict(name='Paint',layers=layers)]))
        obj = root.find(SVG+'g')
        self.assertEqual(obj.get('style'), 'isolation:isolate')
        self.assertEqual([g.get('data-compio-layer') for g in obj], ['Base','Shadow','Light'])
        self.assertEqual([g.get('style') for g in obj],
                         [None, 'mix-blend-mode:multiply', 'mix-blend-mode:hard-light'])
        self.assertEqual([g.get('opacity') for g in obj], ['0.4']*3)
        self.assertEqual([g.find(SVG+'path').get('fill-opacity') for g in obj], ['0.7']*3)
        self.assertFalse(list(root.iter(SVG+'image')))

    def test_single_blended_layer_cannot_blend_against_an_unrelated_object(self):
        artwork = dict(name='Paint', layers=[dict(name='Ink', blend_mode='MULTIPLY', strokes=[square()])])
        obj = ET.fromstring(vectors.encode_svg(3,3,[artwork])).find(SVG+'g')
        self.assertEqual(obj.get('style'), 'isolation:isolate')
        self.assertEqual(obj[0].get('style'), 'mix-blend-mode:multiply')
        self.assertEqual(obj[0].get('data-compio-layer'), 'Ink')

    def test_explicit_rendered_mode_and_approximate_math_mappings(self):
        layer = NS(name='Ink', opacity=.5, use_lights=False, blend_mode='MULTIPLY',
                   current_frame=lambda:NS(drawing=NS(strokes=[object()])))
        obj = NS(name='Paint', data=object(), use_grease_pencil_lights=False)
        with patch.object(reader, '_iter_gp_layers', return_value=[layer]), \
                patch.object(reader, '_stroke_from_blender', return_value=square()):
            for mode in ('MULTIPLY','HARDLIGHT','ADD','SUBTRACT','DIVIDE'):
                layer.blend_mode = mode
                with self.assertRaisesRegex(vectors.VectorFallback, 'retain Blender appearance'):
                    vectors._gp_from_blender(None,None,obj,NS(name='GP'))
                art = vectors._gp_from_blender(None,None,obj,NS(name='GP'), editable_layer_blends=True)
                self.assertEqual(art['layers'][0]['blend_mode'], mode)
            for mode,css in [('ADD','screen'),('SUBTRACT','difference'),('DIVIDE','color-dodge')]:
                group=ET.fromstring(vectors.encode_svg(3,3,[dict(name='Paint',layers=[
                    dict(name='Ink',blend_mode=mode,strokes=[square()])])]))[0][0]
                self.assertEqual(group.get('style'),'mix-blend-mode:'+css)
                self.assertEqual(group.get('data-compio-blend-approximation'),css)
            for mode in ('UNKNOWN',):
                layer.blend_mode = mode
                with self.assertRaisesRegex(vectors.VectorFallback, 'no supported SVG equivalent'):
                    vectors._gp_from_blender(None,None,obj,NS(name='GP'), editable_layer_blends=True)
                with self.assertRaises(vectors.VectorFallback):
                    vectors.encode_svg(3,3,[dict(name='Paint',layers=[dict(name='Ink',blend_mode=mode,strokes=[square()])])])

    def test_f12_defers_blend_setting_without_touching_scene(self):
        scene = NS(name='Scene',frame_current=1,
                   render=NS(resolution_x=3,resolution_y=3,resolution_percentage=100))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'source.svg'
            with patch.object(hybrid,'_source_objects'), \
                    patch.object(hybrid,'_write_snapshot',return_value=path.with_suffix('.blend')):
                ok,reason = hybrid.queue_hybrid_svg(scene,NS(name='GP'),path,editable_layer_blends=True)
            self.assertTrue(ok,reason)
            plan = json.loads(ET.parse(path).getroot().get(hybrid.DEFERRED))
            self.assertIs(plan['editable_layer_blends'],True)

    def test_retry_rejects_changed_blend_semantics_instead_of_reusing_old_pixels(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'source.svg'
            root = ET.Element(SVG+'svg',{hybrid.HYBRID:'1',hybrid.RESOLVED:'1'})
            ET.ElementTree(root).write(path)
            self.assertTrue(hybrid.retained_hybrid(path,editable_layer_blends=False))
            with self.assertRaisesRegex(ValueError,'Layer Blends changed.*F12'):
                hybrid.retained_hybrid(path,editable_layer_blends=True)
            root.set(hybrid.LAYER_BLENDS,'1')
            root.set(hybrid.BLEND_VERSION,'2')
            ET.ElementTree(root).write(path)
            self.assertTrue(hybrid.retained_hybrid(path,editable_layer_blends=True))
            with self.assertRaises(ValueError):
                hybrid.retained_hybrid(path,editable_layer_blends=False)

    def test_document_import_keeps_native_svg_blend_groups(self):
        from PIL import Image
        from svg_document import write_svg_document
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            source,cache,dest = (path/name for name in ('source.svg','input.png','document.svg'))
            source.write_text(vectors.encode_svg(3,3,[dict(name='Paint',layers=[
                dict(name='Base',strokes=[square()]),
                dict(name='Shadow',opacity=.5,blend_mode='MULTIPLY',strokes=[square()])])]))
            Image.new('RGBA',(3,3)).save(cache)
            write_svg_document(dict(dest=str(dest),depth=8,hierarchy='GROUPS'),
                               [(dict(name='Art',vector_svg=str(source)),cache)],logger=lambda *args:None)
            root = ET.parse(dest).getroot()
            blended = [n for n in root.iter() if n.get('data-compio-gp-blend')]
            self.assertEqual(len(blended),1)
            self.assertEqual(blended[0].get('style'),'mix-blend-mode:multiply')
            self.assertEqual(blended[0].get('opacity'),'0.5')
            self.assertTrue(any(n.get('style')=='isolation:isolate' for n in root.iter()))
            self.assertFalse(list(root.iter(SVG+'image')))


if __name__ == '__main__':
    unittest.main()
