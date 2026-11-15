"""Ensure an invisible raster fallback carries actionable source diagnostics."""
import unittest
from svg_document import empty_raster_diagnostic


class MissingRenderedPixels(unittest.TestCase):
    def test_source_and_vector_reason_are_retained(self):
        msg = empty_raster_diagnostic('Shine', {
            'source_view_layer': 'Shine',
            'vector_reason': 'Grease Pencil modifiers require PNG',
        })
        self.assertIn('SVG EMPTY RASTER: Shine', msg)
        self.assertIn('View Layer: Shine', msg)
        self.assertIn('modifiers require PNG', msg)
        self.assertIn('Depth pass', msg)
        self.assertIn('new Blender render', msg)
        self.assertIn('Fill/Stroke Holdout', msg)
        self.assertIn('Holdout erases', msg)
        self.assertIn('Color Ramp stop alpha', msg)

    def test_legacy_job_without_reason(self):
        msg = empty_raster_diagnostic('Test', {})
        self.assertIn('zero alpha', msg)
        self.assertNotIn('Vector fallback reason:', msg)


if __name__ == '__main__':
    unittest.main()
