"""Native linked GP data across View Layers -> standard OCA clone references."""
import os,sys,json,copy,traceback
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor'),str(ROOT/'development')]

def run():
 import bpy
 import handoff as addon
 from test_oca_vectors_blender import fixture
 from pillow_loader import ensure_pillow
 ensure_pillow()
 from oca_project import nodes
 addon.register();scene,tree,node=fixture(bpy)
 scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
 scene.view_settings.view_transform='Standard'
 first=bpy.data.objects['First'];second=bpy.data.objects['Second'];second.data=first.data
 for obj,x in ((first,-1),(second,.25)):
  obj.animation_data_clear()
  for f in range(3):
   obj.location=(x,f*.25,0);obj.keyframe_insert(data_path='location',frame=f)
 # An independently copied datablock must remain independent, even when its
 # silhouette and style match perfectly. A rotated linked object also stays
 # independent: OCA 1.3 does not express its rotation transform.
 for name,x,shared,rotation in [('Independent',1.3,False,0),('Rotated',-1.7,True,.15)]:
  coll=bpy.data.collections.new(name);scene.collection.children.link(coll)
  obj=bpy.data.objects.new(name,first.data if shared else first.data.copy());coll.objects.link(obj)
  obj.location=(x,.8,0);obj.rotation_euler.z=rotation;obj.use_grease_pencil_lights=False
  view=scene.view_layers.new(name)
  for layer in scene.view_layers:
   for child in layer.layer_collection.children:
    if child.name in ('First','Second','Independent','Rotated'):child.exclude=child.name!=layer.name
  source=tree.nodes.new('CompositorNodeRLayers');source.scene=scene;source.layer=view.name
  node.file_output_items.new('RGBA',name);tree.links.new(source.outputs['Image'],node.inputs[len(node.file_output_items)-1])
 out=Path(os.environ['HANDOFF_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
 node.directory=str(out/'native');node.file_name='Shared';scene.render.filepath=str(out/'native/render_')
 item=node.blend_artwork_exports.add();item.format='OCA';item.enabled=True;item.depth='8';item.path=str(out/'exports');item.relative_path=False
 item.use_groups=True;item.oca_keep_png=True;item.oca_write_json=False;item.oca_write_template=False
 captures=[]
 with patch.object(addon,'launch_worker',side_effect=lambda scene,path,*a,**k:captures.append(Path(path))):bpy.ops.render.render(animation=True)
 assert len(captures)==1
 addon.unregister()
 from psd_worker import run as convert
 assert convert(captures[0])==0
 path=out/'exports/Shared.oca/Shared.oca';doc=json.loads(path.read_text());layers=list(nodes(doc['layers']))
 clones=[n for n in layers if n['type']=='clonelayer'];assert len(clones)==1,[(n['name'],n['type']) for n in layers]
 source=next(n for n in layers if n['id']==clones[0]['source']['id'])
 assert source['type']=='vectorlayer' and source['meta']['handoff']['sourceName'] in ('First','Second')
 assert clones[0]['meta']['handoff']['sourceName'] in ('First','Second')
 assert all(n['type']=='vectorlayer' for n in layers if n.get('meta',{}).get('handoff',{}).get('sourceName') in ('Independent','Rotated'))
 from oca_validation import validate
 validate(doc,path.parent,document_path=path)
 (out/'result.json').write_text(json.dumps(dict(document=str(path),clone=clones[0]['name'],source=source['name'],independent_copy_preserved=True,unsupported_rotation_preserved=True,frames=3),indent=2))
 print('OCA_SHARED_LAYERS_NATIVE_PASS',str(path),flush=True)
if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();raise
