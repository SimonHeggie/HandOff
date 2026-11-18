"""Install the actual ZIP in isolated Blender user scripts, then render with it."""
import importlib,json,os,runpy,sys
from pathlib import Path
import bpy,addon_utils

source=Path(__file__).resolve().parents[1];sys.path.insert(0,str(source.parent))
out=Path(os.environ['HANDOFF_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
legacy=importlib.import_module('blend_psd_tools');legacy.register()
tree=bpy.data.node_groups.new('Saved legacy settings','CompositorNodeTree')
tree.use_fake_user=True
node=tree.nodes.new('CompositorNodeOutputFile');item=node.blend_artwork_exports.add()
item.format='OCA';item.trim_empty_pixels=False;item.oca_padding=4;item.oca_scale=50
saved=out/'legacy-settings.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(saved),copy=True)
archive=Path(os.environ['HANDOFF_ZIP']).resolve()
assert bpy.ops.preferences.addon_install(filepath=str(archive),overwrite=True)=={'FINISHED'}
package=addon_utils.enable('handoff',default_set=False,persistent=False)
assert package is not None and package.bl_info['name']=='HandOff'
assert node.blend_artwork_exports[0].oca_padding==4
assert node.blend_artwork_exports[0].oca_scale==50
assert not node.blend_artwork_exports[0].trim_empty_pixels
bpy.ops.wm.open_mainfile(filepath=str(saved),load_ui=False,use_scripts=False)
restored=bpy.data.node_groups['Saved legacy settings'].nodes[0].blend_artwork_exports[0]
assert restored.oca_padding==4 and restored.oca_scale==50 and not restored.trim_empty_pixels
for group in (bpy.app.handlers.render_init,bpy.app.handlers.render_pre,bpy.app.handlers.render_post,bpy.app.handlers.render_complete):
 assert not any(getattr(f,'__module__','')=='blend_psd_tools' for f in group)
 assert len([f for f in group if getattr(f,'__module__','')=='handoff'])==1
assert Path(package.__file__).is_relative_to(Path(os.environ['BLENDER_USER_SCRIPTS']))
from handoff.pillow_loader import ensure_pillow,select_wheel
ensure_pillow();assert 'cp313' in select_wheel().name
assert (Path(package.__file__).parent/'vendor/fonts/Bfont-Regular.otf').is_file()
report=dict(package=str(Path(package.__file__).parent),archive=str(archive),registration=True,
            legacy_settings_preserved=True,saved_blend_reopened=True,one_active_handler_set=True,pillow=True,bfont=True)
(out/'installation-results.json').write_text(json.dumps(report,indent=2))
addon_utils.disable('handoff',default_set=False)
os.environ['HANDOFF_PACKAGE']='handoff'
os.environ['HANDOFF_PACKAGE_PARENT']=str(Path(package.__file__).parent.parent)
runpy.run_path(str(Path(package.__file__).parent/'development/test_oca_vectors_blender.py'),run_name='__main__')
print('HANDOFF_ZIP_INSTALL_PASS',json.dumps(report),flush=True)
