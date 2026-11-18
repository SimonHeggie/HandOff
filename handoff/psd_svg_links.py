"""Compact SVG sources and linked PSD Smart Objects with cached preview pixels.

One PSD representation is used for all editors. Application validation is
recorded separately; it is not a user-facing publishing switch.
"""
from pathlib import Path
from xml.etree import ElementTree as ET
import hashlib
import uuid

def preserve_source_file(job,label,source):
    """Preserve an already resolved hybrid SVG without losing embedded images."""
    from svg_metadata import slug
    source=Path(source);payload=source.read_bytes();root=ET.fromstring(payload)
    if root.get('data-compio-source-plan') or root.get('data-compio-raster-plan'):
        raise ValueError('Source SVG preparation has not completed')
    destination=Path(job['dest']);folder=destination.parent/(destination.stem+'.assets')
    folder.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256(str((job.get('node_name'),label,job.get('_publication_view_layer'))).encode()).hexdigest()[:10]
    path=folder/(slug(label)+'-'+key+'.svg');temporary=path.with_suffix('.writing.svg')
    try:temporary.write_bytes(payload);temporary.replace(path)
    finally:temporary.unlink(missing_ok=True)
    return path

def svg_sidecar(job,label,objects,size):
    from svg_export import encode_svg
    from svg_metadata import SVG,INK,slug,annotate
    root=ET.fromstring(encode_svg(*size,objects))
    from svg_collections import group_svg
    from svg_document import _highlight
    group_svg(root,objects)
    children=list(root);root[:]=[]
    group=ET.SubElement(root,SVG+'g',{INK+'groupmode':'layer',INK+'label':label,
        'id':'source-content','data-asset-role':'published-source'})
    colors={obj.get('inherited_color') or 'NO_COLOR' for obj in objects}
    _highlight(group,next(iter(colors)) if len(colors)==1 else 'NO_COLOR')
    group.extend(children)
    annotate(root,scope='sidecar',manifest=[dict(name=label,
        source_scene=job.get('source_scene',''),source_view_layer=job.get('_publication_view_layer',''))])
    payload=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    key=hashlib.sha256(str([(o.get('source_metadata',{}).get('object_id'),o['name']) for o in objects]).encode()).hexdigest()[:10]
    destination=Path(job['dest']);folder=destination.parent/(destination.stem+'.assets')
    folder.mkdir(parents=True,exist_ok=True);path=folder/(slug(label)+'-'+key+'.svg')
    temporary=path.with_suffix('.writing.svg')
    try:temporary.write_bytes(payload);temporary.replace(path)
    finally:temporary.unlink(missing_ok=True)
    return path

def preview(objects,size,depth,*,compact=False):
    """SVG-equivalent GP subset. Compose tight bounds, not a canvas per paint."""
    import numpy as np
    from psd_vectors import _preview
    from vector_artwork import layer_paints
    from merge_groups import over
    from raster_bounds import crop_rgba
    width,height=size
    def combine(back,front,mode):
        if front is None:return back
        if back is None:return front
        a,ax,ay=back;b,bx,by=front
        left=min(ax,bx);top=min(ay,by)
        right=max(ax+a.shape[1],bx+b.shape[1]);bottom=max(ay+a.shape[0],by+b.shape[0])
        x=np.zeros((bottom-top,right-left,4),np.float32);y=np.zeros_like(x)
        x[ay-top:ay-top+a.shape[0],ax-left:ax-left+a.shape[1]]=a
        y[by-top:by-top+b.shape[0],bx-left:bx-left+b.shape[1]]=b
        return over(x,y,mode),left,top
    result=None
    for obj in objects:
        if obj.get('svg_kind') not in (None,'GP'):raise ValueError('SVG preview renderer supports GP paint only')
        object_pixels=None
        for drawing in obj['layers']:
            mode={'REGULAR':'normal','NORMAL':'normal','MULTIPLY':'multiply'}.get(drawing.get('blend_mode','REGULAR'))
            if mode is None:raise ValueError('SVG preview blend requires source renderer')
            layer_pixels=None
            for paint in layer_paints(drawing):
                part=_preview(paint,width,height,depth)
                if part is None:continue
                pixels,x,y=part;pixels[...,3]*=paint.get('opacity',1)
                layer_pixels=combine(layer_pixels,(pixels,x,y),'normal')
            if layer_pixels is not None:layer_pixels[0][...,3]*=drawing.get('opacity',1)
            object_pixels=combine(object_pixels,layer_pixels,mode)
        result=combine(result,object_pixels,'normal')
    if result is None or not np.any(result[0][...,3]>0):
        raise ValueError('SVG preview has no visible paint; no blank substitute was published')
    pixels,left,top=result
    if compact:
        cropped,dx,dy=crop_rgba(pixels)
        return cropped,left+dx,top+dy
    canvas=np.zeros((height,width,4),np.float32)
    canvas[top:top+pixels.shape[0],left:left+pixels.shape[1]]=pixels
    return canvas


