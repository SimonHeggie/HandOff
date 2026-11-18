"""OCA-only high-precision alpha crop, premultiplied resampling and padding."""
import math
import struct
import zlib
from pathlib import Path
import numpy as np


def dimensions(width, height, percent):
    factor = percent / 100.0
    return max(1, math.floor(width * factor + .5)), max(1, math.floor(height * factor + .5))


def load(path, depth):
    path = Path(path)
    if path.suffix.lower() == '.exr':
        from psd_worker import read_blender_pixels
        data = read_blender_pixels(path)
        alpha = data[..., 3:4]
        np.divide(data[..., :3], alpha, out=data[..., :3], where=alpha != 0)
        data[..., :3] = np.where(alpha != 0, data[..., :3], 0)
        return data
    if depth == 16:
        from png16_pixels import read_png16_rgba
        return read_png16_rgba(path)
    from PIL import Image
    with Image.open(path) as image:
        return np.asarray(image.convert('RGBA'), np.float32) / 255.0


def resize(rgba, width, height):
    """Float32, centre-aligned bilinear resize in associated-alpha space.

    No conversion to 8-bit; transparent RGB cannot bleed into visible edges.
    """
    h, w = rgba.shape[:2]
    if (w, h) == (width, height): return rgba
    associated = rgba.copy()
    associated[..., :3] *= associated[..., 3:4]
    xs = np.clip((np.arange(width) + .5) * w / width - .5, 0, w-1)
    ys = np.clip((np.arange(height) + .5) * h / height - .5, 0, h-1)
    x0, y0 = xs.astype(int), ys.astype(int)
    x1, y1 = np.minimum(x0+1, w-1), np.minimum(y0+1, h-1)
    fx = (xs-x0).astype(np.float32)[None, :, None]
    result = np.empty((height, width, 4), np.float32)
    for y in range(height):
        fy = np.float32(ys[y]-y0[y])
        top = associated[y0[y], x0]*(1-fx[0]) + associated[y0[y], x1]*fx[0]
        bottom = associated[y1[y], x0]*(1-fx[0]) + associated[y1[y], x1]*fx[0]
        result[y] = top*(1-fy) + bottom*fy
    np.divide(result[..., :3], result[..., 3:4], out=result[..., :3], where=result[..., 3:4] != 0)
    result[..., :3] = np.where(result[..., 3:4] != 0, result[..., :3], 0)
    return result


def process(rgba, settings):
    height, width = rgba.shape[:2]
    left = top = 0
    if settings['trimWhitespace']:
        occupied = rgba[..., 3] != 0
        ys, xs = np.flatnonzero(occupied.any(axis=1)), np.flatnonzero(occupied.any(axis=0))
        if not len(xs): return None, (0.0, 0.0)
        left, right, top, bottom = int(xs[0]), int(xs[-1])+1, int(ys[0]), int(ys[-1])+1
        rgba = rgba[top:bottom, left:right]
        height, width = rgba.shape[:2]
    factor = settings['scale']/100.0
    centre = ((left+width/2)*factor, (top+height/2)*factor)
    scaled = dimensions(width, height, settings['scale'])
    result = resize(rgba, *scaled)
    padding = settings['padding']
    if padding: result = np.pad(result, ((padding,padding),(padding,padding),(0,0)))
    return result, centre


def colour_chunks(source):
    if not source or Path(source).suffix.lower() != '.png': return
    data = Path(source).read_bytes(); offset = 8
    while offset+12 <= len(data):
        size = int.from_bytes(data[offset:offset+4], 'big'); tag = data[offset+4:offset+8]
        if tag in (b'iCCP', b'sRGB', b'gAMA', b'cHRM'):
            yield tag, data[offset+8:offset+8+size]
        offset += size+12
        if tag == b'IDAT': break


def png16(rgba, source=None):
    """Encode native unsigned 16-bit samples and preserve source colour chunks."""
    h, w = rgba.shape[:2]
    def chunk(tag, payload):
        return struct.pack('>I', len(payload))+tag+payload+struct.pack('>I', zlib.crc32(tag+payload)&0xffffffff)
    output = bytearray(b'\x89PNG\r\n\x1a\n')
    output += chunk(b'IHDR', struct.pack('>IIBBBBB', w,h,16,6,0,0,0))
    for tag, payload in colour_chunks(source): output += chunk(tag, payload)
    values = np.rint(np.clip(rgba,0,1)*65535).astype('>u2')
    compressor=zlib.compressobj();parts=[]
    for row in values: parts.append(compressor.compress(b'\0'+row.tobytes()))
    parts.append(compressor.flush());output += chunk(b'IDAT',b''.join(parts))+chunk(b'IEND',b'')
    return bytes(output)


def save(path, rgba, depth, source=None, *, half_float=False):
    if depth == 32:
        from psd_worker import write_blender_image
        write_blender_image(Path(path),rgba,16 if half_float else 32,fmt='EXR')
    elif depth == 16:
        Path(path).write_bytes(png16(rgba, source))
    else:
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo
        profile={}
        info=PngInfo()
        for tag, payload in colour_chunks(source):
            if tag != b'iCCP': info.add(tag, payload)
        if source and Path(source).suffix.lower()=='.png':
            with Image.open(source) as original:
                if original.info.get('icc_profile'): profile['icc_profile']=original.info['icc_profile']
        Image.fromarray(np.rint(np.clip(rgba,0,1)*255).astype(np.uint8),'RGBA').save(path,pnginfo=info,**profile)
