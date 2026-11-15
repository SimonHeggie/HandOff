"""Offline platform-wheel selection and actionable failure diagnostics."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pillow_loader


class PillowLoaderTests(unittest.TestCase):
    def test_select_linux_cp313_matches_multi_platform_tag(self):
        with tempfile.TemporaryDirectory() as folder:
            wheel=Path(folder)/'pillow-12.0.0-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl'
            wheel.touch()
            with patch.object(pillow_loader,'WHEELS',Path(folder)):
                self.assertEqual(pillow_loader.select_wheel(python_tag='cp313', system='Linux', machine='x86_64'),wheel)

    def test_select_other_platform_wheels(self):
        cases=[('Linux','aarch64','manylinux_2_27_aarch64.manylinux_2_28_aarch64'),
               ('Windows','AMD64','win_amd64'),('Windows','ARM64','win_arm64'),
               ('Darwin','x86_64','macosx_10_13_x86_64'),
               ('Darwin','arm64','macosx_11_0_arm64')]
        with tempfile.TemporaryDirectory() as folder:
            for system,machine,tag in cases:
                (Path(folder)/f'pillow-12.0.0-cp313-cp313-{tag}.whl').touch()
            with patch.object(pillow_loader,'WHEELS',Path(folder)):
                for system,machine,tag in cases:
                    with self.subTest(system=system,machine=machine):
                        wheel=pillow_loader.select_wheel(python_tag='cp313',system=system,machine=machine)
                        self.assertIn(tag,wheel.name)

    def test_missing_wheels_report_actual_install_location(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(pillow_loader,'WHEELS',Path(folder)):
                with self.assertRaisesRegex(RuntimeError,'Pillow wheels not installed') as caught:
                    pillow_loader.select_wheel(python_tag='cp313',system='Linux',machine='x86_64')
                message=str(caught.exception)
                self.assertIn(str(folder),message)
                self.assertIn('release',message)
                self.assertIn('(none)',message)

if __name__=='__main__':unittest.main()
