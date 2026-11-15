"""Readable SVG identifiers and inert, versioned Blender source identity.

Names describe artwork; UUIDs identify it. This is provenance for a future
importer, not an implementation of SVG/PSD round-trip updates or scripts.
"""

try:
    from .svg_compat import normalize_metadata
except ImportError:
    try:
        from svg_compat import normalize_metadata
    except ImportError:
        def normalize_metadata(root):
            return root
import hashlib
import json
import re
import uuid
from xml.etree import ElementTree as ET

SVG='{http://www.w3.org/2000/svg}'
INK='{http://www.inkscape.org/namespaces/inkscape}'
XLINK='{http://www.w3.org/1999/xlink}'
NS='urn:asset-parts:source:1'
ET.register_namespace('asset',NS)
PREFIX='data-asset-'

def source_id(value):
    """Persist local Blender IDs; derive a stable key for read-only libraries."""
    stored=value.get('_asset_parts_id')
    if stored:return str(stored)
    library=getattr(value,'library',None)
    if library:
        return str(uuid.uuid5(uuid.NAMESPACE_URL,str(library.filepath)+'#'+value.name_full))
    result=str(uuid.uuid4())
    try:
        value['_asset_parts_id']=result
        value['_asset_parts_owner_name']=getattr(value,'name_full',value.name)
        value['_asset_parts_owner_session']=getattr(value,'session_uid',0)
    except (TypeError,AttributeError,RuntimeError):
        result=str(uuid.uuid5(uuid.NAMESPACE_URL,str(getattr(value,'name_full',getattr(value,'name','')))))
    return result

def source_metadata(scene,obj):
    obj=getattr(obj,'original',obj)
    return dict(schema=1,scene_id=source_id(scene),object_id=source_id(obj),
        data_id=source_id(obj.data),object_name=obj.name,data_name=obj.data.name,
        scene_name=scene.name,object_type=obj.type,frame=int(scene.frame_current),
        source_library=getattr(getattr(obj,'library',None),'filepath',''))

def ensure_unique_ids(scene):
    """Blender duplicates custom properties too; copies need new object IDs.

    Shared datablocks keep one data UUID. Independent copied datablocks receive
    distinct UUIDs. This runs on authored data before a worker snapshot.
    """
    objects=sorted((o for o in scene.objects if o.type in ('GREASEPENCIL','CURVE','FONT')),key=lambda o:o.name)
    data={o.data.as_pointer():o.data for o in objects}
    try:
        import bpy
        scenes=sorted(bpy.data.scenes,key=lambda s:s.name)
    except (ImportError,AttributeError):scenes=[scene]
    for values in (scenes,objects,sorted(data.values(),key=lambda d:d.name)):
        families={}
        for value in values:families.setdefault(source_id(value),[]).append(value)
        for identity,family in families.items():
            preferred=next((v for v in family if v.get('_asset_parts_owner_session') and
                v.get('_asset_parts_owner_session')==getattr(v,'session_uid',None)),None)
            preferred=preferred or next((v for v in family if v.get('_asset_parts_owner_name')==v.name_full),family[0])
            for value in family:
                if value.library:continue
                if value!=preferred:value['_asset_parts_id']=str(uuid.uuid4())
                value['_asset_parts_owner_name']=value.name_full
                value['_asset_parts_owner_session']=getattr(value,'session_uid',0)

def source_attributes(source):
    return {PREFIX+key.replace('_','-'):str(value) for key,value in source.items()}

def slug(value):
    return re.sub(r'[^a-z0-9]+','-',str(value).casefold()).strip('-')[:64] or 'artwork'

def identifier(kind,label,key):
    suffix=hashlib.sha256(str(key).encode()).hexdigest()[:12]
    return kind+'-'+slug(label)+'-'+suffix

def remap_references(elements,mapping):
    for root in elements:
        for element in root.iter():
            for key,value in list(element.attrib.items()):
                if key=='id':element.set(key,mapping.get(value,value))
                elif key=='data-layered-instance-source':element.set(key,mapping.get(value,value))
                elif key in ('href',XLINK+'href',INK+'path-effect'):
                    element.set(key,';'.join('#'+mapping.get(part[1:],part[1:]) if part.startswith('#') else part for part in value.split(';')))
                elif 'url(#' in value:
                    element.set(key,re.sub(r'url\(#([^)]*)\)',lambda m:'url(#'+mapping.get(m[1],m[1])+')',value))

