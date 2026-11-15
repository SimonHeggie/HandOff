"""Photoshop-only shape, gradient, stroke and type records.

Consumes the same detached camera-space artwork cache as SVG. Pixel channels
are compatibility previews at the document depth; paths and paint descriptors
remain authoritative and editable in Photoshop. No PSD backend is replaced.
"""

try:
    from .branding import LOG_PREFIX
except ImportError:
    from branding import LOG_PREFIX
import json
import math
import re
from pathlib import Path
try:
    from .export_performance import timed
except ImportError:
    from export_performance import timed

PSD_VECTOR_API_VERSION=1


def bind_source(container,obj,layers):
    """Bind native PSD layer IDs to the same source UUIDs carried by SVG."""
    if not obj.get('source_metadata'):return []
    import hashlib
    from xml.etree import ElementTree as ET
    from psd_tools.constants import Tag,Resource
    from psd_tools.psd.image_resources import ImageResource
    from svg_metadata import NS
    document=container._psd;ids=[];used={layer.layer_id for layer in document.descendants()}
    nodes=[]
    for layer in layers:
        nodes.append(layer)
        if hasattr(layer,'descendants'):nodes.extend(layer.descendants())
    for i,layer in enumerate(nodes):
        key=(obj['source_metadata']['object_id'],obj['name'],i)
        identity=int.from_bytes(hashlib.sha256(str(key).encode()).digest()[:4],'big')&0x7fffffff
        identity=max(identity,1)
        while identity in used:identity=identity%0x7fffffff+1
        layer.tagged_blocks.set_data(Tag.LAYER_ID,identity);used.add(identity);ids.append(identity)
    resources=document.image_resources;data=resources.get_data(Resource.XMP_METADATA)
    root=ET.fromstring(data) if data else ET.Element('{adobe:ns:meta/}xmpmeta')
    rdf=root.find('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF')
    if rdf is None:rdf=ET.SubElement(root,'{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF')
    desc=ET.SubElement(rdf,'{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')
    ET.SubElement(desc,'{'+NS+'}binding',{'schema':'1'}).text=json.dumps(dict(source=obj['source_metadata'],
        layer_ids=ids,source_name=obj['name'],shared_instance=obj.get('svg_instance',{}).get('key','')),ensure_ascii=False)
    resources[Resource.XMP_METADATA]=ImageResource(key=Resource.XMP_METADATA,data=ET.tostring(root,encoding='utf-8'))
    return ids


def rgb(paint,depth=8):
    if depth==32 and paint.get('linear') is not None:return tuple(paint['linear'])
    value=paint.get('color','#000000')
    if value.startswith('#'):return tuple(int(value[i:i+2],16)/255 for i in (1,3,5))
    values=re.findall(r'[-\d.]+',value)
    return tuple(float(v)/(100 if '%' in value else 255) for v in values[:3])


def _color(values):
    from psd_tools.psd.descriptor import Descriptor,Double
    return Descriptor(classID=b'RGBC',items={k:Double(float(v)*255) for k,v in zip((b'Rd  ',b'Grn ',b'Bl  '),values)})


def _solid(values):
    from psd_tools.psd.descriptor import Descriptor
    return Descriptor(classID=b'solidColorLayer',items={b'Clr ':_color(values)})


