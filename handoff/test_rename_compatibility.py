"""Brand migration must not invalidate existing saved SVGs or sync identifiers."""
import unittest
from xml.etree import ElementTree as ET
from svg_compat import normalize_metadata
from view_layer_sync import _legacy_value, _json

class RenameCompatibility(unittest.TestCase):
    def test_old_svg_attributes_are_read_as_new(self):
        root = ET.fromstring('<svg data-compio-raster-plan="{&quot;id&quot;:1}"><g id="compio-old-id" data-compio-object="Old" /></svg>')
        normalize_metadata(root)
        self.assertIn('data-handoff-raster-plan', root.attrib)
        self.assertNotIn('data-compio-raster-plan', root.attrib)
        self.assertEqual(root[0].get('data-handoff-object'), 'Old')
        self.assertEqual(root[0].get('id'), 'compio-old-id')

    def test_new_metadata_takes_precedence(self):
        root = ET.fromstring('<svg data-compio-object="Old" data-handoff-object="New" />')
        normalize_metadata(root)
        self.assertEqual(root.get('data-handoff-object'), 'New')

    def test_saved_scene_identifiers_survive(self):
        old = {'_compio_sync_scene_id':'stable-id', '_compio_view_layer_sync':'{ "old": true }'}
        self.assertEqual(_legacy_value(old,'_handoff_sync_scene_id'),'stable-id')
        self.assertEqual(_json(old,'_handoff_view_layer_sync',{}),{'old':True})
        old['_handoff_sync_scene_id']='new-id'
        self.assertEqual(_legacy_value(old,'_handoff_sync_scene_id'),'new-id')

if __name__ == '__main__':
    unittest.main()
