"""OCA-only identities, portable project publication, metadata and rollback.

Existing image/sequence writers build their familiar layout in private staging.
Only validated complete projects are made visible to receiving applications.
"""
import copy
import hashlib
import json
import re
import shutil
import tempfile
import unicodedata
import uuid
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path


def component(value,limit=96):
    text=unicodedata.normalize('NFC',str(value))
    text=re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]|[\ud800-\udfff]','_',text).strip(' .') or 'Layer'
    if text.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:text+='_' 
    while len(text.encode('utf-8'))>limit:text=text[:-1]
    return text.rstrip(' .') or 'Layer'


def nodes(items):
    for layer in items:
        yield layer
        yield from nodes(layer.get('childLayers',[]))


def identities(document):
    layers=list(nodes(document['layers']));families=Counter();frame_ids={}
    for layer in layers:
        meta=layer.setdefault('meta',{}).setdefault('handoff',{})
        key=meta.get('sourceIdentity') or ('legacy:'+layer['id'])
        families[key]+=1
    seen=Counter()
    for layer in layers:
        meta=layer.setdefault('meta',{}).setdefault('handoff',{})
        key=meta.get('sourceIdentity') or ('legacy:'+layer['id'])
        if families[key]>1:
            if layer['type']=='grouplayer':
                children=sorted(c.get('meta',{}).get('handoff',{}).get('sourceIdentity',c['id']) for c in nodes(layer.get('childLayers',[])) if c['type']!='grouplayer')
                key+=':fragment:'+hashlib.sha256(json.dumps(children).encode()).hexdigest()
            else:
                seen[key]+=1;key+=':indistinguishable-occurrence:'+str(seen[key])
        layer['id']=str(uuid.uuid5(uuid.NAMESPACE_URL,'urn:handoff:oca:'+key))
        for frame in layer.get('frames',[]):
            previous_id=frame['id']
            frame['id']=str(uuid.uuid5(uuid.NAMESPACE_URL,layer['id']+':frame:'+str(frame['frameNumber'])))
            frame_ids[previous_id]=frame['id']
    # Names are document-global in OCA. Keep original Blender/export names in
    # metadata, allocate suffixes by identity rather than stack position.
    reserved={layer['name'] for layer in layers};used=set()
    for layer in sorted(layers,key=lambda n:(n['name'],n['id'])):
        original=layer['name'];name=original;index=2
        while name in used or (name!=original and name in reserved):
            name=f'{original} ({index})';index+=1
        used.add(name)
        if name!=original:
            layer['meta'].setdefault('handoff',{})['originalName']=original
            layer['name']=name
    return frame_ids


def _paths(document):
    for layer in nodes(document['layers']):
        for cel in layer.get('frames',[]):
            if cel.get('fileName'):yield cel
            for key,value in cel.get('meta',{}).get('handoff',{}).items():
                if key in ('raster','editableSource') and isinstance(value,dict) and value.get('fileName'):yield value


def _portable_assets(document,old_assets,new_root,prefix,reserved=()):
    old_assets=Path(old_assets);new_root=Path(new_root)
    aliases={};used={():{n.casefold() for n in reserved}}
    def rename(parts):
        parent=();output=[]
        for index_part,part in enumerate(parts):
            key=(*parent,part)
            if key not in aliases:
                is_file=index_part==len(parts)-1
                suffix=Path(part).suffix if is_file else ''
                stem=part[:-len(suffix)] if suffix else part
                match=re.search(r'(_-?\d{4,})$',stem) if is_file else None
                frame_suffix=match[0] if match else ''
                if match:stem=stem[:match.start()]
                base=component(stem,limit=240-len((frame_suffix+suffix).encode('utf-8')) if is_file else 96)
                name=base+frame_suffix+suffix;index=2
                namespace=used.setdefault(parent,set())
                while name.casefold() in namespace:name=f'{base}-{index}{frame_suffix}{suffix}';index+=1
                namespace.add(name.casefold());aliases[key]=name
            output.append(aliases[key]);parent=key
        return Path(*output)
    # Same names are allocated independently of stack order.
    files=sorted(p for p in old_assets.rglob('*') if p.is_file())
    for path in files:rename(path.relative_to(old_assets).parts)
    for descriptor in _paths(document):
        path=Path(descriptor['fileName'])
        if not path.parts or path.parts[0]!=old_assets.name:raise ValueError('OCA asset does not belong to the staged project: '+str(path))
        relative=rename(path.parts[1:]);descriptor['fileName']=(Path(prefix)/relative).as_posix() if prefix else relative.as_posix()
    for path in files:
        relative=rename(path.relative_to(old_assets).parts);target=new_root/relative
        target.parent.mkdir(parents=True,exist_ok=True);path.replace(target)
    # Companion JSON attachment paths refer to the same assets. Rewrite only
    # its existing image references when filesystem sanitization changed them.
    for path in (new_root/'_companions').glob('*.spine.json') if (new_root/'_companions').is_dir() else ():
        data=json.loads(path.read_text())
        for skin in data.get('skins',[]):
            for attachments in skin.get('attachments',{}).values():
                for region in attachments.values():
                    rel=Path(region['path']+'.png');region['path']=rename(rel.parts).with_suffix('').as_posix()
        path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')


