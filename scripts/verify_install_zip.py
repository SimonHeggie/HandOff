#!/usr/bin/env python3
"""Validate a released Blender add-on ZIP from a clean installation.

This intentionally tests the installed layout, not the developer's source tree.
The Blender-free check does not replace running the add-on inside Blender.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'docs/pillow-wheels.json'


def verify(path: Path) -> None:
    expected = json.loads(MANIFEST.read_text(encoding='utf-8'))
    expected_names = {'handoff/pillow/' + row['filename'] for row in expected}
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Install ZIP integrity check failed')
        names = set(archive.namelist())
        for required in ('handoff/__init__.py', 'handoff/pillow_loader.py', 'handoff/runtime_paths.py'):
            if required not in names:
                raise RuntimeError(f'Missing add-on file: {required}')
        supplied = {n for n in names if n.startswith('handoff/pillow/') and n.endswith('.whl')}
        if supplied != expected_names:
            raise RuntimeError(f'Pillow wheel set differs from manifest: missing={expected_names-supplied} extra={supplied-expected_names}')
        for row in expected:
            binary = archive.read('handoff/pillow/' + row['filename'])
            if len(binary) != row['bytes'] or hashlib.sha256(binary).hexdigest() != row['sha256']:
                raise RuntimeError(f'Pillow wheel failed integrity check: {row["filename"]}')
        if any('/__pycache__/' in n or n.endswith('.pyc') for n in names):
            raise RuntimeError('Generated Python bytecode should not ship in installation ZIP')
        with tempfile.TemporaryDirectory(prefix='handoff-install-test-') as folder:
            base = Path(folder)
            archive.extractall(base)
            addon = base / 'handoff'
            code = '''import sys
import pillow_loader
w=pillow_loader.select_wheel(python_tag='cp313',system='Linux',machine='x86_64')
assert w.exists() and 'x86_64' in w.name
if sys.platform.startswith('linux') and sys.version_info[:2] == (3,13):
    pillow_loader.ensure_pillow()
    from PIL import Image
    assert Image.__version__.startswith('12.')
print('Clean-install Pillow smoke test passed:',w.name)
'''
            env = dict(os.environ, PYTHONPATH=str(addon), HANDOFF_CACHE=str(base / 'cache'))
            result = subprocess.run([sys.executable, '-c', code], env=env,
                                    text=True, capture_output=True, timeout=60)
            if result.returncode:
                raise RuntimeError('Clean installation Pillow loader failed:\n' + result.stdout + '\n' + result.stderr)
            print(result.stdout.strip())
    print(f'Install ZIP verified: {path} ({path.stat().st_size:,} bytes; {len(expected)} pinned wheels)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    verify(parser.parse_args().archive)
