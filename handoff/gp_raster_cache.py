"""Recover empty native GP Image caches using a captured direct source only.

The Hatshepsut multi-view export can yield zero GP alpha although rendering its
GP-only View Layer alone succeeds. Never bypass a compositor operation and never
render during Retry Export Without Rendering.
"""
import json
import hashlib
from pathlib import Path


def source_plan(path):
    from xml.etree import ElementTree as ET
    try:
        root=ET.parse(path).getroot()
        raw=root.get('data-compio-source-plan') or root.get('data-compio-raster-plan')
        return json.loads(raw) if raw else None
    except (OSError,ValueError,ET.ParseError):return None


def repair(job, inputs):
    import numpy as np
    from oca_images import load
    from disabled_layers import notice
    for entry,path in inputs:
        if entry.get('render_disabled') or not entry.get('gp_render_source'):continue
        depth=32 if Path(path).suffix.lower()=='.exr' else (16 if job.get('cache_kind')=='PNG16' else int(job.get('depth',8)))
        if np.any(load(path,depth)[...,3]):continue
        marker=Path(str(path)+'.gp-native-blank')
        digest=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if marker.is_file() and marker.read_text()==digest:
            entry['gp_native_blank']=True
            continue
        if not job.get('allow_gp_cache_repair',False):
            notice(job,entry['name']+': empty GP raster cache requires a new render; retry performs no rendering')
            continue
        plan=dict(entry['gp_render_source']);plan['frame']=int(job.get('frame',plan['frame']))
        import bpy
        from svg_hybrid import _load_snapshot
        scene,view,_=_load_snapshot(Path(entry['vector_svg']),plan)
        # This path is eligible only for the direct GP-only source recorded at
        # preparation, never inferred from the name of a Collection or layer.
        objects=[o for o in view.objects if not o.hide_render and o.type not in ('CAMERA','LIGHT','LIGHT_PROBE','ARMATURE','EMPTY')]
        if not objects or any(o.type!='GREASEPENCIL' for o in objects):continue
        scene.render.use_compositing=False;scene.render.use_sequencer=False
        for layer in scene.view_layers:layer.use=layer==view
        if not job.get('save_as_render',True):
            scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
            scene.view_settings.exposure=0;scene.view_settings.gamma=1;scene.view_settings.use_curve_mapping=False
        settings=scene.render.image_settings;settings.media_type='IMAGE'
        settings.file_format='OPEN_EXR' if depth==32 else 'PNG'
        settings.color_mode='RGBA';settings.color_depth=str(depth)
        from render_temp import ensure_render_tempdir
        ensure_render_tempdir(bpy.app.tempdir)
        bpy.ops.render.render(scene=scene.name,layer=view.name,write_still=False)
        target=Path(path).with_name('.gp-render-'+Path(path).name)
        try:
            bpy.data.images['Render Result'].save_render(str(target),scene=scene)
            if not np.any(load(target,depth)[...,3]):
                entry['gp_native_blank']=True
                marker.write_text(digest)
                notice(job,entry['name']+': isolated native GP render also confirms a blank frame')
                continue
            target.replace(path)
            notice(job,entry['name']+': recovered empty multi-view GP cache using its isolated native Blender render')
        finally:target.unlink(missing_ok=True)
