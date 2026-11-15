"""Generate offline topic pages from the XML registries used by the exporter.

Run standalone with Python 3.13 after generate_manual.py, or imported by it.
No Markdown viewer, third-party parser or internet required.
"""
from pathlib import Path
from html import escape as esc
from workflow_notes import as_html
import xml.etree.ElementTree as ET
import re

root=Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(root.parent))
from branding import VERSION, NAME as BRAND_NAME, SUBTITLE as BRAND_SUBTITLE, TAGLINE as BRAND_TAGLINE, OVERVIEW as BRAND_OVERVIEW

product=esc(BRAND_NAME)
version=VERSION
out=root.parent/'manual'
tags=ET.parse(root/'tags.xml').getroot()
blends=ET.parse(root/'blend_modes.xml').getroot()
behaviors=sorted(tags.findall('./behaviors/behavior'),key=lambda b:int(b.get('rank')))
modes=sorted(blends.findall('./modes/mode'),key=lambda x:int(x.get('rank')))
sources={x.get('id'): x for x in tags.findall('./sources/source')}
profiles={'spine':'Spine','generator':'Photoshop Generator','oca':'OCA / Krita'}
assert tags.get('schema')=='explicit-tag-mapping-v1'
assert len(behaviors)==26 and len(modes)==111

# Keep the full Markdown edition as a searchable text reference.
old_tags=(out/'LAYER_TAGS.md').read_text(encoding='utf-8')
old_blends=(out/'BLEND_MODES.md').read_text(encoding='utf-8')
md='''# {product} - User Manual

**Layered Asset Interchange & Publishing for Blender**

**One render. Every deliverable.**

## Contents

1. [Getting started](#getting-started)
2. [Layer Tags](#layer-tags)
3. [Photoshop Generator](#photoshop-generator)
4. [Blend Modes](#blend-modes)
5. [OpenEXR naming reference](#openexr-naming-reference)
6. [Credits and source documentation](#credits-and-source-documentation)

## Getting started

Choose **Tag Compatibility** independently for each Additional Export.
Use **Check Export Status** to review conversions and warnings.
No Conversion keeps authored naming. Unsupported conversions are reported and retained.

For the best-rendered tables and quick navigation, open **MANUAL.html** in a web browser.

---

## Layer Tags

'''
# Drop duplicate document-level title; the sections below are clearly delimited.
md+='\n'.join(old_tags.splitlines()[1:]).replace('## Photoshop Generator syntax','## Photoshop Generator',1)
md+='\n\n---\n\n## Blend Modes\n\n'+'\n'.join(old_blends.splitlines()[1:])
md+='\n\n## Credits and source documentation\n\n'
for src in sources.values():
    md+=f"- [{src.get('by')} - {src.get('title')}]({src.get('url')})\n"
(out/'MANUAL.md').write_text(md, encoding='utf-8')

def e(t):return esc(str(t if t is not None else '-'),quote=True)
def code(t):return f'<code>{e(t)}</code>' if t not in (None,'','-') else '<span class="muted">-</span>'
def badge(t):
    t=t or 'none';return f'<span class="chip chip-{e(t)}">{e(t)}</span>'
def desc(t):return e(t).replace('\n','<br>')

def profile_syntax(b,profile):
    for x in b.findall('./target'):
        if x.get('profile')==profile:
            return code(x.get('syntax'))
    return '<span class="muted">-</span>'

def table(headers, rows, cls=''):
    th=''.join('<th scope="col">'+e(x)+'</th>' for x in headers)
    body=''.join('<tr>'+''.join('<td>'+val+'</td>' for val in row)+'</tr>' for row in rows)
    return f'<div class="table-wrap {cls}"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'

quick=[]
for b in behaviors:
    quick.append([f'<a href="#tag-{e(b.get("id"))}">{e(b.get("label"))}</a>',
            profile_syntax(b,'spine'), profile_syntax(b,'generator'),profile_syntax(b,'oca')])
quick_table=table(['Function - most common first','Spine','Photoshop Generator','OCA / Krita'],quick,'tag-quick')

