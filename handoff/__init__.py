# Blender's legacy add-on loader can inspect this dictionary before enable.
# Keep a literal fallback and synchronise identity to branding.py at import.
bl_info = {
    'name': 'HandOff',
    'author': 'Simon Heggie',
    'version': (0, 7, 53),
    'blender': (5, 0, 0),
    'location': 'Compositor > File Output > Node sidebar',
    'description': 'One render, every deliverable: layered PSD/PSB, OCA, Spine-ready artwork and production image exports',
    'category': 'Compositing',
}

import importlib as _identity_importlib
from . import branding as _branding
_branding = _identity_importlib.reload(_branding)
from .branding import (NAME as BRAND_NAME, SUBTITLE as BRAND_SUBTITLE,
                       TAGLINE as BRAND_TAGLINE, SHORT_DESCRIPTION as BRAND_DESCRIPTION,
                       OVERVIEW as BRAND_OVERVIEW, VERSION_INFO, LOG_PREFIX)
bl_info['name'] = BRAND_NAME
bl_info['description'] = BRAND_DESCRIPTION
bl_info['location'] = 'Compositor > File Output > Node sidebar > ' + BRAND_NAME
bl_info['version'] = VERSION_INFO

import bpy
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from functools import lru_cache
from pathlib import Path

from bpy.app.handlers import persistent
from bpy.props import (
    BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty,
    PointerProperty, StringProperty,
)
from bpy.types import Operator, Panel, PropertyGroup, UIList, AddonPreferences
from .runtime_paths import (job_roots, IMAGE_PREFIX, PRIVATE_PREFIX, TEMP_NODE_PREFIX,
                            TEMP_NODE_PREFIXES, TEMP_MARKER, TEMP_MARKERS, WORKER_FILE,
                            JOB_PREFIXES, is_temporary_node)
# Blender can retain helper modules when a ZIP is installed over a previous
# build. Refresh the stack algorithm when its exported API changes.
import importlib as _stack_importlib
from . import layer_stack as _layer_stack
from .collection_colors import source_collection_colors, theme_collection_colors
from .job_cache_cleanup import clear_jobs
if (getattr(_layer_stack, 'STACK_API_VERSION', 0) < 8 or
        not callable(getattr(_layer_stack, 'preview_merge_groups', None))):
    _layer_stack = _stack_importlib.reload(_layer_stack)
prepared_entries = _layer_stack.prepared_entries
build_stack = _layer_stack.build_stack
strip_tags = _layer_stack.strip_tags
preview_merge_groups = _layer_stack.preview_merge_groups
# Conservative SVG export lives independently of the PSD/PSB writer.
from . import svg_source as _svg_source
from . import svg_export as _svg_export
if getattr(_svg_source, "SOURCE_API_VERSION", 0) < 1:
    _svg_source = _stack_importlib.reload(_svg_source)
# SVG is inexpensive to import and is frequently changed during development.
# Reload it every time the legacy add-on is enabled, including when Blender
# retains a same-version module object from a previous ZIP installation.
_svg_export = _stack_importlib.reload(_svg_export)
# Blender can re-enable an updated legacy zip without clearing cached helpers.
# Reload only if the new API is missing, preserving compatible prior sessions.
from . import attribution_names as _attribution_names
if (not callable(getattr(_attribution_names, 'unique_source_scene_collection', None)) or
        not callable(getattr(_attribution_names, 'related_output_owner', None))):
    import importlib as _names_importlib
    _attribution_names = _names_importlib.reload(_attribution_names)
_legacy_name_match = _attribution_names.name_match
_related_output_owner = _attribution_names.related_output_owner
unique_source_scene_collection = _attribution_names.unique_source_scene_collection
from . import tag_registry as _tag_registry
# XML is loaded lazily when an export or status check runs, never during registration.

# Blender's legacy "Install from Disk" can reload __init__.py while leaving
# previously imported package submodules alive in sys.modules. In 0.6.7 the
# collection_provenance helper did not yet export view_layer_evidence(), so
# upgrading in the same Blender process raised ImportError during enable.
# Refresh the *existing module object* rather than importing individual names
# from potentially stale Python bytecode / sys.modules state.
import importlib as _importlib
from . import collection_provenance as _provenance
_REQUIRED_PROVENANCE_API = 8
if getattr(_provenance, 'PROVENANCE_API_VERSION', 0) < _REQUIRED_PROVENANCE_API:
    _provenance = _importlib.reload(_provenance)
from . import artwork_probe as _artwork_probe
_REQUIRED_PROBE_API = 2
if (getattr(_artwork_probe, 'PROBE_API_VERSION', 0) < _REQUIRED_PROBE_API or
        not callable(getattr(_artwork_probe, 'attribution_status_detail', None))):
    _artwork_probe = _importlib.reload(_artwork_probe)

collection_index = _provenance.collection_index
infer_from_socket = _provenance.infer_from_socket
source_render_layers = _provenance.source_render_layers
unique_camera_owner = _provenance.unique_camera_owner

# The diagnostic report must never prevent registration or F12 if an old
# helper happens to survive on disk during a mixed-version installation.
def _fallback_view_layer_evidence(view_layer):
    return {'view_layer': getattr(view_layer, 'name', '<unknown>'),
            'warning': 'Collection evidence reporting unavailable: reinstall the complete add-on zip',
            'candidates': []}

view_layer_evidence = getattr(_provenance, 'view_layer_evidence',
                              _fallback_view_layer_evidence)

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / 'vendor'
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))
from .pillow_loader import ensure_pillow
from . import font_delivery as _font_delivery
if getattr(_font_delivery,'FONTS_API_VERSION',0)<1:
    _font_delivery=_stack_importlib.reload(_font_delivery)
from .font_delivery import system_font_directory, user_font_directory
from .job_ownership import create_owned_job, discard_owned_job

SESSIONS = {}
MONITORS = []

FORMATS = [
    ('PSD', '.PSD', 'Use PSD normally; automatically switch to PSB when document limits require it'),
    ('PSB', '.PSB', 'Always write a large-format PSB document'),
    ('OCA', '.OCA', 'Publish layered animation from Render Animation, or the current frame from Render Image'),
    ('PNG', '.PNG', 'Export additional PNG files (one per layer or a flattened PNG)'),
    ('SVG', '.SVG', 'One SVG with editable Grease Pencil, Curve, live Text and PNG fallback'),
    ('EXR', '.EXR', 'Export additional OpenEXR files. Multilayer EXR can increase memory use and decoding time for large stacks'),
    ('TIFF', '.TIFF', 'Export additional TIFF files'),
    ('JPEG', '.JPEG', 'Export additional JPEG images (RGB, no alpha)'),
    ('FONTS', 'FONTS', 'Copy referenced font files and write a font/text manifest'),
]
SUPPORTED_NOW = {'PSD', 'PSB', 'OCA', 'PNG', 'EXR', 'TIFF', 'JPEG', 'SVG', 'FONTS'}
LAYER_CAPABLE = {'PSD', 'PSB', 'OCA', 'EXR', 'SVG'}
TAG_PROFILES = [
    ('PASSTHROUGH', 'No Conversion', 'Keep authored tags unchanged. Default and safest for manual workflows.', 4),
    ('SPINE', 'Spine', 'Translate explicitly recognised tags to Spine syntax', 1),
    ('GENERATOR', 'Photoshop Generator', 'Translate supported filename instructions; preserve unsupported tags with warnings', 2),
    ('OCA', 'OCA / Krita', 'Convert supported Krita OCA-exporter tag conventions; native OCA uses structured metadata', 3),
]


FORMATS_EXT = {'PSD': '.psd', 'PSB': '.psb', 'OCA': '.oca', 'PNG': '.png', 'SVG': '.svg',
               'EXR': '.exr', 'TIFF': '.tif', 'JPEG': '.jpg', 'FONTS': '.fonts.json'}


def scene_tree(scene):
    return getattr(scene, 'compositing_node_group', None) or getattr(scene, 'node_tree', None)


def target(context):
    space = getattr(context, 'space_data', None)
    if not space or space.type != 'NODE_EDITOR' or space.tree_type != 'CompositorNodeTree':
        return None
    tree = getattr(space, 'edit_tree', None)
    node = tree.nodes.active if tree else None
    return node if node and node.bl_idname == 'CompositorNodeOutputFile' else None


@lru_cache(maxsize=1)
def missing():
    try:
        ensure_pillow()
        import PIL, numpy, attr
        from psd_tools import PSDImage
        return ''
    except Exception as exc:
        return str(exc)


def connected(tree, node):
    entries = []
    for sock in node.inputs:
        if sock.is_linked:
            for lk in tree.links:
                if lk.to_socket == sock:
                    entries.append((sock.name, lk.from_socket))
                    break
    return entries


def base_name(node):
    return (getattr(node, 'file_name', None) or 'Image').strip() or 'Image'


def actual_path(item, fmt, node=None):
    """Destination uses FOLDER and optional filename, never embeds a file name
    inside the directory property. Blender relative // paths are supported.
    """
    directory = bpy.path.abspath(item.path).strip() if item.path else ''
    if not directory:
        directory = bpy.path.abspath(node.directory) if node else ''
    if not directory:
        raise ValueError('Additional output directory cannot be empty')
    filename = (item.custom_name.strip() if item.use_custom_name else base_name(node))
    if not filename:
        raise ValueError('Custom filename cannot be empty')
    filename = os.path.splitext(os.path.basename(filename))[0]
    return Path(directory).expanduser().resolve() / (filename + FORMATS_EXT[fmt])


def _relative_update(self, context):
    try:
        current = self.path.strip()
        if not current:
            return
        if self.relative_path:
            if not current.startswith('//'):
                self.path = bpy.path.relpath(bpy.path.abspath(current))
        elif current.startswith('//'):
            self.path = bpy.path.abspath(current)
    except Exception as exc:
        print(f'{LOG_PREFIX} Relative path conversion deferred:', exc)


def normalize_legacy_path(item, node):
    """One-way upgrade from old destination FILE to directory + custom name.
    Preserve previously selected Character.psd names even when node is Hatshepsut.
    """
    if item.get('_v061_path_migrated'):
        return
    raw = item.path.strip()
    if raw and Path(raw).suffix.lower() in FORMATS_EXT.values():
        directory, filename = os.path.split(raw)
        if filename:
            item.custom_name = os.path.splitext(filename)[0]
            item.use_custom_name = True
        item.path = directory if directory else '//'
    elif not raw:
        item.path = node.directory or '//'
    if item.relative_path and item.path and not item.path.startswith('//'):
        try:
            item.path = bpy.path.relpath(bpy.path.abspath(item.path))
        except Exception:
            pass
    item['_v061_path_migrated'] = True


def job_cache_base():
    base = job_roots()[0]
    base.mkdir(parents=True, exist_ok=True)
    return base


def create_companion(tree, original, folder, entries, cache_kind, save_as_render=True):
    """Add an ephemeral native file output node with no edits to existing outputs.

    Cache formats:
        PNG8, PNG16 (RGBA straight PNG)
        EXR32 (RGBA full-float linear OpenEXR)
    """
    temp = tree.nodes.new('CompositorNodeOutputFile')
    temp.label = BRAND_NAME + ' temporary ' + cache_kind
    temp.name = TEMP_NODE_PREFIX + uuid.uuid4().hex[:10]
    temp[TEMP_MARKER] = True
    temp.hide = True
    temp.location = (original.location.x + 120, original.location.y - 220)
    temp.directory = str(folder)
    temp.file_name = IMAGE_PREFIX
    temp.format.media_type = 'IMAGE'
    if cache_kind.startswith('PNG'):
        temp.format.file_format = 'PNG'
        temp.format.color_mode = 'RGBA'
        temp.format.color_depth = cache_kind[3:]
        extension = '.png'
        # Blender File Output's own Save as Render and Follow Scene settings.
        try:
            temp.save_as_render = bool(save_as_render)
        except AttributeError:
            pass
        try:
            temp.format.color_management = 'FOLLOW_SCENE'
        except (AttributeError, TypeError, ValueError):
            pass
    else:
        temp.format.file_format = 'OPEN_EXR'
        temp.format.color_mode = 'RGBA'
        temp.format.color_depth = '32'
        temp.format.exr_codec = 'ZIP'
        extension = '.exr'
    try:
        temp.file_output_items.clear()
    except (AttributeError, TypeError):
        for item in list(temp.file_output_items):
            temp.file_output_items.remove(item)
    manifest = []
    for i, entry in enumerate(entries):
        name, source = entry['name'], entry['socket']
        slug = f'L{i:04d}_'
        output_item = temp.file_output_items.new('RGBA', slug)
        if cache_kind.startswith('PNG'):
            try:
                output_item.save_as_render = bool(save_as_render)
            except AttributeError:
                pass
        tree.links.new(source, temp.inputs[i])
        manifest.append({'name': name, 'slug': IMAGE_PREFIX + slug,
                         'collection_path': entry.get('collection_path', ''),
                         'source_view_layer': entry.get('source_view_layer', ''),
                         'collection_colors': entry.get('collection_colors', [])})
        manifest[-1].update({key: entry[key] for key in
                            ('source_identity', 'render_disabled', 'disabled_sources') if key in entry})
        manifest[-1]['render_was_disabled'] = bool(entry.get('render_disabled'))
    return temp, manifest, extension


# Source attribution stays read-only. The optional Update Inputs action manages
# node sockets independently; ordinary export does not require a sync step.


