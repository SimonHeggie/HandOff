"""Blender 5.3 exact Bfont glyphs and project-wide, image-independent font output."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT)]


def run():
    import bpy
    import numpy as np
    import blend_psd_tools as addon
    import importlib
    addon._font_delivery.FONTS_API_VERSION=0
    addon._font_delivery.user_font_directory=None
    addon=importlib.reload(addon)
    assert callable(addon._font_delivery.user_font_directory),'Upgrade retained stale font helpers'
    from builtin_font import embedded_bfont,cache_bfont,compatible_bfont
    from font_delivery import user_font_directory
    from psd_worker import run as worker
    from svg_hybrid import export_hybrid_svg
    assert bpy.app.version[:2]==(5,3)
    addon.register()
    out=Path(os.environ.get('COMP_IO_TEST_OUT') or tempfile.mkdtemp(prefix='compio-bfont-'))
    out.mkdir(parents=True,exist_ok=True)
    scene=bpy.context.scene
    for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
    original_file=bpy.data.filepath
    raw=embedded_bfont(bpy.app.binary_path);file=cache_bfont(bpy.app.binary_path,out)
    loaded=bpy.data.fonts.load(str(file))
    body='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,;:!?()[]{}+-/\\&%#@'
    objects=[]
    for name,font in (('Builtin',None),('Loaded twin',loaded)):
        data=bpy.data.curves.new(name,'FONT');data.body=body
        if font is not None:data.font=font
        obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj);objects.append(obj)
    bpy.context.view_layer.update();graph=bpy.context.view_layer.depsgraph
    coordinates=[]
    for obj in objects:
        evaluated=obj.evaluated_get(graph);mesh=evaluated.to_mesh()
        try:
            values=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',values)
            coordinates.append(values)
        finally:evaluated.to_mesh_clear()
    assert len(coordinates[0])>0 and np.array_equal(*coordinates),'Delivered Bfont glyphs differ from the actual built-in font'
    print('EXACT_GLYPHS_PASS',len(coordinates[0])//3,'vertices',flush=True)
    objects[0].data.body='Actual Bfont';objects[0].data.size=.5;objects[0].location=(-2,0,0)
    objects[1].hide_render=True
    extra=bpy.data.scenes.new('Other scene')
    data=bpy.data.curves.new('Hidden elsewhere','FONT');data.body='Project asset'
    obj=bpy.data.objects.new('Hidden elsewhere',data);extra.collection.objects.link(obj);obj.hide_render=True
    camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera)
    camera.location=(0,0,10);camera.data.type='ORTHO';camera.data.ortho_scale=6;scene.camera=camera
    scene.render.film_transparent=True;scene.render.resolution_x=512;scene.render.resolution_y=128;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
    material=bpy.data.materials.new('Flat text');material.use_nodes=True
    emission=material.node_tree.nodes.new('ShaderNodeEmission')
    output=next(n for n in material.node_tree.nodes if n.bl_idname=='ShaderNodeOutputMaterial')
    material.node_tree.links.new(emission.outputs[0],output.inputs['Surface'])
    objects[0].data.materials.append(material)
    bpy.context.view_layer.update()
    ok,reason=export_hybrid_svg(scene,bpy.context.view_layer,out/'Bfont-live.svg');assert ok,reason
    svg=ET.parse(out/'Bfont-live.svg').getroot();ns='{http://www.w3.org/2000/svg}'
    text=next(svg.iter(ns+'text'));assert text.get('font-family')=='Bfont'
    assert text.get('data-compio-font-substituted') is None
    assert not list(svg.iter(ns+'style')) and not list(svg.iter(ns+'font'))
    scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.device='CPU'
    scene.render.use_compositing=False
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='8'
    bpy.ops.render.render(write_still=False)
    bpy.data.images['Render Result'].save_render(str(out/'Bfont-native.png'),scene=scene)
    tree=bpy.data.node_groups.new('Fonts only','CompositorNodeTree');scene.compositing_node_group=tree
    node=tree.nodes.new('CompositorNodeOutputFile');node.file_name='Project fonts'
    addon.migrate_legacy(node)
    for item in node.blend_artwork_exports:item.enabled=False
    for name in ('first','second'):
        item=node.blend_artwork_exports.add();item.format='FONTS';item.enabled=True
        assert item.path==user_font_directory()
        item.path=str(out/name);item.relative_path=False
    assert not any(socket.is_linked for socket in node.inputs)
    addon.prepare(scene);session=addon.SESSIONS[scene.as_pointer()]
    assert len(session['jobs'])==2 and not session['temps'],'Font detection required image outputs'
    jobfile=Path(session['root'])/'jobs.json';jobfile.write_text(json.dumps(dict(jobs=session['jobs']),indent=2))
    addon.cleanup(scene,discard=False)
    assert worker(jobfile)==0
    for job in json.loads(jobfile.read_text())['jobs']:
        dest=Path(job['dest']);manifest=json.loads(dest.read_text())
        assert {t['name'] for t in manifest['text_objects']}=={'Builtin','Loaded twin','Hidden elsewhere'}
        assert manifest['complete'] and all(f['family']=='Bfont' and not f['substituted'] for f in manifest['fonts'])
        for entry in manifest['fonts']:
            assert (dest.parent/entry['file']).read_bytes()==raw
            assert (dest.parent/entry['compatible_file']).read_bytes()==compatible_bfont(raw)
        assert not list(dest.parent.rglob('*.blend'))
    assert bpy.data.filepath==original_file
    print('PASS: exact native Bfont glyphs, original live SVG family, project fonts from hidden objects and other scenes, two independent font outputs without image links or rendering',flush=True)


if __name__=='__main__':
    try:run()
    except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
    sys.stdout.flush();sys.stderr.flush();os._exit(0)
