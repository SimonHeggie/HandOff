# HandOff

**Hit render, go home.**

**Layered asset interchange and publishing for Blender.** HandOff extends Blender's **Compositor > File Output** node with additional export destinations. From the same render, it can assemble layered artwork, editable vector documents, frame-based OCA animation and other deliverables while retaining Blender's ordinary File Output functionality.

Created and maintained by **Simon Heggie**. **Current release: [v0.7.51 Alpha 1](https://github.com/SimonHeggie/HandOff/releases/tag/v0.7.51-alpha.1)**. This is alpha software; inspect its output before production delivery.

## What it does today

| Destination | Implemented output | Important boundary |
| --- | --- | --- |
| **PSD / PSB** | Layered Photoshop-format artwork, Collection-derived groups, supported paint-layer blend modes and colour labels; selected Grease Pencil/Curve/Text content can become native shapes, paths or text | Unsupported artwork uses rendered pixels and, where supported, SVG-linked sources. Vector and editor round-trips are not guaranteed. 32-bit float PSD/PSB is experimental. |
| **OCA** | Layered still documents; **Render Animation** writes a frame sequence with relative image assets, frame rate and exposure holds | OCA artwork is raster-based here. There is no exported Blender rig, skeletal animation or transform-curve interchange. |
| **SVG** | A layered SVG with supported editable Grease Pencil strokes, closed 2D Curve paths and live Text; preserves supported grouping, paint and clone relationships | Requires an orthographic render camera and Film Transparent for vector extraction. Unsupported effects/objects use PNG fallbacks. |
| **PNG / TIFF / JPEG** | Per-input images or a flattened image | JPEG is RGB only. Format-specific bit depths apply. |
| **OpenEXR** | Additional EXR images, including layered output options | Processing large/multilayer EXRs can be memory-intensive. |
| **Fonts / Text Assets** | Copies recoverable referenced fonts and writes a `.fonts.json` index with text-object references | The bundled package **does not** include the optional Bfont OpenType/CFF companion; Blender's built-in Bfont may be recovered as PostScript `.pfb`. |

These are available through **Additional Outputs** on a compositor File Output node. The format selector also offers 8/16/32-bit choices where supported; do not assume every destination supports every depth.

## How to use it

1. Install the **release asset** `HandOff-v0.7.51-alpha.1-blender-addon.zip` through Blender's **Edit > Preferences > Add-ons > Install from Disk** and enable **HandOff**. The add-on declares Blender **5.0 or newer** as its minimum; this is not a claim of validation against every later Blender build.
2. In the **Compositor**, connect the desired image sources to a **File Output** node. Each connected input represents a layer or image contribution. **Input/socket order determines stack order**.
3. Select that File Output node, open the **Node** tab of the right sidebar, and find **HandOff - Additional Exports**. Add the destinations you need, set paths and options, and enable them.
4. Use **Check Export Status** before rendering. It reports source Collection inference, hierarchy and tag issues; details are also printed in Blender's terminal.
5. Use **Render Image (F12)** for a still, or **Render Animation (Ctrl+F12)** for an OCA frame sequence. The regular File Output node continues to work independently.
6. If a retained render cache exists, **Backend / Recovery > Retry Export (No Render)** can reconvert supported outputs after edits to names, tags or destination settings. **Clear Cache** removes retained jobs without deleting delivered files.

The offline user manual is available from the add-on Preferences (**Open HandOff User Manual**) and in [the repository's manual index](handoff/manual/MANUAL.md).

## Layer structure, directives and interchange

HandOff uses **Blender Collection ancestry** to form document groups, while preserving the order of File Output inputs. Nonconsecutive artwork from one Collection may require separate output-group segments; Check Export Status previews the result.

Authoring directives can be appended to Collection/layer names without altering the source geometry:

| Example | Effect |
| --- | --- |
| `Character.merge` | Merge a group into a raster paint layer |
| `Guides.ref` | Mark/reference guide artwork (destination behaviour varies) |
| `FX.ignore` | Omit the corresponding export subtree |
| `Parts.ungroup` | Promote children without the group container |
| `Shadows.multiply`, `Glow.add` | Request a supported document blend mode |

Other directives cover initial visibility and exported names, paths and grouping. **Tag Compatibility** offers **No Conversion** (default), **Spine**, **Photoshop Generator**, and **OCA / Krita** mappings. These translate supported document naming/metadata conventions; **Spine compatibility does not mean exporting a `.spine` project, bones or a running Spine rig**. Unsupported conversions are retained or reported rather than silently invented.

References: [Layer tags and format mappings](handoff/manual/LAYER_TAGS.md), [blend modes and approximations](handoff/manual/BLEND_MODES.md), [Collection hierarchy](handoff/manual/groups.html), [Spine PSD directives](handoff/manual/tags-spine.html).

## Vectors, rendering and editability

For compatible source artwork, the SVG writer projects evaluated **Grease Pencil**, **Curve** and **Text** content into editable vector elements. It supports a defined subset of fills, strokes, Bézier handles, pressure strokes, gradients, text styles and GP modifiers. Some shared GP datablocks are represented using SVG clones. Source relationships can be retained as metadata.

It is **not** a general converter for every Blender shader or procedural effect. Lighting, masks, complex gradients, 3D objects, non-orthographic projections and unsupported modifiers may be rasterised; approximated blend modes are reported. The PSD/PSB writer can preserve supported native vector/text representations, but some paths require linked SVG sources plus a raster preview. Target editors may interpret those differently.

For specifics and conversion limits, see [SVG and vector artwork](handoff/manual/vectors.html) and [the feature matrix](handoff/compatibility/vector_features.csv). Do not infer universal Photoshop, PhotoCraft, Krita or Inkscape round-trip compatibility from the availability of an output format.

## Installation, upgrades and dependencies

- Download the ZIP attached to the **[GitHub release](https://github.com/SimonHeggie/HandOff/releases/tag/v0.7.51-alpha.1)**, **not** GitHub's automatically generated source ZIP. The source checkout omits six pinned Pillow wheel binaries that are included in the installable package.
- The bundled Pillow wheels are for **CPython 3.13** on their supported platforms. Blender builds using another Python ABI (including 3.14) need compatible dependencies; the package cannot be assumed to work unchanged.
- **When upgrading from Comp-IO / `blend_psd_tools`: disable and uninstall the old add-on first.** `handoff` is a different Python package, so enabling both may register duplicate render handlers. Old Blender RNA properties and `blend_psd.*` operator IDs are deliberately retained for saved-file and script compatibility. Some package-specific preferences may need setting again.
- Save a backup of working Blender scenes before migration. See [migration details](docs/RENAME_MIGRATION.md) and the [wheel manifest](docs/PILLOW_WHEELS.md).

## Release status and known limits

**v0.7.51 Alpha 1 is principally the v0.7.50 functionality with a product/package rename and legacy-data compatibility handling.** It is **not** a new Blender-to-Blender document exporter. Tests and ZIP validation have been run, but a complete interactive Blender integration pass is still outstanding. The optional Bfont-compatible `.otf` asset is absent; the documented fallback is to recover the original built-in `.pfb` where possible.

See [accurate release notes](docs/RELEASE_NOTES_v0.7.51-alpha.1.md) and the preserved [development history](docs/DEVELOPMENT_HISTORY.md).

## Roadmap and product domains

These are **planned directions**, not features claimed for this release.

- **Art Source:** editable assets, animation, rigging and source-document interchange. Next: editable Blender-to-Blender handoff, followed by evaluated animation isolation and capture.
- **Deployment:** game/engine delivery, packaging, publishing, server deployment and web services.
- **Marketing:** promotional output and content deliveries.

Advanced OCO, Rive and Spine rig-format work is deferred until Blender-native handoff and animation isolation/capture are reliable.

## Licensing and credits

HandOff is authored by **Simon Heggie**. The vendored `psd_tools` library retains its [MIT licence notice](handoff/PSD_TOOLS_LICENSE.txt); **the project as a whole has not yet been assigned a licence in this repository**. Third-party notices and technical reference links are available in the [manual](handoff/manual/README.md). Do not assume the vendored-library licence applies to all HandOff source code.
