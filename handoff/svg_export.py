"""Conservative, camera-space SVG sidecars for HandOff Grease Pencil.

Unsupported cases use rendered PNG. Layer blends use the closest supported
SVG compositing mode with explicit approximation diagnostics.
No bpy imports at module import time so pure path tests can run outside Blender.
"""
from collections import OrderedDict
from html import escape
from math import isfinite, atan, degrees
import re
import json
from pathlib import Path

try:
    from . import vector_artwork as _artwork
except ImportError:
    import vector_artwork as _artwork
if getattr(_artwork, 'ARTWORK_API_VERSION', 0) < 3:
    import importlib
    _artwork = importlib.reload(_artwork)

try:
    from .vector_artwork import (VectorFallback, _effective_radius, _css_font_family, _text_style_for_index, _srgb_hex, _is_visible, _camera_visible_objects, _object_camera_depth, _sort_gp_objects, _render_size, _camera_projection, _uniform, _mixed_color, _stroke_from_blender, _flat_material_color, _object_materials, _constant_socket, _text_material_rgba, _curve_from_blender, _font_from_blender, _iter_gp_layers, _gp_from_blender)
except ImportError:
    from vector_artwork import (VectorFallback, _effective_radius, _css_font_family, _text_style_for_index, _srgb_hex, _is_visible, _camera_visible_objects, _object_camera_depth, _sort_gp_objects, _render_size, _camera_projection, _uniform, _mixed_color, _stroke_from_blender, _flat_material_color, _object_materials, _constant_socket, _text_material_rgba, _curve_from_blender, _font_from_blender, _iter_gp_layers, _gp_from_blender)

SVG_API_VERSION = 17

# These names describe standard SVG compositing, not Blender's GP buffer
# arithmetic. The export worker reports these appearance approximations.
GP_SVG_BLENDS = {'REGULAR': 'normal', 'NORMAL': 'normal',
                 'MULTIPLY': 'multiply', 'HARDLIGHT': 'hard-light',
                 'ADD': 'screen', 'SUBTRACT': 'difference', 'DIVIDE': 'color-dodge'}
GP_APPROXIMATE_BLENDS = frozenset({'ADD', 'SUBTRACT', 'DIVIDE'})


def _gp_layer_blend_attrs(layer):
    mode = layer.get('blend_mode', 'REGULAR')
    if mode not in GP_SVG_BLENDS:
        raise VectorFallback(f'Grease Pencil {mode} has no supported SVG layer blend')
    if GP_SVG_BLENDS[mode] == 'normal':
        return ''
    approximation = (f' data-compio-blend-approximation="{GP_SVG_BLENDS[mode]}"'
                     if mode in GP_APPROXIMATE_BLENDS else '')
    return (f' data-compio-gp-blend="{mode}"{approximation}'
            f' style="mix-blend-mode:{GP_SVG_BLENDS[mode]}"')



def fmt(value):
    value = float(value)
    if not isfinite(value):
        raise VectorFallback('Invalid projected coordinate')
    return f'{value:.5f}'.rstrip('0').rstrip('.') or '0'


def svg_path(points, curve_type='POLY', cyclic=True):
    # GP Dash can emit a one-point open stroke, rendered as a round dot.
    if len(points)==1 and not cyclic:
        x,y=points[0]['co']
        return f'M {fmt(x)} {fmt(y)} L {fmt(x)} {fmt(y)}'
    minimum = (2 if curve_type == 'BEZIER' else 3) if cyclic else 2
    if len(points) < minimum:
        raise VectorFallback('Insufficient points for vector curve')
    if curve_type not in ('POLY', 'BEZIER'):
        raise VectorFallback('Unsupported Grease Pencil curve type: ' + str(curve_type))
    def xy(p):
        return fmt(p[0]) + ' ' + fmt(p[1])
    path = ['M ' + xy(points[0]['co'])]
    segments = len(points) if cyclic else len(points) - 1
    for i in range(segments):
        start, end = points[i], points[(i + 1) % len(points)]
        if curve_type == 'BEZIER':
            if start.get('right') is None or end.get('left') is None:
                raise VectorFallback('Bézier handles unavailable')
            path.append('C ' + xy(start['right']) + ' ' + xy(end['left']) + ' ' + xy(end['co']))
        else:
            path.append('L ' + xy(end['co']))
    if cyclic:
        path.append('Z')
    return ' '.join(path)