def _gradient(paint,values):
    from psd_tools.psd.descriptor import Descriptor,Double,Integer,List,Enumerated,String as UnicodeString,UnitFloat,Bool
    from psd_tools.terminology import Unit
    pressure=paint['pressure'];profile=pressure['gradient'];opacities=pressure['opacities']
    colors=[Descriptor(classID=b'Clrt',items={b'Clr ':_color(values),b'Type':Enumerated(b'Clry',b'UsrS'),
             b'Lctn':Integer(n),b'Mdpn':Integer(50)}) for n in (0,4096)]
    transparency=[Descriptor(classID=b'TrnS',items={b'Opct':UnitFloat(a*100,Unit.Percent),
                   b'Lctn':Integer(round(t*4096)),b'Mdpn':Integer(50)}) for t,a in zip(profile['stops'],opacities)]
    ramp=Descriptor(classID=b'Grdn',items={b'Nm  ':UnicodeString('Grease Pencil opacity'),
         b'GrdF':Enumerated(b'GrdF',b'CstS'),b'Intr':Double(4096),b'Clrs':List(colors),b'Trns':List(transparency)})
    angle=0 if profile['axis']==0 else -90
    if profile['end']<profile['start']:angle+=180
    return Descriptor(classID=b'gradientLayer',items={b'Grad':ramp,b'Angl':UnitFloat(angle,Unit.Angle),
        b'Type':Enumerated(b'GrdT',b'Lnr '),b'Rvrs':Bool(False),b'Dthr':Bool(True),b'Algn':Bool(True),
        b'Scl ':UnitFloat(100,Unit.Percent),
        b'Ofst':Descriptor(classID=b'Pnt ',items={b'Hrzn':UnitFloat(0,Unit.Percent),b'Vrtc':UnitFloat(0,Unit.Percent)})})


def _mask(contours,width,height):
    from psd_tools.psd.vector import (Path as VPath,PathFillRule,InitialFillRule,
        OpenPath,ClosedPath,OpenKnotUnlinked,ClosedKnotUnlinked)
    records=[PathFillRule(),InitialFillRule(0)]
    for contour in contours:
        closed=contour.get('cyclic',False);knot=ClosedKnotUnlinked if closed else OpenKnotUnlinked
        def xy(p):return (float(p[1])/height,float(p[0])/width)
        knots=[knot(preceding=xy(p.get('left') or p['co']),anchor=xy(p['co']),
                    leaving=xy(p.get('right') or p['co'])) for p in contour['points']]
        records.append((ClosedPath if closed else OpenPath)(items=knots,operation=0))
    return VPath(records)


def _dot(paint):
    """A GP one-point dash is a filled circle, not a Photoshop one-node path."""
    contour=paint['contours'][0]
    if paint['kind']!='stroke' or len(contour['points'])!=1:return paint
    x,y=contour['points'][0]['co'];r=paint['width']/2;k=r*.5522847498307936
    points=[dict(co=(x+r,y),left=(x+r,y-k),right=(x+r,y+k)),
            dict(co=(x,y+r),left=(x+k,y+r),right=(x-k,y+r)),
            dict(co=(x-r,y),left=(x-r,y+k),right=(x-r,y-k)),
            dict(co=(x,y-r),left=(x-k,y-r),right=(x+k,y-r))]
    return dict(paint,kind='fill',contours=[dict(points=points,type='BEZIER',cyclic=True)])


