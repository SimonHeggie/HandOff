"""Optional artwork-only companions for OCA; no rig conversion or new destination."""
import copy
import json
import shutil
from pathlib import Path
import numpy as np


def leaves(nodes, visible=True):
    for node in nodes:
        shown = visible and node.get('visible', True) and not node.get('reference', False)
        if node['type'] == 'grouplayer': yield from leaves(node['childLayers'], shown)
        else: yield node, shown


def active_frame(layer, frame):
    return next((cel for cel in reversed(layer['frames']) if cel['frameNumber'] <= frame < cel['frameNumber']+cel['duration']), None)


def asset_path(assets, filename):
    # Serialized filenames are relative to the OCA document, including its assets folder.
    direct=Path(assets)/filename
    if direct.is_file():return direct
    sibling=Path(assets).parent/filename
    if sibling.is_file():return sibling
    return Path(assets).joinpath(*Path(filename).parts[1:])


def positioned(rgba, width, height, cx, cy):
    """Place pixels by OCA centre coordinates, including fractional positions."""
    h,w=rgba.shape[:2];left,top=cx-w/2,cy-h/2
    result=np.zeros((height,width,4),np.float32)
    if left.is_integer() and top.is_integer():
        x,y=int(left),int(top);l,t=max(0,x),max(0,y);r,b=min(width,x+w),min(height,y+h)
        if r>l and b>t:result[t:b,l:r]=rgba[t-y:b-y,l-x:r-x]
        return result
    src=rgba.copy();src[...,:3]*=src[...,3:4]
    xs=np.arange(width)-left;ys=np.arange(height)-top
    x0=np.floor(xs).astype(int);y0=np.floor(ys).astype(int)
    fx=xs-x0;fy=ys-y0
    for dy in (0,1):
        for dx in (0,1):
            xi,yi=x0+dx,y0+dy
            valid=(yi[:,None]>=0)&(yi[:,None]<h)&(xi[None,:]>=0)&(xi[None,:]<w)
            weight=(fy if dy else 1-fy)[:,None]*(fx if dx else 1-fx)[None,:]
            result+=src[np.clip(yi,0,h-1)[:,None],np.clip(xi,0,w-1)[None,:]]*(weight*valid)[...,None]
    np.divide(result[...,:3],result[...,3:4],out=result[...,:3],where=result[...,3:4]!=0)
    return result


def composite(document, assets, frame):
    from oca_render import composite as render
    return render(document,assets,frame)


