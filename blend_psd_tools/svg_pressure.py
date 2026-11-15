"""Editable pressure strokes: PowerStroke width and SVG opacity gradients.

No scene mutations or Inkscape executable are needed. The standard SVG outline
is a sampled approximation; Inkscape retains the authored cubic centreline and
live width handles. Opacity uses an independent, editable axis gradient only
when the source progresses monotonically along that axis.
"""
from html import escape
import json


def _vectors():
    try:
        from . import svg_export
    except ImportError:
        import svg_export
    return svg_export






def prepare(stroke):
    try:
        from .vector_artwork import prepare_pressure
    except ImportError:
        from vector_artwork import prepare_pressure
    return prepare_pressure(stroke)


def markup(stroke, element_id, label):
    v=_vectors();fmt=v.fmt;p=stroke['pressure'];ident=f'compio-pressure-{element_id}'
    defs=[];paint=stroke['stroke'];opacity=stroke.get('stroke_opacity',1)
    gradient=p.get('gradient')
    if gradient:
        axis=gradient['axis'];coords=(f'x1="{fmt(gradient["start"])}" y1="0" x2="{fmt(gradient["end"])}" y2="0"'
                                     if axis==0 else f'x1="0" y1="{fmt(gradient["start"])}" x2="0" y2="{fmt(gradient["end"])}"')
        defs.append(f'<linearGradient id="{ident}-alpha" gradientUnits="userSpaceOnUse" {coords}>')
        for offset,alpha in zip(gradient['stops'],p['opacities']):
            defs.append(f'<stop offset="{fmt(offset)}" stop-color="{paint}" stop-opacity="{fmt(alpha)}"/>')
        defs.append('</linearGradient>')
        paint=f'url(#{ident}-alpha)'
    centre=v.svg_path(stroke['points'],stroke['type'],False)
    metadata=escape(json.dumps({k:p[k] for k in ('widths','opacities') if k in p}),quote=True)
    attrs=(f'id="{ident}" inkscape:label="{label}" data-compio-role="outline" '
           f'data-compio-pressure="{metadata}"')
    if p.get('widths'):
        offsets=' | '.join(f'{i},{fmt(w/2)}' for i,w in enumerate(p['widths']))
        defs.append(f'<inkscape:path-effect id="{ident}-width" effect="powerstroke" is_visible="true" lpeversion="1" '
                    f'offset_points="{offsets}" sort_points="true" not_jump="false" interpolator_type="Linear" '
                    'interpolator_beta="0" start_linecap_type="round" end_linecap_type="round" '
                    'linejoin_type="round" miter_limit="4" scale_width="1"/>')
        path=(f'<path {attrs} data-compio-geometry="powerstroke" inkscape:original-d="{escape(centre,quote=True)}" '
              f'inkscape:path-effect="#{ident}-width" d="{escape(v.svg_path(p["outline"],"POLY",True),quote=True)}" '
              f'fill="{paint}" fill-opacity="{fmt(opacity)}" stroke="none"/>')
    else:
        path=(f'<path {attrs} data-compio-geometry="opacity-gradient" d="{escape(centre,quote=True)}" '
              f'fill="none" stroke="{paint}" stroke-opacity="{fmt(opacity)}" '
              f'stroke-width="{fmt(stroke["width"])}" stroke-linecap="round" stroke-linejoin="round"/>')
    return '<defs>'+''.join(defs)+'</defs>'+path


def artwork(scene,view_layer,obj,graph,*,editable_layer_blends):
    try:
        from .vector_artwork import evaluated_artwork
    except ImportError:
        from vector_artwork import evaluated_artwork
    return evaluated_artwork(scene,view_layer,obj,graph,
                             editable_layer_blends=editable_layer_blends)
