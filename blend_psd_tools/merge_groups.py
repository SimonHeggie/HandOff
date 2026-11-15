"""Rasterise authored .merge Collection groups using their cached artwork.

This module only operates on the export tree. Blender data stays unchanged.
All intermediate pixels are straight-alpha float32 in the source colour space.
"""

try:
    from .branding import LOG_PREFIX
except ImportError:
    from branding import LOG_PREFIX
import numpy as np

from layer_stack import tags, strip_tags
from group_blends import canonical_mode, promoted_blend, effective_layer_mode


def over(back, front, mode):
    """Straight-alpha compositing in float for a supported paint blend mode."""
    mode = canonical_mode(mode)
    a = np.clip(front[..., 3:4], 0, 1)
    b = np.clip(back[..., 3:4], 0, 1)
    f = front[..., :3]
    d = back[..., :3]
    if mode == 'normal':
        blend = f
    elif mode == 'multiply':
        blend = f * d
    elif mode == 'add':
        blend = f + d
    elif mode == 'screen':
        blend = 1 - (1 - f) * (1 - d)
    elif mode == 'overlay':
        blend = np.where(d <= .5, 2*f*d, 1-2*(1-f)*(1-d))
    elif mode == 'darken':
        blend = np.minimum(f, d)
    elif mode == 'lighten':
        blend = np.maximum(f, d)
    else:
        raise ValueError('Cannot rasterise .merge with unsupported blend mode: ' + mode)
    combined_alpha = a + b * (1-a)
    rgb = (f*a*(1-b) + d*b*(1-a) + blend*a*b)
    return np.concatenate((np.where(combined_alpha > 1e-8, rgb/np.maximum(combined_alpha,1e-8), 0), combined_alpha), axis=2).astype(np.float32)


def collapse_merged_groups(root, load_pixels, size, logger=print):
    """Replace .merge groups with single pixel nodes, preserving draw order.

    load_pixels(item) should return straight-alpha float RGBA (height,width,4).
    Other groups, their nesting and original source images are left untouched.
    """
    height, width = size[1], size[0]
    zero = np.zeros((height, width, 4), np.float32)

    def pixels_for(item):
        arr = item.get('pixels')
        if arr is None:
            arr = load_pixels(item)
        arr = np.asarray(arr, np.float32)
        if arr.shape != zero.shape:
            raise ValueError('Merging group: cached artwork dimensions mismatch')
        return arr

    def render_children(group, inherited_mode=None):
        result = zero.copy()
        # Writer order is top-to-bottom, hence composite bottom-to-top.
        for child in reversed(group['children']):
            if child['kind'] == 'layer':
                item = child['item']
                if item.get('flags', set()) & {'ref', 'reference', 'disabled'}:
                    continue
                result = over(result, pixels_for(item), effective_layer_mode(item, inherited_mode))
            else:
                if 'ref' in tags(child['raw']) or 'reference' in tags(child['raw']):
                    continue
                inner_mode = promoted_blend(child)
                sub = render_children(child, inner_mode)
                result = over(result, sub, inner_mode or 'normal')
        return result

    def recurse(parent):
        children = []
        for child in parent['children']:
            if child['kind'] != 'group':
                children.append(child)
                continue
            recurse(child)
            if 'merge' not in tags(child['raw']):
                children.append(child)
                continue
            name = strip_tags(child['name'])
            mode = promoted_blend(child) or 'normal'
            pixels = render_children(child, mode)
            inherited_flags = tags(child['raw']) & {'ref', 'reference'}
            # Store prepared RGBA without an intermediate image on disk.
            item = {'entry': {'name': name}, 'source': None,
                    'parts': [name], 'mode': mode, 'flags': inherited_flags,
                    'pixels': pixels, 'merged': True,
                    'inherited_color': child.get('sheet_color') or next((
                        (leaf['item'].get('inherited_color') or '') for leaf in child['children']
                        if leaf['kind'] == 'layer' and leaf['item'].get('inherited_color')), '')}
            children.append({'kind': 'layer', 'name': name, 'item': item})
            logger(f'{LOG_PREFIX} MERGE:', child['raw'], '->', name,
                   '| source pixels:', count_leaves(child),
                   '| blend:', mode)
        parent['children'] = children

    def count_leaves(node):
        return sum(1 if c['kind']=='layer' else count_leaves(c) for c in node['children'])

    recurse(root)
    return root
