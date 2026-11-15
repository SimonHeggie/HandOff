"""Read-only scene and compositor evidence for layered-export attribution.

This module deliberately never creates passes, edits shaders, or modifies render
settings. Output-socket names are NOT treated as proof of mesh ownership.
"""

import datetime
import re

PROBE_API_VERSION = 2


def _text(value):
    try:
        return str(value)
    except Exception:
        return '<unavailable>'


def _objects_in_collection(collection):
    try:
        return list(collection.objects)
    except Exception:
        return []


def _object_record(obj):
    materials = []
    try:
        for slot in obj.material_slots:
            if slot.material is not None:
                materials.append(slot.material.name)
    except Exception:
        pass
    try:
        memberships = [c.name for c in obj.users_collection]
    except Exception:
        memberships = []
    return {
        'name': obj.name,
        'type': getattr(obj, 'type', None),
        'data_name': getattr(getattr(obj, 'data', None), 'name', None),
        'parent_object': getattr(getattr(obj, 'parent', None), 'name', None),
        'collections': sorted(memberships),
        'materials': materials,
        'hide_render': bool(getattr(obj, 'hide_render', False)),
        'visible_camera': bool(getattr(obj, 'visible_camera', True)),
        'visible_diffuse': bool(getattr(obj, 'visible_diffuse', True)),
        'visible_glossy': bool(getattr(obj, 'visible_glossy', True)),
        'visible_transmission': bool(getattr(obj, 'visible_transmission', True)),
        'visible_shadow': bool(getattr(obj, 'visible_shadow', True)),
    }


def view_layer_details(scene, view_layer):
    rows = []
    geom = {}

    def walk(lc, path, excluded_parent=False, indirect_parent=False, holdout_parent=False):
        collection = lc.collection
        is_master = lc == view_layer.layer_collection
        here = path if is_master else path + (collection.name,)
        excluded = bool(excluded_parent or getattr(lc, 'exclude', False) or
                        getattr(collection, 'hide_render', False))
        indirect = bool(indirect_parent or getattr(lc, 'indirect_only', False))
        holdout = bool(holdout_parent or getattr(lc, 'holdout', False))
        if not is_master:
            directly = _objects_in_collection(collection)
            for obj in directly:
                if obj.name not in geom:
                    geom[obj.name] = _object_record(obj)
            rows.append({
                'path': '/'.join(here),
                'name': collection.name,
                'direct_objects': [o.name for o in directly],
                'exclude_effective': excluded,
                'exclude_local': bool(getattr(lc, 'exclude', False)),
                'holdout_effective': holdout,
                'indirect_only_effective': indirect,
                'hide_render': bool(getattr(collection, 'hide_render', False)),
                'hide_viewport': bool(getattr(lc, 'hide_viewport', False)),
            })
        for child in lc.children:
            walk(child, here, excluded, indirect, holdout)

    walk(view_layer.layer_collection, ())
    aovs = []
    try:
        aovs = [{'name': item.name, 'type': str(item.type)} for item in view_layer.aovs]
    except Exception:
        pass
    crypto = {}
    for owner in (view_layer, getattr(view_layer, 'cycles', None)):
        if owner is None:
            continue
        for name in ('use_pass_crypto_object', 'use_pass_crypto_material', 'use_pass_crypto_asset',
                     'pass_crypto_depth', 'use_pass_ambient_occlusion', 'use_pass_z',
                     'use_pass_normal', 'use_pass_diffuse_color'):
            try:
                crypto[name] = getattr(owner, name)
            except Exception:
                continue
    return {'name': view_layer.name, 'collections': rows,
            'objects': list(geom.values()), 'aovs': aovs, 'pass_flags': crypto}


def material_evidence(view_layer_details_list):
    # A view-layer summary contains material assignments, allowing correlation
    # with an upstream AOV name without assuming every material actually writes
    # that AOV or contributes visible pixels.
    mats = {}
    for layer in view_layer_details_list:
        for obj in layer.get('objects', []):
            for mat in obj.get('materials', []):
                mats.setdefault(mat, set()).add(obj['name'])
    return [{'material': mat, 'objects': sorted(names)} for mat, names in sorted(mats.items())]


