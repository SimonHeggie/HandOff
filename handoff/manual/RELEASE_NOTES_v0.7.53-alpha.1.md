# HandOff v0.7.53 Alpha 1 — OCA 1.3 Interchange

This update makes it easier to turn Blender artwork and animation into **portable, editable OCA projects**. It adds Grease Pencil vector cels, reusable artwork references, more control over exported layers and groups, and more dependable project packaging.

## What's new

- **Portable OCA 1.3 projects.** Export complete OCA document folders with relative artwork paths, consistent source identities and validated assets. Projects are prepared and checked before replacing existing output.
- **Editable Grease Pencil cels.** Export supported Grease Pencil drawings as SVG artwork inside OCA animation. Choose **Rasterise Vector Layers** for rendered images, or **Keep Alternative Artwork** to include an optional SVG/PNG companion without creating duplicate visible layers.
- **Reusable artwork and nested documents.** Share eligible linked Grease Pencil drawings through OCA clone layers, or keep instances independent. Reference other View Layers with position and time offsets, and include nested OCA documents with their required assets.
- **More layer controls.** Set OCA visibility, backgrounds, layer and frame opacity, blend modes, alpha inheritance and group isolation through Blender View Layer and Collection settings.
- **More reliable animation delivery.** Preserve frame exposure timing, transparent frames, layer order and cropped artwork placement. Improved asset naming and output validation help keep exported projects consistent. Supported image paths include 8/16-bit PNG and half/full-float EXR.

## Compatibility notes

Eligible Grease Pencil drawings remain editable; unsupported artwork or effects use rendered-image fallbacks. Blend modes, gradients, alpha clipping and colour appearance may vary between receiving applications. This is an alpha release, so check the result in the editor where you plan to use it.

## Installation

**[Download the Blender add-on ZIP](https://github.com/SimonHeggie/HandOff/releases/download/v0.7.53-alpha.1/HandOff-v0.7.53-alpha.1-blender-addon.zip)** and install it through **Blender → Edit → Preferences → Add-ons → Install from Disk**. Use the attached add-on ZIP, not GitHub's automatically generated source archive.

If upgrading from Comp-IO / `blend_psd_tools`, disable the old add-on first to avoid duplicate render handlers.

For setup and OCA options, see the [HandOff Wiki](https://github.com/SimonHeggie/HandOff/wiki), [OCA authoring guide](https://github.com/SimonHeggie/HandOff/blob/main/handoff/manual/OCA_AUTHORING.md), [OCA controls](https://github.com/SimonHeggie/HandOff/blob/main/handoff/manual/OCA_CONTROLS.md) and [OCA vector artwork guide](https://github.com/SimonHeggie/HandOff/blob/main/handoff/manual/OCA_VECTORS.md).
