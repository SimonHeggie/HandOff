"""Validate Blender's own session directory before Cycles writes tile buffers."""

try:
    from .branding import LOG_PREFIX
except ImportError:
    from branding import LOG_PREFIX
from pathlib import Path
import tempfile


def ensure_render_tempdir(directory, *, logger=print):
    """Restore a vanished session directory; never remove session directories."""
    if not directory:
        raise RuntimeError('Blender has no session temporary directory; restart Blender')
    path = Path(directory)
    missing = not path.is_dir()
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=path, prefix='compio-write-check-') as probe:
            probe.write(b'write-test')
            probe.flush()
    except OSError as exc:
        raise RuntimeError('Blender cannot write render tile buffers in ' + str(path) + ': ' + str(exc)) from exc
    if missing:
        logger(f'{LOG_PREFIX} Restored missing Blender session temp directory:', str(path))
    return path
