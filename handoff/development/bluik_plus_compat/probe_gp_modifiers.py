import bpy,json,os
from pathlib import Path
report={}
data=bpy.data.grease_pencils.new('Probe');obj=bpy.data.objects.new('Probe',data);bpy.context.scene.collection.objects.link(obj)
for kind in ('GREASE_PENCIL_TIME','GREASE_PENCIL_OPACITY'):
 try:
  mod=obj.modifiers.new('Probe '+kind,kind)
  report[kind]={p.identifier:dict(type=p.type,description=p.description,value=str(getattr(mod,p.identifier,None)),enum=[i.identifier for i in p.enum_items] if p.type=='ENUM' else None) for p in mod.bl_rna.properties if p.identifier not in ('rna_type',)}
 except Exception as exc:report[kind]=str(exc)
out=Path(os.environ['BLUIK_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True);(out/'modifiers.json').write_text(json.dumps(report,indent=2))
print('GP_MODIFIER_PROBE',json.dumps(report),flush=True)
