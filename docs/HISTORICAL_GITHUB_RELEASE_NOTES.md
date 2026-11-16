# HandOff — Historical GitHub Release Notes

These are the verbatim release descriptions preserved before consolidating the public release list. The corresponding Git tags and repository commit history should be retained even if the old release entries are removed.

---

## v0.7.50-alpha.1 — HandOff v0.7.50 Alpha 1 - Initial Release (Comp-IO build)

- Published: 2026-11-15T00:58:53Z
- Original URL: https://github.com/SimonHeggie/HandOff/releases/tag/v0.7.50-alpha.1
- Release assets: HandOff-v0.7.50-alpha.1-blender-addon.zip, SHA256SUMS.txt

# HandOff v0.7.50 Alpha 1 — Initial Release

The initial release of the Blender add-on originally developed as **Comp-IO**. It adds independent export destinations to the compositor's **File Output** node, allowing one render to produce several deliverables. File Output inputs set layer order; Blender Collections supply groups.

## Features

- **PSD / PSB:** Layered artwork with Collection-based groups, colour labels, supported blend modes, and editable Grease Pencil, Curve or Text elements where compatible.
- **OCA:** Layered stills with **F12** and animated frame sequences with **Ctrl+F12**, including frame timing, exposure holds and relative image assets.
- **SVG:** Layered vectors from supported Grease Pencil, 2D Curves and Text, with rendered fallbacks for unsupported effects.
- **Image and font delivery:** PNG, TIFF, JPEG, OpenEXR (including layered options), referenced fonts and a `.fonts.json` manifest.
- **Layer controls:** `.merge`, `.ungroup`, `.ignore`, `.ref` and blend-mode directives, plus naming conventions for Spine PSD, Photoshop Generator and OCA/Krita.
- **Production tools:** **Check Export Status**, **Retry Export (No Render)** using retained artwork, **Clear Cache**, and an offline user manual.

## Install

Download **`HandOff-v0.7.50-alpha.1-blender-addon.zip`** from this release's assets (not GitHub's source ZIP). Install it through **Blender > Edit > Preferences > Add-ons > Install from Disk**. This original build installs as **`blend_psd_tools`** and declares **Blender 5.0+**. Its included Pillow wheels target supported **CPython 3.13** platforms.

This is an **alpha** release. Verify exported files in their target applications; 32-bit PSD/PSB support is experimental.

[User manual](https://github.com/SimonHeggie/HandOff/wiki) · [Development history](https://github.com/SimonHeggie/HandOff/blob/main/docs/DEVELOPMENT_HISTORY.md)

---

## v0.7.51-alpha.1 — HandOff v0.7.51 Alpha 1 - Naming and Compatibility Update

- Published: 2026-11-15T03:20:51Z
- Original URL: https://github.com/SimonHeggie/HandOff/releases/tag/v0.7.51-alpha.1
- Release assets: HandOff-v0.7.51-alpha.1-blender-addon.zip, SHA256SUMS.txt

# HandOff v0.7.51 Alpha 1 — Rename Update

**Renamed Comp-IO to HandOff**, including the add-on's Python package (`blend_psd_tools` → `handoff`). Existing export features are unchanged. Supported legacy identifiers remain readable for compatibility with saved projects and scripts.

**Upgrading:** Disable and uninstall the old Comp-IO add-on before installing HandOff to avoid duplicate render handlers. Download the **release ZIP**, not GitHub's source ZIP, and check your add-on preferences afterward.

For the feature list, see the [initial v0.7.50 release](https://github.com/SimonHeggie/HandOff/releases/tag/v0.7.50-alpha.1). [Migration details](https://github.com/SimonHeggie/HandOff/blob/main/docs/RENAME_MIGRATION.md).

