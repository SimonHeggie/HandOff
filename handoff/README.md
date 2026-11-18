# HandOff

**Layered Asset Interchange & Publishing for Blender**

**One render. Every deliverable.**

Designed and maintained by **Simon Heggie**.

HandOff adds multiple independent export destinations to Blender's native compositor File Output node. Write PSD/PSB artwork, OCA documents, Spine-ready character artwork, image sequences and other production deliverables from a single render. The native node keeps functioning without the add-on.

## Installation

Install the complete ZIP through **Edit → Preferences → Add-ons → Install from Disk**. Restart Blender after upgrading, particularly when changing versions within the same running session.

Select a compositor **File Output** node, open **Node → HandOff - Additional Exports**, and add destinations. Test with **Check Export Status** before F12. You can use **Retry Export (No Render)** when cached images from a previous render are available.

The current build is alpha software; inspect output documents before delivering production assets.

## What's new in v0.7.53 Alpha 1 — OCA 1.3 interchange

This update is built directly from the latest supplied working source, without
merging older releases into it. It expands OCA authoring and publication:

- **OCA 1.3 project packaging:** canonical folders, portable paths, unique names,
  deterministic source-aware identifiers, validation and safe staged publishing.
- **Editable Grease Pencil SVG cels** where eligible, with optional raster
  alternatives for receivers that cannot reproduce vector artwork.
- **OCA authoring properties** on source View Layers and Collections: visibility,
  opacity (including frame exposure), blending, alpha inheritance, background
  selection and group isolation.
- **Reusable artwork and references:** verified linked Grease Pencil clones,
  explicit source View Layer references, translated/time-offset exposures and
  nested OCA documents (with cycle checks and portable referenced assets).
- **Image precision and continuity:** crop/scale/padding, 8/16-bit PNG, floating
  point EXR, frame sequencing/exposure timing, and compatibility test coverage.

This is an **alpha**. The new OCA features do not constitute arbitrary Blender
armature/weight conversion, 3D transform curve export, general frame
change-deduplication, independent `.blend` reconstruction or VSE export.
Please test the receiving application before production delivery.

See [release notes](manual/RELEASE_NOTES_v0.7.53-alpha.1.md),
[OCA controls](manual/OCA_CONTROLS.md) and
[OCA vector artwork](manual/OCA_VECTORS.md).

## Earlier local OCA completion build (v0.7.50)

The installable Python package is `handoff`. Legacy operator IDs and saved RNA
settings remain compatible. Enabling the renamed package disables an inactive
legacy installation's handlers before registering its own; active exports must
finish first. The production directory switch is separate from building this ZIP.

- Supported GP compositor inputs publish individual SVG OCA vector layers.
- **Rasterise Vector Layers** selects rendered pixels while retaining the SVG.
- **Keep Rendered PNG Fallback** retains a native-rendered alternative without
  inserting a second visible layer.
- Alpha cropping, scale, padding, visibility, hierarchy and current retry options
  use the existing OCA processing path.
- OCA filenames retain frame numbers and disambiguate real collisions, without
  numeric layer-order prefixes. Existing OCA colour assignment is restored.

See [OCA vector artwork](manual/OCA_VECTORS.md),
[OCA controls](manual/OCA_CONTROLS.md), and the
[local validation report](development/HANDOFF_FINAL_VALIDATION.md).
Build locally with `python3 development/build_handoff.py`.

## Changes in v0.7.50 Alpha

- **Render Animation** captures the rendered frame range for OCA and publishes one layered document with standard frame arrays, relative PNG/EXR assets, frame rate and exposure durations. **Render Image** continues to publish a still. Blender Frame Step is represented as exposure holds; no deduplication, rigging or transform extraction is performed.
- Mixed PSD/PSB/SVG destinations still publish the final rendered frame. OCA sequence publication uses the existing hierarchy, blend, precision and cache conversion paths; incomplete ranges fail before replacing existing artwork.
- Simplified format labels to `.PSD`, `.PSB`, `.OCA`, `.PNG`, `.SVG`, `.EXR`, `.TIFF`, `.JPEG`, `FONTS`; identifiers, extensions and tooltips remain intact.

## Changes in v0.7.49 Alpha

