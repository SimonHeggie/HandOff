# HandOff

**Hit render, go home.**

**Layered artwork and animation interchange for Blender.** HandOff extends the Compositor's **File Output** node so one Blender project can publish layered documents, editable vector artwork, animation and other production assets. You can configure several destinations on the same node; Blender's normal File Output behaviour is preserved.

HandOff is developed by **Simon Heggie** and is currently **experimental alpha software**. Check exported files in their destination applications before using them in production.

## What it exports

| Destination | Output |
| --- | --- |
| **PSD / PSB** | Layered Photoshop-format documents with Collection-based groups, supported blend modes and colour labels. Compatible Grease Pencil, Curve and Text artwork can retain editable vector or text representations; unsupported elements are rendered or accompanied by linked SVG artwork where supported. |
| **OCA** | Layered stills and timed cel animation with frame exposures and portable image assets. Supports eligible Grease Pencil SVG cels, raster alternatives, source-linked clone layers, nested OCA documents and OCA-specific layer/group properties. |
| **SVG** | Layered vector documents using supported Grease Pencil strokes and fills, Curve paths and live Text, with raster fallbacks for artwork that cannot be represented as vectors. |
| **PNG / TIFF / JPEG** | Individual layer images or flattened output. |
| **OpenEXR** | Additional EXR images, including layered output options. |
| **Fonts / text assets** | Recoverable referenced font files and a metadata index identifying their source text objects. |

For OCA animation, **Render Animation** exports the frame range as one timed document. Other document destinations currently export still artwork rather than an equivalent editable animation timeline.

## Key features

- **One render, multiple outputs:** configure independent destinations without replacing Blender's native File Output node.
- **Organised layers:** derive document groups from Blender Collections, with File Output socket order determining layer stack order. Preserve supported names, visibility, blend modes, colour labels and hierarchy.
- **Authoring controls:** use supported layer/Collection naming directives for merging, omission, grouping and blending. OCA also provides dedicated View Layer and Collection controls for opacity, exposure opacity, visibility, blending, alpha inheritance and source references.
- **Editable where possible:** keep supported vectors and text editable, and use rendered artwork when the destination cannot preserve the original source.
- **Export diagnostics and recovery:** use **Check Export Status** to spot hierarchy and compatibility issues; **Retry Export (No Render)** can rebuild supported outputs from retained cached renders.

## Getting started

1. Download the **installable add-on ZIP** from [GitHub Releases](https://github.com/SimonHeggie/HandOff/releases), **not** GitHub's automatically generated source ZIP.
2. In Blender, choose **Edit → Preferences → Add-ons → Install from Disk** and install the ZIP. Enable **HandOff**. The add-on targets Blender 5.0 and newer; check the release documentation for supported Python/platform dependencies.
3. In the **Compositor**, connect the desired image outputs to a **File Output** node. Input order determines exported layer order.
4. Select the node and open the **Node** sidebar → **HandOff - Additional Exports**. Add and configure your output destinations.
5. Run **Check Export Status**, then use **F12** for a still or **Ctrl+F12** for an OCA animation sequence.

When upgrading from the older Comp-IO / `blend_psd_tools` add-on, disable and uninstall the old add-on first to avoid duplicate render handlers. Back up important `.blend` files before upgrading.

## Current limitations

- HandOff does **not** yet transfer Blender armatures, bone weights or general object-transform animation into editable 2D rigs. OCA animation is currently built from artwork exposures and supported reference metadata.
- Vector conversion covers specific Grease Pencil, Curve and Text features; arbitrary 3D materials, lighting, effects and unsupported geometry can require raster fallbacks. The SVG vector path requires an orthographic camera and transparent film.
- Blend modes, colour handling, native vectors and linked artwork can be interpreted differently by Photoshop, Krita, SVG editors and OCA importers. Support for an output format does not guarantee a lossless editing round trip.

## Documentation and support

- [User manual](handoff/manual/MANUAL.md) · [GitHub Wiki](https://github.com/SimonHeggie/HandOff/wiki)
- [OCA authoring](handoff/manual/OCA_AUTHORING.md) · [OCA export controls](handoff/manual/OCA_CONTROLS.md) · [OCA vector artwork](handoff/manual/OCA_VECTORS.md)
- [Layer directives](handoff/manual/LAYER_TAGS.md) · [Blend mode compatibility](handoff/manual/BLEND_MODES.md)
- [Releases and change history](https://github.com/SimonHeggie/HandOff/releases) · [Report an issue](https://github.com/SimonHeggie/HandOff/issues)

## Licensing and credits

Created and maintained by **Simon Heggie**. The bundled `psd_tools` dependency carries its own [MIT licence](handoff/PSD_TOOLS_LICENSE.txt); this **does not establish a licence for the HandOff project as a whole**. See the [manual](handoff/manual/README.md) for additional credits and third-party notices.
