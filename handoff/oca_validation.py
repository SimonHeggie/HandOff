"""Strict OCA 1.3 publication checks, including actual referenced image files."""
import json
import math
import struct
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

ROOT_FIELDS=set('name frameRate width height startTime endTime colorDepth backgroundColor layers ocaVersion'.split())
LAYER_FIELDS=set('name id type animated fileType frames childLayers blendingMode inheritAlpha position width height label opacity visible passThrough reference meta source'.split())
FRAME_FIELDS=set('name id fileName frameNumber opacity position width height duration meta'.split())
TYPES={'paintlayer','vectorlayer','grouplayer','clonelayer','ocalayer'}
DEPTHS={'U8','U16','F16','F32'}


class OCAValidationError(ValueError):pass


def fail(where, prop, message):
    raise OCAValidationError(f'{where}.{prop}: {message}')


def number(value, where, prop, *, integer=False, minimum=None):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        fail(where,prop,'must be a finite number')
    if integer and not isinstance(value,int):fail(where,prop,'must be an integer')
    if minimum is not None and value<minimum:fail(where,prop,f'must be at least {minimum}')


def position(value, where):
    if not isinstance(value,list) or len(value)!=2:fail(where,'position','must contain two centre coordinates')
    for v in value:number(v,where,'position')


def local_asset(root, value, where):
    if not isinstance(value,str) or not value or '\\' in value or ':' in value:
        fail(where,'fileName','must be a nonempty portable relative path')
    path=PurePosixPath(value)
    if path.is_absolute() or any(p in ('..','.') for p in value.split('/')):
        fail(where,'fileName','absolute paths and traversal are forbidden')
    result=(root/Path(value)).resolve()
    if not result.is_relative_to(root.resolve()):fail(where,'fileName','asset escapes the project directory')
    if not result.is_file():fail(where,'fileName','missing artwork: '+value)
    return result


def image_info(path):
    """Read EXR channel storage directly; validate PNG/SVG using real readers."""
    path=Path(path)
    if path.suffix.lower()=='.png':
        from PIL import Image
        with Image.open(path) as image:
            size=image.size;image.verify()
        with Image.open(path) as image:image.load()
        return (*size,'U'+str(path.read_bytes()[24]))
    if path.suffix.lower()=='.svg':
        root=ET.parse(path).getroot()
        if root.tag!='{http://www.w3.org/2000/svg}svg':raise ValueError('not an SVG root')
        def pixels(key):
            raw=root.get(key,'').removesuffix('px')
            value=float(raw)
            if not math.isfinite(value) or value<=0:raise ValueError('invalid SVG '+key)
            return value
        return (pixels('width'),pixels('height'),'SVG')
    if path.suffix.lower()!='.exr':raise ValueError('unsupported artwork format')
    with path.open('rb') as stream:
        if stream.read(4)!=struct.pack('<I',20000630):raise ValueError('invalid EXR signature')
        stream.read(4);fields={}
        def cstring():
            data=bytearray()
            while True:
                b=stream.read(1)
                if not b:raise ValueError('truncated EXR header')
                if b==b'\0':return bytes(data)
                data+=b
                if len(data)>4096:raise ValueError('invalid EXR header string')
        while True:
            name=cstring()
            if not name:break
            cstring();length=struct.unpack('<I',stream.read(4))[0]
            if length>8*1024*1024:raise ValueError('invalid EXR header field length')
            fields[name]=stream.read(length)
        x0,y0,x1,y1=struct.unpack('<4i',fields[b'dataWindow'])
        channels={};data=fields[b'channels'];offset=0
        while offset<len(data) and data[offset]:
            end=data.index(0,offset);name=data[offset:end].decode('ascii')
            channels[name]=struct.unpack_from('<i',data,end+1)[0];offset=end+17
        if not {'R','G','B','A'}<=channels.keys():raise ValueError('EXR requires R, G, B and A channels')
        storage={channels[n] for n in ('R','G','B','A')}
        if storage not in ({1},{2}):raise ValueError('EXR RGBA channels must consistently use HALF or FLOAT')
        if path.stat().st_size<=stream.tell()+8:raise ValueError('EXR has no pixel payload')
    try:import bpy
    except ImportError:bpy=None
    if bpy is not None:
        from psd_worker import read_blender_pixels
        pixels=read_blender_pixels(path)
        if pixels.shape[:2]!=(y1-y0+1,x1-x0+1):raise ValueError('EXR decoded size mismatch')
    return (x1-x0+1,y1-y0+1,'F16' if storage=={1} else 'F32')


