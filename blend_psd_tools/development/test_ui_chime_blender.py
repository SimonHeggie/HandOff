"""Blender 5.3 UI disclosure, chime migration and silent linear-gain tests.

Uses the Null audio device: never plays sound through the user's speakers.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT.parent), str(ROOT)]


class Layout:
    def __init__(self, calls):
        self.calls = calls
    def row(self, **kw): return Layout(self.calls)
    def column(self, **kw): return Layout(self.calls)
    def box(self): return Layout(self.calls)
    def separator(self): pass
    def label(self, **kw): self.calls.append(('label', kw))
    def prop(self, data, prop, **kw): self.calls.append(('prop', dict(prop=prop, **kw)))
    def operator(self, *args, **kw): return NS()


def run():
    import bpy
    import aud
    import numpy as np
    import blend_psd_tools as addon
    assert bpy.app.version[:2] == (5, 3)
    addon.register()
    scene = bpy.context.scene
    # A legacy saved mute does not accidentally become an enabled slider.
    scene['blend_psd_chime_enabled'] = False
    assert 'blend_psd_chime_volume' not in scene
    assert scene.blend_psd_chime_volume == 0
    scene['blend_psd_chime_enabled'] = True
    assert scene.blend_psd_chime_volume == 1
    scene.blend_psd_chime_volume = .35
    assert abs(scene.blend_psd_chime_volume-.35) < 1e-6
    assert scene.blend_psd_chime_enabled
    scene.blend_psd_chime_volume = 0
    assert not scene.blend_psd_chime_enabled
    # Existing API scripts can continue using the old checkbox property.
    scene.blend_psd_chime_enabled = True
    assert scene.blend_psd_chime_volume == 1
    scene.blend_psd_chime_enabled = False
    assert scene.blend_psd_chime_volume == 0
    properties = scene.bl_rna.properties['blend_psd_chime_volume']
    assert properties.hard_min == 0 and properties.hard_max == 1
    assert properties.subtype == 'NONE'  # Numeric 0–1, not percentages.
    # Zero and background use return before even looking for the asset.
    frontend = NS(app=NS(background=False, timers=bpy.app.timers))
    with patch.object(addon, 'bpy', frontend), patch.object(addon, 'ROOT') as root, patch.object(aud, 'Sound') as sound, patch.object(aud, 'Device') as device:
        addon.notify_success(scene)
        root.__truediv__.assert_not_called()
        sound.assert_not_called(); device.assert_not_called()
    scene.blend_psd_chime_volume = .35
    with patch.object(addon, 'ROOT') as root, patch.object(aud, 'Sound') as sound, patch.object(aud, 'Device') as device:
        addon.notify_success(scene)  # Real bpy.app.background is True.
        root.__truediv__.assert_not_called()
        sound.assert_not_called(); device.assert_not_called()
    wav = str(ROOT/'assets/export_success.wav')
    base = aud.Sound(wav).data()
    for level in (0, .1, .25, .5, .75, 1):
        samples = aud.Sound(wav).volume(level).data()
        assert np.allclose(samples, base*level, rtol=1e-6, atol=1e-7), level
    # Execute the actual notification path with native factories and a Null
    # device. This verifies gain selection, resource lifetime and mute cleanup.
    make_device = aud.Device
    make_sound = aud.Sound
    gains = []
    class Factory:
        def __init__(self, path): self.sound = make_sound(path)
        def volume(self, gain):
            gains.append(gain)
            return self.sound.volume(gain)
    with patch.object(addon, 'bpy', frontend), patch.object(aud, 'Device', side_effect=lambda: make_device('None')), patch.object(aud, 'Sound', Factory):
        addon.notify_success(scene)
        assert gains == [scene.blend_psd_chime_volume]
        assert addon._CHIME_DEVICE is not None and addon._CHIME_HANDLE is not None
        assert bpy.app.timers.is_registered(addon._poll_chime)
        scene.blend_psd_chime_volume = 0
        assert addon._CHIME_DEVICE is None and addon._CHIME_HANDLE is None
        assert not bpy.app.timers.is_registered(addon._poll_chime)
    # Collapsing diagnostics never discards the stored report.
    tree = bpy.data.node_groups.new('UI settings fixture', 'CompositorNodeTree')
    node = tree.nodes.new('CompositorNodeOutputFile'); tree.nodes.active = node
    report = dict(added=[], renamed=['Alias -> Layer'], removed=[],
                  warnings=['Parent collection diagnostics should be collapsed'])
    node['_compio_view_layer_sync_report'] = json.dumps(report)
    assert not node.blend_psd_show_sync_details
    context = NS(scene=scene, space_data=NS(type='NODE_EDITOR', tree_type='CompositorNodeTree', edit_tree=tree))
    calls = []
    panel = NS(layout=Layout(calls))
    addon.PanelNode.draw(panel, context)
    assert not any('diagnostics should be collapsed' in kw.get('text', '') for kind, kw in calls)
    assert any(kind=='prop' and kw['prop']=='blend_psd_chime_volume' and kw.get('slider') for kind, kw in calls)
    assert not any(kind=='prop' and kw['prop']=='blend_psd_chime_enabled' for kind, kw in calls)
    node.blend_psd_show_diagnostics = True
    calls.clear(); addon.PanelNode.draw(panel, context)
    assert any('diagnostics should be collapsed' in kw.get('text', '') for kind, kw in calls)
    assert json.loads(node['_compio_view_layer_sync_report']) == report
    # One PSD writer for all editors. Old saved flags must never expose a
    # target selector, a locked checkbox or an internal validation message.
    legacy = node.blend_artwork_exports.add(); legacy.format='PSD'; legacy.enabled=True
    legacy.psd_target='PHOTOCRAFT'; legacy.psd_link_svg_fallbacks=False; legacy.psd_svg_sidecars=True
    calls.clear()
    with patch.object(addon,'missing',return_value=''):
        addon.PanelNode.draw(panel,context)
    assert not any(kind=='prop' and kw['prop'] in ('psd_target','psd_link_svg_fallbacks','psd_svg_sidecars') for kind,kw in calls)
    assert not any('awaits editor validation' in kw.get('text','') for kind,kw in calls)
    # Font destination previews identify both the actual font folder and index.
    item = node.blend_artwork_exports.add(); item.format = 'FONTS'; item.enabled = True
    item.path = '/tmp/compio-font-preview'; item.relative_path = False
    node.file_name = 'Project'
    calls.clear()
    with patch.object(addon, 'missing', return_value=''):
        addon.PanelNode.draw(panel, context)
    assert any(kw.get('text','').startswith('Font files: ') and kw['text'].endswith('Project.fonts') for kind, kw in calls)
    assert any(kw.get('text','').startswith('Font index: ') and kw['text'].endswith('Project.fonts.json') for kind, kw in calls)
    node.blend_psd_show_diagnostics = False
    scene.blend_psd_export_notices = json.dumps(['Held render diagnostics should be collapsed'])
    calls.clear()
    with patch.object(addon, 'missing', return_value=''):
        addon.PanelNode.draw(panel, context)
    assert not any('Held render diagnostics' in kw.get('text','') for kind,kw in calls)
    node.blend_psd_show_diagnostics = True
    calls.clear()
    with patch.object(addon, 'missing', return_value=''):
        addon.PanelNode.draw(panel, context)
    assert any('Held render diagnostics' in kw.get('text','') for kind,kw in calls)
    # Round-trip old/new scene settings without ever opening a user project.
    scene.blend_psd_chime_volume = .42
    with tempfile.TemporaryDirectory(prefix='compio-chime-settings-') as folder:
        file = Path(folder)/'settings.blend'
        bpy.data.libraries.write(str(file), {scene})
        bpy.ops.wm.open_mainfile(filepath=str(file), load_ui=False, use_scripts=False)
        loaded = bpy.data.scenes[0]
        assert abs(loaded.blend_psd_chime_volume-.42) < 1e-6
    addon.unregister()
    assert not hasattr(bpy.types.Scene, 'blend_psd_chime_volume')
    assert not hasattr(bpy.types.Node, 'blend_psd_show_sync_details')
    print('UI_CHIME_NATIVE_PASS: disclosure, legacy mute, zero-load guard, linear samples, Null playback, cleanup, font paths and saved volume', flush=True)


if __name__ == '__main__':
    try:
        run()
    except BaseException:
        traceback.print_exc(); sys.stdout.flush(); sys.stderr.flush(); os._exit(1)
    sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
