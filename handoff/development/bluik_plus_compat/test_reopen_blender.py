"""Open an actual imported .blend with Bluik registered; verify persisted links."""
import bpy,os,sys,json
from pathlib import Path
source=Path(os.environ['BLUIK_SOURCE']);sys.path.insert(0,str(source.parent))
import bluik_plus
bluik_plus.register();scene=bpy.context.scene
objects=[o for o in scene.objects if o.get('oca_layer_id')]
clones=[o for o in objects if o.get('oca_source_id')]
assert clones
for clone in clones:
 candidates=[o for o in objects if o.get('oca_layer_id')==clone['oca_source_id'] and o.get('oca_source_file')==clone.get('oca_source_file')]
 assert len(candidates)==1,(clone.name,len(candidates))
 assert clone.data==candidates[0].data,clone.name
for frame in range(scene.frame_start,min(scene.frame_end,scene.frame_start+2)+1):scene.frame_set(frame)
from bluik_plus.oca13_import import is_standard
assert is_standard(dict(ocaVersion='1.3.0',layers=[]))
assert not is_standard(dict(ocaVersion='1.3.0',layers=[dict(pivot=[1,2])]))
bluik_plus.unregister()
assert not any(fn.__module__.startswith('bluik_plus') for fn in bpy.app.handlers.frame_change_post)
print('BLUIK_REOPEN_PASS',len(clones),'shared references',flush=True)
