"""Run the real Retry operator with package-only imports and untagged GP data."""
import sys,os,json,traceback
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))  # Deliberately do not add the add-on root.

def run():
 import bpy
 import handoff as addon
 from handoff.svg_hybrid import export_hybrid_svg
 from handoff.disabled_layers import transparent_cache
 from xml.etree import ElementTree as E
 assert str(ROOT) not in sys.path
 assert 'layer_stack' not in sys.modules
 addon.register();scene=bpy.context.scene
 for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
 scene.render.resolution_x=scene.render.resolution_y=128;scene.render.resolution_percentage=100;scene.render.film_transparent=True
 cam=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(cam)
 cam.location=(0,0,10);cam.data.type='ORTHO';cam.data.ortho_scale=8;scene.camera=cam
 parent=bpy.data.collections.new('Assets.ungroup');parent.color_tag='COLOR_02';scene.collection.children.link(parent)
 group=bpy.data.collections.new('Shine');group.color_tag='NONE';parent.children.link(group)
 gp=bpy.data.grease_pencils.new('Shared');obj=bpy.data.objects.new('Sprite',gp);group.objects.link(obj);obj.use_grease_pencil_lights=False
 mat=bpy.data.materials.new('Paint');bpy.data.materials.create_gpencil_data(mat);gp.materials.append(mat)
 mat.grease_pencil.show_fill=True;mat.grease_pencil.show_stroke=False;mat.grease_pencil.fill_color=(1,1,1,1)
 layer=gp.layers.new('Drawing',set_active=True);layer.use_lights=False;draw=layer.frames.new(1).drawing;draw.add_strokes([4]);draw.set_types(type='POLY')
 stroke=draw.strokes[0];stroke.cyclic=True;stroke.fill_id=1;stroke.hide_stroke=True
 for p,co in zip(stroke.points,[(-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0)]):p.position=co;p.opacity=1
 copy=obj.copy();group.objects.link(copy);copy.location.x=2
 view=scene.view_layers[0];view.name='Shine';view.update()
 tree=bpy.data.node_groups.new('Retry fixture','CompositorNodeTree');scene.compositing_node_group=tree
 node=tree.nodes.new('CompositorNodeOutputFile')
 while len(node.file_output_items):node.file_output_items.remove(node.file_output_items[0])
 node.file_output_items.new('RGBA','Shine')
 source=tree.nodes.new('CompositorNodeRLayers');source.layer=view.name;source.scene=scene
 tree.links.new(source.outputs['Image'],node.inputs[0])
 output=Path(os.environ['LAYERED_TEST_OUTPUT']);output.mkdir(parents=True,exist_ok=True)
 cache=output/'png8';cache.mkdir(exist_ok=True);vectors=output/'vectors';vectors.mkdir(exist_ok=True)
 item=node.blend_artwork_exports.add();item.format='SVG';item.enabled=True;item.depth='8';item.path=str(output/'exports');item.relative_path=False;item.use_groups=True
 svg=vectors/'source.svg';ok,reason=export_hybrid_svg(scene,view,svg,allow_raster=False);assert ok,reason
 transparent_cache(cache/'layer_L0000_.png',(128,128),8)
 job=dict(format='SVG',depth=8,extension='.png',cache_kind='PNG8',dir=str(cache),dest=str(output/'exports/Artwork.svg'),
   node_name=node.name,export_index=0,save_as_render=True,hierarchy='GROUPS',overwrite=True,
   psd_target='PHOTOSHOP',psd_link_svg_fallbacks=False,psd_svg_sidecars=True,
   manifest=[dict(name='Shine',slug='layer_L0000_',collection_path='Assets.ungroup/Shine',vector_svg=str(svg))])
 (output/'jobs.json').write_text(json.dumps(dict(jobs=[job])))
 scene.blend_psd_retry_folder=str(output)
 before=(obj.data.as_pointer(),tuple(copy.location),view.use)
 with patch.object(addon,'launch_worker') as launch:
  result=bpy.ops.blend_psd.retry_job()
  assert result=={'FINISHED'},result
  launch.assert_called_once()
 data=json.loads((output/'jobs-retry.json').read_text());entry=data['jobs'][0]['manifest'][0]
 assert 'psd_target' not in data['jobs'][0] and 'psd_link_svg_fallbacks' not in data['jobs'][0]
 assert 'psd_svg_sidecars' not in data['jobs'][0]
 assert entry['collection_colors'][-1]=='NO_COLOR',entry
 root=E.parse(entry['vector_svg']).getroot();INK='{http://www.inkscape.org/namespaces/inkscape}';SVG='{http://www.w3.org/2000/svg}'
 assert len(list(root.iter(SVG+'use')))==1
 groups=[g for g in root.iter() if g.get('data-handoff-object') or g.get(INK+'groupmode')=='layer']
 assert groups and all(g.get(INK+'highlight-color')=='#ffffff' for g in groups),[(g.attrib) for g in groups]
 assert before==(obj.data.as_pointer(),tuple(copy.location),view.use)
 assert str(ROOT) not in sys.path and 'layer_stack' not in sys.modules
 addon.unregister();print('PACKAGE_RETRY_PASS: actual operator, fresh GP/clone extraction, no worker path preload, white untagged collection',flush=True)

if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
 sys.stdout.flush();sys.stderr.flush();os._exit(0)
