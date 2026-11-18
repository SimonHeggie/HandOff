"""Camera-space SVG support for Blender Curve and editable Text objects."""
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from svg_export import (encode_svg, _font_from_blender, _curve_from_blender,
                        export_view_layer_svg, VectorFallback, svg_path, _text_material_rgba)

SVG = '{http://www.w3.org/2000/svg}'
INK = '{http://www.inkscape.org/namespaces/inkscape}'


def p(x, y):
    return NS(co=(x,y,0),handle_left=(x-.1,y,0),handle_right=(x+.1,y,0))


def curve_data(splines=None, **kw):
    data = dict(dimensions='2D',extrude=0,bevel_depth=0,bevel_object=None,
                taper_object=None,bevel_factor_start=0,bevel_factor_end=1,
                fill_rule='EVEN_ODD',splines=splines or [])
    data.update(kw)
    return NS(**data)


def material(rgba=(1,.5,0,1)):
    return NS(material=NS(diffuse_color=rgba))


def font_data(**kw):
    data = dict(body='Live SVG',font=NS(name='LiberationSans-Regular',filepath='//fonts/LiberationSans-Regular.ttf'),
                font_bold=None,font_italic=None,font_bold_italic=None,
                size=2.2,align_x='LEFT',align_y='TOP_BASELINE',
                space_character=1,space_word=1,space_line=1.1,offset_x=0,offset_y=0,
                shear=0,extrude=0,bevel_depth=0,follow_curve=None,overflow='NONE',
                text_boxes=[],body_format=[])
    data.update(kw)
    return NS(**data)


