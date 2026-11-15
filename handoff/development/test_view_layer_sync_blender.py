"""Exercise native Blender 5.3 File Output synchronization without user files."""
import bpy
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT.parent), str(ROOT)]
from view_layer_sync import synchronize, Graph, STATE, LAYER_ID, SyncError


def fixture(name):
    scene = bpy.data.scenes.new(name)
    bpy.context.window.scene = scene
    tree = bpy.data.node_groups.new(name+' compositor', 'CompositorNodeTree')
    scene.compositing_node_group = tree
    output = tree.nodes.new('CompositorNodeOutputFile')
    return scene, tree, output


def layers(scene, *names):
    scene.view_layers[0].name = names[0]
    for name in names[1:]:
        scene.view_layers.new(name)


def source(scene, tree, layer):
    node = tree.nodes.new('CompositorNodeRLayers')
    node.scene = scene; node.layer = layer
    return node


def incoming(tree, socket):
    return next((l.from_socket for l in tree.links if l.to_socket == socket), None)


def names(node):
    return [i.name for i in node.file_output_items]


def run():
    assert bpy.app.version[:2] == (5, 3)
    # Create sources, preserve input order/identifier/format and processed link.
    scene, tree, output = fixture('Basic')
    layers(scene, 'Back', 'Front', 'New')
    scene.view_layers['Front'].use_pass_z = True
    render = source(scene, tree, 'Front')
    blur = tree.nodes.new('CompositorNodeBlur')
    tree.links.new(render.outputs['Image'], blur.inputs['Image'])
    slot = output.file_output_items.new('RGBA', 'Old alias')
    slot.override_node_format = True; slot.format.file_format = 'OPEN_EXR'; slot.format.color_depth = '32'
    tree.links.new(blur.outputs['Image'], output.inputs[0])
    identifier = output.inputs[0].identifier
    manual = output.file_output_items.new('FLOAT', 'Depth utility')
    tree.links.new(render.outputs['Depth'], output.inputs[1])
    report = synchronize(scene, output)
    assert names(output) == ['Front', 'Depth utility', 'Back', 'New'], report
    assert output.inputs[0].identifier == identifier
    assert incoming(tree, output.inputs[0]) == blur.outputs['Image']
    assert output.file_output_items[0].format.file_format == 'OPEN_EXR'
    assert output.file_output_items[0].format.color_depth == '32'
    assert report['created_nodes'] == ['Back', 'New']
    assert any('Depth utility' in x for x in report['warnings'])
    twice = synchronize(scene, output)
    assert not any(twice[k] for k in ('added', 'removed', 'renamed', 'connected', 'created_nodes')), twice
    scene.view_layers['Front'].name = 'Front.add'
    report = synchronize(scene, output)
    assert report['renamed'] == ['Front -> Front.add']
    assert incoming(tree, output.inputs[0]) == blur.outputs['Image']
    scene.view_layers.remove(scene.view_layers['Front.add'])
    assert render.layer != 'Front.add', 'Blender deletion retarget behavior changed'
    report = synchronize(scene, output)
    assert len(report['removed']) == 1 and 'Front.add' in report['removed'][0]
    assert 'Depth utility' in names(output)
    assert tree.nodes.get(blur.name) == blur
    assert any('Removed inputs:' in x for x in report['warnings'])
    # Duplicate layer IDs are regenerated so one deletion cannot delete both.
    live = scene.view_layers['Back']; duplicate = scene.view_layers.new('Duplicate')
    duplicate[LAYER_ID] = live[LAYER_ID]
    synchronize(scene, output)
    assert duplicate[LAYER_ID] != live[LAYER_ID]
    # Repeated names (swap) keep layer identity, slot settings, and graph links.
    before = [(s.identifier, incoming(tree, s)) for s in list(output.inputs)[:len(output.file_output_items)]]
    scene.view_layers['Back'].name = 'Temporary'
    scene.view_layers['New'].name = 'Back'
    scene.view_layers['Temporary'].name = 'New'
    synchronize(scene, output)
    assert [(s.identifier, incoming(tree, s)) for s in list(output.inputs)[:len(output.file_output_items)]] == before
    assert names(output) == ['Depth utility', 'New', 'Back', 'Duplicate']
    # File Output's C array reallocates on every addition/removal: exercise
    # bulk deletion plus addition plus rename in one action with fresh lookups.
    scene.view_layers.remove(scene.view_layers['Back'])
    scene.view_layers.remove(scene.view_layers['Duplicate'])
    scene.view_layers['New'].name = 'New.screen'
    scene.view_layers.new('Added after deletions')
    report = synchronize(scene, output)
    assert len(report['removed']) == 2 and report['added'] == ['Added after deletions'], report
    assert names(output) == ['Depth utility', 'New.screen', 'Added after deletions']
    # Unconnected processed result is preferred to a raw source; ambiguous
    # competing image branches are reported, never picked by node position.
    sc, tr, out = fixture('Branches')
    layers(sc, 'Blurred', 'Ambiguous')
    a = source(sc, tr, 'Blurred'); b = tr.nodes.new('CompositorNodeBlur')
    tr.links.new(a.outputs['Image'], b.inputs['Image'])
    a2 = source(sc, tr, 'Ambiguous')
    for _ in range(2):
        branch = tr.nodes.new('CompositorNodeBlur'); tr.links.new(a2.outputs['Image'], branch.inputs['Image'])
    report = synchronize(sc, out)
    assert names(out) == ['Blurred'], report
    assert incoming(tr, out.inputs[0]) == b.outputs['Image']
    assert any('multiple downstream image results' in x for x in report['warnings'])
    sc.view_layers['Blurred'].use = False
    report = synchronize(sc, out)
    assert not sc.view_layers['Blurred'].use
    assert any('disabled for rendering' in x for x in report['warnings'])
    # Route from inside a unique group to a root File Output.
    sc, tr, out = fixture('Nested source')
    layers(sc, 'Nested')
    sub = bpy.data.node_groups.new('Nested source data', 'CompositorNodeTree')
    instance = tr.nodes.new('CompositorNodeGroup'); instance.node_tree = sub
    r = source(sc, sub, 'Nested'); bl = sub.nodes.new('CompositorNodeBlur')
    sub.links.new(r.outputs['Image'], bl.inputs['Image'])
    report = synchronize(sc, out)
    assert len(out.file_output_items) == 1, report
    assert incoming(tr, out.inputs[0]).node == instance
    group_output = next(n for n in sub.nodes if n.bl_idname == 'NodeGroupOutput')
    assert incoming(sub, group_output.inputs[0]) == bl.outputs['Image']
    count = len(sub.interface.items_tree)
    synchronize(sc, out)
    assert len(sub.interface.items_tree) == count
    # Route root processing into a File Output located inside a unique group.
    sc, tr, unused = fixture('Nested destination')
    tr.nodes.remove(unused)
    sub = bpy.data.node_groups.new('Nested destination data', 'CompositorNodeTree')
    instance = tr.nodes.new('CompositorNodeGroup'); instance.node_tree = sub
    out = sub.nodes.new('CompositorNodeOutputFile')
    r = source(sc, tr, sc.view_layers[0].name)
    report = synchronize(sc, out)
    assert incoming(sub, out.inputs[0]).node.bl_idname == 'NodeGroupInput', report
    assert incoming(tr, instance.inputs[0]) == r.outputs['Image']
    synchronize(sc, out)
    assert len(out.file_output_items) == 1 and len(sub.interface.items_tree) == 1
    # The same definition used twice must not be edited via an ambiguous
    # instance; reject before writing IDs or changing inputs.
    again = tr.nodes.new('CompositorNodeGroup'); again.node_tree = sub
    old = out[STATE]
    try: synchronize(sc, out)
    except SyncError: pass
    else: raise AssertionError('Shared destination accepted')
    assert out[STATE] == old
    # Multiple scene effects are explicitly out of scope, not guessed.
    sc, tr, out = fixture('Multiple effects')
    bpy.context.window.scene = sc
    bpy.ops.scene.add_compositor_effect()
    sc.compositor_effects[-1].node_group = bpy.data.node_groups.new('Second effect', 'CompositorNodeTree')
    before = len(tr.nodes)
    try: synchronize(sc, out)
    except SyncError: pass
    else: raise AssertionError('Multiple scene effects accepted')
    assert len(tr.nodes) == before and STATE not in out
    # Node colour matches the actual parent collection palette.
    sc, tr, out = fixture('Node colour')
    sc.view_layers[0].name = 'Art'
    collection = bpy.data.collections.new('Art'); collection.color_tag = 'COLOR_05'
    sc.collection.children.link(collection)
    obj = bpy.data.objects.new('Plane', bpy.data.meshes.new('Plane data')); collection.objects.link(obj)
    bpy.context.window.scene = sc
    synchronize(sc, out)
    r = next(n for n in tr.nodes if n.bl_idname == 'CompositorNodeRLayers')
    from collection_colors import theme_collection_colors
    assert r.use_custom_color
    assert max(abs(a-b) for a,b in zip(r.color, theme_collection_colors(bpy)[4])) < 1e-6
    # Ensure the registered UI action supports a single undo step.
    import handoff as addon
    addon.register()
    assert 'UNDO' in addon.OT_sync_view_layers.bl_options
    assert hasattr(bpy.ops.blend_psd, 'sync_view_layers')
    # Exercise the real operator in a native node-editor context. Background
    # scripts have no UI event loop to push undo states, so bracket the action
    # explicitly, then verify that Blender restores its slots and source nodes.
    sc, tr, out = fixture('Operator undo')
    tr.nodes.active = out
    area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
    area.type = 'NODE_EDITOR'
    area.spaces.active.tree_type = 'CompositorNodeTree'
    area.spaces.active.pin = True; area.spaces.active.node_tree = tr
    region = next(r for r in area.regions if r.type == 'WINDOW')
    with bpy.context.temp_override(window=bpy.context.window, area=area, region=region):
        bpy.context.preferences.edit.use_global_undo = True
        bpy.ops.ed.undo_push(message='Sync baseline')
        assert bpy.ops.blend_psd.sync_view_layers() == {'FINISHED'}
        assert len(out.file_output_items) == 1
        bpy.ops.ed.undo_push(message='Sync applied')
        assert bpy.ops.ed.undo() == {'FINISHED'}
        restored = bpy.data.node_groups['Operator undo compositor']
        restored_output = next(n for n in restored.nodes if n.bl_idname == 'CompositorNodeOutputFile')
        assert not restored_output.file_output_items
        assert not any(n.bl_idname == 'CompositorNodeRLayers' for n in restored.nodes)
    addon.unregister()
    print('VIEW_LAYER_SYNC_NATIVE_PASS', flush=True)


if __name__ == '__main__':
    try:
        run()
    except BaseException:
        traceback.print_exc(); sys.stdout.flush(); sys.stderr.flush(); os._exit(1)
    sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
