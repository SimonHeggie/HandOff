"""Inspect the installed GP SVG importer and drawing-copy API in Blender 5.3."""
import bpy,json,os
from pathlib import Path
root=Path(os.environ['BLUIK_TEST_OUTPUT']);root.mkdir(parents=True,exist_ok=True)
p=root/'probe.svg';p.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10" viewBox="0 0 20 10"><path d="M 2 3 L 12 3 L 2 9 Z" fill="#ff0000"/></svg>')
bpy.ops.object.select_all(action='DESELECT')
result=bpy.ops.wm.grease_pencil_import_svg(filepath=str(p),scale=1.0,use_scene_unit=False,recenter_bounds=False)
obj=bpy.context.object
report=dict(result=list(result),object=obj.name,matrix=[list(r) for r in obj.matrix_world],layers=[])
for l in obj.data.layers:
 frames=[]
 for f in l.frames:
  frames.append(dict(frame=f.frame_number,strokes=[[list(p.position) for p in s.points] for s in f.drawing.strokes]))
 report['layers'].append(dict(name=l.name,frames=frames,copy_doc=l.frames.copy.__doc__))
report['drawing_attributes']=[(a.name,a.data_type,a.domain) for a in obj.data.layers[0].frames[0].drawing.attributes]
# Try copying a drawing between data blocks using the actual RNA API.
new=bpy.data.grease_pencils.new('Copy target');layer=new.layers.new('Drawing',set_active=True)
try:
 frame=layer.frames.copy(obj.data.layers[0].frames[0],frame_number=8)
 report['cross_data_copy']=dict(frame=frame.frame_number,strokes=len(frame.drawing.strokes))
except Exception as exc:report['cross_data_copy']=str(exc)
(root/'svg-probe.json').write_text(json.dumps(report,indent=2));print('SVG_API_PROBE',json.dumps(report),flush=True)
