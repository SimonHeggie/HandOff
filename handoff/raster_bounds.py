"""Conservative raster bounds: preserve nonzero RGB even under zero alpha."""
import numpy as np


def crop_rgba(pixels):
    # Any occupied sample on each outer edge proves the full bounds. This
    # common Blender case avoids scanning/allocating a full-canvas mask for
    # renders with nonzero colour underneath transparent pixels.
    if (np.any(pixels[0] != 0) and np.any(pixels[-1] != 0) and
            np.any(pixels[:, 0] != 0) and np.any(pixels[:, -1] != 0)):
        return pixels, 0, 0
    occupied = np.any(pixels != 0, axis=2)
    rows = np.flatnonzero(np.any(occupied, axis=1))
    columns = np.flatnonzero(np.any(occupied, axis=0))
    if not len(rows):
        return pixels[:1, :1], 0, 0
    top, bottom = int(rows[0]), int(rows[-1]) + 1
    left, right = int(columns[0]), int(columns[-1]) + 1
    return pixels[top:bottom, left:right], left, top
