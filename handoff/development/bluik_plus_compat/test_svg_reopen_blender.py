"""Reopen a clean SVG OCA import and verify its generated preview is packed.

Open the imported .blend in isolated Blender. Set BLUIK_SOURCE to the extracted
compatibility ZIP and BLUIK_TEST_OUTPUT outside the installed package.
"""
import bpy,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(os.environ['BLUIK_SOURCE']).parent))
import bluik_plus
bluik_plus.register()
objects=[o for o in bpy.context.scene.objects if o.get('oca_layer_id')]
assert objects,'Saved import has no artwork'
previews=[im for im in bpy.data.images if 'bluik-oca-svg-' in im.filepath]
assert previews and all(im.packed_file and len(im.pixels)>0 for im in previews),'SVG preview was not packed'
scene=bpy.context.scene;scene.render.resolution_percentage=12;scene.cycles.samples=1
out=Path(os.environ['BLUIK_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
scene.render.filepath=str(out/'reopened.png');bpy.ops.render.render(write_still=True)
bluik_plus.unregister()
assert not any(fn.__module__.startswith('bluik_plus') for fn in bpy.app.handlers.frame_change_post)
print('CLEAN_PACKED_REOPEN_PASS',len(objects),len(previews),flush=True)
