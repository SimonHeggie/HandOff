"""Reference-aware OCA composition for existing templates/artwork companions.

This is an OCA-only consumer. It never changes PSD merging or Blender renders.
"""
import copy,os
from pathlib import Path
import json
import numpy as np


class UnsupportedRender(ValueError):pass


def root_for(document,assets):
    assets=Path(assets)
    return assets.parent if assets.name==document['name'] else assets


def expanded(document,root):
    root=Path(root).resolve();width,height=document['width'],document['height']
    def asset_path(path,filename):
        candidate=path/filename
        if candidate.is_file():return candidate
        stripped=path.joinpath(*Path(filename).parts[1:])
        return stripped if stripped.is_file() else candidate
    def index(data):
        result={}
        def walk(items):
            for n in items:result[n['id']]=n;walk(n.get('childLayers',[]))
        walk(data['layers']);return result
    def walk(items,data,path,origin,offset,clip,chain):
        byid=index(data)
        for original in items:
            layer=copy.deepcopy(original);kind=layer['type']
            if kind=='clonelayer':
                seen=set(chain);time=offset;overrides=[]
                while layer['type']=='clonelayer':
                    key=(str(path),layer['id'])
                    if key in seen:raise ValueError('Cyclic OCA clone: '+layer['name'])
                    seen.add(key);overrides.append(layer)
                    source=byid.get(layer['source']['id'])
                    if source is None:raise ValueError(layer['name']+': missing OCA clone source')
                    time+=int(layer['source'].get('timeOffset',0));layer=copy.deepcopy(source)
                for instance in reversed(overrides):
                    layer.update({k:v for k,v in instance.items() if k not in ('type','frames','animated','fileType','width','height','childLayers','source')})
                    for key,default in (('opacity',1),('blendingMode','normal'),('visible',True),('reference',False),('inheritAlpha',False)):
                        layer[key]=instance.get(key,default)
                yield from walk([layer],data,path,origin,time,clip,seen);continue
            w,h=layer.get('width',data['width']),layer.get('height',data['height'])
            cx,cy=layer.get('position',[w/2,h/2]);top=(origin[0]+cx-w/2,origin[1]+cy-h/2)
            if kind=='ocalayer':
                source=layer['source'];filename=source.get('relFileName','');child=(path/filename).resolve() if filename else Path('/__missing_oca__')
                if not child.exists():child=Path(source.get('absFileName',''))
                if child.is_dir():
                    docs=list(child.glob('*.oca'))
                    if len(docs)!=1:raise ValueError(layer['name']+': nested project needs one root document')
                    child=docs[0]
                key=(str(child.resolve()),source.get('id',''))
                if key in chain:raise ValueError('Cyclic nested OCA reference: '+layer['name'])
                nested=json.loads(child.read_text(encoding='utf-8'));nw,nh=nested['width'],nested['height']
                top=(origin[0]+cx-nw/2,origin[1]+cy-nh/2)
                time=offset+int(source.get('timeOffset',0));interval=(max(clip[0],nested['startTime']+time),min(clip[1],nested['endTime']+time))
                targets=nested['layers'] if not source.get('id') else [index(nested)[source['id']]]
                children=list(walk(targets,nested,child.parent,top,time,interval,chain|{key}))
                layer.update(type='grouplayer',frames=[],childLayers=children,passThrough=False)
                layer['_clip']=[*top,nw,nh]
            elif kind=='grouplayer':
                layer['childLayers']=list(walk(layer.get('childLayers',[]),data,path,top,offset,clip,chain))
                layer['_clip']=[*top,w,h]
            else:
                frames=[]
                for cel in layer.get('frames',[]):
                    begin=int(cel['frameNumber'])+offset;end=begin+int(cel.get('duration',1))
                    begin,end=max(begin,clip[0]),min(end,clip[1])
                    if end<=begin:continue
                    cel['frameNumber']=begin;cel['duration']=end-begin
                    if cel.get('fileName'):
                        cel['fileName']=os.path.relpath(asset_path(path,cel['fileName']),root).replace(os.sep,'/')
                        cel['position']=[top[0]+cel['position'][0],top[1]+cel['position'][1]]
                    for alternative in cel.get('meta',{}).get('handoff',{}).values():
                        if isinstance(alternative,dict) and alternative.get('fileName'):
                            alternative['fileName']=os.path.relpath(asset_path(path,alternative['fileName']),root).replace(os.sep,'/')
                            alternative['position']=list(cel['position'])
                    cel['_depth']={'U8':8,'U16':16,'F16':32,'F32':32}[data['colorDepth']]
                    frames.append(cel)
                layer['frames']=frames;layer['_clip']=[*top,w,h]
            layer.update(position=[width/2,height/2],width=width,height=height)
            yield layer
    result=copy.deepcopy(document)
    result['layers']=list(walk(document['layers'],document,root,(0,0),0,(document['startTime'],document['endTime']),set()))
    return result


