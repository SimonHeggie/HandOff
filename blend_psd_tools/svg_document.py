"""Self-contained, ordered SVG document using Comp-IO's existing layer tree.

Writer input order is File Output TOP to BOTTOM. SVG paint order is bottom
first, so we reverse each sibling list without changing the saved stack.
"""

try:
    from .branding import LOG_PREFIX
except ImportError:
    from branding import LOG_PREFIX
import base64
import io
import re
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from .layer_stack import prepared_entries, build_stack, strip_tags, tags
    from .group_blends import promoted_blend, effective_layer_mode, canonical_mode
    from .disabled_layers import notice
except ImportError:
    from layer_stack import prepared_entries, build_stack, strip_tags, tags
    from group_blends import promoted_blend, effective_layer_mode, canonical_mode
    from disabled_layers import notice

SVG_NS = 'http://www.w3.org/2000/svg'
INK_NS = 'http://www.inkscape.org/namespaces/inkscape'
# Inkscape's actual namespace uses www.inkscape.org, not inkscape.org.
ET.register_namespace('', SVG_NS)
ET.register_namespace('inkscape', INK_NS)


def _tag(element):
    return f'{{{SVG_NS}}}{element}'


def _ink(element):
    return f'{{{INK_NS}}}{element}'


# Inkscape's highlight colour reader expects #RRGGBB, not SVG paint RGBA.
INKSCAPE_COLORS = {
    'NO_COLOR': '#ffffff',
    'RED': '#d95858', 'ORANGE': '#e19a42', 'YELLOW': '#e7d14f',
    'GREEN': '#65b36b', 'BLUE': '#6598e4', 'VIOLET': '#a37be0',
    'MAGENTA': '#d576c2', 'GRAY': '#858585',
}


def _highlight(node, color):
    value = INKSCAPE_COLORS.get(str(color or '').upper())
    if value:
        node.set(_ink('highlight-color'), value)


def _inherit_highlight(element, parent_color):
    """Editor highlight metadata is not an inherited SVG/CSS paint property."""
    color = element.get(_ink('highlight-color')) or parent_color
    if color and element.tag in (_tag('g'), _tag('use'), _tag('path'), _tag('image'), _tag('text')):
        element.set(_ink('highlight-color'), color)
    for child in element:
        _inherit_highlight(child, color)


def _blend(element, mode):
    mode = canonical_mode(mode)
    if mode == 'normal':
        return
    css_mode = {'add': 'plus-lighter', 'multiply':'multiply', 'screen':'screen',
                'overlay':'overlay', 'darken':'darken', 'lighten':'lighten'}.get(mode)
    if css_mode is None:
        raise ValueError('Unsupported SVG blend mode: ' + mode)
    element.set('style', 'mix-blend-mode:' + css_mode + ';isolation:isolate')


def empty_raster_diagnostic(label, entry):
    """Describe a missing raster fallback without claiming a vector bake succeeded."""
    source = str(entry.get('source_view_layer') or '').strip()
    reason = str(entry.get('vector_reason') or '').strip()
    msg = f'{LOG_PREFIX} SVG EMPTY RASTER: ' + str(label) + ': the PNG cache contains zero alpha.'
    if source:
        msg += ' View Layer: ' + source + '.'
    if reason:
        msg += ' Vector fallback reason: ' + reason + '.'
    msg += (' The rendered Image pass has no visible pixels. The Depth pass alone'
            ' cannot supply colour/alpha. For Grease Pencil, check View Layer >'
            ' Filter > Grease Pencil, object and layer render visibility, drawing'
            ' View Layer assignment, both GP lighting switches, and material'
            ' Fill/Stroke Holdout. Holdout erases GP paint; it does not enable'
            ' alpha. Objects containing only holdouts can render fully transparent.'
            ' For a painted fading sprite, disable Holdout and use Color Ramp stop alpha. A new Blender'
            ' render is required to repair a transparent raster cache.')
    return msg


def _png_bytes_for(item, path, width, height):
    """Unchanged cached PNG for normal art; encode .merge pixels to PNG."""
    prepared = item.get('pixels')
    if prepared is None:
        path = Path(path)
        if path.suffix.lower() != '.png':
            raise ValueError('SVG raster image requires a PNG cache: ' + str(path))
        return path.read_bytes()
    from PIL import Image
    import numpy as np
    arr = (np.clip(prepared, 0, 1) * 255 + .5).astype('uint8')
    if arr.shape != (height, width, 4):
        raise ValueError('Merged PNG dimensions do not match SVG document')
    out = io.BytesIO()
    Image.fromarray(arr, 'RGBA').save(out, format='PNG')
    return out.getvalue()


def _can_unwrap(element):
    """Removing a repeated label must not remove opacity or other styling."""
    metadata = {'id', _ink('label'), 'data-compio-object', 'data-compio-layer', 'opacity'}
    return (set(element.attrib) <= metadata and float(element.get('opacity', '1')) == 1.0)