def scan_material_nodes(scene):
    """Collect relevant shader evidence, including nested shader node groups."""
    records = []
    found_materials = set()

    def inspect_tree(tree, ancestry=(), visited=None, depth=0):
        if tree is None or depth > 8:
            return []
        visited = set() if visited is None else set(visited)
        identity = id(tree)
        if identity in visited:
            return []
        visited.add(identity)
        interesting = []
        for n in getattr(tree, 'nodes', []):
            kind = getattr(n, 'bl_idname', '')
            if (kind in ('ShaderNodeOutputAOV', 'ShaderNodeAttribute', 'ShaderNodeLightPath',
                         'ShaderNodeEmission', 'ShaderNodeBsdfTransparent', 'ShaderNodeMixShader')
                    or 'AOV' in kind):
                row = {'name': n.name, 'type': kind,
                       'node_group_path': '/'.join(ancestry)}
                for attr in ('aov_name', 'attribute_name', 'attribute_type'):
                    if hasattr(n, attr):
                        try:
                            row[attr] = _text(getattr(n, attr))
                        except Exception:
                            pass
                interesting.append(row)
            if kind == 'ShaderNodeGroup' and getattr(n, 'node_tree', None):
                interesting.extend(inspect_tree(n.node_tree, ancestry + (n.name,), visited, depth+1))
        return interesting

    for obj in scene.objects:
        for slot in getattr(obj, 'material_slots', []):
            mat = getattr(slot, 'material', None)
            if mat is None or mat.name in found_materials:
                continue
            found_materials.add(mat.name)
            interesting = inspect_tree(getattr(mat, 'node_tree', None))
            if interesting:
                records.append({'material': mat.name, 'nodes': interesting})
    return records


def _linked_from(tree, input_socket):
    try:
        return next((lk.from_socket for lk in tree.links
                     if lk.to_socket == input_socket and getattr(lk, 'is_valid', True)), None)
    except Exception:
        return None


def node_trace(tree, socket, limit=110):
    """Return a bounded nested compositor chain, with socket-level details."""
    nodes = []
    seen = set()

    def trace(cur_tree, out, parents=(), depth=0):
        if out is None or depth > 65 or len(nodes) >= limit:
            return
        owner = getattr(out, 'node', None)
        if owner is None:
            return
        key = (id(cur_tree), id(owner), getattr(out, 'identifier', out.name),
               tuple(id(p[1]) for p in parents))
        if key in seen:
            return
        seen.add(key)
        kind = owner.bl_idname
        row = {'tree': cur_tree.name, 'node': owner.name,
               'type': kind, 'output': out.name, 'depth': depth,
               'linked_inputs': [i.name for i in owner.inputs if getattr(i, 'is_linked', False)]}
        if kind == 'CompositorNodeRLayers':
            row['scene'] = getattr(getattr(owner, 'scene', None), 'name', None)
            row['view_layer'] = getattr(owner, 'layer', None)
        if kind == 'CompositorNodeValue':
            try:
                row['value'] = float(owner.outputs[0].default_value)
            except Exception:
                pass
        nodes.append(row)
        if kind == 'CompositorNodeGroup' and getattr(owner, 'node_tree', None):
            inner = owner.node_tree
            group_outs = [n for n in inner.nodes if n.bl_idname == 'NodeGroupOutput']
            group_out = next((n for n in group_outs if getattr(n, 'is_active_output', False)),
                             group_outs[0] if group_outs else None)
            index = next((i for i, s in enumerate(owner.outputs) if s == out), -1)
            if group_out is not None and 0 <= index < len(group_out.inputs):
                trace(inner, _linked_from(inner, group_out.inputs[index]),
                      parents + ((cur_tree, owner),), depth+1)
        elif kind == 'NodeGroupInput' and parents:
            parent_tree, parent_node = parents[-1]
            index = next((i for i, s in enumerate(owner.outputs) if s == out), -1)
            if 0 <= index < len(parent_node.inputs):
                trace(parent_tree, _linked_from(parent_tree, parent_node.inputs[index]),
                      parents[:-1], depth+1)
        elif kind != 'CompositorNodeRLayers':
            for inp in owner.inputs:
                if getattr(inp, 'is_linked', False):
                    trace(cur_tree, _linked_from(cur_tree, inp), parents, depth+1)
    trace(tree, socket)
    return {'nodes': nodes, 'truncated': len(nodes) >= limit}