class CurveTextTests(unittest.TestCase):
    def test_text_uses_connected_emission_colour_and_strength_not_display_colour(self):
        color = NS(is_linked=False, default_value=(.2,.4,.8,.1))
        strength = NS(is_linked=False, default_value=2.0)
        shader = NS(bl_idname='ShaderNodeEmission',inputs={'Color':color,'Strength':strength})
        output = NS(bl_idname='ShaderNodeOutputMaterial',is_active_output=True,target='ALL',
                    inputs={'Volume':NS(is_linked=False),'Displacement':NS(is_linked=False),
                            'Surface':NS(is_linked=True,links=[NS(from_node=shader)])})
        mat = NS(node_tree=NS(nodes=[shader,output]),use_nodes=True,diffuse_color=(1,0,0,1))
        self.assertEqual(_text_material_rgba(mat), (.4,.8,1.6,1.0))

    def test_principled_text_needs_explicit_flatten_override_and_keeps_alpha(self):
        shader = NS(bl_idname='ShaderNodeBsdfPrincipled',inputs={
            'Base Color':NS(is_linked=False,default_value=(.1,.2,.3,1)),
            'Alpha':NS(is_linked=False,default_value=.4)})
        output = NS(bl_idname='ShaderNodeOutputMaterial',is_active_output=True,target='ALL',
                    inputs={'Volume':NS(is_linked=False),'Displacement':NS(is_linked=False),
                            'Surface':NS(is_linked=True,links=[NS(from_node=shader)])})
        mat = NS(node_tree=NS(nodes=[shader,output]),use_nodes=True)
        with self.assertRaisesRegex(VectorFallback,'Use Flat Text Colour'):
            _text_material_rgba(mat)
        self.assertEqual(_text_material_rgba(mat,flat_material=True), (.1,.2,.3,.4))
        shader.inputs['Base Color'].is_linked=True
        shader.inputs['Base Color'].links=[NS(from_node=NS(bl_idname='ShaderNodeTexNoise'))]
        with self.assertRaisesRegex(VectorFallback,'texture/procedural'):
            _text_material_rgba(mat,flat_material=True)

    def test_native_curve_bezier_handles_and_compound_hole(self):
        outer = NS(type='BEZIER',use_cyclic_u=True,bezier_points=[p(0,0),p(5,0),p(3,3)],material_index=0)
        inner = NS(type='BEZIER',use_cyclic_u=True,bezier_points=[p(1,1),p(2,1),p(1.5,1.8)],material_index=0)
        obj=NS(type='CURVE',name='Bezier Logo',data=curve_data([outer,inner]),modifiers=[],material_slots=[material()])
        with patch('vector_artwork._camera_projection',side_effect=lambda sc,ca,ob,ly,xyz:(xyz[0]*10,xyz[1]*10)):
            extracted=_curve_from_blender(None,None,obj)
        root=ET.fromstring(encode_svg(256,256,[extracted]))
        paths=list(root.iter(SVG+'path'))
        self.assertEqual(len(paths),1)
        self.assertEqual(paths[0].get('d').count('M '),2)
        self.assertIn('C ',paths[0].get('d'))
        self.assertEqual(paths[0].get('fill-rule'),'evenodd')
        self.assertEqual(paths[0].get(INK+'label'),'Bezier Logo')

    def test_multimaterial_curve_stays_one_object_in_collection_grouping(self):
        from svg_collections import group_svg
        obj=dict(svg_kind='CURVE',name='Two colours',collection_parts=['Authored folder'],
                 splines=[dict(d='M 0 0 L 5 0 L 5 5 Z',fill=color,opacity=1)
                          for color in ('#ff0000','#00ff00')])
        root=ET.fromstring(encode_svg(64,64,[obj]))
        group_svg(root,[obj])
        self.assertEqual(len(root),1)
        self.assertEqual(root[0].get(INK+'label'),'Authored folder')
        self.assertEqual(len(list(root.iter(SVG+'path'))),2)

    def test_curve_fallback_for_unsupported_dimensions_and_modifiers(self):
        spline=NS(type='POLY',use_cyclic_u=True,points=[NS(co=v) for v in
                   ((0,0,0,1),(1,0,0,1),(1,1,0,1))],material_index=0)
        obj=NS(name='A',data=curve_data([spline],dimensions='3D'),modifiers=[],material_slots=[])
        with self.assertRaisesRegex(VectorFallback,'3D Curve'):
            _curve_from_blender(None,None,obj)
        obj.data.dimensions='2D';obj.data.bevel_depth=.5
        with self.assertRaisesRegex(VectorFallback,'bevelled'):
            _curve_from_blender(None,None,obj)
        obj.data.bevel_depth=0
        with patch('vector_artwork._camera_projection',side_effect=lambda sc,ca,ob,ly,xyz:(xyz[0],xyz[1])):
            extracted=_curve_from_blender(None,None,obj)
        self.assertEqual(extracted['splines'][0]['fill'],'#ffffff')

    def test_live_text_preserves_characters_and_style_runs(self):
        text='Hi & <you>\nBold'
        formats=[(False,False,False,False,0)]*len(text)
        formats[-4:]=[(True,False,False,False,0)]*4
        info=dict(svg_kind='FONT',name='Title',body=text,
                  family='Liberation Sans',font_source='LiberationSans-Regular',
                  size=2,align='CENTER',align_y='TOP_BASELINE',
                  fill='#ffffff',opacity=.9,space_character=1.15,
                  space_word=1.1,space_line=1.2,shear=0,offset_x=0,offset_y=0,
                  matrix=(100,0,0,100,50,250),formats=formats,material_colors=[('#ffffff',.9)])
        root=ET.fromstring(encode_svg(500,500,[info]))
        el=next(root.iter(SVG+'text'))
        self.assertEqual(el.get('font-family'),'Liberation Sans')
        self.assertEqual(el.get('font-size'),'2')
        self.assertEqual(el.get('text-anchor'),'middle')
        self.assertEqual(el.get('transform'),'matrix(100 0 0 100 50 250)')
        self.assertEqual(''.join(el.itertext()),text.replace('\n',''))
        self.assertGreaterEqual(len(list(el.iter(SVG+'tspan'))),2)
        self.assertEqual(el.get('data-compio-space-character'),'1.15')
        self.assertTrue(any(t.get('font-weight')=='bold' for t in el.iter(SVG+'tspan')))
        self.assertEqual(el.get('letter-spacing'),'0.15')
        self.assertEqual(el.get(INK+'label'),'Title')

    def test_camera_text_baseline_and_font_data(self):
        obj=NS(type='FONT',name='Headline',data=font_data(body='HELLO',size=1.5),
               material_slots=[material((.5,.2,.1,.75))],modifiers=[])
        with patch('vector_artwork._camera_projection',side_effect=lambda sc,ca,ob,ly,xyz:(100*xyz[0]+70,240-100*xyz[1])):
            info=_font_from_blender(None,None,obj)
        self.assertEqual(info['matrix'],(100,0,0,100,70,240))
        self.assertEqual(info['family'],'Liberation Sans')
        self.assertEqual(info['body'],'HELLO')
        root=ET.fromstring(encode_svg(500,500,[info]))
        el=next(root.iter(SVG+'text'))
        self.assertEqual(el.get('transform'),'matrix(100 0 0 100 70 240)')

    def test_text_fallback_for_extrusion_follow_curve_and_justification(self):
        obj=NS(type='FONT',name='Headline',data=font_data(extrude=.3),
               material_slots=[],modifiers=[])
        with self.assertRaisesRegex(VectorFallback,'Extruded'):
            _font_from_blender(None,None,obj)
        obj.data.extrude=0; obj.data.follow_curve=object()
        with self.assertRaisesRegex(VectorFallback,'following'):
            _font_from_blender(None,None,obj)
        obj.data.follow_curve=None;obj.data.align_x='JUSTIFY'
        with self.assertRaisesRegex(VectorFallback,'Justified'):
            _font_from_blender(None,None,obj)

    def test_mixed_curve_and_live_font_no_grease_pencil_filter_required(self):
        from unittest.mock import patch
        font=NS(type='FONT',name='Title',hide_render=False)
        curve=NS(type='CURVE',name='Logo',hide_render=False)
        camera=NS(data=NS(type='ORTHO',dof=NS(use_dof=False)))
        scene=NS(camera=camera,render=NS(film_transparent=True,use_motion_blur=False,
                    resolution_x=120,resolution_y=80,resolution_percentage=100))
        view=NS(name='Title',use_grease_pencil=False)
        fi=dict(svg_kind='FONT',name='Title',family='sans-serif',font_source='Font',body='Test',
                size=4,fill='#ffffff',opacity=1,matrix=(1,0,0,1,0,20),source=font)
        ci=dict(svg_kind='CURVE',name='Logo',fill_rule='evenodd',
                splines=[dict(d='M 0 0 L 5 0 L 5 5 Z',fill='#ff0000',opacity=1)],source=curve)
        with TemporaryDirectory() as tmp, \
                patch('svg_export._camera_visible_objects',return_value=[curve,font]), \
                patch('svg_export._is_visible',return_value=True), \
                patch('vector_artwork._object_camera_depth',return_value=1), \
                patch('svg_export._font_from_blender',return_value=fi), \
                patch('svg_export._curve_from_blender',return_value=ci):
            path=Path(tmp)/'out.svg'
            ok,msg=export_view_layer_svg(scene,view,path)
            self.assertTrue(ok,msg)
            root=ET.parse(path).getroot()
            self.assertEqual(len(list(root.iter(SVG+'path'))),1)
            self.assertEqual(len(list(root.iter(SVG+'text'))),1)

