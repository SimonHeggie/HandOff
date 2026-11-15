"""Operational manual text. Tag and blend mappings are defined in the XML registries."""
from html import escape
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from branding import NAME

TOPICS = [
    ('Collection hierarchy and group names', [
        ('p', '{product} uses Blender Collection ancestry to organise grouped exports. File Output socket order determines the final layer order. A Collection can appear in separate group instances when other artwork falls between its outputs.'),
        ('p', 'When repeated groups need distinguishing names, {product} uses a relevant child Collection or exported layer name. Original Collection names are preserved wherever the result remains unambiguous. Group and paint layers may share the same name.'),
        ('p', 'PSD and PSB group colour labels follow Blender Collection colour tags. Paint layers follow their owning Collection label. An explicitly untagged Collection stops ancestor colour inheritance, including ancestors removed by `.ungroup`. SVG displays untagged highlights as white; PSD maps them to its native Grey label. The receiving PSD editor controls the brightness of that swatch. Colour labels affect document organisation only.'),
        ('p', 'An output covering several Collections can remain at the document root. Check Export Status prints source Collection paths and a preview of the output hierarchy in the Blender terminal.'),
    ]),
    ('Dot suffixes and blend modes', [
        ('p', '{product} interprets recognised dot suffixes on authored output names. A suffix can specify a blend mode or an export operation. It is removed from the displayed layer name after the instruction is applied.'),
        ('code', 'Highlight.add -> Highlight (Add)\nShadow.multiply -> Shadow (Multiply)'),
        ('p', 'If a strict majority of a group\'s direct pixel layers use the same non-Normal blend mode, {product} can apply that mode to their group and set the affected children to Normal. Check the composite when mixing modes or working between editors.'),
        ('p', 'OpenEXR commonly uses dot-separated channel identifiers such as `Layer.R`. {product}\'s dot suffixes are authoring directives defined by {product}; OpenEXR channel names have separate semantics.'),
    ]),
    ('Collection export operations', [
        ('p', 'A Collection with `.merge` is rasterised to one paint layer. The exported paint layer takes the Collection name with the suffix removed. Child outputs are composited in their File Output order.'),
        ('code', 'Artwork.merge\n  Base\n  Details\n\nExport: Artwork (paint layer)'),
        ('p', '`.ungroup` removes a Collection container and promotes its children to the next retained ancestor. `.ignore` omits its subtree. `.ref` keeps reference artwork hidden in PSD and marked as reference in OCA.'),
        ('p', 'Do not use `.merge` and `.ungroup` together on the same Collection. A merge applies to a consecutive group run, preserving the overall layer order. Merging layers with backdrop-dependent blends may change the composite.'),
    ]),
    ('PSD/PSB colour handling', [
        ('p', 'For 8-bit and 16-bit display-referred PSD/PSB exports, {product} embeds the PNG source ICC profile when present and otherwise assigns sRGB. The 16-bit path preserves the PNG channel values during transfer.'),
        ('p', '32-bit exports preserve scene-linear HDR pixels. The standard Blender Rec.709 working space uses a corresponding linear RGB ICC profile. When a custom OCIO override is detected, the writer reports this and leaves the profile unassigned.'),
        ('p', 'PSD and PSB support group and paint-layer colour labels. {product} reads Collection colour tags and applies the nearest supported Photoshop label colour. Editor support for displaying those labels varies.'),
    ]),
]


def _inline_html(s):
    s=s.replace('{product}',NAME)
    return ''.join('<code>'+escape(part[1:-1])+'</code>' if part.startswith('`') else escape(part)
                   for part in re.split(r'(`[^`]+`)', s))


def as_markdown():
    lines=[]
    for title, entries in TOPICS:
        lines.extend(['## '+title,''])
        for kind, val in entries:
            if kind=='code':lines.extend(['```text',val,'```',''])
            else:lines.extend([val.replace('{product}',NAME),''])
    return '\n'.join(lines)


def as_html():
    # Only used as the combined generator's intermediate input. The paginated
    # manual assigns these paragraphs to their subject-specific pages.
    chunks=['<section id="collection-groups" class="chapter"><h2>Collection hierarchy</h2>']
    for title, entries in TOPICS:
        chunks.append('<h3>'+escape(title)+'</h3>')
        for kind,val in entries:
            chunks.append('<pre><code>'+escape(val)+'</code></pre>' if kind=='code' else '<p>'+_inline_html(val)+'</p>')
    chunks.append('</section>')
    return ''.join(chunks)