def validate(document, root, *, document_path=None, _chain=()):
    root=Path(root);where='document'
    if not isinstance(document,dict):fail(where,'schema','must be an object')
    if set(document)-ROOT_FIELDS:fail(where,'schema','nonstandard root fields: '+', '.join(sorted(set(document)-ROOT_FIELDS)))
    if document.get('ocaVersion')!='1.3.0':fail(where,'ocaVersion','expected 1.3.0')
    for key in ('width','height'):number(document.get(key),where,key,integer=True,minimum=1)
    number(document.get('frameRate'),where,'frameRate',minimum=0)
    if document['frameRate']==0:fail(where,'frameRate','must be positive')
    for key in ('startTime','endTime'):number(document.get(key),where,key,integer=True)
    if document['endTime']<=document['startTime']:fail(where,'endTime','must be greater than startTime (exclusive end)')
    if document.get('colorDepth') not in DEPTHS:fail(where,'colorDepth','expected U8, U16, F16 or F32')
    color=document.get('backgroundColor',[0,0,0,0])
    if not isinstance(color,list) or len(color)!=4:fail(where,'backgroundColor','expected RGBA array')
    for value in color:
        number(value,where,'backgroundColor',minimum=0)
        if document['colorDepth'] in ('U8','U16') and value>1:fail(where,'backgroundColor','integer-depth values must be in 0..1')
    if not isinstance(document.get('name'),str) or not document['name']:fail(where,'name','must be a nonempty string')
    layers=document.get('layers')
    if not isinstance(layers,list):fail(where,'layers','must be an array')
    ids=set();names=set();by_id={};references=[];edges={};checked={}
    blend_root=ET.parse(Path(__file__).parent/'compatibility/blend_modes.xml').getroot()
    blends={n.get('oca') for n in blend_root.findall('./modes/mode')}
    def identity(obj, loc):
        value=obj.get('id')
        if not isinstance(value,str) or not value:fail(loc,'id','must be a nonempty string')
        if value in ids:fail(loc,'id','duplicate ID '+value)
        ids.add(value)
    def walk(items, parent='document.layers'):
        for index,layer in enumerate(items):
            loc=f'{parent}[{index}] ({layer.get("name","?")})' if isinstance(layer,dict) else parent
            if not isinstance(layer,dict):fail(loc,'schema','layer must be an object')
            if set(layer)-LAYER_FIELDS:fail(loc,'schema','nonstandard layer fields')
            name=layer.get('name')
            if not isinstance(name,str) or not name:fail(loc,'name','must be a nonempty string')
            if name in names:fail(loc,'name','duplicate document-level name '+name)
            names.add(name);identity(layer,loc);by_id[layer['id']]=layer;edges[layer['id']]=[]
            kind=layer.get('type')
            if kind not in TYPES:fail(loc,'type','unsupported OCA 1.3 layer type '+str(kind))
            for key in ('visible','reference','passThrough','inheritAlpha','animated'):
                if key in layer and not isinstance(layer[key],bool):fail(loc,key,'must be boolean')
            opacity=layer.get('opacity',1);number(opacity,loc,'opacity',minimum=0)
            if opacity>1:fail(loc,'opacity','must be in 0..1')
            if not isinstance(layer.get('meta',{}),dict):fail(loc,'meta','must be an object')
            number(layer.get('label',-1),loc,'label',integer=True)
            if layer.get('blendingMode','normal') not in blends:fail(loc,'blendingMode','not in the official OCA registry')
            if kind in ('clonelayer','ocalayer'):
                position(layer.get('position',[document['width']/2,document['height']/2]),loc)
                source=layer.get('source')
                if not isinstance(source,dict):fail(loc,'source','reference requires a source object')
                number(source.get('timeOffset',0),loc,'source.timeOffset',integer=True)
                references.append((layer,loc));continue
            for key in ('width','height'):number(layer.get(key),loc,key,integer=True,minimum=1)
            position(layer.get('position'),loc)
            children=layer.get('childLayers',[]);frames=layer.get('frames',[])
            if not isinstance(children,list) or not isinstance(frames,list):fail(loc,'schema','children/frames must be arrays')
            if kind=='grouplayer':
                if frames:fail(loc,'frames','group must not contain image frames')
                walk(children,loc+'.childLayers');edges[layer['id']]=[n['id'] for n in children];continue
            if children:fail(loc,'childLayers','paint/vector layers cannot contain children')
            expected='svg' if kind=='vectorlayer' else ('png' if document['colorDepth'].startswith('U') else 'exr')
            if layer.get('fileType')!=expected:fail(loc,'fileType','expected '+expected)
            previous=None
            for frame in frames:
                if not isinstance(frame,dict):fail(loc,'frames','frame must be an object')
                floc=loc+f'.frames[{frame.get("frameNumber","?")}]'
                if set(frame)-FRAME_FIELDS:fail(floc,'schema','nonstandard frame fields')
                identity(frame,floc)
                number(frame.get('frameNumber'),floc,'frameNumber',integer=True)
                number(frame.get('duration'),floc,'duration',integer=True,minimum=1)
                if previous is not None and frame['frameNumber']<previous:fail(floc,'frameNumber','frames overlap or are out of order')
                previous=frame['frameNumber']+frame['duration']
                position(frame.get('position'),floc)
                opacity=frame.get('opacity',1);number(opacity,floc,'opacity',minimum=0)
                if opacity>1:fail(floc,'opacity','must be in 0..1')
                if not isinstance(frame.get('meta',{}),dict):fail(floc,'meta','must be an object')
                if frame.get('name')=='_blank':
                    if frame.get('fileName')!='' or frame.get('width')!=0 or frame.get('height')!=0:fail(floc,'fileName','blank frame requires empty filename and zero dimensions')
                    continue
                for key in ('width','height'):number(frame.get(key),floc,key,integer=True,minimum=1)
                path=local_asset(root,frame.get('fileName'),floc)
                if path.suffix.lower()!='.'+expected:fail(floc,'fileName','extension disagrees with layer fileType')
                try:
                    if path not in checked:checked[path]=image_info(path)
                    w,h,depth=checked[path]
                except Exception as exc:fail(floc,'fileName','invalid artwork: '+str(exc))
                if [w,h]!=[frame['width'],frame['height']]:fail(floc,'width/height',f'asset is {w} x {h}, declaration is {frame["width"]} x {frame["height"]}')
                if kind=='paintlayer' and depth!=document['colorDepth']:fail(floc,'colorDepth','asset is '+depth+', document declares '+document['colorDepth'])
                extension=frame.get('meta',{}).get('handoff',{})
                if not isinstance(extension,dict):fail(floc,'meta.handoff','must be an object')
                for key,alternative in extension.items():
                    if key not in ('raster','editableSource'):continue
                    if not isinstance(alternative,dict):fail(floc,'meta.handoff.'+key,'must be an object')
                    apath=local_asset(root,alternative.get('fileName'),floc+'.meta.handoff.'+key)
                    try:aw,ah,_=image_info(apath)
                    except Exception as exc:fail(floc,'meta.handoff.'+key,'invalid companion: '+str(exc))
                    if [aw,ah]!=[alternative.get('width'),alternative.get('height')]:fail(floc,'meta.handoff.'+key,'companion dimensions disagree')
                    if alternative.get('position')!=frame['position']:fail(floc,'meta.handoff.'+key,'companion centre differs')
    walk(layers)
    for layer,loc in references:
        source=layer['source'];target=source.get('id','')
        if layer['type']=='clonelayer':
            if target not in by_id:fail(loc,'source.id','missing cloned layer '+str(target))
            edges[layer['id']].append(target)
        else:
            relative=source.get('relFileName','');absolute=source.get('absFileName','')
            path=(root/relative).resolve() if relative else Path('/__missing_oca_source__')
            if not path.exists() and absolute:path=Path(absolute)
            if path.is_dir():
                docs=list(path.glob('*.oca'))
                if len(docs)!=1:fail(loc,'source.relFileName','nested project must have one root data file')
                path=docs[0]
            if not path.is_file():fail(loc,'source.relFileName','missing nested OCA document')
            resolved=path.resolve()
            chain=(*_chain,Path(document_path).resolve()) if document_path else _chain
            if resolved in chain:fail(loc,'source','nested OCA cycle')
            try:
                child=json.loads(path.read_text(encoding='utf-8'))
                child_ids=validate(child,path.parent,document_path=path,_chain=chain)
            except (OSError,ValueError) as exc:fail(loc,'source','invalid nested document: '+str(exc))
            if target and target not in child_ids:fail(loc,'source.id','missing layer in nested document')
    def acyclic(identity,stack):
        if identity in stack:fail('layer '+by_id[identity]['name'],'source.id','cyclic clone/group reference')
        for target in edges.get(identity,[]):acyclic(target,stack|{identity})
    for identity in by_id:acyclic(identity,set())
    return set(by_id)


def validate_metadata(data):
    """Standard metadata fields are typed; additional exporter fields are legal."""
    if not isinstance(data,dict):fail('metadata','schema','must be an object')
    strings='author copyright created description exportedBy exportedByID exportedByOrg exportedByURL license licenseLong licenseURL originApp originAppVersion'.split()
    for key in strings:
        if key in data and not isinstance(data[key],str):fail('metadata',key,'must be a string')
    if 'meta' in data and not isinstance(data['meta'],dict):fail('metadata','meta','must be an object')
    if isinstance(data.get('meta'),dict) and 'handoff' in data['meta'] and not isinstance(data['meta']['handoff'],dict):
        fail('metadata','meta.handoff','must be an object')