if __name__ == '__main__':
    unittest.main()

class SVGAssemblerLiveTextTests(unittest.TestCase):
    def test_layered_svg_assembler_keeps_live_text_elements(self):
        from PIL import Image
        from svg_document import write_svg_document
        with TemporaryDirectory() as t:
            directory=Path(t)
            cache=directory/'cache'; cache.mkdir()
            Image.new('RGBA',(100,100),(0,0,0,0)).save(cache/'psd_L0000_0001.png')
            standalone=directory/'Title-source.svg'
            standalone.write_text(encode_svg(100,100,[dict(
                svg_kind='FONT',name='Title',family='sans-serif',font_source='Test Font',
                size=20,body='Hello SVG',fill='#ffffff',opacity=1,
                matrix=(1,0,0,1,10,60))]),encoding='utf-8')
            job=dict(dest=str(directory/'Layered.svg'), depth=8, flatten=False,
                     hierarchy='GROUPS',tag_profile='PASSTHROUGH',bake_svg_png=False)
            entry=dict(name='Title',slug='psd_L0000_',collection_path='Title',
                       vector_svg=str(standalone))
            inputs=[(entry,cache/'psd_L0000_0001.png')]
            write_svg_document(job,inputs,logger=lambda *args:None)
            root=ET.parse(directory/'Layered.svg').getroot()
            text=list(root.iter(SVG+'text'))
            self.assertEqual(len(text),1)
            self.assertEqual(''.join(text[0].itertext()),'Hello SVG')
            self.assertEqual(len(list(root.iter(SVG+'image'))),0)
