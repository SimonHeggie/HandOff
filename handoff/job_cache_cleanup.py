"""Conservative cleanup of retained render jobs.

Only direct children using recognised new or legacy job prefixes
are candidates. No project files, destination images or external retry folders
are considered for deletion.
"""
from pathlib import Path
import shutil
try:
    from .runtime_paths import JOB_PREFIX, JOB_PREFIXES
except ImportError:
    from runtime_paths import JOB_PREFIX, JOB_PREFIXES


def _canonical(path):
    return Path(path).expanduser().resolve(strict=False)


def candidate_jobs(root):
    root = _canonical(root)
    if not root.is_dir():
        return []
    result = []
    for entry in root.iterdir():
        if (entry.name.startswith(JOB_PREFIXES) and entry.is_dir() and
                not entry.is_symlink() and _canonical(entry).parent == root):
            result.append(entry)
    return sorted(result, key=lambda p: p.name)


def clear_jobs(root, current=None, clear_all=False, active=()):
    """Delete unused job directories; never delete the active worker's job.

    Default protects `current`. `clear_all=True` includes `current`, after
    the explicit UI checkbox. An active background worker is always protected.
    Returns (deleted_count, skipped_active_count, freed_bytes, deleted_paths).
    """
    base = _canonical(root)
    current_path = _canonical(current) if current else None
    active_paths = {_canonical(p) for p in active if p}
    removed, skipped_active, byte_count, names = 0, 0, 0, []
    for entry in candidate_jobs(base):
        resolved = _canonical(entry)
        if resolved in active_paths:
            skipped_active += 1
            continue
        if not clear_all and current_path == resolved:
            continue
        # Check the boundary again immediately before the destructive operation.
        if entry.is_symlink() or resolved.parent != base:
            continue
        # Do not count paths outside the cleanup scope, even if linked inside it.
        for path in entry.rglob('*'):
            try:
                if path.is_file() and not path.is_symlink():
                    byte_count += path.stat().st_size
            except OSError:
                pass
        shutil.rmtree(entry)
        names.append(entry.name)
        removed += 1
    return removed, skipped_active, byte_count, names
