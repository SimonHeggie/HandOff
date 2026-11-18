# HandOff local completion build

Working source: `blend_psd_tools`. Installable package: `handoff`.
Version remains 0.7.50; no GitHub access, commits, publication or release bump.
The reference installation under `../OLD/handoff` was inspected selectively and
not modified. Recoverable source backups and hashes are in
`.backups/handoff-final-local`, excluded from the installable package and Git.

## Added and corrected

- Native OCA `vectorlayer`/SVG assets for individual supported GP compositor
  inputs, using the existing traced Scene/View Layer and evaluated SVG pipeline.
  Collection folders, logical input artwork and inner SVG paths remain distinct.
- OCA **Rasterise Vector Layers** and **Keep Rendered PNG Fallback**. Standard
  frame `meta.handoff` describes non-displaying companion SVG/PNG assets. Native
  PNGs also serve the existing template and artwork-JSON consumers. No new
  destination, rig conversion, clone-layer model or external OCA extension.
- Verified empty GP cache recovery through an isolated native Blender render of
  the captured GP-only source. Retry never renders. Native-confirmed blank frames
  retain blank semantics and a cache confirmation for later retries.
- Per-frame deferred SVG plans preserve animation. A logical animation that
  needs raster fallback uses one consistent layer type across its frames.
- Removed numeric layer-order filename prefixes. Frame numbers stay; collisions
  such as the three Eyes assets become `Eyes`, `Eyes-2`, `Eyes-3` in their existing
  group-relative directory. Existing layer names/order and deterministic IDs stay.
- Restored missing OCA group/paint label assignment using the reference
  installation's existing numeric palette. The shared Blender/PSD palette and
  PSD/PSB group-label writer are unchanged.
- Fixed two reproduced mixed-animation dispatch failures: pending SVG plans were
  mistaken for incomplete retries; refreshed Fonts jobs lacked the frame field
  that dispatch unconditionally accessed.
- HandOff naming comes from `branding.py`; version is unchanged. Legacy RNA,
  operators, metadata namespaces and cache aliases remain compatible. The renamed
  package disables the legacy handler set when safe, preserving saved settings.
- Added a local ZIP builder, generated-file exclusions, linked OCA manual pages,
  controls/defaults sourced from the existing shared OCA policy, and tests.

## Source and modules

Runtime additions: `oca_vectors.py`, `gp_raster_cache.py`, `package_compat.py`.
Focused runtime changes: `__init__.py`, `branding.py`, `psd_worker.py`,
`oca_sequence.py`, `oca_companions.py`.
Existing SVG/helper docstrings were rebranded; their conversion algorithms were
not rewritten. `assemble_psd` and Collection colour-mapping code remain unchanged.

Tests/build: `test_oca_vectors.py`, updated branding reload assertion,
`development/test_oca_vectors_blender.py`, `test_handoff_zip_blender.py`,
`inspect_hatshepsut_oca.py`, `build_handoff.py`; the existing OCA runner is reused.
Documentation: README, manual pages, shared manual generator, OCA guides,
this report, `.gitignore`, and the development-instructions title.

## Actual production-scene evidence

The newest appropriate scene was `Remake_v38_TouchUps.blend`, saved November 15.
It was opened with scripts disabled and never overwritten. All native and
additional File Output destinations were redirected into owned test directories.
The source has frames 0–1; the production export check used frame 0, CPU Cycles
with one sample, at 12% resolution: **245 x 327** pixels. This was not a full-size
quality render or a target-editor visual sign-off.

The first full export reproduced the actual GP failure: Shine's cached PNG had
zero alpha while its captured SVG contained five valid editable objects. Native
renders of Shine alone, including direct compositor Image-pass tests, produced
nonempty pixels. Disabling its separate-GP-pass flag was not required. The
isolated native recovery repaired the cache; all **eight** test destinations
then completed: OCA, PSD, PSB, SVG, PNG, Fonts, rasterized OCA and unsupported-input
raster OCA. The exact Blender-internal cause of the full-pipeline omission remains
unconfirmed; no general render-setting workaround was imposed on the source.

The resulting document contains 21 artwork layers: a Shine SVG, native raster
artwork and the existing hidden blank Combined placeholder. Shine's SVG and PNG
alternative both measure **39 x 37**, centre **[24.5, 95.5]**. The three Eyes
filenames are collision-safe. `.merge`/`.ungroup`, nested folders, pass-through and
promoted blends remain. Native group and paint labels are present.