def _visible_outline(stroke):
    return (bool(stroke.get('stroke')) and not stroke.get('hide_stroke')
            and float(stroke.get('stroke_opacity', 1)) > 0
            and float(stroke.get('width', 0)) > 0)


def _outline_style(stroke):
    return (stroke.get('stroke', ''), float(stroke.get('stroke_opacity', 1)), float(stroke.get('width', 0)))


def _outline_style_key(stroke):
    """Prevent imperceptible FP noise from splitting a uniform GP outline.

    Widths are in final SVG pixels. Differences of 0.001px or less are
    below the writer's useful precision, while intentional width and opacity
    changes remain independent paths.
    """
    color, opacity, width = _outline_style(stroke)
    return (color, round(opacity, 6), round(width, 3))


def _stroke_path_markup(element_id, label, paths, style):
    """A compound stroke stays one editable Inkscape path per style run."""
    color, opacity, width = style
    return (f'<path id="compio-gp-{element_id}" inkscape:label="{label}"'
            f' data-compio-role="outline" d="{escape(" ".join(paths), quote=True)}" fill="none"'
            f' stroke="{color}" stroke-opacity="{fmt(opacity)}"'
            f' stroke-width="{fmt(width)}" stroke-linecap="round" stroke-linejoin="round"/>')


def _outline_runs(contours):
    """Join neighbouring contours that have the same visible outline style."""
    runs = []
    for contour in contours:
        if not _visible_outline(contour):
            continue
        style = _outline_style(contour)
        key = _outline_style_key(contour)
        path = svg_path(contour['points'], contour['type'], contour['cyclic'])
        if runs and runs[-1][2] == key:
            runs[-1][1].append(path)
        else:
            runs.append((style, [path], key))
    return [(style, paths) for style, paths, _key in runs]








