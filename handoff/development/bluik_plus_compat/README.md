# Bluik Plus / HandOff OCA integration

This is an additive **development integration**, not an installed replacement
for Bluik Plus and not a new HandOff import destination. `stage.py` copies a
specified Bluik Plus source into an isolated test directory and applies focused
compatibility changes there. Installed Blender 5.0/5.2 extensions are untouched.
HandOff's production exporter changes are separate root-package modules.

## Baselines inspected

- Blender 5.0 `extensions/user_default/bluik_plus`: v0.8.0. Registration initially
  failed on removed `bgl`; a subsequent test also found `preferences.py` importing
  `bluik` instead of its own package. Both are corrected in staged copies.
- Blender 5.2 `extensions/user_default/bluik_plus`: v0.9.0-alpha. Contains
  `oca_transform_import.py`, pivot/pivotPosition and prototype transform code.
  Its standard OCA path is extended without rewriting that prototype.
- Archived `bluik-plus_v0.8.2_pivotPosition_origin_verbose.zip` also contains pivot
  handling. The local ordinary v0.8.2 ZIP matches the published GitHub asset SHA:
  `3fd45961392c00d9ae490ca3eaa3f5ed7dd8505fdf0ed77566dda9796a28b6ac`.
- GitHub [Bluik Plus releases](https://github.com/SimonHeggie/Bluik-Plus/releases):
  latest published asset inspected was v0.8.2; main contains reference files rather
  than the newer installed Python implementation. No remote changes were made.

New code uses only the actual Blender 5.3 API. Probes record SVG import support,
GP drawing copy/remove signatures and Time/Opacity modifier properties. Existing
Bluik scene creation, planes, materials and TexAnim handler are reused.

## What the staged integration adds

- Standard 1.3 document dispatch, with legacy/prototype dispatch left intact.
- Direct file or canonical project-directory loading; correct relative paths.
- GP SVG drawing sequences with Bézier handles, attributes and materials copied
  through actual GP drawing APIs. Unsupported SVG features use existing rendered
  companions, with source SVG references preserved; no doubled artwork.
- Cropped raster dimensions and centres, absolute timeline frames, blank frames,
  exposure ends, frame opacity and hidden/reference layers.
- Source-ID clone resolution, including forward references and clone chains.
  GP clones share the actual GP datablock. Per-instance opacity is applied with
  a native GP opacity modifier. Delayed drawings use stepped native fixed-frame
  selection, avoiding dependence on scene-range retiming/loop settings.
- Relative-first nested OCA loading, source layer IDs and timeline offsets.
- Numeric labels and OCA metadata retained on imported objects/Collections.
- Missing/cyclic source errors cancel the operator rather than report success.

## Boundaries: do not claim complete native preview fidelity

Bluik's existing 3D layer model does **not** reproduce Inherit Alpha, isolated
opacity across overlapping group children or arbitrary paint blending exactly.
Those properties are retained and warnings are explicit. Group-clone retiming
also needs a separate animation-instance design. Native GP cannot reproduce all
SVG gradients, filters or clones; compatible rendered companions remain necessary.
The legacy pivot prototype is preserved and its dispatch is checked, but its
editing/animation behaviour is not newly certified by these standard-OCA tests.

HandOff's OCA files and its separate OCA composition tests preserve standard
alpha/group/reference semantics. Successful Bluik import is not evidence that
these remaining 3D preview limitations have disappeared.

## Reproduce

From this directory, using a fresh empty output directory:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 run_validation.py \
 --blender /home/simon/.Applications/Blender/beta/blender/blender \
 --bluik-source /home/simon/.config/blender/5.2/extensions/user_default/bluik_plus \
 --results /tmp/handoff-bluik-recheck
```

The runner exports a real three-frame scene, imports it, edits shared GP data
and renders both instances, exports an authored reference/opacity/nested project,
checks a delayed drawing against an independent same-time drawing copy, and
reopens the saved Blender document. It records functional success and clean
shutdown separately. It returns nonzero for the known sandbox audio shutdown
hang, including when functional tests pass. No preferences are saved.

`source-patches-*.json` preserves source hashes and diffs. The original installed
sources plus `stage.py` and `oca13_import.py` fully reproduce the test copy;
generated renders/caches stay outside the installed package. Installing these
changes into a Bluik extension requires a separately writable destination; this
session only permits writes inside HandOff and `/tmp`.

## Clean SVG projects (2026-11-17)

The relocated Blender 5.3 `addons/bluik_plus` v0.8.0 has the same two registration
faults (`bgl` removed and `from bluik import dublf`). `stage.py` corrects them in
an isolated copy. A ZIP built from that copy, then freshly extracted, was used
for native import/render tests of both full-size Hatshepsut OCA representations.
No installed Bluik directory was modified.

A standard SVG can now be imported without a HandOff-specific PNG companion.
Simple SVG still uses native editable GP. For gradients/unsupported GP features,
the staged importer first uses a supplied rendered alternative when present;
otherwise it calls an existing `inkscape` executable to render the actual SVG
page at the declared frame dimensions. These temporary PNG previews are packed
into Blender images and survive save/reopen. The OCA project is read-only and
gets no extra files. Missing Inkscape or renderer errors cancel import explicitly;
they do not produce an empty substitute. This path is a raster preview of SVG,
not a claim of editable GP gradient conversion or exact Blender paint blending.

Regression scripts: `development/test_oca_clean_blender.py` exercises fresh
three-frame renders, both representation choices, stale retry snapshots and
optional companion isolation. `test_svg_reopen_blender.py` verifies packed
previews after reopening an imported .blend. Existing standard clone/pivot
routing remains unchanged. Native image/compositing limits above still apply.

## Installed paint-blend repair (2026-11-18)

The installed Blender 5.3 Bluik package is now writable and repaired directly.
This snapshot's importer and `oca_shaders.py` mirror the installed implementation.
The staging helper accepts already-fixed sources without duplicate dispatch or
bgl wrappers, copies the shader module, and fixes the old Eevee engine ID.

Supported image-plane paint modes now have actual backdrop-aware shader nodes;
Screen is distinct from Add. Authored Object/Collection display names are
restored independently of OCA's unique transport aliases. See
`../OCA_BLEND_RECOVERY.md` for exact tests and remaining group/GP/alpha limits.
The older metadata-only blend warning descriptions above are historical.
