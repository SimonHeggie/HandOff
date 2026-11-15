#!/usr/bin/env python3
"""Build the installable Blender add-on ZIP from sources plus pinned Pillow wheels."""
from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'handoff'
WHEEL_MANIFEST = ROOT / 'docs' / 'pillow-wheels.json'


def build(wheel_dir: Path, output: Path) -> None:
    wheel_files = json.loads(WHEEL_MANIFEST.read_text(encoding='utf-8'))
    for row in wheel_files:
        wheel = wheel_dir / row['filename']
        if not wheel.is_file():
            raise FileNotFoundError(f'Missing wheel: {wheel}')
        data = wheel.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError(f'Wheel checksum does not match manifest: {wheel}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(ADDON.rglob('*')):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            parts = rel.parts
            if any(p in ('__pycache__', '.backups', 'development') for p in parts):
                continue
            if path.name.startswith('test_') or path.suffix in ('.pyc', '.pyo', '.whl'):
                continue
            archive.write(path, rel.as_posix())
        for row in wheel_files:
            path = wheel_dir / row['filename']
            archive.write(path, 'handoff/pillow/' + path.name)
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheels-from', required=True, type=Path)
    parser.add_argument('--output', default=ROOT / 'dist' / 'HandOff_install.zip', type=Path)
    opts = parser.parse_args()
    build(opts.wheels_from, opts.output)
