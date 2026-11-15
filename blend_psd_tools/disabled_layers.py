"""Explicit disabled-render sources and reuse of previous rendered pixels.

Missing enabled cache files remain errors. Disabled sources reuse only a
matching render cache; exported PSD/SVG documents are never read or merged.
"""

try:
    from .branding import LOG_PREFIX
except ImportError:
    from branding import LOG_PREFIX
import hashlib
import json
import struct
import zlib
import shutil
from pathlib import Path


def source_state(tree, socket, scene, trace):
    sources = trace(tree, socket, default_scene=scene)
    identities, disabled = [], []
    for origin, name in sources:
        layer = origin.view_layers.get(name)
        if layer is None:
            continue
        library = getattr(origin, 'library', None)
        owner = origin.get('_compio_sync_scene_id') or (
            str(getattr(library, 'filepath', '')) + '/' + origin.name)
        identities.append((str(owner), str(layer.get('_compio_view_layer_id') or name)))
        if not layer.use:
            disabled.append(origin.name + '/' + name)
    # Existing sync UUIDs survive View Layer renames. Unsynced sources use
    # their exact scene/layer identity; export itself does not modify them.
    payload = [sorted(identities), socket.node.name, socket.identifier]
    key = hashlib.sha256(json.dumps(payload).encode()).hexdigest() if identities else ''
    return dict(source_identity=key, render_disabled=bool(disabled), disabled_sources=disabled)


def notice(job, text):
    messages = job.setdefault('_notices', [])
    if text not in messages:
        messages.append(text)
        print(f'{LOG_PREFIX} NOTICE:', text, flush=True)


def transparent_cache(path, size, depth):
    """Write lossless zero-alpha PNG8/PNG16 without quantising other layers."""
    width, height = map(int, size)
    if width < 1 or height < 1 or depth not in (8, 16):
        raise ValueError('Invalid disabled-layer PNG dimensions/depth')
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    encoder = zlib.compressobj()
    row = bytes(1 + width * 4 * (depth // 8))
    compressed = b''.join(encoder.compress(row) for _ in range(height)) + encoder.flush()
    data = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, depth, 6, 0, 0, 0))
            + chunk(b'IDAT', compressed) + chunk(b'IEND', b''))
    Path(path).write_bytes(data)


def held_path(job, entry):
    slug = entry['slug']
    if Path(slug).name != slug:
        raise ValueError('Invalid layer cache slug')
    return Path(job['dir']) / ('.compio-held-' + slug + job.get('extension', '.png'))


def _compatible(job, previous):
    if (job.get('node_name') != previous.get('node_name') or
            job.get('extension', '.png') != previous.get('extension', '.png') or
            job.get('cache_kind', 'PNG' + str(job.get('depth', 8))) !=
            previous.get('cache_kind', 'PNG' + str(previous.get('depth', 8))) or
            bool(job.get('save_as_render', True)) != bool(previous.get('save_as_render', True))):
        return False
    if previous.get('source_file') and job.get('source_file'):
        return (previous['source_file'] == job['source_file'] and
                previous.get('source_scene') == job.get('source_scene'))
    # Legacy retained jobs have no project identity. An exact destination
    # match avoids borrowing from another project with similarly named layers.
    return previous.get('dest') == job.get('cache_destination', job.get('dest'))


def _matches(entry, candidate):
    if entry.get('source_identity') and candidate.get('source_identity'):
        return entry['source_identity'] == candidate['source_identity']
    source = entry.get('source_view_layer')
    return bool(source and candidate.get('source_view_layer') == source)


def _fits(path, job, size):
    try:
        if path.suffix.lower() == '.png':
            from pillow_loader import ensure_pillow
            ensure_pillow()
            from PIL import Image
            with Image.open(path) as image:
                dimensions = image.size
                image.verify()
            expected_depth = 16 if job.get('cache_kind') == 'PNG16' or job.get('depth') == 16 else 8
            with path.open('rb') as stream:
                header = stream.read(25)
            return dimensions == tuple(size) and len(header) == 25 and header[24] == expected_depth
        from psd_worker import read_rgba
        pixels = read_rgba(path)
        return (pixels.shape[1], pixels.shape[0]) == tuple(size)
    except (OSError, ValueError, RuntimeError, SyntaxError):
        return False


def last_render(job, entry, size):
    """Return a private retained copy of the newest compatible rendered image.

    Held pixels keep their original mtime, so repeatedly skipping a View Layer
    cannot make its old render appear newer than an actual new render.
    """
    candidates = []
    folder = Path(job['dir'])
    if not entry.get('render_was_disabled', False):
        candidates.extend(folder.glob(entry['slug'] + '*' + job.get('extension', '.png')))
    held = held_path(job, entry)
    if held.is_file():
        candidates.append(held)
    base = Path(job.get('cache_history_root') or folder.parent.parent)
    from job_cache_cleanup import candidate_jobs
    roots = job.get('cache_history_roots') or [base]
    for root in (folder for history in roots for folder in candidate_jobs(history)):
        for index in ('jobs.json', 'jobs-retry.json'):
            try:
                previous_jobs = json.loads((root/index).read_text())['jobs']
            except (OSError, ValueError, KeyError):
                continue
            for previous in previous_jobs:
                if not _compatible(job, previous):
                    continue
                matches = [candidate for candidate in previous.get('manifest', []) if _matches(entry, candidate)]
                if len(matches) != 1:
                    continue
                candidate = matches[0]
                previous_folder = Path(previous['dir'])
                if not previous_folder.resolve().is_relative_to(root.resolve()):
                    continue
                if not candidate.get('render_was_disabled', candidate.get('render_disabled', False)):
                    candidates.extend(previous_folder.glob(candidate['slug'] + '*' + job.get('extension', '.png')))
                old_held = held_path(previous, candidate)
                if old_held.is_file():
                    candidates.append(old_held)
    existing = [path for path in set(candidates) if path.is_file()]
    for path in sorted(existing, key=lambda p: (p.stat().st_mtime_ns, str(p)), reverse=True):
        if not _fits(path, job, size):
            continue
        if path.resolve() != held.resolve():
            shutil.copy2(path, held)
        notice(job, entry['name'] + ': disabled for rendering; using last rendered image (' + str(path) + ')')
        return held
    return None