def _map_layers(node, names, paths, fallback='', *, tree=None, pairs=None, scene=None, verbose=False):
    """Source-scoped restoration of the reliable 0.6.x matching behaviour.

    Exact object / Collection identities run BEFORE camera-only inference.
    The source View Layer supplies eligible Collection records, including
    Indirect Only branches. This is evidence of authoring association, not
    proof that every rendered pixel originated from those objects.
    """
    mapped = []
    # Collect source tracing once per socket and Collection records once per
    # View Layer. Check Export Status should stay responsive even when a File
    # Output contains dozens of art passes from the same scene.
    socket_sources = []
    if tree is not None and pairs is not None:
        for _, source_socket in pairs:
            try:
                socket_sources.append(source_render_layers(
                    tree, source_socket, default_scene=scene))
            except Exception:
                socket_sources.append([])
    peer_record_cache = {}
    for index, name in enumerate(names):
        chosen = ''
        explanation = 'no identified source'
        sources = []
        if tree is not None and pairs is not None and index < len(pairs):
            try:
                sources = socket_sources[index]
            except Exception as exc:
                explanation = 'cannot trace render source: ' + str(exc)
        # Use the traced source View Layer, not Blender's currently active layer.
        # Where multiple Render Layers feed a composite, the fallback works
        # only if the same exact Collection path is the unique candidate.
        candidate_maps = []
        for source_scene, source_layer_name in sources:
            layer = source_scene.view_layers.get(source_layer_name)
            if layer is None:
                continue
            try:
                match, reason = _legacy_name_match(name, collection_index(layer))
                candidate_maps.append((match, reason))
            except Exception as exc:
                candidate_maps.append(('', 'name lookup error: ' + str(exc)))
        if candidate_maps:
            valid = {match for match, reason in candidate_maps if match}
            if len(valid) == 1 and all(x == next(iter(valid)) for x, _ in candidate_maps):
                chosen = next(iter(valid))
                explanation = 'source-scoped ' + next(reason for match, reason in candidate_maps if match)
            else:
                explanation = 'source matches disagree or are ambiguous'
        # When no Render Layers source is traceable, permit only a globally
        # unique exact Blender Collection / object identity, never a majority.
        if not chosen and scene is not None and not sources:
            matches = []
            for layer in scene.view_layers:
                m, r = _legacy_name_match(name, collection_index(layer))
                if m:
                    matches.append((m, r))
            if len({m for m, _ in matches}) == 1:
                chosen = matches[0][0]
                explanation = 'scene-wide unique ' + matches[0][1]
        # Provenance may know a unique camera owner or material-mask owner
        # even when there is no useful exact authoring name.
        if not chosen and tree is not None and pairs is not None and index < len(pairs):
            try:
                source_owner, _, reason = infer_from_socket(
                    tree, pairs[index][1], default_scene=scene)
                if source_owner:
                    chosen, explanation = source_owner, reason
                elif not explanation or explanation == 'no identified source':
                    explanation = reason
            except Exception as exc:
                explanation = 'provenance failed: ' + str(exc)
        # Lowest-confidence fallback: the *source View Layer's* label may
        # identify its source collection even when the File Output label is a
        # production/translation alias (e.g. Head_Back -> Hood_BG). Only use
        # this after the structural and material/footprint analysis fails.
        if not chosen and len(sources) == 1:
            try:
                source_scene, source_layer_name = sources[0]
                source_layer = source_scene.view_layers.get(source_layer_name)
                if source_layer is not None:
                    m, r = _legacy_name_match(source_layer_name, collection_index(source_layer))
                    if m:
                        chosen = m
                        explanation = 'last-resort source View Layer name: ' + r
            except Exception as exc:
                explanation = 'source View Layer alias lookup failed: ' + str(exc)
        # Last-resort, source-SCENE-specific authored identity for pass outputs
        # whose source View Layer has no direct-camera geometry. This restores
        # the useful pre-0.7.10 matching for reflection and shade AOV artwork
        # without consulting the active View Layer or unrelated scenes.
        # A collision or ambiguity is NOT silently resolved.
        if not chosen and len(sources) == 1:
            try:
                source_scene, source_layer_name = sources[0]
                m, r = unique_source_scene_collection(name, source_scene)
                if m:
                    chosen = m
                    explanation = 'source-scene authored identity fallback: ' + r
            except Exception as exc:
                if verbose:
                    print(f'{LOG_PREFIX} Source Scene identity fallback skipped:', exc)
        # Preserve nested authoring where the output's ACTUAL source View Layer
        # identifies a unique included child of the resolved Collection.
        # Particularly important for non-camera AOV/shade/reflection layers,
        # for which camera_objects can legitimately be empty.  Use the source
        # LayerCollection tree, never bpy.context.view_layer; ambiguous children
        # leave the parent ownership unchanged.
        peers = []
        if chosen and len(sources) == 1:
            try:
                src_scene, src_name = sources[0]
                src_layer = src_scene.view_layers.get(src_name)
                if src_layer is not None:
                    # The other Render Layers sources are relevant when a
                    # branch exists only for reflection or shading. Compare
                    # their Collection inclusion first, then use the general
                    # single-child rule only if there are no peer sources.
                    peers = []
                    skipped_peers = []
                    if pairs is not None:
                        for (other_name, other_socket), other_sources in zip(pairs, socket_sources):
                            for peer_scene, peer_name in other_sources:
                                if peer_scene != src_scene or peer_name == src_name:
                                    continue
                                peer = peer_scene.view_layers.get(peer_name)
                                if peer is None or peer in peers:
                                    continue
                                # Exact identities keep this comparison in the
                                # same artwork branch. Other outputs may have
                                # Membrane/Shade enabled for lighting while
                                # exporting an arm or a hood. They must not
                                # veto the actual Eyes_Reflect source branch.
                                peer_key = (peer_scene.name, peer_name)
                                if peer_key not in peer_record_cache:
                                    peer_record_cache[peer_key] = collection_index(peer)
                                peer_records = peer_record_cache[peer_key]
                                related, candidate = _related_output_owner(
                                    chosen, other_name, peer_name, peer_records)
                                if related:
                                    peers.append(peer)
                                else:
                                    skipped_peers.append(peer_name)
                    more = (_provenance.unique_distinct_authored_child(src_layer, chosen, peers)
                            if peers else _provenance.unique_authored_child(src_layer, chosen))
                    if verbose:
                        print(f'{LOG_PREFIX} COLLECTION PEERS', repr(name),
                              'owner=', repr(chosen),
                              'related=', [p.name for p in peers],
                              'unrelated=', skipped_peers,
                              'nested=', repr(more or '(unresolved)'))
                    if more:
                        chosen = more
                        explanation += ' -> uniquely included nested source Collection'
            except Exception as exc:
                if verbose:
                    print(f'{LOG_PREFIX} Nested LayerCollection lookup skipped:', exc)
        # Only use the legacy camera-only shortcut when there are no other
        # source View Layers to compare. Otherwise it can incorrectly move
        # Eyes_Base into an active occluder Collection such as Membrane_Shade.
        if chosen and len(sources) == 1 and not peers:
            try:
                render_scene, render_layer_name = sources[0]
                render_layer = render_scene.view_layers.get(render_layer_name)
                rows = collection_index(render_layer) if render_layer is not None else []
                parent = next((p for p in rows if '/'.join(p['path']) == chosen), None)
                if parent is not None and not parent.get('camera_direct'):
                    ppath = parent['path']
                    all_direct = set(parent.get('camera_objects', ()))
                    children = [p for p in rows
                                if len(p['path']) == len(ppath) + 1 and p['path'][:-1] == ppath
                                and p.get('camera_objects')]
                    if all_direct and len(children) == 1 and set(children[0]['camera_objects']) == all_direct:
                        chosen = '/'.join(children[0]['path'])
                        explanation += ' → unique direct child Collection'
            except Exception as exc:
                if verbose:
                    print(f'{LOG_PREFIX} Nested source refinement skipped:', exc)
        mapped.append(chosen)
        if verbose:
            print(f'{LOG_PREFIX} SOURCE: {name!r} -> '
                  f'{chosen or "(unresolved/root)"} [{explanation}]')
    if verbose:
        try:
            from .group_blends import promoted_blend
            preview = build_stack(prepared_entries(
                [(dict(name=nm, collection_path=path), None)
                 for nm, path in zip(names, mapped)], True))
            preview_merge_groups(preview)
            print(f'{LOG_PREFIX} GROUP TREE PREVIEW (top to bottom, no render required):')
            def walk_group(node, depth=0):
                for child in node['children']:
                    if child['kind'] == 'group':
                        mode = promoted_blend(child)
                        print(f'{LOG_PREFIX} ' + '  '*depth + '[GROUP] ' + child['name'] +
                              (' (blend ' + mode + ')' if mode else ''))
                        walk_group(child, depth + 1)
                    else:
                        print(f'{LOG_PREFIX} ' + '  '*depth + ('[MERGED LAYER] ' if child.get('merged_preview') else '[LAYER] ') + child['name'])
            walk_group(preview)
        except Exception as exc:
            print(f'{LOG_PREFIX} Tree preview unavailable:', repr(exc))
    return mapped


def _source_view_layer_label(tree, socket, scene):
    """Exact source Render Layers label for an image socket, if unique.

    Display name only. Never select Blender's active view layer or use a name
    to infer the Collection that owns the pixel data.
    """
    try:
        sources = source_render_layers(tree, socket, default_scene=scene)
        return sources[0][1] if len(sources) == 1 else ''
    except Exception:
        return ''


def _source_render_state(tree, socket, scene):
    from .disabled_layers import source_state as _render_source_state
    return _render_source_state(tree, socket, scene, source_render_layers)


def _canvas_size(scene):
    render = scene.render
    scale = render.resolution_percentage / 100
    width, height = max(1, int(render.resolution_x * scale)), max(1, int(render.resolution_y * scale))
    if render.use_border and render.use_crop_to_border:
        width = max(1, int(width * render.border_max_x) - int(width * render.border_min_x))
        height = max(1, int(height * render.border_max_y) - int(height * render.border_min_y))
    return [width, height]


def _current_view_layer(scene):
    try:
        layer = bpy.context.view_layer
        if layer in scene.view_layers[:]:
            return layer
    except Exception:
        pass
    return scene.view_layers[0] if len(scene.view_layers) else None


def _stack_report(node, tree, item, paths):
    pairs = connected(tree, node)
    names = [name for name, _ in pairs]
    group_names = _map_layers(node, names, paths, tree=tree, pairs=pairs, scene=bpy.context.scene)
    pseudo = [(dict(name=n, collection_path=group_names[i]), None)
              for i, n in enumerate(names)]
    items = prepared_entries(pseudo, True)
    stack = build_stack(items)
    group_counts = {}
    def count(node):
        if node['kind'] == 'group':
            path = tuple(node.get('path', ()))
            if path:
                group_counts[path] = group_counts.get(path, 0) + 1
            for c in node['children']:
                count(c)
    count(stack)
    duplicates = sum(n - 1 for n in group_counts.values())
    unmatched = sum(not path for path in group_names)
    return unmatched, duplicates, [n for n, p in zip(names,group_names) if not p]


def cache_kind_for(item):
    if item.format == 'FONTS':
        return 'FONTS'
    if item.format == 'OCA':
        return {'8':'PNG8', '16':'PNG16', '32':'EXR32'}[item.depth]
    if item.format in ('PSD', 'PSB') and item.depth == '16' and item.save_as_render:
        return 'PNG16'
    if item.format == 'SVG':
        return 'PNG8' if item.depth == '8' else 'PNG16'
    if item.format == 'PNG':
        return 'PNG8' if item.depth == '8' else 'PNG16'
    if item.format == 'JPEG':
        return 'PNG8'
    return 'PNG8' if item.depth == '8' else 'EXR32'


ALLOWED_DEPTHS = {
    'PSD': ('8', '16', '32'), 'PSB': ('8', '16', '32'),
    'OCA': ('8', '16', '32'), 'PNG': ('8', '16'), 'SVG': ('8', '16'),
    'EXR': ('16', '32'), 'TIFF': ('8', '16'), 'JPEG': ('8',), 'FONTS': ('8',),
}


def _normalize_display_filename(name):
    # Keep names identical to the still-image worker, including collision suffixes.
    name = strip_tags(name)
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', '_', name.strip())
    return name.strip('. ')[:96] or 'Layer'


def _unique_still_paths(destination, names, *, profile='PASSTHROUGH', fmt='PNG'):
    """Expected image-series filenames; mirror psd_worker.assemble_stills."""
    collisions = {}
    out = []
    effective = _tag_registry.effective_profile(profile, fmt)
    for name in names:
        display = strip_tags(name)
        try:
            display, _warnings = _tag_registry.translate_label(display, name, effective, 'layer')
        except Exception:
            pass  # Preview must not break the native output node.
        label = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', '_', display.strip()).strip('. ')[:96] or 'Layer'
        collisions[label] = collisions.get(label, 0) + 1
        suffix = '' if collisions[label] == 1 else f'-{collisions[label]}'
        out.append(destination.with_name(destination.stem + label + suffix + destination.suffix))
    return out


def _format_update(self, context):
    options = ALLOWED_DEPTHS.get(self.format, ('8',))
    if self.depth not in options:
        self.depth = options[0]
    if self.format == 'FONTS' and not self.get('_font_destination_initialized',False):
        self.relative_path=False
        self.path=user_font_directory()
        self['_font_destination_initialized']=True
    if self.format == 'SVG':
        self['_v0722_svg_layers_migrated'] = True
        self.use_groups = True
        self.flatten = False
        self.bake_svg_png = False
    if self.format=='OCA' and not self.get('_oca_layout_initialized',False):
        self.oca_layout='PROJECT'
        self['_oca_layout_initialized']=True



