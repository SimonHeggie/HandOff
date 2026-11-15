"""Identify a direct image connection for a conservative SVG render-source test."""

SOURCE_API_VERSION = 1


def direct_render_image_source(tree, source_socket, default_scene, source_render_layers):
    """Return (scene, ViewLayer, reason) or (None, None, reason).

    Reroutes are transparent. Any compositor operation, group, mix, or
    non-Image pass must be rendered rather than silently bypassed.
    """
    cursor = source_socket
    seen = set()
    while cursor is not None:
        node = getattr(cursor, 'node', None)
        if node is None:
            return None, None, 'Source node unavailable'
        key = id(node)
        if key in seen:
            return None, None, 'Cycle in compositor source'
        seen.add(key)
        if getattr(node, 'bl_idname', '') == 'NodeReroute':
            inp = node.inputs[0] if len(node.inputs) else None
            links = [link for link in tree.links if link.to_socket == inp]
            if len(links) != 1:
                return None, None, 'Unconnected or ambiguous reroute'
            cursor = links[0].from_socket
            continue
        if getattr(node, 'bl_idname', '') not in ('CompositorNodeRLayers', 'CompositorNodeRenderLayers'):
            return None, None, 'Compositor processing requires rendered PNG'
        if getattr(cursor, 'name', '') != 'Image':
            return None, None, 'Non-Image render pass requires PNG'
        origins = source_render_layers(tree, source_socket, default_scene=default_scene)
        if len(origins) != 1:
            return None, None, 'Ambiguous source scene or View Layer'
        scene, name = origins[0]
        if scene is None:
            scene = default_scene
        layer = scene.view_layers.get(name) if scene is not None else None
        return (scene, layer, 'Direct Render Layers image source' if layer else 'View Layer unavailable')
    return None, None, 'No source'
