"""Object-boundary, retry and opacity contracts for editable hybrid SVG."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from xml.etree import ElementTree as ET

from svg_export import VectorFallback, _uniform, _mixed_color, encode_svg
from svg_hybrid import (ordered_components, retained_hybrid, _evaluated_artwork,
                        queue_hybrid_svg, HYBRID, RESOLVED, DEFERRED)

SVG = '{http://www.w3.org/2000/svg}'


class ObjectClassificationTests(unittest.TestCase):
    def test_svg_canvas_matches_blender_integer_render_resolution(self):
        from svg_export import _render_size
        scene = NS(render=NS(resolution_x=2048, resolution_y=2729, resolution_percentage=10))
        self.assertEqual(_render_size(scene), (204,272))
        scene.render = NS(resolution_x=700, resolution_y=700, resolution_percentage=29)
        self.assertEqual(_render_size(scene), (203,203))

    def test_rasters_never_merge_across_an_editable_object(self):
        rows = [dict(kind='raster', name='Back 1', reason='lighting'),
                dict(kind='raster', name='Back 2', reason='lighting'),
                dict(kind='vector', name='Editable', artwork=dict(name='Editable')),
                dict(kind='raster', name='Front', reason='opacity')]
        parts, requests = ordered_components(rows)
        self.assertEqual([p.get('svg_kind', 'vector') for p in parts],
                         ['RASTER', 'vector', 'RASTER'])
        self.assertEqual([[r['name'] for r in group] for group in requests],
                         [['Back 1', 'Back 2'], ['Front']])
        self.assertEqual([parts[i]['request'] for i in (0, 2)], [0, 1])

    def test_modifiers_use_evaluated_geometry_and_baked_layer_adjustments(self):
        evaluated = NS(type='GREASEPENCIL')
        obj = NS(name='Mirror',modifiers=[NS(type='GREASE_PENCIL_MIRROR', name='Mirror',
                              show_render=True, show_viewport=True)],
                 evaluated_get=lambda graph: evaluated)
        scene, layer, graph = NS(camera=object()), object(), NS(mode='VIEWPORT')
        with patch('vector_artwork._gp_from_blender', return_value={'name':'Mirror','layers':[]}) as extract:
            artwork=_evaluated_artwork(scene, layer, obj, graph)
            self.assertEqual(artwork['name'],'Mirror')
            self.assertIs(artwork['source'],obj)
            self.assertEqual(artwork['modifiers'][0]['type'],'GREASE_PENCIL_MIRROR')
        self.assertEqual(extract.call_count,2)
        self.assertEqual(extract.call_args_list[0].args,(scene,scene.camera,evaluated,layer))
        self.assertEqual(extract.call_args_list[1].args,(scene,scene.camera,obj,layer))
        self.assertEqual(artwork['source_geometry'],[])

    def test_render_viewport_modifier_mismatch_uses_private_copy_and_cleans_up_on_failure(self):
        from unittest.mock import Mock
        import vector_artwork
        original=NS(show_render=True,show_viewport=False)
        copied=NS(show_render=True,show_viewport=False)
        duplicate=NS(modifiers=[copied],evaluated_get=Mock(return_value=object()))
        obj=NS(modifiers=[original],copy=Mock(return_value=duplicate))
        graph=NS(mode='VIEWPORT',update=Mock())
        scene=NS(collection=NS(objects=NS(link=Mock())))
        fake=NS(data=NS(objects=NS(remove=Mock())))
        with patch.dict('sys.modules',{'bpy':fake}):
            with self.assertRaisesRegex(RuntimeError,'extraction failed'):
                with vector_artwork.render_object(scene,obj,graph):
                    self.assertTrue(copied.show_viewport)
                    self.assertFalse(original.show_viewport)
                    raise RuntimeError('extraction failed')
        fake.data.objects.remove.assert_called_once_with(duplicate,do_unlink=True)
        self.assertFalse(original.show_viewport)
        self.assertEqual(graph.update.call_count,2)

    def test_constant_paint_is_editable_but_varying_attributes_require_fallback(self):
        self.assertEqual(_uniform([(.4,), (.4,)], 'varying'), (.4,))
        with self.assertRaisesRegex(VectorFallback, 'varying'):
            _uniform([(.4,), (.8,)], 'varying')
        self.assertEqual(_mixed_color((1, 0, 0, .3), (0, 0, 1, .5)), (.5, 0, .5, .3))


class RetainedHybridTests(unittest.TestCase):
    def test_all_raster_source_leaves_no_unfinished_plan_on_successful_fallback(self):
        import json
        import svg_hybrid
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.svg'
            plan = dict(scene='Scene', view_layer='GP', save_as_render=True)
            ET.ElementTree(ET.Element(SVG+'svg', {DEFERRED:json.dumps(plan)})).write(path)
            with patch.object(svg_hybrid, '_load_snapshot', return_value=(object(),object(),Path(folder)/'source.blend')), \
                    patch.object(svg_hybrid, 'export_hybrid_svg', return_value=(False, 'Unsupported GP')):
                self.assertFalse(svg_hybrid.resolve_hybrid_source(path, logger=lambda *a:None))
            self.assertFalse(path.exists())
            self.assertFalse(retained_hybrid(path))

    def test_render_preparation_does_not_evaluate_or_convert_colours(self):
        import svg_hybrid
        scene = NS(name='Source', frame_current=12,
                   render=NS(resolution_x=80, resolution_y=60, resolution_percentage=50))
        layer = NS(name='GP')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.svg'
            with patch.object(svg_hybrid, '_source_objects'), \
                    patch.object(svg_hybrid, '_write_snapshot', return_value=Path(folder)/'source.blend'), \
                    patch.object(svg_hybrid, '_evaluated_artwork', side_effect=AssertionError('render thread evaluation')), \
                    patch.object(svg_hybrid, '_scene_colors', side_effect=AssertionError('render thread scene mutation')):
                ok, reason = queue_hybrid_svg(scene, layer, path)
            self.assertTrue(ok, reason)
            self.assertEqual(ET.parse(path).getroot().get('viewBox'), '0 0 40 30')
            with self.assertRaisesRegex(ValueError, 'preparation is incomplete'):
                retained_hybrid(path)

    def test_retry_requires_complete_coupled_artwork(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.svg'
            root = ET.Element(SVG+'svg', {HYBRID:'1'})
            ET.ElementTree(root).write(path)
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                retained_hybrid(path)
            root.set(RESOLVED, '1')
            ET.ElementTree(root).write(path)
            self.assertTrue(retained_hybrid(path))
            root.attrib.clear()
            ET.ElementTree(root).write(path)
            self.assertFalse(retained_hybrid(path))


class SVGOpacityTests(unittest.TestCase):
    def test_object_container_and_layer_path_labels_without_repeated_wrapper(self):
        stroke = dict(type='POLY', points=[dict(co=p) for p in ((0,0),(2,0),(2,2))],
                      cyclic=True, fill_id=1, fill='#ffffff', fill_opacity=1, stroke='', width=0)
        root = ET.fromstring(encode_svg(3,3,[dict(name='Golden outline', layers=[
            dict(name='Ink', opacity=.35, strokes=[stroke])])]))
        group = root.find(SVG+'g')
        ink = '{http://www.inkscape.org/namespaces/inkscape}'
        self.assertEqual(group.get(ink+'label'), 'Golden outline')
        self.assertEqual(group.get('data-compio-layer'), 'Ink')
        self.assertEqual(group.get('opacity'), '0.35')
        self.assertIsNone(group.find(SVG+'g'))
        self.assertEqual(group.find(SVG+'path').get(ink+'label'), 'Ink')

    def test_worker_rejection_uses_cached_png_instead_of_empty_vector_stub(self):
        from PIL import Image
        from svg_document import write_svg_document
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache, source, dest = (root/name for name in ('input.png','source.svg','document.svg'))
            Image.new('RGBA', (3,3), (128,64,32,255)).save(cache)
            ET.ElementTree(ET.Element(SVG+'svg', {DEFERRED:'{}'})).write(source)
            with patch('svg_hybrid.resolve_hybrid_source', return_value=False):
                write_svg_document(dict(dest=str(dest), depth=8, hierarchy='GROUPS'),
                                   [(dict(name='Art', vector_svg=str(source)), cache)], logger=lambda *a:None)
            parsed = ET.parse(dest).getroot()
            self.assertEqual(len(list(parsed.iter(SVG+'image'))), 1)
            self.assertFalse(list(parsed.iter(SVG+'path')))

    def test_repeated_object_and_layer_labels_keep_group_opacity(self):
        from PIL import Image
        from svg_document import write_svg_document
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache = root/'input.png'
            Image.new('RGBA', (3,3)).save(cache)
            source = root/'source.svg'
            stroke = dict(type='POLY', points=[dict(co=p) for p in ((0,0),(2,0),(2,2))],
                          cyclic=True, fill_id=1, fill='#ffffff', fill_opacity=1, stroke='', width=0)
            source.write_text(encode_svg(3,3,[dict(name='Art', layers=[
                dict(name='Art', opacity=.35, strokes=[stroke])])]))
            dest = root/'document.svg'
            write_svg_document(dict(dest=str(dest), depth=8, hierarchy='GROUPS'),
                               [(dict(name='Art', vector_svg=str(source)), cache)], logger=lambda *a:None)
            parsed = ET.parse(dest).getroot()
            self.assertEqual([n.get('opacity') for n in parsed.iter() if n.get('opacity')], ['0.35'])
            self.assertEqual(len(list(parsed.iter(SVG+'path'))), 1)


if __name__ == '__main__':
    unittest.main()