class AdditionalExport(PropertyGroup):
    enabled: BoolProperty(name='Enabled', default=True, description='Include this additional export on F12')
    expanded: BoolProperty(name='Expanded', default=True, description='Show or hide this export entry settings')
    format: EnumProperty(name='File Format', items=FORMATS, default='PSD', update=_format_update)
    tag_profile: EnumProperty(name='Tag Compatibility', items=TAG_PROFILES, default='PASSTHROUGH',
        description='Convert recognised layer and group tags using the bundled XML registry. Original Blender names never change; unsupported tags remain with warnings in Check Export Status')
    path: StringProperty(name='Output Directory', subtype='DIR_PATH', default='//',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'},
        description='Destination folder; // is relative to the saved .blend file')
    relative_path: BoolProperty(name='Relative Path', default=True, update=_relative_update,
        description='Store this destination relative to the blend file (//), for portability')
    use_custom_name: BoolProperty(name='Custom Name', default=False,
        description='Override the File Output node filename for this additional destination')
    custom_name: StringProperty(name='File Name', default='')
    depth: EnumProperty(name='Color Depth', items=[('8', '8-bit', '8-bit integer'),
        ('16', '16-bit', '16-bit integer or EXR half-float as applicable'),
        ('32', '32-bit float', '32-bit floating point')], default='8')
    svg_root_mode: EnumProperty(name='Root Group',
        items=[('AUTO', 'Authored Collections', 'Use the existing Blender Collection hierarchy without an extra container'),
               ('NAMED', 'Custom Root', 'Wrap all exported SVG layers in a named group')],
        default='AUTO')
    svg_root_name: StringProperty(name='Root Name', default='',
        description='Name for the optional SVG root group. Defaults to the output document name')
    bake_svg_png: BoolProperty(name='Rasterise Vector Artwork', default=False,
        description='Use rendered pixels for vector sources instead of editable paths, shape layers or live text')
    svg_flat_text_material: BoolProperty(name='Use Flat Text Colour', default=False,
        description='Use constant Principled Base Color and Alpha for editable text, omitting lighting and surface effects. Does not rasterise text or change Blender materials. Flat Emission text needs no override')
    svg_editable_layer_blends: BoolProperty(name='Editable SVG Layer Blends', default=True,
        description='Legacy setting retained for saved files; SVG layer blends now apply automatically with approximation warnings')
    use_font_directory: BoolProperty(name='Find Missing Font Files', default=True,
        description='Search the selected folder for missing referenced font files; never substitute unrelated fonts')
    font_directory: StringProperty(name='Font Search Folder', subtype='DIR_PATH',
        default=system_font_directory(), options={'PATH_SUPPORTS_BLEND_RELATIVE'},
        description='Font lookup folder; defaults to this operating system font location and can be changed to a company font folder')
    psd_svg_sidecars: BoolProperty(name='Legacy Layered SVG Copy', default=False,options={'HIDDEN'},
        description='Legacy saved setting; complete SVG documents use a separate SVG export destination')
    # Retain retired properties for saved-file/script compatibility.
    # Publishing decisions are automatic and never depend on these values.
    psd_link_svg_fallbacks: BoolProperty(name='Legacy SVG Linking', default=False,options={'HIDDEN'},
        description='Legacy saved setting; unsupported PSD vectors now link their SVG sources automatically')
    psd_target: EnumProperty(name='Legacy Target Editor',default='PHOTOSHOP',options={'HIDDEN'},items=[
        ('PHOTOSHOP','Adobe Photoshop','Legacy setting; the same PSD writer is used for all editors'),
        ('PHOTOCRAFT','PhotoCraft','Legacy setting; the same PSD writer is used for all editors')])
    psd_compression: EnumProperty(name='PSD Compression', default='AUTO', items=[
        ('AUTO', 'Automatic', 'Use lossless ZIP for raster channels and a portable RLE document preview'),
        ('RLE', 'RLE', 'Legacy lossless run-length encoding'),
        ('ZIP', 'ZIP', 'Lossless ZIP compression'),
        ('ZIP_WITH_PREDICTION', 'ZIP with Prediction', 'Lossless ZIP with sample prediction'),
        ('RAW', 'Uncompressed', 'Store full uncompressed pixel channels')])
    # OCA-only publishing controls. Keep trim_empty_pixels as the persisted
    # identifier used by earlier saved projects; the label is destination-local.
    oca_ignore_hidden_layers: BoolProperty(name='Ignore hidden layers', default=False,
        description='Omit hidden source layers and Collections, including hidden-group descendants')
    oca_ignore_background: BoolProperty(name='Ignore background layer', default=True,
        description='Omit only source View Layers explicitly marked with custom property handoff_oca_background=True; names and layer order are never used')
    trim_empty_pixels: BoolProperty(name='Trim whitespace', default=True,
        description='OCA only: crop transparent alpha borders, preserving frame positions; hidden RGB does not prevent trimming')
    oca_write_json: BoolProperty(name='Write Spine JSON', default=False,
        description='Write an optional artwork/attachment companion using the OCA images and draw order; no skeletal rig conversion')
    oca_write_template: BoolProperty(name='Write template image', default=False,
        description='Write a PNG composite of currently visible eligible OCA artwork')
    oca_scale: FloatProperty(name='Scale', default=100.0, min=0.000001, max=400.0,
        subtype='PERCENTAGE', precision=2, description='Scale assets, canvas and positions together. Raster enlargement resamples existing pixels; it does not add detail. SVG remains vector artwork')
    oca_padding: IntProperty(name='Padding', default=1, min=0,
        description='Transparent pixels around each OCA image after cropping and scaling; does not move its centre')
    oca_keep_png: BoolProperty(name='Keep Alternative Artwork', default=False,
        description='Optional companion source: keep the unselected PNG/SVG representation too. Off publishes only the selected artwork. Alternatives use custom frame metadata, not a standard OCA attachment selector')
    oca_half_float: BoolProperty(name='Half-float EXR (F16)', default=False,
        description='Store floating-point OCA artwork as half-float EXR; full-float render caches remain reusable. Applies to 32-bit destinations only')
    oca_layout: EnumProperty(name='OCA Layout',default='LEGACY',items=[
        ('PROJECT','OCA Project Folder','Standard .oca directory containing one root OCA document, metadata and artwork'),
        ('LEGACY','Legacy Document + Assets','Retain the existing OCA JSON file with its sibling artwork directory')])
    flatten: BoolProperty(name='Flatten Image', default=False,
        description='Flatten layers into one image; disables group hierarchy where the format supports flattening')
    use_groups: BoolProperty(name='Use Groups', default=False,
        description='Collection groups follow output socket order. .ignore excludes a collection and its contents; .ungroup removes only its folder. .merge rasterises groups; .folder provides an export tag. Explicit slash paths override matching')
    unmatched_group: StringProperty(name='Legacy Unmatched Group', default='',
        description='Legacy property retained for loading older files; automatic attribution does not use it')
    save_as_render: BoolProperty(name='Save as Render', default=True,
        description='Use Blender scene view/display colour management for display images (PNG/PSD); OpenEXR caches remain linear')
    overwrite: BoolProperty(name='Overwrite', default=True,
        description='Replace this destination after a successful export')


class Settings(PropertyGroup):
    # Kept verbatim for backward compatibility with v0.4.9 .blend files.
    enabled: BoolProperty(name='Export PSD on F12', default=False)
    destination: StringProperty(name='PSD Path', subtype='FILE_PATH', default='//Character.psd')
    hierarchy: EnumProperty(name='Layer Structure', items=[
        ('FLAT', 'Single-Level Layers', ''), ('GROUPS', 'Preserve Groups', '')], default='FLAT')
    overwrite: BoolProperty(name='Overwrite PSD', default=False)


def migrate_legacy(node):
    if node.bl_idname != 'CompositorNodeOutputFile':
        return False
    if len(node.blend_artwork_exports):
        return False
    old = node.blend_psd_settings
    if not old.enabled:
        return False
    new = node.blend_artwork_exports.add()
    new.name = 'PSD Export'
    new.format = 'PSD'
    new.path = old.destination
    normalize_legacy_path(new, node)
    new.overwrite = old.overwrite
    new.use_groups = old.hierarchy == 'GROUPS'
    new.depth = '8'
    new.enabled = True
    print(f'{LOG_PREFIX} Migrated original PSD settings:', node.name)
    return True


def all_compositor_trees():
    found = set()
    for tree in list(bpy.data.node_groups) + [scene_tree(sc) for sc in bpy.data.scenes]:
        if tree and tree.bl_idname == 'CompositorNodeTree' and tree.as_pointer() not in found:
            found.add(tree.as_pointer())
            yield tree


def migrate_all():
    for tree in all_compositor_trees():
        for node in tree.nodes:
            if node.bl_idname == 'CompositorNodeOutputFile':
                try:
                    migrate_legacy(node)
                    for export in node.blend_artwork_exports:
                        normalize_legacy_path(export, node)
                        if export.format == 'SVG' and not export.get('_v0722_svg_layers_migrated', False):
                            export.use_groups = True
                            export.flatten = False
                            export['_v0722_svg_layers_migrated'] = True
                except Exception as exc:
                    print(f'{LOG_PREFIX} Legacy migration failed:', node.name, exc)



def _provenance_report(scene, jobs):
    """Save inspectable evidence for each image without rendering extra passes.

    Each source list is computed from the current compositor graph; object
    coverage is recorded for each view layer. Missing evidence is explicit.
    """
    report = {'scene': scene.name, 'exports': [], 'view_layers': []}
    node_locations = {}
    try:
        for tree in all_compositor_trees():
            for n in tree.nodes:
                if n.bl_idname == 'CompositorNodeOutputFile' and not is_temporary_node(n.name):
                    node_locations.setdefault(n.name, []).append((tree, n))
    except Exception:
        pass
    for job in jobs:
        node_locations_for_job = node_locations.get(job.get('node_name'), [])
        src = None
        if len(node_locations_for_job) == 1:
            src_tree, src_node = node_locations_for_job[0]
            src = connected(src_tree, src_node)
        rows = []
        for i, entry in enumerate(job.get('manifest', [])):
            result = {'image': entry.get('name'),
                      'collection': entry.get('collection_path') or None,
                      'source_view_layers': []}
            if src is not None and i < len(src):
                try:
                    upstream = source_render_layers(src_tree, src[i][1], default_scene=scene)
                    result['source_view_layers'] = [f'{origin.name}/{layer}' for origin, layer in upstream]
                except Exception as exc:
                    result['source_error'] = str(exc)
            rows.append(result)
        report['exports'].append({
            'node': job.get('node_name'), 'destination': job.get('dest'),
            'layers': rows})
    for v in scene.view_layers:
        try:
            report['view_layers'].append(view_layer_evidence(v))
        except Exception as exc:
            report['view_layers'].append({'view_layer': v.name, 'error': str(exc)})
    return report


def _export_svg_candidate(scene, layer, candidate, item, *, retained=None, collection_root=''):
    # A hybrid source couples editable paths to isolated rendered objects.
    # Retry reuses that complete artwork together, keeping its no-render contract.
    if retained is not None:
        from . import svg_hybrid
        if getattr(svg_hybrid, 'HYBRID_API_VERSION', 0) < 13:
            svg_hybrid = _stack_importlib.reload(svg_hybrid)
        if svg_hybrid.retained_hybrid(retained, editable_layer_blends=True):
            return True, 'Retained per-object SVG artwork; F12 refreshes source geometry', Path(retained)
    ok, reason = _svg_export.export_view_layer_svg(
        scene, layer, candidate, hybrid=True, allow_raster=retained is None,
        save_as_render=bool(item.save_as_render), deferred=retained is None,
        flat_text_material=bool(getattr(item, 'svg_flat_text_material', False)),
        editable_layer_blends=True,
        collection_root=collection_root,
        font_directory=bpy.path.abspath(getattr(item, 'font_directory', system_font_directory())),
        use_font_directory=bool(getattr(item, 'use_font_directory', True)))
    return ok, reason, candidate


def _capture_fonts(scene, tree, node, raw, item, root, index):
    from .font_delivery import capture_font_job
    # Fonts are project assets, independently of connected render sockets,
    # camera framing and render visibility. Detect text across all scenes.
    sources = [(source_scene,None) for source_scene in bpy.data.scenes]
    return capture_font_job(sources, root, actual_path(item,'FONTS',node),
        directory=bpy.path.abspath(item.font_directory), lookup=item.use_font_directory,
        node_name=node.name, export_index=index)


