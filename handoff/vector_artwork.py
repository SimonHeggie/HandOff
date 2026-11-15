"""Shared camera-space vector artwork for SVG and Photoshop adapters.

Blender data is read into plain geometry/paint records. This module contains
no SVG markup or Photoshop descriptors; format adapters retain their own
serialization. Private SVG reader names remain available through svg_export
for compatibility with existing scripts.
"""

try:
    from .runtime_paths import PRIVATE_PREFIX
except ImportError:
    from runtime_paths import PRIVATE_PREFIX
from math import isfinite, atan2, cos, sin, pi, hypot
from contextlib import contextmanager
import json
from pathlib import Path

SUPPORTED_GP_BLENDS = frozenset({'REGULAR','NORMAL','MULTIPLY','HARDLIGHT','ADD','SUBTRACT','DIVIDE'})
ARTWORK_API_VERSION = 3


def sample_gradient(gradient,x,y,*,linear=False):
    """Sample the detached SVG-equivalent paint; no Blender or format records."""
    import numpy as np
    a,b,c,d,e,f=gradient['matrix'];det=a*d-b*c
    if abs(det)<1e-12:raise ValueError('Cannot render a singular gradient')
    u=(d*(x-e)-c*(y-f))/det;v=(-b*(x-e)+a*(y-f))/det
    if gradient['kind']=='LINEAR':t=u
    elif gradient['kind']=='RADIAL':t=2*np.hypot(u-.5,v-.5)
    else:raise ValueError('Unsupported gradient renderer')
    if gradient.get('spread','pad')!='pad':raise ValueError('Gradient spread renderer is not verified')
    stops=gradient['stops'];positions=[s['position'] for s in stops]
    if not positions or positions!=sorted(positions):raise ValueError('Invalid gradient stops')
    def color(stop):
        if linear:
            if stop.get('linear') is None:raise ValueError('HDR gradient preview needs linear source stops')
            return stop['linear']
        value=stop['color']
        if value.startswith('#'):return [int(value[i:i+2],16)/255 for i in (1,3,5)]
        import re
        return [float(s)/(100 if '%' in value else 255) for s in re.findall(r'[-\d.]+',value)[:3]]
    colors=[color(s) for s in stops]
    return np.stack([np.interp(t,positions,[c[i] for c in colors]) for i in range(3)]+
                    [np.interp(t,positions,[s['opacity'] for s in stops])],axis=-1).astype(np.float32)


@contextmanager
def render_object(scene, obj, graph):
    """Evaluate render flags on a private object, never on the authored rig."""
    mismatch=(graph.mode!='RENDER' and any(m.show_render!=m.show_viewport for m in obj.modifiers))
    if not mismatch:
        yield obj.evaluated_get(graph)
        return
    import bpy
    copy=None
    try:
        copy=obj.copy()
        copy.name=PRIVATE_PREFIX + 'RenderVectors'
        copy.hide_viewport=False
        for modifier in copy.modifiers:
            modifier.show_viewport=modifier.show_render
        scene.collection.objects.link(copy)
        graph.update()
        yield copy.evaluated_get(graph)
    finally:
        if copy is not None:
            bpy.data.objects.remove(copy,do_unlink=True)
            graph.update()


def modifier_records(obj):
    """Portable provenance; target apps cannot execute Blender modifier stacks."""
    result=[]
    for modifier in obj.modifiers:
        record={'name':modifier.name,'type':modifier.type,'render_enabled':modifier.show_render,'settings':{}}
        for prop in getattr(getattr(modifier,'bl_rna',None),'properties',()):
            if prop.identifier in ('rna_type','name','type') or prop.type not in ('BOOLEAN','INT','FLOAT','ENUM','STRING'):continue
            value=getattr(modifier,prop.identifier)
            if not isinstance(value,(bool,int,float,str)):
                try:value=list(value)
                except TypeError:continue
            record['settings'][prop.identifier]=value
        result.append(record)
    return result


def evaluated_artwork(scene,view_layer,obj,graph,*,camera=None,editable_layer_blends=True):
    """Detach render-evaluated GP geometry while its temporary IDs are valid."""
    with render_object(scene,obj,graph) as evaluated:
        camera=(scene.camera.evaluated_get(graph) if hasattr(scene.camera,'evaluated_get')
                else camera or scene.camera)
        if evaluated.type!='GREASEPENCIL':
            raise VectorFallback('Evaluated object is not Grease Pencil')
        try:
            result=_gp_from_blender(scene,camera,evaluated,view_layer,
                                    evaluated=True,editable_layer_blends=editable_layer_blends)
        except VectorFallback as exc:
            if not str(exc).startswith(('Variable-width visible stroke','Varying per-point opacity')):raise
            result=_gp_from_blender(scene,camera,evaluated,view_layer,
                                    evaluated=True,editable_layer_blends=editable_layer_blends,
                                    editable_pressure=True)
            if result:
                for layer in result['layers']:
                    for stroke in layer['strokes']:prepare_pressure(stroke)
        if result:
            result['name']=obj.name
            result['source']=obj
            result['modifiers']=modifier_records(obj)
            if result['modifiers']:
                try:
                    authored=_gp_from_blender(scene,camera,obj,view_layer,evaluated=True,
                        editable_layer_blends=editable_layer_blends,editable_pressure=True)
                    if authored:result['source_geometry']=authored['layers']
                except (VectorFallback,AttributeError,ValueError):
                    pass  # Evaluated geometry remains usable without provenance.
        return result


def write_artwork(path,width,height,objects):
    """The shared plain-data cache is consumed by both document adapters."""
    def plain(value):
        if isinstance(value,dict):return {k:plain(v) for k,v in value.items() if k!='source'}
        if isinstance(value,(tuple,list)):return [plain(v) for v in value]
        return value
    path=Path(path)
    path.write_text(json.dumps({'version':1,'width':width,'height':height,
                                'objects':plain(objects)},ensure_ascii=False),encoding='utf-8')


