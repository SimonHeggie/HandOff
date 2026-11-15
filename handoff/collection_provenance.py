"""Determine collection provenance from compositor Render Layers nodes.

This is deliberately conservative: if the graph mixes multiple view layers or
its render layer contains multiple unrelated camera-visible branches, there is
no honest way to infer the collection of an arbitrary shader-masked image.
The native File Output stack remains authoritative for final artwork order.
"""

PROVENANCE_API_VERSION = 8

GEOMETRY_TYPES = frozenset({
    'MESH', 'CURVE', 'CURVES', 'SURFACE', 'FONT', 'META',
    'VOLUME', 'POINTCLOUD', 'GREASEPENCIL', 'GPENCIL',
})


def _socket_index(sockets, socket):
    for i, candidate in enumerate(sockets):
        if candidate == socket:
            return i
    identifier = getattr(socket, 'identifier', None)
    if identifier:
        for i, candidate in enumerate(sockets):
            if getattr(candidate, 'identifier', None) == identifier:
                return i
    return -1


def _from_link(tree, input_socket):
    for link in tree.links:
        if link.to_socket == input_socket and getattr(link, 'is_valid', True):
            return link.from_socket
    return None


def _owner(tree, output_socket):
    node = getattr(output_socket, 'node', None)
    if node is not None:
        return node
    for n in tree.nodes:
        if any(s == output_socket for s in n.outputs):
            return n
    return None


def _active_group_output(node_tree):
    candidates = [n for n in node_tree.nodes if n.bl_idname == 'NodeGroupOutput']
    return next((n for n in candidates if getattr(n, 'is_active_output', False)),
                candidates[0] if candidates else None)


def source_render_layers(tree, from_socket, default_scene=None):
    """Return set of (Scene, view-layer name) used upstream of one image output.

    Handles reroutes/regular nodes, nested CompositorNodeGroup inputs/outputs,
    and scenes whose compositor is already a custom node group.
    """
    found = {}
    visited = set()

    def follow_input(cur_tree, socket, parents, depth):
        if socket is not None:
            upstream = _from_link(cur_tree, socket)
            if upstream is not None:
                follow_output(cur_tree, upstream, parents, depth + 1)

    def follow_output(cur_tree, socket, parents, depth):
        if socket is None or depth > 120:
            return
        owner = _owner(cur_tree, socket)
        if owner is None:
            return
        key = (id(cur_tree), id(owner),
               _socket_index(owner.outputs, socket),
               tuple((id(t), id(n)) for t, n in parents))
        if key in visited:
            return
        visited.add(key)
        kind = owner.bl_idname
        if kind == 'CompositorNodeRLayers':
            render_scene = getattr(owner, 'scene', None) or default_scene
            layer_name = getattr(owner, 'layer', '')
            if render_scene is not None and layer_name:
                found[(render_scene.name, layer_name)] = (render_scene, layer_name)
            return
        if kind == 'CompositorNodeGroup' and getattr(owner, 'node_tree', None):
            inner_tree = owner.node_tree
            out_node = _active_group_output(inner_tree)
            index = _socket_index(owner.outputs, socket)
            if out_node is not None and 0 <= index < len(out_node.inputs):
                follow_input(inner_tree, out_node.inputs[index],
                             parents + ((cur_tree, owner),), depth + 1)
            return
        if kind == 'NodeGroupInput' and parents:
            parent_tree, group_node = parents[-1]
            index = _socket_index(owner.outputs, socket)
            if 0 <= index < len(group_node.inputs):
                follow_input(parent_tree, group_node.inputs[index], parents[:-1], depth + 1)
            return
        # A regular compositor operation can use several render sources.
        # Collect all, but only use attribution if the answer is unambiguous.
        for input_socket in owner.inputs:
            if getattr(input_socket, 'is_linked', False):
                follow_input(cur_tree, input_socket, parents, depth + 1)

    follow_output(tree, from_socket, (), 0)
    return list(found.values())