beh_sections=[]
for b in behaviors:
    targets=b.findall('./target')
    rows=[]
    for t in targets:
        rows.append([f'<strong>{e(profiles.get(t.get("profile"), t.get("profile")))}</strong>',
                     badge(t.get('equivalence')),code(t.get('syntax')),
                     code(t.get('emit')),e(t.get('representation')),desc(t.get('note'))])
    author=b.find('./authoring');caution=b.findtext('./caution')
    note=(f'<p><strong>Blender authoring:</strong> {code(author.get("syntax"))}</p>' if author is not None else '')
    if caution: note+=f'<p class="caution"><strong>Caution:</strong> {desc(caution)}</p>'
    beh_sections.append(f'''<section class="rule" id="tag-{e(b.get('id'))}">
<h3><span class="num">{e(b.get('rank'))}</span> {e(b.get('label'))}</h3>
<p>{desc(b.get('description'))} <span class="muted">Scope: {e(b.get('scope'))}.</span></p>
{table(['Destination','Support','Actual tag / syntax','Emission template','Representation','Notes'],rows)}
{note}</section>''')

source_rules=tags.findall('./sourceTokens/token')
srcrows=[]
for t in sorted(source_rules,key=lambda r:(int(next((b.get('rank') for b in behaviors if b.get('id')==r.get('behavior')),'999')),r.get('profile',''),r.get('template',''))):
    srcrows.append([code(t.get('template')),e(t.get('profile')),f'<a href="#tag-{e(t.get("behavior"))}">{e(t.get("behavior"))}</a>',e(t.get('scope'))])

grammar_rows=[]
for t in tags.findall('./generatorGrammar/rule'):
    grammar_rows.append([e(t.get('profile')),code(t.get('example')),e(t.get('id')),desc(t.get('description'))])

# Keep the long tail of blend modes available without making the page endless.
mode_rows=[]
for m in modes:
    apps={a.get('id'):a for a in m.findall('app')}
    ae=apps.get('after-effects');ps=apps.get('photoshop')
    ps_val=code(ps.get('name')) if ps is not None else '<span class="muted">No vetted mapping</span>'
    ae_val=code(ae.get('name')) if ae is not None else '<span class="muted">No vetted mapping</span>'
    if ae is not None and ae.get('status')=='approximation': ae_val+=' '+badge('approximation')
    mode_rows.append([code(m.get('oca')),code(m.get('krita')),ps_val,ae_val])

# Same XML registry, deliberately NOT parsed as suffix tokens in runtime.
exr = tags.find('exrConventions')
if exr is None or exr.get('schema') != 'openexr-naming-v1':
    raise ValueError('Missing OpenEXR reference in tags.xml')
exr_channels = table(['Channel','Meaning','Type','Specification status'], [
    [code(ch.get('name')), e(ch.get('meaning')),e(ch.get('kind')),e(ch.get('status'))]
    for ch in exr.findall('./channels/channel')])
exr_patterns = table(['Pattern','Interpretation'], [
    [code(x.get('syntax')), e(x.get('meaning'))] for x in exr.findall('./patterns/pattern')])
exr_passes = table(['Blender pass group','Pass name','Specification status'], [
    [e(x.get('category')),code(x.get('name')),e(x.get('status'))]
    for x in exr.findall('./blenderPasses/pass')])
exr_html = (
    '<section class="chapter" id="exr"><h2>4. OpenEXR Channels and Render Passes</h2>'
    '<p>OpenEXR organises pixel data into named channel groups. The naming convention is '
    '<code>Layer.Channel</code>. OpenEXR has <strong>no standard name tags for Multiply, '
    'Add, Screen, Ignore, Merge or draw order.</strong></p>'
    '<h3>Channel names</h3>' + exr_channels +
    '<h3>Layer/channel naming patterns</h3>' + exr_patterns +
    '<h3>Blender render pass names (application-specific)</h3>'
    '<p>Blender groups passes by purpose. Actual EXR channel names depend on '
    'the render settings and File Output configuration.</p>' + exr_passes +
    '</section>'
)