def write_companions(job, document, assets):
    from oca_controls import options
    from oca_images import load, save
    from disabled_layers import notice
    settings=options(job)
    if job.get('_oca_companions') is False or not (settings['writeJson'] or settings['writeTemplate']):return
    assets=Path(assets);folder=assets/'_companions';folder.mkdir(exist_ok=True)
    # Temporary preview pixels serve optional companions without adding a second
    # representation or any attachment metadata to the published OCA document.
    document=copy.deepcopy(document)
    previews=job.get('_oca_preview_rasters',{})
    for layer,_ in leaves(document['layers']):
        for cel in layer.get('frames',[]):
            preview=previews.get(cel['id'])
            if not preview:continue
            preview=dict(preview)
            if settings['writeJson']:
                relative=Path(cel['fileName'])
                if relative.parts[0]==document['name']:relative=Path(*relative.parts[1:])
                target=folder/'images'/relative.with_suffix('.png')
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(preview['fileName'],target)
                preview['fileName']=str(target.resolve())
            cel.setdefault('meta',{}).setdefault('handoff',{})['raster']=preview
    stem=document['name'];depth={'U8':8,'U16':16,'F16':32,'F32':32}[document['colorDepth']]
    frame=int(job.get('frame',document['endTime']-1))
    frame=min(max(frame,document['startTime']),document['endTime']-1)
    if settings['writeTemplate']:
        from oca_render import UnsupportedRender
        try:image=composite(document,assets,frame)
        except UnsupportedRender as exc:
            notice(job,'OCA template omitted: '+str(exc)+'; native OCA artwork retained')
        else:
            target=folder/(stem+'.template.png')
            if depth==32:
                from psd_worker import write_blender_image
                write_blender_image(target,image,16,fmt='PNG')
                notice(job,'OCA template is a display PNG preview; native floating-point frame images are unchanged')
            else:
                source=next((asset_path(assets,cel['fileName']) for layer,_ in leaves(document['layers']) for cel in layer.get('frames',[]) if cel['fileName'] and not cel['fileName'].lower().endswith('.svg')),None)
                save(target,image,depth,source)
    if not settings['writeJson']:return
    from oca_render import expanded,root_for
    document=expanded(document,root_for(document,assets))
    slots=[];attachments={};timelines={};used=set()
    for layer,shown in leaves(document['layers']):
        base_slot=layer.get('meta',{}).get('handoff',{}).get('originalName',layer['name'])
        slot=base_slot;counter=2
        while slot in used:slot=base_slot+'-'+str(counter);counter+=1
        used.add(slot);regions={};keys=[];setup=None
        for cel in layer['frames']:
            from oca_vectors import raster_frame
            cel=raster_frame(cel)
            attachment=None
            if cel['fileName']:
                path=asset_path(assets,cel['fileName'])
                if path.suffix.lower()=='.svg':
                    notice(job,'Spine artwork companion omitted '+layer['name']+': external SVG has no rendered preview; native OCA artwork retained')
                    keys.append(dict(time=(cel['frameNumber']-document['startTime'])/document['frameRate'],name=None))
                    continue
                if path.suffix.lower()=='.exr':
                    preview=path.with_suffix('.spine.png')
                    from psd_worker import write_blender_image
                    write_blender_image(preview,load(path,32),16,fmt='PNG');path=preview
                relative=path.relative_to(assets).with_suffix('').as_posix()
                attachment=Path(relative).name
                regions[attachment]=dict(type='region',path=relative,
                    x=cel['position'][0]-document['width']/2,y=document['height']/2-cel['position'][1],
                    width=cel['width'],height=cel['height'])
            keys.append(dict(time=(cel['frameNumber']-document['startTime'])/document['frameRate'],name=attachment))
            if cel['frameNumber']<=frame<cel['frameNumber']+cel['duration']:setup=attachment
        record=dict(name=slot,bone='root')
        if setup is not None:record['attachment']=setup
        if not shown:record['color']='ffffff00'
        mode=layer.get('blendingMode','normal')
        if mode in ('multiply','screen','add'):record['blend']='additive' if mode=='add' else mode
        elif mode!='normal':notice(job,'Spine artwork companion: '+mode+' has no native slot equivalent; OCA blend mode preserved')
        slots.append(record);attachments[slot]=regions
        if len(keys)>1:
            end=(document['endTime']-document['startTime'])/document['frameRate']
            keys.append(dict(time=end,name=keys[-1]['name']))
            timelines[slot]=dict(attachment=keys)
    if depth==32:notice(job,'Spine artwork companion uses PNG previews of EXR images; native OCA floating-point assets are unchanged')
    def group_notice(nodes):
        for node in nodes:
            if node['type']=='grouplayer':
                if node.get('blendingMode','normal')!='normal':notice(job,'Spine artwork companion cannot reproduce isolated group blending; native OCA groups are unchanged')
                group_notice(node['childLayers'])
    group_notice(document['layers'])
    data=dict(skeleton=dict(spine='4.2.0',images='../',fps=document['frameRate'],x=-document['width']/2,y=-document['height']/2,
                           width=document['width'],height=document['height']),
              bones=[dict(name='root')],slots=slots,skins=[dict(name='default',attachments=attachments)],
              animations={'oca':dict(slots=timelines)} if timelines else {})
    (folder/(stem+'.spine.json')).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')


def composite_stack(root, size, depth):
    """Visible cache artwork for the existing OCA Flatten Image mode."""
    from oca_images import load
    from merge_groups import over
    from group_blends import promoted_blend, effective_layer_mode
    from layer_stack import tags
    zero=np.zeros((size[1],size[0],4),np.float32)
    def render(branch,backdrop,inherited=None):
        for child in reversed(branch['children']):
            if not child.get('oca_visible',True):continue
            if child['kind']=='group':
                if tags(child['raw']) & {'ref','reference'}:continue
                mode=promoted_blend(child)
                if mode:
                    image=render(child,zero.copy(),mode);backdrop=over(backdrop,image,mode)
                else:backdrop=render(child,backdrop)
            else:
                item=child['item']
                if item.get('flags',set()) & {'ref','reference','disabled'}:continue
                image=item.get('pixels')
                if image is None:image=load(item['source'],depth)
                backdrop=over(backdrop,image,effective_layer_mode(item,inherited))
        return backdrop
    return render(root,zero.copy())
