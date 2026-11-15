"""Generate the two bundled HandOff manuals from tags.xml / blend_modes.xml.

No network, no Blender dependency. Run from any working directory:
    python3 compatibility/generate_manual.py
"""
from pathlib import Path
from workflow_notes import as_markdown, NAME
from html import escape
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / 'manual'
OUT.mkdir(parents=True,exist_ok=True)
tags=ET.parse(ROOT/'tags.xml').getroot()
blends=ET.parse(ROOT/'blend_modes.xml').getroot()
assert tags.attrib['schema']=='explicit-tag-mapping-v1'
source={e.get('id'):e.attrib for e in tags.findall('./sources/source')}


def md_code(value):
    if not value or value in ('-', 'none'):
        return '-'
    return '`' + value.replace('`','\\`').replace('|','\\|') + '`'


def cells(x):
    return (x or '').replace('|','\\|').replace('\n',' ').strip()


def credits(keys):
    lines=[]
    for key in keys:
        item=source[key]
        lines.append('- **[{by}]({url})** - {title}.'.format(**item))
    return lines

behaviors=sorted(tags.findall('./behaviors/behavior'),key=lambda x:int(x.get('rank')))
txt=[
'# '+NAME+' - Layer Tag Compatibility',
'',
'Reference for layer tags and their destination mappings.',
'',
'## How to use this reference',
'',
'**Tag Compatibility** belongs to each Additional Output entry. `Manual / No Conversion` is the default. Select Spine, Generator or OCA only when the destination requires it. `Manual / No Conversion` retains the authored expressions. Tag conversion changes exported names, never Blender Collection or socket names.',
'',
'The entries below are sorted by **common workflow function**, not alphabetically. Each mapping is an explicit token or a structured metadata instruction. When a feature has no safe equivalent, the exporter preserves the original directive and **Check Export Status** reports it.',
'',
as_markdown(),
'## Common functions - quick lookup','',
'| Function | Spine PSD | Photoshop Generator | OCA for Krita |',
'|:--|:--|:--|:--|',
]
for b in behaviors:
    mapping={x.get('profile'):x for x in b.findall('target')}
    def show(profile):
        m=mapping.get(profile)
        if m is None:return '-'
        form=m.get('syntax','')
        if len(form)>42:form=form[:37]+'…'
        return md_code(form)
    txt.append(f"| [{cells(b.get('label'))}](#{b.get('id')}) | {show('spine')} | {show('generator')} | {show('oca')} |")
txt+=['', '## Detailed functions by topic', '']
md_topics={
  'exclude':'Group and export operations', 'reference':'Group and export operations',
  'merge':'Group and export operations','group':'Group and export operations',
  'hidden':'Group and export operations','folder':'Group and export operations',
  'slot':'Spine directives', 'bone':'Spine directives', 'skin':'Spine directives',
  'mesh':'Spine directives', 'attachment-path':'Spine directives',
  'trim':'Spine directives','padding':'Spine directives','rotation':'Spine directives',
  'origin':'Spine directives','overlay':'Spine directives',
  'child-bones':'Spine directives','child-slots':'Spine directives','group-pattern':'Spine directives',
  'asset-format':'Photoshop Generator','asset-multiple':'Photoshop Generator',
  'asset-scale':'Photoshop Generator','asset-dimensions':'Photoshop Generator',
  'asset-quality':'Photoshop Generator','asset-depth':'Photoshop Generator',
  'blend':'EXR-style suffixes and blend modes',
}
last_topic=None
for b in behaviors:
    topic=md_topics[b.get('id')]
    if topic != last_topic:
        txt.extend(['', '### '+topic, ''])
        last_topic=topic
    txt.extend([f'<a id="{b.get("id")}"></a>',f'#### {b.get("label")}', '',b.get('description',''),'',f'**Where applicable:** {b.get("scope")}.',''])
    for m in b.findall('target'):
        txt.extend([f'**{ {"spine":"Spine", "oca":"OCA for Krita / native OCA", "generator":"Photoshop Generator"}[m.get("profile")]}** - {m.get("equivalence")}', '',
                    f'- Syntax / property: {md_code(m.get("syntax"))}',
                    f'- Direct emission template: {md_code(m.get("emit"))}',
                    f'- Representation: {cells(m.get("representation"))}',
                    f'- Meaning / caveat: {cells(m.get("note"))}', ''])
    src=b.find('authoring')
    if src is not None:txt.extend(['**Blender authoring syntax:** '+md_code(src.get('syntax')),''])
    caution=b.findtext('caution')
    if caution: txt.extend(['**Important:** '+caution,''])

