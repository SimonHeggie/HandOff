# v0.7.47 validation and implementation notes

Immutable pre-change backup: `/tmp/asset-parts-policy-p74ssrdd/before-v0746.tar.gz`.
The original character project and production deliverables were read as sources;
character test exports and editor candidates are private files under that audit
directory. No character rendering was required.

## Modified files

- `__init__.py`, `branding.py`: version, saved target/link settings, validation
  gate in the existing PSD settings, partial status and success-only chime.
- `svg_metadata.py`, `svg_export.py`, `svg_hybrid.py`, `svg_instances.py`,
  `svg_document.py`: persistent source identity, readable IDs, reference updates,
  clone identity and inert publication metadata. Existing rendering and clone
  compatibility checks remain in use.
- `conversion_policy.py`, `compatibility/vector_features.csv`: shared capability
  source, validation profiles and per-object publication records.
- `psd_gradients.py`, `psd_svg_links.py`, `psd_vectors.py`, `vector_artwork.py`,
  `psd_worker.py`: isolated record prototypes, compact SVG preservation,
  supported GP preview sampling, smallest-safe object fallback, source bindings,
  Grey labels and accurate failure/partial reports.
- `README.md`, `compatibility/paginate_manual.py`,
  `compatibility/workflow_notes.py`, generated `manual/` pages and
  `development/CONVERSION_POLICY.md`: current behaviour, shared matrix and limits.
- Root unit tests and `development/test_source_metadata_blender.py`,
  `development/test_worker_startup_blender.py`: source identity, native records,
  sidecar references, partial conversion, target gates and status regression.

## Checks completed

- **190 unit tests passed** using Blender's Python 3.13, bundled psd-tools and
  existing Pillow cache. These include 8/16/32-bit native gradient and linked SVG
  record save/reopen, HDR channels, stops/alpha, Bézier handles, per-instance
  transforms, shared-source references, relative folder moves, independent
  native neighbours and rejected empty/unsupported fallback cases.
- **17 compatibility/manual tests passed**. The 62-feature matrix is generated
  from the CSV used by the runtime; the XML tag/blend registries are unchanged.
- Installed Blender **5.3 Beta, hash 2ebd15112ac6** exercised source UUIDs through
  copy/rename/save/reopen, saved publish settings, real GP clone extraction,
  independent data/material overrides, UI disclosure/chime, actual worker
  startup, shared preparation and disabled View Layer reuse across PNG8/PNG16/
  EXR32 with six output destinations. Source render flags stayed unchanged.
- The actual Retry operator also passed against the user's character project
  with package-only imports and worker launch intercepted. It refreshed the
  untagged Shine Collection to explicit `NO_COLOR`; no render was performed.
- A private character PSD16/SVG export completed from retained caches. The PSD
  contains five visible Shine preview layers and native Grey labels. Its source
  SVG contains one original and four clones, with unique IDs and shared data
  identity. KDE's installed image reader successfully decoded the PSD preview.
- Inkscape 1.4.4 rendered the clone fixture and independent equivalent with at
  most **0.765/255** premultiplied RGB difference. Editing the source changed
  the original and both linked instances; the independent copy and material
  override did not change. This does not verify editor metadata retention or a
  Blender reimporter.
- CairoSVG compared linear and transformed radial GP preview fixtures against
  independent SVG rendering. Interior maximum premultiplied RGB differences
  were **1.483/255** and **0.968/255**; alpha differences were **1.542/255** and
  **0.571/255**. These are display-referred subset checks, not proof of exact
  Blender Ease interpolation or Photoshop native gradient equivalence.
- All root Python files passed syntax parsing. Blender tests exercised module
  imports and actual native API calls, beyond syntax checks.

## Limits and next validation

Neither Adobe Photoshop nor PhotoCraft was available for an actual editing
session. New native material-gradient and linked Smart Object publication
therefore remains gated, following the supplied brief. Gradient Overlay and
shared embedded Smart Object writers remain to implement. The existing native
vector writer continues to operate; no claim is made that these older features
have newly passed Photoshop/PhotoCraft editing validation.

The real worker produced valid files and a complete report in the native
startup test, but this execution sandbox hung during Blender's audio shutdown.
The test terminated only its own completed child and simulated a successful
process exit to exercise the monitor. Desktop process shutdown and audible
notification are not established by that test; Null-device chime samples and
partial/failure notification suppression were tested separately.

Reader-checked editor candidates, with matching SVG sidecars, are packaged at
`/tmp/asset-parts-policy-p74ssrdd/SVG-link-validation.zip`. The bundle includes
the full character with Shine collapsed into one linked-source candidate,
two-instance sharing fixtures at 8/16/32 bits, native gradient fixtures and
instructions for application rendering/edit/save/reopen validation.

SVG event fields are standard scripting hooks; the exporter adds no scripts or
event actions. Identity uses inert attributes and metadata. See the
[SVG interaction specification](https://www.w3.org/TR/SVG2/interact.html),
[Adobe PSD specification](https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/)
and the independent
[ag-psd record writer](https://github.com/Agamnentzar/ag-psd/blob/master/src/additionalInfo.ts)
used to cross-check the candidate record structure. Format documentation does
not establish target-editor validation.