def _preview(paint,width,height,depth):
    """Compatibility channels only; the cubic path records are not sampled."""
    import numpy as np
    from PIL import Image,ImageDraw
    from vector_artwork import flatten_contour
    contours=[flatten_contour(c) for c in paint['contours']]
    points=[p for contour in contours for p in contour]
    pad=paint.get('width',0)/2+2
    left=max(0,math.floor(min(p[0] for p in points)-pad));right=min(width,math.ceil(max(p[0] for p in points)+pad))
    top=max(0,math.floor(min(p[1] for p in points)-pad));bottom=min(height,math.ceil(max(p[1] for p in points)+pad))
    if right<=left or bottom<=top:return None
    scale=4;size=((right-left)*scale,(bottom-top)*scale)
    mask=Image.new('L',size)
    if paint['kind']=='fill':
        combined=np.zeros((size[1],size[0]),dtype=np.uint8)
        for contour in contours:
            part=Image.new('L',size);ImageDraw.Draw(part).polygon([((x-left)*scale,(y-top)*scale) for x,y in contour],fill=255)
            combined^=np.asarray(part)
        mask=Image.fromarray(combined)
    else:
        draw=ImageDraw.Draw(mask);radius=paint['width']*scale/2
        for contour,source in zip(contours,paint['contours']):
            pts=[((x-left)*scale,(y-top)*scale) for x,y in contour]
            if source.get('cyclic'):pts=pts+[pts[0]]
            draw.line(pts,fill=255,width=max(1,round(2*radius)),joint='curve')
            for x,y in pts:draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=255)
    alpha=np.asarray(mask.resize((right-left,bottom-top),Image.Resampling.LANCZOS),dtype=np.float32)/255
    gradient=paint.get('pressure',{}).get('gradient')
    if gradient:
        coordinates=(np.arange(left,right,dtype=np.float32)+.5 if gradient['axis']==0 else
                     np.arange(top,bottom,dtype=np.float32)+.5)
        positions=(coordinates-gradient['start'])/(gradient['end']-gradient['start'])
        ramp=np.interp(positions,gradient['stops'],paint['pressure']['opacities'])
        alpha*=ramp[None,:] if gradient['axis']==0 else ramp[:,None]
    material=paint['contours'][0].get('fill_gradient') if paint['kind']=='fill' else None
    if material:
        if any(contour.get('fill_gradient')!=material for contour in paint['contours']):
            raise ValueError('Compound gradient preview needs matching contour paints')
        from vector_artwork import sample_gradient
        x,y=np.meshgrid(np.arange(left,right)+.5,np.arange(top,bottom)+.5)
        rgba=sample_gradient(material,x,y,linear=depth==32);rgba[...,3]*=alpha
    else:
        rgba=np.empty((*alpha.shape,4),dtype=np.float32);rgba[...,:3]=rgb(paint,depth);rgba[...,3]=alpha
    return rgba,left,top


def shape_layer(container,paint,name,size,depth,*,native_material_gradient=False):
    from psd_tools.constants import Tag
    from psd_tools.psd.descriptor import DescriptorBlock,Double,UnitFloat,Integer,Bool,Enumerated,List
    from psd_tools.terminology import Unit
    material=any(c.get('fill_gradient') for c in paint['contours']) and paint['kind']=='fill'
    if material and not native_material_gradient:
        raise ValueError('GP material gradient has no supported native PSD mapping; preserving SVG source')
    material_content=None
    if material:
        from psd_gradients import material_gradient
        material_content=material_gradient(dict(paint,_depth=depth),size)
    paint=_dot(paint);preview=_preview(paint,*size,depth)
    if preview is None:return None
    pixels,left,top=preview
    layer=container.create_pixel_layer_from_array(pixels,name=name,left=left,top=top)
    layer._record.flags.pixel_data_irrelevant=True
    mask_tag=Tag.VECTOR_MASK_SETTING2 if paint['kind']=='stroke' else Tag.VECTOR_MASK_SETTING1
    layer.tagged_blocks.set_data(mask_tag,path=_mask(paint['contours'],*size))
    values=rgb(paint,depth);gradient=paint.get('pressure',{}).get('gradient')
    content=material_content or (_gradient(paint,values) if gradient else _solid(values))
    if paint['kind']=='stroke':
        layer.tagged_blocks.set_data(Tag.VECTOR_STROKE_DATA,classID=b'strokeStyle',items={
            b'strokeStyleVersion':Integer(2),b'strokeEnabled':Bool(True),b'fillEnabled':Bool(False),
            b'strokeStyleLineWidth':UnitFloat(paint['width'],Unit.Pixels),
            b'strokeStyleLineDashOffset':UnitFloat(0,Unit.Pixels),b'strokeStyleMiterLimit':Double(4),
            b'strokeStyleLineCapType':Enumerated(b'strokeStyleLineCapType',b'strokeStyleRoundCap'),
            b'strokeStyleLineJoinType':Enumerated(b'strokeStyleLineJoinType',b'strokeStyleRoundJoin'),
            b'strokeStyleLineAlignment':Enumerated(b'strokeStyleLineAlignment',b'strokeStyleAlignCenter'),
            b'strokeStyleScaleLock':Bool(False),b'strokeStyleStrokeAdjust':Bool(False),
            b'strokeStyleLineDashSet':List([]),b'strokeStyleBlendMode':Enumerated(b'BlnM',b'Nrml'),
            b'strokeStyleOpacity':UnitFloat(100,Unit.Percent),b'strokeStyleContent':content,
            b'strokeStyleResolution':Double(72)})
        layer.tagged_blocks.set_data(Tag.VECTOR_STROKE_CONTENT_DATA,classID=b'null',items={b'Clr ':_color(values)})
        layer.tagged_blocks.get_data(Tag.VECTOR_STROKE_CONTENT_DATA).key=b'SoCo'
    elif gradient or material:
        layer.tagged_blocks.set_data(Tag.GRADIENT_FILL_SETTING,classID=b'null',items=content.items())
    else:
        layer.tagged_blocks.set_data(Tag.SOLID_COLOR_SHEET_SETTING,classID=b'null',items={b'Clr ':_color(values)})
    layer.opacity=round(max(0,min(1,paint.get('opacity',1)))*255)
    if paint.get('centreline'):
        _saved_path(container,[paint['centreline']],container.name+' / '+name+' centreline',size)
    return layer