txt+=['## Photoshop Generator syntax', '',
       'Generator asset names are *filename expressions*, not Spine tags and not OCA metadata. These must remain intact when you select **Photoshop Generator**. The add-on does not itself run Photoshop Generator.', '',
       '| Purpose | Valid example |','|:--|:--|',
       '| JPEG quality | `Photo.jpg5`, `Hero.jpg80%` |',
       '| PNG asset depth (total bits) | `Icon.png8`, `Icon.png24`, `Icon.png32` |',
       '| GIF / SVG | `Animation.gif`, `Shape.svg` |',
       '| Percentage resize | `200% Logo.png`, `50% Icon.jpg` |',
       '| Absolute / mixed units | `100x80 Thumb.png`, `4in x 100 Banner.jpg` |',
       '| Proportional wildcard | `100x? Logo.png`, `?x60in Banner.jpg` |',
       '| Multiple outputs | `Icon.png8, Icon.jpg90%` |',
       '| Subfolder | `icons/Icon.png`, `@2x/Hero.jpg` |',
       '', '**Invalid:** `100x100foo.png` (missing separator), `80x100 60% foo.png` (mixed scaling), `30nm x20 Image.png` (invalid unit). Generator does not allow colons or asterisks in asset names.', '',
       '### Schema-defined recognizers', '',
       'This table records the **explicit grammar** available to validation code. Conversion never searches arbitrary filenames for keywords.', '',
       '| System | Recognizer | Example |','|:--|:--|:--|']
for rule in tags.findall('./generatorGrammar/rule'):
    txt.append(f"| {cells(rule.get('profile'))} | {md_code(rule.get('id'))} | {md_code(rule.get('example'))} |")
# OpenEXR is NOT a naming-tag conversion language. Keep these entries in the
# same XML registry but out of sourceTokens, to avoid incorrect translations.
exr = tags.find('exrConventions')
if exr is None or exr.get('schema') != 'openexr-naming-v1':
    raise ValueError('Missing explicit OpenEXR channel reference')
txt += ['', '## OpenEXR - channel and pass naming', '',
        'EXR layers are sets of named pixel channels, not PSD paint layers. '
        'OpenEXR has **no standard layer blend-mode, draw-order, ignore or merge name tag**. '
        'The following data is a **channel naming reference**, not a tag converter.', '',
        '| Channel | Category | Definition | Standard status |',
        '|:--|:--|:--|:--|']
for channel in exr.findall('./channels/channel'):
    txt.append('| {name} | {kind} | {meaning} | {status} |'.format(
        name=md_code(channel.get('name')), kind=cells(channel.get('kind')),
        meaning=cells(channel.get('meaning')), status=cells(channel.get('status'))))
txt += ['', '### Layer naming patterns', '', '| Structure | Meaning |', '|:--|:--|']
for pat in exr.findall('./patterns/pattern'):
    txt.append('| {} | {} |'.format(md_code(pat.get('syntax')), cells(pat.get('meaning'))))
txt += ['', '### Blender Render Passes - examples, not official EXR tags', '',
        '| Blender pass family | Blender render pass |', '|:--|:--|']
for ps in exr.findall('./blenderPasses/pass'):
    txt.append('| {} | {} |'.format(cells(ps.get('category')), md_code(ps.get('name'))))
txt += ['', 'Exact EXR channel prefixes depend on the writing application, View Layer and output settings. '
        'OpenEXR channel names do not prescribe how to composite passes.', '']

txt+=['', '## Conversion and fallback policy','',
       '1. Match **only tokens explicitly declared** under `sourceTokens` in `tags.xml`; parameterised tokens use `{value}`.',
       '2. Look up the behaviour ID, then its destination profile and `emit` template. Do not infer a template from prose.',
       '3. If the mapping is unavailable, retain the original token and emit a warning. Preservation is not a guarantee that all third-party applications will ignore the token.',
       '4. `Manual / No Conversion` is the default. Flattened outputs disable tag compatibility. Legacy Automatic profiles now resolve to No Conversion.',
       '5. Native `.oca` uses structured fields (`reference`, `visible`, `blendingMode`); `_reference_` etc. are **Krita OCA-exporter name tags**, not native OCA JSON tags.',
       '6. Layer/Collection identity, raster content and alpha processing are separate from translated output labels.',
       '', '## Credits and source documentation','',*credits(['spine','generator','oca_tags','oca_schema','openexr','openexr_deep','openexr_multiview','blender_passes','cryptomatte']),'',
       'The OCA conventions and source material are credited to **Nicolas Dufresne (Duduf)** and **RxLaboratorio**. This registry is an independently authored compatibility mapping rather than a verbatim copy of vendor manuals.','']