- Removed **Also Export Layered SVG** and its duplicate export path. Complete SVG documents use the existing SVG destination; automatic SVG assets required by linked PSD layers continue to export normally.
- Old saved settings remain loadable but cannot create or overwrite an extra full-document SVG. Retry removes the retired field from refreshed jobs.

## Changes in v0.7.48 Alpha

- Removed **Target Editor** and the locked **Link SVG Sidecars** checkbox. PSD/PSB uses the same writer for Photoshop and PhotoCraft. Old saved values remain readable and do not change publishing behaviour.
- Unsupported native vector content links its SVG source automatically, with visible cached preview pixels. Compatible objects remain native. A contiguous shared GP gradient source such as Shine is kept together as one linked layer with its SVG clones intact.
- If a link cannot be written, retain visible pixels and the editable SVG with a notice. **Rasterise Vector Artwork**, **Flatten Image**, `.merge` and disabled-layer handling retain their existing behaviour.
- Application validation remains recorded in the shared capability table; it is not a user-facing unlock or editor switch. Reader checks do not establish Photoshop/PhotoCraft edit/save compatibility.

## Changes in v0.7.47 Alpha

- Untagged Blender Collections export as white SVG highlights and Photoshop's native **Grey** colour label. Grey brightness is controlled by the receiving application.
- SVG element IDs describe the object and paint role. Inert source metadata carries persistent scene, object and datablock UUIDs, names and clone relationships. Save the Blender project after publishing to retain these new properties. A future importer can use this identity; importing and automatic round trips are not implemented.
- The exporter and offline manual share a 62-feature [capability CSV](compatibility/vector_features.csv). It distinguishes preferred format representations, implemented writer features and separate Photoshop, PhotoCraft, Inkscape and generic SVG validation. [Publishing policy](development/CONVERSION_POLICY.md) explains the decision order and current limits.
- Unsupported GP material gradients preserve a compact editable SVG beside the PSD. If the rendered source is empty, the supported GP paint subset can supply visible SVG-derived pixels while compatible neighbouring objects remain native. Interpolation differences are reported. Unknown empty fallbacks are omitted with a **partial** status instead of publishing an invisible substitute as successful artwork.
- Native linear/radial gradient descriptors and external SVG Smart Object records have isolated 8/16/32-bit save/reopen tests. **Link SVG Fallbacks** is visible in PSD/PSB settings, but remains disabled until the target editor passes validation. These prototypes are not advertised as working Photoshop or PhotoCraft features. Gradient Overlays and shared embedded Smart Objects remain to implement.
- Source relationships are retained in SVG and PSD source metadata; independent PSD shape copies are explicitly reported as losing live instance editing. Detailed publication choices appear in the retained job report and terminal, under the existing collapsed Diagnostics UI.

## Changes in v0.7.46 Alpha

- Fixed **Retry Conversion** importing SVG grouping helpers through Blender's add-on package without a worker search path. Verified through the actual Retry operator, with linked GP objects and no render.
- An explicitly untagged Blender Collection now stops ancestor colour inheritance, including ancestors removed by `.ungroup`. SVG shows the default as white. PSD records No Colour, since its supported label palette has no white; the receiving app controls its default appearance.
- SVG clones do not change PSD vector conversion: PSD still reads the full shared artwork model. Shine's current raster fallback is caused by its material gradient transform, not clone references. Embedded vector Smart Objects remain a separate, unimplemented compatibility feature.
- A fully transparent rendered cache used after PSD vector fallback now produces a Diagnostics notice. It does not silently substitute different artwork or pretend the raster layer contains vectors.

## Changes in v0.7.45 Alpha

- Fixed worker startup under Blender's `--python` launcher: its own folder is added to Python's import path before helper imports. This repairs exports that stopped before producing a result report.
- The short status reads **Exporting assets…** during conversion. An early worker failure reports **Export failed - Retry available**, with the log location under Diagnostics. Stale results from earlier retries are cleared before launch; the completion chime still plays only on success.
- Shortened the new cache folder to `asset-parts`. Existing `layered-document-export` and `blend-psd-tools` job folders remain available for retry, disabled-layer history and cache cleanup.

