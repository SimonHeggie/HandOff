"""Neutral new cache names retain compatibility with existing render jobs."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import runtime_paths as paths
from job_cache_cleanup import candidate_jobs, clear_jobs


class RuntimePaths(unittest.TestCase):
    def test_default_names_are_independent_of_public_brand(self):
        with patch.dict(os.environ,{'XDG_CACHE_HOME':'/tmp/cache'},clear=True):
            self.assertEqual(paths.job_roots(),[paths.cache_root()/'jobs',
                paths.cache_root(name='layered-document-export')/'jobs',paths.cache_root(True)/'jobs'])
            self.assertEqual(paths.pillow_cache(),paths.cache_root())
            self.assertEqual(paths.cache_root().name,'asset-parts')
        self.assertEqual(paths.IMAGE_PREFIX,'layer_')
        self.assertEqual(paths.JOB_PREFIX,'layered_render_')

    def test_new_environment_overrides_take_precedence_and_old_ones_work(self):
        with patch.dict(os.environ,{'BLEND_PSD_TOOLS_CACHE':'/tmp/old-cache',
                                    'BLEND_PSD_TOOLS_JOB_ROOT':'/tmp/old-jobs'},clear=True):
            self.assertEqual(paths.pillow_cache(),Path('/tmp/old-cache'))
            self.assertEqual(paths.job_roots(),[Path('/tmp/old-jobs')])
            with patch.dict(os.environ,{'LAYERED_EXPORT_CACHE':'/tmp/new-cache',
                                       'LAYERED_EXPORT_JOB_ROOT':'/tmp/new-jobs'}):
                self.assertEqual(paths.pillow_cache(),Path('/tmp/new-cache'))
                self.assertEqual(paths.job_roots(),[Path('/tmp/new-jobs')])

    def test_cleanup_accepts_both_job_generations_and_protects_active_jobs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            new=root/(paths.JOB_PREFIX+'new');new.mkdir()
            old=root/'blend_psd_render_old';old.mkdir()
            unrelated=root/'my_artwork';unrelated.mkdir()
            self.assertEqual(set(candidate_jobs(root)),{old,new})
            deleted,skipped,_,_=clear_jobs(root,clear_all=True,active=[new])
            self.assertEqual((deleted,skipped),(1,1))
            self.assertTrue(new.exists() and unrelated.exists())

    def test_both_temporary_node_names_are_recognised(self):
        self.assertTrue(paths.is_temporary_node(paths.TEMP_NODE_PREFIX+'abc'))
        self.assertTrue(paths.is_temporary_node('__blend_psd_TEMP_abc'))
        self.assertFalse(paths.is_temporary_node('Authored Artwork'))
