"""OCA destination policy; no other exporter consumes these controls."""
import math
import uuid

DEFAULTS = dict(ignoreHiddenLayers=False, ignoreBackground=True, trimWhitespace=True,
                writeJson=False, writeTemplate=False, scale=100.0, padding=1)
PROPERTIES = dict(ignoreHiddenLayers='oca_ignore_hidden_layers', ignoreBackground='oca_ignore_background',
                  trimWhitespace='trim_empty_pixels', writeJson='oca_write_json',
                  writeTemplate='oca_write_template', scale='oca_scale', padding='oca_padding')


def input_identity(node,socket):
    """Persistent File Output node UUID + Blender's stable input identifier.

    Reordering/renaming a socket does not turn it into another artwork layer.
    Copied nodes need their own UUID; no geometry is evaluated or modified.
    """
    key='_handoff_oca_node_id';owner='_handoff_oca_node_owner'
    token=node.get(key)
    if token:
        others=[n for n in node.id_data.nodes if n!=node and n.get(key)==token]
        if others and (node.get(owner)!=node.name and any(n.get(owner)==n.name for n in others)):
            token=None
        elif others and not any(n.get(owner)==n.name for n in [node,*others]) and node.name!=min(n.name for n in [node,*others]):
            token=None
    if not token:token=uuid.uuid4().hex;node[key]=token
    node[owner]=node.name
    return str(token)+':'+socket.identifier


def capture_options(item):
    return {key: getattr(item, prop, DEFAULTS[key]) for key, prop in PROPERTIES.items()}


def options(job):
    result = dict(DEFAULTS)
    # Retained jobs may have the earlier flat trimming property.
    if 'trim_empty_pixels' in job:
        result['trimWhitespace'] = bool(job['trim_empty_pixels'])
    result.update(job.get('oca_options', {}))
    scale = float(result['scale'])
    padding = result['padding']
    if not math.isfinite(scale) or not 0 < scale <= 400:
        raise ValueError('OCA Scale must be greater than 0 and at most 400 percent')
    if isinstance(padding, bool) or int(padding) != padding or padding < 0:
        raise ValueError('OCA Padding must be a nonnegative integer')
    result['scale'], result['padding'] = scale, int(padding)
    return result


def capture_source(tree, socket, scene, collection_path, trace):
    """Capture publishing visibility and an explicit background designation.

    View Layer/Collection custom properties can additionally hide cached
    artwork without changing render flags. Renderer-disabled data still follows the
    established previous-render/blank-placeholder policy.
    """
    import bpy
    sources = trace(tree, socket, default_scene=scene)
    source_layers = [owner.view_layers.get(name) for owner, name in sources]
    source_layers = [layer for layer in source_layers if layer is not None]
    visible = any(layer.use and bool(layer.get('handoff_oca_visible', True)) for layer in source_layers) if source_layers else True
    background = bool(source_layers) and all(bool(layer.get('handoff_oca_background', False)) for layer in source_layers)
    states = {}
    names = [name for name in collection_path.split('/') if name]
    for name in names:
        collection = bpy.data.collections.get(name)
        state = not bool(collection and (collection.hide_viewport or collection.hide_render))
        if collection:
            state = state and bool(collection.get('handoff_oca_visible', True))
        matches = []
        def visit(layer_collection, ancestor=True):
            # Exclude selects render geometry; it is not document visibility.
            # Compositor-derived artwork may use an excluded Collection solely
            # as its logical owner (e.g. material-mask eye passes).
            current = ancestor and not layer_collection.hide_viewport
            if layer_collection.name == name:
                matches.append(current)
            for child in layer_collection.children:
                visit(child, current)
        for layer in source_layers:
            visit(layer.layer_collection)
        states[name] = state and (any(matches) if matches else True)
    from .oca_authoring import capture
    return dict(oca_visible=visible, oca_background=background, oca_group_visibility=states,
                **capture(scene,source_layers,collection_path))


def visible(entry):
    # Publishing visibility is independent of pixel alpha and RGB contents.
    from layer_stack import tags
    names = [entry.get('name', ''), *entry.get('collection_path', '').split('/')]
    reference = any(tags(name) & {'ref', 'reference'} for name in names)
    return (bool(entry.get('oca_visible', True)) and
            all(entry.get('oca_group_visibility', {}).values()) and
            not reference and not entry.get('render_placeholder', False))


def eligible(entry, settings):
    if settings['ignoreBackground'] and entry.get('oca_background', False):
        return False
    if settings['ignoreHiddenLayers'] and not visible(entry):
        return False
    return True


def annotate_stack(root, settings):
    """Attach OCA-only visibility to existing stack nodes; never rename nodes."""
    def visit(node, ancestor=True):
        for child in node['children']:
            if child['kind'] == 'group':
                states = []
                def gather(branch):
                    for sub in branch['children']:
                        if sub['kind'] == 'group': gather(sub)
                        else:
                            value = sub['item']['entry'].get('oca_group_visibility', {}).get(child['raw'])
                            if value is not None: states.append(bool(value))
                gather(child)
                child['oca_visible'] = (any(states) if states else True) and ancestor
                visit(child, child['oca_visible'])
            else:
                child['oca_visible'] = ancestor and visible(child['item']['entry'])
        if settings['ignoreHiddenLayers']:
            node['children'] = [c for c in node['children'] if c['oca_visible']]
    visit(root)
    return root


def merged_visibility(before, after):
    """Carry group visibility through the existing .merge substitution."""
    for original, current in zip(before['children'], after['children']):
        if original['kind'] == 'group' and current['kind'] == 'layer':
            current['oca_visible'] = original['oca_visible']
        elif current['kind'] == 'group':
            current['oca_visible'] = original['oca_visible']
            merged_visibility(original, current)


def check_merge_visibility(root):
    from layer_stack import tags
    for child in root['children']:
        if child['kind'] != 'group': continue
        check_merge_visibility(child)
        if 'merge' not in tags(child['raw']): continue
        def leaves(node):
            for sub in node['children']:
                if sub['kind'] == 'group': yield from leaves(sub)
                else: yield sub['oca_visible']
        if len(set(leaves(child))) > 1:
            raise ValueError('OCA cannot merge visible and hidden artwork while retaining hidden layers: '
                             + child['name'] + '. Enable Ignore hidden layers or remove .merge.')
