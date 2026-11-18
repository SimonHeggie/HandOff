# PSD vector-layer investigation

Development notes for v0.7.39. These describe tested records and limits; they do not claim Photoshop application validation.

## Existing implementations

- psd-tools (MIT, https://github.com/psd-tools/psd-tools): current HandOff writer. It can read/write lower-level tagged blocks and read vector masks, but does not offer a complete public API for creating Photoshop shape and Smart Object layers. Relevant tagged blocks include `vmsk`, `vsms`, `vstk`, `vscg`, `vogk`, `SoLd`, `SoLE`, `PlLd`.
- ag-psd (MIT, https://github.com/Agamnentzar/ag-psd): TypeScript PSD writer with vector mask, Bézier knots and placed-layer metadata. Its format model is a useful reference. It cannot write 16/32 bits per channel, so swapping HandOff's PSD writer to ag-psd would lose working precision.
- ag-psd-rs (https://github.com/Vasyanator/ag-psd-rs): Rust port with vector/shape and Smart Object metadata. Some branches of path, stroke, linked-file and filter metadata are partial. Not a drop-in Python backend.
- Blender Grease Pencil SVG exporter (Blender 5.3 manual): exports Bézier curves and fills, but reads the largest 3D Viewport rather than the render camera. HandOff uses camera coordinates directly for first-phase SVG.

## Implemented shared preparation

`vector_artwork.py` owns Blender readers, camera projection, evaluated modifier geometry, colour conversion, pressure outlines/profiles and detached artwork caches. `svg_export.py` and `svg_pressure.py` serialize SVG-specific markup and live effects. `psd_vectors.py` owns Photoshop path, stroke, gradient and type descriptors and compatibility pixel previews. `psd_worker.py` retains the established precision, ICC, grouping and raster backend.

Render/viewport modifier visibility mismatches are evaluated on a private object copy using the render flags. Original geometry, modifier flags and scene IDs are checked after extraction, including failure cleanup. The camera is reacquired after dependency-graph updates. No original project is saved.

PSD shape layers carry normalized cubic knots in vmsk/vsms, SoCo fills or native gradients, and vstk/vscg stroke records. Their ordinary pixel channels are compatibility previews at the document bit depth. The native paths remain editable; this is not an embedded SVG Smart Object. PSD supports uniform native strokes; varying width is a filled path with an additional named centreline. SVG PowerStroke has live width controls and a portable outline. Eligible point alpha uses independent opacity gradients in both adapters.

Source paths for modified GP objects are named PSD Paths resources; modifier parameters and original geometry are retained in custom XMP. SVG retains the same provenance as data attributes. These are references for rebuilding edits, not executable cross-application stacks. No project files or font files are embedded by this metadata.

## Modifier editing equivalents

All supported results first use Blender's render evaluation. Closed Bézier strokes retain their cubic handles when Blender supplies Bézier geometry. Geometry-generating modifiers may return polygons or many short strokes: those remain vectors. An alternative listed below is an authoring suggestion, not a claim that unlike algorithms produce identical shapes.

| Blender modifier | Portable result | Editing equivalent or limitation |
| --- | --- | --- |
| Noise | Evaluated editable paths | Inkscape Roughen or hand edits can be rebuilt from the source path; random seed/algorithm is Blender-specific. |
| Thickness | Native uniform stroke width, or pressure outline | SVG PowerStroke for supported varying width; PSD filled outline plus saved centreline. |
| Opacity | Layer/paint alpha or supported point gradient | Editable opacity/gradient stops; loops and unsupported filled pressure combinations need pixels. |
| Tint | Evaluated editable fill/stroke colour | Edit colour or apply an application colour effect; original tint settings are provenance. |
| Subdivide | Evaluated path with additional points | Manual subdivision preserves geometry; unlike applications may choose different point placement. |
| Smooth | Evaluated editable path | Inkscape smoothing effects or node editing are alternatives, not identical Blender iterations. |
| Mirror | Evaluated mirrored geometry | Clones/duplicate transforms or Inkscape Mirror Symmetry can rebuild a live alternative. No automatic live clone relationship is asserted. |
| Offset | Evaluated coordinates/handles | Application object/path transform when uniform; Blender per-stroke/random offsets remain evaluated geometry. |
| Dash | Evaluated open dash paths and vector dot circles | Native SVG/PSD dash settings suit simple repeating dashes. Blender multi-segment/material patterns remain explicit paths to preserve their positions. |
| Outline | Evaluated closed editable paths | Inkscape Offset or stroke-to-path can rebuild simple outlines; Blender projection/join geometry is retained. |
| Length | Evaluated extended/trimmed paths | Trim/extension effects and node edits can approximate; no shared SVG/PSD live modifier exists. |
| Simplify | Evaluated reduced editable path | Inkscape Simplify or a simplify effect can be reapplied to the retained source. Blender's reduction decisions are already in the result. |

Photoshop does not expose a general SVG live-path-effect stack. Source geometry and scalar settings are retained for recovery; none of the above pretends that Photoshop can execute a Blender modifier. Subdivide and Simplify can alter control topology even when the silhouette barely changes.

## Verified and unverified

Native Blender 5.3.0 Beta 2ebd15112ac6 reads the actual Hatshepsut file and exports all 126 atlas objects without PNG fallback after the user's lighting corrections. The source has eleven remaining modifier stacks; the numbered Thickness example currently has no modifier. Tests check unchanged flags/ID counts and one-point Dash strokes.

Independent PSD serialization/reopen tests verify even-odd holes, cubic handles, uniform stroke and opacity gradient descriptors, live Bfont text, saved source paths and XMP at the supported depths. Editing a reopened solid fill and forcing vector recomposition changes rendered pixels independently of the stored preview. Atlas prototypes contain 136 shapes and 42 type layers at 8/16/32-bit depth.

Photoshop application open/edit/save is **not verified**: it is unavailable here. The Python reader cannot render every native stroke/gradient without optional dependencies; descriptor round trips plus compatibility previews do not prove Photoshop's exact layout. Complex multiline/spacing text and unsupported per-object raster caches currently retain the complete camera source as pixels in PSD, with a log explanation. SVG retains its existing per-object fallback. Lighting, masks and shader effects remain explicit fallback boundaries. No external writer or renderer dependency was added.

## Primary research

- [Blender SVG implementation](https://github.com/blender/blender/blob/main/source/blender/io/grease_pencil/intern/grease_pencil_io_export_svg.cc): evaluated objects and drawing layers; uniform-width Bézier curves and variable-width outlines.
- [Blender GP curve SVG support](https://projects.blender.org/blender/blender/pulls/141594): native curve conversion, with polygon outlines for variable widths.
- [Blender PDF exporter manual](https://docs.blender.org/manual/en/5.0/files/import_export/grease_pencil_pdf.html): active/selected/scene frames, sampling, uniform-width option and viewport-based projection. It does not provide a shared SVG/PSD live modifier stack. Direct PDF implementation source retrieval was unavailable during this audit.
- [Curve-to-SVG project](https://github.com/aryelgois/blender-curve-to-svg): source control points, transforms and material grouping.
- [ag-psd native vector records](https://github.com/Agamnentzar/ag-psd/blob/master/src/additionalInfo.ts): vector masks, stroke records and shape contents; keep HandOff's existing precision-capable writer.
- [Inkscape PowerStroke](https://wiki.inkscape.org/wiki/PowerStroke) and [implementation](https://inkscape.gitlab.io/inkscape/doxygen/lpe-powerstroke_8cpp_source.html): width editing; opacity remains a separate gradient.
- [W3C compositing](https://www.w3.org/TR/compositing-1/): standard blend counterparts; GP colour pipelines can differ.

## Further target-application validation

1. Keep the existing PNG render preview and embedded sRGB/linear ICC paths in their current backend.
2. Create two miniature reference PSDs in Photoshop or PhotoCraft: one shape layer with cubic Bézier points and an even-odd cutout; one embedded SVG Smart Object. Compare their tagged blocks.
3. Author minimal low-level layer blocks for each using the existing `psd-tools` serializer. Start at 8-bit but validate both 16-bit and 32-bit layers before shipping.
4. Open, edit and save each in Photoshop, PhotoCraft and Krita. Verify preserved handles, negative zones, fill/stroke, positions, ICC and thumbnails. Keep a raster fallback when any destination loses editing fidelity.
5. Consider embedded SVG Smart Objects for multiple paths and native Photoshop shape layers for simple fills. They are different kinds of editable object and should remain separate options in the eventual writer.

No third-party implementation code was copied. The format adapters use the bundled psd-tools records and existing Blender API.
