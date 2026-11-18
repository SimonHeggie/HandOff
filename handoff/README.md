# HandOff for Blender

**Hit render, go home.**

By **Simon Heggie**. This folder is the Python add-on package installed as `handoff`. HandOff extends Blender's compositor **File Output** node with configurable, independent **Additional Outputs**. The existing native File Output still operates normally.

**Latest published build:** v0.7.51 Alpha 1. **In-progress source revision:** v0.7.53 Alpha 1 (not yet published). [Download the installable ZIP](https://github.com/SimonHeggie/HandOff/releases/tag/v0.7.51-alpha.1). The GitHub source archive omits Pillow binaries and is not the complete offline installation package.

## Upcoming OCA 1.3 additions in the v0.7.53 source revision

Validated canonical project folders, source-aware identities, clean portable assets, authored visibility/opacity/blend/group controls, Grease Pencil SVG cels, verified reference clones, nested documents and exposure retiming. These changes are pending source synchronization and validation. No object/bone/weight transform interchange is claimed. [Release notes](../docs/RELEASE_NOTES_v0.7.53-alpha.1.md).

## Quick start

1. Install the release ZIP in **Edit > Preferences > Add-ons > Install from Disk**; enable HandOff. The add-on declares Blender **5.0+**, with CPython **3.13** Pillow wheels in this release.
2. In the Compositor, connect image sources to a **File Output** node. Its connected input order controls document layer order.
3. Select the node. In the **Node** sidebar, expand **HandOff - Additional Exports**, press **+**, choose destinations, and configure their paths.
4. Use **Check Export Status** to inspect source Collection grouping, export hierarchy and tag warnings.
5. Press **F12** for still output. For layered **OCA** frame-sequence output, use **Ctrl+F12 / Render Animation**. Other document types are published using the final rendered frame.
6. Expand **Backend / Recovery** to use **Retry Export (No Render)** with a compatible retained cache, or to **Clear Cache**.

## Available export destinations

| Format | Purpose |
| --- | --- |
| `.PSD`, `.PSB` | Layered editable artwork; supported native vector/text conversion with rendered fallback and SVG sources where applicable |
| `.OCA` | Layered still or rendered frame-sequence animation, with relative image assets |
| `.SVG` | Editable document for supported Grease Pencil, 2D Curves and Text; PNG fallback where needed |
| `.PNG`, `.TIFF`, `.JPEG` | Individual images per input or one flattened output |
| `.EXR` | Additional OpenEXR output, including layered options |
| `FONTS` | Referenced/recoverable font files plus a `.fonts.json` manifest |

These destinations have different supported bit depths and conversion constraints. In particular, PSD/PSB 32-bit float handling is experimental; Grease Pencil/Curve/Text extraction to editable SVG requires an orthographic camera and Film Transparent. Unsupported artwork, masks, lighting, shaders and blends may need pixel fallback or may be approximated with a warning.

**Font limitation:** This ZIP omits the optional Bfont OpenType/CFF companion. Where recoverable, Blender's built-in Bfont is delivered in its original `.pfb` form. Do not expect a bundled Bfont `.otf`.

## Document organisation and names

Blender **Collections** supply export hierarchy and group colour tags; File Output input order determines stack order. Directives such as `.merge`, `.ungroup`, `.ignore`, `.ref`, `.multiply` and `.add` control supported export operations.

**Tag Compatibility** offers **No Conversion**, **Spine**, **Photoshop Generator** and **OCA / Krita**. These convert recognised document naming/metadata conventions. They do **not** export `.spine` rigs or animated Blender skeletons.

## Reference manual and technical details

- [Manual index](manual/MANUAL.md) and [offline HTML manual](manual/MANUAL.html) (also opened from Blender's add-on Preferences)
- [Layer tags](manual/LAYER_TAGS.md) and [blend-mode compatibility](manual/BLEND_MODES.md)
- [SVG and vector guide](manual/vectors.html), [PSD colour handling](manual/psd.html), and [OCA / getting started](manual/MANUAL.html)
- [Conversion feature matrix](compatibility/vector_features.csv)
- [Full project README and roadmap](../README.md)
- [Detailed historical development notes](../docs/DEVELOPMENT_HISTORY.md) (v0.7.14–v0.7.50)
- [v0.7.51 Alpha 1 release notes](../docs/RELEASE_NOTES_v0.7.51-alpha.1.md)
- [Rename / legacy compatibility](../docs/RENAME_MIGRATION.md)

## Upgrade warning

Do not enable the old `blend_psd_tools` and new `handoff` packages together: they can register duplicate render handlers. Some existing `blend_psd.*` Blender property and operator IDs intentionally remain unchanged to preserve saved projects and scripts. A full in-Blender compatibility smoke test has **not** yet been completed for this renamed package.

## Current development status

This is **alpha software**, not a completed Blender-to-Blender source-document handoff. Native Blender document creation, advanced animation isolation/capture and OCO/Rive/Spine rig conversion remain future work. Verify output appearance and structure in the receiving application before relying on it.

HandOff was designed and is maintained by **Simon Heggie**. Vendored `psd_tools` has its own [MIT licence notice](PSD_TOOLS_LICENSE.txt); the whole repository currently has **no declared project-wide licence**.
