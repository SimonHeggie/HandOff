# Grease Pencil material gradients and invisible fallbacks

Verified against installed Blender 5.3.0 Beta, build `2ebd15112ac6`.

## Initial v0.7.40 shine diagnosis (12 November 2026)

The supplied v38 project has five ShineSprite objects sharing ShineSprite_Material.
Their fill is RADIAL/GRADIENT, with Fill Holdout enabled. All ramp stops have
alpha 1; their RGB values fade white to black. Both original conversion jobs
already contain PNG caches with zero alpha. SVG embedding did not erase them.

A native Cycles A/B render, changing only use_fill_holdout in a private loaded
copy, produces zero visible pixels when enabled and visible sprites when disabled.
This is Blender's subtraction semantics. A visible viewport preview does not
prove that a Holdout material paints the render pass.

For a white shine with transparent edges: disable Fill Holdout on the shared
material; keep the ramp colours white and reduce ramp stop alpha toward the edge.
For an intentional eraser, retain Holdout. The exporter must never silently turn
an eraser into ordinary paint. True holdouts still use Blender's rendered pixels.

## Implementation

- `gp_gradient.py` reads Blender's actual authored ColorRamp elements one for one
  into detached paint records. No shader/material/scene state changes.
- `vector_artwork.py` supplies evaluated drawing attributes, assigns compound
  holes the first contour's gradient frame, and converts ramp colour samples
  through the existing Blender OCIO palette path. Alpha remains independent.
- `svg_export.py` writes user-space linearGradient/radialGradient resources,
  affine transforms and colour/alpha stops. Original cubic paths remain cubic.
- `svg_hybrid.py` distinguishes Holdout from texture rejection, retains the
  actual object rejection reasons for source-wide fallback, and reports empty
  isolated raster groups. `svg_document.py` explains Holdout in empty-cache logs.
- `psd_vectors.py` explicitly retains the existing complete Blender PNG cache for
  material gradients, instead of substituting a flat shape. Native PSD affine
  elliptical gradients have not been verified. Existing pressure-alpha gradient
  support remains active.

Blender's stroke UV frame uses the first two control points and the Newell normal,
followed by curve uv_rotation, uv_translation and uv_scale attributes. Material
texture_angle, texture_offset and texture_scale then map that frame to ramp space.
This is not a bounding-box gradient. Planarity and nonsingular projection are
checked; unsupported geometry remains raster.

Source references:

- [Blender Drawing texture matrix implementation](https://github.com/blender/blender/blob/main/source/blender/blenkernel/intern/grease_pencil.cc)
- [Blender GP vertex data and compound fill mapping](https://github.com/blender/blender/blob/main/source/blender/draw/intern/draw_cache_impl_grease_pencil.cc)
- [Blender GP fragment shader holdout handling](https://github.com/blender/blender/blob/main/source/blender/draw/engines/gpencil/shaders/gpencil_frag.glsl)

Some online draw-shader revisions predate the installed ColorRamp API. Actual
installed API probes and render comparisons are authoritative for this change.

## Validation and limits

`development/test_svg_gradients_blender.py` creates private fixtures for linear,
radial/Ease, Constant and B-spline gradients, including nondefault curve UVs,
material transforms, object rotation and varying ramp alpha. It exports and
renders them with Blender, checks Holdout-only alpha is zero, and checks extraction
leaves no scene/object/image data behind. Compare its outputs with an independent
SVG renderer. The supplied practical source also exports as five cubic objects,
five radial gradients and zero raster objects when Holdout is disabled privately.

v0.7.40 sampled interpolation into 257 regular stops plus authored positions.
In v0.7.41 the user's editing controls take priority: only authored stops are
exported, with their positions, colours and alpha. Standard SVG interpolates
between those stops; Blender Ease, Constant, B-spline and HSV modes therefore
approximate differently. The original interpolation/color mode is retained as
metadata and the export logs this limitation. Hard edges, view transforms and
overlapping translucent paints can also differ. Blender tessellates
Béziers at the drawing resolution; SVG readers render the retained cubic directly.
HDR and view-transform behaviour uses existing colour handling, with the same
overlapping-transparency limitations as other exported GP paints.

Tests reopen imported SVG resources with independent IDs and a PSD fallback with
its source alpha. The practical files were rendered with Blender and SVG readers;
Photoshop and PhotoCraft were unavailable for direct GUI checks.
