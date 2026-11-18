# HandOff v0.7.53 Alpha 1 — OCA 1.3 authoring and interchange

> **Source revision in preparation — not a published release.** The latest published downloadable release is v0.7.51 Alpha 1. A v0.7.52 consolidated-release note existed as an unpublished draft, so this update reserves v0.7.53 to avoid ambiguity.

## What's new in the supplied source

- **Canonical OCA projects:** A new OCA destination can use a portable `Name.oca/Name.oca` project structure with metadata sidecar and source-relative artwork. Explicit legacy layout remains available to existing saved jobs.
- **Identity, validation and publication:** persistent source identifiers reduce reordering-related identity changes; duplicate exported names and asset names are disambiguated without renaming Blender sources. Validation checks the OCA project and referenced files before staged publication, including recoverable replacement failures.
- **Grease Pencil vector cels:** eligible directly traced GP content becomes editable SVG assets; unsuitable content retains native PNG/EXR output. Rasterise Vector Layers chooses a raster visible layer, while Keep Alternative Artwork can retain unselected SVG or PNG without inserting a second visible layer.
- **OCA-specific authoring:** View Layer and Collection properties permit explicit visibility and background, layer/group/frame opacity, blend selection, alpha inheritance, group isolation and independent OCA source settings. Authored opacity remains separate from source opacity already baked into image pixels.
- **Reusable source artwork:** validated linked GP instances can produce OCA `clonelayer` references. Explicit Source View Layer, position and time offsets, Keep Independent and recursive nested `ocalayer` references provide source-aware interchange. Invalid or cyclic reference graphs fail explicitly.
- **Precision:** U8/U16 image and F16/F32 EXR publishing paths, crop/scale/padding and frame exposure handling have dedicated regression coverage.
- **Compatibility diagnostics:** staged Bluik Plus development integration tested shared GP drawing edits, nested sources, time offsets, crop placement, save/reopen and selected paint blending with Blender 5.3. Bluik receiver changes are a *separate project*, not installed by HandOff.

## Verification evidence and cautions

The uploaded source includes test reports for 243 passing HandOff Python tests and native Blender/OCA/Krita-reader checks. These results are historical evidence from the supplied development environment, not an independently repeated final v0.7.53 release certification. Some Blender runs demonstrated a factory-startup audio shutdown hang after assertions completed.

The supplied code does **not** add selective frame deduplication, captured 3D object transform curves, 3D armature/weight interchange, general 2D skeletal rig reconstruction, Blender-to-Blender scene export, or VSE export. These are future milestones. OCA 1.3 does not standardize pivot/rotation/scale keyframes.

**Known receiving limits:** Blender/Bluik previewing approximates some group-opacity, Inherit Alpha and Grease Pencil SVG gradient cases; other readers may choose different paint/colour interpretations. No blanket Photoshop/PhotoCraft/Krita GUI save-and-reopen equivalence is claimed. No new standalone ZIP or GitHub release has been published.

## Upgrade and documentation

Once the candidate has been fully synchronized, reviewed, built and published, install its **release asset** ZIP from Blender's Edit → Preferences → Add-ons → Install from Disk, not the automatically generated GitHub source ZIP. Disable/uninstall older `blend_psd_tools` registrations before enabling `handoff`.

- [OCA authoring](../handoff/manual/OCA_AUTHORING.md)
- [OCA controls](../handoff/manual/OCA_CONTROLS.md)
- [OCA vector artwork](../handoff/manual/OCA_VECTORS.md)
- [Historical release notes](HISTORICAL_GITHUB_RELEASE_NOTES.md)
