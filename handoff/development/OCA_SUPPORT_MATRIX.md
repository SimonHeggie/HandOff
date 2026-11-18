# HandOff — OCA 1.3 compatibility audit and results

2026-11-16. Development source: installed `handoff/` only. No package migration,
branding change, release, GitHub operation, neighbouring add-on change or
production `.blend` save was performed. Original runtime/test sources were
backed up before modification in `.backups/oca13-compliance/` and
`.backups/oca13-layer-features/`.

## Blender paint-blend repair — 2026-11-18

Installed HandOff visibility and Bluik Plus shader/Eevee/name fixes are verified
in [OCA_BLEND_RECOVERY.md](OCA_BLEND_RECOVERY.md). This supersedes earlier
metadata-only preview limitations for the tested image-plane paint modes and
one-child isolated Shine Overlay. Multi-child isolated groups, Inherit Alpha
and arbitrary 3D ordering remain limited. Native three-frame/save-reopen, both
production render engines and actual ZIP extraction were tested; 243 HandOff
unit tests pass.

## Clean delivery correction — 2026-11-17

The latest user export reproduced an actual option-coupling defect: Write Spine
JSON (previously on by default) forced `_raster` PNGs even when Keep Rendered PNG
Fallback was off. Rasterise Vector Layers also retained SVG sources implicitly.
Both paths now honour a single explicit Keep Alternative Artwork setting. With
it off, each artwork publishes its selected SVG or PNG/EXR only. This setting
keeps the existing RNA identifier `oca_keep_png`; saved explicit choices survive.
Write Spine JSON now defaults off. Optional companions remain available when
selected; `_companions` is a HandOff convention, not required OCA structure.
The standard frame `meta` permits custom data, but does not define a native
alternative-attachment selector: https://oca.rxlab.guide/specs/frame.html .

Template previews use private temporary files. Explicit Spine output keeps its
additional vector preview images under `_companions/images`, without adding
alternative references to the OCA document. Unreferenced files created by this
export and replaced by clone/nested references are removed from clean output.
Routine raster selection remains in the terminal only, not UI notices. Disabled
sources with no compatible render still produce a useful blank-placeholder
notice; the duplicate OCA placeholder notice was removed. Scale above 100% is
ordinary resampling, not AI enhancement; the existing 400% supported range stays.

**Verification:** 243 tests pass. A fresh native three-frame fixture exercises
four clean/optional-companion combinations, changing current options over stale
animation snapshots. A linked-GP variant additionally confirms that clones retain
only referenced artwork (six frame assets instead of nine), without changing
layer order. The conservatively verified clone case uses integer-pixel
translation; a fractional-pixel crop disagreement correctly remains independent.

The user's latest full-size Hatshepsut render cache was copied before use. Clean
SVG and raster projects each contain 21 logical layers and 20 referenced artwork
files (Combined is a hidden blank), no `_raster`, `_vectors` or `_companions`, and
no unreferenced PNG/SVG files. The validator and installed Krita reader both pass.
Both projects imported/rendered through a compatibility ZIP freshly extracted
into an isolated Blender 5.3 installation. SVG previews were packed, saved and
reopened successfully. Krita GUI rendering is still unverified. Functional native
tests pass; the existing environment audio shutdown hang still requires bounded
termination after success.

The relocated Blender 5.3 Bluik v0.8.0 has removed `bgl` and wrong-package import
failures. The staged compatibility package fixes both. Unsupported native GP SVG
features use a supplied companion when present; otherwise an existing Inkscape
renders the SVG at the OCA frame dimensions and the temporary PNG is packed into
the .blend. No extra assets are written into the OCA project. This is a raster
preview, not native editable GP gradient support. Missing renderer/errors cancel
explicitly. Existing blend/group/Inherit Alpha preview limits still apply.

Installed HandOff was updated; installed Bluik and the user's export directory
were not changed because they are outside this session's writable roots. A tested
replacement ZIP is at `.build/Bluik-Plus-Blender53-compat.zip` (86,676 bytes).
Backups are under `.backups/oca-clean-delivery/`.