credits=''.join(f'<li><a href="{e(s.get("url"))}" target="_blank" rel="noopener noreferrer">{e(s.get("by"))}</a> - {e(s.get("title"))}</li>' for s in sources.values())

style='''
:root{color-scheme:light dark;--bg:#f9fafb;--surface:#fff;--ink:#1e293b;--muted:#64748b;--line:#dce3eb;--accent:#166d9c;--sub:#edf5fa;--link:#096da4}
@media(prefers-color-scheme:dark){:root{--bg:#111827;--surface:#1c2532;--ink:#e9eef6;--muted:#acb8ca;--line:#39475a;--accent:#82d1fa;--sub:#263849;--link:#85d0fb}}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:1rem}body{background:var(--bg);color:var(--ink);margin:0;font:15.5px/1.65 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}code{font:0.91em/1.4 ui-monospace,"Liberation Mono",Consolas,monospace;background:var(--sub);padding:.13em .28em;border-radius:4px;overflow-wrap:anywhere}
.layout{display:grid;grid-template-columns:250px minmax(0,1fr);max-width:1700px;margin:0 auto;min-height:100vh}.sidebar{border-right:1px solid var(--line);padding:30px 19px;position:sticky;top:0;height:100vh;overflow:auto}.sidebar .brand{font-weight:800;letter-spacing:-.02em;font-size:1.24rem}.sidebar small{display:block;color:var(--muted);margin:.1rem 0 1.5rem}.sidebar nav a{display:block;margin:.08rem 0;padding:.48rem .67rem;border-radius:6px}.sidebar nav a:hover{background:var(--sub)}.sidebar .sub{padding-left:1.45rem;font-size:.86rem}.content{min-width:0;padding:34px clamp(20px,4vw,72px) 90px}main{max-width:1210px;margin:auto}h1{font-size:2.2rem;letter-spacing:-.045em;margin:.6rem 0 0}h2{font-size:1.68rem;letter-spacing:-.02em;margin:3rem 0 .7rem;border-bottom:1px solid var(--line);padding-bottom:.65rem}h3{font-size:1.14rem;margin:2rem 0 .5rem}p{margin:.55rem 0 1.15rem}.eyebrow{font-weight:700;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);font-size:.73rem}.lead{font-size:1.06rem;max-width:850px}.muted{color:var(--muted)}.rule{padding-top:5px;scroll-margin-top:20px}.num{font-size:.8rem;border-radius:99px;background:var(--sub);color:var(--accent);padding:.25rem .48rem;margin-right:.45rem;font-variant-numeric:tabular-nums}.chapter{margin-top:2.5rem;scroll-margin-top:20px}.table-wrap{max-width:100%;overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:var(--surface);margin:16px 0 20px;overscroll-behavior-x:contain}table{border-collapse:collapse;width:100%;min-width:730px;font-size:.86rem;line-height:1.45}th,td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left;overflow-wrap:anywhere}th{background:var(--sub);font-weight:700;position:sticky;top:0}tbody tr:last-child td{border-bottom:0}tbody tr:hover{background:color-mix(in srgb,var(--accent) 4%,transparent)}.tag-quick td:first-child{min-width:205px}.chip{white-space:nowrap;display:inline-block;padding:.14rem .43rem;border-radius:6px;background:var(--sub);font-size:.78rem}.chip-none{color:var(--muted)}.caution{border-left:3px solid #d99a35;padding:.5rem 1rem;background:var(--sub);border-radius:0 6px 6px 0}.info{background:var(--sub);padding:14px 18px;border-radius:8px;margin:20px 0}.compact{max-width:850px}.toc-mobile{display:none}details{border:1px solid var(--line);border-radius:8px;background:var(--surface);padding:12px 16px;margin:1rem 0}summary{cursor:pointer;font-weight:650}ul{padding-left:1.3rem}.footer{margin-top:4rem;padding-top:1.3rem;border-top:1px solid var(--line);color:var(--muted)}
@media(max-width:900px){.layout{display:block}.sidebar{display:none}.content{padding:20px 16px 80px}.toc-mobile{display:block}.toc-mobile a{display:inline-block;margin:0 12px 7px 0}.content h1{font-size:1.8rem}th,td{padding:8px 9px}}@media print{.layout{display:block}.sidebar{display:none}.content{padding:0}details{break-inside:avoid}details>div{display:block}}
'''

