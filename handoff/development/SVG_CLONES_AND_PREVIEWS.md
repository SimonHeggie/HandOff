# SVG clones, colour labels and portable PSD previews — v0.7.44

The exporter captures intentional GP datablock sharing before preparing the
existing detached vector model. SVG output replaces compatible duplicates with
real `<use>` references. PSD preparation continues to consume the full model.
This preserves existing native PSD shape/type layers and raster fallbacks.

## Artist workflow

- Use linked Blender duplicates sharing one Grease Pencil datablock. Independent
  datablocks remain independent, even when they currently look identical.
- In Inkscape, select a clone, then **Edit > Clone > Select Original** to edit its
  shared paths. **Unlink Clone** makes an instance independent.
- Names, paint order, object transforms, compatible gradients and Bézier handles
  remain editable. Collection/object highlight colours survive SVG assembly and
  an Inkscape save round trip.
- Different materials/modifier results, object-dependent modifiers, live pressure
  effects, singular geometry and incompatible stroke transforms keep independent
  editable vectors. Fill-only anisotropic transforms can share; ordinary strokes
  share under rotation, reflection and uniform scale when widths also match.
- This release does not introduce Photoshop linked or embedded Smart Objects.
- Restart Blender to load the updated add-on. **Retry Conversion (No Render)**
  rewrites an existing PSD with the portable preview. A fresh F12 export is needed
  to capture datablock identities for clones in older completed SVG source caches.

## Thumbnail correction

The optimisation compressed both editable channels and the document preview with
ZIP. KDE's installed PSD image plugin, used by Dolphin, accepts only RAW or RLE
for the document preview. The writer now retains ZIP (or the selected codec) for
layer channels and always writes a portable RLE preview. No JPEG thumbnail or
lower-precision layer substitution is needed.

Authoritative implementation:
[KDE PSD reader](https://invent.kde.org/frameworks/kimageformats/-/blob/master/src/imageformats/psd.cpp).

On the retained character, the old ZIP-preview file is 71,561,189 bytes and the
portable file is 75,465,974 bytes. The actual source measurements in the prior
performance notes remain historical measurements of v0.7.43, not timings of this
preview correction. One full validation export here took 68.18 seconds for PSD
and 2.14 seconds for SVG; it was not a controlled performance benchmark.

## Stable technical names

`runtime_paths.py` owns new technical names: `layered-document-export`,
`layered_render_*`, `layer_L…`, and private staging identifiers. New cache files
are independent of the public product name. Old job prefixes, ownership markers,
snapshot markers, saved Blender identifiers and environment overrides remain
readable. New `LAYERED_EXPORT_CACHE` and `LAYERED_EXPORT_JOB_ROOT` overrides take
precedence over the previous environment names. Default history lookup searches
both new and legacy job roots.

`branding.py` owns the public name, version and log prefix; the UI, runtime logs
and generated manual read those values. The installed add-on module and operator
IDs remain unchanged for saved-file compatibility. Historical metadata IDs and
old documentation/changelog references are deliberately retained.

## Modified files

- `svg_instances.py` (new): datablock identity, affine/paint validation and clones.
- `svg_hybrid.py`, `svg_export.py`, `svg_document.py`: identity capture, source
  snapshot identity, clone encoding/import, ID remapping and final cross-source
  linking. No change to the shared PSD vector representation.
- `svg_collections.py`, `collection_colors.py`, `svg_document.py`: aligned
  Collection colours, six-digit Inkscape highlight metadata and inheritance.
- `psd_worker.py`: portable preview compression, selected layer codec retained.
- `runtime_paths.py` (new), `__init__.py`, `pillow_loader.py`, `job_ownership.py`,
  `job_cache_cleanup.py`, `disabled_layers.py`: neutral new paths and legacy
  recovery/cleanup compatibility.
- Other runtime helpers: canonical log prefix and private staging names only.
- `branding.py`, four manual generators, generated manual, `README.md` and
  `PERFORMANCE.md`: identity/version, workflow and compatibility documentation.
- Regression tests and two new native Blender fixtures cover these changes.

## Validation

Audit folder: `/tmp/layered-export-clones-gtrs84d0/`.
Immutable pre-change runtime backup: `before-v0743.tar.gz`.

- **173 unit tests and 17 compatibility/manual tests passed.** Syntax parsed for
  all root modules, development fixtures and compatibility generators.
- Native Blender 5.3: linked vs independent GP data, object material overrides,
  transformed radial gradients, Bézier handles, visible-stroke constraints,
  layered document import and preservation of source datablocks/transforms.
- Native Blender 5.3: fresh 8/16/32-bit PSD and PSB exports with ZIP layers and
  RLE merged previews. KDE/Qt 6.11.2 actually decoded the fresh previews and the
  16-bit character PSD into thumbnail images.
- Character comparison: all **84 nonempty ZIP channels**, 39 layer/group records,
  names, positions, blend modes, visibility, opacity and merged preview pixels
  match the previous optimised PSD. Layer precision remains 16 bits.
- Native render/assembly regression: disabled View Layers still reuse the last
  image through PNG8/16, EXR32, PSD, SVG, PNG and OCA; neutral cache names are used.
- Native shared-source preparation and saved UI/chime settings fixtures passed.
- Inkscape 1.4.4 rendered linked, independent, Bézier and outlined fixtures. An
  original-only edit updated all three linked circles while independent paint
  stayed unchanged. Inkscape's own **Unlink Clone** action recognised the output.
  Largest clone-vs-independent difference: alpha 1/255; premultiplied RGB below
  1/255, at three antialiased edge pixels. Colour metadata survived Inkscape's
  normal SVG save.
- The real character has five objects sharing `Stroke`; the new SVG contains
  **one Bézier original and four clones**, with no rasterisation of those objects.
- Full character SVG parsed and rendered through CairoSVG. Its blend support is
  different from Inkscape, so this is not a claim of exact composite equivalence.
  Inkscape's full embedded-PNG rendering could not be verified in the tool
  sandbox: even a separate tiny valid PNG fails through the installed
  GDK/Glycin loader with a D-Bus I/O permission error. Vector-only Inkscape tests
  and KDE's PSD image loader work. No system/desktop configuration was changed.

Private review outputs, using the existing rendered cache and newly extracted
Shine vectors, without modifying the source project or its deliverables:

- `character/Character.psd` — portable preview, unchanged layer data.
- `character/Hatshepsut.svg` — combined document with four ShineSprite clones.
- `character/Shine.svg` — small isolated clone example.
- `character/Hatshepsut-cairo.png` — renderer check, with the blend limitation above.
