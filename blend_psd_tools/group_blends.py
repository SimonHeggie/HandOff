"""Choose group blending from the actual layers assigned to an export folder.

Keep pixel modes on mixed folders without a strict majority. When a folder
has a majority non-normal mode, the folder owns it and matching child layers
become normal inside that isolated folder.
"""
from collections import Counter


def canonical_mode(mode):
    mode = (mode or 'normal').lower()
    return 'add' if mode in ('additive', 'linear_dodge', 'linear-dodge') else mode


def promoted_blend(group):
    """Return the group's common blend mode, or None for pass-through.

    Only examine direct pixel children. A group containing subgroups must keep
    those subgroups' distinct modes; inherited modes must never propagate
    across another authored Collection boundary.
    """
    children = group.get('children', [])
    if not children or any(child['kind'] == 'group' for child in children):
        return None
    modes = [canonical_mode(child['item']['mode']) for child in children]
    counted = Counter(modes)
    mode, number = counted.most_common(1)[0]
    return mode if mode != 'normal' and number > len(modes) / 2 else None


def effective_layer_mode(item, promoted):
    mode = canonical_mode(item['mode'])
    return 'normal' if promoted == mode else mode