Changed runtime files: `__init__.py`, `oca_controls.py`, `oca_vectors.py`,
`oca_project.py`, `oca_sequence.py`, `oca_companions.py`, `psd_worker.py`.
Changed/new tests and guidance: `test_oca_vectors.py`,
`development/test_oca_clean_blender.py`,
`development/bluik_plus_compat/oca13_import.py`,
`development/bluik_plus_compat/test_svg_reopen_blender.py`, its README/source patch
evidence, and `manual/oca.html`. No PSD/SVG writer changes, branding changes,
version bump, release or remote operation.

Evidence outside the installable package:

- `/tmp/oca-clean-delivery/export-results.json` — full-size copied production cache.
- `/tmp/oca-clean-delivery/unit-suite.log` — 243 tests.
- `/tmp/oca-clean-delivery/native-results.json` — fresh render, both production imports, packed reopen.
- `/tmp/oca-clean-delivery/linked-check2/native-results.json` — clean linked-GP sequence.
- `/tmp/oca-clean-delivery/krita-reader.log` — both clean projects accepted unchanged.
- `/tmp/oca-clean-delivery/package.json` — tested ZIP size/hash.

## Follow-up: Bluik Plus integration and remaining standard export features

The follow-up implementation adds `oca_authoring.py`, `oca_features.py`,
`oca_references.py`, and `oca_render.py`. It extends OCA publication only, with
source-specific authoring panels in View Layer and Collection Properties.
`oca_project.py`, `oca_controls.py`, `oca_companions.py`, `psd_worker.py` and
`__init__.py` integrate these features. Existing suffix promotion is retained;
explicit OCA blend overrides correctly undo obsolete automatic group promotion.
Standalone SVG/PSD/PSB behaviour and colour mapping are unchanged.

**Recommended authoring design:** linked GP duplicates in separate View Layers.
This reuses Blender's native shared data. A real three-frame fixture compared
that with independent data copies, a rotated linked copy and a processed raster
input. Only the verified translation pair became an OCA clone. An advanced
Source View Layer selector additionally provides explicit references and time
shifts; it fails on ambiguous/missing/cyclic sources. No names or geometry are
changed in Blender to manufacture a relationship.

**Bluik source comparison:** the user-supplied Blender 5.0 folder contains v0.8.0;
Blender 5.2 contains v0.9.0-alpha with the pivot/transform prototype. Both were
read-only sources for isolated copies. The ordinary local v0.8.2 ZIP was verified
against the published GitHub SHA-256. The special v0.8.2 pivot archive also has
pivot handling. Standard OCA dispatch does not modify the legacy pivot path;
legacy pivot editing is not newly certified. Both local versions register and
import the standard linked-artwork test after staged compatibility fixes.

**Native receiver proof:** Bluik Plus's existing scene/plane/material/TexAnim
facilities are reused, with actual Blender GP SVG import and drawing APIs.
A staged `oca13_import.py` adds GP drawing sequences, centre-aware cropped image
placement, ID references, source timing and nested documents. It preserves actual
shared GP data. Editing one drawing changed **99 and 131 pixels** in the two
rendered instances. The delayed drawing matched an independently copied expected
drawing rendered at the same scene time, with **zero F32 pixel error**. Scene-time
and modifier animation are checked independently of visual antialiasing variation.
Imported shared references survived a saved `.blend` reopening.

**Important remaining receiver limits:** Bluik's 3D plane model approximates
isolated opacity across overlapping children and paint blending, and stores
Inherit Alpha without native clipping. These are correctly written/evaluated in
HandOff's OCA path, but full Bluik visual equivalence is not claimed. Group-clone
retiming also needs a separate instance-animation design. SVG features outside
the native GP importer use non-displaying source references plus the rendered
companion. General pivots/transform animation remain outside OCA 1.3.

