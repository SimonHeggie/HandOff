"""Apply explicit standard OCA publication instructions after existing writers.

No inference from Blender's already-baked material transparency. PSD/SVG and
source Blender geometry are not modified by these OCA-specific instructions.
"""
import copy,hashlib,json,os,shutil
from pathlib import Path


def _nodes(items):
    for n in items:
        yield n
        yield from _nodes(n.get('childLayers',[]))


def _file(path):
    path=Path(path).resolve()
    if path.is_dir():
        docs=list(path.glob('*.oca'))
        if len(docs)!=1:raise ValueError('Nested OCA project must contain exactly one root data file: '+str(path))
        path=docs[0]
    if not path.is_file():raise FileNotFoundError('Nested OCA source missing: '+str(path))
    return path


def copy_nested(source,assets,project,visited=None,percent=100):
    """Copy only the reachable OCA graph and artwork; retain metadata/IDs."""
    from oca_project import component,_paths
    from oca_validation import local_asset
    visited={} if visited is None else visited
    source=_file(source)
    if source in visited:return visited[source]
    folder=Path(assets)/'_oca_sources'/hashlib.sha256(str(source).encode()).hexdigest()[:16]
    folder.mkdir(parents=True,exist_ok=True);target=folder/(component(source.stem)+'.oca');visited[source]=target
    document=json.loads(source.read_text(encoding='utf-8'))
    from oca_images import dimensions,load,resize,save
    from xml.etree import ElementTree as ET
    old_width,old_height=document['width'],document['height'];factor=percent/100
    copied_assets=set()
    for descriptor in _paths(document):
        image=local_asset(source.parent,descriptor['fileName'],'nested artwork')
        dest=folder/descriptor['fileName'];dest.parent.mkdir(parents=True,exist_ok=True)
        if image not in copied_assets:
            if percent==100:shutil.copy2(image,dest)
            elif image.suffix.lower()=='.svg':
                tree=ET.parse(image);svg=tree.getroot();w,h=dimensions(float(svg.get('width')),float(svg.get('height')),percent)
                svg.set('width',str(w));svg.set('height',str(h));tree.write(dest,encoding='utf-8',xml_declaration=True)
            else:
                depth={'U8':8,'U16':16,'F16':32,'F32':32}.get(descriptor.get('colorDepth',document['colorDepth']),8)
                rgba=load(image,depth);w,h=dimensions(rgba.shape[1],rgba.shape[0],percent)
                save(dest,resize(rgba,w,h),depth,image,half_float=document['colorDepth']=='F16')
            copied_assets.add(image)
        if percent!=100:
            descriptor['width'],descriptor['height']=dimensions(descriptor['width'],descriptor['height'],percent)
            descriptor['position']=[float(v)*factor for v in descriptor['position']]
    for layer in _nodes(document.get('layers',[])):
        if layer.get('type')!='ocalayer':continue
        ref=layer['source'];relative=ref.get('relFileName','');absolute=ref.get('absFileName','')
        child=source.parent/relative if relative else Path('/__missing_nested_oca__')
        if not child.exists():child=Path(absolute) if absolute else child
        copied=copy_nested(child,assets,project,visited,percent)
        ref.update(relFileName=os.path.relpath(copied,folder).replace(os.sep,'/'),absFileName=str(_file(child)))
    if percent!=100:
        document['width'],document['height']=dimensions(old_width,old_height,percent)
        for layer in _nodes(document.get('layers',[])):
            w,h=layer.get('width',old_width),layer.get('height',old_height)
            layer['width'],layer['height']=dimensions(w,h,percent)
            old_position=layer.get('position',[w/2,h/2])
            layer['position']=[(float(pos)-old_size/2)*factor+new_size/2 for pos,old_size,new_size in zip(old_position,(w,h),(layer['width'],layer['height']))]
    target.write_text(json.dumps(document,indent=4,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    meta=source.with_name(source.stem+'_meta.json')
    if meta.is_file():shutil.copy2(meta,target.with_name(target.stem+'_meta.json'))
    return target


def apply(document,job,project,assets):
    from oca_project import component
    layers=list(_nodes(document['layers']))
    entries={str(e.get('oca_source_id') or e.get('source_identity') or ''):e for e in job.get('manifest',[])}
    by_name={}
    for e in job.get('manifest',[]):by_name.setdefault(e.get('name'),[]).append(e)
    groups={}
    for e in job.get('manifest',[]):
        for name,values in e.get('oca_authored_groups',{}).items():
            if name in groups and groups[name]!=values:raise ValueError('Conflicting OCA properties for source Collection '+name)
            groups[name]=values
    authored={}
    for layer in layers:
        meta=layer.get('meta',{}).get('handoff',{});identity=meta.get('sourceIdentity','')
        if layer['type']=='grouplayer':
            name=identity.removeprefix('group:').split('/')[-1]
            values=groups.get(name,{})
        else:
            entry=entries.get(identity)
            if entry is None:
                options=by_name.get(meta.get('sourceName'),[]);entry=options[0] if len(options)==1 else {}
            values=entry.get('oca_authored',{})
            meta['sourceViewLayer']=entry.get('source_view_layer','')
            meta['keepIndependent']=bool(values.get('keepIndependent',False))
        authored[layer['id']]=values
        if layer['type']=='grouplayer':
            meta=layer.get('meta',{}).get('handoff',{});promoted=meta.get('autoPromotedBlend')
            children=layer.get('childLayers',[])
            override=values.get('blend','SOURCE')!='SOURCE'
            if not override:
                for child in children:
                    identity=child.get('meta',{}).get('handoff',{}).get('sourceIdentity','')
                    if entries.get(identity,{}).get('oca_authored',{}).get('blend','SOURCE')!='SOURCE':override=True
            if promoted and override:
                layer.update(blendingMode='normal',passThrough=True)
                for child in children:
                    if child.get('meta',{}).get('handoff',{}).get('sourceBlend')==promoted and child['blendingMode']=='normal':child['blendingMode']=promoted
        layer['opacity']=float(values.get('opacity',layer.get('opacity',1)))
        layer['inheritAlpha']=bool(values.get('inheritAlpha',layer.get('inheritAlpha',False)))
        mode=values.get('blend','SOURCE')
        if mode!='SOURCE':layer['blendingMode']=mode
        if layer['type']=='grouplayer' and (values.get('isolate') or layer['opacity']!=1 or layer['inheritAlpha'] or mode!='SOURCE'):
            layer['passThrough']=False
        for frame in layer.get('frames',[]):
            current=values
            for captured in job.get('oca_frames',[]):
                if int(captured['frame'])!=frame['frameNumber']:continue
                match=next((e for e in captured['manifest'] if str(e.get('oca_source_id') or e.get('source_identity') or '')==identity),None)
                if match:current=match.get('oca_authored',values)
            frame['opacity']=float(current.get('frameOpacity',1))
    background=job.get('oca_background_color')
    if background is not None:document['backgroundColor']=list(background)
    from oca_controls import options
    percent=options(job)['scale']
    for layer in layers:
        values=authored[layer['id']]
        if values.get('external') or values.get('sourceLayer'):
            offset=values.get('offset',[0,0]);layer['position']=[p+float(d)*percent/100 for p,d in zip(layer['position'],offset)]
        if values.get('external'):
            target=copy_nested(values['external'],assets,project,percent=percent)
            layer.update(type='ocalayer',frames=[],childLayers=[],source=dict(id=values.get('sourceID',''),
                relFileName=target.relative_to(project).as_posix(),absFileName=str(_file(values['external'])),timeOffset=int(values.get('timeOffset',0))))
        elif values.get('sourceLayer'):
            candidates=[n for n in layers if n.get('meta',{}).get('handoff',{}).get('sourceViewLayer')==values['sourceLayer']]
            if len(candidates)!=1:raise ValueError(layer['name']+': OCA source View Layer must match exactly one exported input: '+values['sourceLayer'])
            target=candidates[0]
            if target is layer:raise ValueError(layer['name']+': OCA clone cannot reference itself')
            layer.update(type='clonelayer',frames=[],childLayers=[],source=dict(id=target['id'],relFileName='',absFileName='',timeOffset=int(values.get('timeOffset',0))))
