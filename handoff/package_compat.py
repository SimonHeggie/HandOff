"""Prevent simultaneous registration of the renamed and legacy add-on packages."""
import sys


def disable_legacy(package):
    if package != 'handoff': return
    import bpy
    import addon_utils
    old = sys.modules.get('blend_psd_tools')
    if old is None or not callable(getattr(old, 'unregister', None)): return
    active = any(getattr(fn, '__module__', '') == 'blend_psd_tools'
                 for group in (bpy.app.handlers.render_init, bpy.app.handlers.render_pre,
                               bpy.app.handlers.render_post, bpy.app.handlers.render_complete)
                 for fn in group)
    if not active: return
    if getattr(old, 'SESSIONS', {}) or getattr(old, 'MONITORS', []):
        raise RuntimeError('Wait for the legacy HandOff export to finish before enabling the renamed package')
    if bpy.context.preferences.addons.get('blend_psd_tools'):
        addon_utils.disable('blend_psd_tools', default_set=True)
    else:
        old.unregister()
