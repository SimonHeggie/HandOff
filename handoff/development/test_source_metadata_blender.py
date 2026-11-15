"""Persistent source identity, duplicate ownership and fresh SVG/PSD settings."""
import os,sys,json,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT)]

def run():
 import bpy
 import handoff as addon
 from svg_metadata import source_metadata,ensure_unique_ids
 addon.register();scene=bpy.context.scene
 data=bpy.data.grease_pencils.new('Source Data');original=bpy.data.objects.new('Original',data);scene.collection.objects.link(original)
 ensure_unique_ids(scene);old=source_metadata(scene,original)
 clone=original.copy();clone.name='A Copied Object';scene.collection.objects.link(clone)
 independent=original.copy();independent.data=data.copy();independent.name='B Independent';scene.collection.objects.link(independent)
 original.name='Z Renamed Original';ensure_unique_ids(scene)
 actual=source_metadata(scene,original);copy=source_metadata(scene,clone);separate=source_metadata(scene,independent)
 assert actual['object_id']==old['object_id']
 assert copy['object_id']!=actual['object_id'] and separate['object_id']!=actual['object_id']
 assert copy['data_id']==actual['data_id'] and separate['data_id']!=actual['data_id']
 output=Path(os.environ['LAYERED_TEST_OUTPUT']);output.mkdir(parents=True,exist_ok=True)
 tree=bpy.data.node_groups.new('Settings','CompositorNodeTree');scene.compositing_node_group=tree
 node=tree.nodes.new('CompositorNodeOutputFile');item=node.blend_artwork_exports.add();item.format='PSD'
 assert not item.psd_link_svg_fallbacks and item.psd_target=='PHOTOSHOP'
 item.psd_link_svg_fallbacks=True;item.psd_target='PHOTOCRAFT'
 bpy.data.libraries.write(str(output/'identity.blend'),{scene})
 bpy.ops.wm.open_mainfile(filepath=str(output/'identity.blend'),load_ui=False,use_scripts=False)
 loaded=bpy.data.objects['Z Renamed Original'];assert loaded['_asset_parts_id']==actual['object_id']
 loaded_scene=next(s for s in bpy.data.scenes if s.objects.get(loaded.name))
 saved=next(n for n in loaded_scene.compositing_node_group.nodes if n.bl_idname=='CompositorNodeOutputFile')
 assert saved.blend_artwork_exports[0].psd_link_svg_fallbacks and saved.blend_artwork_exports[0].psd_target=='PHOTOCRAFT'
 addon.unregister();print('SOURCE_METADATA_NATIVE_PASS: persistent object/data UUIDs, linked vs independent copies, rename, save/reopen and publish settings',flush=True)

if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
 sys.stdout.flush();sys.stderr.flush();os._exit(0)