def collection_index(view_layer):
    """Return tree in the view-layer's order with direct and descendant objects.

    Render visibility, not viewport visibility, determines candidates. Object
    visible_camera is a coarse Cycles setting; shader Is Camera Ray / AOV
    masking is NOT represented by this property and cannot be inferred here.
    """
    if view_layer is None:
        return []
    result = []

    def effective_object_state(obj, flag):
        # Blender 5.3 exposes evaluated per-object, per-view-layer holdout and
        # indirect-only state. A mesh can be linked into both Rigging and Assets:
        # checking only one LayerCollection branch misclassifies that mesh.
        checker = getattr(obj, flag, None)
        if callable(checker):
            try:
                return bool(checker(view_layer=view_layer))
            except (TypeError, RuntimeError, ValueError):
                pass
        return None

    def walk(lc, parents, blocked=False, indirect=False, holdout=False):
        coll = lc.collection
        excluded = (blocked or bool(getattr(lc, 'exclude', False)) or
                    bool(getattr(coll, 'hide_render', False)))
        if excluded:
            # The caller always unpacks (camera_objects, descendant_objects).
            # Skipping an excluded/hidden collection must retain that shape.
            return [], []
        is_master = lc == view_layer.layer_collection
        path = parents if is_master else parents + (coll.name,)
        local_indirect = indirect or bool(getattr(lc, 'indirect_only', False))
        local_holdout = holdout or bool(getattr(lc, 'holdout', False))
        direct = list(coll.objects) if not is_master else []
        camera = []
        for obj in direct:
            if (getattr(obj, 'type', '') not in GEOMETRY_TYPES or
                    getattr(obj, 'hide_render', False) or
                    not getattr(obj, 'visible_camera', True)):
                continue
            # Use Blender's effective object state when available, not only
            # an OR of local collection flags. This matters for objects linked
            # to multiple Collections with different LayerCollection flags.
            indirect_state = effective_object_state(obj, 'indirect_only_get')
            holdout_state = effective_object_state(obj, 'holdout_get')
            if indirect_state is None:
                indirect_state = local_indirect
            if holdout_state is None:
                holdout_state = local_holdout
            if not indirect_state and not holdout_state:
                camera.append(obj)
        here = None
        if not is_master:
            here = {'path': path, 'objects': [o.name for o in direct],
                    'desc_objects': [], 'camera_objects': [],
                    'camera_direct': tuple(o.name for o in camera),
                    'exclude_local': bool(getattr(lc, 'exclude', False)),
                    'indirect_local': bool(getattr(lc, 'indirect_only', False)),
                    'holdout_local': bool(getattr(lc, 'holdout', False)),
                    'indirect_effective': local_indirect,
                    'holdout_effective': local_holdout,
                    'evaluation': 'object-level when Blender supplies *_get(view_layer)'}
            result.append(here)
        all_cam = list(camera)
        descendants = list(direct)
        for child in lc.children:
            cam, objs = walk(child, path, excluded, local_indirect, local_holdout)
            all_cam.extend(cam)
            descendants.extend(objs)
        if here is not None:
            here['camera_objects'] = tuple(sorted({o.name for o in all_cam}))
            here['desc_objects'] = tuple(sorted({o.name for o in descendants}))
        return all_cam, descendants

    walk(view_layer.layer_collection, ())
    return result


def unique_camera_owner(paths):
    """Find the deepest collection shared by ALL camera-visible render objects.

    Don't pick root or a trivial wrapper with multiple unrelated children when
    source ownership isn't uniquely determined. A branch can contain several
    nested object collections, e.g. Main Body -> Mesh / Eye Geometry.
    """
    if not paths:
        return ''
    all_cameras = set()
    for p in paths:
        all_cameras.update(p['camera_objects'])
    if not all_cameras:
        return ''
    matches = [p for p in paths
               if p['camera_objects'] and set(p['camera_objects']) == all_cameras]
    if not matches:
        return ''
    deepest = max(matches, key=lambda p: len(p['path']))
    # Never claim a trivial .ungroup/.ignore root as the owner.
    if deepest['path'] and deepest['path'][-1].lower().endswith(('.ungroup', '.ignore')):
        return ''
    return '/'.join(deepest['path'])



