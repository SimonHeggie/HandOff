# HandOff v0.7.52 Alpha 1 — Initial Consolidated Release

The first consolidated **HandOff**-branded alpha package, replacing the earlier public Comp-IO/rename preview releases in the Releases list. Previous release descriptions are preserved verbatim in [historical release notes](https://github.com/SimonHeggie/HandOff/blob/main/docs/HISTORICAL_GITHUB_RELEASE_NOTES.md), along with the existing development history and historical Git tags.

## Included capabilities
- Compositor File Output integration and independent layered PSD/PSB, OCA, SVG, image and font deliverables.
- Blender Collection hierarchy, authored layer order, supported blend modes, colour labels and established naming directives.
- Layered OCA stills and cel animation with the existing seven export controls.
- Supported Grease Pencil SVG vector artwork in OCA, with optional rendered PNG companion/fallback assets.
- Clean OCA asset filenames, optional trimming and correct placement, plus sequence and retry handling.
- HandOff branding, the `handoff` package, legacy project compatibility, required bundled font/template assets and pinned Pillow wheels.

## Installation
Download **the attached Blender add-on ZIP**, not GitHub's automatic source ZIP. Install via Blender **Edit → Preferences → Add-ons → Install from Disk**. Disable/uninstall any old `blend_psd_tools` or other HandOff installation first to avoid duplicate render handlers.

**Alpha warning:** Validate exports in their intended receiving applications. The available test evidence does not establish a complete Blender 5.3 production integration pass.

[Manual](https://github.com/SimonHeggie/HandOff/wiki) · [Source](https://github.com/SimonHeggie/HandOff) · [Preserved historical notes](https://github.com/SimonHeggie/HandOff/blob/main/docs/HISTORICAL_GITHUB_RELEASE_NOTES.md)