def metadata(job,previous):
    from branding import NAME,VERSION,GITHUB
    result=copy.deepcopy(previous)
    supplied=job.get('oca_metadata',{})
    for key in ('author','copyright','license','licenseLong','licenseURL','description','created'):
        if isinstance(supplied.get(key),str):result[key]=supplied[key]
    version=job.get('origin_app_version')
    if not version:
        try:
            import bpy
            version=bpy.app.version_string
        except ImportError:version='unknown'
    result.update(exportedBy=NAME,exportedByID=GITHUB,originApp='Blender',originAppVersion=version,exportedByURL=GITHUB)
    result.setdefault('created',datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'))
    result.setdefault('meta',{}).setdefault('handoff',{}).update(exporterVersion=VERSION,warnings=list(job.get('_notices',[])))
    return result


def _remove(path):
    if path.is_dir():shutil.rmtree(path)
    else:path.unlink(missing_ok=True)


def commit(artifacts):
    """Retire the old manifest first; restore it last if any rename fails."""
    retired=[];installed=[]
    try:
        for staged,target in artifacts:
            if target.is_symlink():raise ValueError('OCA publication refuses symlink destination: '+str(target))
            if target.exists():
                backup=target.with_name('.'+target.name+'.oca-backup-'+uuid.uuid4().hex[:8])
                target.replace(backup);retired.append((target,backup))
        for staged,target in reversed(artifacts):
            staged.replace(target);installed.append(target)
    except Exception:
        for target in reversed(installed):_remove(target)
        for target,backup in reversed(retired):backup.replace(target)
        raise
    for target,backup in retired:_remove(backup)


def publish(job,producer):
    from oca_validation import validate,validate_metadata
    requested=Path(job['dest']).with_suffix('.oca');name=component(requested.stem)
    target=requested.with_name(name+'.oca');standard=job.get('oca_layout','LEGACY')=='PROJECT'
    if target.exists() and target.is_dir()!=standard:
        raise ValueError('OCA layout conflicts with existing '+str(target)+'. Choose the matching layout or a new destination.')
    old_meta=target/(name+'_meta.json') if standard else target.with_name(name+'_meta.json')
    previous=json.loads(old_meta.read_text(encoding='utf-8')) if old_meta.is_file() else {}
    validate_metadata(previous)
    old_assets=target.with_suffix('')
    if not job.get('overwrite',False) and (target.exists() or (not standard and old_assets.exists())):
        raise FileExistsError('Overwrite disabled for '+str(target))
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.oca-publish-',dir=target.parent) as temporary:
        work=Path(temporary);source=work/'source';source.mkdir()
        internal=dict(job,dest=str(source/(name+'.oca')),_oca_internal=True,_oca_companions=False,overwrite=True)
        internal['_oca_preview_dir']=str(work/'previews')
        internal['_oca_preview_rasters']={}
        internal.setdefault('cache_destination',str(requested))
        produced=Path(producer(internal));document=json.loads(produced.read_text(encoding='utf-8'))
        for key in ('_notices','_publication','_partial'):job[key]=internal.get(key,[] if key!='_partial' else False)
        frame_ids=identities(document)
        previews={frame_ids.get(key,key):value for key,value in internal['_oca_preview_rasters'].items()}
        project=work/'ready';project.mkdir()
        assets=project if standard else project/name
        assets.mkdir(exist_ok=True)
        _portable_assets(document,source/name,assets,'' if standard else name,
                         (name+'.oca',name+'_meta.json','_oca_sources') if standard else ('_oca_sources',))
        original_artwork={d['fileName'] for d in _paths(document)}
        from oca_features import apply
        apply(document,job,project,assets)
        from oca_references import link_vector_clones
        count=link_vector_clones(document,project)
        if count:
            from disabled_layers import notice
            notice(job,f'OCA: {count} verified linked GP layer(s) published as standard clone references')
        # Reference layers need their master's assets only. Remove just files
        # created by this export that no longer have a document reference.
        if not job.get('oca_keep_png',False):
            retained={d['fileName'] for d in _paths(document)}
            for filename in original_artwork-retained:
                path=project/filename
                path.unlink(missing_ok=True)
                parent=path.parent
                while parent!=assets and parent.is_relative_to(assets) and not any(parent.iterdir()):
                    parent.rmdir();parent=parent.parent
        from oca_companions import write_companions
        write_companions(dict(job,_oca_preview_rasters=previews),document,assets)
        data_path=project/(name+'.oca')
        sidecar=project/(name+'_meta.json')
        data_path.write_text(json.dumps(document,indent=4,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        meta=metadata(job,previous);validate_metadata(meta)
        sidecar.write_text(json.dumps(meta,indent=4,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        validate(document,project,document_path=data_path)
        if standard:
            commit([(project,target)])
            print('OCA PROJECT COMPLETE:',target/(name+'.oca'),flush=True)
            return str(target/(name+'.oca'))
        commit([(data_path,target),(sidecar,old_meta),(assets,old_assets)])
        print('OCA PROJECT COMPLETE:',target,flush=True)
        return str(target)
