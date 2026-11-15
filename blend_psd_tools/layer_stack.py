"""Non-destructive collection-based ordering for layered artwork exports.

The compositor socket order is the sole stack authority (TOP to BOTTOM).
A Photoshop/OCA group can only contain consecutive entries; returning to a
collection after an intervening layer creates a new group segment.
"""
import re

STACK_API_VERSION = 8

from collections import Counter, defaultdict

BLEND_SUFFIX = re.compile(r'(?:__|\.)(normal|multiply|screen|additive|add|linear_dodge|linear-dodge|overlay|darken|lighten)$', re.I)
TAG = re.compile(r'\.(ignore|ungroup|merge|folder|ref|reference)(?=\.|$)', re.I)
PSD_TAG = re.compile(r'\.(ignore|folder)(?=\.|$)', re.I)


def tags(s):
    return {m.group(1).lower() for m in TAG.finditer(s)}


def strip_tags(s):
    return TAG.sub('', s).strip() or 'Layer'


def explicit_parts(entry):
    label = BLEND_SUFFIX.sub('', entry['name'])
    parts = [p.strip() for p in label.replace('\\', '/').split('/') if p.strip() and p.strip() not in ('.', '..')]
    return parts or ['Layer']


def prepared_entries(inputs, use_groups):
    """Return [{entry,path,parts,mode}], in compositor TOP -> BOTTOM order.

    Inputs must be (manifest-entry, source-file) pairs.
    Ignore excludes itself/children, ungroup strips container while retaining
    the children, and [blend].suffix stays on the pixel layer only.
    """
    out = []
    for entry, source in inputs:
        raw = explicit_parts(entry)
        # .ignore applies to all additional export formats, regardless of
        # whether grouping/flattening is enabled.
        collection = [p.strip() for p in entry.get('collection_path', '').split('/') if p.strip()]
        if any({'merge', 'ungroup'} <= tags(component) for component in collection):
            raise ValueError('A Collection cannot use both .merge and .ungroup')
        if any('ignore' in tags(component) for component in (raw + collection)):
            continue
        original = entry['name']
        match = BLEND_SUFFIX.search(original)
        mode = match.group(1).lower() if match else 'normal'
        if use_groups:
            parts = raw
            coll = collection
            if len(parts) == 1:
                parts = coll + parts
            # Collection colour slots match the authored path, including
            # ancestors removed later by .ungroup. Names may change during
            # collision resolution, so colours belong to nodes, not labels.
            authored_colors = entry.get('collection_colors', [])
            colors = [''] * len(parts)
            if len(raw) == 1 and coll:
                for index in range(min(len(coll), len(authored_colors))):
                    colors[index] = authored_colors[index]
            # With an explicitly authored group path, only apply colours when
            # the group names exactly match the Blender Collection ancestry.
            elif parts[:-1] == coll:
                for index in range(min(len(coll), len(authored_colors))):
                    colors[index] = authored_colors[index]
            paired = [(part, color) for part, color in zip(parts, colors)
                      if 'ungroup' not in tags(part)]
            parts = [part for part, _ in paired]
            group_colors = [color for _, color in paired[:-1]]
            # Nearest coloured Collection controls its descendant pixels, even
            # if that Collection is removed from the PSD by .ungroup.
            leaf_color = next((c for c in reversed(colors[:-1]) if c), '')
        else:
            leaf_color = ''
            parts = [' / '.join(strip_tags(p) for p in raw)]
        if not parts:
            parts = ['Layer']
        # .ref/.reference are exporter metadata, not part of artwork names.
        # Blend suffixes (.add, .multiply) remain only as operational metadata.
        parts[-1] = strip_tags(parts[-1])
        flags = set()
        for component in raw + collection:
            flags.update(tags(component))
        if entry.get('render_placeholder'):
            flags.add('disabled')
        out.append({'entry': entry, 'source': source, 'parts': parts, 'mode': mode, 'flags': flags,
                    'group_colors': group_colors if use_groups else [],
                    'inherited_color': leaf_color,
                    'source_view_layer': entry.get('source_view_layer', '')})
    return out


def _name_segment(original, letter):
    """E.g. HAT.merge -> HAT-A.merge, preserving trailing metadata tags."""
    m = TAG.search(original)
    at = m.start() if m else len(original)
    return original[:at] + '-' + letter + original[at:]


def _alpha_index(index):
    """Spreadsheet-like A..Z, AA..AZ, for repeated group segments."""
    value = ''
    index += 1
    while index:
        index, r = divmod(index - 1, 26)
        value = chr(65 + r) + value
    return value