def flatten_contour(stroke):
    """Sample a projected contour for preview renderers, retaining source handles."""
    points=stroke['points']
    if stroke['type']!='BEZIER' or len(points)<2:return [p['co'] for p in points]
    result=[];count=len(points) if stroke.get('cyclic') else len(points)-1
    for index in range(count):
        a,b=points[index],points[(index+1)%len(points)]
        p,q,r,s=a['co'],a['right'],b['left'],b['co']
        length=sum(hypot(y[0]-x[0],y[1]-x[1]) for x,y in ((p,q),(q,r),(r,s)))
        samples=max(8,min(256,int(length/2)+1))
        for step in range(samples):
            t=step/samples;u=1-t
            result.append(tuple(u**3*p[k]+3*u*u*t*q[k]+3*u*t*t*r[k]+t**3*s[k] for k in (0,1)))
    if not stroke.get('cyclic'):result.append(points[-1]['co'])
    return result


def layer_paints(layer):
    """Ordered compound fills and independent outlines, shared by target adapters."""
    fills={};emitted=set()
    for stroke in layer['strokes']:
        fid=stroke.get('fill_id',0)
        if fid:fills.setdefault(fid,[]).append(stroke)
    for stroke in layer['strokes']:
        fid=stroke.get('fill_id',0)
        if fid:
            if fid in emitted:continue
            emitted.add(fid);contours=fills[fid]
            yield dict(kind='fill',contours=contours,color=stroke['fill'],
                       linear=stroke.get('fill_linear'),opacity=stroke.get('fill_opacity',1))
            outlines=[s for s in contours if _visible_outline(s)]
        else:outlines=[stroke] if _visible_outline(stroke) else []
        for outline in outlines:
            pressure=outline.get('pressure',{})
            if pressure.get('widths'):
                contour=dict(points=pressure['outline'],type='POLY',cyclic=True)
                yield dict(kind='fill',contours=[contour],color=outline['stroke'],
                           linear=outline.get('stroke_linear'),opacity=outline.get('stroke_opacity',1),
                           pressure=pressure,centreline=outline)
            else:
                yield dict(kind='stroke',contours=[outline],color=outline['stroke'],
                           linear=outline.get('stroke_linear'),opacity=outline.get('stroke_opacity',1),
                           width=outline['width'],pressure=pressure)


def artwork_tree(objects):
    """Collection folders in paint order; merge only spatially disjoint segments."""
    from layer_stack import tags,strip_tags
    tree={'children':[]};stack=[((),tree)];previous=()
    for artwork in objects:
        parts=tuple(p for p in artwork.get('collection_parts',[]) if 'ungroup' not in tags(p))
        common=0
        while common<min(len(previous),len(parts)) and previous[common]==parts[common]:common+=1
        stack=stack[:common+1]
        for i in range(common,len(parts)):
            group=dict(name=strip_tags(parts[i]),path=parts[:i+1],flags=tags(parts[i]),children=[])
            stack[-1][1]['children'].append(group);stack.append((parts[:i+1],group))
        stack[-1][1]['children'].append(dict(artwork=artwork));previous=parts
    def bounds(node):
        if 'artwork' in node:return node['artwork'].get('bounds')
        boxes=[bounds(c) for c in node['children']]
        if not boxes or any(b is None for b in boxes):return None
        return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
    def overlaps(a,b):return a is None or b is None or a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]
    def consolidate(node):
        children=node['children'];paths={c['path'] for c in children if 'path' in c}
        for path in paths:
            segments=[c for c in children if c.get('path')==path]
            if len(segments)<2:continue
            own=bounds({'children':segments});first,last=children.index(segments[0]),children.index(segments[-1])
            if any(overlaps(own,bounds(c)) for c in children[first:last+1] if c.get('path')!=path):continue
            for segment in segments[1:]:segments[0]['children'].extend(segment['children']);children.remove(segment)
        for child in children:
            if 'children' in child:consolidate(child)
    consolidate(tree)
    return tree

class VectorFallback(ValueError):
    pass



def _effective_radius(point_radius, layer_radius_offset=0.0):
    """Grease Pencil's layer Stroke Thickness is an additive radius offset."""
    return max(0.0, float(point_radius) + float(layer_radius_offset))



def _css_font_family(font, directory='', lookup=True, cache=None):
    """Return an SVG family label without embedding or exposing a font file.

    Real files use their internal family name. Missing files retain legacy
    filename-based naming. The original datablock name remains as metadata.
    """
    try:
        from .font_delivery import font_record, resolve_font, system_font_directory
    except ImportError:
        from font_delivery import font_record, resolve_font, system_font_directory
    resolved = resolve_font(font_record(font,cache), directory or system_font_directory(), lookup)
    return resolved['family'], resolved['source_name']



def _text_style_for_index(text_data, index):
    """Blender TextCurve exposes per-character formatting separately."""
    collection = getattr(text_data, 'body_format', ()) or ()
    ch = collection[index] if index < len(collection) else None
    return (bool(getattr(ch, 'use_bold', False)),
            bool(getattr(ch, 'use_italic', False)),
            bool(getattr(ch, 'use_underline', False)),
            bool(getattr(ch, 'use_small_caps', False)),
            int(getattr(ch, 'material_index', 0)))



def _srgb_hex(rgb):
    def channel(c):
        c = max(0.0, min(1.0, float(c)))
        e = 12.92*c if c <= .0031308 else 1.055*c**(1/2.4)-.055
        return int(round(e * 255))
    return '#' + ''.join(f'{channel(c):02x}' for c in rgb[:3])



def _is_visible(obj, view_layer):
    if getattr(obj, 'hide_render', False):
        return False
    try:
        return bool(obj.visible_get(view_layer=view_layer))
    except (AttributeError, TypeError):
        return True



