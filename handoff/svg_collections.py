"""Source collection paths and SVG grouping without changing paint order."""

try:
    from .svg_compat import normalize_metadata
except ImportError:
    try:
        from svg_compat import normalize_metadata
    except ImportError:
        def normalize_metadata(root):
            return root
from xml.etree import ElementTree as ET
import json

SVG = '{http://www.w3.org/2000/svg}'
INK = '{http://www.inkscape.org/namespaces/inkscape}'


def collection_paths(view_layer, root_path=''):
    found = {}
    def walk(branch, path=(), inactive=False):
        if inactive or branch.exclude or branch.collection.hide_render:
            return
        indirect = branch.indirect_only
        if not indirect:
            for obj in branch.collection.objects:
                found.setdefault(obj.name, []).append(path)
        for child in branch.children:
            walk(child, path + (child.collection.name,), indirect)
    walk(view_layer.layer_collection)
    prefix = tuple(p for p in root_path.split('/') if p)
    result = {}
    for name, paths in found.items():
        common = list(paths[0])
        for path in paths[1:]:
            common = common[:next((i for i,(a,b) in enumerate(zip(common,path)) if a!=b), min(len(common),len(path)))]
        path = tuple(common)
        result[name] = list(path[len(prefix):] if prefix and path[:len(prefix)] == prefix else path)
    return result


def group_svg(root, components):
    """Collection folders follow contiguous artwork runs, like the layer stack.

    Returning to a collection makes another segment: moving geometry merely to
    combine folders could change overlapping artwork. Fallback images go
    directly in their authored folder, without a synthetic fallback folder.
    """
    try:
        from .layer_stack import build_stack, tags
        from .svg_document import _blend, _highlight
        from .group_blends import promoted_blend, effective_layer_mode
    except ImportError:
        from layer_stack import build_stack, tags
        from svg_document import _blend, _highlight
        from group_blends import promoted_blend, effective_layer_mode
    normalize_metadata(root)
    children = list(root)
    if len(children) != len(components):
        raise ValueError('SVG object metadata does not match its paint elements')
    entries = []
    for o,e in zip(components,children):
        path = o.get('collection_parts', [])
        flags = set().union(*(tags(p) for p in path)) if path else set()
        if 'ignore' in flags:
            continue
        colors = o.get('collection_colors', [])
        visible = [(p, colors[i] if i < len(colors) else '') for i,p in enumerate(path) if 'ungroup' not in tags(p)]
        entries.append(dict(entry=dict(name=o['name'], element=e),
                            parts=[p for p,c in visible] + [o['name']],
                            flags=flags, mode='normal', group_colors=[c for p,c in visible],
                            inherited_color=o.get('inherited_color') or next((c for c in reversed(colors) if c), '')))
    tree = build_stack(list(reversed(entries)))
    root[:] = []
    group_index = 0
    def emit(nodes, parent, promoted=None):
        nonlocal group_index
        for node in reversed(nodes):
            if node['kind'] == 'group':
                group_index += 1
                el = ET.SubElement(parent, SVG+'g', {'id':f'handoff-collection-{group_index}',
                    INK+'label':node['name'], INK+'groupmode':'layer',
                    'data-handoff-collection':'/'.join(node['path']),
                    'data-handoff-collection-parts':json.dumps(node['path']),
                    'data-handoff-collection-name':node['raw']})
                _highlight(el,node.get('sheet_color') or 'NO_COLOR')
                mode = promoted_blend(node)
                _blend(el,mode or 'normal')
                if '.ref' in node['raw']:
                    el.set('display','none')
                emit(node['children'],el,mode)
            else:
                item=node['item'];el=item['entry']['element']
                _highlight(el,item.get('inherited_color'))
                _blend(el,effective_layer_mode(item,promoted))
                if 'ref' in item.get('flags',set()) or 'reference' in item.get('flags',set()):
                    el.set('display','none')
                parent.append(el)
    emit(tree['children'],root)
    # A raster marker is needed while pixels are being resolved; afterwards
    # the image itself can carry the label and marker, without a fake folder.


def unwrap_raster_groups(root):
    for parent in list(root.iter()):
        for index, child in enumerate(list(parent)):
            if child.tag != SVG+'g' or child.get('data-handoff-raster-request') is None:
                continue
            image = child.find(SVG+'image')
            if image is not None and len(child) == 1:
                image.set('id',child.get('id','')+'-image')
                image.set(INK+'label',child.get(INK+'label','Rendered artwork'))
                image.set('data-handoff-raster-request',child.get('data-handoff-raster-request'))
                parent.remove(child);parent.insert(index,image)


def consolidate_collections(root):
    """Merge interleaved folders only when their complete footprints commute."""
    try:
        from .layer_stack import strip_tags
    except ImportError:
        from layer_stack import strip_tags
    def union(boxes):
        if any(b is None for b in boxes):return None
        return [min(b[0] for b in boxes),min(b[1] for b in boxes),
                max(b[2] for b in boxes),max(b[3] for b in boxes)] if boxes else [0,0,0,0]
    def bounds(el):
        if el.get('data-handoff-bounds'):
            return json.loads(el.get('data-handoff-bounds'))
        if el.tag==SVG+'g':return union([bounds(c) for c in el])
        return None
    def overlap(a,b):
        return a is None or b is None or (a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3])
    merged=0
    for parent in reversed(list(root.iter())):
        children=list(parent);by_key={}
        for child in children:
            key=child.get('data-handoff-collection-parts')
            if key:by_key.setdefault(key,[]).append(child)
        for key,segments in by_key.items():
            if len(segments)<2:continue
            paint_keys=('style','opacity','transform','filter','clip-path','mask','display')
            if any(any(s.get(k)!=segments[0].get(k) for k in paint_keys) for s in segments):continue
            # Combining opacity/isolation groups changes compositing even
            # when the intervening collections are spatially disjoint.
            if any(segments[0].get(k) for k in paint_keys):continue
            own=union([bounds(s) for s in segments])
            first,last=children.index(segments[0]),children.index(segments[-1])
            others=[c for c in children[first:last+1] if c.get('data-handoff-collection-parts')!=key]
            if any(overlap(own,bounds(other)) for other in others):continue
            for segment in segments[1:]:
                segments[0].extend(list(segment));parent.remove(segment);merged+=1
            segments[0].set(INK+'label',strip_tags(segments[0].get('data-handoff-collection-name','Collection')))
    return merged