def write_svg_document(job, inputs, *, logger=print):
    """Produce one layered SVG with editable paths and self-contained PNG fallbacks."""
    from PIL import Image
    from merge_groups import collapse_merged_groups
    from psd_worker import read_rgba, merge_layers
    from tag_registry import effective_profile, translate_label

    if not inputs:
        raise ValueError('No source layers for SVG')
    with Image.open(inputs[0][1]) as im:
        width, height = im.size
    grouped = job.get('hierarchy', 'GROUPS') == 'GROUPS'
    depth = int(job.get('depth', 8))
    if job.get('flatten'):
        layer_name = Path(job['dest']).stem
        stack = {'children':[{'kind':'layer','name':layer_name,
                              'item':{'entry':{'name':layer_name},'source':None,
                                      'pixels':merge_layers(inputs, depth=depth),
                                      'mode':'normal','flags':set(), 'merged':True}}]}
    else:
        stack = build_stack(prepared_entries(inputs, grouped))
    if depth not in (8, 16):
        raise ValueError('SVG PNG fallback requires 8-bit or 16-bit cache')

    def load_pixels(item):
        return read_rgba(item['source'], source_depth=depth)

    collapse_merged_groups(stack, load_pixels, (width, height), logger=logger)
    root = ET.Element(_tag('svg'), {'version':'1.1', 'width':str(width), 'height':str(height),
                                   'viewBox':f'0 0 {width} {height}'})
    ET.SubElement(root, _tag('title')).text = Path(job['dest']).stem
    counters = {'vector':0, 'raster':0, 'merged':0, 'groups':0, 'layers':0}
    profile = effective_profile(job.get('tag_profile', 'PASSTHROUGH'), 'SVG')

    def display_label(name, scope):
        name = strip_tags(name)
        try:
            translated, warnings = translate_label(name, name, profile, scope)
            for warning in warnings:
                logger(f'{LOG_PREFIX} SVG TAG:', warning)
            return translated
        except Exception as exc:
            logger(f'{LOG_PREFIX} SVG TAG WARNING:', exc)
            return name

    # The SVG root is mandatory, but an extra root group is optional. An
    # existing common authored Collection is already in build_stack and needs
    # no synthetic wrapper; do not duplicate it here.
    root_target = root
    root_mode = job.get('svg_root_mode', 'AUTO')
    if root_mode == 'NAMED':
        root_name = str(job.get('svg_root_name') or '').strip() or Path(job['dest']).stem
        root_target = ET.SubElement(root, _tag('g'), {
            'id': 'compio-root', _ink('label'): root_name,
        })

    def write_children(children, target, promoted=None):
        for node in reversed(children):
            if node['kind'] == 'group':
                group = ET.SubElement(target, _tag('g'), {
                    'id':'compio-group-' + str(counters['groups']),
                    _ink('groupmode'):'layer',
                    _ink('label'):display_label(node['name'], 'group')})
                # Inkscape displays highlight colours on its layer entries.
                # Without an explicit colour, it invents one based on the ID.
                # Untagged Collections use Blender's white; tagged Collections
                # use the Blender-authored colour already carried by Comp-IO.
                _highlight(group, node.get('sheet_color') or 'NO_COLOR')
                if 'ref' in tags(node['raw']) or 'reference' in tags(node['raw']):
                    group.set('display','none')
                counters['groups'] += 1
                mode = promoted_blend(node)
                _blend(group, mode or 'normal')
                write_children(node['children'], group, mode)
                continue
            item = node['item']
            label = display_label(node['name'], 'layer')
            entry = item.get('entry', {})
            layer = ET.SubElement(target, _tag('g'), {
                'id':'compio-layer-' + str(counters['layers']),
                _ink('label'):label})
            for key in ('source_identity','source_view_layer','collection_path'):
                if entry.get(key):layer.set('data-asset-'+key.replace('_','-'),str(entry[key]))
            counters['layers'] += 1
            _highlight(layer, item.get('inherited_color'))
            if item.get('flags', set()) & {'ref', 'reference', 'disabled'}:
                layer.set('display','none')
            if entry.get('render_placeholder'):
                notice(job, entry['name'] + ': hidden blank SVG placeholder created')
            _blend(layer, effective_layer_mode(item, promoted))
            candidate = entry.get('vector_svg', '') if not job.get('bake_svg_png') and not item.get('merged') else ''
            source = Path(candidate) if candidate else None
            use_vector = source is not None and source.is_file()
            if use_vector:
                from svg_hybrid import resolve_hybrid_source
                use_vector = resolve_hybrid_source(source, depth=depth, logger=logger)
            if use_vector:
                inner = ET.parse(source).getroot()
                if inner.tag != _tag('svg'):
                    raise ValueError('Vector source is not an SVG document: ' + str(source))
                if inner.get('viewBox') != f'0 0 {width} {height}':
                    raise ValueError('SVG viewBox differs from render size: ' + str(source))
                # Remove redundant wrappers when source Grease Pencil object
                # and layer merely repeat the exported artwork layer name.
                svg_children = [child for child in list(inner)
                                if child.tag in (_tag('g'), _tag('path'), _tag('text'), _tag('image'), _tag('use'))]
                # Older retained sources may include the collection ancestry
                # already supplied by the document's outer stack.
                for component in entry.get('collection_path','').split('/'):
                    if not component or 'ungroup' in tags(component):continue
                    if len(svg_children)!=1:break
                    wrapper=svg_children[0]
                    if (not wrapper.get('data-compio-collection') or
                            wrapper.get(_ink('label'))!=strip_tags(component) or
                            any(wrapper.get(k) for k in ('style','opacity','transform','display','filter','mask','clip-path'))):break
                    svg_children=list(wrapper)
                # When the single GP object and its only internal layer both
                # repeat the destination name, omit these redundant wrappers.
                # Keep genuinely distinct layers and their source order.
                for marker in ('data-compio-object', 'data-compio-layer'):
                    if len(svg_children) != 1 or svg_children[0].tag != _tag('g'):
                        break
                    wrapper = svg_children[0]
                    if (wrapper.get(marker, '').casefold() != label.casefold() or
                            (wrapper.get('data-compio-layer', label).casefold() != label.casefold()) or
                            not _can_unwrap(wrapper)):
                        break
                    svg_children = list(wrapper)
                # Every imported vector SVG starts its own local ID sequence.
                # Prefix these IDs to avoid duplicate IDs in the combined file.
                from svg_metadata import qualify_imports
                qualify_imports(svg_children,entry.get('source_identity') or (entry.get('collection_path'),entry['name'],entry.get('slug')))
                for child in svg_children:
                    layer.append(child)
                    _inherit_highlight(child, layer.get(_ink('highlight-color')))
                counters['vector'] += 1
            else:
                src = item.get('source')
                data = _png_bytes_for(item, src, width, height)
                image = ET.SubElement(layer, _tag('image'), {
                    'id':'compio-image-' + str(counters['layers'] - 1),
                    _ink('label'):label, 'x':'0', 'y':'0', 'width':str(width),
                    'height':str(height), 'preserveAspectRatio':'none',
                    'href':'data:image/png;base64,' + base64.b64encode(data).decode('ascii')})
                for key,value in layer.attrib.items():
                    if key.startswith('data-asset-'):image.set(key,value)
                counters['raster'] += 1
                if item.get('merged'):
                    counters['merged'] += 1
                # A transparent fallback is easy to mistake for missing SVG
                # geometry. Report this without modifying any pixels.
                with Image.open(io.BytesIO(data)) as fallback_img:
                    if (not entry.get('render_placeholder') and 'A' in fallback_img.getbands() and
                            fallback_img.getchannel('A').getextrema()[1] == 0):
                        logger(empty_raster_diagnostic(label, entry))
            logger(f'{LOG_PREFIX} SVG LAYER:', label, '| vector' if use_vector else '| PNG')
            from conversion_policy import record
            job['_publication_view_layer']=entry.get('source_view_layer','')
            job['_publication_source_svg']=entry.get('vector_svg','')
            if use_vector and source.with_suffix('.vectors.json').is_file():
                import json
                model=json.loads(source.with_suffix('.vectors.json').read_text())
                for obj in model['objects']:
                    record(job,obj,'NATIVE_EDITABLE' if obj.get('svg_kind')!='RASTER' else 'RASTER_WITH_SOURCE',
                        source_svg=str(job['dest']),validation='SVG source and reader fixtures')
            else:
                record(job,dict(name='',collection_parts=entry.get('collection_path','').split('/')),
                    'SKIPPED' if entry.get('render_placeholder') else 'NATIVE_EDITABLE',
                    destination_layer=label,source_feature='raster',source_svg=str(job['dest']))

    write_children(stack['children'], root_target)
    from svg_instances import link_instances
    link_instances(root, logger=logger)
    from svg_metadata import annotate
    annotate(root,scope='document',manifest=[{key:entry.get(key) for key in
        ('name','source_identity','source_view_layer','collection_path','render_disabled')}
        for entry,path in inputs])
    destination = Path(job['dest'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not job.get('overwrite', True):
        raise FileExistsError('Overwrite disabled: ' + str(destination))
    staging = destination.with_name(destination.stem + '.writing.svg')
    try:
        ET.ElementTree(root).write(staging, encoding='utf-8', xml_declaration=True)
        if staging.stat().st_size < 100:
            raise ValueError('SVG document unexpectedly empty')
        staging.replace(destination)
    finally:
        staging.unlink(missing_ok=True)
    logger(f'{LOG_PREFIX} SVG COMPLETE:', destination, '| vectors:', counters['vector'],
           '| raster layers:', counters['raster'], '| merged:', counters['merged'])
    return str(destination)