def _camera_visible_objects(view_layer):
    """Return objects from collections contributing camera-visible artwork.

    Indirect Only collections are allowed to affect lights and shadows, but
    their geometry must not force a GP-only source to raster fallback.
    """
    root = getattr(view_layer, 'layer_collection', None)
    if root is None:
        return list(view_layer.objects)
    selected = {}
    def walk(branch, inactive=False):
        if (inactive or getattr(branch, 'exclude', False) or
                getattr(branch.collection, 'hide_render', False)):
            return
        indirect = bool(getattr(branch, 'indirect_only', False))
        if not indirect:
            for obj in getattr(branch.collection, 'objects', ()):
                selected[id(obj)] = obj
        # A child of an Indirect Only branch is indirect too, even if it
        # clears its own flag. Only the camera-visible collection path counts.
        for child in getattr(branch, 'children', ()):
            walk(child, inactive or indirect)
    walk(root)
    return list(selected.values())



def _object_camera_depth(scene, camera, obj):
    """Camera distance of a GP object's bounds centre, for SVG paint order.

    Blender uses the object's bounding-box midpoint as its depth plane for
    2D-layer Grease Pencil ordering. Greater camera-space depth is farther
    away, and SVG must paint farther objects first. Equal depths retain the
    source View Layer's object order, avoiding an arbitrary raster fallback.
    """
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    bounds = getattr(obj, 'bound_box', ()) or ()
    if len(bounds) == 8:
        centre = Vector(tuple(sum(float(p[i]) for p in bounds) / len(bounds)
                              for i in range(3)))
    else:
        centre = Vector((0, 0, 0))
    world = obj.matrix_world @ centre
    depth = float(world_to_camera_view(scene, camera, world).z)
    if not isfinite(depth):
        raise VectorFallback('Invalid Grease Pencil object depth')
    return depth



def _sort_gp_objects(scene, camera, objects):
    """Stable back-to-front ordering; never drop additional GP objects."""
    return sorted(objects, key=lambda obj: -_object_camera_depth(scene, camera, obj['source']))