def analyze_outputs(scene, node, tree, provenance, with_trace=False):
    rows = []
    for slot in node.inputs:
        if not getattr(slot, 'is_linked', False):
            continue
        upstream_socket = _linked_from(tree, slot)
        row = {'socket': slot.name, 'socket_identifier': getattr(slot, 'identifier', ''),
               'upstream_socket': getattr(upstream_socket, 'name', None),
               'upstream_node': getattr(getattr(upstream_socket, 'node', None), 'name', None),
               'upstream_node_type': getattr(getattr(upstream_socket, 'node', None), 'bl_idname', None)}
        try:
            owner, sources, reason = provenance.infer_from_socket(tree, upstream_socket, default_scene=scene)
            row['assigned_collection'] = owner or None
            row['reason'] = reason
            row['render_sources'] = [{'scene': s.name, 'view_layer': layer} for s, layer in sources]
            if not owner:
                candidates = []
                for s, layer in sources:
                    view = s.view_layers.get(layer)
                    if view:
                        evidence = provenance.view_layer_evidence(view)
                        candidates.append({'scene': s.name, 'view_layer': layer,
                                           'camera_objects': evidence.get('total_camera_objects', 0),
                                           'collections': evidence.get('candidates', [])})
                row['candidate_collections'] = candidates
        except Exception as exc:
            row['assigned_collection'] = None
            row['reason'] = 'provenance analysis failed: ' + repr(exc)
            row['render_sources'] = []
        if with_trace:
            row['compositor_trace'] = node_trace(tree, upstream_socket)
        rows.append(row)
    return rows


def complete_probe(scene, node, tree, provenance, blender_version='unknown'):
    all_views = [view_layer_details(scene, vl) for vl in scene.view_layers]
    outputs = analyze_outputs(scene, node, tree, provenance, with_trace=True)
    return {
        'probe_version': 1,
        'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'blender_version': blender_version,
        'scene': scene.name,
        'file_output_node': node.name,
        'node_tree': tree.name,
        'method_note': ('Render Layers and Collection membership are source evidence, not proof '
                        'of pixel ownership when shader camera-ray switches, AOVs, masks or mixed '
                        'compositor branches are used. No scene changes made.'),
        'summary': {'output_count': len(outputs),
                    'unresolved_count': sum(not x.get('assigned_collection') for x in outputs),
                    'unresolved_sockets': [x['socket'] for x in outputs if not x.get('assigned_collection')]},
        'outputs': outputs,
        'view_layers': all_views,
        'materials': material_evidence(all_views),
        'material_shader_nodes': scan_material_nodes(scene),
    }


def attribution_status_detail(row, scene=None):
    """Readable, qualified grouping evidence for Check Export Status.

    This is *not* pixel attribution. Indirect-only objects are not counted as
    directly camera-visible by the exporter, even though their Collection
    memberships can still be examined in the scene. No image/render changes.
    """
    if row.get('assigned_collection'):
        return 'Verified: ' + str(row['assigned_collection'])
    if str(row.get('reason', '')).startswith('shader mask found'):
        return str(row['reason'])
    sources = row.get('render_sources', [])
    if not sources:
        return 'Compositor source unresolved; check upstream connections'
    if len(sources) > 1:
        return f'{len(sources)} Render Layers contribute; no single owner'
    src = sources[0]
    layer_name = src.get('view_layer', '?')
    if scene is None or src.get('scene') != scene.name:
        return 'View Layer ' + layer_name + ': source scene not available'
    view_layer = scene.view_layers.get(layer_name)
    if view_layer is None:
        return 'View Layer ' + layer_name + ': no longer exists'
    try:
        details = view_layer_details(scene, view_layer)
        objects = {o['name']: o for o in details['objects']}
        geometric_types = {'MESH', 'CURVE', 'CURVES', 'SURFACE', 'FONT',
                           'META', 'VOLUME', 'POINTCLOUD', 'GREASEPENCIL', 'GPENCIL'}
        direct = set()
        indirect = set()
        holdout = set()
        indirect_collections = set()
        for coll in details['collections']:
            if coll.get('exclude_effective') or coll.get('hide_render'):
                continue
            filtered = {name for name in coll.get('direct_objects', [])
                        if name in objects
                        and objects[name].get('type') in geometric_types
                        and not objects[name].get('hide_render')
                        and objects[name].get('visible_camera')}
            if not filtered:
                continue
            if coll.get('indirect_only_effective'):
                indirect.update(filtered)
                indirect_collections.add(coll['path'])
            elif coll.get('holdout_effective'):
                holdout.update(filtered)
            else:
                direct.update(filtered)
        if not direct and indirect:
            return (f'{layer_name}: 0 direct camera objects; '
                    f'{len(indirect_collections)} Indirect Only branches')
        if direct and indirect:
            return (f'{layer_name}: {len(direct)} direct / {len(indirect)} '
                    f'indirect-only objects; mixed candidates')
        if direct:
            return f'{layer_name}: {len(direct)} direct objects in several Collections'
        if holdout:
            return f'{layer_name}: Holdout geometry; no unique direct owner'
        return f'{layer_name}: no direct camera geometry; shader/AOV masks may contribute'
    except Exception as exc:
        return f'{layer_name}: evidence unavailable ({type(exc).__name__})'
