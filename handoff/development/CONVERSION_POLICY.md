# Vector publication policy

The user's SVG / PSD / PSB conversion brief, as amended by the request for
automatic SVG linking in v0.7.48, governs this extension. The 62-row matrix is stored once in
[`compatibility/vector_features.csv`](../compatibility/vector_features.csv).
The runtime reads it through `conversion_policy.py`; the generated offline
manual reads that same registry. Preferred representations are objectives,
not claims that all of those writers already exist.

## Decision order

1. Faithful native editable geometry and paint.
2. Native equivalents using effects, masks or gradients.
3. A modest number of native objects inside the authored hierarchy.
4. Validated shared embedded Smart Objects when source relationships matter.
5. Validated independent embedded Smart Objects for complex standalone art.
6. Raster artwork with its editable SVG source retained.
7. An explicit partial/failure report when no valid representation exists.

External linked SVG Smart Objects are selected automatically when the native
writer cannot represent the source. They use one PSD/PSB representation across
editors, with visible preview channels and relative SVG paths. Do not choose
Smart Objects merely because a source has a gradient. Never call independent
copies linked instances, or an empty fallback a successful conversion.

Preserve visual appearance, editable structure, document simplicity and shared
identity as distinct requirements. A reader parsing a PSD is insufficient
evidence of target-editor support. Photoshop and PhotoCraft require separate
profiles and actual application tests. Inkscape and generic SVG readers also
have separate validation fields. These describe testing status; they are not
user-facing unlocks. Existing working native conversions remain available.

## Current implementation boundary

- Existing native paths, compound masks, uniform strokes, supported text and
  pressure-gradient conversion continue using the established writer.
- The new material-gradient descriptor prototype covers RGB linear ramps on
  axis-aligned linear or circular radial mappings. Stop positions/opacity,
  Bézier handles and high-depth data survive reader save/reopen tests.
  Photoshop's 4096-position gradient encoding quantises ramp positions.
  Rotated linear mappings, elliptical radial mappings, Ease/B-spline/HSV
  interpolation, repeat/reflection and unsupported transforms are rejected.
  Automatic native material-gradient publication remains gated.
- Gradient Fill/vector-mask alternatives and Gradient Overlay layer effects
  still need implementation and application validation before eligibility.
- Linked SVG fallbacks write external-source records, cached preview pixels,
  relative paths and shared source identifiers. Reader tests cover 8/16/32-bit
  documents, distinct placement IDs, save/reopen, moving the document together
  with its assets folder, and opening one changed source through both
  instances. This does **not** establish application rendering, automatic
  refresh, edit/save behaviour or PhotoCraft compatibility.
- Shared embedded Smart Objects are not implemented. External SVG linking is
  automatic; no target-editor selector or link checkbox is exposed. Their old
  saved properties remain loadable but do not affect export decisions.
- A contiguous shared GP gradient source with matching paint configuration and
  no nested Collection boundary can publish as one linked SVG composition.
  That SVG preserves the clone graph without exposing each clone as a separate
  PSD layer. Mixed supported/unsupported sources retain per-object boundaries;
  a nonempty whole-source render may require a whole-source link to preserve
  its verified pixels.
- Existing independent native PSD copies retain their source-family metadata;
  live PSD linkage is explicitly reported as lost. SVG clones remain linked.

## Source preservation and fallback

Fallback operates per logical object where a verified renderer can isolate
that object's paint. Supported neighbours remain native. Compound contours
sharing a fill/hole remain one logical shape.

When a GP material gradient cannot be converted, a compact SVG containing only
that source layer's artwork is written to `<document>.assets/`. Existing
nonempty Blender-rendered pixels remain authoritative. If that cache is empty,
the supported GP paint subset can build an SVG-equivalent preview. It retains
the exact authored SVG stop count and reports that SVG interpolation can differ
from Blender. Unknown effects and unsupported blends are rejected instead of
being approximated silently. A visible whole-source cached render may require
whole-source fallback because its individual objects cannot be isolated from
that composite safely.

An empty cache with no verified renderer is omitted with a partial publication
report; its resolved SVG is preserved where available. Unrelated valid layers
continue. Intentional hidden placeholders for disabled View Layers remain
supported. Partial output does not play the success chime.

## Names and future import identity

Authored labels remain unchanged. SVG IDs describe object/paint role with a
short uniqueness suffix. Versioned `data-asset-*` attributes and an inert source
index retain scene, object and datablock UUIDs, names, source library, frame and
View Layer context. Shared datablocks share a data ID; object copies retain
separate object IDs. Independent copied datablocks receive new data IDs.

The first export adds local `_asset_parts_*` identity properties in memory.
Save the Blender project to retain them across sessions. Publishing does not
save the user's project automatically. Read-only libraries use derived identity.
PSD XMP binds source identities to native layer IDs. These are foundations for
a future importer, not implemented round-trip updates. External editors may
remove unsupported metadata; that requires future application-specific tests.
SVG event attributes are standard scripting hooks, left empty by this exporter.

## Validation and diagnostics

Before enabling a new conversion in a target profile, verify initial appearance,
editable structure, control handles, paint/effect settings, geometry placement,
ICC/bit depth/alpha, save/reopen, editing and source-instance propagation.
Test Photoshop and PhotoCraft separately. Text must retain its size on entry to
editing. Gradients must edit the intended stop. Smart Object instances must
update after editing the shared source. Compare against a reference renderer at
the same resolution/colour-management settings. Include partial failure cases
and the existing exporter regression suite.

Publication records use `NATIVE_EDITABLE`, `NATIVE_WITH_EFFECTS`,
`SHARED_SMART_OBJECT`, `EMBEDDED_SMART_OBJECT`, `RASTER_WITH_SOURCE`,
`APPROXIMATED`, `PARTIAL`, `SKIPPED`, or `FAILED`. Requested external links add
`LINKED_SMART_OBJECT`. Records include source object/View Layer/Collection,
destination, SVG reference, instance family, preserved or lost features,
validation and fallback reasons where applicable. Details remain in the terminal
and retained job `result.json`; the default UI stays concise and collapsed.

No change to the XML directive registries, compositor ordering, document ICC
profiles or cache identity is needed for this extension. Native gradients,
effect/mask combinations and shared embedded Smart Objects must be developed
incrementally without replacing the working document pipeline.