def _encode_live_text(info, element_id):
    """Editable SVG text. Local SVG Y is down, Blender text Y is up."""
    name = escape(str(info['name']), quote=True)
    family = escape(str(info['family']), quote=True)
    label = escape(str(info.get('font_source', info['family'])), quote=True)
    matrix = ' '.join(fmt(n) for n in info['matrix'])
    shear = float(info.get('shear', 0))
    transform = f'matrix({matrix})' + (f' skewX({fmt(degrees(atan(shear)))})' if abs(shear) > .00001 else '')
    alignment = info.get('align', 'LEFT')
    anchors = {'LEFT': 'start', 'CENTER': 'middle', 'RIGHT': 'end'}
    baselines = {'TOP_BASELINE': 'alphabetic', 'TOP': 'text-before-edge',
                 'CENTER': 'central', 'BOTTOM': 'text-after-edge',
                 'BOTTOM_BASELINE': 'alphabetic'}
    baseline = baselines.get(info.get('align_y'), 'alphabetic')
    attrs = [f'id="compio-text-{element_id}"', f'inkscape:label="{name}"',
             f'data-compio-object="{name}"', f'data-compio-font="{label}"',
             f'font-family="{family}"', f'font-size="{fmt(info["size"])}"',
             f'fill="{info["fill"]}"', f'fill-opacity="{fmt(info["opacity"])}"',
             f'text-anchor="{anchors.get(alignment, "start")}"',
             f'dominant-baseline="{baseline}"',
             f'data-compio-space-character="{fmt(info.get("space_character", 1))}"',
             f'data-compio-space-word="{fmt(info.get("space_word", 1))}"',
             f'data-compio-space-line="{fmt(info.get("space_line", 1))}"',
             f'data-compio-small-caps-scale="{fmt(info.get("small_caps_scale", .75))}"',
             f'data-compio-underline-height="{fmt(info.get("underline_height", .05))}"',
             f'data-compio-underline-position="{fmt(info.get("underline_position", 0))}"',
             f'transform="{transform}"',
             f'x="{fmt(info.get("offset_x", 0))}"',
             f'y="{fmt(-info.get("offset_y", 0))}"']
    if info.get('font_substituted',False):
        attrs.append('data-compio-font-substituted="true"')
    spacing = float(info.get('space_character', 1))
    if abs(spacing - 1) > 0.00001:
        # Spacing factors in Blender multiply advances. SVG letter-spacing
        # adds a fixed offset, so this is approximate; the exact factor above
        # is retained for round-tripping.
        attrs.append(f'letter-spacing="{fmt((spacing - 1) * info["size"] * .5)}"')
    if abs(float(info.get('space_word', 1)) - 1) > .00001:
        attrs.append(f'word-spacing="{fmt((info["space_word"] - 1) * info["size"] * .5)}"')
    if abs(float(info.get('shear', 0))) > .00001:
        attrs.append(f'data-compio-shear="{fmt(info["shear"])}"')
    text = str(info['body']).replace('\r\n','\n')
    if not text:
        return ''
    # Keep the original content including line breaks for round-tripping.
    attrs.append(f'data-compio-source-text="{escape(text, quote=True).replace(chr(10), "&#10;")}"')
    kerning = info.get('kerning', ())
    if any(abs(float(v)) > .00001 for v in kerning):
        attrs.append('data-compio-char-kerning="' + ','.join(fmt(v) for v in kerning) + '"')
    output = ['<text ' + ' '.join(attrs) + '>']
    formats = info.get('formats', [])
    colors = info.get('material_colors', [])
    # Keep the text as real SVG characters, not glyph outlines. Runs preserve
    # bold/italic/underline/small-caps and per-character colour assignments.
    for line_index, line in enumerate(text.split('\n')):
        line_chars = []
        if line_index:
            output.append(f'<tspan x="{fmt(info.get("offset_x", 0))}" dy="{fmt(info["size"] * info.get("space_line", 1))}">')
        else:
            output.append('<tspan>')
        start = sum(len(part) + 1 for part in text.split('\n')[:line_index])
        cursor = 0
        while cursor < len(line):
            idx = start + cursor
            style = tuple(formats[idx]) if idx < len(formats) else (False, False, False, False, 0)
            next_index = cursor + 1
            while next_index < len(line):
                ni = start + next_index
                next_style = tuple(formats[ni]) if ni < len(formats) else (False, False, False, False, 0)
                if next_style != style:
                    break
                next_index += 1
            bold, italic, underline, small_caps, material_id = style
            props = []
            if bold:
                props.append('font-weight="bold"')
            if italic:
                props.append('font-style="italic"')
            variant = info.get('font_variants', {}).get(('bold' if bold else '') + ('italic' if italic else ''))
            if variant:
                props.append('font-family="' + escape(variant, quote=True) + '"')
            if underline:
                props.append('text-decoration="underline"')
            if small_caps:
                props.append('font-variant="small-caps"')
            if material_id and material_id < len(colors):
                props.append(f'fill="{colors[material_id][0]}"')
                props.append(f'fill-opacity="{fmt(colors[material_id][1])}"')
            output.append('<tspan' + (' ' + ' '.join(props) if props else '') + '>' + escape(line[cursor:next_index]) + '</tspan>')
            cursor = next_index
        output.append('</tspan>')
    output.append('</text>')
    return ''.join(output)


