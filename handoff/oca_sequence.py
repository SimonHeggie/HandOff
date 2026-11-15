"""Publish standard OCA frame arrays through the existing still OCA writer."""
import json
import shutil
import tempfile
import uuid
from pathlib import Path


def assemble_oca_sequence(job, assemble_frame):
    frames=job['oca_frames']
    numbers=[int(frame['frame']) for frame in frames]
    start,end,step=map(int,job['oca_range'])
    if numbers!=list(range(start,end+1,step)):
        raise ValueError('OCA animation cache is incomplete for the Blender animation range')
    dest=Path(job['dest']).with_suffix('.oca');assets=dest.with_suffix('')
    if not job['overwrite'] and (dest.exists() or assets.exists()):
        raise FileExistsError('Overwrite disabled for '+str(dest))
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.oca-sequence-',dir=dest.parent) as temporary:
        work=Path(temporary);staging=work/'assets';staging.mkdir()
        result=None;layers=None;copied=set()
        def nodes(items):
            for node in items:
                yield node
                yield from nodes(node.get('childLayers',[]))
        for i,frame_job in enumerate(frames):
            # Reuse cache resolution, directives, flattening, blend promotion,
            # precision and hierarchy. Temporary documents are standard OCA.
            frame_job=dict(frame_job,dest=str(work/'frame'/dest.name),overwrite=True)
            frame_job.pop('oca_frames',None);frame_job.pop('oca_range',None)
            path=Path(assemble_frame(frame_job))
            current=json.loads(path.read_text(encoding='utf-8'))
            current_nodes=list(nodes(current['layers']))
            if result is None:
                result=current;layers=current_nodes
                result['startTime']=start;result['endTime']=end+1
                for layer in layers:layer['frames']=[]
                # Read the first frame again: result and current share objects.
                current_nodes=list(nodes(json.loads(path.read_text(encoding='utf-8'))['layers']))
            elif any(current[k]!=result[k] for k in ('width','height','colorDepth','frameRate')):
                raise ValueError('OCA document dimensions, depth or frame rate changed during rendering')
            if len(layers)!=len(current_nodes):raise ValueError('OCA layer hierarchy changed during rendering')
            duration=(numbers[i+1] if i+1<len(numbers) else end+1)-numbers[i]
            for target,source in zip(layers,current_nodes):
                if ({k:v for k,v in target.items() if k not in ('frames','animated','childLayers')}!=
                        {k:v for k,v in source.items() if k not in ('frames','animated','childLayers')}):
                    raise ValueError('OCA layer properties changed during rendering: '+source['name'])
                for cel in source['frames']:
                    relative=Path(cel['fileName']).relative_to(dest.stem)
                    if relative in copied:raise ValueError('Duplicate OCA frame asset: '+str(relative))
                    original=path.parent/cel['fileName'];image=staging/relative
                    image.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(original,image);copied.add(relative)
                    target['frames'].append(dict(cel,duration=duration))
                if target['type']=='paintlayer':target['animated']=len(target['frames'])>1
        publication=work/'document.oca'
        publication.write_text(json.dumps(result,indent=4,ensure_ascii=False),encoding='utf-8')
        old=assets.with_name(assets.name+'.old-'+uuid.uuid4().hex[:7])
        if assets.exists():assets.rename(old)
        try:
            staging.rename(assets);publication.replace(dest)
        except Exception:
            if assets.exists():shutil.rmtree(assets)
            if old.exists():old.rename(assets)
            raise
        if old.exists():shutil.rmtree(old)
    print('OCA ANIMATION COMPLETE:',dest,'| frames:',len(numbers),'| image assets:',len(copied),flush=True)
    return str(dest)
