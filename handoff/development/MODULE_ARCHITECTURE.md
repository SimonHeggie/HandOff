# HandOff — module inventory and safe reorganisation plan

Review of the uploaded `blend_psd_tools(1).zip` snapshot. This is a **proposal**, not a refactor already applied.

## Safety findings

- 46 top-level non-test Python modules were present; none lacked a static Python reference in a source or test. **No Python modules have been deleted or moved.**
- `__init__.py` is the Blender registration/orchestration layer. `psd_worker.py` is an independent worker entry point whose imports currently use top-level module names and a vendor/Pillow loader. Moving it requires adapting its process bootstrap and testing Blender subprocesses.
- Dynamic Blender registration, old RNA identifiers, legacy caches, `data-compio-*` SVG/metadata keys, packaged dependencies and importable test fixtures must remain compatible even after renaming the *package* to `handoff`.
- The `handoff` ZIP already packs the source files under the renamed Python package. Source-level branding is primarily centralised in `branding.py`. The pre-import Blender `bl_info` literal is deliberately retained and synchronised on import.
- The existing package builder previously missed `assets/export_success.wav`; the cleaned builder now includes it. This file is read at runtime by `__init__.py`.

## Recommended logical grouping (future refactor)

| Future namespace | Modules currently at package root | Reason |
|---|---|---|
| `core/` | `layer_stack`, `collection_provenance`, `collection_colors`, `attribution_names`, `artwork_probe`, `group_blends`, `merge_groups`, `disabled_layers`, `view_layer_sync`, `tag_registry`, `conversion_policy` | Blender source discovery, ownership, Collections, grouping, authoring semantics |
| `formats/oca/` | `oca_controls`, `oca_images`, `oca_sequence`, `oca_vectors`, `oca_companions` | OCA export and asset conversion in one discoverable namespace |
| `formats/svg/` | `svg_export`, `svg_document`, `svg_collections`, `svg_hybrid`, `svg_instances`, `svg_source`, `svg_pressure`, `svg_width`, `svg_bounds`, `svg_metadata`, `vector_artwork`, `gp_gradient`, `gp_raster_cache` | Evaluated geometry, Grease Pencil rendering, SVG writing, source metadata and fallbacks |
| `formats/psd/` | `psd_worker`, `psd_vectors`, `psd_svg_links`, `psd_gradients`, `psd_color_profiles`, `png16_pixels`, `raster_bounds` | PSD/PSB writer and precision/profiles; some image helpers could eventually move to `core/image` |
| `assets/fonts/` | `font_delivery`, `builtin_font` | Font delivery and Bfont |
| `runtime/` | `runtime_paths`, `render_temp`, `job_ownership`, `job_cache_cleanup`, `export_performance`, `pillow_loader`, `package_compat` | Filesystem ownership, lifecycle, resource loading, compatibility |
| package root | `__init__.py`, `branding.py` | Blender registration and central identity; keep minimal |

## How to reduce lookup overload without breaking imports

**Stage 0 — already safe:** Keep source paths stable. Use the table above as the code navigation index. Add a compact `core/__init__.py` style *API index* only when a use-case justifies it; avoid a generic god-module or a second copy of the same functions.

**Stage 1 — lowest-risk extraction:** Split registration/UI wiring from the 2,100+ line `__init__.py` into `ui/panels.py`, `ui/properties.py`, and `runtime/registration.py`, but preserve the existing registration order, Blender RNA property names and operator IDs. New code must not change the saved `.blend` data model.

**Stage 2 — format facades:** Give each format an explicit public entry point, e.g. `formats/oca/export.py`, `formats/svg/export.py`, `formats/psd/export.py`, each calling shared `core/` services. Use backwards-compatible import facades at former module paths while the import graph and worker bootstraps are migrated. Avoid circular imports by keeping `core/` format-agnostic.

**Stage 3 — physically group modules:** Move one format at a time, starting with OCA's five helpers, after making all internal imports package-relative. Retain old import aliases until Blender background-worker and ZIP-installed tests pass. Moving `psd_worker.py` is last because it is independently launched and imports through `sys.path`.

**Stage 4 — consolidate functions only when genuinely duplicated:** Candidates for a *single owner* (not code elimination) are image extents (`raster_bounds`, `svg_bounds`, `oca_images`), generic cache IDs/paths (`runtime_paths`, `job_cache_cleanup`, `job_ownership`), colour/profile utilities (`psd_color_profiles`, `png16_pixels`) and vector source metadata (`svg_metadata`, `svg_source`). Their algorithms have different semantics, so merge *interfaces* only after equivalence tests, not by combining similarly named functions blindly.

**Verification gate for each stage:** 214+ Blender-free tests, 17+ compatibility tests, Blender registration/unregistration, isolated worker startup, package ZIP installation, a PSD/PSB round trip, a simple SVG scene, OCA mixed raster/GP vector production-scene export, and no duplicate handlers. Do not simultaneously refactor the runtime and implement new OCA features.

## What was deliberately NOT removed

All top-level Python modules, all tests, all live worker/vendor files, six platform-specific Pillow wheels, Bfont (`vendor/fonts/Bfont-Regular.otf` and JSON), original licensing, profiles and `assets/export_success.wav`. File name `test_compio_hierarchy.py` and legacy XML/data keys remain because changing internal identity is distinct from public branding and could require changes to existing tests and saved data.
