from xml.etree import ElementTree as ET
import unittest
from svg_collections import group_svg, unwrap_raster_groups, consolidate_collections, SVG, INK
import json


class CollectionTests(unittest.TestCase):
    def test_package_helpers_work_without_worker_search_path(self):
        import tempfile,subprocess,sys
        from pathlib import Path
        from shutil import copy2
        with tempfile.TemporaryDirectory() as folder:
            package=Path(folder)/'frontend_fixture';package.mkdir();(package/'__init__.py').write_text('')
            for name in ('svg_collections','svg_document','layer_stack','group_blends','disabled_layers','branding'):
                copy2(Path(__file__).parent/(name+'.py'),package/(name+'.py'))
            code='''import sys
sys.path.insert(0,sys.argv[1])
from frontend_fixture.svg_collections import group_svg,consolidate_collections,SVG,INK
from xml.etree import ElementTree as E
root=E.Element(SVG+'svg');E.SubElement(root,SVG+'path')
group_svg(root,[dict(name='Paint',collection_parts=['Shine'],collection_colors=['NO_COLOR'],inherited_color='NO_COLOR')])
consolidate_collections(root)
assert root[0].get(INK+'highlight-color')=='#ffffff'
assert root[0][0].get(INK+'highlight-color')=='#ffffff'
assert 'layer_stack' not in sys.modules
'''
            result=subprocess.run([sys.executable,'-I','-c',code,folder],cwd=folder,capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def interleaved(self, boxes):
        root=ET.Element(SVG+'svg');objects=[]
        for i,(name,box) in enumerate(zip(('Case A','Case B','Case A'),boxes)):
            el=ET.SubElement(root,SVG+'path',id=str(i))
            if box is not None:el.set('data-compio-bounds',json.dumps(box))
            objects.append(dict(name='Object '+str(i),collection_parts=[name]))
        group_svg(root,objects)
        return root

    def test_disjoint_collection_segments_share_one_authored_folder(self):
        root=self.interleaved(([0,0,10,10],[20,0,30,10],[0,12,10,15]))
        self.assertEqual(consolidate_collections(root),1)
        self.assertEqual([e.get(INK+'label') for e in root],['Case A','Case B'])
        self.assertEqual([e.get('id') for e in root[0]],['0','2'])

    def test_overlap_and_unknown_footprints_keep_paint_order(self):
        for middle in ([5,0,15,10],None):
            root=self.interleaved(([0,0,10,10],middle,[0,12,10,15]))
            self.assertEqual(consolidate_collections(root),0)
            self.assertEqual([e.get('id') for e in root.iter(SVG+'path')],['0','1','2'])

    def test_effect_groups_keep_their_compositing_boundaries(self):
        root=self.interleaved(([0,0,10,10],[20,0,30,10],[0,12,10,15]))
        root[0].set('opacity','.5');root[2].set('opacity','.5')
        self.assertEqual(consolidate_collections(root),0)

    def test_grouping_keeps_exact_paint_order_and_literal_collection_names(self):
        root=ET.Element(SVG+'svg')
        parts=[['Shapes / literal'],['Other'],['Shapes / literal']]
        objects=[]
        for i,path in enumerate(parts):
            ET.SubElement(root,SVG+'text',id=str(i))
            objects.append(dict(name='Text / literal',collection_parts=path))
        group_svg(root,objects)
        self.assertEqual([e.get('id') for e in root.iter(SVG+'text')],['0','1','2'])
        self.assertEqual(len(list(root.iter(SVG+'g'))),3)
        self.assertTrue(any('Shapes / literal' in e.get(INK+'label','') for e in root))

    def test_fallback_image_lives_directly_in_authored_collection(self):
        root=ET.Element(SVG+'svg');group=ET.SubElement(root,SVG+'g',{'id':'raster',INK+'label':'Actual object','data-compio-raster-request':'0'})
        ET.SubElement(group,SVG+'image',href='data:image/png;base64,test')
        group_svg(root,[dict(name='Actual object',collection_parts=['Case'])]);unwrap_raster_groups(root)
        folder=root[0]
        self.assertEqual(folder.get(INK+'label'),'Case')
        self.assertEqual(folder[0].tag,SVG+'image')
        self.assertEqual(folder[0].get(INK+'label'),'Actual object')
