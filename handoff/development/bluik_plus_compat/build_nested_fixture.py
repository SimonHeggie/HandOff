"""Create a small ID-clone/nested interoperability fixture from a real export."""
import copy,json,shutil,sys
from pathlib import Path

def build(source,output):
 source=Path(source).resolve();output=Path(output).resolve()
 if output.exists():raise FileExistsError(output)
 target=output/'Cloned.oca';shutil.copytree(source.parent,target)
 path=target/source.name;document=json.loads(path.read_text())
 def nodes(items):
  for n in items:
   yield n;yield from nodes(n.get('childLayers',[]))
 artwork=next(n for n in nodes(document['layers']) if n['type']=='vectorlayer')
 clone=dict(name='ID-based clone',id='clone-reference-fixture',type='clonelayer',position=[52,32],opacity=1,visible=True,source=dict(id=artwork['id'],timeOffset=0))
 document['layers'].insert(0,clone);path.write_text(json.dumps(document,indent=4))
 parent=output/'Nested.oca';parent.mkdir()
 outer={key:copy.deepcopy(value) for key,value in document.items() if key!='layers'};outer.update(name='Nested',endTime=document['endTime']+1)
 outer['layers']=[dict(name='Nested artwork',id='nested-source-fixture',type='ocalayer',position=[document['width']/2,document['height']/2],source=dict(relFileName='../Cloned.oca/'+source.name,absFileName='/unavailable.oca',id='',timeOffset=1))]
 dest=parent/'Nested.oca';dest.write_text(json.dumps(outer,indent=4));return dest
if __name__=='__main__':print(build(*sys.argv[1:3]))