def blend(back,front,mode):
    from merge_groups import over
    if mode in ('normal','multiply','screen','overlay','add','darken','lighten'):return over(back,front,mode)
    f,d=front[...,:3],back[...,:3]
    if mode=='difference':mixed=np.abs(d-f)
    elif mode=='exclusion':mixed=d+f-2*d*f
    elif mode=='hard_light':mixed=np.where(f<=.5,2*f*d,1-2*(1-f)*(1-d))
    elif mode in ('soft_light','soft_light_svg'):
        g=np.where(d<=.25,((16*d-12)*d+4)*d,np.sqrt(np.maximum(d,0)))
        mixed=np.where(f<=.5,d-(1-2*f)*d*(1-d),d+(2*f-1)*(g-d))
    else:raise UnsupportedRender('OCA template does not implement paint blend '+mode)
    a,b=front[...,3:4],back[...,3:4];alpha=a+b*(1-a)
    rgb=f*a*(1-b)+d*b*(1-a)+mixed*a*b
    return np.concatenate((np.divide(rgb,alpha,out=np.zeros_like(rgb),where=alpha!=0),alpha),axis=2)


def composite(document,assets,frame):
    from oca_companions import positioned,active_frame
    from oca_vectors import raster_frame
    from oca_images import load
    root=root_for(document,assets);view=expanded(document,root)
    width,height=document['width'],document['height'];zero=np.zeros((height,width,4),np.float32)
    def clip(image,box):
        x,y,w,h=box;xs=np.arange(width)+.5;ys=np.arange(height)+.5
        image[...,3]*=((xs>=x)&(xs<x+w))[None,:]*((ys>=y)&(ys<y+h))[:,None]
        return image
    def render(items,back):
        for layer in items:
            if not layer.get('visible',True) or layer.get('reference'):continue
            if layer['type']=='grouplayer':
                if layer.get('passThrough',False):back=render(layer.get('childLayers',[]),back);continue
                image=clip(render(layer.get('childLayers',[]),zero.copy()),layer['_clip'])
            else:
                cel=active_frame(layer,frame)
                if not cel or not cel.get('fileName'):continue
                cel=raster_frame(cel)
                if cel['fileName'].lower().endswith('.svg'):raise UnsupportedRender(layer['name']+': SVG template needs a rendered raster companion')
                pixels=load(root/cel['fileName'],{'U8':8,'U16':16,'F16':32,'F32':32}.get(cel.get('colorDepth'),cel.get('_depth',8)))
                image=positioned(pixels,width,height,*map(float,cel['position']))
                image[...,3]*=float(cel.get('opacity',1));image=clip(image,layer['_clip'])
            image[...,3]*=float(layer.get('opacity',1))
            if layer.get('inheritAlpha'):image[...,3]*=back[...,3]
            back=blend(back,image,layer.get('blendingMode','normal'))
        return back
    background=zero.copy();background[:]=document.get('backgroundColor',[0,0,0,0])
    return render(view['layers'],background)