## Changes in v0.7.44 Alpha

- Linked Grease Pencil datablocks export as editable SVG clones when evaluated geometry, paint and transforms are compatible. Editing the original in Inkscape updates its clones; separate Blender datablocks stay independent. Bézier handles, gradients, object names and paint order are preserved. Unsupported sharing cases keep their independent vectors.
- SVG groups, layers and imported objects carry Inkscape-compatible colour labels again.
- Restored Dolphin PSD thumbnails by writing an RLE document preview. Individual raster layers still use the selected compression, including Automatic ZIP. Native 8/16/32-bit PSD/PSB exports were tested with KDE's actual image reader.
- New temporary jobs use `layered-document-export/jobs/layered_render_*` and `layer_L…` cache images. Existing jobs and environment overrides remain supported. Public product identity/version/log labels live in `branding.py`; technical identifiers live in `runtime_paths.py`. Saved Blender setting and operator identifiers remain compatible.
- Validation, compatibility limits and private character examples: [development notes](development/SVG_CLONES_AND_PREVIEWS.md).

## Changes in v0.7.43 Alpha

- Exports record total time, stage timings and peak worker memory in `result.json`. Preparation and combined render/cache duration are recorded separately; nested stage times overlap and must not be summed.
- Flattened images stream one decoded layer at a time. Pixel order, blend equations, reference filtering and source precision are preserved.
- Raster PSD/PSB layers trim only rows/columns containing **all-zero RGBA** and keep their offsets. Hidden RGB, fractional alpha and HDR values are preserved. Many Blender renders contain colour under transparent pixels; those layers remain full size. SVG and ordinary still-image bounds are unchanged.
- Identical GP vector preparation is shared across compatible destinations on a File Output node. Different material, colour-management, font-search and collection-root options remain separate. This shares export preparation; it does not yet create SVG clones or linked Smart Objects.
- **PSD Compression** offers Automatic, RLE, ZIP, ZIP with Prediction and Uncompressed. Automatic uses lossless ZIP for raster channels. Since v0.7.44, the document preview uses portable RLE for Dolphin/KDE compatibility. Old retained jobs without this field keep RLE until Retry refreshes their settings. Shape/type records and existing file naming remain intact.
- Input sync, export notices, performance and collection reports now live under one **Diagnostics** disclosure, closed by default. Existing saved report data and legacy disclosure properties remain readable.
- Benchmarks and validation are documented in [the performance notes](development/PERFORMANCE.md).

## Changes in v0.7.42 Alpha

- Input-sync diagnostics are collapsed under **Input Sync Details** by default. Export notices have their own collapsed **Export Details** disclosure.
- **Completion Chime Volume** replaces the checkbox with a linear 0–1 slider. Zero stops any active chime and skips loading sound or opening an audio device. Existing saved mute settings and the legacy script property remain supported.
- **FONTS** already copies the actual font files into a companion folder such as `Hatshepsut.fonts/`. The `.fonts.json` file is an additional index of fonts, styles, source objects, delivered filenames and hashes, useful for automation and checking missing fonts. The output-path display now labels the font folder and index separately. Bfont's exact `.pfb` and the compatible `.otf` are both delivered.
- Disabled View Layers reuse their **last compatible rendered image**, including alpha and original cache precision. The exporter matches project/source, cache format, display-transform setting and canvas dimensions, then retains a private copy in the current job cache. It never re-enables rendering, imports an existing PSD/SVG or merges an illustrator's document edits.
- If no compatible previous image exists, layered documents receive a hidden blank placeholder and a notice. Flattened images receive transparent pixels for that source (JPEG has no alpha). Missing cache files for enabled View Layers remain errors. Clearing all retained caches removes the last-render history too.
- Flattened images now use the same standard blend calculation as merged groups, including overlay, darken and lighten. This fixes the separate PNG failure triggered by `Shine.overlay`.
- Legacy retained caches can be reused when destination and source View Layer match uniquely. Run **Retry Export (No Render)** from the open project to refresh old job metadata. An old failed job with unfinished SVG source preparation still requires F12 to rebuild that source.
- Details and validation: [disabled-render handling](development/DISABLED_VIEW_LAYERS.md).

