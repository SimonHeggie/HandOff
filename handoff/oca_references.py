"""Conservative OCA references: authored linked GP data, verified translations.

This reuses the existing SVG instance identity/geometry checks. Similar-looking
independent artwork is never promoted into a clone. Unknown transforms remain
independent vector layers with their existing artwork and raster alternatives.
"""
import json,math,copy
from pathlib import Path
from xml.etree import ElementTree as ET


def vector_instance(frame,root):
    from svg_instances import KEY,CONFIG,BASIS,SVG
    if not frame.get('fileName'):return None
    svg=ET.parse(Path(root)/frame['fileName']).getroot()
    objects=[n for n in svg.iter() if n.get(KEY) and n.tag==SVG+'g']
    if len(objects)!=1 or any(n.tag==SVG+'use' for n in svg.iter()):return None
    obj=objects[0]
    try:
        basis=json.loads(obj.get(BASIS,'null'));viewport=list(map(float,svg.get('viewBox','').split()))
        if len(basis)!=6 or len(viewport)!=4:return None
        paint=ET.Element(SVG+'g')
        for defs in svg:
            if defs.tag==SVG+'defs':paint.append(copy.deepcopy(defs))
        paint.append(copy.deepcopy(obj))
        return paint,(obj.get(KEY),obj.get(CONFIG)),basis,viewport,float(svg.get('width'))/viewport[2]
    except (TypeError,ValueError,ZeroDivisionError):return None


def translation(master,candidate,root):
    from svg_instances import multiply,inverse,compatible,_close
    left,right=master.get('frames',[]),candidate.get('frames',[])
    if len(left)!=len(right) or not left:return None
    delta=None
    for a,b in zip(left,right):
        if any(a.get(k)!=b.get(k) for k in ('frameNumber','duration','opacity')):return None
        if not a.get('fileName') or not b.get('fileName'):
            if bool(a.get('fileName'))!=bool(b.get('fileName')):return None
            continue
        aa,bb=vector_instance(a,root),vector_instance(b,root)
        if aa is None or bb is None or aa[1]!=bb[1] or not math.isclose(aa[4],bb[4]):return None
        try:transform=multiply(bb[2],inverse(aa[2]))
        except (ValueError,ArithmeticError):return None
        if not _close(transform[:4],[1,0,0,1],tolerance=1e-5):return None
        if not compatible(aa[0],bb[0],transform):return None
        viewport=[aa[3][0]+transform[4],aa[3][1]+transform[5],aa[3][2],aa[3][3]]
        if not _close(viewport,bb[3],tolerance=.002):return None
        current=[transform[4]*aa[4],transform[5]*aa[4]]
        if delta is not None and not _close(delta,current,tolerance=.002):return None
        delta=current
    return delta


def link_vector_clones(document,root):
    """Only constant translations with matching style and crop are OCA clones."""
    def leaves(items,origin=(0,0)):
        for layer in items:
            yield layer,origin
            if layer['type']=='grouplayer':
                x,y=layer['position'];w,h=layer['width'],layer['height']
                yield from leaves(layer['childLayers'],(origin[0]+x-w/2,origin[1]+y-h/2))
    masters=[];count=0
    for layer,origin in sorted(leaves(document['layers']),key=lambda item:item[0]['id']):
        if layer['type']!='vectorlayer' or layer.get('meta',{}).get('handoff',{}).get('keepIndependent'):continue
        match=None
        for master,master_origin in masters:
            delta=translation(master,layer,root)
            if delta is not None:match=master,master_origin,delta;break
        if match is None:masters.append((layer,origin));continue
        master,master_origin,delta=match
        layer.update(type='clonelayer',frames=[],childLayers=[],source=dict(id=master['id'],absFileName='',relFileName='',timeOffset=0),
            position=[master_origin[0]+master['position'][0]+delta[0]-origin[0],master_origin[1]+master['position'][1]+delta[1]-origin[1]])
        layer['meta'].setdefault('handoff',{}).update(sharedSourceIdentity=master['meta']['handoff']['sourceIdentity'],
            clonePolicy='Linked GP datablock; evaluated SVG paint/geometry, constant translation and crop verified')
        count+=1
    return count
