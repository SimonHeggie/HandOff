"""Blender 5.3: collections, referenced fonts, cancellation and recovery safety."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import traceback
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT)]
SVG='{http://www.w3.org/2000/svg}'


def run():
    import bpy
    import handoff as addon
    from font_delivery import system_font_directory, user_font_directory, font_names
    from builtin_font import embedded_bfont
    from psd_worker import run as worker
    addon.register()
    assert bpy.app.version[:2]==(5,3)
    directory=Path(os.environ.get('HANDOFF_TEST_OUT') or tempfile.mkdtemp(prefix='handoff-font-groups-'))
    directory.mkdir(parents=True,exist_ok=True)
    company=directory/'company-fonts';company.mkdir(exist_ok=True)
    original_font=next(Path(system_font_directory()).rglob('*.ttf'))
    real_family=font_names(original_font)['family']
    builtin=embedded_bfont(bpy.app.binary_path)
    source=company/'Renamed-font.ttf';shutil.copy2(original_font,source)
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    sentinel=company/'important-project.blend';sentinel.write_bytes(b'project that must survive')
    scene=bpy.context.scene
    for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
    scene.view_layers[0].name='Art'
    scene.render.engine='CYCLES';scene.cycles.samples=1;scene.cycles.device='CPU'
    scene.render.resolution_x=scene.render.resolution_y=64;scene.render.resolution_percentage=100
    scene.render.film_transparent=True
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
    parent=bpy.data.collections.new('Art');scene.collection.children.link(parent)
    collections=[]
    for name in ('Case / One','Case Two'):
        c=bpy.data.collections.new(name);parent.children.link(c);collections.append(c)
    camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera)
    camera.location=(0,0,10);camera.data.type='ORTHO';camera.data.ortho_scale=8;scene.camera=camera
    material=bpy.data.materials.new('Flat text');material.use_nodes=True;material.node_tree.nodes.clear()
    emission=material.node_tree.nodes.new('ShaderNodeEmission');output=material.node_tree.nodes.new('ShaderNodeOutputMaterial')
    material.node_tree.links.new(emission.outputs[0],output.inputs['Surface'])
    font=bpy.data.fonts.load(str(source));font.name='Misleading datablock name';font.pack()
    for index,c in enumerate(collections):
        data=bpy.data.curves.new('Text data','FONT');data.body='Editable text';data.size=.6;data.materials.append(material)
        if index==0:data.font=font
        obj=bpy.data.objects.new('Label '+str(index),data);c.objects.link(obj);obj.location=(-3,index*2,0)
    tree=bpy.data.node_groups.new('Fixture compositor','CompositorNodeTree');scene.compositing_node_group=tree
    layers=tree.nodes.new('CompositorNodeRLayers');layers.scene=scene;layers.layer='Art'
    node=tree.nodes.new('CompositorNodeOutputFile');node.file_name='Fixture';node.directory=str(directory/'native')
    node.format.media_type='IMAGE';node.format.file_format='PNG';node.file_output_items.clear();node.file_output_items.new('RGBA','Art')
    tree.links.new(layers.outputs['Image'],node.inputs[0])
    # A similarly named authored node is deliberately left unmarked.
    authored=tree.nodes.new('CompositorNodeOutputFile');authored.name='__blend_psd_TEMP_0123456789'
    authored.directory=str(directory/'authored');authored.mute=True
    addon.migrate_legacy(node)
    for item in node.blend_artwork_exports:item.enabled=False
    outputs=[]
    for kind,folder in (('SVG','svg'),('FONTS','fonts-one'),('FONTS','fonts-two')):
        item=node.blend_artwork_exports.add();item.format=kind;item.enabled=True;item.depth='8'
        assert item.font_directory==system_font_directory()
        if kind=='FONTS':assert item.path==user_font_directory() and not item.relative_path
        item.path=str(directory/folder);item.relative_path=False;item.font_directory=str(company)
        if kind=='SVG':item.use_groups=True
        outputs.append(item)
    bpy.context.view_layer.update()
    originals={n.name for n in tree.nodes}
    addon.prepare(scene);session=addon.SESSIONS[scene.as_pointer()];cache=Path(session['root'])
    assert cache.is_dir() and len(session['jobs'])==3
    addon.cancel_render(scene)
    assert not cache.exists()
    assert {n.name for n in tree.nodes}==originals
    assert sentinel.read_bytes()==b'project that must survive'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    print('CANCEL_PASS',flush=True)
    # An autosave/recovery may contain a marked cache node; load must remove
    # only that node and preserve the similarly named authored output.
    addon.prepare(scene)
    recovery=directory/'recovery-fixture.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(recovery))
    addon.cleanup(scene)
    bpy.ops.wm.open_mainfile(filepath=str(recovery),load_ui=False,use_scripts=False)
    scene=bpy.context.scene;tree=scene.compositing_node_group
    assert tree.nodes.get('__blend_psd_TEMP_0123456789') is not None
    assert not any(n.get('_handoff_temporary',False) for n in tree.nodes)
    print('RECOVERY_PASS',flush=True)
    # Real rendering exercises the handlers; capture dispatch without starting
    # a second process so we can inspect the complete retained manifest.
    manifests=[]
    addon.launch_worker=lambda s,m,l,skipped=False:manifests.append(Path(m))
    bpy.ops.render.render(write_still=False)
    assert manifests
    assert not any(n.get('_handoff_temporary',False) for n in tree.nodes)
    assert worker(manifests[-1])==0
    data=json.loads(manifests[-1].read_text())
    font_jobs=[j for j in data['jobs'] if j['format']=='FONTS'];assert len(font_jobs)==2
    for job in font_jobs:
        manifest=json.loads(Path(job['dest']).read_text())
        assert manifest['complete'] and len(manifest['text_objects'])==2
        assert {f['family'] for f in manifest['fonts']}=={real_family,'Bfont'}
        assert not any(f['substituted'] for f in manifest['fonts'])
        for entry in manifest['fonts']:
            copied=Path(job['dest']).parent/entry['file']
            assert copied.read_bytes()==(builtin if entry['family']=='Bfont' else source.read_bytes())
        assert not list(Path(job['dest']).parent.rglob('*.blend'))
    svg_job=next(j for j in data['jobs'] if j['format']=='SVG')
    root=ET.parse(svg_job['dest']).getroot();parents={child:parent for parent in root.iter() for child in parent}
    texts=list(root.iter(SVG+'text'));assert len(texts)==2
    assert {t.get('font-family') for t in texts}=={real_family,'Bfont'}
    assert {parents[t].get('data-handoff-collection') for t in texts}=={'Case / One','Case Two'}
    assert not list((manifests[-1].parent/'vectors').glob('*.blend'))
    refreshed=addon.refresh_cached_jobs(scene,data)
    assert len([j for j in refreshed['jobs'] if j['format']=='FONTS'])==2,'Retry duplicated font outputs'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    assert sentinel.read_bytes()==b'project that must survive'
    print('PASS: two font outputs, writable user defaults, exact packed font and Bfont bytes, original SVG families, collections, cancel/recovery and snapshot cleanup',flush=True)


if __name__=='__main__':
    try:run()
    except BaseException:
        traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
    sys.stdout.flush();sys.stderr.flush();os._exit(0)