def _encode_curve_object(info, element_id):
    """Contiguous material runs keep the authored curve spline order."""
    label = escape(str(info['name']), quote=True)
    paths = info['splines']
    fill_rule = info.get('fill_rule', 'evenodd')
    runs = []
    for part in paths:
        style = (part['fill'], part['opacity'])
        if runs and runs[-1][0] == style:
            runs[-1][1].append(part.get('d') or svg_path(part['points'],part['type'],True))
        else:
            runs.append((style, [part.get('d') or svg_path(part['points'],part['type'],True)]))
    out = []
    for i, ((color, opacity), ds) in enumerate(runs):
        out.append(f'<path id="compio-curve-{element_id}-{i}" inkscape:label="{label}"'
                   f' data-compio-object="{label}" d="{escape(" ".join(ds), quote=True)}"'
                   f' fill="{color}" fill-opacity="{fmt(opacity)}"'
                   f' fill-rule="{fill_rule}" stroke="none"/>')
    if len(out) > 1:
        return (f'<g id="compio-curve-object-{element_id}" inkscape:label="{label}"'
                f' data-compio-object="{label}">' + '\n'.join(out) + '</g>')
    return '\n'.join(out)


def _fill_gradient_markup(gradient, identifier):
    tag = 'radialGradient' if gradient['kind'] == 'RADIAL' else 'linearGradient'
    coords = 'cx=".5" cy=".5" r=".5"' if tag == 'radialGradient' else 'x1="0" y1="0" x2="1" y2="0"'
    matrix = ' '.join(fmt(n) for n in gradient['matrix'])
    # Stops have already passed through Blender's scene colour management.
    stops = ''.join(f'<stop offset="{fmt(s["position"])}" stop-color="{s["color"]}"'
                    f' stop-opacity="{fmt(s["opacity"])}"/>' for s in gradient['stops'])
    return (f'<defs><{tag} id="{identifier}" gradientUnits="userSpaceOnUse"'
            f' {coords} gradientTransform="matrix({matrix})" color-interpolation="sRGB"'
            f' data-compio-interpolation="{escape(gradient.get("interpolation", "LINEAR"), quote=True)}"'
            f' data-compio-color-mode="{escape(gradient.get("color_mode", "RGB"), quote=True)}"'
            f' spreadMethod="pad">{stops}</{tag}></defs>')


