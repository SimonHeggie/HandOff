"""Generate the artist-facing offline manual from XML-backed reference material.

The tag and blend registries are read-only inputs. Topic assignment changes only
where the documented functions appear, never their order or mapping.
"""
from pathlib import Path
from html import escape
import re
import xml.etree.ElementTree as ET
from workflow_notes import TOPICS, _inline_html
from branding import NAME, VERSION


OPERATIONS = ('exclude', 'reference', 'merge', 'group', 'hidden', 'folder')
GENERATOR = ('asset-format', 'asset-multiple', 'asset-scale', 'asset-dimensions', 'asset-quality', 'asset-depth')
SPINE = ('slot', 'bone', 'skin', 'mesh', 'attachment-path', 'trim', 'padding', 'rotation', 'origin', 'overlay', 'child-bones', 'child-slots', 'group-pattern')
SUFFIXES = ('blend',)
PAGES = [
    ('MANUAL.html', 'Getting started', 'Basics'),
    ('groups.html', 'Collection hierarchy', 'Basics'),
    ('psd.html', 'PSD/PSB colour', 'Basics'),
    ('vectors.html', 'SVG / Vector Artwork', 'Basics'),
    ('tags.html', 'Tag compatibility', 'Tags'),
    ('tags-operations.html', 'Group and export directives', 'Tags'),
    ('tags-spine.html', 'Spine directives', 'Tags'),
    ('generator.html', 'Photoshop Generator', 'Tags'),
    ('exr-suffixes.html', 'EXR-style suffixes and blending', 'EXR-style naming'),
    ('openexr.html', 'OpenEXR channels', 'EXR-style naming'),
    ('sources.html', 'Sources and credits', 'Reference'),
]


def _topic(entries):
    output = []
    for kind, value in entries:
        output.append('<pre><code>' + escape(value) + '</code></pre>' if kind == 'code' else '<p>' + _inline_html(value) + '</p>')
    return ''.join(output)


def _markup_table(headers, rows, css_class=''):
    heads=''.join('<th scope="col">'+escape(str(x))+'</th>' for x in headers)
    body=''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in rows)
    return '<div class="table-wrap '+css_class+'"><table><thead><tr>'+heads+'</tr></thead><tbody>'+body+'</tbody></table></div>'


def _syntax(entry):
    if entry is None: return '<span class="muted">-</span>'
    syntax=entry.get('syntax')
    if not syntax:
        return '<span class="muted">metadata</span>' if entry.get('equivalence')=='metadata' else '<span class="muted">-</span>'
    note = ' <small>(approx.)</small>' if entry.get('equivalence')=='approximation' else ''
    return '<code>'+escape(syntax)+'</code>'+note


def _rules(identifiers, fragments):
    parts=[]
    for ident in identifiers:
        content=fragments[ident]
        content=re.sub(r'<span class="num">[^<]+</span>\s*', '',content)
        # All 26 behaviour titles and compatibility data come from tags.xml.
        parts.append(content)
    return ''.join(parts)