def prepare(scene):
    preparation_start = time.perf_counter()
    print(f'{LOG_PREFIX} ACTIVE ADDON v{bl_info["version"][0]}.{bl_info["version"][1]}.{bl_info["version"][2]} | preparing export destinations')
    sid = scene.as_pointer()
    if sid in SESSIONS:
        if SESSIONS[sid].get('oca_capture'):return
        cleanup(scene)
    tree = scene_tree(scene)
    if not tree:
        return
    jobs = []
    temp_nodes = []
    skipped = []
    root = None
    owner_token = None
    oca_capture = any(n.bl_idname=='CompositorNodeOutputFile' and not is_temporary_node(n.name)
        and any(e.enabled and e.format=='OCA' for e in n.blend_artwork_exports) for n in tree.nodes)
    try:
        # Collection provenance is determined per linked output socket from
        # its upstream Render Layers node. No single active View Layer owns
        # all sockets, and no legacy _collection_paths lookup is needed.
        paths = ()
        for node in list(tree.nodes):
            if node.bl_idname != 'CompositorNodeOutputFile' or is_temporary_node(node.name):
                continue
            migrate_legacy(node)
            for export in node.blend_artwork_exports:
                normalize_legacy_path(export, node)
                if export.format == 'SVG' and not export.get('_v0722_svg_layers_migrated', False):
                    export.use_groups = True
                    export.flatten = False
                    export['_v0722_svg_layers_migrated'] = True
            selected = [item for item in node.blend_artwork_exports if item.enabled]
            print(f'{LOG_PREFIX} DESTINATIONS:', node.name, '=>',
                  [(i+1, item.format, 'enabled' if item.enabled else 'disabled')
                   for i, item in enumerate(node.blend_artwork_exports)])
            if not selected:
                continue
            raw = connected(tree, node)
            if not raw:
                if any(item.format!='FONTS' for item in selected):
                    skipped.append(node.name + ': no linked image sockets for image outputs')
                selected=[item for item in selected if item.format=='FONTS']
                if not selected:continue
            names = [name for name, _ in raw]
            try:
                mapped = _map_layers(node, names, paths, tree=tree, pairs=raw, scene=scene, verbose=True) if raw else []
            except Exception:
                print(f'{LOG_PREFIX} WARNING: Collection mapping failed, preserving ungrouped artwork:', traceback.format_exc())
                mapped = [''] * len(names)
            print(f'{LOG_PREFIX} Automatic collection matches: {sum(bool(x) for x in mapped)}/{len(raw)}')
            supported = []
            for item in selected:
                supported_depth = {
                    'PSD': (8,16,32), 'PSB': (8,16,32), 'OCA': (8,16,32),
                    'PNG': (8,16), 'SVG': (8,16), 'EXR': (16,32), 'TIFF': (8,16), 'JPEG': (8,), 'FONTS': (8,),
                }
                if int(item.depth) not in supported_depth.get(item.format, ()):
                    skipped.append(f'{node.name}: unsupported {item.format} {item.depth}-bit configuration')
                    continue
                if item.format not in SUPPORTED_NOW:
                    skipped.append(f'{node.name}: {item.format} uses native File Output (no additional writer yet)')
                    continue
                try:
                    dest = actual_path(item, item.format, node)
                except Exception as exc:
                    skipped.append(f'{node.name}: {exc}')
                    continue
                supported.append((item, dest))
                print(f'{LOG_PREFIX} OUTPUT READY:', item.format, '=>', dest)
            if not supported:
                continue
            err = missing() if any(i.format != 'FONTS' for i,_ in supported) else None
            if err:
                skipped.append(f'{node.name}: PSD/OCA dependency unavailable: {err}')
                continue
            if root is None:
                root, owner_token = create_owned_job(str(job_cache_base()))
            caches = {}
            vector_sources = {}
            for item, dest in supported:
                if item.format == 'FONTS':
                    jobs.append(_capture_fonts(scene,tree,node,raw,item,root,
                                                list(node.blend_artwork_exports).index(item)))
                    continue
                kind = cache_kind_for(item)
                cache_key = (kind, bool(item.save_as_render) if kind.startswith('PNG') else False)
                if cache_key not in caches:
                    folder = root / f'{len(temp_nodes):03d}_{kind.lower()}'
                    folder.mkdir(parents=True, exist_ok=True)
                    available = [{'name': name, 'socket': sock, 'collection_path': mapped[i],
                                  **_source_render_state(tree, sock, scene),
                                  'source_view_layer': _source_view_layer_label(tree, sock, scene),
                                  'collection_colors': source_collection_colors(mapped[i], bpy.data.collections, theme_collection_colors(bpy))}
                                 for i, (name, sock) in enumerate(raw)]
                    temp, manifest, extension = create_companion(tree, node, folder, available, kind,
                                                                save_as_render=bool(item.save_as_render))
                    temp_nodes.append(temp.name)
                    caches[cache_key] = (folder, manifest, extension)
                folder, manifest, extension = caches[cache_key]
                # Capture source snapshots before rendering; evaluated geometry
                # and colour conversion belong in the isolated worker process.
                vector_by_index = {}
                vector_fallback_reasons = {}
                if (item.format == 'OCA' or (item.format in ('SVG','PSD','PSB') and not item.bake_svg_png)) and not item.flatten:
                    for vec_i, (_, source_socket) in enumerate(raw):
                        if manifest[vec_i].get('render_disabled'):
                            vector_fallback_reasons[vec_i] = 'Source View Layer disabled for rendering'
                            continue
                        src_scene, src_layer, reason = _svg_source.direct_render_image_source(
                            tree, source_socket, scene, source_render_layers)
                        if src_scene is not None and src_layer is not None:
                            vector_key = (src_scene.as_pointer(), src_layer.as_pointer(), int(src_scene.frame_current),
                                          bool(item.save_as_render), bool(item.svg_flat_text_material), mapped[vec_i],
                                          str(item.font_directory), bool(item.use_font_directory))
                            if vector_key not in vector_sources:
                                candidate = root / 'vectors' / f'{len(jobs):03d}_{vec_i:04d}.svg'
                                vector_sources[vector_key] = _export_svg_candidate(src_scene, src_layer, candidate, item,
                                                                                 collection_root=mapped[vec_i])
                            ok, reason, candidate = vector_sources[vector_key]
                            if ok:
                                vector_by_index[vec_i] = str(candidate)
                        source_label = (f'{src_scene.name}/{src_layer.name}'
                                        if src_scene is not None and src_layer is not None
                                        else '(unresolved)')
                        if vec_i not in vector_by_index:
                            vector_fallback_reasons[vec_i] = str(reason)
                        print(f'{LOG_PREFIX} SVG {names[vec_i]}: '+
                              ('vector' if vec_i in vector_by_index else 'PNG fallback')+
                              ' (' + reason + ') | source: ' + source_label)
                # Collection provenance is independent of destination format.
                per_item_paths = mapped
                job_manifest = [dict(entry, collection_path=per_item_paths[i],
                                           vector_svg=vector_by_index.get(i, ''),
                                           vector_reason=(vector_fallback_reasons.get(i, '') if not item.bake_svg_png
                                                          else 'User selected Rasterise Vector Artwork'),
                                           collection_colors=source_collection_colors(per_item_paths[i], bpy.data.collections, theme_collection_colors(bpy)))
                                for i, entry in enumerate(manifest)]
                if item.format == 'OCA':
                    from .oca_controls import capture_source,input_identity
                    linked_inputs=[s for s in node.inputs if s.is_linked]
                    for entry, (_, socket),destination_socket in zip(job_manifest, raw,linked_inputs):
                        entry.update(capture_source(tree, socket, scene, entry['collection_path'], source_render_layers))
                        entry['oca_source_id']=input_identity(node,destination_socket)
                from .gp_raster_cache import source_plan
                for entry in job_manifest:
                    if entry.get('vector_svg'):
                        plan=source_plan(entry['vector_svg'])
                        if plan:entry['gp_render_source']=plan
                jobs.append({
                    'allow_gp_cache_repair': True,
                    'node_name': node.name,
                    'export_index': next(i for i, entry in enumerate(node.blend_artwork_exports) if entry == item),
                    'cache_kind': kind,
                    'canvas_size': _canvas_size(scene),
                    'source_file': bpy.data.filepath,
                    'source_scene': scene.name,
                    'cache_history_root': str(job_cache_base()),
                    'cache_history_roots': [str(path) for path in job_roots()],
                    'cache_destination': str(dest),
                    'dir': str(folder),
                    'manifest': job_manifest,
                    'extension': extension,
                    'dest': str(dest),
                    'format': item.format,
                    'tag_profile': _tag_registry.effective_profile('PASSTHROUGH' if item.flatten else item.tag_profile, item.format),
                    'depth': int(item.depth),
                    'hierarchy': 'GROUPS' if item.use_groups and not item.flatten else 'FLAT',
                    'flatten': bool(item.flatten),
                    'overwrite': True,
                    'save_as_render': bool(item.save_as_render),
                    'bake_svg_png': bool(item.bake_svg_png),
                    'svg_flat_text_material': bool(item.svg_flat_text_material),
                    'svg_editable_layer_blends': True,
                    'font_directory': bpy.path.abspath(item.font_directory),
                    'use_font_directory': bool(item.use_font_directory),
                    'svg_root_mode': item.svg_root_mode,
                    'svg_root_name': item.svg_root_name,
                    'psd_compression': item.psd_compression,
                    'frame': int(scene.frame_current),
                    'frame_rate': float(scene.render.fps) / max(0.0001, float(scene.render.fps_base)),
                })
                if item.format == 'OCA':
                    from .oca_controls import capture_options
                    jobs[-1]['oca_options'] = capture_options(item)
                    jobs[-1]['trim_empty_pixels'] = bool(item.trim_empty_pixels)
                    jobs[-1]['oca_keep_png'] = bool(item.oca_keep_png)
                    jobs[-1]['oca_half_float'] = bool(item.oca_half_float)
                    jobs[-1]['oca_layout']=item.oca_layout
                    jobs[-1]['oca_background_color']=list(scene.handoff_oca_background_color)
                    jobs[-1]['origin_app_version']=bpy.app.version_string
                    jobs[-1]['oca_metadata']={key:scene.get(key) for key in ('author','copyright','license','licenseLong','licenseURL','description','created') if isinstance(scene.get(key),str)}
        print(f'{LOG_PREFIX} JOB QUEUE:', len(jobs),
              [(j['format'], j['dest']) for j in jobs])
        if skipped:
            for note in skipped:
                print(f'{LOG_PREFIX} SKIPPED:', note)
        if jobs:
            try:
                report = _provenance_report(scene, jobs)
                (root / 'collection_mapping.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            except Exception as exc:
                print(f'{LOG_PREFIX} Warning writing collection report:', repr(exc))
            scene.blend_psd_retry_folder = str(root)
            scene.blend_psd_status = f'Render started - {len(jobs)} export(s) queued'
            SESSIONS[sid] = {'tree': tree, 'root': str(root), 'jobs': jobs,
                             'temps': temp_nodes, 'skipped': skipped, 'owner_token': owner_token,
                             'oca_frames':{},'oca_capture':oca_capture,
                             'frame_range':(int(scene.frame_start),int(scene.frame_end),int(scene.frame_step)),
                             'preparation_seconds': time.perf_counter() - preparation_start,
                             'render_started_at': time.perf_counter()}
            print(f'{LOG_PREFIX} Jobs:', len(jobs), 'retained at:', root)
        else:
            if root:
                discard_owned_job(root, owner_token)
            if skipped:
                scene.blend_psd_status = 'No exports prepared - check output settings'
    except Exception:
        if root:
            discard_owned_job(root, owner_token)
        for name in temp_nodes:
            temp = tree.nodes.get(name)
            if temp:
                tree.nodes.remove(temp)
        raise


def cleanup(scene, discard=True):
    sess = SESSIONS.pop(scene.as_pointer(), None)
    if sess:
        for name in sess['temps']:
            node = sess['tree'].nodes.get(name)
            if node:
                try:
                    sess['tree'].nodes.remove(node)
                except Exception as exc:
                    print(f'{LOG_PREFIX} Failed cleaning temporary node:', exc)
        if discard:
            discard_owned_job(sess['root'], sess.get('owner_token'))
    return sess


_CHIME_DEVICE = None
_CHIME_HANDLE = None


def _release_chime():
    global _CHIME_DEVICE, _CHIME_HANDLE
    if _CHIME_HANDLE is not None:
        try:
            _CHIME_HANDLE.stop()
        except Exception:
            pass  # The audio device may already have closed.
    _CHIME_HANDLE = None
    _CHIME_DEVICE = None


def _stop_chime():
    if bpy.app.timers.is_registered(_poll_chime):
        bpy.app.timers.unregister(_poll_chime)
    _release_chime()


def _poll_chime():
    if _CHIME_HANDLE is not None:
        import aud
        if _CHIME_HANDLE.status == aud.STATUS_PLAYING:
            return .25
    _release_chime()
    return None


def _chime_volume_get(scene):
    # Old files store only the checkbox. An existing mute remains muted;
    # an enabled old file starts at the original, unattenuated level.
    if not scene.get('blend_psd_chime_enabled', True):
        return 0.0
    return max(0.0, min(1.0, float(scene.get('blend_psd_chime_volume', 1.0))))


def _chime_volume_set(scene, value):
    value = max(0.0, min(1.0, float(value)))
    scene['blend_psd_chime_volume'] = value
    scene['blend_psd_chime_enabled'] = value > 0
    if value == 0:
        _stop_chime()


def _legacy_chime_get(scene):
    return bool(scene.get('blend_psd_chime_enabled', True))


def _legacy_chime_set(scene, enabled):
    value = float(scene.get('blend_psd_chime_volume', 1.0)) if enabled else 0.0
    _chime_volume_set(scene, value if value > 0 or not enabled else 1.0)


def notify_success(scene):
    volume = _chime_volume_get(scene)
    # No audio import, file access, sound factory or device at zero.
    if volume <= 0 or bpy.app.background:
        return
    wav = ROOT / 'assets' / 'export_success.wav'
    if not wav.is_file():
        print(f'{LOG_PREFIX} Completion chime asset missing:', wav)
        return
    try:
        import aud
        global _CHIME_DEVICE, _CHIME_HANDLE
        _stop_chime()
        # Apply linear sample gain BEFORE playback, avoiding an initial burst
        # at full volume. Blender supplies this cross-platform audio backend.
        sound = aud.Sound(str(wav)).volume(volume)
        _CHIME_DEVICE = aud.Device()
        _CHIME_HANDLE = _CHIME_DEVICE.play(sound)
        bpy.app.timers.register(_poll_chime, first_interval=.25)
    except Exception as exc:
        _stop_chime()
        print(f'{LOG_PREFIX} Completion chime failed:', exc)


def start_monitor(scene, process, jobfile, partial=False, log=None):
    key = {'scene': scene.name, 'process': process, 'jobfile': str(jobfile), 'partial': partial,
           'log': str(log or Path(jobfile).parent / 'conversion.log')}
    MONITORS.append(key)

    def poll():
        if key not in MONITORS:
            return None
        if process.poll() is None:
            return 1.0
        MONITORS.remove(key)
        current = bpy.data.scenes.get(key['scene'])
        if not current:
            return None
        report_path = Path(key['jobfile']).parent / 'result.json'
        try:
            report = json.loads(report_path.read_text(encoding='utf-8'))
            succeeded = report['succeeded']
            failed = report['failed']
            notices = [note for detail in report.get('details', []) for note in detail.get('notices', [])]
            current.blend_psd_export_notices = json.dumps(list(dict.fromkeys(notices)))
            current.blend_psd_export_timings = json.dumps(report)
            if process.returncode == 0 and failed == 0 and succeeded > 0:
                auto_psb = any(x.get('dest', '').lower().endswith('.psb') for x in report.get('details', []))
                current.blend_psd_status = (
                    f'Last operation successful ({succeeded} export(s))'
                    if not partial else
                    f'Exports successful ({succeeded}); other formats were skipped'
                )
                if auto_psb:
                    current.blend_psd_status += ' - PSB written'
                if notices:
                    current.blend_psd_status += f' - {len(set(notices))} notice(s); see Diagnostics'
                if any(detail.get('partial') for detail in report.get('details',[])):
                    current.blend_psd_status='Export partial - see Diagnostics'
                else:
                    notify_success(current)
            else:
                current.blend_psd_status = f'Export failed - {failed} failed, {succeeded} succeeded; Retry available'
        except (OSError, ValueError, KeyError, TypeError):
            current.blend_psd_status = 'Export failed - Retry available'
            current.blend_psd_export_timings = '{}'
            current.blend_psd_export_notices = json.dumps([
                'Export worker stopped without a valid result report '
                f'(exit code {process.returncode}). See '
                + key['log']])
        # Force visible node editors to pick up status changes, without editing nodes.
        wm = bpy.context.window_manager
        if wm:
            for window in wm.windows:
                for area in window.screen.areas:
                    if area.type == 'NODE_EDITOR':
                        area.tag_redraw()
        return None

    bpy.app.timers.register(poll, first_interval=1.0)


def launch_worker(scene, manifest, log, skipped=False):
    # Completion audio belongs to the UI process; the conversion worker does
    # not need an audio device (and must not wait for one during shutdown).
    command = [bpy.app.binary_path, '-b', '--factory-startup', '-noaudio', '--python',
               str(ROOT / WORKER_FILE), '--', str(manifest)]
    # A failed retry must not be mistaken for the previous operation's report.
    (Path(manifest).parent / 'result.json').unlink(missing_ok=True)
    with Path(log).open('wb') as handle:
        proc = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT,
                                start_new_session=True)
    scene.blend_psd_status = 'Exporting assets…'
    start_monitor(scene, proc, manifest, partial=skipped, log=log)
    print(f'{LOG_PREFIX} Conversion log:', log)