def _saved_path(container,contours,name,size):
    from psd_tools.psd.image_resources import ImageResource
    resources=container._psd.image_resources
    key=next((key for key in range(2000,2998) if key not in resources),None)
    if key is None:return
    name=name.encode('macroman',errors='replace').decode('macroman')[:240]
    resources[key]=ImageResource(key=key,name=name,data=_mask(contours,*size))


def _engine(value):
    from psd_tools.psd import engine_data as ed
    if isinstance(value,dict):
        result=ed.Dict({})
        for key,item in value.items():result[key]=_engine(item)
        return result
    if isinstance(value,list):return ed.List([_engine(v) for v in value])
    if isinstance(value,bool):return ed.Bool(value)
    if isinstance(value,int):return ed.Integer(value)
    if isinstance(value,float):return ed.Float(value)
    return ed.String(str(value))


def _text_preview(info,depth,size):
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    a,b,c,d,e,f=info['matrix'];scale=max(math.hypot(a,b),math.hypot(c,d));aa=4
    font=ImageFont.truetype(info['font_file'],max(1,round(info['size']*scale*aa)))
    text=info['body'];box=font.getbbox(text,anchor='ls')
    shift={'LEFT':0,'CENTER':-.5,'RIGHT':-1}.get(info.get('align'),0)*font.getlength(text)
    offset_x=info.get('offset_x',0)*scale*aa+shift;offset_y=-info.get('offset_y',0)*scale*aa
    left,top,right,bottom=[v/aa for v in box]
    local=Image.new('L',(max(1,box[2]-box[0]+8),max(1,box[3]-box[1]+8)))
    ImageDraw.Draw(local).text((4-box[0],4-box[1]),text,font=font,fill=255,anchor='ls')
    a,b,c,d=a/scale,b/scale,c/scale,d/scale
    x0=left+(offset_x-4)/aa;y0=top+(offset_y-4)/aa
    corners=[(a*x+c*y+e,b*x+d*y+f) for x,y in ((x0,y0),(x0+local.width/aa,y0),(x0,y0+local.height/aa),(x0+local.width/aa,y0+local.height/aa))]
    l=max(0,math.floor(min(p[0] for p in corners)));t=max(0,math.floor(min(p[1] for p in corners)))
    r=min(size[0],math.ceil(max(p[0] for p in corners)));bt=min(size[1],math.ceil(max(p[1] for p in corners)))
    if r<=l or bt<=t:return None
    determinant=a*d-b*c
    inverse=(aa*d/determinant,-aa*c/determinant,aa*(d*(l-e)-c*(t-f))/determinant-aa*x0,
             -aa*b/determinant,aa*a/determinant,aa*(-b*(l-e)+a*(t-f))/determinant-aa*y0)
    mask=local.transform((r-l,bt-t),Image.Transform.AFFINE,inverse,resample=Image.Resampling.BICUBIC)
    pixels=np.empty((bt-t,r-l,4),dtype=np.float32)
    pixels[...,:3]=rgb(dict(color=info['fill'],linear=(info.get('material_linear_colors') or [[0,0,0]])[0][:3]),depth)
    pixels[...,3]=np.asarray(mask,dtype=np.float32)/255
    return pixels,l,t,scale