def build_stack(items):
    """Build contiguous group tree in top-to-bottom order.

    Group nodes: {kind:'group', raw, path, children, name}; layers carry item.
    Can be used by both PSD and OCA writers.
    """
    root = {'kind': 'group', 'children': [], 'path': (), 'name': ''}
    active = [root]
    for item in items:
        group_path = tuple(item['parts'][:-1])
        matching = 0
        for a, b in zip([n['raw'] for n in active[1:]], group_path):
            if a != b:
                break
            matching += 1
        active = active[:matching + 1]
        for depth, segment in enumerate(group_path[matching:], start=matching):
            parent = active[-1]
            node = {'kind': 'group', 'raw': segment,
                    'path': parent['path'] + (segment,), 'children': [], 'name': segment,
                    'parent_segment_id': id(parent),
                    'sheet_color': (item.get('group_colors') or [])[depth]
                                   if depth < len(item.get('group_colors') or []) else ''}
            parent['children'].append(node)
            active.append(node)
        # Another layer in the same uninterrupted Collection run can provide
        # the tag when the first entry was exported from older cache metadata.
        for depth, node in enumerate(active[1:]):
            colors = item.get('group_colors') or []
            if depth < len(colors) and colors[depth] and not node.get('sheet_color'):
                node['sheet_color'] = colors[depth]
        active[-1]['children'].append({'kind': 'layer', 'name': item['parts'][-1], 'item': item})
    # Disambiguate only groups that actually share a name in one parent.
    # In particular, an authored "-B" already distinguishes a second group.
    # Children of two distinct parent instances have independent namespaces.
    def authored_route(node):
        """Read immediate group names before looking at a pixel-layer name.

        A single authored Collection chain is the strongest naming clue.
        With multiple children, prefer their common first group. A generic
        fallback is handled by the collision resolver, not guessed here.
        """
        children = node['children']
        groups = [c for c in children if c['kind'] == 'group']
        if len(groups) == 1:
            child = groups[0]
            return [strip_tags(child['raw'])] + authored_route(child)
        if len(groups) > 1:
            group_names = list(dict.fromkeys(strip_tags(c['raw']) for c in groups))
            if len(group_names) == 1:
                return group_names
            return []
        leaves = [c for c in children if c['kind'] == 'layer']
        if len(leaves) == 1:
            return [BLEND_SUFFIX.sub('', strip_tags(leaves[0]['name'])).strip()]
        return []

    def collision_name(raw, route, depth):
        """Keep the authored parent name and add the shortest useful clue.

        We examine an immediate child Collection first, and descend only if
        that name is shared by another competing group. For nested branches
        such as Hood / Hood_FG, the unique leaf provides the suffix without
        repeating Hood in the final label. This does not change group nesting.
        """
        if depth < 1 or depth > len(route):
            return ''
        suffix = strip_tags(route[depth - 1])
        if not suffix or suffix.casefold() == strip_tags(raw).casefold():
            return ''
        return _name_segment(raw, suffix)

    def resolve(parent):
        siblings = [c for c in parent['children'] if c['kind'] == 'group']
        collisions = defaultdict(list)
        for child in siblings:
            collisions[strip_tags(child['raw']).casefold()].append(child)
        # Suffix names only within one parent; nested groups have their own
        # namespaces. Existing distinct authored names are always reserved.
        names_taken = {strip_tags(child['name']).casefold() for child in siblings}
        for base, duplicate in collisions.items():
            if len(duplicate) <= 1:
                continue
            routes = [authored_route(x) for x in duplicate]
            # A source group containing a same-named child is a good choice
            # for the unsuffixed instance. An otherwise unlabelled group also
            # keeps its original name. When every group has a *distinct*
            # child identity, suffix all of them for symmetric naming, such
            # as MainBody-ForeArm_L and MainBody-ForeArm_R.
            keep = next((i for i, route in enumerate(routes)
                         if not route or route[0].casefold() == base), None)
            if keep is None:
                if any(not route for route in routes) or len({tuple(x.casefold() for x in r) for r in routes}) != len(routes):
                    keep = 0
            if keep is not None:
                # The authored unsuffixed group is already reserved.
                names_taken.add(base)
            for index, group in enumerate(duplicate):
                if index == keep:
                    continue
                route = routes[index]
                name = ''
                for depth in range(1, len(route) + 1):
                    prefix = tuple(x.casefold() for x in route[:depth])
                    if any(tuple(x.casefold() for x in other[:depth]) == prefix
                           for j, other in enumerate(routes) if j != index):
                        continue
                    candidate = collision_name(group['raw'], route, depth)
                    # A group's authored name must survive unless the group
                    # genuinely collides. Prefer semantic child names before
                    # an alphabetical fallback.
                    if candidate and candidate.casefold() not in names_taken:
                        name = candidate
                        break
                if not name:
                    n = 0
                    while True:
                        candidate = _name_segment(group['raw'], _alpha_index(n))
                        if candidate.casefold() not in names_taken:
                            name = candidate
                            break
                        n += 1
                group['name'] = name
                names_taken.add(name.casefold())
        for child in siblings:
            resolve(child)

    resolve(root)

    # The local collision pass above cannot see an authored Collection that
    # appears under multiple *separate* parent group instances.  In a PSD,
    # Headgear-Hood_FG/Hood and Headgear-Head_Back/Hood have distinct immediate
    # parents, but both Hood groups are disjoint exports of the same Blender
    # Collection. Give the repeated Hood instances meaningful names too.
    # This is a naming operation only: never coalesce separated stack runs.
    repeated_paths = defaultdict(list)
    def collect_groups(node):
        for child in node['children']:
            if child['kind'] == 'group':
                repeated_paths[tuple(x.casefold() for x in child['path'])].append(child)
                collect_groups(child)
    collect_groups(root)
    for path, occurrences in repeated_paths.items():
        if len(occurrences) < 2 or len({g['parent_segment_id'] for g in occurrences}) < 2:
            continue
        routes = [authored_route(g) for g in occurrences]
        # For repeated instances under different parents, require usable,
        # distinct authored child identities. Same-name group/pixel pairs are
        # allowed and do not receive a pointless repeated-name suffix.
        if not all(routes):
            continue
        for i, group in enumerate(occurrences):
            if group['name'] != group['raw']:
                continue  # A local collision already assigned a useful name.
            route = routes[i]
            other_routes = routes[:i] + routes[i + 1:]
            for depth in range(1, len(route) + 1):
                prefix = tuple(x.casefold() for x in route[:depth])
                if any(tuple(x.casefold() for x in r[:depth]) == prefix
                       for r in other_routes):
                    continue
                candidate = collision_name(group['raw'], route, depth)
                if candidate:
                    group['name'] = candidate
                    break

    # If a top-level Collection contributes only one named subcollection,
    # label that partial branch with the child identity. Hair/UpperLashes is
    # more informative as Hair-UpperLashes: otherwise the exported Hair group
    # looks like the entire Hair Collection. This deliberately excludes a
    # same-name parent/child pair (e.g. Sceptres_R/Sceptres_R) and full groups
    # containing several distinct subcollections (e.g. Headgear/Band, Snake).
    for group in root['children']:
        if group['kind'] != 'group' or group['name'] != group['raw']:
            continue
        children = group['children']
        if len(children) != 1 or children[0]['kind'] != 'group':
            continue
        child = children[0]
        if strip_tags(child['raw']).casefold() == strip_tags(group['raw']).casefold():
            continue
        if len(child['children']) != 1 or child['children'][0]['kind'] != 'layer':
            continue
        if strip_tags(child['children'][0]['name']).casefold() != strip_tags(child['raw']).casefold():
            continue
        candidate = _name_segment(group['raw'], strip_tags(child['raw']))
        if not any(other is not group and other['kind'] == 'group'
                   and other['name'].casefold() == candidate.casefold()
                   for other in root['children']):
            group['name'] = candidate
    return root


def leaf_names(tree):
    out = []
    def visit(node, path=()):
        if node['kind'] == 'layer':
            out.append((*path, node['name']))
        else:
            for child in node['children']:
                visit(child, path + ((node['name'],) if node['name'] else ()))
    visit(tree)
    return out


def psd_group_name(name):
    """Convert Blender dot tags to Spine's bracket tags on PSD export."""
    return PSD_TAG.sub(lambda m: ' [' + m.group(1).lower() + ']', name)


def preview_merge_groups(root):
    """Show the shape of .merge outputs before pixels are rendered."""
    try:
        from .group_blends import promoted_blend
    except ImportError:
        # The standalone PSD worker imports layer_stack as a top-level module.
        from group_blends import promoted_blend
    def walk(node):
        new_children = []
        for child in node['children']:
            if child['kind'] != 'group':
                new_children.append(child)
                continue
            walk(child)
            if 'merge' in tags(child['raw']):
                name = strip_tags(child['name'])
                new_children.append({
                    'kind': 'layer', 'name': name, 'merged_preview': True,
                    'item': {'mode': promoted_blend(child) or 'normal', 'flags': set()},
                })
            else:
                new_children.append(child)
        node['children'] = new_children
    walk(root)
    return root