## Changes in v0.7.41 Alpha

- SVG gradients now keep exactly the authored ramp stops: three Blender stops become three SVG stops. Positions, colours, alpha and transforms are preserved. Blender Ease/B-spline/HSV interpolation is recorded as metadata and approximated by SVG interpolation, with a warning.
- Added **Update Inputs to ViewLayers** to the selected File Output node's **Node → HandOff - Additional Exports** panel. It creates missing Render Layers nodes, follows unambiguous processed image branches, connects missing inputs, updates names and colours Render Layers nodes from their parent Collection tags. One scene effect is supported, including unique nested node groups.
- Existing input order, processed links and per-input formats are preserved. Missing inputs append at the end. Durable View Layer identity distinguishes renames from deletions; deleted layers remove only their previously synced input, with a warning. Unrecognised/manual inputs and ambiguous branches remain intact. The action supports Undo; it never renders or saves the project.
- Disabled View Layers/pass settings are reported and kept unchanged. Shared groups are not given new routing ports; multiple scene-effect stacks are deferred. See [sync behavior and validation](development/VIEW_LAYER_SYNC.md).

## Changes in v0.7.40 Alpha

- SVG exports planar GP linear/radial material gradients with their stroke UV mapping, material transforms, ramp colour and stop alpha. Bézier handles and compound holes stay editable. Ramps become sampled SVG stops using Blender's interpolation and scene colour management; renderer differences are reported.
- Holdout and texture fallbacks now have distinct explanations. Empty PNG warnings identify material Holdout as a possible cause. Holdout erases GP paint; use gradient stop alpha for a painted shine fading to transparency.
- PSD/PSB retain Blender's rendered pixels for these material gradients until their affine transforms have a verified native Photoshop equivalent. Existing shape, stroke and pressure-gradient export is preserved.
- See [the shine investigation and validation](development/GP_GRADIENT_RESEARCH.md).

## Changes in v0.7.39 Alpha

- SVG and PSD/PSB share camera-space geometry, paint, pressure and font preparation. Supported GP modifier results remain editable vector paths, including render-only modifiers; source objects are never modified.
- PSD/PSB now write native shape masks, uniform strokes, supported opacity gradients and single-line text. Variable width uses editable outlines with saved centrelines. Original modifier paths/settings are retained as provenance, not executable Photoshop modifiers. The existing pixel, depth and ICC backend is preserved.
- **Rasterise Vector Artwork** requests pixels. **Use Flat Text Colour** keeps text editable and omits material lighting. **Flatten Image** merges document layers.
- The modifier editing guide and limitations are in [the offline vector manual](manual/vectors.html) and [development notes](development/PSD_VECTOR_RESEARCH.md). Photoshop itself was unavailable for validation; inspect native output before production delivery.

## Changes in v0.7.21 Alpha

- Added **SVG / GP Auto** as an additional output format. For plain Grease Pencil artwork from a direct Render Layers Image output, export Bézier and polygon paths in render-camera coordinates, with separate SVG groups and even-odd holes.
- Unsupported, mixed, effect-driven or non-orthographic sources automatically export the cached rendered PNG. Enable **Rasterise Vector Artwork** to request pixel output. The terminal logs each decision.
- Existing compositor socket order and PSD/PSB/OCA render and output paths remain unchanged. Native PSD vector layers were added in v0.7.39.
- Fixed an existing still-image filename sanitisation error that could remove letters from ordinary layer names.

## Changes in v0.7.20 Alpha

- Added a **Clear Cache** action under Backend / Recovery. By default it deletes old retained job folders while keeping the selected retry job. The adjacent **Clear all** checkbox also includes the selected job.
- Cleanup is limited to recognised `layered_render_*` and legacy `blend_psd_render_*` directories under the dedicated cache roots. Active workers and their retained jobs are protected, and finished artwork outside the job cache is unaffected.
- Verified PSD group colour labels and their paint-layer counterparts are written independently. Some Krita PSD imports show only the paint-layer colours, while PhotoCraft displays group colours correctly; PSD writing is unchanged pending a confirmed Krita importer issue.

## Changes in v0.7.19 Alpha