def _render_size(scene):
    render = scene.render
    # Blender truncates the integer percentage calculation. Rounding can make
    # the vector canvas one pixel larger than the actual PNG cache.
    percentage = int(render.resolution_percentage)
    return (max(1, int(render.resolution_x) * percentage // 100),
            max(1, int(render.resolution_y) * percentage // 100))



def _camera_projection(scene, camera, obj, layer, co):
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    point = Vector(co)
    layer_matrix = getattr(layer, 'matrix_local', None)
    if layer_matrix is not None:
        point = layer_matrix @ point
    world = obj.matrix_world @ point
    n = world_to_camera_view(scene, camera, world)
    if n.z <= 0:
        raise VectorFallback('Shape reaches behind the camera')
    w, h = _render_size(scene)
    return (n.x * w, (1.0 - n.y) * h)



def _uniform(values, reason, tolerance=.00001):
    """A constant GP attribute has a direct SVG paint equivalent."""
    first = values[0]
    if any(abs(a - b) > tolerance for value in values for a, b in zip(first, value)):
        raise VectorFallback(reason)
    return first



def _mixed_color(base, tint):
    factor = max(0.0, min(1.0, float(tint[3])))
    return tuple((1-factor)*base[c] + factor*tint[c] for c in range(3)) + (base[3],)



def _stroke_from_blender(scene, camera, obj, layer, stroke, *, evaluated=False,
                         editable_pressure=False, drawing=None, stroke_index=None):
    # Blender's high-level GP API exposes curve_type as an integer.
    # Blender 5.3 DNA_curves_types.h: 0 = CATMULL_ROM, 1 = POLY,
    # 2 = BEZIER, 3 = NURBS. Interpolated types must not be read as polylines.
    kind = getattr(stroke, 'curve_type', None)
    ctype = {1: 'POLY', 2: 'BEZIER', 'POLY': 'POLY', 'BEZIER': 'BEZIER'}.get(kind)
    if ctype is None:
        raise VectorFallback('Unsupported GP stroke curve type ' + str(kind))
    if abs(float(getattr(stroke, 'softness', 0))) > 0.001:
        raise VectorFallback('Soft stroke gradient requires PNG')
    if abs(float(getattr(stroke, 'aspect_ratio', 1)) - 1) > 0.001:
        raise VectorFallback('Noncircular stroke profile requires PNG')
    style_idx = int(getattr(stroke, 'material_index', 0))
    if style_idx >= len(obj.material_slots):
        raise VectorFallback('Missing Grease Pencil material')
    mat = obj.material_slots[style_idx].material
    style = getattr(mat, 'grease_pencil', None) or getattr(mat, 'gpencil_settings', None)
    if style is None:
        raise VectorFallback('Material has no Grease Pencil style')
    points = []
    radii = []
    vertex_colors = []
    opacities = []
    for point in stroke.points:
        co = _camera_projection(scene, camera, obj, layer, point.position)
        left = right = None
        if ctype == 'BEZIER':
            lh, rh = getattr(point, 'handle_left', None), getattr(point, 'handle_right', None)
            if lh is None or rh is None:
                raise VectorFallback('Bézier handles are not available')
            # Blender exposes GP Bézier handles as Vector coordinates in some
            # builds and as point-like values in others. Both are valid.
            left = _camera_projection(scene, camera, obj, layer, getattr(lh, 'position', lh))
            right = _camera_projection(scene, camera, obj, layer, getattr(rh, 'position', rh))
        points.append({'co': co, 'left': left, 'right': right})
        radii.append(float(getattr(point, 'radius', 0)))
        vertex = getattr(point, 'vertex_color', (0,0,0,0))
        vertex_colors.append(tuple(vertex) if len(vertex) >= 4 else (0,0,0,0))
        opacities.append((float(getattr(point, 'opacity', 1)),))
    if not points:
        raise VectorFallback('Empty Grease Pencil stroke')
    varying_opacity = max(p[0] for p in opacities)-min(p[0] for p in opacities)>.0001
    point_opacity = (1 if editable_pressure and varying_opacity else
                     _uniform(opacities, 'Varying per-point opacity requires PNG')[0])
    vertex_color = ((0,0,0,0) if all(c[3] <= .001 for c in vertex_colors) else
                    _uniform(vertex_colors, 'Varying vertex-colour mixing requires PNG'))
    cyclic = bool(getattr(stroke, 'cyclic', False))
    fill_id = int(getattr(stroke, 'fill_id', 0))
    # Blender 5.1+ controls drawn fills and outlines on the geometry.
    # Material.show_fill/show_stroke are legacy and may be False even while
    # Blender visibly renders a filled shape.
    hide_stroke = bool(getattr(stroke, 'hide_stroke', False))
    if bool(getattr(style, 'use_fill_holdout', False) or getattr(style, 'use_stroke_holdout', False)):
        raise VectorFallback(f'{obj.name}: Holdout material {mat.name!r} requires PNG. '
                             'Fill/Stroke Holdout erases GP paint; it does not enable alpha. '
                             'An object containing only holdouts can render fully transparent. '
                             'For a painted fading sprite, disable Holdout and use Color Ramp stop alpha')
    if getattr(style, 'fill_style', 'SOLID') not in ('SOLID', 'NONE', 'GRADIENT') or getattr(style, 'stroke_style', 'SOLID') not in ('SOLID', 'NONE'):
        raise VectorFallback('Textured Grease Pencil material requires PNG')
    if fill_id and not cyclic:
        raise VectorFallback('Fill has open contour')
    stroke_color = tuple(getattr(style, 'color', getattr(style, 'stroke_color', (0,0,0,1))))
    stroke_color = _mixed_color(stroke_color, vertex_color)
    # Pressure variation matters only for a visible outline. Filled-only
    # curves should remain editable vectors even when point radii vary.
    varying_width = (radii and max(radii)-min(radii)>.0001 and not hide_stroke
                     and float(stroke_color[3])>0)
    if varying_width and not editable_pressure:
        raise VectorFallback('Variable-width visible stroke requires PNG; vector outline baking not implemented')
    fill_color = tuple(getattr(style, 'fill_color', (0,0,0,1)))
    tint = tuple(getattr(stroke, 'fill_color', (0,0,0,0)))
    if len(tint) >= 4 and tint[3] > 0:
        fill_color = _mixed_color(fill_color, tint)
    # Width is determined from an orthographic camera-space unit, independently of viewport size.
    from mathutils import Vector
    unit = camera.matrix_world.to_3x3() @ Vector((1, 0, 0))
    origin = obj.matrix_world @ Vector(stroke.points[0].position)
    from bpy_extras.object_utils import world_to_camera_view
    a = world_to_camera_view(scene, camera, origin)
    b = world_to_camera_view(scene, camera, origin + unit)
    w, h = _render_size(scene)
    px_per_unit = ((b.x-a.x)**2*w*w + (b.y-a.y)**2*h*h)**0.5
    # Evaluated GP drawings already contain layer radius/tint adjustments.
    # The draw shader scales radius by the model matrix's median scale.
    factor=2*px_per_unit*float(getattr(obj.matrix_world,'median_scale',1.0))
    widths=[_effective_radius(radius,0 if evaluated else getattr(layer,'radius_offset',0.0))*factor for radius in radii]
    width=widths[0] if widths else 0
    result = {'type': ctype, 'points': points, 'cyclic': cyclic,
            'fill_id': fill_id, 'fill': _srgb_hex(fill_color),
            'fill_opacity': fill_color[3] * float(getattr(stroke, 'fill_opacity', 1)),
            'stroke': _srgb_hex(stroke_color) if not hide_stroke else '',
            'stroke_opacity': stroke_color[3] * point_opacity, 'width': width, 'material_index': style_idx,
            'fill_linear': fill_color[:3], 'stroke_linear': stroke_color[:3]}
    if fill_id and getattr(style, 'fill_style', 'SOLID') == 'GRADIENT':
        try:
            from . import gp_gradient
        except ImportError:
            import gp_gradient
        if getattr(gp_gradient, 'GRADIENT_API_VERSION', 0) < 2:
            import importlib
            gp_gradient = importlib.reload(gp_gradient)
        result['fill_gradient'] = gp_gradient.fill_gradient(style, stroke, drawing, stroke_index,
            lambda co: _camera_projection(scene, camera, obj, layer, co), tint)
        # The GP shader uses ramp RGBA, independently of the legacy solid
        # fill material's colour/alpha (verified with native render fixtures).
        result['fill_opacity'] = float(getattr(stroke, 'fill_opacity', 1))
    if editable_pressure and (varying_width or varying_opacity):
        result['pressure']={}
        if varying_width:result['pressure']['widths']=widths
        if varying_opacity:result['pressure']['opacities']=[a[0] for a in opacities]
    return result



def _flat_material_color(material):
    """Read material display colour without carrying any external textures."""
    if material is None:
        return '#ffffff', 1.0
    rgba = tuple(getattr(material, 'diffuse_color', (1.0, 1.0, 1.0, 1.0)))
    return _srgb_hex(rgba), max(0.0, min(1.0, float(rgba[3])))



def _object_materials(obj):
    return [_flat_material_color(getattr(slot, 'material', None))
            for slot in getattr(obj, 'material_slots', ())]



def _constant_socket(socket, depth=0):
    """Uniform socket inputs only; procedural/image shading needs raster pixels."""
    if socket is None or depth > 16:
        raise VectorFallback('Text material has an unavailable or cyclic colour input')
    if not socket.is_linked:
        return socket.default_value
    link = socket.links[0]
    node = link.from_node
    if node.bl_idname in ('ShaderNodeRGB', 'ShaderNodeValue'):
        return link.from_socket.default_value
    if node.bl_idname == 'NodeReroute':
        return _constant_socket(node.inputs[0], depth + 1)
    raise VectorFallback('Text material uses a linked texture/procedural input; a uniform SVG fill is unavailable')



def _text_material_rgba(material, *, flat_material=False, engine='CYCLES'):
    if material is None:
        return (1.0, 1.0, 1.0, 1.0)
    tree = getattr(material, 'node_tree', None)
    if tree is None or not getattr(material, 'use_nodes', True):
        return tuple(material.diffuse_color)
    target = 'CYCLES' if engine == 'CYCLES' else 'EEVEE'
    outputs = [n for n in tree.nodes if n.bl_idname == 'ShaderNodeOutputMaterial'
               and n.is_active_output and n.target in ('ALL', target)]
    outputs.sort(key=lambda n: n.target != target)
    if not outputs:
        raise VectorFallback('Text material has no active Material Output')
    output = outputs[0]
    if any(output.inputs[name].is_linked for name in ('Volume', 'Displacement')):
        raise VectorFallback('Text volume/displacement requires PNG')
    surface = output.inputs['Surface']
    for _ in range(17):
        if not surface.is_linked:
            raise VectorFallback('Text material Surface is not connected')
        shader = surface.links[0].from_node
        if shader.bl_idname != 'NodeReroute':
            break
        surface = shader.inputs[0]
    else:
        raise VectorFallback('Text material has a cyclic shader connection')
    if shader.bl_idname == 'ShaderNodeEmission':
        rgb = _constant_socket(shader.inputs['Color'])
        strength = float(_constant_socket(shader.inputs['Strength']))
        alpha = 1.0  # Emission Color's alpha does not make its surface transparent.
    elif shader.bl_idname == 'ShaderNodeBsdfPrincipled' and flat_material:
        rgb = _constant_socket(shader.inputs['Base Color'])
        strength = 1.0
        alpha = float(_constant_socket(shader.inputs['Alpha']))
    else:
        raise VectorFallback('Editable text needs a flat Emission material. For Principled Base Color, enable Use Flat Text Colour in the SVG output; the Blender material is unchanged')
    if isinstance(rgb, (float, int)):
        rgb = (rgb, rgb, rgb)
    rgba = tuple(float(c) * max(0.0, strength) for c in rgb[:3]) + (max(0.0, min(1.0, alpha)),)
    if len(rgba) != 4 or not all(isfinite(c) for c in (*rgba, strength, alpha)):
        raise VectorFallback('Text material colour/opacity is invalid')
    return rgba



def _curve_from_blender(scene, camera, obj):
    """Vectorise flat Blender Curve splines; refuse 3D shapes and modifiers."""
    data = obj.data
    if str(getattr(data, 'dimensions', '2D')) != '2D':
        raise VectorFallback('3D Curve geometry requires rendered PNG')
    if float(getattr(data, 'extrude', 0)) or float(getattr(data, 'bevel_depth', 0)):
        raise VectorFallback('Extruded or bevelled Curve requires PNG')
    if abs(float(getattr(data, 'offset', 0))) > .000001:
        raise VectorFallback('Offset Curve outlines require PNG')
    if getattr(data, 'bevel_object', None) is not None or getattr(data, 'taper_object', None) is not None:
        raise VectorFallback('Curve bevel or taper object requires PNG')
    if float(getattr(data, 'bevel_factor_start', 0)) > .000001 or float(getattr(data, 'bevel_factor_end', 1)) < .999999:
        raise VectorFallback('Trimmed Curve geometry requires PNG')
    if getattr(obj, 'modifiers', None) and any(getattr(m, 'show_render', True) for m in obj.modifiers):
        raise VectorFallback('Modified Curve requires PNG')
    colors = _object_materials(obj)
    linear_colors=[tuple(getattr(getattr(slot,'material',None),'diffuse_color',(1,1,1,1)))[:3]
                   for slot in getattr(obj,'material_slots',())]
    if not colors:
        colors = [('#ffffff', 1.0)]
        linear_colors=[(1,1,1)]
    splines=[]
    for spline in getattr(data, 'splines', ()):
        ctype = str(getattr(spline, 'type', ''))
        if ctype not in ('BEZIER','POLY'):
            raise VectorFallback(f'Curve {ctype} requires evaluated raster fallback')
        cyclic=bool(getattr(spline, 'use_cyclic_u', False))
        if not cyclic:
            # Blender un-bevelled open Curve lines have no rendered stroke;
            # authoring a visible SVG stroke here would invent artwork.
            raise VectorFallback('Open Curve has no native 2D rendered stroke')
        points=[]
        collection = spline.bezier_points if ctype == 'BEZIER' else spline.points
        for p in collection:
            co=getattr(p,'co', (0,0,0))
            if ctype == 'POLY' and len(co) >= 4 and abs(float(co[3])) > 1e-8:
                co = tuple(float(v)/float(co[3]) for v in co[:3])
            else:
                co=co[:3]
            entry={'co':_camera_projection(scene,camera,obj,None,co)}
            if ctype == 'BEZIER':
                entry['left']=_camera_projection(scene,camera,obj,None,p.handle_left)
                entry['right']=_camera_projection(scene,camera,obj,None,p.handle_right)
            points.append(entry)
        if len(points)<(2 if ctype=='BEZIER' else 3):
            raise VectorFallback('Insufficient points for vector curve')
        material_id=int(getattr(spline,'material_index',0))
        if material_id >= len(colors):
            raise VectorFallback('Curve spline material index unavailable')
        color,alpha=colors[material_id]
        splines.append({'points':points,'type':ctype,'cyclic':True,'fill':color,'opacity':alpha,
                        'fill_linear':linear_colors[material_id]})
    if not splines:
        raise VectorFallback('Curve has no visible closed splines')
    return {'svg_kind':'CURVE','name':obj.name,'splines':splines,
            'fill_rule':'evenodd' if str(getattr(data,'fill_rule','EVEN_ODD'))=='EVEN_ODD' else 'nonzero',
            'source':obj}



def _font_from_blender(scene, camera, obj, *, flat_material=False, font_directory='',
                        use_font_directory=True, font_cache=None):
    """Prepare editable text content, paint and its projected object transform."""
    data=obj.data
    if not str(getattr(data, 'body', '')):
        raise VectorFallback('Text object is empty')
    if float(getattr(data, 'extrude', 0)) or float(getattr(data, 'bevel_depth', 0)):
        raise VectorFallback('Extruded or bevelled text requires PNG')
    if getattr(data,'follow_curve',None) is not None:
        raise VectorFallback('Text following a Curve requires PNG')
    if getattr(data, 'family', ''):
        raise VectorFallback('Object-based Text character family requires PNG')
    if abs(float(getattr(data, 'offset', 0))) > .000001:
        raise VectorFallback('Offset Text outlines require PNG')
    if str(getattr(data,'overflow','NONE')) != 'NONE':
        raise VectorFallback('Text box overflow or text-fit requires PNG')
    if str(getattr(data,'align_x','LEFT')) in ('JUSTIFY','FLUSH'):
        raise VectorFallback('Justified text layout requires PNG for exact appearance')
    if getattr(obj,'modifiers',None) and any(getattr(m,'show_render',True) for m in obj.modifiers):
        raise VectorFallback('Modified text geometry requires PNG')
    # SVG live text will not reproduce 3D illumination of a Blender shader.
    # Preserve flat colour; other material channels need a rendered PNG.
    if getattr(data,'text_boxes',None):
        for box in data.text_boxes:
            if float(getattr(box,'width',0)) > 0 or float(getattr(box,'height',0)) > 0:
                raise VectorFallback('Multi-column or bounded text box requires PNG')
    offsets=[]
    for point in ((0,0,0),(1,0,0),(0,1,0)):
        offsets.append(_camera_projection(scene,camera,obj,None,point))
    origin,x,y=offsets
    # SVG glyphs extend towards negative local y; Blender glyphs extend
    # towards positive local y. Invert the local vertical basis.
    matrix=(x[0]-origin[0],x[1]-origin[1], origin[0]-y[0],origin[1]-y[1],origin[0],origin[1])
    family, original_font = _css_font_family(getattr(data,'font',None), font_directory,
                                            use_font_directory, font_cache)
    try:
        from .font_delivery import font_record,resolve_font,font_names
        from .builtin_font import compatible_bfont
    except ImportError:
        from font_delivery import font_record,resolve_font,font_names
        from builtin_font import compatible_bfont
    resolved=resolve_font(font_record(getattr(data,'font',None),font_cache),font_directory,use_font_directory)
    font_file=resolved.get('file','')
    if font_file and resolved.get('builtin') and font_cache:
        modern=compatible_bfont(Path(font_file).read_bytes())
        if modern:
            target=Path(font_cache)/'fonts'/'Bfont-Regular.otf';target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists() or target.read_bytes()!=modern:target.write_bytes(modern)
            font_file=str(target)
    names=font_names(font_file) if font_file else {}
    variants = {}
    for bold, italic, key in ((True,False,'bold'),(False,True,'italic'),(True,True,'bolditalic')):
        variant = getattr(data, 'font_' + key if key != 'bolditalic' else 'font_bold_italic', None)
        if variant is not None:
            variants[key] = _css_font_family(variant,font_directory,use_font_directory,font_cache)[0]
    engine = getattr(getattr(scene, 'render', None), 'engine', 'CYCLES')
    formatted=[_text_style_for_index(data,i) for i in range(len(data.body))]
    used_materials = {style[4] for style in formatted}
    linear_colors = [(_text_material_rgba(getattr(slot, 'material', None),
                                         flat_material=flat_material, engine=engine)
                      if index in used_materials else (1.0,1.0,1.0,1.0))
                     for index, slot in enumerate(getattr(obj, 'material_slots', ()))] or [(1.0,1.0,1.0,1.0)]
    colors = [(_srgb_hex(rgba), rgba[3]) for rgba in linear_colors]
    if any(style[4] >= len(colors) for style in formatted):
        raise VectorFallback('Text character material missing')
    return {'svg_kind':'FONT','name':obj.name,'body':data.body,
            'family':family,'font_source':original_font,'font_variants':variants,
            'font_file':font_file,'font_postscript':names.get('postscript') or family,
            'font_builtin':getattr(getattr(data,'font',None),'filepath','')=='<builtin>',
            'font_substituted':False,
            'size':float(getattr(data,'size',1)),
            'align':str(getattr(data,'align_x','LEFT')),
            'align_y':str(getattr(data,'align_y','TOP_BASELINE')),
            'space_character':float(getattr(data,'space_character',1)),
            'space_word':float(getattr(data,'space_word',1)),
            'space_line':float(getattr(data,'space_line',1)),
            'shear':float(getattr(data,'shear',0)),
            'offset_x':float(getattr(data,'offset_x',0)),
            'offset_y':float(getattr(data,'offset_y',0)),
            'matrix':matrix,'fill':colors[0][0],'opacity':colors[0][1],
            'formats':formatted,'material_colors':colors,
            'material_linear_colors':linear_colors,
            'kerning':[float(getattr(ch, 'kerning', 0)) for ch in getattr(data, 'body_format', ())],
            'small_caps_scale':float(getattr(data, 'small_caps_scale', .75)),
            'underline_height':float(getattr(data, 'underline_height', .05)),
            'underline_position':float(getattr(data, 'underline_position', 0)),
            'source':obj}



def _iter_gp_layers(gp):
    # Blender 5.1 root_nodes includes nested layer groups; leaf layers expose current_frame().
    def descend(nodes):
        for node in nodes:
            if getattr(node, 'hide', False):
                continue
            if hasattr(node, 'children'):
                yield from descend(node.children)
            else:
                yield node
    nodes = getattr(gp, 'root_nodes', None)
    if nodes is None:
        nodes = gp.layers
    yield from descend(nodes)



def _gp_from_blender(scene, camera, obj, view_layer, skipped_layers=None, *, evaluated=False,
                     editable_layer_blends=False, editable_pressure=False):
    """One whole GP object; unsupported parts reject this object together."""
    skipped_layers = [] if skipped_layers is None else skipped_layers
    if getattr(view_layer, 'use_grease_pencil', True) is False:
        raise VectorFallback('Grease Pencil disabled in source View Layer')
    for mod in getattr(obj, 'modifiers', ()):
        if not evaluated and getattr(mod, 'show_render', True):
            raise VectorFallback(
                f'{obj.name}: active Grease Pencil modifier '
                f'{getattr(mod, "name", "(unnamed)")} requires PNG'
            )
    if getattr(obj, 'shader_effects', None) and len(obj.shader_effects):
        raise VectorFallback('Grease Pencil effects require PNG')
    gp_layers = []
    for layer in _iter_gp_layers(obj.data):
        # A drawing layer can be limited to a particular View Layer,
        # independently of the GP object's Collection visibility.
        assigned = str(getattr(layer, 'viewlayer_render', '') or '')
        if assigned and assigned != view_layer.name:
            skipped_layers.append(f'{obj.name}/{layer.name} assigned to {assigned}')
            continue
        # Blender has independent Grease Pencil lighting switches on
        # the object and its drawing layer. The flat SVG style remains
        # faithful when either switch is off. Checking only the layer
        # rejected unlit objects created by Blender's GP defaults.
        if (getattr(obj, 'use_grease_pencil_lights', True)
                and getattr(layer, 'use_lights', False)):
            raise VectorFallback(
                f'{obj.name}/{layer.name}: Grease Pencil lighting is enabled '
                '(Object > Visibility > Grease Pencil > Use Lights and '
                'Layer Properties > Lights). Disable lighting on the '
                'object or layer for a flat-colour SVG, or bake to PNG.'
            )
        blend_mode = getattr(layer, 'blend_mode', 'REGULAR')
        if blend_mode not in ('REGULAR', 'NORMAL'):
            if blend_mode not in SUPPORTED_GP_BLENDS:
                raise VectorFallback(f'Grease Pencil {blend_mode} layer blend requires PNG; no supported SVG equivalent')
            if not editable_layer_blends:
                raise VectorFallback(f'Grease Pencil {blend_mode} layer blend requires PNG to retain Blender appearance')
        if getattr(layer, 'layer_masks', None) and len(layer.layer_masks):
            raise VectorFallback('Grease Pencil masks require PNG in this phase')
        if getattr(layer, 'use_masks', False):
            raise VectorFallback('Grease Pencil masks require PNG')
        frame = layer.current_frame() if hasattr(layer, 'current_frame') else None
        if frame is None or getattr(frame, 'drawing', None) is None:
            skipped_layers.append(f'{obj.name}/{layer.name} has no drawing on frame {getattr(scene, 'frame_current', '?')}')
            continue
        strokes = [_stroke_from_blender(scene, camera, obj, layer, stroke, evaluated=evaluated,
                    editable_pressure=editable_pressure, drawing=frame.drawing, stroke_index=index)
                   for index, stroke in enumerate(frame.drawing.strokes)]
        # Blender uses the first contour's UV frame for every contour of a
        # compound fill, including its holes.
        gradients = {}
        for stroke in strokes:
            if stroke.get('fill_gradient'):
                stroke['fill_gradient'] = gradients.setdefault(stroke['fill_id'], stroke['fill_gradient'])
        if strokes:
            gp_layers.append({'name': layer.name, 'opacity': layer.opacity,
                              'blend_mode': blend_mode, 'strokes': strokes})
    if gp_layers:
        if not any(stroke.get('fill_id') or stroke.get('stroke')
                   for lyr in gp_layers for stroke in lyr['strokes']):
            raise VectorFallback('No drawable fills or strokes in Grease Pencil source')
        return {'name': obj.name, 'layers': gp_layers, 'source': obj}
    return None



def _visible_outline(stroke):
    return (bool(stroke.get('stroke')) and not stroke.get('hide_stroke')
            and float(stroke.get('stroke_opacity',1))>0 and float(stroke.get('width',0))>0)

def prepare_pressure(stroke):
    pressure = stroke.get('pressure')
    if not pressure:
        return
    if stroke['cyclic'] or stroke.get('fill_id') or not _visible_outline(stroke):
        raise VectorFallback('Editable pressure requires an open visible stroke without a fill')
    points = stroke['points']
    if len(points) < 2:
        raise VectorFallback('Editable pressure requires at least two points')
    if pressure.get('opacities'):
        for axis in sorted((0,1),key=lambda a:abs(points[-1]['co'][a]-points[0]['co'][a]),reverse=True):
            start,end = points[0]['co'][axis],points[-1]['co'][axis]
            if abs(end-start)<1e-6:
                continue
            stops=[(p['co'][axis]-start)/(end-start) for p in points]
            if any(b-a<1e-7 for a,b in zip(stops,stops[1:])):
                continue
            if stroke['type']=='BEZIER' and any(
                    not (a['co'][axis]/(end-start)<=a['right'][axis]/(end-start)
                         <=b['left'][axis]/(end-start)<=b['co'][axis]/(end-start))
                    for a,b in zip(points,points[1:])):
                continue
            pressure['gradient']=dict(axis=axis,start=start,end=end,stops=stops)
            break
        else:
            raise VectorFallback('Point opacity on a looping or reversing stroke requires PNG; no monotonic SVG gradient axis')
    if pressure.get('widths'):
        # Reject sharp polygon joints rather than introducing miter spikes.
        if stroke['type']=='POLY':
            tangents=[]
            for a,b in zip(points,points[1:]):
                dx,dy=(b['co'][i]-a['co'][i] for i in (0,1));length=hypot(dx,dy)
                if length<1e-7:
                    raise VectorFallback('Repeated pressure points require PNG')
                tangents.append((dx/length,dy/length))
            if any(sum(x*y for x,y in zip(a,b))<cos(pi/4) for a,b in zip(tangents,tangents[1:])):
                raise VectorFallback('Sharp polygon pressure joints require PNG')
        pressure['outline']=pressure_outline(stroke)


def pressure_outline(stroke):
    """Portable filled fallback for linear width along cubic/polygon segments."""
    points=stroke['points'];widths=stroke['pressure']['widths'];samples=[]
    for index,(a,b) in enumerate(zip(points,points[1:])):
        count=32 if stroke['type']=='BEZIER' else 1
        for step in range(count+1):
            if index and step==0:
                continue
            t=step/count;u=1-t
            if stroke['type']=='BEZIER':
                p,q,r,s=a['co'],a['right'],b['left'],b['co']
                co=tuple(u**3*p[k]+3*u*u*t*q[k]+3*u*t*t*r[k]+t**3*s[k] for k in (0,1))
                tangent=tuple(3*u*u*(q[k]-p[k])+6*u*t*(r[k]-q[k])+3*t*t*(s[k]-r[k]) for k in (0,1))
            else:
                co=tuple(u*a['co'][k]+t*b['co'][k] for k in (0,1))
                tangent=tuple(b['co'][k]-a['co'][k] for k in (0,1))
            if hypot(*tangent)<1e-8:
                tangent=tuple(b['co'][k]-a['co'][k] for k in (0,1))
            angle=atan2(tangent[1],tangent[0]);radius=(u*widths[index]+t*widths[index+1])/2
            samples.append((co,angle,radius))
    left=[(co[0]-sin(a)*r,co[1]+cos(a)*r) for co,a,r in samples]
    right=[(co[0]+sin(a)*r,co[1]-cos(a)*r) for co,a,r in reversed(samples)]
    def cap(sample,start):
        co,a,r=sample
        return [(co[0]+cos(a+start-pi*i/16)*r,co[1]+sin(a+start-pi*i/16)*r) for i in range(1,16)]
    contour=left+cap(samples[-1],pi/2)+right+cap(samples[0],-pi/2)
    return [dict(co=p) for p in contour]



def scene_colors(scene, objects, directory, save_as_render):
    """Use Blender's actual OCIO/view settings for flat GP and text colours.

    Alpha stays separate. An opaque float palette prevents Blender's associated
    alpha conversion from altering the colour samples during save_render.
    """
    import bpy
    import tempfile
    try:
        from .png16_pixels import read_png16_rgba
    except ImportError:
        from png16_pixels import read_png16_rgba
    import numpy as np
    strokes = [s for o in objects for layer in o.get('layers', []) for s in layer['strokes']]
    fonts = [o for o in objects if o.get('svg_kind') == 'FONT']
    colors = list(dict.fromkeys(
        [tuple(s[key]) for s in strokes
         for key in ('fill_linear', 'stroke_linear') if key in s] +
        [tuple(rgba[:3]) for o in fonts for rgba in o.get('material_linear_colors', [])] +
        [tuple(stop['linear']) for s in strokes for stop in s.get('fill_gradient', {}).get('stops', [])]))
    if not colors:
        return
    staging = scene.copy()
    staging.name = PRIVATE_PREFIX + 'SVG_Colors'
    image = None
    try:
        settings = staging.render.image_settings
        settings.media_type = 'IMAGE'
        settings.file_format = 'PNG'
        settings.color_mode = 'RGB'
        settings.color_depth = '16'
        settings.color_management = 'FOLLOW_SCENE'
        staging.render.dither_intensity = 0
        if not save_as_render:
            staging.view_settings.view_transform = 'Standard'
            staging.view_settings.look = 'None'
            staging.view_settings.exposure = 0
            staging.view_settings.gamma = 1
            staging.view_settings.use_curve_mapping = False
        image = bpy.data.images.new(PRIVATE_PREFIX + 'SVG_Palette', width=len(colors), height=1,
                                    alpha=True, float_buffer=True)
        pixels = np.ones((len(colors), 4), np.float32)
        pixels[:, :3] = colors
        image.pixels.foreach_set(pixels.ravel())
        image.update()
        with tempfile.TemporaryDirectory(prefix='palette-', dir=str(directory)) as folder:
            path = Path(folder) / 'palette.png'
            image.save_render(str(path), scene=staging)
            samples = read_png16_rgba(path)[0, :, :3]
        encoded = {color: 'rgb(' + ','.join(f'{float(c)*100:.6f}%' for c in sample) + ')'
                   for color, sample in zip(colors, samples)}
        for stroke in strokes:
            for stop in stroke.get('fill_gradient', {}).get('stops', []):
                stop['color'] = encoded[tuple(stop['linear'])]
            for paint in ('fill', 'stroke'):
                if stroke.get(paint) and paint + '_linear' in stroke:
                    stroke[paint] = encoded[tuple(stroke[paint + '_linear'])]
        for font in fonts:
            if font.get('material_linear_colors'):
                font['material_colors'] = [(encoded[tuple(rgba[:3])], float(rgba[3]))
                                           for rgba in font['material_linear_colors']]
                font['fill'], font['opacity'] = font['material_colors'][0]
    finally:
        if image is not None:
            bpy.data.images.remove(image)
        bpy.data.scenes.remove(staging)

