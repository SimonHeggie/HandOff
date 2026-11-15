"""Translate Blender Collection colour tags to Photoshop group colour labels.

Labels follow the authored Collection path. Blender permits theme-defined
swatches, so use the current theme when available and a stable fallback otherwise.
"""

# Stable fallback for Blender's eight numbered Collection tag slots. Photoshop
# provides a different palette, so these labels are approximate counterparts.
BLENDER_TO_PSD = {
    'COLOR_01': 'RED',
    'COLOR_02': 'ORANGE',
    'COLOR_03': 'YELLOW',
    'COLOR_04': 'GREEN',
    'COLOR_05': 'BLUE',
    'COLOR_06': 'VIOLET',
    'COLOR_07': 'MAGENTA',
    'COLOR_08': 'GRAY',
}


def theme_collection_colors(bpy):
    """Read all eight active Blender Collection swatches when available."""
    try:
        palette = bpy.context.preferences.themes[0].collection_color
        if len(palette) < 8:
            return None
        return [tuple(float(x) for x in palette[i].color[:3]) for i in range(8)]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return None


def nearest_psd_label(rgb):
    """Find the closest conventional Photoshop layer label by hue/brightness."""
    from colorsys import rgb_to_hsv
    swatches = {
        'RED': (0.84, 0.29, 0.29),
        'ORANGE': (0.89, 0.55, 0.23),
        'YELLOW': (0.94, 0.78, 0.22),
        'GREEN': (0.31, 0.67, 0.32),
        'BLUE': (0.30, 0.52, 0.87),
        'VIOLET': (0.59, 0.36, 0.78),
        'MAGENTA': (0.80, 0.29, 0.66),
        'GRAY': (0.51, 0.51, 0.51),
    }
    h, sat, val = rgb_to_hsv(*(max(0.0,min(1.0,float(c))) for c in rgb[:3]))
    if sat < .14:
        return 'GRAY'
    def distance(ref):
        rh, rs, rv = rgb_to_hsv(*ref)
        delta_h = min(abs(h-rh),1-abs(h-rh))
        return 3.0 * delta_h**2 + .30 * (sat-rs)**2 + .10 * (val-rv)**2
    return min((k for k in swatches if k != 'GRAY'), key=lambda k: distance(swatches[k]))


def source_collection_colors(path, collections, theme_colors=None):
    """Return PSD label names aligned with the authored Collection path.

    `collections` can be Blender's bpy.data.collections or a test mapping.
    Untagged Collections explicitly stop ancestor colour inheritance. A missing
    Collection leaves an unknown slot, preserving legacy fallback behaviour.
    """
    results = []
    parts = (path or '').split('/') if isinstance(path, str) or path is None else path
    for name in (part.strip() for part in parts):
        if not name:
            continue
        collection = collections.get(name) if collections is not None else None
        tag = getattr(collection, 'color_tag', 'NONE') if collection is not None else None
        label = BLENDER_TO_PSD.get(tag, 'NO_COLOR' if tag == 'NONE' else '')
        if tag in BLENDER_TO_PSD and theme_colors is not None:
            index = int(tag[-2:]) - 1
            if 0 <= index < len(theme_colors):
                label = nearest_psd_label(theme_colors[index])
        results.append(label)
    return results