**Fresh integration results:** Hatshepsut was rendered again at 12% / one CPU
sample: 21 inputs, one SVG, nonempty GP fallback; PSD, PSB, SVG, PNG, fonts and OCA
completed. The full native seven-control matrix and all 19 U16/F32/F16 precision
combinations passed again. Ten native blend constructions matched exactly;
OCA/SVG Soft Light versus Blender Soft Light differed by up to **0.03520** for
the selected linear RGB values, so that mapping is explicitly not exact.
The F16 project also imported as floating-point HDR through Bluik without 8-bit
source conversion. Krita's reader loaded the new clone/nested projects unchanged;
Krita GUI import remains unverified.

**Combined test runner:** `development/bluik_plus_compat/run_validation.py` ran
all five native stages successfully: shared export, import/edit render proof,
authored export/retry, authored import/timing proof, and saved-file reopening.
`/tmp/bluik-oca13/combined-final/process-results.json` records functional success
separately from the pre-existing factory-startup audio shutdown hang. No production
Blender file, installed Bluik package, preferences or GitHub content was changed.
The tested integration and source patches are durable in
`development/bluik_plus_compat/`; generated projects/caches remain outside source.

Examples and additional evidence:

- `/tmp/bluik-oca13/combined-final/shared-export/exports/Shared.oca/Shared.oca`
- `/tmp/bluik-oca13/combined-final/authored-export/exports/Authored.oca/Authored.oca`
- `/tmp/bluik-oca13/combined-final/shared-import/shared-edit-proof.json`
- `/tmp/bluik-oca13/combined-final/authored-import/time-offset-proof.json`
- `/tmp/bluik-oca13/handoff-final-suite.log` — 239 tests
- `/tmp/bluik-oca13/production-final.log` and `precision-final.log`
- `/tmp/bluik-oca13/blends-final/result.json`
- `/tmp/bluik-oca13/version50-final.log` — staged v0.8.0 import

Manual guidance is in `manual/oca.html#oca-authoring`. Reproduction and exact
source-version notes are in `development/bluik_plus_compat/README.md`.

## Audit and implemented changes

The initial baseline passed 214 Python tests. The existing exporter already
supported the seven controls, image processing, SVG/PNG companions, sequences,
Collection directives, hierarchy, labels and blending. Those implementations
were retained. The compliance gaps were legacy-only project layout, duplicate
OCA names, order-dependent UUIDs, no complete asset validator, no separate
metadata file and incomplete publication protection.

New OCA destinations default to the standard accessible project directory:
`Character.oca/Character.oca`, `Character_meta.json`, and group-relative artwork.
Existing saved destinations and retained jobs default to **Legacy Document +
Assets**. The OCA Layout selector makes the choice explicit. A file/directory
layout conflict raises an error before replacing anything; choose a new
name/location or the existing layout. No ZIP is required.

All OCA publication now happens in private staging. Names and paths are made
portable, metadata is written separately, and the manifest and actual assets
are validated before replacement. Recoverable rename failures restore the
previous publication. The final success message/status refers to the published
path. This protects against ordinary validation/I/O failures, not a guarantee
against power loss in the middle of filesystem operations.

New layer identities use a persistent File Output node UUID and Blender socket
identifier, independent of socket order/name. Collection groups and merged
layers use their authored paths. UUIDs for frames derive from layer identity
and frame number. Duplicate document-level names receive stable exported
aliases such as `Eyes (2)`; original names/source names remain in layer metadata.
Blender names, stack order, naming directives and PSD/SVG naming are unchanged.
New node UUIDs become persistent across sessions when the project is saved;
fresh background runs of an unsaved original file cannot persist newly assigned UUIDs.
Collection renames change path-derived group identity; indistinguishable legacy
entries without source identity use an occurrence fallback. These limitations
are recorded rather than claiming universal round-trip identity.

An optional **Half-float EXR (F16)** setting appears for 32-bit OCA destinations.
It changes published EXR storage only. Render caches remain F32 and reusable;
current settings override frame snapshots during retry. It defaults off, so
existing U8/U16/F32 behaviour is unchanged.

