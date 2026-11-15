"""Blender's evaluated outline geometry for flat variable-radius GP strokes."""

try:
    from .runtime_paths import PRIVATE_PREFIX
except ImportError:
    from runtime_paths import PRIVATE_PREFIX
from math import dist, cos, radians


def _smooth_profile(strokes):
    # Blender's Outline geometry differs visibly from the draw shader for
    # sparse corners and steep pressure changes. Keep those cases raster.
    for stroke in strokes:
        points=stroke['points']
        if len(points)<16:return False
        tangents=[]
        for a,b in zip(points,points[1:]):
            length=dist(a['position'],b['position'])
            if length<1e-8 or abs(a['radius']-b['radius'])/length>.08:return False
            tangents.append(tuple((y-x)/length for x,y in zip(a['position'],b['position'])))
        if any(sum(x*y for x,y in zip(a,b))<cos(radians(40))
               for a,b in zip(tangents,tangents[1:])):return False
    return True


def expanded_stroke(scene,view_layer,obj,graph):
    import bpy
    try:
        from . import vector_artwork as vectors
    except ImportError:
        import vector_artwork as vectors
    evaluated=obj.evaluated_get(graph)
    if any(m.show_render for m in obj.modifiers):
        raise vectors.VectorFallback('Variable-width strokes with modifiers require PNG')
    layers=list(vectors._iter_gp_layers(evaluated.data))
    if len(layers)!=1:
        raise vectors.VectorFallback('Variable-width outline expansion currently requires one GP layer')
    frame=layers[0].current_frame()
    strokes=list(frame.drawing.strokes) if frame else []
    if not strokes or any(s.fill_id or s.hide_stroke for s in strokes):
        raise vectors.VectorFallback('Variable-width fill/stroke combinations require PNG')
    if any(s.cyclic for s in strokes):
        raise vectors.VectorFallback('Closed variable-width strokes require PNG to preserve the inner contour')
    indices={s.material_index for s in strokes}
    if len(indices)!=1:
        raise vectors.VectorFallback('Variable-width multi-material strokes require PNG')
    points=[p for s in strokes for p in s.points]
    if any(p.vertex_color[3]>.001 for p in points):
        raise vectors.VectorFallback('Variable-width vertex-colour mixing requires PNG')
    opacity=vectors._uniform([(p.opacity,) for p in points],'Varying per-point opacity requires PNG')[0]
    color=tuple(evaluated.data.materials[next(iter(indices))].grease_pencil.color)
    source=[dict(cyclic=bool(s.cyclic),points=[dict(position=list(p.position),radius=p.radius) for p in s.points]) for s in strokes]
    if not _smooth_profile(source):
        raise vectors.VectorFallback('Sparse or sharply varying pressure strokes require PNG for faithful appearance')
    copy=None;data=None;material=None
    try:
        copy=obj.copy();data=obj.data.copy();copy.data=data
        scene.collection.objects.link(copy)
        material=bpy.data.materials.new(PRIVATE_PREFIX + 'WidthFill')
        bpy.data.materials.create_gpencil_data(material)
        material.grease_pencil.show_fill=True
        material.grease_pencil.show_stroke=False
        material.grease_pencil.color=(0,0,0,0)
        material.grease_pencil.fill_color=(*color[:3],color[3]*opacity)
        data.materials.append(material)
        modifier=copy.modifiers.new(PRIVATE_PREFIX + 'ExpandWidth','GREASE_PENCIL_OUTLINE')
        modifier.outline_material=material;modifier.subdivision=3
        graph.update()
        artwork=vectors._gp_from_blender(scene,scene.camera.evaluated_get(graph),
                                         copy.evaluated_get(graph),view_layer,evaluated=True)
        if not artwork:
            raise vectors.VectorFallback('Variable-width outline generated no visible geometry')
        artwork['name']=obj.name
        artwork['expanded_stroke']=source
        artwork.pop('source',None)
        return artwork
    finally:
        if copy is not None:bpy.data.objects.remove(copy,do_unlink=True)
        if data is not None:bpy.data.grease_pencils.remove(data)
        if material is not None:bpy.data.materials.remove(material)
        graph.update()
