"""Standalone standard-library regression tests for the bundled XML registry.
Run: python3 compatibility/test_registry.py
"""
from pathlib import Path
import importlib.util
import unittest
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('tag_registry_test',ROOT/'tag_registry.py')
reg=importlib.util.module_from_spec(spec)
spec.loader.exec_module(reg)

class Tags(unittest.TestCase):
    def test_parse_registry(self):
        self.assertEqual(reg.check(),(26,40,111))
    def test_profiles(self):
        self.assertEqual(reg.effective_profile('AUTO','PSD'),'PASSTHROUGH')
        self.assertEqual(reg.effective_profile('AUTO','OCA'),'PASSTHROUGH')
        self.assertEqual(reg.effective_profile('AUTO','PNG'),'PASSTHROUGH')
    def test_ref_to_spine(self):
        a,w=reg.preview('Pose.ref','SPINE','PSD')
        self.assertEqual(a,'Pose [ignore]')
        self.assertTrue(w)
    def test_ref_to_oca(self):
        self.assertEqual(reg.preview('Pose.ref','OCA','PSD')[0],'Pose _reference_')
    def test_oca_to_spine(self):
        self.assertEqual(reg.preview('Pose _reference_','SPINE','PSD')[0],'Pose [ignore]')
    def test_merge_group(self):
        self.assertEqual(reg.translate_label('Hat-A.merge','Hat.merge','SPINE','group')[0], 'Hat-A [merge]')
    def test_merge_layer_not_silently_promoted(self):
        label,notes=reg.preview('Hair.merge','SPINE','PSD','layer')
        self.assertIn('.merge',label)
        self.assertTrue(any('not safe' in s for s in notes))
    def test_unsupported_tag_preserved(self):
        label,notes=reg.preview('Head [bone:skull]','OCA','PSD')
        self.assertEqual(label,'Head [bone:skull]')
        self.assertTrue(any('no safe' in s for s in notes))
    def test_unknown_tag_preserved(self):
        label,notes=reg.preview('Mystery [custom:foo]','SPINE','PSD')
        self.assertIn('[custom:foo]',label)
        self.assertTrue(notes)
    def test_generator_filename(self):
        a,w=reg.preview('50% Logo.png8','GENERATOR','PSD')
        self.assertEqual(a,'50% Logo.png8')
        self.assertFalse(w)
        a,w=reg.preview('50% Logo.png8','SPINE','PSD')
        self.assertEqual(a,'50% Logo.png8')
        self.assertTrue(any('Generator' in s for s in w))
    def test_manual(self):
        self.assertEqual(reg.preview('Pose.ref','PASSTHROUGH','PSD')[0],'Pose.ref')
    def test_blend_no_writable_alias(self):
        self.assertIn('multiply',reg.blend_registry())
        self.assertIn('add',reg.blend_registry())
    def test_all_source_behaviours_resolve(self):
        b,_=reg.registry()
        tags=ET.parse(ROOT/'compatibility'/'tags.xml').getroot()
        for e in tags.findall('./sourceTokens/token'):
            self.assertIn(e.get('behavior'),b)
    def test_direct_target_templates(self):
        for behavior in reg.registry()[0].values():
            self.assertEqual(len(behavior.findall('target')),3)
            for target in behavior.findall('target'):
                self.assertIn(target.get('profile'),('spine','generator','oca'))

if __name__=='__main__': unittest.main(verbosity=2)
