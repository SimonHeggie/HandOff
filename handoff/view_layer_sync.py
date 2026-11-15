"""Explicit, undoable File Output input sync for one scene compositor effect.

Graph discovery is read-only. Existing output links/order/settings take priority;
new routes follow unambiguous image branches, including nested node groups.
No render, export, project save, or source datablock deletion is performed.
"""

try:
    from .runtime_paths import PRIVATE_PREFIX
except ImportError:
    from runtime_paths import PRIVATE_PREFIX
import json
import uuid
from dataclasses import dataclass

SYNC_API_VERSION = 1
LAYER_ID = '_handoff_view_layer_id'
SCENE_ID = '_handoff_sync_scene_id'
STATE = '_handoff_view_layer_sync'
REPORT = '_handoff_view_layer_sync_report'
PORTS = '_handoff_sync_ports'


class SyncError(ValueError):
    pass


def _legacy_value(owner, key, default=None):
    """Read saved pre-rename identifiers without writing more old ones."""
    value = owner.get(key)
    if value is None and key.startswith('_handoff_'):
        value = owner.get('_compio_' + key[len('_handoff_'):])
    return default if value is None else value


def _json(owner, key, default):
    try:
        return json.loads(_legacy_value(owner, key, ''))
    except (TypeError, ValueError):
        return default


def _input(tree, socket):
    return next((link.from_socket for link in tree.links
                 if link.to_socket == socket and link.is_valid), None)


def _socket(sockets, identifier):
    return next((s for s in sockets if s.identifier == identifier), None)


def _item(node, identifier):
    # Native File Output items live in a reallocating C array. Never retain
    # their RNA wrappers across new/remove/move: even a name write can crash
    # Blender through a stale pointer. Socket identifiers remain stable.
    index = next(i for i in range(len(node.file_output_items))
                 if node.inputs[i].identifier == identifier)
    return node.file_output_items[index]


def _color(socket):
    return socket.type == 'RGBA' and not socket.is_unavailable


@dataclass(eq=False)
class Context:
    tree: object
    parent: object = None
    instance: object = None

    def trail(self):
        return self.parent.trail() + [self] if self.parent else [self]


