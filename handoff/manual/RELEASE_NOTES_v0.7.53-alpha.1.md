# Handoff v0.7.53 Alpha 1 — OCA 1.3 authoring and interchange

> **Alpha release:** Validate exports in their intended applications before production use.

Handoff v0.7.53 advances the Blender Compositor File Output workflow from layered OCA still/animation export to a more structured, source-aware OCA 1.3 publishing system. It does **not** claim general 3D-to-2D rig conversion.

## Changes from the published v0.7.51 source

### Standards-compliant OCA project delivery
- New destinations can publish canonical `Name.oca/Name.oca` projects, with a separate `Name_meta.json`, portable relative artwork and a selection for legacy folder layout.
- Exported layer names and source-derived identities are disambiguated without renaming Blender objects, collections or inputs. Persist newly assigned node IDs by saving the Blender project.
- Asset and document validation runs before staged publication. Recoverable rename failures restore the previous project. This does not guarantee recovery from abrupt power loss.
- Original frame numbers, cropped centre placement, transparent exposures and input stack order are retained. New PNG/EXR precision handling covers U8/U16/F16/F32 as appropriate to the destination.

### Editable artwork and source-aware authoring
- Supported Grease Pencil inputs publish individual editable SVG cels; unsupported content keeps rendered images. **Rasterise Vector Layers** selects a raster representation, and **Keep Alternative Artwork** optionally retains an SVG/PNG companion without a duplicate visible OCA layer.
- View Layer and Collection authoring panels add OCA-specific visibility/background, layer/frame opacity, alpha inheritance, blend selection, isolation and group options. Source alpha already baked into pixels is not inferred and reapplied.
- Verified linked Grease Pencil source instances can reuse artwork through standard OCA `clonelayer` references. **Keep Independent** leaves an instance separate. Unsupported transforms/styles use independent artwork rather than claiming false sharing.
- **Source View Layer**, reference positioning and time offsets support explicit cross-input reuse; ambiguous, missing or cyclic references fail validation. **Nested OCA Document** uses the standard `ocalayer` type and copies reachable referenced assets.
- Source order, `.merge`/`.ungroup`, rendered PSD/PSB/SVG outputs, colour labels and legacy saved identifiers remain on their established paths.

### Compatibility, testing and corrections
- The included Blender 5.3 development test matrix exercises actual OCA exports and Bluik 1.3 imports: shared GP editing, cropped raster cels, opacity changes, blank exposures, nested sources, time offsets, saved-file reopening and blend calculation.
- An installed-engine mismatch, OCA visibility inherited from excluded rendering collections, and several import preview/paint-mode limitations were identified; Bluik receiver fixes are **separate Bluik Plus changes**, not part of the Handoff add-on install.
- The local validation logs report 243 Python tests passing, native test fixtures and Krita reader loading selected projects. Tests were performed against the supplied source snapshot; the newly bumped version has not been independently certified in a complete application UI test pass.

## Known limitations

- OCA 1.3 has no interoperable general transform, pivot, 3D bones or mesh-weight animation encoding. Handoff does **not** preserve these as native 2D rigs in this release.
- Selective frame sequence deduplication, transform capture, 3D skeleton/weight capture, Blender-document reconstruction and VSE/scene export remain planned milestones.
- Some Grease Pencil gradients, isolated multi-child group blending, Inherit Alpha clipping and target editor colour management differ across readers. Bluik native 3D preview fidelity is explicitly limited.
- Native SVG/Photoshop/Krita edit-and-save round-trip parity has not been established. The existing Blender factory-startup audio shutdown hang on the test machine prevents treating process termination as a clean integration result.
- Do not install the automatic GitHub source ZIP as a substitute for a complete Blender release asset containing required third-party dependencies. No v0.7.53 binary release has yet been published.

## Installation and documentation

Use an installable **release asset ZIP** once v0.7.53 has been built, validated and published. In Blender: Edit → Preferences → Add-ons → Install from Disk. Restart Blender when upgrading and disable previous renamed packages to avoid duplicate render handlers. Use the Compositor's File Output node → **HandOff - Additional Exports**; **Check Export Status** before exporting, and **Retry Export (No Render)** for retained caches.

- [OCA authoring](OCA_AUTHORING.md)
- [OCA controls](OCA_CONTROLS.md)
- [OCA vector representation](../handoff/manual/OCA_VECTORS.md)
- [Full source manual](../handoff/manual/MANUAL.html)
- [Historical release descriptions](HISTORICAL_GITHUB_RELEASE_NOTES.md)