def view_layer_evidence(view_layer):
    """Summarise candidate camera geometry for diagnosis; no pixel render needed."""
    paths = collection_index(view_layer)
    universe = set().union(*(set(x.get('camera_objects', ())) for x in paths)) if paths else set()
    ranked = sorted((
        {'collection': '/'.join(x['path']),
         'camera_objects': len(set(x.get('camera_objects', ()))),
         'fraction': round(len(set(x.get('camera_objects', ()))) / max(1, len(universe)), 3)}
        for x in paths if x.get('path')
    ), key=lambda x: (-x['fraction'], -len(x['collection'].split('/'))))
    return {'view_layer': view_layer.name, 'total_camera_objects': len(universe),
            'candidates': ranked[:16]}


def _shader_mask_attributes(node_tree, depth=0, visited=None):
    """Shader attribute readers with their Blender RNA source type.

    A View Layer attribute is not a mesh attribute. In particular, the
    VIEW_LAYER source can read ID properties from ViewLayer, Scene, or World.
    """
    if node_tree is None or depth > 12:
        return set()
    visited = set() if visited is None else visited
    ident = id(node_tree)
    if ident in visited:
        return set()
    visited.add(ident)
    results = set()
    for node in getattr(node_tree, 'nodes', ()):
        if getattr(node, 'bl_idname', '') == 'ShaderNodeAttribute':
            value = getattr(node, 'attribute_name', '')
            if value:
                results.add((value, getattr(node, 'attribute_type', 'GEOMETRY')))
        if getattr(node, 'bl_idname', '') == 'ShaderNodeGroup':
            results.update(_shader_mask_attributes(getattr(node, 'node_tree', None),
                                                   depth + 1, visited))
    return results


def _used_materials(obj):
    """Materials referenced by at least one face, never orphaned slots.

    A material slot does not imply the geometry uses that material. The
    original mesh's polygon indexes are the cheap read-only first pass.
    """
    slots = getattr(obj, 'material_slots', ())
    if getattr(obj, 'type', '') != 'MESH':
        return [s.material for s in slots if getattr(s, 'material', None)]
    polygons = getattr(getattr(obj, 'data', None), 'polygons', None)
    if polygons is None:
        return []
    indexes = {int(poly.material_index) for poly in polygons}
    return [slots[i].material for i in sorted(indexes)
            if 0 <= i < len(slots) and getattr(slots[i], 'material', None)]


def _layer_attribute_exists(scene, view_layer, attribute_name):
    """View layer attribute may live on ViewLayer, Scene or World."""
    for owner in (view_layer, scene, getattr(scene, 'world', None)):
        if owner is None:
            continue
        try:
            if attribute_name in owner:
                return True
        except (TypeError, AttributeError):
            pass
    return False


def _mesh_has_attribute(obj, name):
    """Verify the actual source mesh has the named mask (not just material)."""
    data = getattr(obj, 'data', None)
    for collection in (getattr(data, 'attributes', None),
                       getattr(data, 'color_attributes', None),
                       getattr(obj, 'vertex_groups', None)):
        if collection is None:
            continue
        try:
            if collection.get(name) is not None:
                return True
        except Exception:
            try:
                if any(getattr(x, 'name', None) == name for x in collection):
                    return True
            except Exception:
                pass
    return False


def _mask_names_for_layer(layer_name):
    """Explicit material mask convention: Mask_<view layer>[.Alpha]."""
    return {('Mask_' + layer_name).casefold(),
            ('Mask_' + layer_name + '.Alpha').casefold()}