class Graph:
    def __init__(self, scene, target_tree):
        effects = getattr(scene, 'compositor_effects', None)
        roots = [effect.node_group for effect in effects if effect.node_group] if effects is not None else []
        if not roots:
            legacy = getattr(scene, 'compositing_node_group', None) or getattr(scene, 'node_tree', None)
            roots = [legacy] if legacy else []
        if len(roots) != 1:
            raise SyncError('Update Inputs currently supports one scene compositor effect. No nodes or inputs changed')
        self.scene = scene
        self.contexts = []
        self.children = {}
        def walk(tree, parent=None, instance=None, ancestors=()):
            if tree.as_pointer() in ancestors:
                raise SyncError('Recursive compositor group; no inputs changed')
            context = Context(tree, parent, instance)
            self.contexts.append(context)
            for node in tree.nodes:
                if node.bl_idname == 'CompositorNodeGroup' and node.node_tree:
                    child = walk(node.node_tree, context, node, ancestors + (tree.as_pointer(),))
                    self.children[(id(context), node.as_pointer())] = child
            return context
        self.root = walk(roots[0])
        targets = [c for c in self.contexts if c.tree == target_tree]
        if len(targets) != 1:
            raise SyncError('Selected File Output must belong to one unique group instance in the current scene effect')
        self.target = targets[0]
        if not target_tree.is_editable:
            raise SyncError('The File Output node group is linked or read-only')
        import bpy
        for other in bpy.data.scenes:
            if other != scene and any(effect.node_group == roots[0]
                                      for effect in getattr(other, 'compositor_effects', ())):
                raise SyncError('This scene effect is shared by another scene; make it single-user before syncing')
        if not scene.is_editable:
            raise SyncError('The current scene is linked or read-only')
        self._origins = {}

    def child(self, context, node):
        return self.children[(id(context), node.as_pointer())]

    def origins(self, context, socket, visiting=None):
        if socket is None:
            return set()
        key = (id(context), socket.as_pointer())
        if key in self._origins:
            return self._origins[key]
        visiting = set() if visiting is None else visiting
        if key in visiting:
            return set()
        visiting = visiting | {key}
        node = socket.node
        kind = node.bl_idname
        if kind == 'CompositorNodeRLayers':
            scene = node.scene or self.scene
            result = {(scene.as_pointer(), node.layer)}
        elif kind == 'NodeGroupInput' and context.parent:
            port = _socket(context.instance.inputs, socket.identifier)
            result = self.origins(context.parent, _input(context.parent.tree, port), visiting)
        elif kind == 'CompositorNodeGroup' and node.node_tree:
            child = self.child(context, node)
            outputs = [n for n in child.tree.nodes if n.bl_idname == 'NodeGroupOutput']
            output = next((n for n in outputs if n.is_active_output), outputs[0] if outputs else None)
            port = _socket(output.inputs, socket.identifier) if output else None
            result = self.origins(child, _input(child.tree, port), visiting) if port else set()
        else:
            result = set()
            for port in node.inputs:
                if port.is_linked:
                    result |= self.origins(context, _input(context.tree, port), visiting)
        self._origins[key] = result
        return result

    def render_nodes(self, layer):
        result = []
        for context in self.contexts:
            for node in context.tree.nodes:
                if (node.bl_idname == 'CompositorNodeRLayers' and
                        (node.scene or self.scene) == self.scene and node.layer == layer.name):
                    result.append((context, node))
        return result

    def terminal(self, layer, sources, target):
        """Prefer existing image destinations over unfinished image branches."""
        wanted = {(self.scene.as_pointer(), layer.name)}
        candidates = {}
        visited = set()
        def offer(rank, context, socket):
            if _color(socket) and self.origins(context, socket) == wanted:
                key = (id(context), socket.as_pointer())
                previous = candidates.get(key)
                if previous is None or rank < previous[0]:
                    candidates[key] = (rank, context, socket)
        def follow(context, socket):
            key = (id(context), socket.as_pointer())
            if key in visited:
                return
            visited.add(key)
            links = [link for link in context.tree.links if link.from_socket == socket and link.is_valid]
            if not links:
                offer(3, context, socket)
            for link in links:
                node, port = link.to_node, link.to_socket
                kind = node.bl_idname
                if node == target:
                    offer(0, context, socket)
                elif kind == 'CompositorNodeOutputFile':
                    offer(0, context, socket)
                elif kind in ('CompositorNodeViewer', 'CompositorNodeComposite'):
                    offer(2, context, socket)
                elif kind == 'NodeGroupOutput':
                    if context.parent and node.is_active_output:
                        external = _socket(context.instance.outputs, port.identifier)
                        if external is not None:
                            follow(context.parent, external)
                    elif not context.parent:
                        offer(1, context, socket)
                elif kind == 'CompositorNodeGroup' and node.node_tree:
                    child = self.child(context, node)
                    for inputs in child.tree.nodes:
                        if inputs.bl_idname == 'NodeGroupInput':
                            internal = _socket(inputs.outputs, port.identifier)
                            if internal is not None:
                                follow(child, internal)
                else:
                    # Scalar/mask side branches do not become the image result.
                    outputs = [s for s in node.outputs if _color(s)]
                    if kind == 'NodeReroute':
                        outputs = list(node.outputs)
                    for output in outputs:
                        follow(context, output)
        for context, node in sources:
            image = node.outputs.get('Image')
            if image is not None:
                follow(context, image)
        if not candidates:
            raise SyncError(layer.name + ': no unambiguous downstream image result (mixed sources or mask-only branch)')
        rank = min(row[0] for row in candidates.values())
        choices = [row for row in candidates.values() if row[0] == rank]
        if len(choices) != 1:
            names = ', '.join(c.tree.name + '/' + s.node.name + '.' + s.name for _, c, s in choices)
            raise SyncError(layer.name + ': multiple downstream image results; preserved existing graph: ' + names)
        return choices[0][1:]

    def check_route(self, source):
        """Never add interface sockets to shared or linked group definitions."""
        a, b = source.trail(), self.target.trail()
        common = 0
        while common < min(len(a), len(b)) and a[common] is b[common]:
            common += 1
        boundaries = a[common:] + b[common:]
        import bpy
        for context in boundaries:
            references = sum(n.bl_idname == 'CompositorNodeGroup' and n.node_tree == context.tree
                             for tree in bpy.data.node_groups if tree.bl_idname == 'CompositorNodeTree'
                             for n in tree.nodes)
            if not context.tree.is_editable or references != 1:
                raise SyncError('Cannot add a route through shared/read-only group ' + context.tree.name)
        if not source.tree.is_editable:
            raise SyncError('Downstream source group is read-only: ' + source.tree.name)
        return a, b, common


def _owner_color(scene, layer, palette, sources):
    if layer.layer_collection is None:
        return None
    try:
        from .collection_provenance import collection_index, unique_camera_owner, infer_from_socket
        from .attribution_names import name_match
    except ImportError:
        from collection_provenance import collection_index, unique_camera_owner, infer_from_socket
        from attribution_names import name_match
    records = collection_index(layer)
    path, _ = name_match(layer.name, records)
    path = path or unique_camera_owner(records)
    if not path and sources and sources[0][1].outputs.get('Image') is not None:
        context, source = sources[0]
        candidate, _, reason = infer_from_socket(context.tree, source.outputs['Image'], default_scene=scene)
        if not reason.startswith('approximate'):
            path = candidate
    if not path:
        return None
    for name in reversed(path.split('/')):
        import bpy
        collection = bpy.data.collections.get(name)
        tag = getattr(collection, 'color_tag', 'NONE')
        if tag != 'NONE':
            return tuple(palette[int(tag[-2:])-1])
    return ()  # Known parent with no colour tag: use Blender's default node colour.


