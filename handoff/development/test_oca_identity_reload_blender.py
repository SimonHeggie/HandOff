"""Reopen the native fixture and verify saved identities and handler cleanup."""
import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT)]
import bpy
import handoff as addon
from handoff.oca_controls import input_identity
out=Path(os.environ['HANDOFF_TEST_OUTPUT'])
expected=json.loads((out/'exports/Mixed.oca/Mixed.oca').read_text())
def nodes(ns):
 for n in ns:
  yield n;yield from nodes(n['childLayers'])
ids={n['meta']['handoff']['sourceIdentity'] for n in nodes(expected['layers']) if n['type']!='grouplayer'}
def ours():
 return {name:[fn.__name__ for fn in getattr(bpy.app.handlers,name) if fn.__module__.startswith('handoff')] for name in ('render_init','render_pre','render_post','render_complete','render_cancel','load_post')}
assert not any(ours().values()),ours()
counts=[]
for _ in range(2):
 addon.register();node=next(n for n in addon.scene_tree(bpy.context.scene).nodes if n.bl_idname=='CompositorNodeOutputFile')
 assert ids=={input_identity(node,s) for s in node.inputs if s.is_linked}
 active=ours();assert all(len(names)==len(set(names)) for names in active.values()),active
 counts.append(active);addon.unregister();assert not any(ours().values()),ours()
assert counts[0]==counts[1]
(out/'reload-result.json').write_text(json.dumps(dict(saved_ids=True,registration_cycles=2,duplicate_handlers=False,handlers=counts[0]),indent=2))
print('OCA_IDENTITY_RELOAD_PASS',flush=True)