def _collection_for_masked_geometry(scene, view_layer, layer_name):
    """Find a Collection from a shader mask verified against its RNA source.

    This provides supporting evidence for shader-authored layers. It never
    implies that an Indirect Only object is a directly rendered contributor.
    """
    path_index = collection_index(view_layer)
    object_paths = {}
    for record in path_index:
        path = record.get('path', ())
        if not path or any(c.casefold().endswith('.ignore') for c in path):
            continue
        # A material on indirect-only/holdout geometry may influence lighting
        # or shadows, but does not establish ownership of painted RGB.
        for name in record.get('camera_direct', ()):
            object_paths.setdefault(name, set()).add(tuple(path))
    if not object_paths:
        return '', 'no directly visible artwork geometry (excluded/holdout/indirect-only ignored)'
    names = _mask_names_for_layer(layer_name)
    material_cache = {}
    verified = {}
    unverified = set()
    objects = getattr(scene, 'objects', None)
    for name, paths in object_paths.items():
        try:
            obj = objects.get(name) if hasattr(objects, 'get') else next(
                (o for o in objects if getattr(o, 'name', '') == name), None)
        except Exception:
            obj = None
        if obj is None or getattr(obj, 'hide_render', False):
            continue
        for mat in _used_materials(obj):
            if mat is None or not getattr(mat, 'use_nodes', True):
                continue
            key = id(mat)
            if key not in material_cache:
                material_cache[key] = _shader_mask_attributes(getattr(mat, 'node_tree', None))
            matching = [(a, typ) for a, typ in material_cache[key]
                        if a.casefold() in names]
            for attr, typ in matching:
                if (typ == 'VIEW_LAYER' and _layer_attribute_exists(scene, view_layer, attr)) or (
                        typ in {'GEOMETRY', 'OBJECT', 'INSTANCER'} and _mesh_has_attribute(obj, attr)):
                    verified[name] = (paths, attr)
                else:
                    unverified.add((name, attr))
    if not verified:
        if unverified:
            return '', ('shader mask found, but no matching mesh attribute confirmed: ' +
                        ', '.join(sorted({a for _, a in unverified})[:3]))
        return '', 'no matching used-material shader mask with a verified attribute source'
    # Use only direct Collection membership; descendant ownership is not proof.
    # Accept one unique group. Multiple groups can have a shared parent, but
    # do not collapse to a trivial .ungroup root merely for a match.
    paths = set()
    for item_paths, _ in verified.values():
        paths.update(item_paths)
    if len(paths) != 1:
        return '', ('shader mask found on multiple Collection owners: ' +
                    ', '.join(sorted('/'.join(p) for p in paths)[:4]))
    path = next(iter(paths))
    if path[-1].casefold().endswith(('.ungroup', '.ignore')):
        return '', 'shader mask owner is only an ungrouped root Collection'
    mask_names = sorted({v[1] for v in verified.values()})
    return '/'.join(path), ('material reads ' + ', '.join(mask_names) +
                            ' on mesh ' + ', '.join(sorted(verified)[:3]))


def _projected_bbox_area(scene, obj):
    """Cheap camera-space footprint, NOT a per-pixel visibility measurement."""
    camera = getattr(scene, 'camera', None)
    if camera is None or getattr(obj, 'type', '') not in GEOMETRY_TYPES:
        return 0.0
    try:
        from bpy_extras.object_utils import world_to_camera_view
        from mathutils import Vector
        coords = [world_to_camera_view(scene, camera, obj.matrix_world @ Vector(pt))
                  for pt in obj.bound_box]
        front = [pt for pt in coords if pt.z >= 0]
        if len(front) < 4:
            return 0.0
        xmin = max(0.0, min(pt.x for pt in front))
        xmax = min(1.0, max(pt.x for pt in front))
        ymin = max(0.0, min(pt.y for pt in front))
        ymax = min(1.0, max(pt.y for pt in front))
        return max(0.0, xmax - xmin) * max(0.0, ymax - ymin)
    except (TypeError, AttributeError, ValueError, ZeroDivisionError):
        return 0.0