def _palette():
    import bpy
    try:
        from .collection_colors import theme_collection_colors
    except ImportError:
        from collection_colors import theme_collection_colors
    return theme_collection_colors(bpy) or [(.84,.29,.29),(.89,.55,.23),(.94,.78,.22),
        (.31,.67,.32),(.30,.52,.87),(.59,.36,.78),(.80,.29,.66),(.51,.51,.51)]


def synchronize(scene, node):
    """Apply an explicit sync; preserve native links, input order and formats."""
    if node.bl_idname != 'CompositorNodeOutputFile':
        raise SyncError('Select a native File Output node')
    graph = Graph(scene, node.id_data)
    tree = node.id_data
    layers = list(scene.view_layers)
    state = _json(node, STATE, {})
    if state and not isinstance(state, dict):
        raise SyncError('Saved input-sync metadata is invalid; no inputs changed')
    scene_id = str(_legacy_value(scene, SCENE_ID) or uuid.uuid4().hex)
    tokens = {}
    for layer in layers:
        token = str(_legacy_value(layer, LAYER_ID) or uuid.uuid4().hex)
        if token in tokens:
            token = uuid.uuid4().hex  # Duplicated View Layers can copy custom properties.
        tokens[token] = layer
    reverse = {layer.as_pointer(): token for token, layer in tokens.items()}
    report = dict(added=[], removed=[], renamed=[], created_nodes=[], warnings=[], connected=[], kept=[])
    assigned = {}; stale = []; unmanaged = []
    slots = list(node.file_output_items)
    for index, item in enumerate(slots):
        socket = node.inputs[index]
        record = state.get(socket.identifier)
        layer = None
        if record and record.get('scene') == scene_id:
            layer = tokens.get(record.get('layer'))
            if layer is None:
                stale.append((socket.identifier, item.name, record.get('name', item.name)))
                continue
        if layer is None:
            origins = graph.origins(graph.target, _input(tree, socket))
            valid = [vl for vl in layers if (scene.as_pointer(), vl.name) in origins]
            # A linked utility pass remains manual; only Image/processed colour
            # slots can be claimed by this button.
            if socket.type == 'RGBA':
                if len(origins) == 1 and len(valid) == 1:
                    layer = valid[0]
                elif item.name in scene.view_layers:
                    layer = scene.view_layers[item.name]
        if layer is not None and layer.as_pointer() not in assigned:
            assigned[layer.as_pointer()] = socket.identifier
        else:
            unmanaged.append(item.name)
    if unmanaged:
        report['warnings'].append('Preserved unrecognised or additional manual inputs: ' + ', '.join(unmanaged))
    plans = []
    palette = _palette()
    for layer in layers:
        sources = graph.render_nodes(layer)
        existing = assigned.get(layer.as_pointer())
        connection = _input(tree, _socket(node.inputs, existing)) if existing else None
        if connection is not None and (scene.as_pointer(), layer.name) not in graph.origins(graph.target, connection):
            report['warnings'].append(layer.name + ': existing input has no traced source for this View Layer; '
                                      'its authored processing link was preserved')
        if not layer.use:
            report['warnings'].append(layer.name + ': View Layer is disabled for rendering; render flag unchanged')
        if not layer.use_pass_combined:
            report['warnings'].append(layer.name + ': Combined Image pass is disabled; pass settings unchanged')
        color = _owner_color(scene, layer, palette, sources)
        if color is None:
            report['warnings'].append(layer.name + ': parent Collection colour is ambiguous; existing node colours kept')
        destination = None
        if connection is None and sources:
            try:
                destination = graph.terminal(layer, sources, node)
                graph.check_route(destination[0])
            except SyncError as exc:
                report['warnings'].append(str(exc))
        elif connection is None and not graph.root.tree.is_editable:
            report['warnings'].append(layer.name + ': scene compositor is read-only')
        create = not sources and graph.root.tree.is_editable
        if create:
            try:
                graph.check_route(graph.root)
            except SyncError as exc:
                create = False
                report['warnings'].append(layer.name + ': ' + str(exc))
        plans.append(dict(layer=layer, existing=existing, sources=sources, destination=destination,
                          create=create, color=color))
    # All topology/scope decisions above are read-only. Only this explicit action
    # gives View Layers durable identities; ordinary export still needs no sync.
    scene[SCENE_ID] = scene_id
    for token, layer in tokens.items():
        layer[LAYER_ID] = token
    new_state = {}
    for plan in plans:
        layer = plan['layer']; token = reverse[layer.as_pointer()]
        sources = plan['sources']
        if plan['create']:
            source = graph.root.tree.nodes.new('CompositorNodeRLayers')
            source.scene = scene; source.layer = layer.name
            source.label = layer.name
            source.location = (node.location.x-400, node.location.y-160*len(report['created_nodes']))
            sources = [(graph.root, source)]
            report['created_nodes'].append(layer.name)
            image = source.outputs.get('Image')
            if image is not None and not image.is_unavailable:
                plan['destination'] = (graph.root, image)
            else:
                report['warnings'].append(layer.name + ': Render Layers node has no available Image output; input was not connected')
        for context, source in sources:
            # Reused node groups are coloured once per actual node, never moved.
            if context.tree.is_editable:
                if plan['color'] is not None:
                    source.use_custom_color = bool(plan['color'])
                    if plan['color']:
                        source.color = plan['color']
        existing = plan['existing']
        if existing:
            socket = _socket(node.inputs, existing)
            report['kept'].append(layer.name)
        elif plan['destination']:
            item = node.file_output_items.new('RGBA', layer.name)
            socket = node.inputs[len(node.file_output_items)-1]
            assigned[layer.as_pointer()] = socket.identifier
            report['added'].append(layer.name)
        else:
            continue
        if _input(tree, socket) is None and plan['destination']:
            context, source = plan['destination']
            source = _route(graph, context, source, layer.name, token)
            tree.links.new(source, socket)
            report['connected'].append(layer.name)
        new_state[socket.identifier] = dict(scene=scene_id, layer=token, name=layer.name)
    # Remove only inputs previously associated with a proven deleted View Layer.
    # Render Layers nodes and compositor processing are deliberately retained.
    for identifier, item_name, old_name in reversed(stale):
        report['removed'].append(item_name + ' (deleted View Layer ' + old_name + ')')
        node.file_output_items.remove(_item(node, identifier))
    # Temporarily free old names to handle swaps without Blender adding .001.
    renames = [(layer, assigned[layer.as_pointer()], _item(node, assigned[layer.as_pointer()]).name)
               for layer in layers if layer.as_pointer() in assigned and
               _item(node, assigned[layer.as_pointer()]).name != layer.name]
    occupied = set(unmanaged)
    for layer, identifier, old_name in renames:
        if layer.name in occupied:
            report['warnings'].append('Cannot rename input to ' + layer.name + ': a manual input already uses that name')
        else:
            report['renamed'].append(old_name + ' -> ' + layer.name)
            _item(node, identifier).name = PRIVATE_PREFIX + 'sync_' + uuid.uuid4().hex
    for layer, identifier, old_name in renames:
        if layer.name not in occupied:
            _item(node, identifier).name = layer.name
    if report['removed']:
        report['warnings'].append('Removed inputs: ' + '; '.join(report['removed']))
    node[STATE] = json.dumps(new_state)
    node[REPORT] = json.dumps(report)
    return report


