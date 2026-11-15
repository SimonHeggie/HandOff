import unittest
from xml.etree import ElementTree as ET
from svg_metadata import annotate,SVG,INK
from svg_export import encode_svg
from test_svg_instances import artwork

class SourceMetadata(unittest.TestCase):
    def test_readable_ids_stable_source_identity_and_clone_references(self):
        objects=[artwork(),artwork('Copy',(1,0,0,1,60,0))]
        for i,obj in enumerate(objects):obj['source_metadata']=dict(object_id='object-'+str(i),data_id='shared-data',object_name=obj['name'])
        a=ET.fromstring(encode_svg(160,100,objects));b=ET.fromstring(encode_svg(160,100,objects))
        self.assertEqual([n.get('id') for n in a.iter()],[n.get('id') for n in b.iter()])
        clone=next(a.iter(SVG+'use'));ids={n.get('id') for n in a.iter() if n.get('id')}
        self.assertIn(clone.get('href')[1:],ids)
        self.assertEqual(clone.get('data-asset-data-id'),'shared-data')
        self.assertEqual(clone.get('data-asset-object-id'),'object-1')
        self.assertTrue(clone.get('id').startswith('object-copy-'))
        self.assertNotIn('copy-copy',clone.get('id'))
        self.assertTrue(any(i.startswith('object-original-') for i in ids))
        self.assertFalse(any(i.startswith('compio-') for i in ids))
        self.assertFalse(list(a.iter(SVG+'script')))
        self.assertFalse(any(key.startswith('on') for node in a.iter() for key in node.attrib))

    def test_inert_source_index_and_preserved_authored_label(self):
        root=ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg"><g id="old" data-asset-object-id="stable" data-asset-object-name="My Sprite"/></svg>')
        root[0].set(INK+'label','My Sprite')
        annotate(root,manifest=[dict(name='View',source_identity='slot-uuid')])
        self.assertEqual(root[0].get(INK+'label'),'My Sprite')
        metadata=root.find(SVG+'metadata');self.assertIsNotNone(metadata)
        self.assertIn('slot-uuid',ET.tostring(metadata,encoding='unicode'))
