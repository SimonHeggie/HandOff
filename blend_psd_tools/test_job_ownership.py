import json
from pathlib import Path
import tempfile
import unittest

from job_ownership import create_owned_job, discard_owned_job, remove_completed_snapshots


class OwnershipTests(unittest.TestCase):
    def test_cancel_removes_only_the_matching_owned_job(self):
        with tempfile.TemporaryDirectory() as d:
            project=Path(d)/'project';project.mkdir();keep=project/'scene.blend';keep.write_bytes(b'keep')
            root,token=create_owned_job(d)
            self.assertFalse(discard_owned_job(project,token))
            self.assertFalse(discard_owned_job(root,'wrong'))
            self.assertTrue(discard_owned_job(root,token))
            self.assertEqual(keep.read_bytes(),b'keep')

    def test_completed_snapshot_cleanup_preserves_unmarked_and_external_files(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);v=p/'vectors';v.mkdir();outside=p/'original.blend';outside.write_bytes(b'original')
            snapshot=v/'cache.blend';snapshot.write_bytes(b'cache')
            (v/'cache.blend.compio-owned').write_text(json.dumps(dict(kind='CompIO source snapshot',file='cache.blend')))
            unmarked=v/'user.blend';unmarked.write_bytes(b'user')
            (v/'fake.blend.compio-owned').write_text(json.dumps(dict(kind='CompIO source snapshot',file='../original.blend')))
            self.assertEqual(remove_completed_snapshots(p),1)
            self.assertEqual(outside.read_bytes(),b'original')
            self.assertEqual(unmarked.read_bytes(),b'user')
