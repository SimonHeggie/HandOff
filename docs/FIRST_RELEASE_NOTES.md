# Handoff v0.7.50 Alpha 1

This is the first **Handoff repository release**, based on the existing **Comp-IO v0.7.50 Alpha** add-on source. This release does **not** represent a completed implementation of the planned Handoff feature roadmap.

## Included
- Existing Blender add-on functionality from the cleaned Comp-IO 0.7.50 source snapshot.
- Installable ZIP with the `blend_psd_tools/` package and six pinned, hash-verified Pillow 12.0.0 wheels for supported CPython 3.13 platforms.
- Source code, test harnesses, compatibility data and project documentation in the repository.

## Installation
Download `HandOff-v0.7.50-alpha.1-blender-addon.zip` from the release assets. The internal add-on module and UI still use the original `blend_psd_tools` / Comp-IO names for compatibility with existing projects. Do not install the GitHub-generated repository source ZIP as the complete offline add-on: it omits the Pillow wheels.

## Known limitations
- This snapshot has passed syntax and ZIP integrity checks, but has **not** been verified by a Blender integration smoke test as part of this release.
- Bundled Pillow wheels target CPython 3.13, not 3.14.
- The optional Bfont-to-OpenType conversion font asset was removed from the cleaned installation package. A fallback is present, but that exact conversion route is not included.
- Blender-native editable scene handoff, animation isolation/capture, and advanced OCO/Rive/Spine rig interchange are **future work**, not current release features.

## Licensing
Bundled `psd_tools` retains its MIT license notice. A project-wide Handoff license has not yet been chosen.
