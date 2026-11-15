"""Read historical SVG metadata without emitting obsolete brand identifiers.

Only namespaced exporter metadata is migrated. Artist-authored SVG IDs and
content are left intact to avoid silently changing external references.
"""

def normalize_metadata(root):
    for node in root.iter():
        for key, value in list(node.attrib.items()):
            if key.startswith('data-compio-'):
                newer = 'data-handoff-' + key[len('data-compio-'):]
                if newer not in node.attrib:
                    node.set(newer, value)
                del node.attrib[key]
    return root
