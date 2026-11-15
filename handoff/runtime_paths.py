"""Stable technical identifiers, independent of public product branding.

Legacy names are read-only compatibility aliases for retained jobs, saved
Blender settings and existing environment overrides. New files use neutral IDs.
"""
import os
import sys
from pathlib import Path

CACHE_ID = 'asset-parts'
LEGACY_CACHE_ID = 'handoff'
PREVIOUS_CACHE_IDS = ('layered-document-export', LEGACY_CACHE_ID)
JOB_PREFIX = 'layered_render_'
JOB_PREFIXES = (JOB_PREFIX, 'blend_psd_render_')
IMAGE_PREFIX = 'layer_'
PRIVATE_PREFIX = '__layered_export_'
TEMP_NODE_PREFIX = PRIVATE_PREFIX + 'TEMP_'
TEMP_NODE_PREFIXES = (TEMP_NODE_PREFIX, '__blend_psd_TEMP_')
TEMP_MARKER = '_layered_export_temporary'
TEMP_MARKERS = (TEMP_MARKER, '_compio_temporary', '_handoff_temporary')
OWNER_MARKER = '.export-job-owner.json'
OWNER_MARKERS = (OWNER_MARKER, '.compio-job-owner.json', '.handoff-job-owner.json')
SNAPSHOT_KIND = 'layered-export-source-snapshot'
SNAPSHOT_KINDS = (SNAPSHOT_KIND, 'CompIO source snapshot', 'HandOff source snapshot')
SNAPSHOT_SUFFIX = '.export-owned'
SNAPSHOT_SUFFIXES = (SNAPSHOT_SUFFIX, '.compio-owned', '.handoff-owned')
WORKER_FILE = 'psd_worker.py'  # Stable Python entry point used by old scripts.


def cache_root(legacy=False, *, name=None):
    name = name or (LEGACY_CACHE_ID if legacy else CACHE_ID)
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home())))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Caches'
    else:
        base = Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache')))
    return base / name


def pillow_cache():
    override = os.environ.get('HANDOFF_CACHE') or os.environ.get('LAYERED_EXPORT_CACHE') or os.environ.get('BLEND_PSD_TOOLS_CACHE')
    return Path(override).expanduser() if override else cache_root()


def job_roots():
    override = os.environ.get('HANDOFF_JOB_ROOT') or os.environ.get('LAYERED_EXPORT_JOB_ROOT') or os.environ.get('BLEND_PSD_TOOLS_JOB_ROOT')
    if override:
        return [Path(override).expanduser()]
    return [cache_root() / 'jobs', *(cache_root(name=name) / 'jobs' for name in PREVIOUS_CACHE_IDS)]


def is_temporary_node(name):
    return str(name).startswith(TEMP_NODE_PREFIXES)