ForeArm_R physically measures **189 x 115** at this test resolution, including
one-pixel padding, rather than the full canvas. Positions and asset references
were checked. Repeating the production OCA conversion with rendering forbidden
produced **byte-identical OCA document data**, including IDs and frame metadata.

The published Shine SVG was rasterized using the installed CairoSVG and compared
with its actual native PNG: same dimensions, premultiplied RGBA RMSE approximately
**0.029** on a 0–1 scale. Antialiasing/gradient differences remain; this does not
claim pixel-identical SVG rendering. Native PNG is available for fidelity.

## Regression and installation checks

- **214 Python tests pass**, including seven new SVG/PNG/filename/blank-cache cases.
- **17 manual/XML compatibility tests pass**, including all offline links and
  unchanged tag/blend registry order.
- The existing seven-control Blender tests pass all 18 combinations of trim
  on/off, scale 50/100/200%, padding 0/1/4, with current options overriding old
  animation snapshots during retries.
- Native odd-sized 16-bit PNG and 32-bit EXR tests pass another 18 combinations;
  16-bit detail and HDR values remain. The 1536 x 2048 trimming regression test
  physically produces 1164 x 696 pixels with padding zero.
- New actual three-frame GP renders verify two independently editable GP inputs,
  moving bounds, nonempty PNG alternatives, an actual Blur input remaining raster,
  rasterized publishing, no alternative layer duplication, and a genuine blank
  frame. Deliberately emptying another actual cache exercises native recovery.
  A subsequent no-render retry of the confirmed-blank sequence is identical.
- The actual `handoff` ZIP installs through Blender's Install from Disk operator
  in isolated preferences/user scripts. Registration, Pillow's Linux x86-64
  Python 3.13 binary, Bfont resources, legacy settings and one handler set pass.
  The installed ZIP also runs the GP animation and mixed-format exports.
- PSD/PSB reopen with `psd-tools`; standalone SVG parses and renders; PNG/font
  deliveries complete. These checks do not establish target-editor edit/re-save
  compatibility. Required six cross-platform Pillow wheels, Bfont, profiles,
  compatibility registries and third-party licences are retained.

Structured evidence was generated in `development/validation/handoff-final.json`. The cleaned GitHub-ready source excludes this host-specific generated file (which contains absolute local paths); regenerate it using the fixtures if needed.
Reproduce with `development/run_oca_controls.py`, the new GP/ZIP fixtures and
`python3 development/build_handoff.py`. Native fixtures require Blender 5.3 and
isolated output/cache environment variables documented in their source headers.

## Remaining limits and installation state

Blender's natural shutdown still hangs here with a PulseAudio `pa_write()`
permission error, including the print-only factory-startup control that never
loads HandOff. Functional assertions finish; bounded tests terminate that hung
process. This is explicitly not a passing clean-shutdown test. The old preparation
crash was not reproduced in the completed production export; it is not claimed
fixed by an unrelated workaround.

Krita GUI and Photoshop/PhotoCraft GUI edit/save/reopen were not verified. The
installed Krita build cannot connect to this session's display and lacks an
offscreen Qt platform. SVG reader differences, gradient interpolation and the
limited direct GP-only eligibility for native cache recovery remain documented.

The live production source directory remains `blend_psd_tools`. This session's
parent `addons` directory is read-only, so a production rename was not performed.
The final ZIP installs as `handoff` and was tested in isolated user scripts;
that successful test is not represented as a completed host installation switch.
The existing reference under `OLD` remains recoverable. No unrelated add-on or
production Blender preference was changed.

## Cleanup and package

Generated Python bytecode, old owned test outputs/caches and isolated test
installations are removed after extracting the structured evidence. Procedural
fixtures, tests, source documentation and original source backups remain. The
cleanup manifest records exact deleted paths and reasons. Unknown experiments
and dynamic worker entry points are retained unless proven obsolete.

The local installable ZIP is `dist/HandOff-0.7.50-local.zip`, approximately
**31.8 MiB**, below the 50 MiB target. `dist/package-report.json` records its
exact size, file count and SHA-256. Final ZIP runtime files are compared against
the tested installed package before its temporary installation is removed.
