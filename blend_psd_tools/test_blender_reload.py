"""Blender-free regression tests for re-installing Comp-IO in one process."""
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import copy2

ROOT = Path(__file__).resolve().parent


class TestBlenderUpgrade(unittest.TestCase):
    def test_branding_refreshes_when_reenabling_over_an_old_install(self):
        with tempfile.TemporaryDirectory() as temp:
            name='identity_upgrade_fixture';package=Path(temp)/name;package.mkdir()
            (package/'__init__.py').write_text('')
            copy2(ROOT/'branding.py',package/'branding.py');sys.path.insert(0,temp)
            try:
                stale=importlib.import_module(name+'.branding');stale.NAME='Old identity'
                del stale.VERSION_INFO
                source=(ROOT/'__init__.py').read_text()
                begin=source.index('import importlib as _identity_importlib')
                end=source.index('\nimport bpy',begin)
                namespace={'__name__':name,'__package__':name,'bl_info':{}}
                exec(source[begin:end],namespace)
                self.assertEqual(namespace['bl_info']['version'],(0,7,50))
                self.assertEqual(namespace['BRAND_NAME'],'Comp-IO')
            finally:
                sys.path.remove(temp)
                for key in list(sys.modules):
                    if key==name or key.startswith(name+'.'):del sys.modules[key]

    def test_cached_old_layer_stack_reloads_and_preview_works(self):
        # The failure in v0.7.17 arose because Blender retained a v0.7.15
        # layer_stack module with API level 4 but without preview_merge_groups.
        with tempfile.TemporaryDirectory() as temp:
            package_name = 'compio_upgrade_fixture'
            package = Path(temp) / package_name
            package.mkdir()
            (package / '__init__.py').write_text('', encoding='utf-8')
            for filename in ('layer_stack.py', 'group_blends.py', 'collection_colors.py', 'job_cache_cleanup.py', 'runtime_paths.py', 'svg_source.py', 'svg_export.py'):
                copy2(ROOT / filename, package / filename)
            sys.path.insert(0, temp)
            try:
                stale = importlib.import_module(package_name + '.layer_stack')
                stale.STACK_API_VERSION = 4
                del stale.preview_merge_groups

                source = (ROOT / '__init__.py').read_text(encoding='utf-8')
                begin = source.index('import importlib as _stack_importlib')
                end = source.index('\n# Blender can re-enable', begin)
                namespace = {'__name__': package_name,
                             '__package__': package_name}
                exec(source[begin:end], namespace)
                self.assertEqual(namespace['_layer_stack'].STACK_API_VERSION, 8)
                self.assertTrue(callable(namespace['preview_merge_groups']))
                entries = namespace['prepared_entries']([
                    (dict(name='SnakeTail', collection_path='Headgear/SnakeTail.merge'), None)
                ], True)
                tree = namespace['build_stack'](entries)
                namespace['preview_merge_groups'](tree)
                self.assertEqual(tree['children'][0]['name'], 'Headgear-SnakeTail')
                self.assertEqual(tree['children'][0]['children'][0]['kind'], 'layer')
                self.assertEqual(tree['children'][0]['children'][0]['name'], 'SnakeTail')
            finally:
                sys.path.remove(temp)
                for name in list(sys.modules):
                    if name == package_name or name.startswith(package_name + '.'):
                        del sys.modules[name]

    def test_same_api_svg_module_is_reloaded_from_disk(self):
        # Installing a new ZIP should refresh SVG even when the cached module
        # advertises the same API version as the replacement module.
        with tempfile.TemporaryDirectory() as temp:
            package_name = 'compio_svg_upgrade_fixture'
            package = Path(temp) / package_name
            package.mkdir()
            (package / '__init__.py').write_text('', encoding='utf-8')
            for filename in ('layer_stack.py', 'group_blends.py', 'collection_colors.py',
                             'job_cache_cleanup.py', 'runtime_paths.py', 'svg_source.py', 'svg_export.py'):
                copy2(ROOT / filename, package / filename)
            sys.path.insert(0, temp)
            try:
                stale = importlib.import_module(package_name + '.svg_export')
                stale.export_view_layer_svg = lambda *args, **kwargs: (False, 'stale')
                source = (ROOT / '__init__.py').read_text(encoding='utf-8')
                begin = source.index('import importlib as _stack_importlib')
                end = source.index('\n# Blender can re-enable', begin)
                namespace = {'__name__': package_name, '__package__': package_name}
                exec(source[begin:end], namespace)
                refreshed = namespace['_svg_export']
                self.assertEqual(refreshed.SVG_API_VERSION, 17)
                self.assertNotEqual(refreshed.export_view_layer_svg(None, None, '/tmp/none.svg')[1], 'stale')
            finally:
                sys.path.remove(temp)
                for name in list(sys.modules):
                    if name == package_name or name.startswith(package_name + '.'):
                        del sys.modules[name]

    def test_worker_can_use_top_level_layer_stack(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            for filename in ('layer_stack.py', 'group_blends.py', 'collection_colors.py', 'job_cache_cleanup.py', 'runtime_paths.py', 'svg_source.py', 'svg_export.py'):
                copy2(ROOT / filename, path / filename)
            # Standalone worker imports layer_stack as a top-level module.
            sys.path.insert(0, temp)
            previous = {key: sys.modules.pop(key, None)
                        for key in ('layer_stack', 'group_blends')}
            try:
                stack_module = importlib.import_module('layer_stack')
                entries = stack_module.prepared_entries([
                    (dict(name='SnakeTail', collection_path='Headgear/SnakeTail.merge'), None)
                ], True)
                tree = stack_module.build_stack(entries)
                stack_module.preview_merge_groups(tree)
                self.assertEqual(tree['children'][0]['children'][0]['kind'], 'layer')
            finally:
                sys.path.remove(temp)
                for key in previous:
                    sys.modules.pop(key, None)
                    if previous[key] is not None:
                        sys.modules[key] = previous[key]


if __name__ == '__main__':
    unittest.main()
