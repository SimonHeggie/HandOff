"""Offline Pillow wheel bootstrap for handoff.

Blender classic add-ons do not automatically install wheel dependencies.
Pillow contains native binaries and therefore needs to be extracted,
not just inserted as a .whl in sys.path.
"""
from pathlib import Path
import hashlib
import os
import platform
import sys
import sysconfig
import tempfile
import zipfile
try:
    from .runtime_paths import pillow_cache
except ImportError:
    from runtime_paths import pillow_cache

ROOT = Path(__file__).resolve().parent
WHEELS = ROOT / 'pillow'


def select_wheel(python_tag=None, system=None, machine=None):
    python_tag = python_tag or ('cp%d%d' % sys.version_info[:2])
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    if system == 'windows':
        marker = 'win_arm64' if machine in ('arm64', 'aarch64') else 'win_amd64' if machine in ('amd64', 'x86_64') else None
    elif system == 'linux':
        marker = 'aarch64' if machine in ('aarch64', 'arm64') else 'x86_64' if machine in ('x86_64', 'amd64') else None
    elif system == 'darwin':
        marker = 'arm64' if machine in ('arm64', 'aarch64') else 'x86_64' if machine in ('x86_64', 'amd64') else None
    else:
        marker = None
    if marker is None:
        raise RuntimeError('Unsupported Pillow platform: %s/%s' % (system, machine))
    candidates = []
    for p in WHEELS.glob('*.whl'):
        name = p.name.lower()
        if not name.startswith('pillow-') or ('-' + python_tag + '-' + python_tag + '-') not in name:
            continue
        if system == 'windows' and ('-' + marker + '.whl') in name:
            candidates.append(p)
        elif system == 'linux' and 'manylinux' in name and name.endswith('_' + marker + '.whl'):
            candidates.append(p)
        elif system == 'darwin' and 'macosx' in name and name.endswith('_' + marker + '.whl'):
            candidates.append(p)
    if not candidates:
        # Install archives include every pinned wheel. A source-only ZIP or a
        # second/older Blender add-on installation has no compatible wheel.
        available = sorted(p.name for p in WHEELS.glob('*.whl'))
        reason = ('Pillow wheels not installed' if not available else
                  'No matching Pillow wheel in the installed add-on')
        raise RuntimeError(
            f'{reason} at {WHEELS} (platform: {system}/{machine}; Python {python_tag}). '
            'Install the full HandOff release or test-build ZIP, NOT the GitHub source ZIP; '
            'disable/remove duplicate handoff installations and restart Blender. '
            'Installed wheels: ' + (', '.join(available) if available else '(none)'))
    return sorted(candidates)[-1]


def ensure_pillow():
    """Select/extract Pillow and activate it in current Python process."""
    wheel = select_wheel()
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()[:16]
    # Shared between ordinary Blender and background PSD worker, even if
    # add-on install folders are read-only.
    cache = pillow_cache()
    target = cache / (wheel.stem + '_' + digest)
    ready = target / '.ready'
    if not ready.exists():
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.pillow-staging-', dir=str(cache)) as td:
            stage = Path(td)
            with zipfile.ZipFile(wheel) as z:
                for member in z.infolist():
                    dest = (stage / member.filename).resolve()
                    if not dest.is_relative_to(stage.resolve()):
                        raise RuntimeError('Unsafe path in bundled Pillow wheel: ' + member.filename)
                z.extractall(stage)
            if not (stage / 'PIL' / '__init__.py').exists():
                raise RuntimeError('Pillow wheel lacks PIL package: ' + wheel.name)
            # Races are benign: identical wheel, identical digest.
            try:
                stage.rename(target)
            except FileExistsError:
                pass
            except OSError:
                if not target.exists():
                    raise
        if (target / 'PIL' / '__init__.py').exists():
            ready.touch(exist_ok=True)
    if not (target / 'PIL' / '__init__.py').exists():
        raise RuntimeError('Bundled Pillow extraction failed: ' + str(target))
    if str(target) not in sys.path:
        sys.path.insert(0, str(target))
    # If another Pillow already loaded, report that instance instead of claiming
    # the bundled wheel was imported.
    from PIL import Image
    Image.init()
    return str(target)