def dispatch(scene):
    sess = cleanup(scene, discard=False)
    if not sess:
        return
    root = Path(sess['root'])
    if any(len(frames)>1 for frames in sess.get('oca_frames',{}).values()):
        # Other formats still publish only the final frame. Refresh their
        # deferred vectors/text at that frame, without changing the render.
        sess['jobs']=refresh_cached_jobs(scene,{'jobs':sess['jobs']},allow_pending_vectors=True)['jobs']
        for job in sess['jobs']:
            if 'frame' in job: job['cache_frame']=job['frame']
    for job in sess['jobs']:
        frames=sess.get('oca_frames',{}).get((job.get('node_name'),job.get('export_index')),[])
        if job['format']=='OCA' and len(frames)>1:
            job['oca_frames']=frames
            job['oca_range']=sess['frame_range']
    manifest = root / 'jobs.json'
    manifest.write_text(json.dumps({'jobs': sess['jobs'], 'python_paths': list(sys.path),
        'render_performance': {'preparation_seconds': sess.get('preparation_seconds', 0),
                              'render_and_cache_seconds': max(0.0, time.perf_counter() - sess.get('render_started_at', time.perf_counter()))}},
        indent=2), encoding='utf-8')
    scene.blend_psd_retry_folder = str(root)
    log = root / 'conversion.log'
    try:
        launch_worker(scene, manifest, log, skipped=bool(sess['skipped']))
    except Exception:
        scene.blend_psd_status = 'Could not start PSD worker - Retry available'
        print(f'{LOG_PREFIX} Failed dispatch:', traceback.format_exc())


# IMPORTANT: Blender enables extensions under _RestrictData. Accessing
# bpy.data.node_groups/scenes from register() throws AttributeError there.
# Schedule legacy settings migration for normal runtime instead.
_MIGRATION_ATTEMPTS = 0


def _migrate_after_registration():
    global _MIGRATION_ATTEMPTS
    try:
        migrate_all()
    except AttributeError as exc:
        # On startup, some Blender builds may still be restricting bpy.data.
        # Retry briefly, without blocking extension installation.
        if '_RestrictData' in str(exc) and _MIGRATION_ATTEMPTS < 10:
            _MIGRATION_ATTEMPTS += 1
            return 0.5
        print(f'{LOG_PREFIX} Deferred migration unavailable:', exc)
    except Exception:
        print(f'{LOG_PREFIX} Deferred migration error:', traceback.format_exc())
    return None


@persistent
def before_render(scene, *args):
    try:
        from .render_temp import ensure_render_tempdir
        ensure_render_tempdir(bpy.app.tempdir)
        prepare(scene)
    except Exception:
        print(f'{LOG_PREFIX} F12 preparation failed:', traceback.format_exc())
        cleanup(scene)
        scene.blend_psd_status = 'Export preparation failed - see console'


@persistent
def begin_oca_render(scene, *args):
    tree=scene_tree(scene)
    if tree and any(n.bl_idname=='CompositorNodeOutputFile' and not is_temporary_node(n.name)
            and any(e.enabled and e.format=='OCA' for e in n.blend_artwork_exports) for n in tree.nodes):
        before_render(scene)


@persistent
def capture_oca_frame(scene, *args):
    sess=SESSIONS.get(scene.as_pointer())
    if not sess:return
    for job in sess['jobs']:
        job['frame']=int(scene.frame_current)
        if job['format']!='OCA':continue
        key=(job.get('node_name'),job.get('export_index'))
        frames=sess['oca_frames'].setdefault(key,[])
        if frames and frames[-1]['frame']==job['frame']:continue
        captured=dict(job,cache_frame=job['frame'])
        from .oca_vectors import capture_frame_sources
        from .oca_authoring import capture_frame
        captured['manifest']=capture_frame_sources([capture_frame(e) for e in job['manifest']],job['frame'])
        frames.append(captured)


@persistent
def after_render(scene, *args):
    try:
        dispatch(scene)
    except Exception:
        print(f'{LOG_PREFIX} Dispatch failed:', traceback.format_exc())
        scene.blend_psd_status = 'PSD conversion could not start'


@persistent
def cancel_render(scene, *args):
    cleanup(scene)
    scene.blend_psd_status = 'Render cancelled'


@persistent
def after_load(_):
    # A recovery file may retain an interrupted render's cache companion.
    # Never remove unmarked or merely similarly named authored nodes.
    for tree in all_compositor_trees():
        for node in list(tree.nodes):
            if (node.bl_idname == 'CompositorNodeOutputFile' and
                    any(re.fullmatch(re.escape(prefix) + r'[0-9a-f]{10}', node.name) for prefix in TEMP_NODE_PREFIXES) and
                    any(node.get(marker, False) for marker in TEMP_MARKERS)):
                tree.nodes.remove(node)
    migrate_all()


