"""Session temp recovery without touching any other Blender process's files."""
from pathlib import Path
import tempfile
import unittest

from render_temp import ensure_render_tempdir


class RenderTempTests(unittest.TestCase):
    def test_restores_missing_directory_and_preserves_existing_contents(self):
        with tempfile.TemporaryDirectory() as folder:
            session = Path(folder)/'blender_test'
            notes = []
            self.assertEqual(ensure_render_tempdir(session, logger=lambda *a:notes.append(a)), session)
            self.assertEqual(len(notes), 1)
            keep = session/'existing.exr'
            keep.write_bytes(b'existing tile')
            ensure_render_tempdir(session, logger=lambda *a:notes.append(a))
            self.assertEqual(keep.read_bytes(), b'existing tile')
            self.assertEqual(list(session.iterdir()), [keep])
            self.assertEqual(len(notes), 1)

    def test_unusable_path_reports_tile_buffer_problem(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'file'
            path.write_text('keep')
            with self.assertRaisesRegex(RuntimeError, 'tile buffers'):
                ensure_render_tempdir(path)
            self.assertEqual(path.read_text(), 'keep')

    def test_empty_directory_does_not_default_to_working_directory(self):
        with self.assertRaisesRegex(RuntimeError, 'restart Blender'):
            ensure_render_tempdir('')