def generate_pages(out, combined_html, stylesheet, behavior_sections, source_table):
    out=Path(out)
    root=out.parent/'compatibility'
    tags=ET.parse(root/'tags.xml').getroot()
    blends=ET.parse(root/'blend_modes.xml').getroot()
    behaviors=sorted(tags.findall('./behaviors/behavior'), key=lambda e:int(e.get('rank')))
    fragments={}
    for fragment in behavior_sections:
        hit=re.search(r'<section[^>]*id="tag-([^" ]+)"', fragment)
        if hit:fragments[hit.group(1)]=fragment
    assert len(behaviors)==len(fragments)==26
    assert set(fragments)==set(OPERATIONS+GENERATOR+SPINE+SUFFIXES)

    # The cross-format matrix follows tags.xml's authored common-function order.
    destinations=('spine','generator','oca')
    rows=[]
    for behavior in behaviors:
        ident=behavior.get('id')
        dest=next((page for group,page in ((OPERATIONS,'tags-operations.html'), (GENERATOR,'generator.html'), (SPINE,'tags-spine.html'), (SUFFIXES,'exr-suffixes.html')) if ident in group),None)
        mapping={t.get('profile'):t for t in behavior.findall('target')}
        rows.append([f'<a href="{dest}#tag-{escape(ident)}">{escape(behavior.get("label"))}</a>']
                    + [_syntax(mapping.get(profile)) for profile in destinations])
    matrix=_markup_table(['Function', 'Spine PSD', 'Photoshop Generator', 'OCA / Krita'],rows,'tag-quick')

    # Exact tokens remain accessible as an appendix. They do not replace the
    # side-by-side cross-ecosystem matrix.
    token_links={ident:page for ids,page in ((OPERATIONS,'tags-operations.html'),(GENERATOR,'generator.html'),(SPINE,'tags-spine.html'),(SUFFIXES,'exr-suffixes.html')) for ident in ids}
    for ident,page in token_links.items():
        source_table=source_table.replace('href="#tag-'+ident+'"', 'href="'+page+'#tag-'+ident+'"')
    token_index='<details id="token-index"><summary>Exact recognised tokens</summary>'+source_table+'</details>'

    # Preserve source names and equivalences in the detailed pages, removing
    # numeric badges that previously divided reference sections arbitrarily.
    pages={
      'MANUAL.html': '''<section class="chapter" id="start"><h2>Getting started</h2>
<p>{product} uses Blender's compositor File Output inputs to build layered artwork. Socket order determines the output stack.</p><p>Designed by Simon Heggie.</p>
<p>Set the destination format in Additional Outputs. Use <strong>Tag Compatibility</strong> to select No Conversion, Spine, Photoshop Generator or OCA / Krita. Use <strong>Check Export Status</strong> to inspect the source Collection mapping and export hierarchy.</p>
<p>For layered OCA animation, enable an <strong>.OCA</strong> destination and use Blender's <strong>Render Animation</strong>. The rendered animation range is published as standard OCA frame sequences with relative image assets. Keep the OCA file beside its image folder. Frame Step becomes exposure holds; Render Image publishes a still. Other document formats continue to publish the final rendered frame.</p>
<p>Use <strong>Retry Export (No Render)</strong> to reconvert compatible cached pixels after changes to names, Collection tags and supported output settings.</p>
<p>The <a href="tags.html">Tag compatibility</a> reference compares shared functions across ecosystems. Open the relevant topic for syntax, scope and limitations.</p></section>
<section class="chapter" id="cache"><h2>Retained jobs</h2>
<p><strong>Clear Cache</strong> removes older retained jobs while preserving the selected Job Folder. Enable <strong>Clear all</strong> to include the selected job. Active jobs are protected. Finished deliverables outside {product}'s cache directory are unaffected.</p></section>''',
      'groups.html': '<section class="chapter" id="collection-groups"><h2>Collection hierarchy</h2>'+_topic(TOPICS[0][1])+'</section>',
      'psd.html': '<section class="chapter" id="psd-color"><h2>PSD and PSB colour handling</h2>'+_topic(TOPICS[3][1])+'</section>',
      'vectors.html': '''<section class="chapter" id="vectors"><h2>SVG vector artwork</h2>
<p>Select <strong>SVG / Vector Auto</strong> in Additional Outputs. {product} writes one layered SVG document using the File Output input order and its existing Collection grouping rules. PNG artwork is embedded when a source cannot be converted to editable vectors.</p>
<h3 id="vector-formats">Vector selection and PNG fallback</h3>
<p>{product} detects Grease Pencil, Blender Curve and Blender Text objects from the connected Render Layers Image output. Enable <strong>Rasterise Vector Artwork</strong> when a raster result is required. PSD and PSB consume the same prepared geometry as native shape, stroke, gradient and supported single-line type layers. OCA retains its raster artwork. Unsupported PSD sources retain their complete rendered pixels with a conversion log explanation.</p>
<h3 id="vector-camera">Camera setup</h3>
<p>SVG vector extraction requires an orthographic render camera and Film Transparent. The exporter uses render-camera coordinates and output resolution for paths, handles and text transforms.</p>
<h3 id="vector-compatible">Supported vector geometry</h3>
<p>Grease Pencil polygon and B&eacute;zier strokes retain supported fill, outline and compound hole information. Native Blender 2D Curve objects with closed B&eacute;zier or polygon splines export as editable SVG paths. Their fill rule, flat material colours and curve handles are preserved.</p>
<p>Each supported Grease Pencil object becomes a named editable SVG group. Supported Noise, Thickness, Opacity, Tint, Subdivide, Smooth, Mirror, Offset, Dash, Outline, Length and Simplify modifiers use Blender's evaluated geometry at the current frame. Their results are editable paths; Render-only modifiers use a private evaluation copy; original objects and modifier flags are untouched. Source geometry and scalar modifier settings are retained as reference metadata. Blender modifier stacks cannot execute in SVG or Photoshop. See the modifier editing guide below.</p>
<p>Supported open polygon and cubic B&eacute;zier pressure strokes retain their centreline and width values as a live Inkscape PowerStroke effect. Other SVG readers display a sampled filled outline. Width interpolation and the portable outline approximate Blender's brush geometry, with a conversion warning. Closed pressure contours, sharp polygon joints and unsupported combinations retain PNG fallback. The existing evaluated Outline fallback remains available for other supported smooth strokes.</p>
<p>Objects with multiple GP drawing layers are supported and retain their layer names, order and opacity. A newly added layer may have Lights enabled even when another layer is unlit. For flat vector output, disable Use Lights on the GP object, or disable Lights on every relevant drawing layer. Varying per-point opacity on an open, unfilled stroke becomes an editable SVG opacity gradient when the path progresses monotonically along an axis. Each point retains an opacity stop. This approximates brush interpolation; loops, reversing paths and filled combinations keep PNG fallback. PowerStroke width handles and gradient opacity stops are independent controls.</p>
<p>GP layer blends apply automatically as editable SVG groups, retaining drawing order, opacity and Collection folders. Multiply and Hard Light use their standard SVG modes; Add uses Screen, Subtract uses Difference and Divide uses Color Dodge as the closest supported equivalents. Each blended object produces an approximation warning in the conversion log. Blender's GP transparency calculations and nonlinear view transforms can produce a different appearance. Blending stays inside the isolated GP object. Masks and lighting keep their existing fallback. Use F12 to replace older retained sources that baked these objects to PNG. Rasterise Vector Artwork remains available when rendered appearance is required.</p>
<h3 id="vector-modifiers">Modifier editing guide</h3>
<p>Objects sharing one Grease Pencil datablock use SVG clones when their evaluated paths and paint can share an affine transform. In Inkscape, select a clone and use <strong>Edit &gt; Clone &gt; Select Original</strong> to edit the shared artwork. <strong>Unlink Clone</strong> makes one instance independent. Ordinary Blender duplicates with separate datablocks remain independent. Instances with different materials, incompatible evaluated geometry, pressure effects or unsupported stroke transforms remain editable independent vectors. Collection and object highlight colours are retained. This does not create Photoshop Smart Objects.</p>
<p>Noise, Smooth, Subdivide, Simplify, Mirror, Offset, Dash, Outline and Length retain Blender's evaluated paths, including render-only effects. A modifier may change B&eacute;zier geometry to polygon paths. The result stays vector. Source paths and parameters remain reference metadata; PSD also stores original paths in its Paths resources. Inkscape Roughen, smoothing, Mirror Symmetry, Offset, Simplify, clones and object transforms are possible manual alternatives. They are not identical cross-application versions of Blender algorithms.</p>
<p>Uniform Thickness is an editable stroke width. Supported varying widths retain a live SVG PowerStroke and portable outline; PSD uses an editable filled outline plus saved centreline. Opacity and Tint remain editable paint where representable. Blender Dash patterns become explicit vector dash paths and dot circles. Neither format can execute Blender's full modifier stack; complex masks, lighting and materials can still require pixels.</p>
<h3 id="vector-text">Editable text</h3>
<p>Use an Emission shader connected to Material Output &rarr; Surface for predictable flat text colour; Strength 1 is a useful starting point. Constant colour inputs, including RGB nodes, are supported. For ordinary Principled materials, enable <strong>Use Flat Text Colour</strong> in the SVG or PSD destination to export constant Base Color and Alpha as editable text. This omits lighting and surface effects from SVG without changing the Blender material. Textures and procedural colours still require PNG.</p>
<p>Text remains visible in the normal Blender render; live text is created during SVG conversion. Unsupported text objects fall back independently, so their supported GP neighbours remain editable.</p>
<p>Blender Text objects export as live SVG <code>&lt;text&gt;</code> and <code>&lt;tspan&gt;</code> elements. {product} carries the text content, referenced font family, size, horizontal alignment, basic vertical alignment, line breaks, spacing, colour, bold, italic, underline and small-caps formatting. Original Blender spacing and font metadata are retained as SVG attributes where a direct SVG equivalent is only approximate.</p>
<p>SVG retains the original font family reference and editable text. It does not embed font files or provide font-delivery controls. Install the referenced fonts using your normal document workflow. Blender's built-in Bfont retains the Bfont family and Regular face; {product} does not substitute Noto Sans or another system font. Exact text layout can still vary between applications.</p>
<p><strong>Fonts / Text Assets</strong> is an independent output type. It detects fonts used by Text objects across project scenes, including hidden and off-camera text, independently of linked image sockets. Multiple font destinations can be enabled. Referenced and packed font files are copied exactly; built-in Bfont is recovered from Blender's own embedded PostScript <code>.pfb</code> resource. The optional OpenType/CFF <code>.otf</code> companion can be delivered only when the separately verified <code>Bfont-Regular.otf</code> asset is present. <strong>The v0.7.51 Alpha 1 installation archive does not include that optional asset.</strong> The original PostScript <code>.pfb</code> is retained when Blender's built-in font can be recovered, and the font manifest lists only the files actually delivered. A font that cannot be recovered is reported as unavailable rather than replaced.</p>
<p>A new Fonts destination defaults to the current user's font directory: <code>~/.local/share/fonts</code> on Linux (or <code>$XDG_DATA_HOME/fonts</code>), <code>~/Library/Fonts</code> on macOS, or the per-user Microsoft Windows Fonts directory. These avoid the administrator access normally needed for system-wide font folders. Change Directory to a company or game asset folder as required; existing configured paths are preserved.</p>
<p>The optional <strong>Find Missing Font Files</strong> and <strong>Font Search Folder</strong> fields belong to the Fonts output. They search for the actual missing font, with no unrelated-family fallback. Deliveries contain a <code>.fonts.json</code> manifest and an adjacent <code>&lt;name&gt;.fonts</code> subfolder, with font files, hashes and text-object references. Source fonts and project files are never removed. Fonts outputs can be added to a retained job using <strong>Retry Conversion (No Render)</strong>. A fresh F12 export is needed to replace an older cached SVG that referenced a substitute font.</p>
<h3 id="vector-fallback">PNG fallback conditions</h3>
<p>{product} retains the raster render for unsupported artwork, including mixed 3D geometry, compositor effects, non-orthographic cameras, modified or extruded curves, NURBS splines, text on a path, bevelled text and unsupported text box layouts. The Blender terminal reports each fallback reason.</p>
<p>Unsupported Grease Pencil objects use isolated PNG fallbacks alongside supported vectors. Lit materials, masks, complex variable-width strokes and varying point opacity can require raster output. Consecutive raster objects may share one image while preserving their position in the drawing order. One unsupported GP object does not rasterise its vector neighbours. Mixed 3D sources and cross-object holdouts retain the complete source render.</p>
<p>Object fallbacks are rendered after the main render from a temporary scene snapshot. The original project is never saved by this process. Rasterise Vector Artwork continues to use the complete cached source image.</p>
<p>GP object scaling, layer tint, layer thickness and authored opacity are preserved. Flat paint colours follow the scene view settings when Save as Render is enabled. Translucent paint and blending can look different under nonlinear view transforms such as Filmic because SVG editors composite in their own colour pipeline.</p>
<p>GP, background tiles and text retain their authored Collection folders. Separated segments of a Collection are combined when their complete artwork footprints do not overlap intervening artwork. Overlapping or unmeasured segments retain their paint order. Raster fallback images live directly in the authored folder rather than a synthetic fallback folder.</p>
<p>Cancelling removes only this operation's owned cache and tracked temporary nodes. A recovered project removes marked temporary output nodes on load. Scene snapshots remain in the private job cache until conversion is complete, then owned completed snapshots are removed. Project files and source fonts are never delivered as font assets.</p>
<h3 id="vector-retry">Rendering and retry</h3>
<p>GP containers use Blender object names, and their paths use GP layer names. Single-layer objects without layer blending omit the redundant inner layer folder while retaining layer opacity and metadata. Blended layers and objects with several GP layers retain their separate layer folders.</p>
<p>Supported vector geometry is read from the Blender scene. <strong>Retry Conversion (No Render)</strong> reuses a completed hybrid GP source, keeping its vector and raster objects from the same retained render together. Use F12 to refresh its source geometry, modifiers, colours or object fallback pixels. An incomplete object fallback cache requires a new F12 render.</p></section>''',
      'tags.html': '<section class="chapter" id="tags"><h2>Tag compatibility across formats</h2><p>Functions are ordered by shared workflow purpose. Cells show the authored syntax used by each destination; metadata entries are stored as document properties. A dash indicates that no direct syntax is available.</p>'
                   +matrix+'<h3 id="token-notes">Exact source tokens</h3><p>{product} matches recognised tokens from its compatibility registry. Parameterised tokens contain a value field.</p>'+token_index+'</section>',
      'tags-operations.html': '<section class="chapter" id="operations"><h2>Group and export directives</h2><p>{product} reads the supported Collection and output-name directives when assembling the export. The detailed entries below show how the same functions are represented in Spine, Photoshop Generator and OCA.</p>'
                   +_topic(TOPICS[2][1])+_rules(OPERATIONS,fragments)+'</section>',
      'tags-spine.html': '<section class="chapter" id="spine-tags"><h2>Spine directives</h2><p>The bracketed tokens in this section are interpreted by the Spine PSD importer. {product} applies the corresponding conversion only when the destination selects Spine compatibility.</p>'
                   +_rules(SPINE,fragments)+'</section>',
      'generator.html': '<section class="chapter" id="generator"><h2>Photoshop Generator</h2><p>Photoshop Generator uses layer and group filenames to specify image assets. Select Generator tag compatibility for destinations that require that syntax.</p>'
                    +_rules(GENERATOR,fragments)+'</section>',
      'exr-suffixes.html': '<section class="chapter" id="suffixes"><h2>EXR-style dot suffixes</h2><p>{product} accepts dot suffixes on authored names, including blend modes such as <code>.add</code> and <code>.multiply</code>. They use a dot-separated naming pattern familiar from OpenEXR channels. Their behaviour is defined by {product}.</p>'
                    +_topic(TOPICS[1][1])
                    +'<h3 id="blend-rules">Blend-mode authoring and conversion</h3>'+_rules(SUFFIXES,fragments)
                    +'<h3 id="blend-common">Blend-mode compatibility</h3><p>These mappings compare OCA, Krita, Photoshop and After Effects. Blend-mode calculations and colour handling can vary between applications.</p>',
      'openexr.html': '<section class="chapter" id="exr"><h2>OpenEXR channels and passes</h2><p>OpenEXR stores named image channels, conventionally grouped using <code>Layer.Channel</code>. The <a href="exr-suffixes.html">{product} dot suffixes</a> are interpreted during layered-document export.</p></section>',
      'sources.html': '<section class="chapter" id="credits"><h2>Sources and credits</h2><ul>'+''.join('<li><a href="'+escape(s.get('url',''),quote=True)+'">'+escape(s.get('by',''))+'</a>: '+escape(s.get('title',''))+'</li>' for s in tags.findall('./sources/source'))+'</ul></section>',
    }

    mode_rows=[]
    for mode in sorted(blends.findall('./modes/mode'),key=lambda x:int(x.get('rank'))):
        apps={a.get('id'):a for a in mode.findall('app')}
        ps=apps.get('photoshop');ae=apps.get('after-effects')
        ae_label=ae.get('name') if ae is not None else None
        if ae is not None and ae.get('status')=='approximation':ae_label=(ae_label or '')+' (approx.)'
        def cell(v):return '<code>'+escape(v)+'</code>' if v else '<span class="muted">-</span>'
        mode_rows.append([cell(mode.get('oca')),cell(mode.get('krita')),cell(ps.get('name') if ps is not None else None),cell(ae_label)])
    assert len(mode_rows)==111
    blend_headers=['OCA', 'Krita', 'Photoshop', 'After Effects']
    from conversion_policy import capabilities
    features=list(capabilities().values())
    feature_rows=[[escape(r['source']),escape(r['svg_preferred']),escape(r['psd_preferred']),
        escape(r['fallback']),escape(r['svg_format_support']+' / '+r['psd_format_support']),
        escape(r['photoshop_support']+' / '+r['photocraft_support']),escape(r['svg_writer']+' / '+r['psd_writer']),
        escape(r['reader_validation']),escape(r['photoshop_validation']+' / '+r['photocraft_validation']),
        escape(r['inkscape_validation']+' / '+r['generic_svg_validation']),escape(r['notes'])]
        for r in features]
    pages['vectors.html'] += '<section class="chapter" id="conversion-policy"><h2>Conversion policy and capability table</h2>' + \
        '<p>Prefer faithful native paths, fills, gradients, masks, effects and Type layers before Smart Objects. ' + \
        'Preserve shared identity, authored hierarchy and colour precision. Use the smallest safe fallback boundary. ' + \
        'Rendered artwork with its SVG source is preferable to an empty or unverified substitute.</p>' + \
        '<p>This table is generated from the same <code>compatibility/vector_features.csv</code> read by the exporter. ' + \
        'A preferred format representation is not a claim of writer implementation or target-editor validation. ' + \
        'Application validation is recorded separately from the common PSD writer. Existing working native conversions are retained.</p>' + \
        '<p><strong>Automatic SVG sources:</strong> when native PSD conversion cannot represent vector artwork, ' + \
        'the exporter writes a compact SVG beside the document and links it as a Smart Object with visible preview pixels. ' + \
        'Shared GP gradient artwork can stay together as one linked layer with its SVG clones. Compatible neighbours remain native. ' + \
        'There is no editor selector or SVG-link toggle. Keep the PSD beside its <code>.assets</code> folder when moving or sharing it. ' + \
        'If linking fails, visible pixels and the editable source are retained with a notice. Rasterise Vector Artwork and Flatten Image ' + \
        'continue to request raster output. Photoshop and PhotoCraft edit/save validation remains unverified; file parsing alone is insufficient.</p>' + \
        '<p>For the gradient subset, generic SVG validation compares the generated preview against CairoSVG. ' + \
        'This does not verify Photoshop gradient rendering or all SVG readers.</p>' + \
        '<h3>Names and source identity</h3><p>SVG labels retain authored names. Element IDs describe their object and paint role, ' + \
        'with a short uniqueness suffix. Inert <code>data-asset-*</code> attributes and a versioned source index retain object, ' + \
        'datablock and scene UUIDs, original names and View Layer context. Linked instances share a data UUID but keep separate object UUIDs. ' + \
        'Save the Blender project after the first publication to retain its new UUID properties. This prepares for a future importer; ' + \
        'round-trip importing is not implemented and third-party editors may strip metadata.</p>' + \
        '<p>SVG event fields such as <code>onclick</code> are standard scripting hooks. Exports leave them empty and do not add scripts. ' + \
        'They are not needed for layer identity or clone linkage.</p>' + \
        _markup_table(['Source feature','Preferred SVG','Preferred PSD/PSB','Fallback','Format SVG / PSD','App support Photoshop / PhotoCraft','SVG / PSD writer', 'Reader validation', 'Photoshop / PhotoCraft validation', 'Inkscape / generic SVG validation','Implementation limits'],feature_rows) + '</section>'
    pages['exr-suffixes.html']+=_markup_table(blend_headers,mode_rows[:20])
    pages['exr-suffixes.html']+='<details id="blend-extended"><summary>Additional blend modes ('+str(len(mode_rows)-20)+')</summary>'+_markup_table(blend_headers,mode_rows[20:])+'</details></section>'

    exr=tags.find('exrConventions')
    assert exr is not None
    pages['openexr.html']=pages['openexr.html'].replace('</section>',
        '<h3 id="exr-channels">Channel names</h3>'+
        _markup_table(['Channel','Category','Meaning','Status'],[[ '<code>'+escape(c.get('name',''))+'</code>',escape(c.get('kind','')),escape(c.get('meaning','')),escape(c.get('status',''))] for c in exr.findall('./channels/channel')])+
        '<h3 id="exr-patterns">Layer and channel patterns</h3>'+
        _markup_table(['Pattern','Meaning'],[[ '<code>'+escape(p.get('syntax',''))+'</code>',escape(p.get('meaning',''))] for p in exr.findall('./patterns/pattern')])+
        '<h3 id="exr-passes">Blender render passes</h3>'+
        _markup_table(['Category','Pass'],[[escape(p.get('category','')),'<code>'+escape(p.get('name',''))+'</code>'] for p in exr.findall('./blenderPasses/pass')])+
        '</section>')

    labels={file:(title,section) for file,title,section in PAGES}
    known=set(labels)
    # Remove old numeric-partition pages, now replaced by subject pages.
    for obsolete in ('tags-2.html','tags-3.html','tag-tokens.html','blends.html'):
        (out/obsolete).unlink(missing_ok=True)

    css=stylesheet+'''
.sidebar a.page-link.current{background:var(--sub);font-weight:750;border-left:3px solid var(--accent)}
.sidebar a.section-link{font-size:.83rem;padding:.14rem .7rem .14rem 1.3rem;color:var(--muted)}
.sidebar a.section-link.active{background:var(--sub);color:var(--accent);font-weight:750;border-left:3px solid var(--accent)}
.sidebar .small-head{display:block;margin-top:1rem;font-size:.72rem;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.07em}
.sidebar .page-category{display:block;margin-top:1.1rem;margin-left:.65rem;color:var(--muted);font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em}
.mobile-nav{display:none}@media(max-width:900px){.mobile-nav{display:block;margin:1rem 0}.mobile-nav a{margin-right:1rem;display:inline-block}}
'''
    script='''<script>(function(){
 const links=[...document.querySelectorAll('a.section-link')];
 const targets=links.map(a=>document.getElementById(a.hash.slice(1)));
 function update(){let selected=-1;for(let i=0;i<targets.length;i++){if(targets[i]&&targets[i].getBoundingClientRect().top<=innerHeight*.33)selected=i}
 if(selected<0&&targets.length)selected=0;links.forEach((a,i)=>{a.classList.toggle('active',i===selected);if(i===selected)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current')})}
 addEventListener('scroll',update,{passive:true});addEventListener('hashchange',update);addEventListener('load',update);update();
})();</script>'''
    for filename,content in pages.items():
        page_nav=[];last_group=None
        for target,label,group in PAGES:
            if group!=last_group:
                page_nav.append('<span class="page-category">'+escape(group)+'</span>');last_group=group
            page_nav.append('<a class="page-link'+(' current' if target==filename else '')+'" href="'+target+'">'+escape(label)+'</a>')
        headings=re.findall(r'<(?:section|h2|h3|details)\b[^>]*\bid="([^"]+)"[^>]*>(?:\s*<[^>]+>)*',content)
        section_names={b.get('id'):b.get('label') for b in behaviors}
        sections=[]
        for anchor in dict.fromkeys(headings):
            title=section_names.get(anchor[4:]) if anchor.startswith('tag-') else None
            if not title:title=anchor.replace('-', ' ').capitalize()
            if anchor=='blend-common':title='Blend modes'
            if anchor=='token-index':title='Exact tokens'
            sections.append('<a class="section-link" href="#'+escape(anchor)+'">'+escape(title)+'</a>')
        nav=''.join(page_nav)+'<span class="small-head">On this page</span>'+''.join(sections)
        mobile=''.join('<a href="'+target+'">'+escape(label)+'</a>' for target,label,_ in PAGES)
        title=labels[filename][0]
        html=('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
              '<title>{product} | '+escape(title)+'</title><style>'+css+'</style></head>'
              '<body><div class="layout"><aside class="sidebar"><div class="brand">{product}</div><small>User Manual | v{version}</small><nav aria-label="Manual pages">'+nav+'</nav></aside>'
              '<div class="content"><main><div class="eyebrow">{product} documentation</div><h1>'+escape(title)+'</h1>'
              '<nav class="mobile-nav">'+mobile+'</nav>'+content+
              '<footer class="footer">{product} v{version} Alpha. Offline reference.</footer></main></div></div>'+script+'</body></html>')
        (out/filename).write_text(html.replace('{product}',escape(NAME)).replace('{version}',VERSION),encoding='utf-8')
    # Searchable Markdown index without an outdated alternative full manual.
    (out/'MANUAL.md').write_text('# '+NAME+' User Manual\n\nOffline HTML pages:\n\n'+
        '\n'.join('- ['+title+']('+file+')' for file,title,_ in PAGES)+'\n\n'+
        'The compatibility page compares functions across supported destinations.\n',encoding='utf-8')
    print('Generated',len(pages),'topical HTML pages from unchanged XML registries')