class OT_sync_view_layers(Operator):
    bl_idname = 'blend_psd.sync_view_layers'
    bl_label = 'Update Inputs to ViewLayers'
    bl_description = ('Sync this File Output with the current scene View Layers; keep processed links and input order, '
                      'append missing layers, rename inputs and report removed managed inputs. Supports one scene effect')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return target(context) is not None

    def execute(self, context):
        from .view_layer_sync import synchronize, SyncError
        node = target(context)
        if node is None:
            return {'CANCELLED'}
        try:
            report = synchronize(context.scene, node)
        except (SyncError, RuntimeError, TypeError, KeyError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        summary = (f'Inputs: {len(report["added"])} added, {len(report["renamed"])} renamed, '
                   f'{len(report["removed"])} removed; {len(report["created_nodes"])} Render Layers nodes created')
        print(f'{LOG_PREFIX} VIEW LAYER SYNC:', summary, flush=True)
        for kind in ('added', 'renamed', 'removed', 'created_nodes', 'warnings'):
            for message in report[kind]:
                print(f'{LOG_PREFIX} SYNC ' + kind.upper() + ':', message, flush=True)
        self.report({'WARNING'} if report['warnings'] else {'INFO'}, summary)
        if report['removed']:
            self.report({'WARNING'}, 'Removed inputs: ' + '; '.join(report['removed']))
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class OT_add(Operator):
    bl_idname = 'blend_psd.add_export'
    bl_label = 'Add Export'
    bl_description = 'Add a destination to this File Output node'

    def execute(self, context):
        n = target(context)
        if not n:
            return {'CANCELLED'}
        o = n.blend_artwork_exports.add()
        o.name = f'Export {len(n.blend_artwork_exports)}'
        if len(n.blend_artwork_exports) > 1:
            o.path = n.blend_artwork_exports[-2].path
        else:
            o.path = n.directory or '//'
        if not o.path.startswith('//'):
            try:
                o.path = bpy.path.relpath(bpy.path.abspath(o.path))
            except Exception:
                pass
        o.relative_path = True
        o['_v061_path_migrated'] = True
        n.blend_artwork_index = len(n.blend_artwork_exports) - 1
        return {'FINISHED'}


class OT_remove(Operator):
    bl_idname = 'blend_psd.remove_export'
    bl_label = 'Remove Export'
    bl_description = 'Remove the selected additional destination; native Blender output is unchanged'
    index: IntProperty(default=-1)

    def execute(self, context):
        n = target(context)
        if not n:
            return {'CANCELLED'}
        idx = self.index if self.index >= 0 else n.blend_artwork_index
        if not 0 <= idx < len(n.blend_artwork_exports):
            return {'CANCELLED'}
        n.blend_artwork_exports.remove(idx)
        n.blend_artwork_index = min(max(0, idx - 1), max(0, len(n.blend_artwork_exports) - 1))
        return {'FINISHED'}


def refresh_cached_jobs(scene, data, *, allow_pending_vectors=False):
    """Refresh *metadata*, never pixels, from the current Blender scene.

    Important: earlier releases simply reran the old jobs.json. This made a
    new Assets.ignore / Assets.ungroup name or changed hierarchy invisible to
    the Retry button. Do not mutate the original render-time jobs.json.
    """
    import copy
    updated = copy.deepcopy(data)
    # Retry re-evaluates each source socket's real Render Layers provenance.
    # The old view-layer-wide _collection_paths() helper was removed and is
    # deliberately not reinstated.
    paths = ()
    nodes = {}
    for tree in all_compositor_trees():
        for n in tree.nodes:
            if n.bl_idname == 'CompositorNodeOutputFile' and not is_temporary_node(n.name):
                nodes.setdefault(n.name, []).append((n, tree))
    print(f'{LOG_PREFIX} Retry: refreshing collection mapping per source socket')
    refreshed = 0
    for job in updated.get('jobs', []):
        job['allow_gp_cache_repair']=bool(allow_pending_vectors)
        matches = nodes.get(job.get('node_name'), [])
        node, node_tree = matches[0] if len(matches) == 1 else (None, None)
        if node is None:
            print(f'{LOG_PREFIX} WARNING: Source node not found uniquely; using cached options:', job.get('node_name'))
            continue
        exports = node.blend_artwork_exports
        index = job.get('export_index', -1)
        if not (isinstance(index, int) and 0 <= index < len(exports)):
            # Legacy cached jobs: use destination filename to identify output.
            for i, e in enumerate(exports):
                try:
                    if str(actual_path(e, e.format, node)) == str(job['dest']):
                        index = i
                        break
                except Exception:
                    pass
        if not (isinstance(index, int) and 0 <= index < len(exports)):
            print(f'{LOG_PREFIX} WARNING: Destination not matched; retaining cached format settings')
            continue
        current = exports[index]
        if current.format == 'SVG' and not current.get('_v0722_svg_layers_migrated', False):
            current.use_groups = True
            current.flatten = False
            current['_v0722_svg_layers_migrated'] = True
        if not current.enabled:
            print(f'{LOG_PREFIX} Retry skips disabled destination',index+1)
            job['_disabled_on_retry'] = True
            continue
        if current.format == 'FONTS':
            root = Path(job['dir']) if job.get('cache_kind') == 'FONTS' else Path(job['dir']).parent
            job.clear()
            job.update(_capture_fonts(scene,node_tree,node,connected(node_tree,node),current,root,index))
            refreshed += 1
            continue
        expected = cache_kind_for(current)
        actual = job.get('cache_kind')
        if not actual:
            actual = ('EXR32' if job.get('extension') == '.exr' else 'PNG'+str(job.get('depth',8)))
        if expected != actual:
            raise ValueError(f'Output {index+1} needs {expected} cache, but retained render is {actual}. Re-render with F12 for that precision/format change.')
        job.setdefault('cache_destination', job.get('dest'))
        job.setdefault('cache_history_root', str(Path(job['dir']).parent.parent))
        job.setdefault('cache_history_roots', list(dict.fromkeys([job['cache_history_root'], *map(str, job_roots())])))
        job['dest'] = str(actual_path(current, current.format, node))
        job['format'] = current.format
        job['tag_profile'] = _tag_registry.effective_profile('PASSTHROUGH' if current.flatten else current.tag_profile, current.format)
        job['depth'] = int(current.depth)
        job['hierarchy'] = 'GROUPS' if current.use_groups and not current.flatten else 'FLAT'
        job['flatten'] = bool(current.flatten)
        job['overwrite'] = True
        job['save_as_render'] = bool(current.save_as_render)
        job['bake_svg_png'] = bool(current.bake_svg_png)
        job['svg_flat_text_material'] = bool(current.svg_flat_text_material)
        job['svg_editable_layer_blends'] = True
        job['font_directory'] = bpy.path.abspath(current.font_directory)
        job['use_font_directory'] = bool(current.use_font_directory)
        job['svg_root_mode'] = current.svg_root_mode
        job['svg_root_name'] = current.svg_root_name
        job.pop('psd_svg_sidecars',None)
        job.pop('psd_link_svg_fallbacks',None)
        job.pop('psd_target',None)
        job['psd_compression'] = current.psd_compression
        if current.format == 'OCA': job['oca_keep_png'] = bool(current.oca_keep_png)
        if current.format == 'OCA':
            job['oca_layout']=current.oca_layout
            job['oca_background_color']=list(scene.handoff_oca_background_color)
            job['oca_half_float']=bool(current.oca_half_float)
        if current.format == 'OCA':
            from .oca_controls import capture_options
            job['oca_options'] = capture_options(current)
            job['trim_empty_pixels'] = bool(current.trim_empty_pixels)
        job['export_index'] = index
        job['canvas_size'] = _canvas_size(scene)
        raw = connected(node_tree, node)
        current_names = [name for name, sock in raw]
        cached = job.get('manifest', [])
        if len(current_names) != len(cached):
            raise ValueError(f'Retry cannot safely remap {len(cached)} cached layers to {len(current_names)} current sockets. F12 is required after adding or removing layer sockets.')
        old_names = [x['name'] for x in cached]
        # Renaming a socket is fine; changing the order of existing sockets
        # without rerendering would swap image contents silently.
        if any(old_name in current_names and current_names[i] != old_name
               for i, old_name in enumerate(old_names)):
            raise ValueError('File Output layer socket order changed; F12 required to avoid wrong pixel assignments.')
        try:
            groups = _map_layers(node, current_names, paths, tree=node_tree, pairs=raw, scene=scene, verbose=True)
        except Exception:
            print(f'{LOG_PREFIX} WARNING: Retry grouping failed:', traceback.format_exc())
            groups = [''] * len(current_names)
        for i, entry in enumerate(cached):
            entry['name'] = current_names[i]
            entry['collection_path'] = groups[i]
            entry['collection_colors'] = source_collection_colors(groups[i], bpy.data.collections, theme_collection_colors(bpy))
            entry['source_view_layer'] = _source_view_layer_label(node_tree, raw[i][1], scene)
            entry.setdefault('render_was_disabled', bool(entry.get('render_disabled')))
            entry.update(_source_render_state(node_tree, raw[i][1], scene))
            entry.pop('render_placeholder', None)
            if current.format == 'OCA':
                from .oca_controls import capture_source,input_identity
                entry.update(capture_source(node_tree, raw[i][1], scene, entry['collection_path'], source_render_layers))
                entry['oca_source_id']=input_identity(node,[s for s in node.inputs if s.is_linked][i])
            if current.format in ('SVG','PSD','PSB','OCA'):
                retained_vector = entry.get('vector_svg', '')
                entry['vector_svg'] = ''
                entry['vector_reason'] = 'User selected Rasterise Vector Artwork' if current.bake_svg_png else ''
                if entry.get('render_disabled'):
                    entry['vector_reason'] = 'Source View Layer disabled for rendering'
                    continue
                if allow_pending_vectors and retained_vector:
                    # Animation has just finished rendering; its queued SVG has
                    # intentionally not been evaluated by the worker yet.
                    from .oca_vectors import capture_frame_sources, DEFERRED
                    from xml.etree import ElementTree as ET
                    pending=Path(retained_vector)
                    if pending.is_file() and ET.parse(pending).getroot().get(DEFERRED):
                        entry['vector_svg']=capture_frame_sources(
                            [dict(vector_svg=retained_vector)],scene.frame_current)[0]['vector_svg']
                        entry['vector_reason']='SVG evaluation queued for final animation frame'
                        continue
                if (current.format == 'OCA' or (current.format in ('SVG','PSD','PSB') and not current.bake_svg_png)) and not current.flatten:
                    src_scene, src_layer, reason = _svg_source.direct_render_image_source(
                        node_tree, raw[i][1], scene, source_render_layers)
                    if src_scene is not None and src_layer is not None:
                        candidate = Path(job['dir']).parent / 'vectors' / f'retry_{index:03d}_{i:04d}.svg'
                        ok, reason, candidate = _export_svg_candidate(
                            src_scene, src_layer, candidate, current, retained=retained_vector,
                            collection_root=entry['collection_path'])
                        if ok:
                            entry['vector_svg'] = str(candidate)
                    origin = (f'{src_scene.name}/{src_layer.name}' if src_scene is not None and src_layer is not None else '(unresolved)')
                    if not entry['vector_svg']:
                        entry['vector_reason'] = str(reason)
                    print(f'{LOG_PREFIX} SVG retry:', entry['name'],
                          'vector' if entry['vector_svg'] else 'PNG fallback', reason, '| source:', origin)
            print(f"  {entry['name']} => {entry['collection_path'] or '(unmatched/root)'}")
        refreshed += 1
    # An SVG destination may have been added after the last F12 render.
    # Reuse a compatible PNG cache rather than requiring another expensive
    # render just to construct the new layered SVG document.
    for node_name, matches in nodes.items():
        if len(matches) != 1:
            continue
        node, node_tree = matches[0]
        raw = connected(node_tree, node)
        current_names = [n for n, _ in raw]
        for export_index, current in enumerate(node.blend_artwork_exports):
            if not current.enabled or current.format not in ('SVG','FONTS'):
                continue
            if any(j.get('node_name') == node_name and j.get('export_index') == export_index
                   for j in updated.get('jobs', [])):
                continue
            if current.format == 'FONTS':
                donor = next((j for j in updated.get('jobs',[]) if j.get('dir')),None)
                if donor is None:
                    raise ValueError('Retained job location is unavailable')
                root = Path(donor['dir']) if donor.get('cache_kind') == 'FONTS' else Path(donor['dir']).parent
                updated['jobs'].append(_capture_fonts(scene,node_tree,node,raw,current,root,export_index))
                continue
            if any(j.get('node_name') == node_name and j.get('export_index') == export_index
                   for j in updated.get('jobs', [])):
                continue
            if not current.get('_v0722_svg_layers_migrated', False):
                current.use_groups = True
                current.flatten = False
                current['_v0722_svg_layers_migrated'] = True
            expected = cache_kind_for(current)
            donors = [j for j in updated.get('jobs', [])
                      if j.get('node_name') == node_name and j.get('cache_kind') == expected
                      and j.get('extension') == '.png'
                      and bool(j.get('save_as_render', True)) == bool(current.save_as_render)
                      and not j.get('_disabled_on_retry')]
            donor = next((j for j in donors if [e['name'] for e in j['manifest']] == current_names), None)
            if donor is None:
                print(f'{LOG_PREFIX} SVG RETRY SKIPPED:', node_name,
                      '| no matching', expected, 'cache with unchanged socket order; use F12')
                continue
            new_job = copy.deepcopy(donor)
            new_job.update(export_index=export_index,
                           canvas_size=_canvas_size(scene),
                           dest=str(actual_path(current, 'SVG', node)), format='SVG',
                           tag_profile=_tag_registry.effective_profile(current.tag_profile, 'SVG'),
                           depth=int(current.depth), hierarchy='GROUPS' if current.use_groups else 'FLAT',
                           flatten=bool(current.flatten), overwrite=True, bake_svg_png=bool(current.bake_svg_png),
                           svg_flat_text_material=bool(current.svg_flat_text_material),
                           svg_editable_layer_blends=True,
                           font_directory=bpy.path.abspath(current.font_directory),
                           use_font_directory=bool(current.use_font_directory),
                           svg_root_mode=current.svg_root_mode,
                           svg_root_name=current.svg_root_name)
            for i, entry in enumerate(new_job['manifest']):
                entry.setdefault('render_was_disabled', bool(entry.get('render_disabled')))
                entry.update(_source_render_state(node_tree, raw[i][1], scene))
                entry.pop('render_placeholder', None)
                retained_vector = entry.get('vector_svg', '')
                entry['vector_svg'] = ''
                entry['vector_reason'] = 'User selected Rasterise Vector Artwork' if current.bake_svg_png else ''
                if entry.get('render_disabled'):
                    entry['vector_reason'] = 'Source View Layer disabled for rendering'
                    continue
                if not current.bake_svg_png:
                    src_scene, src_layer, reason = _svg_source.direct_render_image_source(
                        node_tree, raw[i][1], scene, source_render_layers)
                    if src_scene is not None and src_layer is not None:
                        candidate = Path(new_job['dir']).parent / 'vectors' / f'added_{export_index:03d}_{i:04d}.svg'
                        ok, reason, candidate = _export_svg_candidate(
                            src_scene, src_layer, candidate, current, retained=retained_vector,
                            collection_root=entry['collection_path'])
                        if ok:
                            entry['vector_svg'] = str(candidate)
                    origin = (f'{src_scene.name}/{src_layer.name}' if src_scene is not None and src_layer is not None else '(unresolved)')
                    if not entry['vector_svg']:
                        entry['vector_reason'] = str(reason)
                    print(f'{LOG_PREFIX} SVG RETRY:', entry['name'],
                          'vector' if entry['vector_svg'] else 'embedded PNG', reason, '| source:', origin)
            updated['jobs'].append(new_job)
            refreshed += 1
            print(f'{LOG_PREFIX} SVG RETRY ADDED:', new_job['dest'], '| from retained PNG cache')
    updated['jobs'] = [x for x in updated.get('jobs',[]) if not x.pop('_disabled_on_retry',False)]
    if not updated['jobs']:
        raise ValueError('All retained export destinations are disabled or missing.')
    from .oca_authoring import refresh_frames
    for job in updated['jobs']:
        if job.get('format')=='OCA' and job.get('oca_frames'):refresh_frames(job)
    print(f'{LOG_PREFIX} Retry: refreshed {refreshed}/{len(updated["jobs"])} jobs; cached images unchanged')
    return updated


class OT_retry(Operator):
    bl_idname = 'blend_psd.retry_job'
    bl_label = 'Retry Conversion (No Render)'
    bl_description = 'Rebuild exports from retained pixels, refreshing collection names and group settings; no render needed'

    def execute(self, context):
        folder = bpy.path.abspath(context.scene.blend_psd_retry_folder).strip()
        jobfile = Path(folder) / 'jobs.json'
        if not jobfile.is_file():
            self.report({'ERROR'}, 'No jobs.json in the selected job folder')
            return {'CANCELLED'}
        try:
            data = json.loads(jobfile.read_text(encoding='utf-8'))
            data = refresh_cached_jobs(context.scene, data)
            data['python_paths'] = list(sys.path)
            retry_manifest = jobfile.parent / 'jobs-retry.json'
            retry_manifest.write_text(json.dumps(data, indent=2), encoding='utf-8')
            try:
                report = _provenance_report(context.scene, data.get('jobs', []))
                (jobfile.parent / 'collection_mapping_retry.json').write_text(
                    json.dumps(report, indent=2), encoding='utf-8')
            except Exception as exc:
                print(f'{LOG_PREFIX} Warning writing retry collection report:', repr(exc))
            launch_worker(context.scene, retry_manifest, jobfile.parent / 'conversion-retry.log')
            self.report({'INFO'}, 'Export retry started (no render)')
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc)[:180])
            return {'CANCELLED'}


class OT_clear_job_cache(Operator):
    bl_idname = 'blend_psd.clear_job_cache'
    bl_label = 'Clear Cache'
    bl_description = (f'Remove old {BRAND_NAME} retained render jobs from the dedicated cache folder. '
                      'The currently selected job is preserved unless Clear all is checked. '
                      'Active jobs are never deleted.')

    def invoke(self, context, event):
        # Filesystem operations are irreversible. Let the user confirm them.
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        root = job_cache_base()
        raw_folder = context.scene.blend_psd_retry_folder.strip()
        current = bpy.path.abspath(raw_folder).strip() if raw_folder else ''
        clear_all = context.scene.blend_psd_cache_clear_all
        if not clear_all and not current:
            self.report({'ERROR'}, 'Select a retained Job Folder, or enable Clear all')
            return {'CANCELLED'}
        if current:
            selected = Path(current).expanduser().resolve(strict=False)
            roots = [path.resolve() for path in job_roots()]
            if selected in roots or selected.parent not in roots:
                self.report({'ERROR'}, 'Selected job folder must be inside the export job cache')
                return {'CANCELLED'}
            root = selected.parent
            if not clear_all and (not selected.is_dir() or
                                  not selected.name.startswith(JOB_PREFIXES)):
                self.report({'ERROR'}, 'Selected job folder is missing or is not a retained job')
                return {'CANCELLED'}
        active = [record.get('root') for record in SESSIONS.values()]
        active += [str(Path(record['jobfile']).parent) for record in MONITORS]
        try:
            deleted = skipped = bytes_removed = 0
            names = []
            for cache_root in job_roots() if clear_all else [root]:
                count, protected, size, removed = clear_jobs(
                    cache_root, current=current, clear_all=clear_all, active=active)
                deleted += count; skipped += protected; bytes_removed += size; names.extend(removed)
        except OSError as exc:
            self.report({'ERROR'}, 'Cache cleanup failed: ' + str(exc)[:160])
            return {'CANCELLED'}
        print(f'{LOG_PREFIX} CACHE CLEAR: {deleted} jobs removed, '
              f'{bytes_removed} bytes, {skipped} active jobs preserved; '
              f'clear_all={clear_all}')
        for name in names:
            print(f'{LOG_PREFIX}   deleted:', name)
        if clear_all:
            if current and not Path(current).exists():
                context.scene.blend_psd_retry_folder = ''
            # Prevent the next click from deleting the current job accidentally.
            context.scene.blend_psd_cache_clear_all = False
        self.report({'INFO'}, f'Removed {deleted} cached job(s); {skipped} active job(s) kept')
        return {'FINISHED'}