def text_layer(container,info,size,depth):
    from psd_tools.constants import Tag
    from psd_tools.psd.descriptor import String as UnicodeString,RawData,Enumerated,DescriptorBlock,Double
    from psd_tools.psd.engine_data import EngineData
    preview=_text_preview(info,depth,size)
    if preview is None:return None
    pixels,left,top,scale=preview;layer=container.create_pixel_layer_from_array(pixels,name=info['name'],left=left,top=top)
    text=info['body'].replace('\n','\r')+'\r';font_size=info['size']*scale
    color=rgb(dict(color=info['fill'],linear=(info.get('material_linear_colors') or [[0,0,0]])[0][:3]),depth)
    base={'Font':0,'FontSize':float(font_size),'AutoLeading':True,'Leading':float(font_size*1.2),
          'FillColor':{'Type':1,'Values':[1.0,*map(float,color)]},'Tracking':0,'Kerning':0,
          'FauxBold':False,'FauxItalic':False,'Underline':False}
    styles=[];lengths=[];current=None
    for index,ch in enumerate(text):
        formatted=info.get('formats',[]);style=formatted[index] if index<len(formatted) else (False,False,False,False,0)
        style=tuple(style)
        units=len(ch.encode('utf-16-be'))//2
        if current==style:lengths[-1]+=units
        else:
            data=dict(base,FauxBold=bool(style[0]),FauxItalic=bool(style[1]),Underline=bool(style[2]))
            material_id=style[4]
            if material_id and material_id<len(info.get('material_colors',[])):
                encoded,alpha=info['material_colors'][material_id]
                linear=(info.get('material_linear_colors') or [])[material_id][:3] if info.get('material_linear_colors') else None
                data['FillColor']={'Type':1,'Values':[float(alpha),*map(float,rgb(dict(color=encoded,linear=linear),depth))]}
            styles.append({'StyleSheet':{'StyleSheetData':data}});lengths.append(units);current=style
    paragraph={'Justification':{'LEFT':0,'RIGHT':1,'CENTER':2}.get(info.get('align'),0)}
    resources={'FontSet':[{'Name':info.get('font_postscript') or info['family'],'Script':0,'FontType':0,'Synthetic':0}],
               'StyleSheetSet':[{'Name':'Normal RGB','StyleSheetData':base}],
               'ParagraphSheetSet':[{'Name':'Normal RGB','Properties':paragraph}],
               'KinsokuSet':[],'MojiKumiSet':[]}
    engine=EngineData({})
    values={'EngineDict':{'Editor':{'Text':text},
        'StyleRun':{'DefaultRunData':{'StyleSheet':{'StyleSheetData':base}},'RunArray':styles,'RunLengthArray':lengths},
        'ParagraphRun':{'DefaultRunData':{'ParagraphSheet':{'Properties':paragraph}},
                        'RunArray':[{'ParagraphSheet':{'Properties':paragraph}}],
                        'RunLengthArray':[len(text.encode('utf-16-be'))//2]},
        'AntiAlias':4,'FractionalGlyphWidths':True},'ResourceDict':resources,'DocumentResources':resources}
    for key,value in values.items():engine[key]=_engine(value)
    descriptor=DescriptorBlock(classID=b'TxLr',items={b'Txt ':UnicodeString(text),b'EngineData':RawData(engine),
        b'textGridding':Enumerated(b'textGridding',b'None'),b'Ornt':Enumerated(b'Ornt',b'Hrzn'),
        b'AntA':Enumerated(b'Annt',b'AnSm')})
    warp=DescriptorBlock(classID=b'warp',items={b'warpStyle':Enumerated(b'warpStyle',b'warpNone'),
          b'warpValue':Double(0),b'warpPerspective':Double(0),b'warpPerspectiveOther':Double(0),b'warpRotate':Enumerated(b'Ornt',b'Hrzn')})
    a,b,c,d,e,f=info['matrix']
    layer.tagged_blocks.set_data(Tag.TYPE_TOOL_OBJECT_SETTING,text_version=50,
        transform=(a/scale,b/scale,c/scale,d/scale,e,f),text_data=descriptor,warp=warp,
        left=left,top=top,right=left+pixels.shape[1],bottom=top+pixels.shape[0])
    layer.opacity=round(max(0,min(1,info.get('opacity',1)))*255)
    layer._record.flags.pixel_data_irrelevant=True
    return layer


@timed('psd_vector_build')
def append_artwork(container,model,depth=8,*,job=None,fallback=None):
    from psd_tools.constants import BlendMode
    from vector_artwork import artwork_tree,layer_paints
    size=(model['width'],model['height']);count=0
    families=[o.get('svg_instance',{}).get('key') for o in model['objects'] if o.get('svg_instance')]
    shared={key for key in families if families.count(key)>1}
    modes={'REGULAR':'NORMAL','NORMAL':'NORMAL','MULTIPLY':'MULTIPLY','HARDLIGHT':'HARD_LIGHT',
           'ADD':'LINEAR_DODGE','SUBTRACT':'SUBTRACT','DIVIDE':'DIVIDE'}
    blended=sorted({drawing.get('blend_mode','REGULAR') for obj in model['objects']
                    for drawing in obj.get('layers',[])
                    if drawing.get('blend_mode','REGULAR') not in ('REGULAR','NORMAL')})
    if blended:
        print(f'{LOG_PREFIX} WARNING: PSD layer blend appearance approximated:',
              ', '.join(mode+' -> '+modes[mode] for mode in blended),
              '| GP transparency and colour management can differ',flush=True)
    def object_layer(parent,obj):
        nonlocal count
        kind=obj.get('svg_kind')
        if kind=='FONT':
            if not obj.get('font_file') or not Path(obj['font_file']).is_file():raise ValueError('PSD text font preview is unavailable: '+obj['name'])
            if '\n' in obj['body']:raise ValueError('PSD multiline text needs a verified paragraph layout')
            if (obj.get('space_character',1)!=1 or obj.get('space_word',1)!=1 or
                    obj.get('align_y','TOP_BASELINE')!='TOP_BASELINE' or obj.get('shear',0) or
                    any(obj.get('kerning',[])) or any(any(s[:4]) for s in obj.get('formats',[])) or
                    any(s[4] for s in obj.get('formats',[]))):
                raise ValueError('PSD formatted text needs a verified layout; preserving its rendered source')
            text_layer(parent,obj,size,depth);count+=1;return
        if kind=='RASTER':raise ValueError('PSD per-object raster cache needs a fresh complete vector source')
        group=parent.create_group(name=obj['name'],blend_mode=BlendMode.NORMAL)
        if obj.get('source_geometry'):
            contours=[stroke for drawing in obj['source_geometry'] for stroke in drawing['strokes']]
            _saved_path(parent,contours,obj['name']+' original',size)
        if kind=='CURVE':
            if obj.get('fill_rule','evenodd')!='evenodd':
                raise ValueError('PSD nonzero Curve fill needs a verified path rule')
            runs=[]
            for spline in obj['splines']:
                key=(spline['fill'],spline['opacity'])
                if runs and runs[-1][0]==key:runs[-1][1].append(spline)
                else:runs.append((key,[spline]))
            for (color,opacity),contours in runs:
                shape_layer(group,dict(kind='fill',contours=contours,color=color,opacity=opacity,
                    linear=contours[0].get('fill_linear')),obj['name'],size,depth)
                count+=1
            return
        for drawing in obj['layers']:
            if len(obj['layers'])==1 and drawing.get('blend_mode','REGULAR') in ('REGULAR','NORMAL'):
                layer=group;layer.opacity=round(drawing.get('opacity',1)*255)
            else:
                layer=group.create_group(name=drawing['name'],opacity=round(drawing.get('opacity',1)*255),
                       blend_mode=getattr(BlendMode,modes[drawing.get('blend_mode','REGULAR')]))
            for paint in layer_paints(drawing):
                from conversion_policy import automatic_eligible
                native_gradient=automatic_eligible('radial_gradient' if
                    paint['contours'][0].get('fill_gradient',{}).get('kind')=='RADIAL' else 'linear_gradient')
                shape_layer(layer,paint,drawing['name'],size,depth,native_material_gradient=native_gradient);count+=1
    def visit(parent,node):
        nonlocal count
        for child in node['children']:
            if 'artwork' in child:
                obj=child['artwork'];before=list(parent);old_count=count
                old_resources=dict(container._psd.image_resources)
                try:
                    object_layer(parent,obj)
                    bound=bind_source(parent,obj,[layer for layer in parent if layer not in before])
                    if job is not None:
                        from conversion_policy import record
                        linked=obj.get('svg_instance',{}).get('key') in shared
                        record(job,obj,'APPROXIMATED' if linked else 'NATIVE_EDITABLE',
                            'Native copy; shared edits preserved in SVG source only' if linked else '',
                            validation='reader fixtures; target editor unverified',layer_ids=bound,
                            features_lost=['live PSD instance editing'] if linked else [])
                except (ValueError,NotImplementedError) as exc:
                    if fallback is None:raise
                    for layer in list(parent):
                        if layer not in before:parent.remove(layer)
                    container._psd.image_resources.clear();container._psd.image_resources.update(old_resources)
                    count=old_count+fallback(parent,obj,str(exc))
            else:
                group=parent.create_group(name=child['name'],blend_mode=BlendMode.PASS_THROUGH)
                if {'ref','reference'} & child.get('flags',set()):group.visible=False
                visit(group,child)
    visit(container,artwork_tree(model['objects']))
    provenance=[{key:obj[key] for key in ('name','modifiers','source_geometry') if key in obj}
                for obj in model['objects'] if obj.get('modifiers')]
    if provenance:
        from xml.etree import ElementTree as ET
        from psd_tools.constants import Resource
        from psd_tools.psd.image_resources import ImageResource
        resources=container._psd.image_resources
        existing=resources.get_data(Resource.XMP_METADATA)
        if existing:
            try:xmp=ET.fromstring(existing)
            except ET.ParseError:xmp=None
        else:xmp=None
        if xmp is None:
            xmp=ET.Element('{adobe:ns:meta/}xmpmeta')
        rdf=xmp.find('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF')
        if rdf is None:rdf=ET.SubElement(xmp,'{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF')
        description=ET.SubElement(rdf,'{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')
        ET.SubElement(description,'{urn:compio:vector-source:1.0}source').text=json.dumps(provenance,ensure_ascii=False)
        resources[Resource.XMP_METADATA]=ImageResource(key=Resource.XMP_METADATA,data=ET.tostring(xmp,encoding='utf-8'))
    return count


def load_artwork(source):
    source=Path(source);model=source.with_suffix('.vectors.json')
    if not model.is_file():
        from svg_hybrid import resolve_hybrid_source
        if not resolve_hybrid_source(source):return None
    if not model.is_file():return None
    return json.loads(model.read_text(encoding='utf-8'))