html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{product} - User Manual</title><style>{style}</style></head>
<body><div class="layout"><aside class="sidebar"><div class="brand">{product}</div><small>Offline user manual · v{version}</small><nav aria-label="Topics">
<a href="#about">About {product}</a><a href="#start">Getting Started</a><a href="#collection-groups">Collection Groups</a><a class="sub" href="#dot-suffixes">Dot suffixes</a><a href="#tags">Layer Tags</a><a href="#tag-quick">Tag conversion chart</a>
<a class="sub" href="#tag-full">Detailed tag rules</a><a class="sub" href="#tag-sources">Recognised source tags</a>
<a href="#generator">Photoshop Generator</a><a href="#modes">Blend Modes</a><a class="sub" href="#modes-extended">Extended blend modes</a><a href="#exr">OpenEXR</a><a href="#credits">Sources &amp; Credits</a></nav></aside>
<div class="content"><main><div class="eyebrow">Reference</div><h1>{product} User Manual</h1>
<p class="lead">Artwork hierarchy, export directives, blend modes and format compatibility.</p>
<div class="toc-mobile"><a href="#collection-groups">Groups and suffixes</a><a href="#tags">Layer Tags</a><a href="#generator">Generator</a><a href="#modes">Blend Modes</a><a href="#exr">OpenEXR</a><a href="#credits">Credits</a></div>
<section id="about" class="chapter"><h2>About {product}</h2>
<p><strong>{e(BRAND_SUBTITLE)}</strong></p><p><strong>{e(BRAND_TAGLINE)}</strong></p>
<p>{e(BRAND_OVERVIEW)}</p>
<p><strong>Designed by <a href="https://github.com/SimonHeggie" target="_blank" rel="noopener noreferrer">Simon Heggie</a>.</strong> Find updates on <a href="https://github.com/SimonHeggie" target="_blank" rel="noopener noreferrer">GitHub</a> or connect on <a href="https://www.linkedin.com/in/simon-heggie-94a1ba40/" target="_blank" rel="noopener noreferrer">LinkedIn</a>.</p>
<h3>Why {product}?</h3><p>Finishing the artwork shouldn't mean spending another day preparing deliverables. Exporting layers, rebuilding documents and distributing files after every update wastes time. Configure these handoffs once and reuse the same export settings after subsequent renders.</p><h3>Multiple deliverables from one render</h3>
<p>Configure PSD/PSB artwork, OCA projects, Spine-ready layers, OpenEXR passes, and PNG/JPEG/TIFF image sequences with independent export destinations and processing options. The native File Output node remains available without the add-on.</p>
<h3>Typical character handoff</h3>{table(['Department','Deliverable'],[['Art','Editable PSD'],['Animation','Spine-ready layers'],['Development','Game-ready sprites'],['Marketing','High-resolution promotional image'],['Production','Archived renders and passes']])}<h3>Project goals</h3><p>Reduce repetitive preparation, preserve layered artwork, support interoperable tools, and provide repeatable artist and technical-director handoffs. {product} complements Spine-IO.</p><h3>Open source</h3><p>{product} aims to support professional interchange without mandatory proprietary licensing and to let artists work in their preferred creative tools.</p><h3>What is still in development</h3>
<p>Network publishing, monitoring, synchronization, reusable output presets and automatic distribution are longer-term goals. {product} is an alpha-stage Blender add-on; check deliverables before production handoff.</p></section>
<section id="start" class="chapter"><h2>Getting started</h2><p>Select <strong>Tag Compatibility</strong> separately for each Additional Output. The default is <strong>No Conversion</strong>. Choose Spine, Photoshop Generator or OCA / Krita when needed. Flattening disables name conversion. <strong>Check Export Status</strong> reports unsupported translations.</p><div class="info"><strong>Safe fallback:</strong> Unsupported directives are retained verbatim and reported. Unknown directives are kept as entered. Passthrough keeps authored names unchanged. Blender Collection and socket names remain unchanged.</div><p>Tag conversion changes exported layer names. Render processing and blend modes are configured separately. Photoshop Generator can use compatible names when the exported document is opened in Photoshop.</p></section>
{as_html()}
<section id="tags" class="chapter"><h2>1. Layer Tags</h2><p>Browse the directive mappings below. Native OCA stores group and layer settings in metadata. Krita uses the <code>_reference_</code>, <code>_ignore_</code> and <code>_merge_</code> name tags when exporting OCA.</p>
<h3 id="tag-quick">Quick conversion chart</h3>{quick_table}<h3 id="tag-full">Detailed conversion rules</h3>{''.join(beh_sections)}
<h3 id="tag-sources">Explicit source tokens</h3><p>The registry recognises the following tokens exactly as shown.</p>{table(['Authored token','Origin','Function','Scope'],srcrows)}</section>
<section id="generator" class="chapter"><h2>2. Photoshop Generator</h2><p>Photoshop Generator reads layer and group names as asset export instructions. Give an asset its filename and use extensions, size prefixes or folder paths to control the output.</p>
{table(['Purpose','Valid syntax examples'],[
['JPEG quality',''.join([code('Logo.jpg5'), ' / ',code('Hero.jpg80%')])],['PNG asset depth',code('Icon.png8')+' / '+code('Photo.png24')+' / '+code('Button.png32')],['GIF / SVG',code('Animation.gif')+' / '+code('Shape.svg')],['Relative resize',code('200% Logo.png')+' / '+code('50% Icon.jpg')],['Absolute dimensions',code('300 x 200 Hero.jpg')+' / '+code('4in x 100 Banner.jpg')],['Wildcard dimensions',code('100x? Logo.png')+' / '+code('?x60in Banner.jpg')],['Multiple assets',code('Icon.png8, Icon.jpg90%')],['Subfolders',code('icons/Logo.png')+' / '+code('@2x/Hero.jpg')]])}
<p>Generator input restrictions include colons and asterisks. Do not combine absolute and percentage scaling on one asset; keep a separating space between dimension prefix and filename. See Adobe's cited documentation for authoritative syntax.</p>
<h3>Registry-defined recognisers</h3>{table(['Profile','Example','Rule ID','Purpose'],grammar_rows)}</section>
<section id="modes" class="chapter"><h2>3. Blend Modes</h2><p>OCA follows Krita's blend-mode naming and semantics. Photoshop and After Effects mappings are named separately and may require visual verification, particularly for alpha and colour-space interactions. An empty entry means a reliable conversion is still unverified.</p>
<h3>Common blend modes</h3>{table(['OCA','Krita','Photoshop','After Effects'],mode_rows[:20])}
<details id="modes-extended"><summary>Extended blend-mode reference ({len(mode_rows)-20} less-common modes)</summary>{table(['OCA','Krita','Photoshop','After Effects'],mode_rows[20:])}</details>
<div class="info">{product} applies a shared blend mode to a group when that mode covers a strict majority of its direct pixel layers. Layers with the promoted mode use Normal inside the group. Mixed groups may composite differently between Photoshop and Krita, so check the exported result before handoff.</div></section>
{exr_html}<section id="credits" class="chapter"><h2>5. Sources &amp; Credits</h2><p>Credits are linked to the original authors and maintainers. The descriptions and mappings were prepared for {product} using the linked source documentation.</p><ul>{credits}</ul>
</section>
<footer class="footer">{product} · v{version} Alpha · Offline reference.</footer></main></div></div></body></html>'''
from paginate_manual import generate_pages
source_table=table(['Authored token','Origin','Function','Scope'],srcrows)
generate_pages(out,html.replace('{product}',esc(BRAND_NAME)).replace('{version}',VERSION),style,beh_sections,source_table)
print('Generated manual from',len(behaviors),'tag functions and',len(modes),'blend modes')
