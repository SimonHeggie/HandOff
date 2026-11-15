"""Validate real SVG references, paint, transforms and linked master edits."""
import copy
import io
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image
import numpy as np
from svg_export import encode_svg
from svg_instances import SVG, INK, XLINK, KEY, BASIS, SOURCE, _basis, multiply, link_instances


def artwork(name='Original', transform=(1,0,0,1,0,0), family='data', stroke=False, gradient=False):
    a,b,c,d,e,f=transform
    points=[dict(co=(a*x+c*y+e,b*x+d*y+f)) for x,y in [(10,10),(30,10),(30,30),(10,30)]]
    shape=dict(type='POLY',cyclic=True,points=points,fill_id=1,fill='#4080b0',fill_opacity=1,
               stroke='#102030' if stroke else '',stroke_opacity=1,width=2*math_scale(transform),material_index=0)
    if gradient:
        shape['fill_gradient']=dict(kind='RADIAL',matrix=multiply(transform,[20,0,0,20,10,10]),
              interpolation='LINEAR',color_mode='RGB',stops=[dict(position=0,color='#ffffff',opacity=1),dict(position=1,color='#000000',opacity=.3)])
    return dict(name=name,layers=[dict(name='Ink',opacity=.5,blend_mode='REGULAR',strokes=[shape])],
                svg_instance=dict(key=family,config='same-material',basis=_basis([p['co'] for p in points])))


def math_scale(matrix):
    return (matrix[0]**2+matrix[1]**2)**.5


class SVGInstances(unittest.TestCase):
    def test_linked_data_becomes_a_real_clone_with_instance_label(self):
        root=ET.fromstring(encode_svg(160,100,[artwork(),artwork('Copy',(1,0,0,1,60,0))]))
        self.assertEqual(len(list(root.iter(SVG+'use'))),1)
        clone=root.find(SVG+'use');self.assertEqual(clone.get(INK+'label'),'Copy')
        self.assertEqual(clone.get('href'),'#'+root[0].get('id'))
        self.assertEqual(clone.get(XLINK+'href'),clone.get('href'))
        self.assertIsNone(clone.get('opacity'))  # Original's GP opacity applies once.

    def test_identical_independent_data_never_becomes_linked(self):
        root=ET.fromstring(encode_svg(160,100,[artwork(),artwork('Independent',(1,0,0,1,60,0),'other-data')]))
        self.assertFalse(list(root.iter(SVG+'use')))

    def test_rotation_uniform_scale_and_reflection_preserve_strokes(self):
        for matrix in ((0,1,-1,0,80,0),(2,0,0,2,60,0),(-1,0,0,1,100,0)):
            root=ET.fromstring(encode_svg(180,100,[artwork(stroke=True),artwork('Clone',matrix,stroke=True)]))
            self.assertEqual(len(list(root.iter(SVG+'use'))),1)

    def test_anisotropic_fill_and_radial_gradient_can_share(self):
        root=ET.fromstring(encode_svg(180,100,[artwork(gradient=True),artwork('Clone',(2,0,0,.5,60,0),gradient=True)]))
        self.assertEqual(len(list(root.iter(SVG+'use'))),1)
        self.assertEqual(len(list(root.iter(SVG+'radialGradient'))),1)

    def test_differing_paint_geometry_and_width_stay_editable_independent_vectors(self):
        for change in ('paint','geometry','width','config','anisotropic-stroke'):
            original=artwork(stroke=True);other=artwork('Copy',(1,0,0,1,60,0),stroke=True)
            shape=other['layers'][0]['strokes'][0]
            if change=='paint':shape['fill']='#abcdef'
            if change=='geometry':shape['points'][2]['co']=(92,31)
            if change=='width':shape['width']=3
            if change=='config':other['svg_instance']['config']='different-material-binding'
            if change=='anisotropic-stroke':other=artwork('Copy',(2,0,0,.5,60,0),stroke=True)
            root=ET.fromstring(encode_svg(180,100,[original,other]))
            self.assertFalse(list(root.iter(SVG+'use')),change)
            self.assertTrue(list(root.iter(SVG+'path')))

    def test_master_edit_changes_all_references_and_no_ids_collide(self):
        root=ET.fromstring(encode_svg(180,100,[artwork(),artwork('Copy',(1,0,0,1,60,0))]))
        master=root[0];path=master.find(SVG+'path');path.set('fill','#ee1100')
        clone=root.find(SVG+'use');target=next(e for e in root.iter() if e.get('id')==clone.get('href')[1:])
        self.assertEqual(target.find(SVG+'path').get('fill'),'#ee1100')
        ids=[e.get('id') for e in root.iter() if e.get('id')]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(link_instances(root),0)

    def test_cross_source_linking_preserves_existing_clone_references(self):
        first=ET.fromstring(encode_svg(200,120,[artwork(),artwork('A',(1,0,0,1,40,0))]))
        second=ET.fromstring(encode_svg(200,120,[artwork('B',(1,0,0,1,0,50)),artwork('C',(1,0,0,1,40,50))]))
        # Mirror the actual document import's per-source ID prefixes.
        for index,source in enumerate((first,second)):
            ids={e.get('id'):str(index)+'-'+e.get('id') for e in source.iter() if e.get('id')}
            for e in source.iter():
                if e.get('id'):e.set('id',ids[e.get('id')])
                for key in ('href',XLINK+'href'):
                    if e.get(key):e.set(key,'#'+ids[e.get(key)[1:]])
        root=ET.Element(SVG+'svg')
        root.extend(list(first));root.extend(list(second));self.assertEqual(link_instances(root),1)
        ids={e.get('id') for e in root.iter() if e.get('id')}
        for clone in root.iter(SVG+'use'):self.assertIn(clone.get('href')[1:],ids)

    def test_layered_document_import_keeps_clones_ids_and_inherited_colours(self):
        from svg_document import write_svg_document
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);png=folder/'cache.png'
            Image.new('RGBA',(200,120)).save(png)
            inputs=[]
            for i,y in enumerate((0,50)):
                source=folder/(str(i)+'.svg')
                source.write_text(encode_svg(200,120,[artwork('Original',(1,0,0,1,0,y)),
                    artwork('Clone',(1,0,0,1,40,y))]))
                inputs.append((dict(name='View '+str(i),collection_path='Art',
                    collection_colors=['GREEN'],vector_svg=str(source)),png))
            dest=folder/'layered.svg'
            write_svg_document(dict(dest=str(dest),depth=8,hierarchy='GROUPS'),inputs,logger=lambda *args:None)
            root=ET.parse(dest).getroot();ids={e.get('id') for e in root.iter() if e.get('id')}
            clones=list(root.iter(SVG+'use'));self.assertEqual(len(clones),3)
            for clone in clones:
                self.assertIn(clone.get('href')[1:],ids)
                self.assertIn(clone.get(SOURCE),ids)
                self.assertEqual(clone.get(INK+'highlight-color'),'#65b36b')
            for path in root.iter(SVG+'path'):
                self.assertEqual(path.get(INK+'highlight-color'),'#65b36b')


if __name__=='__main__':unittest.main()