(OUT/'LAYER_TAGS.md').write_text('\n'.join(txt),encoding='utf-8')

modes=sorted(blends.findall('./modes/mode'),key=lambda x:int(x.get('rank')))
btxt=['# '+NAME+' - Blend Mode Compatibility','',
'Reference for blend-mode compatibility across common artwork formats.', '',
'OCA adopts **Krita** blend-mode semantics as its reference. Similar names in Photoshop or After Effects do not always mean identical mathematics, colour spaces, or alpha treatment.', '',
'## Common blend modes','',
'| OCA mode | Krita mode | Photoshop | After Effects |','|:--|:--|:--|:--|']
def mode_line(m):
    apps={a.get('id'):a for a in m.findall('app')}
    ps=apps.get('photoshop'); ae=apps.get('after-effects')
    ae_n=ae.get('name','') if ae is not None else ''
    if ae is not None and ae.get('status')=='approximation':ae_n+=' (approx.)'
    return f"| {md_code(m.get('oca'))} | {md_code(m.get('krita'))} | {md_code(ps.get('name') if ps is not None else None)} | {md_code(ae_n)} |"
for e in modes[:20]:btxt.append(mode_line(e))
btxt+=['','## Extended OCA/Krita modes','',
'<details>','<summary>Expand the 91 less-common mode mappings</summary>','',
'| OCA mode | Krita mode | Photoshop | After Effects |','|:--|:--|:--|:--|']
for e in modes[20:]:btxt.append(mode_line(e))
btxt+=['','</details>','',
'### Interpretation and cautions','',
'- **Blank cells** indicate no vetted name mapping in the registry. They do not prove the target application lacks an equivalent.',
'- An **approximation** is never safe to substitute silently. Confirm with a composite comparison.',
'- Additive artwork in Spine uses the Photoshop **Linear Dodge (Add)** mode; OCA `add` is modelled on Krita.',
'- Promote a blend mode from multiple child layers to a group only after checking compositing equivalence.',
'- The supplied OCA reference repeated `penumbra a` for three other penumbra variants; these should not drive unattended translations.',
'', '## Credits and source documentation','',*credits(['oca_blends','krita','photoshop_blends','spine']),'',
'**Nicolas Dufresne (Duduf), RxLaboratorio**: OCA blend-mode correspondence material; **Krita/KDE contributors**: blend-mode definitions; **Adobe**: Photoshop mode documentation; **Esoteric Software**: supported Spine PSD blend modes.','']
(OUT/'BLEND_MODES.md').write_text('\n'.join(btxt),encoding='utf-8')

index=['# '+NAME+' - User Manual', '',
       'Open [MANUAL.html](MANUAL.html) for the offline manual with topic pages and active navigation.', '',
       'The [Tag compatibility](tags.html) page compares shared functions across Spine, Photoshop Generator and OCA in the original XML registry order.',
       'The [EXR-style suffixes and blend modes](exr-suffixes.html) page explains '+NAME+' dot directives and links to the full blend-mode matrix.',
       'The [OpenEXR channels](openexr.html) page covers channel naming and render passes.',
       '',
       'Detailed compatibility and source attribution are available on the relevant topic pages.',
       'Detailed text references: [Layer Tags](LAYER_TAGS.md) and [Blend Modes](BLEND_MODES.md).','']
(OUT/'README.md').write_text('\n'.join(index),encoding='utf-8')
print('Generated',*[f'{p.name} ({p.stat().st_size} bytes)' for p in OUT.iterdir()])

# The HTML manual is paginated after extracting the shared registry tables.
# The full Markdown reference remains available for searching the source.
runfile = ROOT / 'add_combined_manual.py'
exec(compile(runfile.read_text(encoding='utf-8'), str(runfile), 'exec'), {'__file__':str(runfile),'__name__':'__main__'})
