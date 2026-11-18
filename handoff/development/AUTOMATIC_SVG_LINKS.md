# v0.7.48 automatic SVG linking

The latest user request replaces the v0.7.47 target-editor selector and locked
SVG-link checkbox. Both are removed from the node panel. Their RNA properties
remain hidden and loadable for saved-file compatibility; publishing ignores
their values. Retry strips the legacy fields from refreshed jobs.

One PSD/PSB writer serves all editors. Existing supported shapes and text remain
native. Unsupported vectors receive a relative SVG source link and visible
preview channels automatically. A contiguous shared GP gradient source with
matching paint configuration and no nested Collection boundary can stay in one
linked SVG composition, preserving its SVG clone graph. Other sources retain
the established smallest-safe conversion boundaries. Existing nonempty Blender
render pixels remain authoritative. Empty caches use only the verified GP
preview subset; unsupported empty artwork remains an explicit partial failure.

Link records are built and serialized before they are committed. Failed link
creation retains visible pixels and the SVG, with a notice. Rollback restores
the original external-source records, avoiding orphan links. Rasterise Vector
Artwork, Flatten Image, merged sources and disabled View Layers retain their
existing handling. Application validation remains recorded separately in the
shared CSV; it does not lock external SVG publishing or select another writer.

Changes are in `__init__.py`, `psd_worker.py`, `psd_svg_links.py`,
`psd_vectors.py`, `conversion_policy.py`, version declarations, the shared
capability CSV and generated manual. The pre-change backup is
`/tmp/asset-parts-auto-links-nlvjaqz1/before-v0747.tar.gz`.

Validation completed:

- 193 unit tests and 17 manual/registry tests passed. Tests cover automatic
  linking despite old False/PhotoCraft settings, unchanged rendered PNG8/16
  samples, native neighbours, preserved clones, link-write failure and explicit
  raster/flatten overrides.
- Native Blender 5.3 tests exercised the panel draw, legacy settings through
  save/reopen, the real package-only Retry operator, and automatic exports from
  real PNG8/PNG16/EXR32 caches. Linked PSD/PSB records, HDR samples, colour labels,
  relative assets and the existing ICC/custom-OCIO policy passed reader checks.
- The character exported from retained caches with one Shine Smart Object and
  four SVG clones. Its merged preview was pixel-for-pixel identical to the
  preceding export. The sRGB profile data matched apart from LittleCMS's
  creation timestamp. KDE's installed image reader decoded the preview.
- All root Python modules passed syntax parsing; real native tests exercised
  their imports and API calls. No character render was performed.

Private character output and matching SVG assets are packaged at
`/tmp/asset-parts-auto-links-nlvjaqz1/Automatic-SVG-Export.zip`. Photoshop and
PhotoCraft editing/save/reopen have not been verified in those applications.
The current application-independent checks establish record structure, source
references and preview fidelity, not editor-specific editing behaviour.
