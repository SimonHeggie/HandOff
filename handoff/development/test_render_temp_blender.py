"""Reproduce a missing session directory in an isolated Blender 5.3 process.

Run with --factory-startup --disable-autoexec --python this_file.py.
Only this fresh process's own bpy.app.tempdir is removed; no user file is read.
"""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import traceback
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT.parent), str(ROOT)]


def run():
    import bpy
    import blend_psd_tools as addon
    assert bpy.app.version[:2] == (5,3)
    addon.register()
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.cycles.use_auto_tile = True
    scene.cycles.tile_size = 64
    scene.render.resolution_x = scene.render.resolution_y = 320
    scene.render.resolution_percentage = 100
    tree = bpy.data.node_groups.new('Temp recovery fixture', 'CompositorNodeTree')
    scene.compositing_node_group = tree
    source = tree.nodes.new('CompositorNodeRLayers')
    source.scene = scene
    source.layer = bpy.context.view_layer.name
    with tempfile.TemporaryDirectory(prefix='compio-temp-recovery-') as folder:
        addon.create_companion(tree, NS(location=NS(x=0,y=0)), Path(folder),
                               [dict(name='Combined',socket=source.outputs['Image'])], 'PNG8')
        session = Path(bpy.app.tempdir)
        assert session.is_dir() and session.name.startswith('blender_')
        shutil.rmtree(session)
        assert not session.exists()
        bpy.ops.render.render(write_still=False)
        assert session.is_dir(), 'render_pre did not restore the session directory'
        images = list(Path(folder).glob('*.png'))
        assert images, 'Cycles did not produce the compositor image cache'
        from pillow_loader import ensure_pillow
        ensure_pillow()
        from PIL import Image
        with Image.open(images[0]) as image:
            assert image.size == (320,320)
            assert image.getchannel('A').getextrema()[1] > 0
    print('PASS: missing Blender session directory restored; tiled Cycles render and PNG cache completed', flush=True)


if __name__ == '__main__':
    try:
        run()
    except BaseException:
        traceback.print_exc()
        sys.stdout.flush(); sys.stderr.flush(); os._exit(1)
    sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