def encode_svg(width, height, objects):
    if width < 1 or height < 1:
        raise VectorFallback('Invalid canvas dimensions')
    text = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="{int(width)}" height="{int(height)}" viewBox="0 0 {int(width)} {int(height)}">']
    element_id = 0
    for obj_index, obj in enumerate(objects):
        if obj.get('svg_kind') == 'RASTER':
            label = escape(obj['name'], quote=True)
            text.append(f'<g id="compio-raster-{obj_index}" inkscape:label="{label}"'
                        f' data-compio-raster-request="{obj["request"]}">'
                        f'<image x="0" y="0" width="{int(width)}" height="{int(height)}"'
                        ' preserveAspectRatio="none"/></g>')
            continue
        if obj.get('svg_kind') == 'FONT':
            text.append(_encode_live_text(obj, obj_index))
            continue
        if obj.get('svg_kind') == 'CURVE':
            text.append(_encode_curve_object(obj, obj_index))
            continue
        obj_label = escape(obj['name'], quote=True)
        # Blend drawing layers against this object's own isolated backdrop.
        # Even one blended layer needs a child group, otherwise its blend
        # would reach unrelated objects outside this GP object.
        blend_attrs = [_gp_layer_blend_attrs(layer) for layer in obj['layers']]
        blended = any(blend_attrs)
        single_layer = len(obj['layers']) == 1 and not blended
        layer_attrs = ''
        if single_layer:
            only_layer = obj['layers'][0]
            layer_attrs = (f' data-compio-layer="{escape(only_layer["name"], quote=True)}"'
                           f' opacity="{fmt(only_layer.get("opacity", 1))}"')
        if obj.get('expanded_stroke'):
            layer_attrs += (' data-compio-geometry="expanded-stroke" data-compio-source-widths="' +
                            escape(json.dumps(obj['expanded_stroke']),quote=True) + '"')
        if blended:
            layer_attrs += ' style="isolation:isolate"'
        if obj.get('modifiers'):
            layer_attrs += ' data-compio-modifiers="'+escape(json.dumps(obj['modifiers']),quote=True)+'"'
        if obj.get('source_geometry'):
            layer_attrs += ' data-compio-source-geometry="'+escape(json.dumps(obj['source_geometry']),quote=True)+'"'
        if obj.get('svg_instance'):
            info = obj['svg_instance']
            layer_attrs += (' data-layered-instance-key="' + escape(info['key'], quote=True) + '"'
                            ' data-layered-instance-config="' + escape(info['config'], quote=True) + '"'
                            ' data-layered-instance-basis="' + escape(json.dumps(info['basis']), quote=True) + '"')
        text.append(f'<g id="compio-gp-object-{obj_index}" data-compio-object="{obj_label}" inkscape:label="{obj_label}"{layer_attrs}>')
        for layer_index, layer in enumerate(obj['layers']):
            layer_label = escape(layer['name'], quote=True)
            if not single_layer:
                text.append(f'<g id="compio-gp-layer-{obj_index}-{layer_index}" data-compio-layer="{layer_label}" inkscape:label="{layer_label}" opacity="{fmt(layer.get("opacity", 1))}"{blend_attrs[layer_index]}>')
            strokes = [dict(stroke) for stroke in layer['strokes']]
            # Blender may supply an outline and its filled contour as two
            # curves. They can share one SVG path only when the path data and
            # material slot are identical and their strokes are adjacent.
            consumed = set()
            for i, fill in enumerate(strokes):
                if not fill.get('fill_id') or _visible_outline(fill):
                    continue
                for j in (i - 1, i + 1):
                    if j < 0 or j >= len(strokes) or j in consumed:
                        continue
                    outline = strokes[j]
                    if outline.get('pressure') or outline.get('fill_id') or not _visible_outline(outline):
                        continue
                    if fill.get('material_index') != outline.get('material_index'):
                        continue
                    if svg_path(fill['points'], fill['type'], fill['cyclic']) != svg_path(outline['points'], outline['type'], outline['cyclic']):
                        continue
                    fill.update({k: outline[k] for k in ('stroke', 'stroke_opacity', 'width') if k in outline})
                    consumed.add(j)
                    break

            fills = OrderedDict()
            # A fill ID may join several contours (including holes). Reject
            # interleaving so path grouping never changes artwork draw order.
            sequence = [st.get('fill_id', 0) for i, st in enumerate(strokes) if i not in consumed]
            finished = set()
            last_id = None
            for fid in sequence:
                if fid != last_id:
                    if last_id:
                        finished.add(last_id)
                    if fid and fid in finished:
                        raise VectorFallback('Interleaved fill contours require PNG')
                    last_id = fid
            for i, stroke in enumerate(strokes):
                if i in consumed:
                    continue
                fid = stroke.get('fill_id', 0)
                if fid:
                    if not stroke['cyclic']:
                        raise VectorFallback('Open curves cannot form a reliable fill')
                    style = (stroke['fill'], stroke.get('fill_opacity', 1), stroke.get('fill_gradient'))
                    if fid in fills and fills[fid][0] != style:
                        raise VectorFallback('One fill group has inconsistent materials')
                    fills.setdefault(fid, (style, []))[1].append(stroke)
            # Export each fill group once. A Grease Pencil fill_id can
            # contain several contours, including holes; those all share
            # one SVG compound fill path. Its outlines must not each become
            # separate paint objects when their style is identical.
            emitted = set()
            i = 0
            while i < len(strokes):
                stroke = strokes[i]
                if i in consumed:
                    i += 1
                    continue
                if stroke.get('pressure'):
                    try:
                        from .svg_pressure import markup
                    except ImportError:
                        from svg_pressure import markup
                    element_id += 1
                    text.append(markup(stroke,element_id,layer_label))
                    i += 1
                    continue
                fid = stroke.get('fill_id', 0)
                if fid:
                    if fid in emitted:
                        i += 1
                        continue
                    (color, opacity, gradient), contours = fills[fid]
                    contours_paths = [svg_path(part['points'], part['type'], True)
                                      for part in contours]
                    all_outlines = [_outline_style(part) for part in contours
                                    if _visible_outline(part)]
                    outline_keys = [_outline_style_key(part) for part in contours
                                    if _visible_outline(part)]
                    can_join = (len(all_outlines) == len(contours) and
                                bool(all_outlines) and len(set(outline_keys)) == 1)
                    # One Grease Pencil fill_id is one logical authored shape.
                    # A single SVG <path> can carry both fill and outline only
                    # when all contours use the same visible outline style.
                    # Otherwise keep the compound fill and independent contour
                    # outlines inside ONE named editable shape group. This
                    # preserves hole behaviour and per-contour stroke styles
                    # without exposing unrelated top-level objects in Inkscape.
                    runs = [] if can_join else _outline_runs(contours)
                    if runs:
                        element_id += 1
                        text.append(
                            f'<g id="compio-gp-shape-{element_id}"'
                            f' inkscape:label="{obj_label}"'
                            f' data-compio-shape="fill-group"'
                            f' data-compio-fill-id="{fid}"'
                            f' data-compio-contours="{len(contours)}">')
                    element_id += 1
                    if gradient:
                        identifier = f'compio-fill-gradient-{element_id}'
                        text.append(_fill_gradient_markup(gradient, identifier))
                        color = f'url(#{identifier})'
                    attrs = (f' id="compio-gp-{element_id}" inkscape:label="{layer_label}"'
                             f' data-compio-role="fill"'
                             f' d="{escape(" ".join(contours_paths), quote=True)}"'
                             f' fill="{color}" fill-opacity="{fmt(opacity)}" fill-rule="evenodd"')
                    if can_join:
                        sc, so, sw = all_outlines[0]
                        attrs += (f' stroke="{sc}" stroke-opacity="{fmt(so)}"'
                                  f' stroke-width="{fmt(sw)}" stroke-linecap="round" stroke-linejoin="round"')
                    else:
                        attrs += ' stroke="none"'
                    text.append('<path' + attrs + '/>')
                    emitted.add(fid)
                    for style, outlines in runs:
                        element_id += 1
                        text.append(_stroke_path_markup(
                            element_id, layer_label, outlines, style))
                    if runs:
                        text.append('</g>')
                    i += 1
                    continue
                if _visible_outline(stroke):
                    # Combine consecutive outline-only GP curves when they
                    # share a paint style. This never crosses a fill-group
                    # boundary, which would change the authored draw order.
                    style = _outline_style(stroke)
                    style_key = _outline_style_key(stroke)
                    outlines = [svg_path(stroke['points'], stroke['type'], stroke['cyclic'])]
                    j = i + 1
                    while j < len(strokes) and j not in consumed:
                        nxt = strokes[j]
                        if nxt.get('pressure') or nxt.get('fill_id', 0) or not _visible_outline(nxt) or _outline_style_key(nxt) != style_key:
                            break
                        outlines.append(svg_path(nxt['points'], nxt['type'], nxt['cyclic']))
                        j += 1
                    element_id += 1
                    text.append(_stroke_path_markup(element_id, layer_label, outlines, style))
                    i = j
                    continue
                i += 1
            if not single_layer:
                text.append('</g>')
        text.append('</g>')
    text.append('</svg>')
    encoded = '\n'.join(text) + '\n'
    if any(obj.get('svg_instance') or obj.get('source_metadata') for obj in objects):
        from xml.etree import ElementTree as ET
        try:
            from .svg_instances import link_instances
        except ImportError:
            from svg_instances import link_instances
        root = ET.fromstring(encoded)
        try:
            from .svg_metadata import source_attributes,annotate
        except ImportError:
            from svg_metadata import source_attributes,annotate
        for child,obj in zip(root,objects):
            if obj.get('source_metadata'):child.attrib.update(source_attributes(obj['source_metadata']))
        link_instances(root)
        if any(obj.get('source_metadata') for obj in objects):annotate(root,scope='source')
        return ET.tostring(root, encoding='unicode') + '\n'
    return encoded







































