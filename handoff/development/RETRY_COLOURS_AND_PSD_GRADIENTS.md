# Retry, untagged labels and PSD gradient limitations — v0.7.46

## Fixed

Retry could enter `svg_collections.group_svg()` through the add-on package,
where the helper incorrectly imported the standalone `layer_stack` module.
Earlier worker tests preloaded the add-on root into `sys.path`, masking this
frontend failure. SVG grouping, consolidation and style helpers now import
package siblings correctly while retaining standalone worker support. A new
isolated test and the real Blender Retry operator exercise package-only imports;
neither preloads `layer_stack` nor adds the add-on root to the search path.

Known Blender Collections with `color_tag == NONE` now produce the explicit
`NO_COLOR` label. This stops ancestor colour inheritance, including an orange
ancestor stripped by `.ungroup`. Missing/unknown Collection metadata retains its
legacy fallback. SVG highlights use white (`#ffffff`). PSD records No Colour;
the supported PSD label palette has no white, so the receiving editor controls
the appearance of its untagged icon. No invented PSD colour index is written.

A PSD rendered fallback with zero alpha now adds a Diagnostics notice. The
exporter does not silently replace the missing render with a different preview.

## What the Shine PSD screenshot shows

The log's gradient-transform fallback is independent of SVG cloning.
`psd_vectors.load_artwork()` reads the complete `.vectors.json` model. SVG
`<use>` references are encoded separately, so they do not remove native PSD
shape instances. A regression test checks that one SVG original plus a clone
still produces both editable PSD shapes for supported paints.

The GP material gradient transform currently has no verified native PSD
representation. Its existing fallback is a pixel layer. The actual retained
`Shine.overlay` PNG (`layer_L0001_.png`) has alpha extrema **(0, 0)**, so that
layer is invisible even though the SVG vectors are present. Retry cannot restore
paint absent from the rendered cache.

The saved source was inspected: the View Layer GP filter and Combined/Depth
passes are enabled; objects are render-visible; GP layers have lighting off;
fill/stroke holdouts are off. A separate GP pass is also enabled. These facts do
not establish why Blender wrote an empty Image output. No render settings were
changed, and the precise Blender render cause remains unresolved.

## Smart Object recommendation; not implemented in this release

For vector paints that native PSD shapes cannot represent faithfully, an
**embedded vector Smart Object with the existing rendered preview** is the
appropriate next fallback to investigate. Keep native shapes/type where they
work, and retain clones in the standalone SVG. Detect unsupported paint or
transforms rather than assuming all clone families need rasterisation.

A PSD cannot directly execute SVG clone commands as native Photoshop shape
layers. Smart Objects are the corresponding container for reusable source
artwork. An embedded SVG may preserve gradients and compact organisation,
without requiring an external link. Where a target SVG importer cannot resolve
`<use>`, only the embedded compatibility payload could expand those references
into vector paths. Embedding alone does not fix an incompatible SVG renderer.
Shared Smart Object source IDs could later retain editing across instances.

This needs verified placed-layer/linked-data records, transformed previews and
actual target-editor Edit Contents/save/reopen tests. The bundled writer can
read Smart Objects but does not provide an established Smart Object creation
path. No speculative PSD records were added or existing fallbacks replaced.
There is no connected target-editor document session, so PhotoCraft's direct
SVG clone import has not been verified from this PSD screenshot.

Primary references:

- [Adobe Smart Objects](https://helpx.adobe.com/photoshop/desktop/create-manage-layers/smart-objects/smart-objects-overview-and-benefits.html)
- [Adobe PSD records, including sheet colour](https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/)
- [Photopea's Smart Object model, as a related browser-editor reference](https://www.photopea.com/learn/smart-objects)

## Validation and changed files

- **178 unit tests and 17 compatibility/manual tests passed.**
- The native package-only fixture executes `bpy.ops.blend_psd.retry_job()`,
  extracts GP vectors/clones, verifies white highlights and preserves source
  datablocks, positions and render flags.
- The same Retry operator was exercised on the actual character project and a
  private copy of `layered_render__if2kp7f`, without rendering or launching a
  worker against production destinations. All four jobs refreshed successfully.
- All four refreshed jobs were then assembled into private output destinations.
  The PSD reopened with all Shine groups/paint layers set to No Colour. The SVG
  retains four clones and white Shine/Sprite highlights. Existing gradient
  fallback and missing Combined placeholder behaviour remain unchanged.
- A regression test confirms an empty GP gradient fallback remains pixel data,
  emits a zero-alpha diagnostic and preserves its original SVG source.

Production changes: `svg_collections.py`, `svg_document.py`,
`collection_colors.py`, `psd_worker.py`; version metadata in `branding.py` and
`__init__.py`. Tests: `test_svg_collections.py`, `test_svg_export.py`,
`test_compio_hierarchy.py`, `test_psd_vectors.py`, `test_blender_reload.py`, and
`development/test_retry_package_blender.py`. README and the generated manual
were updated, including the colour-policy source in `workflow_notes.py`.

Audit and backups: `/tmp/asset-parts-retry-colours-2l6tiqm5/`.
Review copies: `character/outputs/Character.psd` and
`character/outputs/Hatshepsut.svg`. These retain the blank Shine raster;
they demonstrate the retry/colour fixes, not new PSD gradient support.
Production artwork and the source `.blend` were not saved or overwritten.
