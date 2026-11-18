"""Read-only native API/import probe; no preferences or installed sources edited."""
import bpy,json,os,sys,traceback
from pathlib import Path
root=Path(os.environ['BLUIK_SOURCE']);sys.path.insert(0,str(root.parent))
report={'blender':bpy.app.version_string,'source':str(root),'ops':{}}
for name in ('wm.grease_pencil_import_svg','wm.grease_pencil_import_svg_sequence','object.image_plane_add'):
 try:
  operator=bpy.ops
  for part in name.split('.'):operator=getattr(operator,part)
  report['ops'][name]={p.identifier:str(p.type) for p in operator.get_rna_type().properties}
 except Exception as exc:report['ops'][name]=str(exc)
try:
 import bluik_plus
 report['bl_info']=bluik_plus.bl_info
 bluik_plus.register();report['register']=True
 bluik_plus.unregister();report['unregister']=True
except Exception:
 report['error']=traceback.format_exc()
out=Path(os.environ['BLUIK_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
(out/'probe.json').write_text(json.dumps(report,indent=2));print('BLUIK_PROBE',json.dumps(report),flush=True)
