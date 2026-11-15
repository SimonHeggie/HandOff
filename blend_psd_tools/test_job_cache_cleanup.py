"""Blender-free regression tests for safe retained-job cleanup."""
import tempfile
import unittest
from pathlib import Path
from job_cache_cleanup import candidate_jobs, clear_jobs


class TestJobCacheCleanup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'jobs'
        self.root.mkdir()

    def job(self, name):
        directory = self.root / name
        directory.mkdir()
        (directory / 'jobs.json').write_text('{}')
        (directory / 'layer.png').write_bytes(b'cache')
        return directory

    def test_default_keeps_current_and_removes_older_jobs(self):
        old = self.job('blend_psd_render_old')
        current = self.job('blend_psd_render_current')
        active = self.job('blend_psd_render_active')
        other = self.root / 'probes'
        other.mkdir()
        deleted, skipped, size, names = clear_jobs(
            self.root, current, clear_all=False, active=[active])
        self.assertEqual(deleted, 1)
        self.assertEqual(skipped, 1)
        self.assertIn(old.name, names)
        self.assertGreaterEqual(size, 5)
        self.assertFalse(old.exists())
        self.assertTrue(current.exists())
        self.assertTrue(active.exists())
        self.assertTrue(other.exists())

    def test_clear_all_includes_current_but_not_active(self):
        current = self.job('blend_psd_render_current')
        active = self.job('blend_psd_render_active')
        deleted, skipped, *_ = clear_jobs(
            self.root, current, clear_all=True, active=[active])
        self.assertEqual((deleted, skipped), (1, 1))
        self.assertFalse(current.exists())
        self.assertTrue(active.exists())

    def test_never_deletes_outside_root_or_symlink(self):
        outside = Path(self.temp.name) / 'important'
        outside.mkdir()
        (outside / 'keep').write_text('DO NOT DELETE')
        (self.root / 'blend_psd_render_link').symlink_to(outside, target_is_directory=True)
        self.job('blend_psd_render_valid')
        self.assertEqual(len(candidate_jobs(self.root)), 1)
        deleted, *_ = clear_jobs(self.root, clear_all=True)
        self.assertEqual(deleted, 1)
        self.assertEqual((outside / 'keep').read_text(), 'DO NOT DELETE')

    def test_does_not_touch_other_cache_directories(self):
        (self.root / 'probes').mkdir()
        (self.root / 'unrelated').mkdir()
        (self.root / 'probes' / 'debug.json').write_text('keep')
        self.assertEqual(clear_jobs(self.root, clear_all=True)[0], 0)
        self.assertTrue((self.root / 'probes' / 'debug.json').is_file())


if __name__ == '__main__':
    unittest.main()
