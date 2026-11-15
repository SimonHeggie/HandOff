"""Conservative SVG footprints for safe collection consolidation."""

try:
    from .runtime_paths import PRIVATE_PREFIX
except ImportError:
    from runtime_paths import PRIVATE_PREFIX
import math


def artwork_bounds(artwork):
    if artwork.get('svg_kind') in ('FONT','RASTER','CURVE'):return None
    points=[];pad=1.0
    for layer in artwork.get('layers',[]):
        for stroke in layer['strokes']:
            pad=max(pad,max(stroke.get('pressure',{}).get('widths') or [float(stroke.get('width',0))])/2+1)
            for point in stroke['points']:
                points.extend(point[key] for key in ('co','left','right') if point.get(key) is not None)
    if not points:return [0,0,0,0]
    return [min(p[0] for p in points)-pad,min(p[1] for p in points)-pad,
            max(p[0] for p in points)+pad,max(p[1] for p in points)+pad]


def text_bounds(scene,view_layer,rows,directory,lookup,cache):
    """Measure simple live text with its resolved font in the private worker.

    Unknown/complex layouts keep their original ordering. The one-em margin
    accounts for baseline/layout differences between Blender and SVG readers.
    No measured geometry replaces the live SVG text.
    """
    import bpy
    try:
        from .font_delivery import font_record,resolve_font,system_font_directory
    except ImportError:
        from font_delivery import font_record,resolve_font,system_font_directory
    copies=[];before_fonts={f.as_pointer() for f in bpy.data.fonts}
    try:
        for row in rows:
            if row['kind']!='vector':continue
            info=row['artwork']
            if info.get('svg_kind')!='FONT':continue
            if (not info['body'].isascii() or '\n' in info['body'] or info.get('shear') or
                    info.get('align_y') not in ('TOP_BASELINE','BOTTOM_BASELINE') or
                    info.get('space_character',1)!=1 or info.get('space_word',1)!=1 or
                    any(any(s[:4]) for s in info.get('formats',[])) or any(info.get('kerning',[]))):continue
            source=scene.objects.get(row['name'])
            resolved=resolve_font(font_record(source.data.font,cache),directory or system_font_directory(),lookup)
            if not resolved['file']:continue
            data=source.data.copy();data.animation_data_clear();data.body=info['body'];data.size=info['size']
            data.align_x=info['align'];data.align_y=info['align_y']
            data.offset_x=info.get('offset_x',0);data.offset_y=info.get('offset_y',0)
            obj=None
            try:
                data.font=bpy.data.fonts.load(resolved['file'],check_existing=True)
                obj=bpy.data.objects.new(PRIVATE_PREFIX + 'FontBounds',data);scene.collection.objects.link(obj)
                obj.hide_render=True
                copies.append((obj,data,info))
            except BaseException:
                if obj is not None:bpy.data.objects.remove(obj,do_unlink=True)
                bpy.data.curves.remove(data)
                raise
        if not copies:return
        graph=view_layer.depsgraph;graph.update()
        for obj,data,info in copies:
            a,b,c,d,e,f=info['matrix']
            points=[(a*p[0]-c*p[1]+e,b*p[0]-d*p[1]+f)
                    for p in obj.evaluated_get(graph).bound_box]
            pad=info['size']*max(math.hypot(a,b),math.hypot(c,d))+1
            info['bounds']=[min(p[0] for p in points)-pad,min(p[1] for p in points)-pad,
                            max(p[0] for p in points)+pad,max(p[1] for p in points)+pad]
    finally:
        for obj,data,_ in copies:
            bpy.data.objects.remove(obj,do_unlink=True);bpy.data.curves.remove(data)
        for font in list(bpy.data.fonts):
            if font.as_pointer() not in before_fonts and font.users==0:bpy.data.fonts.remove(font)


def image_bounds(path):
    from PIL import Image
    if path.read_bytes()[24]==16:
        try:
            from .png16_pixels import read_png16_rgba
        except ImportError:
            from png16_pixels import read_png16_rgba
        import numpy as np
        ys,xs=np.nonzero(read_png16_rgba(path)[...,3]>0)
        return [int(xs.min())-1,int(ys.min())-1,int(xs.max())+2,int(ys.max())+2] if len(xs) else [0,0,0,0]
    with Image.open(path) as image:
        box=image.getchannel('A').getbbox()
    return [box[0]-1,box[1]-1,box[2]+1,box[3]+1] if box else [0,0,0,0]