def _status_probe_data(context):
    """Check Export Status uses the exact same map as F12 and retry."""
    node = target(context)
    if node is None:
        raise ValueError('Select a native File Output node in the compositor')
    tree = context.space_data.edit_tree
    global _artwork_probe
    if not callable(getattr(_artwork_probe, 'attribution_status_detail', None)):
        _artwork_probe = _importlib.reload(_artwork_probe)
    rows = _artwork_probe.analyze_outputs(context.scene, node, tree, _provenance)
    raw = connected(tree, node)
    assignments = _map_layers(node, [n for n, _ in raw], (),
                              tree=tree, pairs=raw, scene=context.scene, verbose=True)
    for row, assigned in zip(rows, assignments):
        row['assigned_collection'] = assigned or None
        row['reason'] = 'Automatic source-scoped Collection match' if assigned else row.get('reason', '')
        row['status_detail'] = (('Collection: ' + assigned) if assigned else
                                _artwork_probe.attribution_status_detail(row, scene=context.scene))
    return node, tree, rows


class OT_check(Operator):
    bl_idname = 'blend_psd.check'
    bl_label = 'Check Export Status'
    bl_description = ('Validate enabled destinations, inspect connected render sources, '
                      'and list every artwork output without a verified Collection. '
                      'No separate probe, files, or render required.')

    def execute(self, context):
        node = target(context)
        if node is None:
            self.report({'WARNING'}, 'Select a File Output node')
            return {'CANCELLED'}
        migrate_legacy(node)
        entries = [entry for entry in node.blend_artwork_exports if entry.enabled]
        if not entries:
            self.report({'WARNING'}, 'No additional export destinations enabled')
            return {'CANCELLED'}
        try:
            _, _, rows = _status_probe_data(context)
            if not rows:
                self.report({'ERROR'}, 'No connected File Output sockets')
                return {'CANCELLED'}

            # Audit the exact same connected artwork list used by the exporter.
            # A .ref/.reference artwork layer is deliberately hidden and may
            # live at the PSD root. Do not report that as a grouping failure.
            def intentional_reference(row):
                label = row.get('socket', '').casefold()
                return label.endswith(('.ref', '.reference', '__ref', '__reference'))

            references = [r for r in rows
                          if not r.get('assigned_collection') and intentional_reference(r)]
            unresolved = [r for r in rows
                          if not r.get('assigned_collection') and not intentional_reference(r)]
            verified = sum(bool(r.get('assigned_collection')) for r in rows)
            grouping = any(x.use_groups and not x.flatten and x.format in LAYER_CAPABLE
                           for x in entries)
            status_rows = []
            for r in unresolved:
                source_names = [f"{s['scene']}/{s['view_layer']}"
                                for s in r.get('render_sources', [])]
                status_rows.append({
                    'name': r['socket'],
                    'reason': r.get('reason', ''),
                    'source': ', '.join(source_names) if source_names else '(not traced)',
                    'detail': r.get('status_detail', ''),
                })

            scene = context.scene
            scene.blend_psd_check_node = node.name
            scene.blend_psd_check_rows = json.dumps(status_rows, ensure_ascii=False)
            scene.blend_psd_check_count = len(unresolved)
            scene.blend_psd_check_summary = (
                f'{verified}/{len(rows)} grouped, {len(references)} reference, {len(unresolved)} unresolved'
                if grouping else
                f'{verified}/{len(rows)} source Collections identified (Use Groups off)'
            )

            # Same Check Export Status handles tag compatibility. No separate probe.
            tag_notes = []
            for output in entries:
                if output.flatten:
                    continue  # Flattened output has no per-layer names to translate.
                profile = _tag_registry.effective_profile(output.tag_profile, output.format)
                for row in rows:
                    raw_name = row.get('socket', '')
                    try:
                        translated, warnings = _tag_registry.preview(raw_name, output.tag_profile, output.format)
                    except Exception as exc:
                        translated, warnings = raw_name, [f'Tag XML unavailable; writer uses legacy naming: {exc}']
                    if translated != raw_name and (raw_name.startswith('[') or '[' in raw_name or
                                                   '.ref' in raw_name.lower() or '.merge' in raw_name.lower()):
                        tag_notes.append(f'{output.format}/{profile}: {raw_name} -> {translated}')
                    for warning in warnings:
                        tag_notes.append(f'{output.format}/{profile} {raw_name}: {warning}')
                    # Group tags are authored on Collections as well as sockets.
                    collection_path = row.get('assigned_collection') or ''
                    for group_component in collection_path.split('/'):
                        if not group_component:
                            continue
                        try:
                            _, group_warnings = _tag_registry.preview(group_component, output.tag_profile,
                                                                     output.format, scope='group')
                        except Exception as exc:
                            group_warnings = [f'Tag XML unavailable; legacy fallback: {exc}']
                        for warning in group_warnings:
                            tag_notes.append(f'{output.format}/{profile} group {group_component}: {warning}')
                if output.format == 'OCA' and profile not in ('OCA', 'PASSTHROUGH'):
                    tag_notes.append('Native OCA uses metadata, not PSD name tags; select OCA for OCA-specific behaviour')
            # De-duplicate repeated Collection warnings; keep all in collapsed status.
            tag_notes = list(dict.fromkeys(tag_notes))
            scene.blend_psd_tag_report = json.dumps(tag_notes, ensure_ascii=False)
            errors = []
            for entry in entries:
                try:
                    if entry.format not in SUPPORTED_NOW:
                        errors.append(f'{entry.format}: no export writer')
                    elif entry.depth not in ALLOWED_DEPTHS.get(entry.format, ()):
                        errors.append(f'{entry.format}: unsupported bit depth {entry.depth}')
                    else:
                        actual_path(entry, entry.format, node)
                except Exception as exc:
                    errors.append(f'{entry.format}: {exc}')
            dep_issue = missing()
            if dep_issue:
                errors.append(f'Export dependency: {dep_issue}')

            print(f'{LOG_PREFIX} CHECK EXPORT STATUS')
            print('  Destinations:', len(entries), 'errors:', len(errors))
            print('  Collection status:', scene.blend_psd_check_summary)
            print('  Tag compatibility diagnostics:', len(tag_notes))
            for note in tag_notes:
                print('  TAG:', note)
            for row in status_rows:
                print(f"  UNGROUPED: {row['name']} | source: {row['source']} "
                      f"| {row['detail'] or row['reason']}")
            if errors:
                scene.blend_psd_check_summary += f' | {len(errors)} export problem(s)'
                for error in errors:
                    print('  EXPORT ERROR:', error)
                self.report({'ERROR'}, '; '.join(errors)[:240])
                return {'FINISHED'}
            if unresolved and grouping:
                self.report({'WARNING'}, f'{len(unresolved)} of {len(rows)} artwork outputs lack verified groups - see list below')
            else:
                self.report({'INFO'}, f'{len(entries)} destinations ready; {len(rows)} artwork outputs checked')
            return {'FINISHED'}
        except Exception as exc:
            traceback.print_exc()
            self.report({'ERROR'}, 'Check Export Status failed: ' + str(exc)[:170])
            return {'CANCELLED'}


def _draw_diagnostics(layout, context, node):
    scene = context.scene
    layout.prop(node, 'blend_psd_show_diagnostics', text='Diagnostics', emboss=False,
                icon='TRIA_DOWN' if node.blend_psd_show_diagnostics else 'TRIA_RIGHT')
    if not node.blend_psd_show_diagnostics:
        return
    import textwrap
    width = max(24, int(getattr(getattr(context, 'region', None), 'width', 460) / 7) - 8)
    def message(box, text):
        for index, line in enumerate(textwrap.wrap(str(text), width)):
            box.label(text=line, icon='INFO' if index == 0 else 'NONE')
    def saved(value, default):
        try:
            result = json.loads(value)
            return result if isinstance(result, type(default)) else default
        except (ValueError, TypeError):return default
    sync = saved(node.get('_compio_view_layer_sync_report', '{}'), {})
    if sync:
        box = layout.box();box.label(text='Input Sync')
        box.label(text=f'Inputs: {len(sync.get("added", []))} added, {len(sync.get("renamed", []))} renamed, {len(sync.get("removed", []))} removed')
        for text in sync.get('warnings', []):message(box, text)
    notices = saved(scene.blend_psd_export_notices, [])
    if notices:
        box = layout.box();box.label(text='Export Notices')
        for text in notices:message(box, text)
    timings = saved(scene.blend_psd_export_timings, {})
    if timings:
        box = layout.box();box.label(text='Performance')
        render = timings.get('render_performance', {})
        if render:
            message(box, f'Preparation: {render.get("preparation_seconds", 0):.2f}s; render and cache: {render.get("render_and_cache_seconds", 0):.2f}s')
        for row in timings.get('details', []):
            perf = row.get('performance', {})
            if perf:
                message(box, f'{Path(row.get("dest", "Output")).name}: {perf.get("total_seconds", 0):.2f}s')
    if scene.blend_psd_check_node == node.name and scene.blend_psd_check_summary:
        box = layout.box();box.label(text='Collections')
        message(box, scene.blend_psd_check_summary)
        for entry in saved(scene.blend_psd_check_rows, []):
            message(box, entry.get('name', '(unnamed)') + ': ' + (entry.get('detail') or entry.get('reason') or ''))
        notes = saved(scene.blend_psd_tag_report, [])
        for note in notes:message(box, note)
        if not notes:box.label(text='Tag compatibility: no unconvertible directives detected', icon='CHECKMARK')