def _direct_contribution_candidates(scene, view_layer, records):
    """Screen-footprint estimates for DIRECT, non-holdout artwork meshes.

    Group object identity first to avoid double-counting multi-linked meshes;
    ignore admin collections without a useful artwork branch whenever the
    same object is also linked beneath a .ungroup artwork hierarchy.
    """
    objects = {}
    for record in records:
        path = tuple(record['path'])
        if any(x.casefold().endswith('.ignore') for x in path):
            continue
        for name in record.get('camera_direct', ()):
            obj = scene.objects.get(name)
            if obj is None or getattr(obj, 'type', None) not in GEOMETRY_TYPES:
                continue
            if obj.hide_render or not getattr(obj, 'visible_camera', True):
                continue
            objects.setdefault(name, []).append(path)
    scored = {}
    object_counts = {}
    for name, paths in objects.items():
        # .ungroup is a positive signal that a parent was deliberately used
        # for artwork hierarchy; the wrapper itself will not be exported.
        tagged = [p for p in paths if any(x.lower().endswith('.ungroup') for x in p)]
        eligible = tagged or paths
        path = max(eligible, key=len)
        # Do not use excluded or administrative-only branches as PSD folders.
        if not path or path[-1].lower().endswith(('.ignore', '.ungroup')):
            continue
        weight = _projected_bbox_area(scene, scene.objects.get(name))
        if weight > 0.0:
            scored[path] = scored.get(path, 0.0) + weight
            object_counts[path] = object_counts.get(path, 0) + 1
    return sorted(((path, area, object_counts[path]) for path, area in scored.items()),
                  key=lambda item: item[1], reverse=True)


def _camera_footprint_owner(scene, view_layer, records):
    """Return one plausible dominant Collection, but never fake certainty.

    This uses projected bounding rectangles, not geometry rasterisation;
    transparent materials and shader masks are not faithfully represented.
    A clear majority is required and an unresolved result is valid.
    """
    scores = _direct_contribution_candidates(scene, view_layer, records)
    if not scores:
        return '', 'no directly rendered candidate with measurable camera footprint'
    if len(scores) == 1:
        return '/'.join(scores[0][0]), 'one direct geometry Collection (camera footprint)'
    top_path, top_score, _ = scores[0]
    total = sum(row[1] for row in scores)
    runner = scores[1][1]
    if top_score <= total * 0.5 or top_score <= runner * 1.5:
        return '', 'multiple direct artwork contributors with no decisive screen-footprint majority'
    # For sibling groups, use a meaningful secondary suffix when it improves
    # navigation and is unambiguous. The main group still owns this layer.
    if (len(scores) == 2 and top_path[:-1] == scores[1][0][:-1]
            and scores[1][2] >= 2):
        leaf = top_path[-1] + '-' + scores[1][0][-1]
        return '/'.join(top_path[:-1] + (leaf,)), 'approximate dominant + secondary camera footprint'
    return '/'.join(top_path), 'approximate dominant camera footprint (not Cryptomatte)'


def infer_from_socket(tree, from_socket, default_scene=None):
    """Return (collection_path, view_layers, reason).

    Source-first mapping: only a single render view layer whose entire
    camera-visible geometry shares a nontrivial collection can establish a
    structure-based assignment without using socket-name guesses.
    """
    sources = source_render_layers(tree, from_socket, default_scene=default_scene)
    if len(sources) != 1:
        return '', sources, 'mixed source view layers' if sources else 'unknown render source'
    scene, name = sources[0]
    layer = scene.view_layers.get(name)
    if layer is None:
        return '', sources, 'render view layer no longer exists'
    paths = collection_index(layer)
    owner = unique_camera_owner(paths)
    # A valid material/mesh mask is stronger evidence than broad direct
    # visibility: some view layers render shader-selected portions of a shared
    # object while its Collection is Indirect Only. Prefer the verified mask.
    masked, mask_reason = _collection_for_masked_geometry(scene, layer, name)
    if masked:
        return masked, sources, mask_reason
    if owner:
        return owner, sources, 'unique camera-visible collection'
    estimated, estimate_reason = _camera_footprint_owner(scene, layer, paths)
    if estimated:
        return estimated, sources, estimate_reason
    if mask_reason.startswith('shader mask found'):
        return '', sources, mask_reason
    return '', sources, estimate_reason


