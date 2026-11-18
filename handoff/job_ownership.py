"""Automatic cleanup is restricted to a folder created by this operation."""
import json
from pathlib import Path
import shutil
import tempfile
import uuid
try:
    from .runtime_paths import JOB_PREFIX, JOB_PREFIXES, OWNER_MARKER, OWNER_MARKERS, SNAPSHOT_KINDS, SNAPSHOT_SUFFIXES
except ImportError:
    from runtime_paths import JOB_PREFIX, JOB_PREFIXES, OWNER_MARKER, OWNER_MARKERS, SNAPSHOT_KINDS, SNAPSHOT_SUFFIXES

MARKER = OWNER_MARKER


def create_owned_job(base):
    root = Path(tempfile.mkdtemp(prefix=JOB_PREFIX, dir=base))
    token = uuid.uuid4().hex
    (root/MARKER).write_text(json.dumps(dict(token=token, name=root.name)))
    return root, token


def discard_owned_job(root, token):
    if not root or not token:
        return False
    root = Path(root)
    if root.is_symlink() or not root.name.startswith(JOB_PREFIXES):
        return False
    try:
        marker = next((root/name for name in OWNER_MARKERS if (root/name).is_file()), root/MARKER)
        data = json.loads(marker.read_text())
    except (OSError, ValueError):
        return False
    if data != dict(token=token, name=root.name):
        return False
    shutil.rmtree(root)
    return True


def remove_completed_snapshots(root):
    """Remove only marked cache snapshots no longer needed by source plans."""
    import xml.etree.ElementTree as ET
    folder = Path(root)/'vectors'
    if not folder.is_dir() or folder.is_symlink():
        return 0
    needed = set()
    for source in folder.glob('*.svg'):
        try:
            el = ET.parse(source).getroot()
            for key in ('data-compio-source-plan','data-compio-raster-plan'):
                if el.get(key):
                    needed.add(Path(json.loads(el.get(key))['snapshot']).resolve())
        except (OSError, ValueError, ET.ParseError):
            return 0
    removed = 0
    markers = [p for suffix in SNAPSHOT_SUFFIXES for p in folder.glob('*.blend' + suffix)]
    for marker in markers:
        if marker.is_symlink():
            continue
        try:
            record = json.loads(marker.read_text())
            target = folder/record['file']
            if (record.get('kind') not in SNAPSHOT_KINDS or
                    target.suffix != '.blend' or target.is_symlink() or
                    target.resolve().parent != folder.resolve() or
                    marker.name not in tuple(target.name + suffix for suffix in SNAPSHOT_SUFFIXES) or target.resolve() in needed):
                continue
            target.unlink(missing_ok=True); marker.unlink(); removed += 1
        except (OSError, KeyError, ValueError):
            continue
    return removed