Metadata follows the separate-file requirement in the
[OCA specification](https://oca.rxlab.guide/specs/meta.html). It identifies
HandOff, its current version and Blender's actual version; notices are stored
under `meta.handoff.warnings`. Existing artist metadata is preserved. Explicit
Scene string properties `author`, `copyright`, `license`, `licenseLong`,
`licenseURL`, `description`, `created` can supply those fields. No artist or
licence is inferred. Invalid metadata produces a property-specific error.

## Support matrix

“Verified” below identifies the exact test boundary; it never means all target
applications have been tested.

| Capability | Status | Verification / limit |
| --- | --- | --- |
| A1 canonical `.oca/` directory | Newly implemented and verified | Native mixed GP/raster project and relocation; one root data file, separate metadata, local artwork |
| Legacy layout | Existing and verified | Native controls, production export, precision and animation fixtures; old jobs remain compatible |
| A2 unique document names | Newly implemented and verified | Repeated Paint/Eyes and same-name group/child cases; aliases preserve original-name metadata |
| A2 unique/stable IDs | Newly implemented and verified | Native socket reorder, saved-project reopen, still-to-animation, changing bounds; file-based reordered/merged-layer tests; path/legacy limits above |
| A3 validator | Newly implemented and verified | Version/root fields, dimensions, FPS, timeline, types/nesting, names/IDs, frames/durations/order, centres, formats/depth, paths and actual assets; exact offending layer/property in errors |
| Validator image decoding | Newly implemented and verified | PNG header/decode, SVG XML/viewport, EXR channels/storage/dataWindow plus Blender decoding when available; dimensions checked against metadata |
| Clone/nested reference validation | Newly implemented and verified | Small real documents: missing IDs, cycles, nested relative path preferred, absolute fallback/missing documents; reference export and validation are both tested in the follow-up |
| A4 separate `_meta.json` | Newly implemented and verified | Native author/licence/version capture, existing metadata preservation, type errors, no custom root fields |
| A5 portable filenames | Newly implemented and verified | Unicode/NFC, case-insensitive collisions, Windows reserved names, illegal characters, UTF-8 component length; all manifest/companion paths rewritten consistently |
| A5 safe replacement | Newly implemented and verified | Missing asset and injected rename failure preserve prior successful project; staging kept private |
| B1 hierarchy/order | Existing and verified | Native Hatshepsut 21 artwork inputs; synthetic groups/order; unchanged existing tree builder |
| Group pass-through/compositing | Existing and verified | Production Shine isolated Overlay group; ordinary pass-through groups; metadata/stack regressions; all importer visuals not verified |
| Collection/group/paint labels | Existing and verified | Production native export and existing metadata regressions; mapping untouched; app palettes may differ |
| `.merge`, `.ungroup`, `.ignore`, `.ref` | Existing and verified | Production SnakeTail merge, ungrouped Assets and existing tree tests; native `.ref` remains non-displaying; merged IDs additionally checked after reorder |
| Hidden groups and descendants | Existing and verified | Actual viewport-hidden rendered pixels retained when requested; metadata/template never reveal them; ignore-on omits descendants |
| Explicit background exclusion | Existing and verified | Actual View Layer designation; Combined is not guessed to be background |
| Independent editable layer/group/frame opacity | Newly implemented and verified | Explicit OCA authoring controls; native animated metadata/retry and isolated-group composition tests. Baked Blender transparency is retained separately |
| Baked opacity fidelity | Existing and verified | Native GP drawing opacity .5 yields expected fallback alpha while OCA opacity remains 1 |
| `inheritAlpha` | Newly implemented and verified in export/composition | Explicit View Layer/Collection publishing instruction; numeric composition tested. Bluik 3D preview retains the property but does not clip native planes |
| Reference layers | Existing and verified | `.ref` sets `reference:true` and non-displaying visibility; native mixed fixture and file tests |
| Transparent background | Existing and verified | Production and synthetic exports |
| Explicit coloured root background | Newly implemented and verified | Scene OCA Background RGBA control, native authored export and template composition; world colour is not inferred |
| B3 Normal/Multiply/Screen/Overlay/Add/Darken/Lighten | Existing and verified | Real Blender compositor EXR results versus published OCA layer blend: max channel error 0 in tested opaque linear cases; PSD blend code unchanged |
| Other OCA blend modes | Newly implemented; validation varies by mode | Explicit OCA registry selector publishes valid mode names. Ten tested native constructions match; Soft Light definitions differ. Eleven template formulas implemented; other template modes report omission, never blank replacement |
| B4 trim / centres / padding / scale | Existing and verified | 18 native control combinations; alpha-based physical crop, centred placement and 100% reconstruction; odd-sized high-depth fixtures |
| ForeArm_R trimming | Existing and verified | Full-resolution production cache 2048×2729 → 1550×928, alpha box [73,1747,1623,2675], centre [848,2211]; reconstructed visible pixels identical |
| Reported 1536×2048 → 1164×696 case | Existing and verified | Existing focused regression reproduces that exact nonzero bound, including hidden RGB under zero alpha |
| C1 individual GP SVG layers | Existing and verified | Native fixture produces two vectorlayers plus one compositor-processed paintlayer; Hatshepsut has one relevant Shine input containing its five GP objects |
| Editable GP strokes/fills | Existing and verified, visual limits | Inkscape actually renders emitted SVG; existing evaluated source attribution preserved; appearance is not claimed pixel-identical |
| Optional PNG / rasterise-vector mode | Existing and verified | Nonempty native GP fallbacks; explicit alternatives use custom data in the standard meta object, no extra visible layer; production rasterise/unsupported fallback variants |
| C2 U8 PNG / U16 PNG / F32 EXR | Existing and verified | Actual Blender output; 18 native high-depth scale/padding combinations; exact U16 samples and F32 HDR maintained |
| C2 F16 EXR | Newly implemented and verified | Actual HALF EXR header, F16 declaration, premultiplied half-rounded HDR samples/alpha, 4px padding, retry/current option and template/JSON companions; F32 cache confirmed unchanged |
| D still / animated flags | Existing and verified | Native still followed by animation; three-frame paint and SVG layers |
| Frame order, duration, FPS, changing bounds | Existing and verified | Native 1–3 animation and mixed −2..0 cached frames; 23.976 fractional FPS preserved from Blender's actual float setting |
| Blank frames | Existing and verified | Native hidden/off-camera frames use `_blank`, empty fileName and zero dimensions |
| Negative/nonzero timeline starts | Existing and verified at writer/cache boundary | Negative frames genuinely rendered with `frame_set`; Blender animation-range RNA clamps starts to zero, so test assembles these actual caches explicitly; regular nonzero native animation also tested |
| Per-frame independent opacity | Newly implemented and verified | Animatable Frame Opacity captured at each frame; current retry metadata is reevaluated without rerendering; separate from baked alpha |
| Still cache → animation | Existing and verified | Native still publication followed by mixed sequence replacing it, with stable identities |
| Current retry controls | Existing and verified | Native change of trim, scale and padding across retained snapshots; new F16 selection also reaches current job |
| E1 automatic `clonelayer` export | Newly implemented and verified | Linked GP objects in separate View Layers; evaluated geometry/paint/crop and constant translation verified; independent/rotated controls remain SVG. Bluik import, shared-data edit renders, delayed drawing and reopen tested |
| E2 `ocalayer` export | Newly implemented and verified | Explicit nested-document source on View Layer; reachable graph copied, source ID/time offset, portability and U8 scale 50/100/200 verified; high-depth nested scaling not separately integrated |
| Full transforms, interpolated transforms, loops, native masks/effect layers, ZIP projects, rigs | Unsupported by official OCA 1.3 / excluded | No such root/layer properties or new exporters added |
| Krita OCA reader | Existing and verified at parser boundary | Installed Krita OCA core loads/sanitizes four documents unchanged, including canonical mixed and F16, and resolves assets |
| Krita GUI import/reopen/playback | Implemented but unverified | No usable GUI session in this environment; parser checks are not visual importer validation |
| Clean Blender shutdown | Failed, reproducible environment limitation | Factory-startup print-only control and export runs hang with `pa_write() ... Operation not permitted`; bounded runner records functional pass separately from forced termination |

## Actual integration results and examples

Blender: installed **5.3.0 Beta**, hash `2ebd15112ac6`, bundled Python 3.13 and
bundled Pillow. Newest appropriate production source found:
`Remake_v38_TouchUps.blend` (Nov 15, 23:58). Loaded with auto-execution disabled;
production render destinations were redirected and the scene was not saved.

- Fresh Hatshepsut render at 12% / one CPU sample: **245×327**, 21 artwork inputs,
  one SVG vectorlayer. OCA, PSD, PSB, standalone SVG, 21 PNGs, font delivery,
  rasterised OCA and forced unsupported fallback completed. This is a structural
  and reduced-resolution integration test, not a full-quality production render.
- Full-resolution ForeArm cache test used a private copy of the existing rendered
  PNG. Trim-off and trim-on reconstructed identical visible RGBA samples. It did
  not re-render or modify the user's cache.
- Native seven-control matrix: 3 frames, 4 inputs, 18 combinations
  (50/100/200%, padding 0/1/4, trim off/on), retry/current options, hidden group,
  explicit background, blank frame, template/JSON toggles and PSD smoke test.
- Native precision: 18 U16/F32 combinations plus F16; odd 33×25 canvas,
  unclamped HDR, alpha and quantisation checked against actual source samples.
- Native mixed canonical project: two GP inputs, processed raster input,
  reference flag, −2/−1/0 frames, blank frame, authored metadata, duplicate names,
  reorder-stable identities, opacity applied once and whole-project relocation.
- Saved fixture reopened in Blender: identities survived saving/reopening; two registration/unregistration cycles left no HandOff handlers or duplicates.
- Native compositor blend fixture: all seven tested modes have zero measured
  channel error for the chosen opaque linear RGB case. This does not validate
  every partial-alpha or display-colour-space blend construction.
- Inkscape renders both generated GP SVG examples successfully. Production
  Shine preview versus Blender fallback (39×37): alpha MAE **0.00868** and
  premultiplied RGBA MAE **0.00886** on 0–1 scale; maximum alpha difference
  **0.22745**, principally edge/representation differences. The small triangle
  fixture has alpha MAE **0.03564**, RGBA MAE **0.02723**. Pixel-perfect SVG fidelity
  is therefore unverified; rendered alternatives and rasterise remain available.
- Final Python suite: **239 tests passed** (214 original baseline + 13 compliance + 12 authoring/reference tests).
  Native tests, image inspection and actual Inkscape/Krita-reader checks are
  additional to those tests.

Examples (all generated evidence outside the installed package):

- `/tmp/handoff-oca13/final-mixed/exports/Mixed.oca/Mixed.oca`
- `/tmp/handoff-oca13/production/exports/Hatshepsut.oca` (legacy compatibility)
- `/tmp/handoff-oca13/production-crop/Trimmed.oca/Trimmed.oca`
- `/tmp/handoff-oca13/f16/half/Precision.oca`
- `/tmp/handoff-oca13/blends/overlay.oca/overlay.oca`

Evidence: `/tmp/handoff-oca13/final-suite.log`, `native-matrix/process-results.json`,
`production.log`, `production/native-results.json`, `production-crop/result.json`,
`final-mixed/result.json`, `f16/precision-results.json`, `blends/result.json`,
`svg-comparison.json`, `reader.log`. Temporary evidence may be cleared by the OS;
this report and fixture source preserve the outcomes and reproduction steps.

## Reproduction

From this installed package, bootstrap Pillow before Python test discovery:

```bash
PYTHONDONTWRITEBYTECODE=1 LAYERED_EXPORT_CACHE=/tmp/oca-controls-pillow \
PYTHONPATH=vendor /home/simon/.Applications/Blender/beta/blender/5.3/python/bin/python3.13 - <<'PY'
import sys, unittest
from pillow_loader import ensure_pillow
ensure_pillow()
r = unittest.TextTestRunner().run(unittest.defaultTestLoader.discover('.', pattern='test_*.py'))
sys.exit(not r.wasSuccessful())
PY
```

Reproduce controls/precision/animation and the print-only shutdown control:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 development/run_oca_controls.py \
  --blender /home/simon/.Applications/Blender/beta/blender/blender \
  --results /tmp/handoff-oca13-recheck
```

The runner returns nonzero for the shutdown hang even when functional
assertions pass. Inspect both fields in `process-results.json`.

For individual native fixtures, use the same Blender with factory startup,
`--disable-autoexec -b -noaudio --python-exit-code 1 --python SCRIPT`, an external
`HANDOFF_TEST_OUTPUT` (precision uses `LAYERED_TEST_OUTPUT`), and isolated external
`BLENDER_USER_CONFIG`, `BLENDER_USER_SCRIPTS`, `BLENDER_USER_EXTENSIONS`,
`LAYERED_EXPORT_CACHE`, `LAYERED_EXPORT_JOB_ROOT`. Use a bounded process runner
because of the documented startup-control shutdown hang. Fixtures:
`development/test_oca13_blender.py`, `development/test_oca_blends_blender.py`,
`development/test_oca_vectors_blender.py`. Production uses the latter with the
production blend opened read-only and `HANDOFF_SOURCE_BLEND=1`.

Full-resolution cache check:

```bash
PYTHONDONTWRITEBYTECODE=1 LAYERED_EXPORT_CACHE=/tmp/oca-controls-pillow \
/home/simon/.Applications/Blender/beta/blender/5.3/python/bin/python3.13 \
 development/test_oca_production_cache.py \
 /home/simon/.cache/asset-parts/jobs/layered_render__gmwunwg/jobs.json \
 /tmp/handoff-oca13-crop-recheck
```

Installed Krita reader check (parser/sanitizer only):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 development/test_oca_reader.py \
 /home/simon/.Applications/Krita/squashfs-root/usr/share/krita/pykrita/OCA/oca_core \
 /tmp/handoff-oca13/final-mixed/exports/Mixed.oca/Mixed.oca
```

## Files changed and preserved boundaries

New runtime modules: `oca_project.py` (OCA-only identities, metadata, path
normalisation and publication), `oca_validation.py` (document/assets/references
and metadata validation), `oca_authoring.py` (source publishing controls and
frame capture), `oca_features.py` (authored opacity/blending/references and portable
nested assets), `oca_references.py` (verified linked-GP clones), and
`oca_render.py` (OCA-only reference-aware companion composition).

Existing runtime modules modified: `__init__.py` (OCA-only layout/F16 settings,
source identities and job capture/retry), `oca_controls.py` (input identity),
`oca_sequence.py` (current destination settings/identities reach all frames),
`oca_images.py` (optional F16 encoding), `oca_companions.py` (F16 declaration
recognition), `psd_worker.py` (OCA publication boundary/metadata and F16 selection).

Tests: new `test_oca_features.py`, `test_oca_references.py`,
`development/test_oca_shared_layers_blender.py`,
`development/test_oca_authoring_blender.py`, and the staged native receiver runner
and proof fixtures in `development/bluik_plus_compat/`; also
`test_oca_compliance.py`, `development/test_oca13_blender.py`,
`development/test_oca_blends_blender.py`, `development/test_oca_production_cache.py`,
`development/test_oca_identity_reload_blender.py`;
existing native fixture imports now point at `handoff`, retain explicit legacy
layout where testing existing behaviour, and account for exported aliases.
`development/run_oca_controls.py` now defaults generated results outside the
package. `development/test_oca_vectors_blender.py` also supports a negative-frame
fixture offset without changing its normal default.

PSD/PSB colour mapping, hierarchy builders, shared merge/blend math, standalone
SVG writer/extraction, seven-control image processing, fonts, dependencies and
branding were not rewritten. No demonstrated regression was found in the
completed functional checks. Clean shutdown and target GUI reopen remain
unverified as described above. No release/version bump was made.
