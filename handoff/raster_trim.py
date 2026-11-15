"""Lossless trimming of all-zero RGBA borders in exported PNG assets.

Preserve hidden RGB under transparent pixels, as the PSD raster writer does.
The caller must compensate for the returned left/top offset in its document.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from .raster_bounds import crop_rgba
    from .png16_pixels import read_png16_rgba_bytes, encode_png16_rgba
except ImportError:
    from raster_bounds import crop_rgba
    from png16_pixels import read_png16_rgba_bytes, encode_png16_rgba


def crop_png_bytes(data: bytes):
    """Return (PNG bytes, left, top, width, height), retaining PNG16 samples."""
    with Image.open(io.BytesIO(data)) as img:
        width, height = img.size
        if data[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError('Expected a PNG image')
        is_16bit = data[24] == 16
        if is_16bit:
            pixels = read_png16_rgba_bytes(data)
        else:
            pixels = np.asarray(img.convert('RGBA'))
        clipped, left, top = crop_rgba(pixels)
        cut_height, cut_width = clipped.shape[:2]
        if (left, top, cut_width, cut_height) == (0, 0, width, height):
            return data, 0, 0, width, height
        if is_16bit:
            result = encode_png16_rgba(clipped, source=data)
        else:
            out = io.BytesIO()
            # Crop the original RGBA samples rather than compositing against
            # transparency. Keep a colour profile if the cache has one.
            original = img.convert('RGBA')
            extra = {}
            if img.info.get('icc_profile'):
                extra['icc_profile'] = img.info['icc_profile']
            original.crop((left, top, left + cut_width, top + cut_height)).save(
                out, format='PNG', **extra)
            result = out.getvalue()
        return result, left, top, cut_width, cut_height


def crop_png_file(path):
    """Crop a cache output in place; unchanged PNG data are never re-encoded."""
    source = Path(path)
    original = source.read_bytes()
    result, left, top, width, height = crop_png_bytes(original)
    if result is not original:
        source.write_bytes(result)
    return left, top, width, height
