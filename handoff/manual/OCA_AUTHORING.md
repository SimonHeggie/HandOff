# OCA 1.3 authoring

The View Layer and Collection **HandOff — OCA Authoring** controls affect only the OCA destination. Other formats continue through their existing writers. The source project's rendered appearance and these extra OCA properties are deliberately distinct.

## Layer and group properties

| Blender control | OCA result |
| --- | --- |
| View Layer visibility/background | Explicit layer visibility and document background intent, rather than inference from a name or stack position |
| Export Opacity and Frame Opacity | Layer opacity and animated exposure opacity, separately from alpha baked into the raster/vector source |
| Blend / Inherit Alpha | Standard OCA paint-blend and clipping metadata; the target reader's compositing may differ |
| Collection opacity / blend / isolation | Native OCA group representation, retaining source grouping and colour labels |
| Keep Independent | Stops an otherwise safe automatic reuse/clone conversion |

## Source references and reusable artwork

- **Linked GP duplicates** sharing a Blender datablock may become OCA `clonelayer` references when geometry, appearance, identity and translation checks pass; unsupported rotation or styling remains an independent drawing.
- **Source View Layer**, **Reference Offset** and **Time Offset** explicitly select a source artwork stream and move or delay exposures. Missing, ambiguous or cyclic relationships are rejected.
- **Nested OCA Document** creates an OCA `ocalayer`; referenced document assets are copied into the exported project with portable relative paths. An optional source layer ID can select nested content.
- These are **not** 3D skeletal-rig, bone-weight or pivot/rotation/scale animation exports.

## Publication and interoperability

Use the canonical project directory for new deliveries; the old layout is available for saved jobs requiring it. Validated asset links, unique names, source-derived IDs, separate metadata and staged publication reduce accidental corruption.

A Bluik Plus 1.3 importer was tested separately with image, GP SVG and reference scenarios. Complex isolated group opacity, Inherit Alpha clipping, unsupported GP gradients and some paint blending remain reader-dependent; a rendered PNG alternative is an available fallback. See [OCA controls](OCA-controls) and [OCA vector artwork](OCA-vector-artwork).
