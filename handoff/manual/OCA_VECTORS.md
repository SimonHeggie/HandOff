# OCA vector artwork and raster alternatives

Eligible Grease Pencil inputs traced directly through Blender's compositor Render Layers and reroutes can produce OCA `vectorlayer` frames backed by editable SVG artwork. The SVG contains the supported GP strokes/fills and hierarchy for the individual source input. Compositor effects, unsupported gradients/geometry and mixed 3D artwork use the rendered raster image as the visible representation.

- **Rasterise Vector Layers** selects the rendered raster as the one visible OCA layer.
- **Keep Alternative Artwork** optionally retains the unselected editable SVG or native PNG under `_vectors/` or `_raster/`; it never creates duplicate visible OCA layers.
- Unsupported SVG features may require a supplied companion render for correct appearance in receiving software. SVG and PNG previews can differ in gradients and antialiasing.
- Trim, scale, padding, crop centres, frame numbers and blank exposures use the existing OCA export pipeline.
- Supported verified shared GP artwork can additionally export as OCA `clonelayer` references. This is distinct from a general rig, transform-curve or bone-weight conversion.

Alternative references reside in normal OCA frame `meta.handoff` application metadata; they are not standard alternate-representation layer fields. To support a reader that ignores SVG, choose Rasterise Vector Layers when publishing. See [OCA controls](OCA-controls) and [OCA authoring](OCA-authoring).