def _route(graph, source_context, source, name, token):
    """Expose a unique source along group boundaries, reusing owned ports."""
    a, b, common = graph.check_route(source_context)
    def port(context, direction):
        tree = context.tree
        metadata = _json(tree, PORTS, {})
        key = direction + ':' + token
        identifier = metadata.get(key)
        interface = next((s for s in tree.interface.items_tree
                          if s.item_type == 'SOCKET' and s.identifier == identifier and s.in_out == direction), None)
        if interface is None:
            interface = tree.interface.new_socket(name=name, in_out=direction, socket_type='NodeSocketColor')
            metadata[key] = interface.identifier
            tree[PORTS] = json.dumps(metadata)
        return interface
    for context in reversed(a[common:]):
        interface = port(context, 'OUTPUT')
        outputs = [n for n in context.tree.nodes if n.bl_idname == 'NodeGroupOutput']
        output = next((n for n in outputs if n.is_active_output), outputs[0] if outputs else None)
        if output is None:
            output = context.tree.nodes.new('NodeGroupOutput')
        context.tree.links.new(source, _socket(output.inputs, interface.identifier))
        source = _socket(context.instance.outputs, interface.identifier)
    for context in b[common:]:
        interface = port(context, 'INPUT')
        context.parent.tree.links.new(source, _socket(context.instance.inputs, interface.identifier))
        inputs = next((n for n in context.tree.nodes if n.bl_idname == 'NodeGroupInput'), None)
        if inputs is None:
            inputs = context.tree.nodes.new('NodeGroupInput')
        source = _socket(inputs.outputs, interface.identifier)
    return source