def export_view_layer_svg(scene, view_layer, path, *, hybrid=False, save_as_render=True,
                          allow_raster=True, deferred=False, flat_text_material=False,
                          collection_root='', font_directory='', use_font_directory=True,
                          editable_layer_blends=True):
    """Export camera-space vectors, optionally with whole-object GP fallbacks.

    Legacy callers retain conservative source-wide fallback. Hybrid callers
    classify each whole object and isolate unsupported GP artwork in the worker.
    """
    if hybrid:
        try:
            from . import svg_hybrid
        except ImportError:
            import svg_hybrid
        if getattr(svg_hybrid, 'HYBRID_API_VERSION', 0) < 13:
            import importlib
            svg_hybrid = importlib.reload(svg_hybrid)
        if deferred:
            return svg_hybrid.queue_hybrid_svg(scene, view_layer, path,
                                               save_as_render=save_as_render,
                                               flat_text_material=flat_text_material,
                                               editable_layer_blends=editable_layer_blends,
                                               collection_root=collection_root,
                                               font_directory=font_directory,
                                               use_font_directory=use_font_directory)
        return svg_hybrid.export_hybrid_svg(scene, view_layer, path,
                                            save_as_render=save_as_render,
                                            allow_raster=allow_raster,
                                            flat_text_material=flat_text_material,
                                            editable_layer_blends=editable_layer_blends,
                                            collection_root=collection_root,
                                            font_directory=font_directory,
                                            use_font_directory=use_font_directory)
    try:
        camera = scene.camera
        if camera is None or camera.data.type != 'ORTHO':
            raise VectorFallback('First-phase SVG requires an orthographic render camera')
        if not scene.render.film_transparent:
            raise VectorFallback('Transparent film required for SVG-only output')
        if getattr(getattr(camera.data, 'dof', None), 'use_dof', False):
            raise VectorFallback('Camera depth of field requires PNG')
        if getattr(scene.render, 'use_motion_blur', False):
            raise VectorFallback('Motion blur requires PNG')
        objects = []
        skipped_layers = []
        for obj in _camera_visible_objects(view_layer):
            if not _is_visible(obj, view_layer):
                continue
            if obj.type in ('CAMERA', 'LIGHT', 'LIGHT_PROBE', 'ARMATURE', 'EMPTY'):
                continue
            if obj.type == 'CURVE':
                objects.append(_curve_from_blender(scene, camera, obj))
                continue
            if obj.type == 'FONT':
                objects.append(_font_from_blender(scene, camera, obj,
                                                   flat_material=flat_text_material))
                continue
            if obj.type != 'GREASEPENCIL':
                raise VectorFallback('Mixed visible geometry (' + obj.type + ') requires PNG')
            prepared = _gp_from_blender(scene, camera, obj, view_layer, skipped_layers,
                                        editable_layer_blends=editable_layer_blends)
            if prepared:
                objects.append(prepared)
        if not objects:
            extra = ('; ' + '; '.join(skipped_layers[:5])) if skipped_layers else ''
            raise VectorFallback('No visible vector artwork in source View Layer ' +
                                 view_layer.name + extra)
        if len(objects) > 1:
            objects = _sort_gp_objects(scene, camera, objects)
        w, h = _render_size(scene)
        svg = encode_svg(w, h, objects)
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(svg, encoding='utf-8')
        geometry_count = sum(len(layer['strokes']) for obj in objects for layer in obj.get('layers', []))
        geometry_count += sum(len(obj.get('splines', [])) for obj in objects)
        geometry_count += sum(1 for obj in objects if obj.get('svg_kind') == 'FONT')
        live_texts = sum(1 for obj in objects if obj.get('svg_kind') == 'FONT')
        message = f'SVG: {geometry_count} editable vector elements ({len(objects)} objects)'
        if live_texts:
            message += '; live text needs matching fonts in the destination editor'
        return True, message
    except (VectorFallback, AttributeError, ValueError, TypeError, IndexError) as exc:
        return False, str(exc)
