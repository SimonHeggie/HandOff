"""Blender-free tests for HandOff SVG and transparent PNG fallback."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from svg_export import svg_path, encode_svg, VectorFallback, _stroke_from_blender, _camera_visible_objects
from svg_source import direct_render_image_source
from psd_worker import assemble


def point(x, y, left=None, right=None):
    return {'co': (x,y), 'left': left, 'right': right}


class SourceTracing(unittest.TestCase):
    def test_direct_render_node_allowed(self):
        layer = SimpleNamespace(name='Sprite')
        scene = SimpleNamespace(view_layers={'Sprite': layer})
        n = SimpleNamespace(bl_idname='CompositorNodeRLayers')
        socket = SimpleNamespace(node=n, name='Image')
        sc, vl, reason = direct_render_image_source(None, socket, scene, lambda *a, **k: [(scene,'Sprite')])
        self.assertIs(sc, scene)
        self.assertIs(vl, layer)

    def test_effect_chain_falls_back(self):
        n = SimpleNamespace(bl_idname='CompositorNodeGlare')
        sc, vl, reason = direct_render_image_source(None, SimpleNamespace(node=n,name='Image'), None, lambda *a, **k: [])
        self.assertIsNone(vl)
        self.assertIn('processing', reason)


class SVGTests(unittest.TestCase):
    def test_bezier_handles_and_negative_fill(self):
        outer = [point(10, 10, right=(30, 0), left=(0, 15)),
                 point(50, 15, left=(32, 4), right=(60, 20)),
                 point(50, 60, left=(64, 50), right=(23, 70))]
        inner = [point(30, 23), point(40, 40), point(20, 40)]
        strokes = [dict(type='BEZIER', points=outer, cyclic=True, fill_id=1, fill='#ffffff',
                        fill_opacity=1, stroke='', width=0),
                   dict(type='POLY', points=inner, cyclic=True, fill_id=1, fill='#ffffff',
                        fill_opacity=1, stroke='', width=0)]
        svg = encode_svg(256, 512, [dict(name='Shine', layers=[dict(name='Fill', opacity=1, strokes=strokes)])])
        self.assertIn('C 30 0 32 4 50 15', svg)
        self.assertIn('fill-rule="evenodd"', svg)
        self.assertEqual(svg.count('<path'), 1)
        root = ET.fromstring(svg)
        self.assertEqual(root.attrib['viewBox'], '0 0 256 512')

    def test_blender_integer_bezier_curve_api(self):
        # GPv3 uses stroke.curve_type == 2, not stroke.type == 'BEZIER'.
        from unittest.mock import patch
        import types
        class Vec(tuple):
            def __new__(cls, val):
                return tuple.__new__(cls, val)
            def __add__(self, other):
                return Vec(tuple(a+b for a,b in zip(self, other)))
        class Mat:
            def __matmul__(self, v):
                return v
            def to_3x3(self):
                return self
        mathutils = types.ModuleType('mathutils')
        mathutils.Vector = Vec
        extra = types.ModuleType('bpy_extras')
        utils = types.ModuleType('bpy_extras.object_utils')
        utils.world_to_camera_view = lambda scene, camera, p: SimpleNamespace(x=p[0], y=p[1], z=1)
        extra.object_utils = utils
        mat = SimpleNamespace(grease_pencil=SimpleNamespace(show_stroke=False, show_fill=True,
                               color=(1,1,1,1), fill_color=(1,1,1,1), fill_style='SOLID', stroke_style='SOLID'))
        obj = SimpleNamespace(matrix_world=Mat(), material_slots=[SimpleNamespace(material=mat)])
        camera = SimpleNamespace(matrix_world=Mat())
        scene = SimpleNamespace(render=SimpleNamespace(resolution_x=200, resolution_y=100,
                                                      resolution_percentage=100))
        coords = ((.2,.2,0),(.5,.2,0),(.5,.7,0))
        points = [SimpleNamespace(position=xyz, handle_left=SimpleNamespace(position=xyz),
                    handle_right=SimpleNamespace(position=xyz), radius=.01, opacity=1,
                    vertex_color=(0,0,0,0)) for xyz in coords]
        stroke = SimpleNamespace(curve_type=2, points=points, material_index=0, cyclic=True,
                                 fill_id=1, hide_stroke=True, fill_color=(0,0,0,0), fill_opacity=1,
                                 softness=0, aspect_ratio=1)
        with patch.dict(sys.modules, {'mathutils':mathutils,'bpy_extras':extra,
                                      'bpy_extras.object_utils':utils}):
            extracted = _stroke_from_blender(scene, camera, obj, SimpleNamespace(), stroke)
        self.assertEqual(extracted['type'], 'BEZIER')
        self.assertEqual(extracted['fill_id'], 1)
        self.assertEqual(extracted['points'][0]['co'], (40,80))

        # Blender's DNA CurveType enum uses 1 for POLY (0 is Catmull-Rom).
        # Real GP drawings in the compatibility atlas exercise this path.
        stroke.curve_type = 1
        with patch.dict(sys.modules, {'mathutils':mathutils,'bpy_extras':extra,
                                      'bpy_extras.object_utils':utils}):
            extracted = _stroke_from_blender(scene, camera, obj, SimpleNamespace(), stroke)
        self.assertEqual(extracted['type'], 'POLY')
        self.assertEqual(extracted['points'][0]['co'], (40,80))

    def test_interpolated_gp_types_are_not_treated_as_polylines(self):
        for kind in (0, 3):  # CATMULL_ROM, NURBS
            with self.subTest(curve_type=kind), self.assertRaisesRegex(
                    VectorFallback, 'Unsupported GP stroke curve type'):
                _stroke_from_blender(None, None, None, None,
                                     SimpleNamespace(curve_type=kind))

    def test_gp_51_fill_visibility_ignores_legacy_material_toggles(self):
        from unittest.mock import patch
        import types
        class Vec(tuple):
            def __new__(cls, xyz): return super().__new__(cls, xyz)
            def __add__(self, other): return Vec(tuple(a+b for a,b in zip(self, other)))
        class Mat:
            def __matmul__(self, value): return value
            def to_3x3(self): return self
        mathutils=types.ModuleType('mathutils'); mathutils.Vector=Vec
        extra=types.ModuleType('bpy_extras'); utils=types.ModuleType('bpy_extras.object_utils')
        utils.world_to_camera_view=lambda scene, camera, v:SimpleNamespace(x=v[0],y=v[1],z=1)
        extra.object_utils=utils
        # Blender 5.1+ ignores the legacy material flags; this must still fill.
        material=SimpleNamespace(grease_pencil=SimpleNamespace(
            show_fill=False, show_stroke=False, color=(1,1,1,1), fill_color=(1,1,1,1),
            fill_style='SOLID', stroke_style='SOLID'))
        obj=SimpleNamespace(matrix_world=Mat(),material_slots=[SimpleNamespace(material=material)])
        camera=SimpleNamespace(matrix_world=Mat())
        scene=SimpleNamespace(render=SimpleNamespace(resolution_x=100,resolution_y=100,resolution_percentage=100))
        points=[SimpleNamespace(position=(x,y,0),handle_left=(x,y,0),handle_right=(x,y,0),
                                radius=.01, opacity=1, vertex_color=(0,0,0,0))
                for x,y in ((.2,.2),(.5,.2),(.5,.6))]
        gp=SimpleNamespace(curve_type=2,points=points,material_index=0,cyclic=True,
                           fill_id=7,hide_stroke=True,fill_color=(0,0,0,0),fill_opacity=1,
                           softness=0,aspect_ratio=1)
        with patch.dict(sys.modules, {'mathutils':mathutils,'bpy_extras':extra,
                                       'bpy_extras.object_utils':utils}):
            extracted=_stroke_from_blender(scene,camera,obj,SimpleNamespace(),gp)
            self.assertEqual(extracted['fill_id'], 7)
            self.assertEqual(extracted['stroke'], '')
            gp.hide_stroke=False
            extracted=_stroke_from_blender(scene,camera,obj,SimpleNamespace(),gp)
            self.assertTrue(extracted['stroke'])
            # Different point radii do not prevent fill-only SVG conversion.
            gp.points[1].radius=.025
            gp.hide_stroke=True
            extracted=_stroke_from_blender(scene,camera,obj,SimpleNamespace(),gp)
            self.assertEqual(extracted['fill_id'],7)
            gp.hide_stroke=False
            with self.assertRaisesRegex(VectorFallback,'Variable-width visible stroke'):
                _stroke_from_blender(scene,camera,obj,SimpleNamespace(),gp)

    def test_view_layer_specific_gp_drawing_rejected_with_reason(self):
        from unittest.mock import patch
        from svg_export import export_view_layer_svg
        layer=SimpleNamespace(name='ShineLayer', viewlayer_render='Combined')
        gp=SimpleNamespace(type='GREASEPENCIL', name='ShineSprite',
                           data=SimpleNamespace(root_nodes=[layer]),modifiers=[],shader_effects=[])
        view=SimpleNamespace(name='Shine', use_grease_pencil=True)
        scene=SimpleNamespace(camera=SimpleNamespace(data=SimpleNamespace(type='ORTHO',
                   dof=SimpleNamespace(use_dof=False))),
                   render=SimpleNamespace(film_transparent=True,use_motion_blur=False),frame_current=1)
        with patch('svg_export._camera_visible_objects',return_value=[gp]), \
             patch('svg_export._is_visible',return_value=True):
            ok,reason=export_view_layer_svg(scene,view,'/tmp/should-not-write.svg')
        self.assertFalse(ok)
        self.assertIn('assigned to Combined',reason)
        self.assertIn('View Layer Shine',reason)

    def test_interleaved_fill_contours_fall_back(self):
        shape = [point(0,0),point(1,0),point(1,1)]
        strokes = [dict(type='POLY', points=shape, cyclic=True, fill_id=fid,
                        fill='#fff', fill_opacity=1, stroke='', width=0) for fid in (1,2,1)]
        with self.assertRaises(VectorFallback):
            encode_svg(10,10,[dict(name='GP',layers=[dict(name='L',strokes=strokes)])])

    def test_indirect_only_collection_does_not_count_as_camera_geometry(self):
        gp = SimpleNamespace(type='GREASEPENCIL')
        mesh = SimpleNamespace(type='MESH')
        direct = SimpleNamespace(exclude=False, indirect_only=False,
                                 collection=SimpleNamespace(objects=[gp]),children=[])
        indirect = SimpleNamespace(exclude=False, indirect_only=True,
                                   collection=SimpleNamespace(objects=[mesh]),children=[])
        parent=SimpleNamespace(exclude=False,indirect_only=False,
                               collection=SimpleNamespace(objects=[]),children=[direct,indirect])
        view=SimpleNamespace(layer_collection=parent,objects=[gp,mesh])
        self.assertEqual(_camera_visible_objects(view),[gp])

    def test_two_gp_objects_are_preserved_as_vectors(self):
        # Regression: the 7.24 exporter rejected *every* two-object View Layer.
        from unittest.mock import patch
        from svg_export import export_view_layer_svg
        class DrawingLayer:
            name='Shine'
            hide=False
            opacity=1
            viewlayer_render=''
            use_lights=False
            blend_mode='REGULAR'
            use_masks=False
            layer_masks=()
            def current_frame(self):
                return SimpleNamespace(drawing=SimpleNamespace(strokes=[object()]))
        def obj(name):
            return SimpleNamespace(type='GREASEPENCIL',name=name,
                data=SimpleNamespace(root_nodes=[DrawingLayer()]),modifiers=[],shader_effects=[])
        near, far = obj('ShineSprite'), obj('ShineSprite.001')
        camera=SimpleNamespace(data=SimpleNamespace(type='ORTHO',dof=SimpleNamespace(use_dof=False)))
        scene=SimpleNamespace(camera=camera,render=SimpleNamespace(film_transparent=True,use_motion_blur=False),frame_current=1)
        view=SimpleNamespace(name='Shine',use_grease_pencil=True)
        def content(scene,cam,gp,layer,stroke, **kwargs):
            off=2 if gp is far else 12
            return dict(type='POLY',points=[point(off,2),point(off+3,2),point(off+3,5)],
                        cyclic=True,fill_id=1,fill='#ffffff',fill_opacity=1,
                        stroke='',width=0,material_index=0)
        with TemporaryDirectory() as tmp:
            out=Path(tmp)/'shine.svg'
            with patch('svg_export._camera_visible_objects',return_value=[near,far]), \
                 patch('svg_export._is_visible',return_value=True), \
                 patch('vector_artwork._stroke_from_blender',side_effect=content), \
                 patch('svg_export._render_size',return_value=(32,32)), \
                 patch('vector_artwork._object_camera_depth',side_effect=lambda sc,ca,gp: 2 if gp is far else 1):
                ok, reason=export_view_layer_svg(scene,view,out)
            self.assertTrue(ok,reason)
            doc=ET.parse(out).getroot()
            ns='{http://www.w3.org/2000/svg}'
            self.assertEqual(len(list(doc.iter(ns+'path'))),2)
            self.assertEqual([g.get('data-handoff-object') for g in doc.findall(ns+'g')],
                             ['ShineSprite.001','ShineSprite'])

    def test_fill_and_visible_stroke_from_same_curve_become_one_path(self):
        points=[point(0,0),point(6,0),point(6,6)]
        stroke=dict(type='POLY',points=points,cyclic=True,fill_id=2,
                    fill='#ffffff',fill_opacity=1,stroke='#fedcba',
                    stroke_opacity=.75,width=2,material_index=0)
        markup=encode_svg(16,16,[dict(name='Star',layers=[dict(name='Shine',strokes=[stroke])])])
        doc=ET.fromstring(markup)
        paths=list(doc.iter('{http://www.w3.org/2000/svg}path'))
        self.assertEqual(len(paths),1)
        self.assertEqual(paths[0].get('fill'),'#ffffff')
        self.assertEqual(paths[0].get('stroke'),'#fedcba')
        self.assertEqual(paths[0].get('stroke-opacity'),'0.75')
        self.assertEqual(paths[0].get('{http://www.inkscape.org/namespaces/inkscape}label'),'Shine')
        # An alpha-zero stroke is omitted even with the same curve and fill.
        stroke['stroke_opacity']=0
        path=list(ET.fromstring(encode_svg(16,16,[dict(name='Star',layers=[dict(name='Shine',strokes=[stroke])])])).iter('{http://www.w3.org/2000/svg}path'))[0]
        self.assertEqual(path.get('stroke'),'none')

    def test_adjacent_identical_fill_and_outline_curves_share_one_path(self):
        pts=[point(0,0),point(6,0),point(6,6)]
        filled=dict(type='POLY',points=pts,cyclic=True,fill_id=3,fill='#ffffff',fill_opacity=1,
                    stroke='',width=0,material_index=0)
        outline=dict(type='POLY',points=pts,cyclic=True,fill_id=0,fill='#ffffff',fill_opacity=0,
                     stroke='#aaaaaa',stroke_opacity=1,width=2,material_index=0)
        text=encode_svg(16,16,[dict(name='Sprite',layers=[dict(name='Shine',strokes=[filled,outline])])])
        paths=list(ET.fromstring(text).iter('{http://www.w3.org/2000/svg}path'))
        self.assertEqual(len(paths),1)
        self.assertEqual(paths[0].get('stroke'),'#aaaaaa')
        outline['material_index']=2
        text=encode_svg(16,16,[dict(name='Sprite',layers=[dict(name='Shine',strokes=[filled,outline])])])
        self.assertEqual(len(list(ET.fromstring(text).iter('{http://www.w3.org/2000/svg}path'))),2)

    def test_untagged_collection_uses_neutral_inkscape_highlight(self):
        from PIL import Image
        with TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'cache';cache.mkdir()
            Image.new('RGBA',(2,2),(1,2,3,255)).save(cache/'psd_L0000_0001.png')
            job=dict(format='SVG',dir=str(cache),dest=str(root/'Art.svg'),depth=8,
                     extension='.png',overwrite=True,hierarchy='GROUPS',tag_profile='PASSTHROUGH',
                     manifest=[dict(name='Artwork',slug='psd_L0000_',collection_path='Untagged',
                                    collection_colors=[''])])
            assemble(job)
            doc=ET.parse(root/'Art.svg').getroot()
            ns='{http://www.w3.org/2000/svg}'
            ink='{http://www.inkscape.org/namespaces/inkscape}'
            col=next(g for g in doc.iter(ns+'g') if g.get(ink+'label')=='Untagged')
            self.assertEqual(col.get(ink+'groupmode'),'layer')
            self.assertEqual(col.get(ink+'highlight-color'),'#ffffff')

    def test_compound_fill_has_one_outline_even_with_multiple_hole_contours(self):
        # This reproduces the GP layer with a fill plus four contour curves.
        # The inner hole is not outlined; the other three outlines share paint.
        points = [point(1,1),point(9,1),point(9,9),point(1,9)]
        contours = []
        for j in range(4):
            contours.append(dict(type='POLY',points=points,cyclic=True,fill_id=3,
                                 fill='#ffffff',fill_opacity=1,
                                 stroke='' if j == 1 else '#ddff00',
                                 stroke_opacity=1,width=6.4,material_index=0))
        svg = encode_svg(20,20,[dict(name='ShineSprite',layers=[dict(name='Shine',strokes=contours)])])
        ns = '{http://www.w3.org/2000/svg}'
        inkscape = '{http://www.inkscape.org/namespaces/inkscape}'
        paths = list(ET.fromstring(svg).iter(ns+'path'))
        self.assertEqual(len(paths),2)  # One compound fill, one compound outline.
        self.assertEqual(paths[0].get('fill'), '#ffffff')
        self.assertEqual(paths[0].get('stroke'), 'none')
        self.assertEqual(paths[1].get('fill'), 'none')
        self.assertEqual(paths[1].get('stroke'), '#ddff00')
        self.assertEqual(paths[1].get('stroke-width'), '6.4')
        self.assertEqual(paths[1].get('d').count('M '),3)
        self.assertEqual(paths[1].get(inkscape+'label'),'Shine')

    def test_compound_fill_outlines_can_share_one_path(self):
        pts=[point(2,2),point(10,2),point(10,10)]
        strokes=[dict(type='POLY',points=pts,cyclic=True,fill_id=11,
                      fill='#eeeeee',fill_opacity=1,stroke='#aadd00',
                      stroke_opacity=1,width=5,material_index=0) for _ in range(4)]
        svg=encode_svg(20,20,[dict(name='Star',layers=[dict(name='Shine',strokes=strokes)])])
        paths=list(ET.fromstring(svg).iter('{http://www.w3.org/2000/svg}path'))
        self.assertEqual(len(paths),1)
        self.assertEqual(paths[0].get('d').count('M '),4)
        self.assertEqual(paths[0].get('stroke'),'#aadd00')

    def test_one_logical_shape_groups_compound_fill_and_selective_outlines(self):
        # A filled GP star with an unoutlined hole is one logical shape.
        # SVG needs separate paths for different contour styles, but they
        # must share one named shape group, not appear as disconnected objects.
        def curve(x, color, width):
            return dict(type='POLY', points=[point(x,1),point(x+4,1),point(x+4,5)],
                        cyclic=True, fill_id=9, fill='#fff', fill_opacity=1,
                        stroke=color, stroke_opacity=1, width=width, material_index=0)
        contours=[curve(0,'#ffee00',4),curve(1,'',0),curve(2,'#ffee00',4),curve(3,'#00ff00',2)]
        svg=encode_svg(20,20,[dict(name='ShineSprite',layers=[dict(name='Shine',strokes=contours)])])
        root=ET.fromstring(svg)
        ns='{http://www.w3.org/2000/svg}';ink='{http://www.inkscape.org/namespaces/inkscape}'
        groups=[g for g in root.iter(ns+'g') if g.get('data-handoff-shape') == 'fill-group']
        self.assertEqual(len(groups),1)
        shape=groups[0]
        self.assertEqual(shape.get(ink+'label'),'ShineSprite')
        self.assertEqual(shape.get('data-handoff-fill-id'),'9')
        self.assertEqual(shape.get('data-handoff-contours'),'4')
        paths=shape.findall(ns+'path')
        self.assertEqual(len(paths),3)  # fill + yellow outline + green outline
        self.assertEqual([x.get('data-handoff-role') for x in paths],['fill','outline','outline'])
        self.assertEqual([x.get('stroke') for x in paths],['none','#ffee00','#00ff00'])
        self.assertEqual([x.get('fill') for x in paths],['#fff','none','none'])
        # The fill can still represent the hole by even-odd winding.
        self.assertEqual(paths[0].get('fill-rule'),'evenodd')
        self.assertEqual(paths[0].get('d').count('M '),4)

    def test_uniform_contour_style_remains_one_editable_path_no_shape_group(self):
        pts=[point(0,0),point(6,0),point(6,6)]
        contours=[dict(type='POLY',points=pts,cyclic=True,fill_id=2,
                       fill='#fff',fill_opacity=1,stroke='#dddd00',
                       stroke_opacity=1,width=4,material_index=0) for _ in range(2)]
        root=ET.fromstring(encode_svg(15,15,[dict(name='Sprite',layers=[dict(name='Shine',strokes=contours)])]))
        ns='{http://www.w3.org/2000/svg}'
        self.assertFalse(any(g.get('data-handoff-shape') for g in root.iter(ns+'g')))
        paths=list(root.iter(ns+'path'))
        self.assertEqual(len(paths),1)
        self.assertEqual(paths[0].get('stroke'),'#dddd00')

    def test_subpixel_width_rounding_does_not_split_authored_uniform_outline(self):
        paths=[dict(type='POLY',points=[point(i,1),point(i+2,1),point(i+2,4)],
                    cyclic=True,fill_id=4,fill='#ffffff',fill_opacity=1,
                    stroke='#eeee00',stroke_opacity=1,width=6.0+i*.0001,
                    material_index=0) for i in range(3)]
        markup=encode_svg(20,20,[dict(name='Shine',layers=[dict(name='Shine',strokes=paths)])])
        root=ET.fromstring(markup); ns='{http://www.w3.org/2000/svg}'
        self.assertEqual(len(list(root.iter(ns+'path'))),1)
        paths[2]['width']=6.5
        markup=encode_svg(20,20,[dict(name='Shine',layers=[dict(name='Shine',strokes=paths)])])
        root=ET.fromstring(markup)
        shape=next(g for g in root.iter(ns+'g') if g.get('data-handoff-shape')=='fill-group')
        self.assertEqual(len(shape.findall(ns+'path')),3)

    def test_independent_outlines_join_without_merging_different_paints(self):
        pts=[point(1,1),point(6,1),point(6,6)]
        strokes=[dict(type='POLY',points=pts,cyclic=False,fill_id=0,
                      fill='#ffffff',fill_opacity=0,stroke=color,
                      stroke_opacity=1,width=4,material_index=0)
                 for color in ('#ddee00','#ddee00','#ff00cc','#ff00cc')]
        svg=encode_svg(20,20,[dict(name='Star',layers=[dict(name='Shine',strokes=strokes)])])
        paths=list(ET.fromstring(svg).iter('{http://www.w3.org/2000/svg}path'))
        self.assertEqual(len(paths),2)
        self.assertEqual([p.get('stroke') for p in paths],['#ddee00','#ff00cc'])
        self.assertEqual([p.get('d').count('M ') for p in paths],[2,2])

    def test_stroke_thickness_includes_additive_gp_layer_radius_offset(self):
        from unittest.mock import patch
        from svg_export import _effective_radius
        import types
        self.assertAlmostEqual(_effective_radius(.01,.022),.032)
        self.assertEqual(_effective_radius(.01,-.5),0)
        class Vec(tuple):
            def __new__(cls, coords): return super().__new__(cls, coords)
            def __add__(self, other): return Vec(tuple(a+b for a,b in zip(self,other)))
        class Mat:
            def __matmul__(self, coord): return coord
            def to_3x3(self): return self
        mathutils=types.ModuleType('mathutils'); mathutils.Vector=Vec
        extras=types.ModuleType('bpy_extras'); utils=types.ModuleType('bpy_extras.object_utils')
        utils.world_to_camera_view=lambda scene,camera,p:SimpleNamespace(x=p[0],y=p[1],z=1)
        extras.object_utils=utils
        gpstyle=SimpleNamespace(color=(1,1,0,1),fill_color=(1,1,1,1),fill_style='SOLID',stroke_style='SOLID')
        obj=SimpleNamespace(matrix_world=Mat(),material_slots=[SimpleNamespace(material=SimpleNamespace(grease_pencil=gpstyle))])
        scene=SimpleNamespace(render=SimpleNamespace(resolution_x=100,resolution_y=100,resolution_percentage=100))
        camera=SimpleNamespace(matrix_world=Mat())
        points=[SimpleNamespace(position=(x,y,0),radius=.01,opacity=1,vertex_color=(0,0,0,0))
                for x,y in ((.2,.2),(.3,.2),(.3,.3))]
        gp=SimpleNamespace(curve_type=1,points=points,material_index=0,cyclic=True,
                           fill_id=1,hide_stroke=False,fill_color=(0,0,0,0),fill_opacity=1,
                           softness=0,aspect_ratio=1)
        layer=SimpleNamespace(radius_offset=.022)
        with patch.dict(sys.modules,{'mathutils':mathutils,'bpy_extras':extras,'bpy_extras.object_utils':utils}):
            extracted=_stroke_from_blender(scene,camera,obj,layer,gp)
        self.assertAlmostEqual(extracted['width'],6.4,places=3)
        # Source project objects are parent-scaled. Width follows Blender's
        # model scale; evaluated drawings already contain radius_offset.
        obj.matrix_world.median_scale = .5
        for pt in points:
            pt.opacity = .4
        with patch.dict(sys.modules,{'mathutils':mathutils,'bpy_extras':extras,
                                     'bpy_extras.object_utils':utils}):
            adjusted = _stroke_from_blender(scene,camera,obj,layer,gp)
            baked = _stroke_from_blender(scene,camera,obj,layer,gp,evaluated=True)
        self.assertAlmostEqual(adjusted['width'],3.2,places=3)
        self.assertAlmostEqual(baked['width'],1.0,places=3)
        self.assertAlmostEqual(baked['stroke_opacity'],.4,places=6)

    def test_unsupported_curve_rejected(self):
        with self.assertRaises(VectorFallback):
            svg_path([point(1,1),point(10,10),point(12,4)], 'NURBS', True)

    def test_layered_document_preserves_collection_groups_and_embeds_png(self):
        from PIL import Image
        import base64
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root/'cache';cache.mkdir()
            for i, color in enumerate(((10,20,30,255),(2,6,7,255))):
                Image.new('RGBA',(2,2),color).save(cache/f'psd_L{i:04d}_0001.png')
            svg = cache/'shapes.svg'
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2" viewBox="0 0 2 2"><g><path d="M 0 0 L 1 1"/></g></svg>')
            job = {'format':'SVG', 'dir':str(cache), 'dest':str(root/'Character.svg'), 'depth':8,
                   'extension':'.png', 'overwrite':True, 'tag_profile':'PASSTHROUGH', 'flatten':False,
                   'hierarchy':'GROUPS',
                   'manifest':[{'name':'Shine','slug':'psd_L0000_', 'collection_path':'Headgear/Shine', 'vector_svg':str(svg)},
                               {'name':'Hair','slug':'psd_L0001_', 'collection_path':'Hair', 'vector_svg':''}]}
            assemble(job)
            out = root/'Character.svg'
            self.assertTrue(out.is_file())
            self.assertFalse((root/'CharacterShine.svg').exists())
            self.assertFalse((root/'CharacterHair.png').exists())
            doc = ET.parse(out).getroot()
            ns = {'s':'http://www.w3.org/2000/svg', 'i':'http://www.inkscape.org/namespaces/inkscape'}
            layers = doc.findall('.//s:g', ns)
            labels = [x.attrib.get('{'+ns['i']+'}label') for x in layers]
            self.assertIn('Shine', labels)
            self.assertIn('Hair', labels)
            self.assertTrue(any(x.startswith('Headgear') for x in labels if x))
            paths = doc.findall('.//s:path', ns)
            self.assertEqual(len(paths),1)
            images = doc.findall('.//s:image', ns)
            self.assertEqual(len(images), 1)
            data = images[0].get('href')
            self.assertTrue(data.startswith('data:image/png;base64,'))
            self.assertTrue(base64.b64decode(data.split(',',1)[1]).startswith(b'\x89PNG'))
            # Bottom Hair must precede top Shine in SVG paint order.
            self.assertLess(labels.index('Hair'), labels.index('Shine'))
            job['bake_svg_png'] = True
            assemble(job)
            self.assertEqual(len(ET.parse(out).getroot().findall('.//s:image', ns)), 2)
            self.assertEqual(len(ET.parse(out).getroot().findall('.//s:path', ns)), 0)

    def test_inkscape_group_and_layer_semantics_color_and_image_names(self):
        from PIL import Image
        with TemporaryDirectory() as tmp:
            root=Path(tmp); cache=root/'cache'; cache.mkdir()
            Image.new('RGBA',(3,3),(20,30,40,255)).save(cache/'psd_L0000_0001.png')
            job=dict(format='SVG',dir=str(cache),dest=str(root/'Art.svg'),depth=8,extension='.png',
                     overwrite=True,hierarchy='GROUPS',tag_profile='PASSTHROUGH',
                     manifest=[dict(name='Arms_Upper',slug='psd_L0000_',
                         collection_path='Body/UpperArms',collection_colors=['BLUE','YELLOW'])])
            assemble(job)
            doc=ET.parse(root/'Art.svg').getroot()
            svg='{http://www.w3.org/2000/svg}'
            ink='{http://www.inkscape.org/namespaces/inkscape}'
            groups=[n for n in doc.iter(svg+'g') if n.get(ink+'groupmode') is None]
            layers=[n for n in doc.iter(svg+'g') if n.get(ink+'groupmode')=='layer']
            self.assertTrue(groups)  # Artwork wrapper is an ordinary group.
            self.assertEqual([n.get(ink+'label') for n in layers], ['Body', 'UpperArms'])
            self.assertEqual(layers[0].get(ink+'highlight-color'),'#6598e4')
            self.assertEqual(layers[1].get(ink+'highlight-color'),'#e7d14f')
            self.assertEqual(len(list(doc.iter(svg+'image'))),1)
            self.assertEqual(next(doc.iter(svg+'image')).get(ink+'label'),'Arms_Upper')
            self.assertEqual(len({n.get('id') for n in doc.iter() if n.get('id')}),
                             len([n for n in doc.iter() if n.get('id')]))

    def test_root_group_is_optional_and_preserves_authored_collection(self):
        from PIL import Image
        with TemporaryDirectory() as tmp:
            root=Path(tmp); cache=root/'cache';cache.mkdir()
            Image.new('RGBA',(2,2),(30,80,100,255)).save(cache/'psd_L0000_0001.png')
            job=dict(format='SVG',dir=str(cache),dest=str(root/'Character.svg'),depth=8,
                     extension='.png',overwrite=True,hierarchy='GROUPS',
                     manifest=[dict(name='Art',slug='psd_L0000_',collection_path='Assets')],
                     tag_profile='PASSTHROUGH',svg_root_mode='AUTO')
            assemble(job)
            doc=ET.parse(root/'Character.svg').getroot()
            svg='{http://www.w3.org/2000/svg}'
            ink='{http://www.inkscape.org/namespaces/inkscape}'
            self.assertEqual([n.get(ink+'label') for n in doc.findall(svg+'g')],['Assets'])
            job['svg_root_mode']='NAMED';job['svg_root_name']='Hatshepsut'
            assemble(job)
            doc=ET.parse(root/'Character.svg').getroot()
            self.assertEqual([n.get(ink+'label') for n in doc.findall(svg+'g')],['Hatshepsut'])
            self.assertEqual([n.get(ink+'label') for n in doc.find(svg+'g').findall(svg+'g')],['Assets'])

    def test_bezier_coordinate_handles_are_supported(self):
        from unittest.mock import patch
        import types
        class Vec(tuple):
            def __new__(cls, xyz): return super().__new__(cls, xyz)
            def __add__(self, other): return Vec(tuple(a+b for a,b in zip(self,other)))
        class Mat:
            def __matmul__(self, pt): return pt
            def to_3x3(self): return self
        mathutils=types.ModuleType('mathutils');mathutils.Vector=Vec
        extras=types.ModuleType('bpy_extras');utils=types.ModuleType('bpy_extras.object_utils')
        utils.world_to_camera_view=lambda scene,cam,v:SimpleNamespace(x=v[0],y=v[1],z=1)
        extras.object_utils=utils
        mat=SimpleNamespace(grease_pencil=SimpleNamespace(show_stroke=False,show_fill=True,
            color=(1,1,1,1),fill_color=(1,1,1,1),fill_style='SOLID',stroke_style='SOLID'))
        obj=SimpleNamespace(matrix_world=Mat(),material_slots=[SimpleNamespace(material=mat)])
        cam=SimpleNamespace(matrix_world=Mat())
        scene=SimpleNamespace(render=SimpleNamespace(resolution_x=100,resolution_y=100,resolution_percentage=100))
        pts=[SimpleNamespace(position=(x,y,0),handle_left=(x-.02,y,0),handle_right=(x+.02,y,0),
             radius=.01,opacity=1,vertex_color=(0,0,0,0)) for x,y in ((.2,.2),(.4,.2),(.3,.6))]
        stroke=SimpleNamespace(curve_type=2,points=pts,material_index=0,cyclic=True,fill_id=1,
             hide_stroke=True,fill_color=(0,0,0,0),fill_opacity=1,softness=0,aspect_ratio=1)
        with patch.dict(sys.modules,{'mathutils':mathutils,'bpy_extras':extras,'bpy_extras.object_utils':utils}):
            result=_stroke_from_blender(scene,cam,obj,SimpleNamespace(),stroke)
        self.assertIsNotNone(result['points'][0]['left'])
        self.assertIsNotNone(result['points'][0]['right'])

    def test_combined_vector_ids_are_unique_and_named(self):
        from PIL import Image
        from svg_export import encode_svg
        with TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'cache';cache.mkdir()
            for i in range(2):
                Image.new('RGBA',(3,3),(255,255,255,255)).save(cache/f'psd_L{i:04d}_0001.png')
            stroke=dict(type='POLY', points=[point(0,0),point(2,0),point(2,2)], cyclic=True,
                        fill_id=1,fill='#ffffff',fill_opacity=1,stroke='',width=0)
            svg=encode_svg(3,3,[dict(name='Shine',layers=[dict(name='Shine',strokes=[stroke])])])
            for i in range(2):
                (cache/f'vector{i}.svg').write_text(svg,encoding='utf-8')
            job=dict(format='SVG',dir=str(cache),dest=str(root/'Art.svg'),depth=8,
                     extension='.png',overwrite=True,hierarchy='GROUPS',tag_profile='PASSTHROUGH',
                     manifest=[dict(name='Shine',slug=f'psd_L{i:04d}_',
                                    collection_path=f'FX{i}',vector_svg=str(cache/f'vector{i}.svg')) for i in range(2)])
            assemble(job)
            doc=ET.parse(root/'Art.svg').getroot()
            svg_ns='{http://www.w3.org/2000/svg}'
            ink='{http://www.inkscape.org/namespaces/inkscape}'
            ids=[node.get('id') for node in doc.iter() if node.get('id')]
            self.assertEqual(len(ids),len(set(ids)))
            self.assertEqual(len(list(doc.iter(svg_ns+'path'))),2)
            self.assertTrue(all(node.get(ink+'label') for node in doc.iter(svg_ns+'path')))

    def test_flatten_svg_produces_single_embedded_image(self):
        from PIL import Image
        with TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'cache';cache.mkdir()
            rows=[]
            for i in range(2):
                Image.new('RGBA',(2,2),(80*i,100,255,255)).save(cache/f'psd_L{i:04d}_0001.png')
                rows.append({'name':f'L{i}', 'slug':f'psd_L{i:04d}_', 'collection_path':'Drawing'})
            job=dict(format='SVG',dir=str(cache),dest=str(root/'Flat.svg'),depth=8,extension='.png',overwrite=True,
                     hierarchy='FLAT',flatten=True,manifest=rows,tag_profile='PASSTHROUGH')
            assemble(job)
            ns={'s':'http://www.w3.org/2000/svg'}
            doc=ET.parse(root/'Flat.svg')
            self.assertEqual(len(doc.findall('.//s:image',ns)),1)
            self.assertFalse(doc.findall('.//s:path',ns))

    def test_ungroup_and_ignore_in_one_document(self):
        from PIL import Image
        with TemporaryDirectory() as tmp:
            root=Path(tmp); cache=root/'cache';cache.mkdir()
            entries=[]
            for i, (name, path) in enumerate((('A', 'Out.ungroup/Sub'),('B','Skip.ignore'),('C','Other'))):
                Image.new('RGBA',(2,2),(255,0,0,255)).save(cache/f'psd_L{i:04d}_0001.png')
                entries.append(dict(name=name, collection_path=path,slug=f'psd_L{i:04d}_',vector_svg=''))
            job=dict(format='SVG',dir=str(cache),dest=str(root/'Layered.svg'),depth=8,extension='.png',overwrite=True,
                     hierarchy='GROUPS',manifest=entries,tag_profile='PASSTHROUGH')
            assemble(job)
            doc=ET.parse(root/'Layered.svg')
            ns={'s':'http://www.w3.org/2000/svg','i':'http://www.inkscape.org/namespaces/inkscape'}
            labels=[n.get('{'+ns['i']+'}label') for n in doc.findall('.//s:g',ns)]
            self.assertNotIn('Out',labels)
            self.assertNotIn('B',labels)
            self.assertIn('Sub',labels)
            self.assertIn('A',labels)
            self.assertIn('C',labels)

    def test_retired_psd_svg_copy_is_ignored_and_svg_destination_still_exports(self):
        from PIL import Image
        with TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'cache';cache.mkdir()
            png=cache/'psd_L0000_0001.png'
            Image.new('RGBA',(2,2),(2,6,7,255)).save(png)
            svg=cache/'shape.svg'
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2" viewBox="0 0 2 2"><path d="M0 0 L1 1"/></svg>')
            job={'format':'PSD','dir':str(cache),'dest':str(root/'Art.psd'),'depth':8,'extension':'.png',
                 'overwrite':True,'tag_profile':'PASSTHROUGH','hierarchy':'GROUPS',
                 'manifest':[{'name':'GP','slug':'psd_L0000_', 'collection_path':'FX', 'vector_svg':str(svg)}],
                 'psd_svg_sidecars':False,'save_as_render':True}
            assemble(job)
            self.assertTrue((root/'Art.psd').exists())
            self.assertFalse((root/'Art.svg').exists())
            job['psd_svg_sidecars']=True
            assemble(job)
            self.assertFalse((root/'Art.svg').exists())
            existing='<svg xmlns="http://www.w3.org/2000/svg"><title>Illustrator edits</title></svg>'
            (root/'Art.svg').write_text(existing)
            assemble(job)
            self.assertEqual((root/'Art.svg').read_text(),existing)
            assemble(dict(job,format='SVG',dest=str(root/'Explicit.svg')))
            ns={'s':'http://www.w3.org/2000/svg'}
            self.assertEqual(len(ET.parse(root/'Explicit.svg').findall('.//s:path',ns)), 1)

    def test_merge_group_renders_one_embedded_png(self):
        from PIL import Image
        with TemporaryDirectory() as tmp:
            root=Path(tmp); cache=root/'cache'; cache.mkdir()
            rows=[]
            for i,name in enumerate(('Top', 'Bottom')):
                Image.new('RGBA',(2,2),(i*80,150,20,255)).save(cache/f'psd_L{i:04d}_0001.png')
                rows.append(dict(name=name,collection_path='Snake.merge',slug=f'psd_L{i:04d}_'))
            job=dict(format='SVG',dir=str(cache),dest=str(root/'Merged.svg'),depth=8,extension='.png',overwrite=True,
                     hierarchy='GROUPS',manifest=rows,tag_profile='PASSTHROUGH')
            assemble(job)
            ns={'s':'http://www.w3.org/2000/svg','i':'http://www.inkscape.org/namespaces/inkscape'}
            doc=ET.parse(root/'Merged.svg')
            self.assertEqual(len(doc.findall('.//s:image',ns)),1)
            labels=[n.get('{'+ns['i']+'}label') for n in doc.findall('.//s:g',ns)]
            self.assertIn('Snake', labels)
            self.assertNotIn('Top',labels)
            self.assertNotIn('Bottom',labels)




class GpLightingEligibilityTests(unittest.TestCase):
    """The Blender object and GP-layer lighting flags are independent."""

    @staticmethod
    def fixture(object_lights, layer_lights, modifiers=()):
        from svg_export import export_view_layer_svg
        layer = SimpleNamespace(name='Drawing', hide=False, opacity=1,
                                viewlayer_render='', use_lights=layer_lights,
                                blend_mode='REGULAR', use_masks=False,
                                layer_masks=(),
                                current_frame=lambda: SimpleNamespace(
                                    drawing=SimpleNamespace(strokes=[object()])))
        obj = SimpleNamespace(type='GREASEPENCIL', name='AtlasGP',
                              use_grease_pencil_lights=object_lights,
                              data=SimpleNamespace(root_nodes=[layer]),
                              modifiers=modifiers, shader_effects=[])
        camera = SimpleNamespace(data=SimpleNamespace(type='ORTHO',
                                  dof=SimpleNamespace(use_dof=False)))
        scene = SimpleNamespace(camera=camera, frame_current=1,
                                render=SimpleNamespace(film_transparent=True,
                                                       use_motion_blur=False))
        view = SimpleNamespace(name='Shine', use_grease_pencil=True)
        def as_vector(*args, **kwargs):
            return dict(type='POLY',points=[point(1,1),point(5,1),point(3,5)],
                        cyclic=True,fill_id=1,fill='#ffffff',fill_opacity=1,
                        stroke='',width=0,material_index=0)
        with TemporaryDirectory() as tmp:
            out = Path(tmp)/'atlas.svg'
            from unittest.mock import patch
            with patch('svg_export._camera_visible_objects', return_value=[obj]), \
                 patch('svg_export._is_visible', return_value=True), \
                 patch('vector_artwork._stroke_from_blender', side_effect=as_vector), \
                 patch('svg_export._render_size', return_value=(32,32)):
                ok, reason = export_view_layer_svg(scene,view,out)
            return ok, reason, out.exists()

    def test_unlit_object_allows_svg_with_layer_lights_on(self):
        ok, reason, saved = self.fixture(False, True)
        self.assertTrue(ok, reason)
        self.assertTrue(saved)

    def test_unlit_layer_allows_svg_with_object_lights_on(self):
        ok, reason, saved = self.fixture(True, False)
        self.assertTrue(ok, reason)
        self.assertTrue(saved)

    def test_lit_layer_and_lit_object_report_actionable_reason(self):
        ok, reason, saved = self.fixture(True, True)
        self.assertFalse(ok)
        self.assertFalse(saved)
        self.assertIn('AtlasGP/Drawing', reason)
        self.assertIn('Disable lighting', reason)

    def test_modifier_rejected_by_name(self):
        mod=SimpleNamespace(name='Noise',show_render=True)
        ok, reason, saved = self.fixture(False, False, (mod,))
        self.assertFalse(ok)
        self.assertFalse(saved)
        self.assertIn('AtlasGP',reason)
        self.assertIn('Noise',reason)

if __name__ == '__main__':
    unittest.main()
