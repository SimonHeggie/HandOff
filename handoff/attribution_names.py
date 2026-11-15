"""Conservative legacy Collection-name matching, scoped to a source View Layer.

A File Output socket carries no authoritative geometry ownership. We restore
unambiguous Blender object and Collection identity as *evidence*, but do not
infer ownership using camera-object majority, substring matches or guesses.
This module is pure Python for isolated regression tests.
"""
import re

TAG_RE = re.compile(r'\.(?:ignore|ungroup|merge|folder)(?=\.|$)', re.I)
PASS_RE = re.compile(r'(?:__|\.)(?:normal|multiply|screen|add|additive|overlay|darken|lighten|ref|reference)$', re.I)


def normalized(value):
    return re.sub(r'[^a-z0-9]+', '', str(value).casefold())


def variants(value):
    base = normalized(value)
    if not base:
        return set()
    result = {base}
    if base.endswith('es') and len(base) > 2:
        result.add(base[:-2])
    if base.endswith('s') and len(base) > 1:
        result.add(base[:-1])
    return result


def collection_leaf(path):
    return TAG_RE.sub('', path[-1]) if path else ''


def name_match(name, records):
    """Return (path, explanation) only if exactly one candidate matches.

    records include {'path': tuple, 'objects': names}, where objects are only
    DIRECT collection members (not entire descendants). Master collection is
    not exposed. Caller must pass candidate records from relevant View Layer.
    """
    raw = str(name).strip()
    if '/' in raw or '\\' in raw:
        return '', 'explicit layer path handled by stack builder'
    stem = PASS_RE.sub('', raw)
    full = variants(stem)
    parts = [p for p in re.split(r'[_.\s-]+', stem) if p]
    candidates = [rec for rec in records if rec.get('path') and not any(
        '.ignore' in s.casefold() for s in rec['path'])]
    methods = [
        ('exact Blender object name', lambda rec: any(full & variants(obj) for obj in rec.get('objects', ()))),
        ('exact Blender Collection name', lambda rec: bool(full & variants(collection_leaf(rec['path'])))),
    ]
    if len(parts) > 1:
        first = variants(parts[0])
        methods.append(('unique leading-name Collection match',
                        lambda rec: bool(first & variants(collection_leaf(rec['path'])))))
    for reason, check in methods:
        results = {tuple(rec['path']) for rec in candidates if check(rec)}
        if len(results) == 1:
            return '/'.join(next(iter(results))), reason
        if len(results) > 1:
            # Do not let a weaker strategy override a genuine ambiguity.
            return '', 'ambiguous ' + reason
    return '', 'no unique object or Collection name match'


def unique_source_scene_collection(name, source_scene):
    """Find a unique authored Collection by *exact* fallback identity.

    This is a deliberately low-confidence fallback when the traced Render
    Layers View Layer has no useful directly rendered geometry (e.g. an
    indirect-only reflection or shadow layer). It is scoped to the actual
    source SCENE and never reads the active UI View Layer.

    A matching Collection need not be directly visible: rendered RGB can be
    produced from AOV/indirect-only data that still belongs to a real asset.
    Never select by object counts or arbitrary substring similarity.
    """
    if source_scene is None or getattr(source_scene, 'collection', None) is None:
        return '', 'missing source Scene Collection hierarchy'
    records = []

    def collect(coll, path, depth):
        if depth > 60:
            return
        path = path + (coll.name,)
        # A collection may be linked through multiple parent paths. Track
        # ancestry, not a global seen-set, so valid paths are not discarded.
        if id(coll) in depth_stack:
            return
        if any(p.lower().endswith('.ignore') for p in path):
            return
        records.append({'path': path,
                        'objects': [obj.name for obj in coll.objects]})
        depth_stack.add(id(coll))
        try:
            for child in coll.children:
                collect(child, path, depth + 1)
        finally:
            depth_stack.discard(id(coll))

    depth_stack = set()
    for child in source_scene.collection.children:
        collect(child, (), 0)
    match, explanation = name_match(name, records)
    if not match:
        return '', explanation
    return match, 'unique Collection identity in traced render source Scene: ' + explanation


def related_output_owner(chosen, output_name, source_name, peer_records):
    """Use exact source-local identity to scope nested Collection comparisons.

    A File Output can carry many unrelated passes from one character. The
    source peer must belong to the same named collection branch before its
    render-inclusion flags can veto a nested group. An ambiguous name is
    treated as unresolved rather than a reason to guess ownership.
    """
    if not chosen:
        return False, ''
    candidate, _ = name_match(output_name, peer_records)
    if not candidate:
        candidate, _ = name_match(source_name, peer_records)
    return bool(candidate and (candidate == chosen or
                               candidate.startswith(chosen + '/') or
                               chosen.startswith(candidate + '/'))), candidate