def attach_svg_link(layer,path,psd_path,size,*,source_id=None,transform=None):
    """Attach a relative SVG source to existing, verified preview channels.

    Build and serialize both records before committing either. Existing shared
    records are replaced rather than mutated, so callers can roll back a source
    conversion without retaining orphan links.
    """
    from psd_tools.constants import Tag,LinkedLayerType
    from psd_tools.psd.linked_layer import LinkedLayer,LinkedLayers
    from psd_tools.psd.descriptor import DescriptorBlock,Descriptor,String,Integer,Double,List,UnitFloat,Enumerated
    from psd_tools.psd.tagged_blocks import SmartObjectLayerData,TaggedBlock
    from psd_tools.terminology import Unit
    import os,datetime
    width,height=size;path=Path(path);psd_path=Path(psd_path)
    root=ET.parse(path).getroot()
    if root.tag not in ('svg','{http://www.w3.org/2000/svg}svg'):
        raise ValueError('Linked source is not SVG artwork')
    if not any(node.tag.split('}')[-1] in ('path','image','text','use','rect','circle','ellipse','polygon','polyline','line')
               for node in root.iter()):
        raise ValueError('Linked SVG has no paint content')
    identity=source_id or str(uuid.uuid5(uuid.NAMESPACE_URL,path.name))
    document=layer._psd
    existing=(document.tagged_blocks.get_data(Tag.LINKED_LAYER_EXTERNAL)
              if document.tagged_blocks is not None else None)
    relative=os.path.relpath(path,psd_path.parent).replace(os.sep,'/')
    shared=next((r for r in existing or [] if r.uuid==identity),None)
    if shared is not None and (shared.filename!=path.name or
            shared.linked_file[b'relPath'].value!=relative):
        raise ValueError('A shared Smart Object source cannot refer to different SVG files')
    corners=list(transform) if transform is not None else [0.,0.,float(width),0.,float(width),float(height),0.,float(height)]
    if len(corners)!=8:raise ValueError('Placed SVG needs eight corner coordinates')
    warp=Descriptor(classID=b'warp',items={b'warpStyle':Enumerated(b'warpStyle',b'warpNone'),
        b'warpValue':Double(0),b'warpPerspective':Double(0),b'warpPerspectiveOther':Double(0),
        b'warpRotate':Enumerated(b'Ornt',b'Hrzn'),b'bounds':Descriptor(classID=b'Rctn',items={
            b'Top ':UnitFloat(0,Unit.Pixels),b'Left':UnitFloat(0,Unit.Pixels),
            b'Btom':UnitFloat(height,Unit.Pixels),b'Rght':UnitFloat(width,Unit.Pixels)}),
        b'uOrder':Integer(4),b'vOrder':Integer(4)})
    fraction=Descriptor(classID=b'rationalPoint',items={b'numerator':Integer(0),b'denominator':Integer(600)})
    config=DescriptorBlock(classID=b'null',items={b'Idnt':String(identity),b'placed':String(str(uuid.uuid4())),
        b'PgNm':Integer(1),b'totalPages':Integer(1),b'Annt':Integer(16),b'Type':Integer(1),
        b'frameStep':fraction,b'duration':fraction,b'frameCount':Integer(0),
        b'Trnf':List([Double(x) for x in corners]),b'nonAffineTransform':List([Double(x) for x in corners]),
        b'warp':warp,b'Sz  ':Descriptor(classID=b'Pnt ',items={b'Wdth':Double(width),b'Hght':Double(height)}),
        b'Rslt':UnitFloat(72,b'#Rsl')})
    placed=SmartObjectLayerData(version=4,data=config)
    file=DescriptorBlock(classID=b'ExternalFileLink',items={b'descVersion':Integer(2),b'Nm  ':String(path.name),
        b'fullPath':String(path.resolve().as_uri()),b'originalPath':String(path.resolve().as_uri()),b'relPath':String(relative)})
    now=datetime.datetime.now(datetime.timezone.utc)
    record=LinkedLayer(kind=LinkedLayerType.EXTERNAL,version=4,uuid=identity,filename=path.name,filetype=b'svg ',
        filesize=path.stat().st_size,linked_file=file,timestamp=(now.year,now.month-1,now.day,now.hour,now.minute,float(now.second)),data=b'')
    records=LinkedLayers(list(existing or [])+([] if shared else [record]))
    placed.tobytes();records.tobytes()
    layer.tagged_blocks[Tag.SMART_OBJECT_LAYER_DATA2]=TaggedBlock(key=Tag.SMART_OBJECT_LAYER_DATA2,data=placed)
    document.tagged_blocks[Tag.LINKED_LAYER_EXTERNAL]=TaggedBlock(key=Tag.LINKED_LAYER_EXTERNAL,data=records)
    return layer


def create_linked_svg(container,pixels,path,psd_path,size,*,left=0,top=0,
                      source_id=None,transform=None,compression=None):
    from raster_bounds import crop_rgba
    rgba,dx,dy=crop_rgba(pixels)
    options=dict(compression=compression) if compression is not None else {}
    layer=container.create_pixel_layer_from_array(rgba,name=Path(path).stem,
        left=left+dx,top=top+dy,**options)
    try:return attach_svg_link(layer,path,psd_path,size,source_id=source_id,transform=transform)
    except Exception:
        container.remove(layer)
        raise


# Keep development fixtures and callers from v0.7.47 readable.
create_link_prototype=create_linked_svg