def qualify_imports(elements,scope):
    """Disambiguate a reused source without stacking opaque ID prefixes."""
    for element in elements:
        normalize_metadata(element)
    mapping={}
    for child in elements:
        for node in child.iter():
            old=node.get('id')
            if old:
                label=node.get(INK+'label') or node.get('data-handoff-object') or old
                mapping[old]=identifier(node.tag.split('}')[-1],label,(scope,old))
    remap_references(elements,mapping)

def annotate(root,scope='',manifest=None):
    """Normalize IDs/references and append descriptive, non-executable metadata."""
    normalize_metadata(root)
    mapping={};records=[];counts={}
    def walk(node,owner='',drawing='',route=(),owner_name=''):
        owner=node.get(PREFIX+'object-id') or owner
        owner_name=node.get(PREFIX+'object-name') or node.get('data-handoff-object') or owner_name
        drawing=node.get('data-handoff-layer') or drawing
        label=node.get(INK+'label') or node.get('data-handoff-object') or drawing or 'Artwork'
        tag=node.tag.split('}')[-1]
        role=node.get('data-handoff-role') or tag
        if node.get('data-handoff-object'):
            role='object';label=node.get('data-handoff-object')
        elif tag=='g':role='group' if node.get(INK+'groupmode')=='layer' else 'layer'
        if owner and tag in ('path','text','use','image'):
            node.set(PREFIX+'owner-id',owner);node.set(PREFIX+'owner-name',owner_name)
            node.set(PREFIX+'drawing',drawing);node.set(PREFIX+'role',role)
            if label!=owner_name:label=owner_name+' '+label
        old=node.get('id')
        if old:
            family=(owner,drawing,role,label,route if not owner else ())
            index=counts.get(family,0);counts[family]=index+1
            mapping[old]=identifier(role,label,(scope,family,index))
        source={key[len(PREFIX):]:value for key,value in node.attrib.items() if key.startswith(PREFIX)}
        if source and old:records.append(dict(svg_id=old,source=source))
        for index,child in enumerate(list(node)):
            if child.tag not in (SVG+'title',SVG+'desc',SVG+'metadata'):
                walk(child,owner,drawing,route+(index,),owner_name)
    walk(root)
    remap_references([root],mapping)
    for record in records:record['svg_id']=mapping.get(record['svg_id'],record['svg_id'])
    for node in list(root.iter()):
        if not node.get('id') or node.tag in (SVG+'stop',SVG+'defs'):continue
        label=node.get(INK+'label')
        if label and node.get(PREFIX+'owner-name'):
            owner_name=node.get(PREFIX+'owner-name')
            label=(owner_name+' / '+label if label!=owner_name else label)+' ('+node.get(PREFIX+'role','artwork')+')'
        if label and node.tag not in (SVG+'text',SVG+'tspan') and node.find(SVG+'title') is None:
            ET.SubElement(node,SVG+'title').text=label
        if node.get(PREFIX+'object-id') and node.find(SVG+'desc') is None:
            ET.SubElement(node,SVG+'desc').text=('Blender object: '+node.get(PREFIX+'object-name','')+
                '; source ID: '+node.get(PREFIX+'object-id')+'; data ID: '+node.get(PREFIX+'data-id',''))
        elif node.get(PREFIX+'source-view-layer') and node.find(SVG+'desc') is None:
            ET.SubElement(node,SVG+'desc').text=('Blender View Layer: '+node.get(PREFIX+'source-view-layer')+
                '; Collection: '+node.get(PREFIX+'collection-path',''))
        elif node.get(PREFIX+'owner-id') and node.find(SVG+'desc') is None:
            ET.SubElement(node,SVG+'desc').text=('Blender object: '+node.get(PREFIX+'owner-name','')+
                '; drawing: '+node.get(PREFIX+'drawing','')+'; source ID: '+node.get(PREFIX+'owner-id'))
    if manifest is not None:
        metadata=ET.SubElement(root,SVG+'metadata')
        ET.SubElement(metadata,'{'+NS+'}sources',{'schema':'1'}).text=json.dumps(dict(objects=records,layers=manifest),ensure_ascii=False)
    root.set('data-asset-schema','1')
    return root
