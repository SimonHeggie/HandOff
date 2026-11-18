HandOff extends Blender's Compositor **File Output** node with independent exports for layered artwork, vector documents, animation and other production assets. A single render can produce several deliverables while Blender's normal File Output behaviour remains available.

This release includes the established Handoff exporters and introduces additional OCA 1.3 authoring and interchange features.

## Included capabilities

- **PSD / PSB:** Layered Photoshop-format documents with Collection-based groups, layer ordering, supported blend modes and colour labels. Compatible Grease Pencil, Curve and Text artwork can remain editable; other content uses rendered pixels or supported linked SVG artwork.
- **SVG:** Layered vector documents containing supported Grease Pencil strokes and fills, 2D Curves and live Text, with raster fallbacks for unsupported artwork or effects.
- **OCA:** Layered still documents and animated frame sequences, including timing, exposure holds, relative artwork files and cropped frame placement.
- **Images, EXR and fonts:** PNG, TIFF, JPEG and OpenEXR output, including layered EXR options, plus recoverable font files and a `.fonts.json` index.
- **Layer organization:** Collection-derived groups, File Output input ordering, and naming directives such as `.merge`, `.ungroup`, `.ignore`, `.ref` and blend-mode suffixes. Supported naming mappings include Spine PSD, Photoshop Generator and OCA/Krita conventions.
- **Export tools:** **Check Export Status**, **Retry Export (No Render)** for compatible retained caches, **Clear Cache** and an offline manual.

## New in v0.7.53

- **OCA 1.3 project structure:** Canonical project folders with relative asset paths, separate metadata, consistent source identities and unique exported names. Project files and assets are validated before publication, with staged replacement of existing output.
- **Grease Pencil vector cels:** Supported drawings can be delivered as editable SVG cels within OCA animation. **Rasterise Vector Layers** uses rendered images instead, while **Keep Alternative Artwork** retains optional SVG or PNG companions without adding duplicate visible layers.
- **OCA layer and group authoring:** Dedicated View Layer and Collection controls for visibility, background status, layer and frame opacity, blend modes, alpha inheritance and group isolation.
- **Artwork reuse and references:** Eligible linked Grease Pencil artwork can use OCA clone layers. **Keep Independent** prevents sharing when needed. **Source View Layer**, position offsets, time offsets and **Nested OCA Document** support more complex OCA compositions and their referenced assets.
- **OCA export handling:** Improved naming, validation, exposure and image-precision handling, including supported 8/16-bit PNG and half/full-float EXR paths.

## Compatibility

Supported vector artwork remains editable where the destination permits it; unsupported effects use raster output. Blend modes, gradients, alpha clipping and colour management can render differently in receiving applications. Selective frame deduplication and capture of Blender object transforms, skeletal rigs and weights remain future work.

This is alpha software. Verify exported files in their intended applications.

## Installation

[Download the installable HandOff Blender add-on ZIP](https://github.com/SimonHeggie/HandOff/releases/download/v0.7.53-alpha.1/HandOff-v0.7.53-alpha.1-blender-addon.zip). In Blender, select **Edit > Preferences > Add-ons > Install from Disk**. Use the attached release ZIP, not GitHub's automatically generated source archive.

If upgrading from Comp-IO / `blend_psd_tools`, disable and uninstall the old add-on first to avoid duplicate render handlers.

Documentation: [HandOff Wiki](https://github.com/SimonHeggie/HandOff/wiki), [OCA authoring](https://github.com/SimonHeggie/HandOff/blob/main/handoff/manual/OCA_AUTHORING.md), [OCA controls](https://github.com/SimonHeggie/HandOff/blob/main/handoff/manual/OCA_CONTROLS.md), [OCA vectors](https://github.com/SimonHeggie/HandOff/blob/main/handoff/manual/OCA_VECTORS.md).