class PanelNode(Panel):
    bl_label = BRAND_NAME + ' - Additional Exports'
    bl_idname = 'BLENDPSD_PT_ADDITIONAL_OUTPUTS'
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Node'

    @classmethod
    def poll(cls, context):
        return target(context) is not None

    def draw(self, context):
        layout = self.layout
        node = target(context)
        outputs = node.blend_artwork_exports
        layout.operator('blend_psd.sync_view_layers', text='Update Inputs to ViewLayers', icon='FILE_REFRESH')
        layout.prop(context.scene, 'blend_psd_chime_volume', text='Completion Chime Volume', slider=True)
        row = layout.row(align=True)
        row.label(text='Additional Outputs')
        row.operator('blend_psd.add_export', text='', icon='ADD')
        if not outputs:
            layout.label(text='Use + to add an output destination', icon='INFO')
        for idx, item in enumerate(outputs):
            box = layout.box()
            row = box.row(align=True)
            row.prop(item, 'expanded', text='', emboss=False,
                     icon='TRIA_DOWN' if item.expanded else 'TRIA_RIGHT')
            row.prop(item, 'enabled', text='')
            row.label(text=f'{idx + 1}. {item.format}')
            op = row.operator('blend_psd.remove_export', text='', icon='X')
            op.index = idx
            if not item.enabled or not item.expanded:
                continue  # closed/disabled entries consume one line
            sub = box.column(align=True)
            sub.prop(item, 'path', text='Directory')
            sub.prop(item, 'use_custom_name', text='Custom Name')
            if item.use_custom_name:
                sub.prop(item, 'custom_name', text='File Name')
            formatbox = sub.box()
            formatbox.label(text='Node Format')
            formatbox.prop(item, 'format', text='File Format')
            if item.format != 'FONTS':
                row = formatbox.row(align=True)
                row.prop(item, 'depth', text='Color Depth')
                formatbox.prop(item, 'flatten', text='Flatten Image')
            if item.format == 'FONTS':
                formatbox.label(text='Copies font files into a companion .fonts folder', icon='FONT_DATA')
                formatbox.prop(item,'use_font_directory')
                fonts = formatbox.row()
                fonts.enabled = item.use_font_directory
                fonts.prop(item,'font_directory')
            if item.format == 'FONTS':
                continue
            if item.format == 'SVG':
                bake_row = formatbox.row(align=True)
                bake_row.enabled = not item.flatten
                bake_row.prop(item, 'bake_svg_png', text='Rasterise Vector Artwork')
                text_row = formatbox.row()
                text_row.enabled = not item.flatten and not item.bake_svg_png
                text_row.prop(item, 'svg_flat_text_material')
                formatbox.prop(item, 'svg_root_mode', text='Root Group')
                if item.svg_root_mode == 'NAMED':
                    formatbox.prop(item, 'svg_root_name', text='Root Name')
            if item.format == 'OCA':
                controls = formatbox.box()
                controls.prop(item,'oca_layout')
                for prop in ('oca_ignore_hidden_layers', 'oca_ignore_background', 'trim_empty_pixels',
                             'oca_write_json', 'oca_write_template', 'oca_scale', 'oca_padding'):
                    controls.prop(item, prop)
                controls.prop(item, 'bake_svg_png', text='Rasterise Vector Layers')
                controls.prop(item, 'oca_keep_png')
                if item.depth=='32':controls.prop(item,'oca_half_float')
            if item.format in ('PSD', 'PSB'):
                formatbox.prop(item, 'psd_compression')
                raster_row=formatbox.row();raster_row.enabled=not item.flatten
                raster_row.prop(item,'bake_svg_png',text='Rasterise Vector Artwork')
                formatbox.prop(item,'svg_flat_text_material')
            tagrow = formatbox.row(align=True)
            tagrow.enabled = not item.flatten
            tagrow.prop(item, 'tag_profile', text='Tag Compatibility')
            if item.flatten:
                tagrow.label(text='', icon='LOCKED')
            group = formatbox.row(align=True)
            group.enabled = (not item.flatten and item.format in LAYER_CAPABLE)
            group.prop(item, 'use_groups', text='Use Groups')
            cm = formatbox.row(align=True)
            cm.enabled = item.format != 'EXR'
            cm.prop(item, 'save_as_render', text='Save as Render')
            if item.depth not in ALLOWED_DEPTHS.get(item.format, ()):
                sub.label(text='Unsupported depth for this format', icon='ERROR')
            if item.format in ('PSD', 'PSB') and item.depth == '32':
                sub.label(text='Experimental: 32-bit float PSD/PSB; validate round-trip', icon='INFO')
        if outputs:
            row = layout.row(align=True)
            row.prop(context.scene, 'blend_psd_show_paths', text='',
                     icon='TRIA_DOWN' if context.scene.blend_psd_show_paths else 'TRIA_RIGHT', emboss=False)
            row.label(text='Additional Output Paths')
            if context.scene.blend_psd_show_paths:
                panel = layout.box()
                for item in outputs:
                    if item.enabled:
                        try:
                            path = str(actual_path(item, item.format, node))
                            if not item.flatten and item.format in ('PNG', 'EXR', 'TIFF', 'JPEG'):
                                pairs = connected(context.space_data.edit_tree, node)
                                # List the same individual filenames as the
                                # still-image worker; no view-layer-wide helper.
                                # Each connected File Output socket is a file
                                # when Flatten Image is disabled.
                                mapped = _map_layers(node, [n for n, _ in pairs], (),
                                                     tree=context.space_data.edit_tree,
                                                     pairs=pairs, scene=context.scene)
                                pseudo = [(dict(name=n, collection_path=mapped[i]), None)
                                          for i, (n, _) in enumerate(pairs)]
                                images = prepared_entries(pseudo, False)
                                for entrypath in _unique_still_paths(Path(path), [x['entry']['name'] for x in images],
                                                                    profile=item.tag_profile, fmt=item.format):
                                    panel.label(text=str(entrypath), icon='IMAGE_DATA')
                            elif item.format == 'FONTS':
                                panel.label(text='Font files: ' + str(Path(path).with_suffix('')), icon='FILE_FOLDER')
                                panel.label(text='Font index: ' + path, icon='FILE')
                            else:
                                panel.label(text=path, icon='FILE')
                            if item.format == 'OCA' and not item.flatten:
                                panel.label(text='Assets folder: ' + str(Path(path).with_suffix('')), icon='FILE_FOLDER')
                        except Exception as exc:
                            print(f'{LOG_PREFIX} Path preview error:', traceback.format_exc())
                            panel.label(text='Output paths unavailable: ' + str(exc)[:75], icon='ERROR')
        layout.separator()
        err = missing() if any(item.enabled and item.format in SUPPORTED_NOW for item in outputs) else ''
        if err:
            layout.label(text='Export dependency missing: ' + err[:70], icon='ERROR')
        elif any(item.enabled and item.format in SUPPORTED_NOW for item in outputs):
            layout.label(text='Layered export backend ready', icon='CHECKMARK')
        layout.label(text=context.scene.blend_psd_status, icon='INFO')
        scene = context.scene
        _draw_diagnostics(layout, context, node)
        layout.operator('blend_psd.check', text='Check Export Status', icon='INFO')
        row = layout.row(align=True)
        row.prop(context.scene, 'blend_psd_show_backend', text='',
                 icon='TRIA_DOWN' if context.scene.blend_psd_show_backend else 'TRIA_RIGHT', emboss=False)
        row.label(text='Backend / Recovery')
        if context.scene.blend_psd_show_backend:
            row = layout.row(align=True)
            row.prop(context.scene, 'blend_psd_show_recovery', text='',
                 icon='TRIA_DOWN' if context.scene.blend_psd_show_recovery else 'TRIA_RIGHT', emboss=False)
            row.label(text='Recover / Retry', icon='FILE_REFRESH')
        if context.scene.blend_psd_show_backend and context.scene.blend_psd_show_recovery:
            recover = layout.box()
            recover.prop(context.scene, 'blend_psd_retry_folder', text='Job Folder')
            recover.operator('blend_psd.retry_job', text='Retry Export (No Render)', icon='FILE_REFRESH')
            clear_row = recover.row(align=True)
            clear_row.operator('blend_psd.clear_job_cache', text='Clear Cache', icon='TRASH')
            clear_row.prop(context.scene, 'blend_psd_cache_clear_all', text='Clear all')


class OT_open_documentation(Operator):
    bl_idname = 'blend_psd.open_documentation'
    bl_label = 'Open Documentation'
    bl_description = 'Open the complete offline HTML manual in your web browser'

    def execute(self, context):
        manual = ROOT / 'manual' / 'MANUAL.html'
        if not manual.is_file():
            self.report({'ERROR'}, BRAND_NAME + ' manual missing: reinstall the complete add-on ZIP')
            return {'CANCELLED'}
        uri = manual.resolve().as_uri()
        # webbrowser uses the platform browser (not the registered Markdown editor).
        # Keep the fallback within Blender's URL-opening operator, not path_open.
        import webbrowser
        try:
            opened = webbrowser.open_new_tab(uri)
            if not opened:
                bpy.ops.wm.url_open(url=uri)
        except Exception as exc:
            try:
                bpy.ops.wm.url_open(url=uri)
            except Exception:
                self.report({'ERROR'}, 'Cannot open browser for manual: ' + str(exc)[:140])
                return {'CANCELLED'}
        return {'FINISHED'}


class ImageNodePlusPreferences(AddonPreferences):
    bl_idname = __package__ or 'blend_psd_tools'

    def draw(self, context):
        column = self.layout.column(align=True)
        column.operator('blend_psd.open_documentation', text='Open ' + BRAND_NAME + ' User Manual', icon='HELP')


CLASSES = (Settings, AdditionalExport, OT_sync_view_layers, OT_add, OT_remove, OT_retry, OT_clear_job_cache, OT_check,
           OT_open_documentation, ImageNodePlusPreferences, PanelNode)


def register():
    from .package_compat import disable_legacy
    disable_legacy(__package__)
    from .conversion_policy import capabilities
    from . import oca_authoring
    oca_authoring.register()
    capabilities.cache_clear()
    for cl in CLASSES:
        bpy.utils.register_class(cl)
    bpy.types.Node.blend_psd_settings = PointerProperty(type=Settings)
    bpy.types.Node.blend_artwork_exports = CollectionProperty(type=AdditionalExport)
    bpy.types.Node.blend_artwork_index = IntProperty(default=0)
    bpy.types.Node.blend_psd_show_diagnostics = BoolProperty(name='Diagnostics', default=False)
    bpy.types.Scene.blend_psd_export_timings = StringProperty(default='{}')
    bpy.types.Node.blend_psd_show_sync_details = BoolProperty(name='Input Sync Details', default=False,
        description='Show the latest input sync report; diagnostic details are hidden by default')
    bpy.types.Scene.blend_psd_retry_folder = StringProperty(name='Retained PSD Job Folder', subtype='DIR_PATH', default='')
    bpy.types.Scene.blend_psd_cache_clear_all = BoolProperty(
        name='Clear all', default=False,
        description='Also remove the selected current job. Active exports are always protected')
    bpy.types.Scene.blend_psd_status = StringProperty(name='Last Export', default='No export completed yet')
    bpy.types.Scene.blend_psd_export_notices = StringProperty(default='[]')
    bpy.types.Scene.blend_psd_show_export_details = BoolProperty(default=False)
    bpy.types.Scene.blend_psd_check_node = StringProperty(default='')
    bpy.types.Scene.blend_psd_check_summary = StringProperty(default='')
    bpy.types.Scene.blend_psd_check_count = IntProperty(default=0)
    bpy.types.Scene.blend_psd_check_rows = StringProperty(default='')
    bpy.types.Scene.blend_psd_tag_report = StringProperty(default='[]')
    bpy.types.Scene.blend_psd_show_paths = BoolProperty(default=True)
    bpy.types.Scene.blend_psd_show_check_details = BoolProperty(default=False)
    bpy.types.Scene.blend_psd_show_recovery = BoolProperty(default=False)
    bpy.types.Scene.blend_psd_show_backend = BoolProperty(default=False)
    bpy.types.Scene.blend_psd_chime_enabled = BoolProperty(name='Play completion chime', default=True,
        get=_legacy_chime_get, set=_legacy_chime_set, options={'HIDDEN'},
        description='Legacy chime switch retained for older saved projects and scripts')
    bpy.types.Scene.blend_psd_chime_volume = FloatProperty(name='Completion Chime Volume',
        default=1.0, min=0.0, max=1.0, precision=2, step=1,
        get=_chime_volume_get, set=_chime_volume_set,
        description='Linear chime volume: 0 is off and skips sound loading; 1 is the original level')
    for handlers, fn in (
        (bpy.app.handlers.render_init, begin_oca_render),
        (bpy.app.handlers.render_pre, before_render),
        (bpy.app.handlers.render_post, capture_oca_frame),
        (bpy.app.handlers.render_complete, after_render),
        (bpy.app.handlers.render_cancel, cancel_render),
        (bpy.app.handlers.load_post, after_load),
    ):
        # Blender can keep persistent handlers from an earlier installed ZIP.
        # Remove previous package functions with the same role, even if they
        # are different Python function objects after an in-process reload.
        for old in list(handlers):
            if (getattr(old, '__module__', '') == __name__ and
                    getattr(old, '__name__', '') == fn.__name__ and old is not fn):
                handlers.remove(old)
                print(f'{LOG_PREFIX} Replaced stale render handler:', fn.__name__)
        if fn not in handlers:
            handlers.append(fn)
    # Deferred: register() runs inside Blender's restricted data context.
    # In particular, bpy.data.node_groups is inaccessible here on 5.3 Beta.
    global _MIGRATION_ATTEMPTS
    _MIGRATION_ATTEMPTS = 0
    if not bpy.app.timers.is_registered(_migrate_after_registration):
        bpy.app.timers.register(_migrate_after_registration, first_interval=0.5)


def unregister():
    from . import oca_authoring
    oca_authoring.unregister()
    _stop_chime()
    if bpy.app.timers.is_registered(_migrate_after_registration):
        bpy.app.timers.unregister(_migrate_after_registration)
    for handlers, fn in (
        (bpy.app.handlers.render_init, begin_oca_render),
        (bpy.app.handlers.render_pre, before_render),
        (bpy.app.handlers.render_post, capture_oca_frame),
        (bpy.app.handlers.render_complete, after_render),
        (bpy.app.handlers.render_cancel, cancel_render),
        (bpy.app.handlers.load_post, after_load),
    ):
        for old in list(handlers):
            if old is fn or (getattr(old, '__module__', '') == __name__ and
                            getattr(old, '__name__', '') == fn.__name__):
                handlers.remove(old)
    for sess in list(SESSIONS.values()):
        for name in sess['temps']:
            try:
                node = sess['tree'].nodes.get(name)
                if node:
                    sess['tree'].nodes.remove(node)
            except Exception:
                pass
    SESSIONS.clear()
    MONITORS.clear()
    for owner, prop in (
        (bpy.types.Node, 'blend_psd_settings'),
        (bpy.types.Node, 'blend_artwork_exports'),
        (bpy.types.Node, 'blend_artwork_index'),
        (bpy.types.Node, 'blend_psd_show_diagnostics'),
        (bpy.types.Scene, 'blend_psd_export_timings'),
        (bpy.types.Node, 'blend_psd_show_sync_details'),
        (bpy.types.Scene, 'blend_psd_retry_folder'),
        (bpy.types.Scene, 'blend_psd_cache_clear_all'),
        (bpy.types.Scene, 'blend_psd_status'),
        (bpy.types.Scene, 'blend_psd_export_notices'),
        (bpy.types.Scene, 'blend_psd_show_export_details'),
        (bpy.types.Scene, 'blend_psd_check_node'),
        (bpy.types.Scene, 'blend_psd_check_summary'),
        (bpy.types.Scene, 'blend_psd_check_count'),
        (bpy.types.Scene, 'blend_psd_check_rows'),
        (bpy.types.Scene, 'blend_psd_tag_report'),
        (bpy.types.Scene, 'blend_psd_show_paths'),
        (bpy.types.Scene, 'blend_psd_show_check_details'),
        (bpy.types.Scene, 'blend_psd_show_recovery'),
        (bpy.types.Scene, 'blend_psd_show_backend'),
        (bpy.types.Scene, 'blend_psd_chime_enabled'),
        (bpy.types.Scene, 'blend_psd_chime_volume'),
    ):
        if hasattr(owner, prop):
            delattr(owner, prop)
    for cl in reversed(CLASSES):
        bpy.utils.unregister_class(cl)
