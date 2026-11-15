"""Detached GP colour ramps and stroke-space mapping (Blender 5.3).

The mapping follows Drawing::texture_matrices in blenkernel/grease_pencil.cc:
Newell normal, first edge basis, then the curve UV attributes. Material mapping
is independently checked against the installed Blender renderer. No bpy data
is created or changed here. Target writers own their gradient serialization.
"""
from math import sin, cos, isfinite

GRADIENT_API_VERSION = 2


def fill_gradient(style, stroke, drawing, index, project, tint=(0, 0, 0, 0)):
    from mathutils import Vector
    try:
        from .vector_artwork import VectorFallback, _mixed_color, _srgb_hex
    except ImportError:
        from vector_artwork import VectorFallback, _mixed_color, _srgb_hex
    if drawing is None or index is None:
        raise VectorFallback('GP gradient drawing attributes are unavailable; preserving rendered PNG')
    positions = [Vector(p.position) for p in stroke.points]
    if len(positions) < 3:
        raise VectorFallback('GP gradient needs a planar filled contour')
    normal = Vector((0, 0, 0))
    for a, b in zip(positions, positions[1:] + positions[:1]):
        normal += a.cross(b)
    origin = positions[0]
    x = (positions[1] - origin).normalized()
    y = normal.normalized().cross(x).normalized()
    if normal.length < 1e-10 or x.length < .5 or y.length < .5:
        raise VectorFallback('Degenerate GP gradient plane requires PNG')
    normal.normalize()
    extent = max((p-origin).length for p in positions)
    plane_points = positions[:]
    if getattr(stroke, 'curve_type', None) == 2:
        for p in stroke.points:
            plane_points.extend(Vector(h.position) for h in (p.handle_left, p.handle_right))
    if any(abs((p-origin).dot(normal)) > max(1e-6, extent*1e-5) for p in plane_points):
        raise VectorFallback('Nonplanar GP gradient requires PNG')

    def attr(name, default):
        value = drawing.attributes.get(name)
        if value is None:
            return default
        if value.domain != 'CURVE':
            raise VectorFallback('Invalid GP gradient attribute domain: ' + name)
        item = value.data[index]
        return item.vector[:] if hasattr(item, 'vector') else item.value

    uv_angle = float(attr('uv_rotation', 0))
    uv_scale = attr('uv_scale', (1, 1))
    uv_offset = attr('uv_translation', (0, 0))
    angle = float(style.texture_angle)
    scale = tuple(style.texture_scale)
    offset = tuple(style.texture_offset)
    if not all(isfinite(v) for v in (angle, uv_angle, *scale, *offset, *uv_scale, *uv_offset)):
        raise VectorFallback('Invalid GP gradient transform')
    if any(abs(v) < 1e-8 for v in (*scale, *uv_scale)):
        raise VectorFallback('Singular GP gradient transform requires PNG')

    def screen(u, v):
        # Inverse of material UV = .5 + scale^-1 R(-angle)(curve UV + offset).
        u, v = (u-.5)*scale[0], (v-.5)*scale[1]
        u, v = cos(angle)*u-sin(angle)*v-offset[0], sin(angle)*u+cos(angle)*v-offset[1]
        # Inverse of the drawing's R(uv_rotation) scale^-1 basis.
        u, v = u-uv_offset[0], v-uv_offset[1]
        u, v = ((cos(uv_angle)*u+sin(uv_angle)*v)*uv_scale[0],
                (-sin(uv_angle)*u+cos(uv_angle)*v)*uv_scale[1])
        return project(origin + x*u + y*v)

    a, b, c = screen(0, 0), screen(1, 0), screen(0, 1)
    matrix = (b[0]-a[0], b[1]-a[1], c[0]-a[0], c[1]-a[1], a[0], a[1])
    if abs(matrix[0]*matrix[3]-matrix[1]*matrix[2]) < 1e-8:
        raise VectorFallback('Edge-on GP gradient requires PNG')
    kind = style.gradient_type
    if kind not in ('LINEAR', 'RADIAL'):
        raise VectorFallback('Unsupported GP gradient type: ' + str(kind))
    ramp = getattr(style, 'gradient', None)
    if ramp is None:
        raise VectorFallback('GP gradient Color Ramp is unavailable; preserving rendered PNG')
    # Keep the authored editing controls one for one. Standard SVG cannot
    # execute Blender Ease/B-spline/HSV interpolation; preserve that intent
    # as metadata and report the appearance approximation, not extra stops.
    stops = []
    for element in ramp.elements:
        rgba = _mixed_color(tuple(element.color), tint)
        stops.append(dict(position=float(element.position), color=_srgb_hex(rgba),
                          linear=rgba[:3], opacity=rgba[3]))
    return dict(kind=kind, matrix=matrix, stops=stops, interpolation=ramp.interpolation,
                color_mode=ramp.color_mode)