- Embedded ICC profiles in layered PSD/PSB: sRGB for display PNG8/PNG16; linear Rec.709 RGB for standard scene-linear EXR32. Custom OCIO overrides remain untagged with an explicit warning.
- PNG16 sample values are read directly without Blender's scene-linear conversion, preserving the view-transform-baked appearance.
- Paint layers inherit the nearest coloured Collection tag, including `.ungroup` and `.merge` results.

## Changes in v0.7.18 Alpha

- Transfer Blender Collection colour tags to matching PSD and PSB group labels.
- Preserve colour assignment through nested groups, group-name suffixes and separated stack segments.
- Keep pixel layers unlabelled. `.ungroup` removes its colour label; `.merge` rasterises its group, leaving a paint layer without group colour metadata.
- Refresh colour labels from the current Blender scene during Retry Conversion (No Render).
- Use the current Blender theme for approximate Photoshop swatch matching, with a stable fallback when the theme cannot be read.

## Changes in v0.7.17 Alpha

- Fixed in-session upgrade failure where Blender retained an older `layer_stack` helper with a matching API number but no `preview_merge_groups`.
- Fixed preview blend-mode lookup for the Blender add-on package and the standalone worker.
- Existing `.merge`, `.ungroup`, group and colour behaviour unchanged.

## Changes in v0.7.16 Alpha

- Implement `.merge` on Blender Collections for PSD/PSB and OCA: rasterise the ordered child render layers into one paint layer named after the Collection, without the `.merge` directive.
- Keep sibling artwork, `.ungroup` ancestor handling and grouped blend metadata intact. `.ignore` omits unwanted layers and `.ref` artwork stays hidden or marked as reference.
- Check Export Status previews merged paint layers as `[MERGED LAYER]`. Terminal export logs report each rasterised group.
- Open the manual as ten short offline HTML pages with section-aware navigation. The XML-backed tag and blend registries remain authoritative.
- `.merge` is an export operation; the add-on does not alter the Blender Collection or source View Layers.

## Changes in v0.7.15 Alpha

- Name separated nested instances of the same Collection, including `Hood-Hood_FG` and `Hood-Head_Back`, even when their parent groups differ.
- Describe a single subcollection export more precisely, such as `Hair-UpperLashes`.
- Retain same-name group/layer pairs such as `Collar/Collar` and `SnakeTail/SnakeTail` until compatibility policy requires a change.
- Document Collection grouping and `.suffix` behaviour in the offline manual. Existing terminal tree preview remains the diagnostic; no new UI buttons.

## Previous changes in v0.7.14 Alpha

- Preserve Blender Collection ancestry in consecutive exported group segments; retain the parent name when suffixing repeated groups.
- Use immediate child Collections for suffixes where unique, then descend to distinguish repeated branches. Suffix every competing MainBody group when all have distinct identifying children.
- Compare nested Collection inclusion only against outputs associated with the same source artwork branch. Unrelated render View Layers no longer suppress Eye/Membrane or Eye/Shade refinement.
- Print attribution, relevant peer View Layers and the final group tree in Blender's terminal from Check Export Status, F12, or Retry Conversion. No additional UI control.
- Keep group and pixel layer duplicate names as authored, pending an application-specific compatibility policy.
- Remove developer build instructions from the user manual.

## Documentation

In the add-on Preferences entry select **Open HandOff User Manual**. The offline manual starts at `manual/MANUAL.html` and links to the other topic pages. The layer-tag and blend-mode reference sections are generated from `compatibility/tags.xml` and `compatibility/blend_modes.xml`.

## Compatibility

The installed Python package is `handoff`. Legacy `blend_psd_tools` identifiers and existing saved settings remain supported for compatibility. Installation includes platform-specific Pillow wheels and a bundled PSD writer. Native File Output rendering remains available even without the extension.

## Links

- [Author - Simon Heggie on GitHub](https://github.com/SimonHeggie)
- [Simon Heggie on LinkedIn](https://www.linkedin.com/in/simon-heggie-94a1ba40/)

## Credits

Tag mappings reference Esoteric Software, Adobe, Nicolas Dufresne / RxLaboratorio, Krita/KDE, and OpenEXR. The complete attribution and links are in the user manual. Third-party components retain their own notices.
