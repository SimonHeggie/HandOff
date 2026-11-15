"""Native Blender 5.3 rendering, disabled-source capture and image reuse.

Run with factory startup, --disable-autoexec, -noaudio and a /tmp job root.
All scenes, images and caches are private test fixtures.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT.parent), str(ROOT)]


def run():
    import bpy
    import numpy as np
    import handoff as addon
    from psd_worker import assemble, find_inputs, read_rgba
    addon.register()
    # Exercise production prepare explicitly; avoid launching an asynchronous
    # worker from render_complete while assertions inspect the same job.
    for handlers in (bpy.app.handlers.render_pre,bpy.app.handlers.render_complete,bpy.app.handlers.render_cancel):
        for fn in list(handlers):
            if getattr(fn,'__module__','') == addon.__name__:handlers.remove(fn)
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU'
    scene.cycles.samples=1;scene.cycles.use_denoising=False
    scene.render.resolution_x=64;scene.render.resolution_y=48;scene.render.resolution_percentage=100
    scene.render.film_transparent=True
    first=scene.view_layers[0];first.name='Enabled';second=scene.view_layers.new('Disabled');second.use=False
    # Existing UUIDs must survive an ordinary rename; export does not create
    # new UUIDs or alter the source View Layer render flags.
    scene['_handoff_sync_scene_id']='native-scene';second['_handoff_view_layer_id']='native-layer'
    tree=bpy.data.node_groups.new('Disabled rendering fixture','CompositorNodeTree');scene.compositing_node_group=tree
    node=tree.nodes.new('CompositorNodeOutputFile')
    while len(node.file_output_items):node.file_output_items.remove(node.file_output_items[0])
    for index,layer in enumerate((first,second)):
        node.file_output_items.new('RGBA',layer.name)
        source=tree.nodes.new('CompositorNodeRLayers');source.scene=scene;source.layer=layer.name
        tree.links.new(source.outputs['Image'],node.inputs[index])
    with tempfile.TemporaryDirectory(prefix='handoff-disabled-native-') as folder:
        folder=Path(folder);node.directory=str(folder/'native');node.file_name='Raw'
        for fmt,depth in [('PSD',8),('PSD',16),('PSD',32),('SVG',8),('PNG',8),('OCA',8)]:
            item=node.blend_artwork_exports.add();item.format=fmt;item.depth=str(depth)
            item.path=str(folder/'outputs');item.relative_path=False;item.use_custom_name=True
            item.custom_name=fmt+str(depth);item.flatten=fmt=='PNG';item.use_groups=False
            item.bake_svg_png=True
        addon.prepare(scene)
        session=addon.SESSIONS[scene.as_pointer()];jobs=session['jobs']
        assert len(jobs)==6
        state=jobs[0]['manifest'][1]
        assert state['render_disabled'] and state['render_was_disabled']
        assert state['disabled_sources']==['Scene/Disabled']
        old_identity=state['source_identity'];second.name='Renamed disabled'
        assert addon._source_render_state(tree,next(l.from_socket for l in tree.links if l.to_socket==node.inputs[1]),scene)['source_identity']==old_identity
        second.name='Disabled'
        original_file=Path(jobs[0]['dir'])/(jobs[0]['manifest'][1]['slug']+'0001.png')
        bpy.ops.render.render(write_still=False)
        assert not original_file.exists(),'Disabled View Layer unexpectedly wrote a cache image'
        for job in jobs:
            assert not second.use
            result=assemble(job);assert Path(result).exists()
            entries=find_inputs(job)
            assert entries[1][0]['render_placeholder']
            assert read_rgba(entries[1][1],16 if job['cache_kind']=='PNG16' else 8)[...,3].max()==0
        # No previous image: native EXR32 and PNG8/16 create hidden blanks.
        # Render again with both View Layers enabled to establish last images.
        with patch.object(addon, 'launch_worker') as launch:
            addon.dispatch(scene)
            assert launch.call_count == 1
            written=json.loads(Path(launch.call_args.args[1]).read_text())
            assert written['render_performance']['preparation_seconds'] >= 0
            assert written['render_performance']['render_and_cache_seconds'] > 0
        second.use=True
        addon.prepare(scene);rendered=addon.SESSIONS[scene.as_pointer()]
        bpy.ops.render.render(write_still=False)
        (Path(rendered['root'])/'jobs.json').write_text(json.dumps({'jobs':rendered['jobs']}))
        addon.cleanup(scene,discard=False);second.use=False
        addon.prepare(scene);held=addon.SESSIONS[scene.as_pointer()]
        bpy.ops.render.render(write_still=False)
        for job in held['jobs']:
            assemble(job);entry,path=find_inputs(job)[1]
            assert not entry['render_placeholder']
            assert read_rgba(path,16 if job['cache_kind']=='PNG16' else 8)[...,3].max()>0
            assert any('last rendered image' in msg for msg in job['_notices'])
        addon.cleanup(scene,discard=False)
        assert not second.use
    print('DISABLED_NATIVE_PASS: native skipped cache reproduced, 6 destinations exported, PNG8/16 and EXR32 reused, source flags unchanged',flush=True)


if __name__=='__main__':
    try:run()
    except BaseException:
        traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
    sys.stdout.flush();sys.stderr.flush();os._exit(0)
