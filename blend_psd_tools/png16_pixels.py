"""Read native 16-bit RGB(A) PNG sample values without a colour transform.

Blender's image.pixels API exposes scene-linear float values for many PNGs.
This reader preserves the display-encoded 16-bit file samples as-is, so a PSD
with an embedded display profile contains the same pixel channels as the PNG.
Only the RGB/RGBA, non-interlaced PNG16 cache written by Comp-IO is supported.
"""
import struct
import zlib
from pathlib import Path


def read_png16_rgba(path):
    import numpy as np
    data = Path(path).read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('PNG16 reader: invalid PNG signature')
    offset = 8
    chunks = []
    width = height = channels = None
    while offset + 12 <= len(data):
        size = struct.unpack_from('>I', data, offset)[0]
        tag = data[offset+4:offset+8]
        if offset + 12 + size > len(data):
            raise ValueError('PNG16 reader: truncated chunk')
        payload = memoryview(data)[offset+8:offset+8+size]
        offset += 12 + size
        if tag == b'IHDR':
            if size != 13:
                raise ValueError('PNG16 reader: invalid IHDR')
            width, height, depth, ctype, compression, filtering, interlace = struct.unpack('>IIBBBBB', payload)
            if (depth, ctype, compression, filtering, interlace) not in ((16, 2, 0, 0, 0), (16, 6, 0, 0, 0)):
                raise ValueError('PNG16 reader: expected non-interlaced 16-bit RGB or RGBA')
            channels = 4 if ctype == 6 else 3
            if width < 1 or height < 1 or width*height > 250_000_000:
                raise ValueError('PNG16 reader: invalid dimensions')
        elif tag == b'IDAT':
            chunks.append(bytes(payload))
        elif tag == b'IEND':
            break
    if not width or not chunks:
        raise ValueError('PNG16 reader: missing image data')
    stride = width * channels * 2
    scanlines = zlib.decompress(b''.join(chunks))
    if len(scanlines) != (stride+1)*height:
        raise ValueError('PNG16 reader: inconsistent decompressed size')
    decoded = np.empty((height, stride), dtype=np.uint8)
    previous = np.zeros(stride, np.uint8)
    bpp = channels*2
    view = memoryview(scanlines)
    for y in range(height):
        base = y * (stride+1)
        mode = view[base]
        encoded = np.frombuffer(view[base+1:base+1+stride], dtype=np.uint8)
        if mode == 0:
            row = encoded
        elif mode == 1:
            row = (np.cumsum(encoded.reshape(-1, bpp), axis=0, dtype=np.uint32)&255).astype(np.uint8).reshape(-1)
        elif mode == 2:
            row = (encoded.astype(np.uint16)+previous.astype(np.uint16)).astype(np.uint8)
        elif mode in (3, 4):
            # bytearray indexing is substantially faster than Python loops
            # assigning one NumPy scalar per PNG byte.
            row = bytearray(stride)
            prior = previous.tobytes()
            raw_bytes = view[base+1:base+1+stride]
            if mode == 3:
                for x, val in enumerate(raw_bytes):
                    left = row[x-bpp] if x >= bpp else 0
                    row[x] = (val + ((left + prior[x])//2)) & 255
            else:
                for x, val in enumerate(raw_bytes):
                    a = row[x-bpp] if x >= bpp else 0
                    b = prior[x]
                    c = prior[x-bpp] if x >= bpp else 0
                    predictor = a+b-c
                    da, db, dc = abs(predictor-a), abs(predictor-b), abs(predictor-c)
                    predictor = a if da <= db and da <= dc else b if db <= dc else c
                    row[x] = (val + predictor) & 255
            row = np.frombuffer(row, dtype=np.uint8)
        else:
            raise ValueError(f'PNG16 reader: unsupported filter {mode}')
        decoded[y] = row
        previous = decoded[y]
    # PNG samples are big-endian; NumPy's >u2 decodes without quantisation.
    pixels = np.frombuffer(decoded.tobytes(), dtype='>u2').reshape(height, width, channels)
    out = pixels.astype(np.float32) / 65535.0
    if channels == 3:
        out = np.concatenate((out, np.ones((height,width,1), dtype=np.float32)), axis=2)
    return out