def unique_authored_child(view_layer, collection_path):
    """Return a single directly included nested Collection path, or ''.

    This is Collection hierarchy evidence for non-camera compositor AOVs,
    NOT object naming. It never reads the active UI View Layer. A child must
    have some mesh geometry under it. Excluded/hidden/holdout branches and
    indirect-only geometry do not qualify as directly painted content.

    This method is deliberately conservative: if several siblings contain
    eligible geometry, return no refinement rather than guess.
    """
    if not view_layer or not collection_path:
        return ''
    parts = tuple(x for x in collection_path.split('/') if x)
    if not parts:
        return ''

    def descend(lc, target, inherited_path=(), inherited_block=False):
        if inherited_block or getattr(lc, 'exclude', False) or getattr(lc.collection,'hide_render',False):
            return None
        here = inherited_path + (lc.collection.name,)
        if here == target:
            return lc
        if len(here) > len(target) or here != target[:len(here)]:
            return None
        for child in lc.children:
            result = descend(child, target, here)
            if result is not None:
                return result
        return None

    # Root Scene Collection must not appear in paths.
    parent = None
    for top in view_layer.layer_collection.children:
        parent = descend(top, parts)
        if parent is not None:
            break
    if parent is None:
        return ''

    def included_geo(lc, blocked=False, indirect=False, holdout=False):
        if (blocked or getattr(lc, 'exclude', False) or
                getattr(lc.collection, 'hide_render', False)):
            return False
        if indirect or holdout or getattr(lc, 'indirect_only', False) or getattr(lc, 'holdout', False):
            return False
        for obj in lc.collection.objects:
            if (getattr(obj, 'type', None) in GEOMETRY_TYPES and
                    not getattr(obj, 'hide_render', False) and
                    getattr(obj, 'visible_camera', True)):
                return True
        return any(included_geo(child) for child in lc.children)

    # One selected subcollection among several alternatives is intentional.
    # A parent with a single child is harmless but not sufficient evidence
    # that the group should be replaced with a deeper one.
    cursor = parent
    selected_path = parts
    while True:
        candidates = [c for c in cursor.children if included_geo(c)]
        if len(candidates) != 1 or len(cursor.children) < 2:
            break
        cursor = candidates[0]
        selected_path = selected_path + (cursor.collection.name,)
    return '/'.join(selected_path) if selected_path != parts else ''


def unique_distinct_authored_child(view_layer, collection_path, peer_layers):
    """Find a child Collection uniquely enabled for this source among peer outputs.

    Applies only to source View Layers feeding the SAME File Output node.
    Distinguishes an eye's Shade/Membrane branches from persistent iris and
    white geometry when authoring deliberately switches subcollections by
    source pass. It does not use pixel names, active UI layer, or generic
    string matching. Indirect Only and Holdout are not direct paint evidence.
    """
    if not peer_layers or not collection_path:
        return ''
    parts = tuple(n for n in collection_path.split('/') if n)

    def get_collection(layer, path):
        parent = layer.layer_collection
        for part in path:
            parent = next((c for c in parent.children if c.collection.name == part), None)
            if parent is None:
                return None
        return parent

    def has_included_artwork(lc, inherited_block=False):
        """Use Collection render inclusion, including indirect AOV contributors.

        Shader reflection and shade render sources can have no camera-visible
        geometry. Their enabled Collections still establish which authored
        branch the view layer selects. Holdout-only branches are excluded.
        """
        if lc is None or inherited_block or any((
                getattr(lc, 'exclude', False),
                getattr(lc.collection, 'hide_render', False),
                getattr(lc, 'holdout', False))):
            return False
        if any(getattr(o, 'type', '') in GEOMETRY_TYPES and
               not getattr(o, 'hide_render', False)
               for o in lc.collection.objects):
            return True
        return any(has_included_artwork(child) for child in lc.children)

    root = get_collection(view_layer, parts)
    if root is None or not root.children:
        return ''
    active = [c for c in root.children if has_included_artwork(c)]
    unique = []
    for child in active:
        path = parts + (child.collection.name,)
        if all(not has_included_artwork(get_collection(peer, path)) for peer in peer_layers if peer is not view_layer):
            unique.append(path)
    return '/'.join(unique[0]) if len(unique) == 1 else ''
