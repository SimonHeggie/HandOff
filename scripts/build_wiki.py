#!/usr/bin/env python3
"""Build a navigable GitHub Wiki mirror from HandOff's existing manual.

Source of truth: handoff/manual/*.html and the two Markdown reference tables.
The generated pages are publication artifacts, never independently edited.

Dependencies: beautifulsoup4==4.14.3, markdownify==1.2.2.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from markdownify import markdownify as md

WIKI = 'https://github.com/SimonHeggie/HandOff/wiki'
REPOSITORY = 'https://github.com/SimonHeggie/HandOff'
PAGES = [
    ('MANUAL.html', 'Getting-started', 'Getting started'),
    ('groups.html', 'Collection-hierarchy', 'Collection hierarchy'),
    ('psd.html', 'PSD-and-PSB-colour', 'PSD / PSB colour'),
    ('vectors.html', 'SVG-and-vector-artwork', 'SVG / Vector Artwork'),
    ('tags.html', 'Tag-compatibility', 'Tag compatibility'),
    ('tags-operations.html', 'Group-and-export-directives', 'Group and export directives'),
    ('tags-spine.html', 'Spine-directives', 'Spine directives'),
    ('generator.html', 'Photoshop-Generator', 'Photoshop Generator'),
    ('exr-suffixes.html', 'EXR-suffixes-and-blending', 'EXR-style suffixes and blending'),
    ('openexr.html', 'OpenEXR-channels', 'OpenEXR channels'),
    ('sources.html', 'Sources-and-credits', 'Sources and credits'),
]
REFERENCE_PAGES = [
    ('LAYER_TAGS.md', 'Layer-tag-reference', 'Layer-tag reference'),
    ('BLEND_MODES.md', 'Blend-mode-reference', 'Blend-mode reference'),
]
LINKS = {name:slug for name,slug,_ in PAGES + REFERENCE_PAGES}


def converted_href(value: str) -> str:
    """Turn relative chapter/document links into cross-wiki links."""
    if not value or value.startswith('#'):
        return value
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or value.startswith('//'):
        return value
    # Manual chapter links are sibling filenames; keep fragment IDs unchanged.
    relative = Path(parts.path).name
    slug = LINKS.get(relative)
    if slug:
        return f'{WIKI}/{slug}' + (f'#{parts.fragment}' if parts.fragment else '')
    # Any non-wiki local reference stays linked to its canonical source in Git.
    return f'{REPOSITORY}/blob/main/handoff/manual/{parts.path}' + (f'#{parts.fragment}' if parts.fragment else '')


def html_to_wiki(source: Path, title: str) -> str:
    html = BeautifulSoup(source.read_text(encoding='utf-8'), 'html.parser')
    main = html.find('main')
    if main is None:
        raise ValueError(f'{source}: missing main element')
    for element in main.select('nav, footer, .eyebrow, h1'):
        element.decompose()
    for a in main.find_all('a',href=True):
        a['href'] = converted_href(a['href'])
    # Retain all explicit HTML section/heading IDs, including those referenced
    # from other chapters. markdownify drops empty anchor elements, so insert
    # protected plaintext markers and restore them after conversion.
    markers = {}
    for i, node in enumerate(main.find_all(id=True)):
        marker = f'HANDOFFWIKIANCHOR{i}TOKEN'
        markers[marker] = node['id']
        node.insert_before(html.new_string('\n\n' + marker + '\n\n'))
    result = md(str(main), heading_style='ATX', bullets='-', table_infer_header=True,
                escape_underscores=False, escape_asterisks=False)
    for marker, anchorid in markers.items():
        result = result.replace(marker, f'<a id="{anchorid}"></a>')
    result = re.sub(r'\n{4,}', '\n\n\n', result).strip()
    return (f'# {title}\n\n'
            f'> Synced from the [HandOff offline manual]({REPOSITORY}/blob/main/handoff/manual/{source.name}). '
            f'Keep edits in the source manual; this wiki copy is generated automatically.\n\n'
            f'{result}\n')


def render(source_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    home = ('# HandOff User Manual\n\n'
            '**Hit render, go home.**\n\n'
            'This wiki is a browsable copy of the [HandOff user manual]('
            f'{REPOSITORY}/tree/main/handoff/manual), reproduced from the source in the repository. '
            'It documents the currently implemented compositor-based layered artwork exporter, '
            'not proposed future features.\n\n'
            'Start with **[Getting started](Getting-started)**, or choose a chapter below.\n\n'
            '## Manual chapters\n\n')
    for _,slug,label in PAGES:
        home += f'- [{label}]({slug})\n'
    home += '\n## Reference tables\n\n'
    for _,slug,label in REFERENCE_PAGES:
        home += f'- [{label}]({slug})\n'
    home += ('\n## Downloads and support\n\n'
             f'- [Current alpha release (v0.7.51-alpha.1)]({REPOSITORY}/releases/tag/v0.7.51-alpha.1)'
             f' (or [all releases]({REPOSITORY}/releases))\n'
             f'- [Repository and project overview]({REPOSITORY})\n'
             f'- [Full offline HTML manual]({REPOSITORY}/blob/main/handoff/manual/MANUAL.html)\n\n'
             'The HTML manual and wiki use the same underlying documentation. The wiki is a **mirror**, '
             'not an additional source of truth.\n')
    (output_dir/'Home.md').write_text(home, encoding='utf-8')

    for name,slug,title in PAGES:
        page=source_dir/name
        if not page.is_file():
            raise FileNotFoundError(page)
        (output_dir/f'{slug}.md').write_text(html_to_wiki(page,title), encoding='utf-8')

    for name,slug,title in REFERENCE_PAGES:
        page=source_dir/name
        if not page.is_file():
            raise FileNotFoundError(page)
        original=page.read_text(encoding='utf-8')
        # Wiki pages should not link to relative Git files that do not exist in the wiki.
        original=re.sub(r'\]\(([^)#]+\.md)(#[^)]+)?\)', lambda m: ']('+converted_href(m[1]+(m[2] or ''))+')', original)
        (output_dir/f'{slug}.md').write_text(
            f'> Synced from [the source reference]({REPOSITORY}/blob/main/handoff/manual/{name}).\n\n'+original,
            encoding='utf-8')

    sidebar = '**[HandOff Manual](Home)**\n\n'
    for _,slug,title in PAGES:
        sidebar += f'- [{title}]({slug})\n'
    sidebar += '\n**References**\n\n'
    for _,slug,title in REFERENCE_PAGES:
        sidebar += f'- [{title}]({slug})\n'
    (output_dir/'_Sidebar.md').write_text(sidebar, encoding='utf-8')
    (output_dir/'_Footer.md').write_text(
        f'[Source manual]({REPOSITORY}/tree/main/handoff/manual) · '
        f'[HandOff repository]({REPOSITORY}) · '
        'Generated from source; please report errors in the main repository.\n',
        encoding='utf-8')
    print(f'Generated {len(PAGES)+len(REFERENCE_PAGES)+3} wiki pages in {output_dir}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('handoff/manual'))
    parser.add_argument('--output', type=Path, default=Path('.wiki-build'))
    args = parser.parse_args()
    render(args.source,args.output)