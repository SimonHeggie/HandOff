"""Read production scene; recapture OCA visibility against copied retained pixels.

Never saves the source .blend or writes to its original render caches/exports.
"""
import os,sys,json,copy,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
import bpy
import handoff as addon
from handoff.oca_controls import capture_source
from pillow_loader import ensure_pillow
ensure_pillow()
from psd_worker import assemble
from oca_project import nodes
from oca_validation import validate
addon.register();scene=bpy.data.scenes['Hatshepsut'];bpy.context.window.scene=scene
tree=addon.scene_tree(scene);node=max((n for n in tree.nodes if n.bl_idname=='CompositorNodeOutputFile'),key=lambda n:len(addon.connected(tree,n)))
raw=dict(addon.connected(tree,node))
source=Path(os.environ['HANDOFF_SOURCE_JOB']);job=copy.deepcopy(next(j for j in json.loads(source.read_text())['jobs'] if j['format']=='OCA'))
out=Path(os.environ['HANDOFF_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
cache=out/'cache';shutil.copytree(job['dir'],cache,dirs_exist_ok=True)
job.update(dir=str(cache),dest=str(out/'Character.oca'),oca_layout='PROJECT',oca_keep_png=False,overwrite=True,allow_gp_cache_repair=False)
job['oca_options'].update(writeJson=False,writeTemplate=False)
changes=[]
for i,entry in enumerate(job['manifest']):
 before=copy.deepcopy(entry.get('oca_group_visibility',{}))
 entry.update(capture_source(tree,raw[entry['name']],scene,entry['collection_path'],addon.source_render_layers))
 if before!=entry['oca_group_visibility']:changes.append(dict(name=entry['name'],before=before,after=entry['oca_group_visibility']))
 if entry.get('vector_svg'):
  target=out/f'source-{i}.svg';shutil.copy2(entry['vector_svg'],target);entry['vector_svg']=str(target)
path=Path(assemble(job));doc=json.loads(path.read_text());validate(doc,path.parent,document_path=path)
leaves=[n for n in nodes(doc['layers']) if n['type']!='grouplayer']
for prefix,mode in [('Eyes_Shade','multiply'),('Eyes_Reflect','add')]:
 layer=next(n for n in leaves if n['name'].startswith(prefix));assert layer['visible'] and layer['blendingMode']==mode,(layer['name'],layer['visible'],layer['blendingMode'])
# Render exclusion must never override explicit author visibility controls.
entry=next(e for e in job['manifest'] if e['name'].startswith('Eyes_Shade'))
coll=bpy.data.collections['Eye'];old=coll.hide_viewport
try:
 coll.hide_viewport=True
 assert not capture_source(tree,raw[entry['name']],scene,entry['collection_path'],addon.source_render_layers)['oca_group_visibility']['Eye']
finally:coll.hide_viewport=old
addon.unregister()
(out/'result.json').write_text(json.dumps(dict(document=str(path),visibility_changes=changes,artwork_layers=len(leaves),explicit_visibility_respected=True),indent=2))
print('OCA_PRODUCTION_VISIBILITY_PASS',json.dumps(changes),flush=True)
