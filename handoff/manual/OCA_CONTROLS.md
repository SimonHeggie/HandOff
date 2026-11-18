# OCA destination controls

Expand an OCA destination under Additional Outputs. These seven controls affect
that destination only; PSD/PSB, SVG and other destinations retain their existing
settings and behaviour. Supported GP sources may also use editable SVG cels;
see [OCA vector artwork and alternatives](OCA_VECTORS.md), and [OCA-specific authoring and references](OCA_AUTHORING.md).

| Control | Default | Effect |
| --- | --- | --- |
| Ignore hidden layers | Off | Omit hidden source layers and hidden Collection descendants. When off, keep their image assets and OCA visibility flags. |
| Ignore background layer | On | Omit only explicitly marked background View Layers. Names such as Combined or Background and bottommost placement have no special meaning. |
| Trim whitespace | On | Physically crop each frame to its nonzero alpha bounds. RGB values under zero alpha do not enlarge the bounds. |
| Write Spine JSON | On | Write a minimal Spine 4.2 artwork companion using the OCA assets, positions and bottom-to-top slot order. No skeletal rig conversion. |
| Write template image | Off | Write a document-sized PNG composite of eligible, visible artwork at the current captured frame. |
| Scale | 100% | Scale frame assets, document/layer dimensions and frame centres. Range: greater than zero through 400%. |
| Padding | 1 px | Add transparent pixels to all four sides after cropping and scaling. Frame centres do not move. |

Blender has no Photoshop-style background-layer flag. Explicitly mark the source
View Layer once in Blender's Python Console, using its actual name:

```python
bpy.context.scene.view_layers['MyBackdrop']['handoff_oca_background'] = True
```

Remove the custom property or set it to False to clear the designation. It is
saved with the blend file. A compositor input combining multiple Render Layers
is background only when every traced View Layer is explicitly marked.

Visibility comes from the source View Layer's render flag and Collection/Layer
Collection visibility along its attributed Collection path. An optional custom
property `handoff_oca_visible=False` on a source View Layer or Collection also
hides it in OCA. Existing `.ref` / `.reference` directives remain hidden.
Viewport-hidden artwork that Blender still renders can therefore be retained
without revealing it. A source disabled for rendering still follows the existing
last-render/blank-placeholder policy: the exporter does not change Blender's
render flags to manufacture missing pixels.

Each frame is independently cropped, scaled and padded. The stored position is
the original occupied rectangle's centre multiplied by Scale, even when that
centre is fractional. Image and document dimensions round to the nearest integer
(halves upward, minimum one pixel); padding is applied afterward. A one-pixel
rounding difference must not move the stored centre. Fully transparent trimmed
frames use OCA's `_blank` convention without a needless image file.

At 100% scale, cropped frames reconstruct the same visible pixels as their
uncropped sources. Other scales use alpha-aware bilinear resampling, so edge
samples can differ between independently cropped and full-canvas resizes;
placement remains governed by the exact scaled centre. Verify fractional
placement in the intended reader before relying on its subpixel rendering.

For `Artwork.oca`, companions are placed in:

```text
Artwork/_companions/Artwork.spine.json
Artwork/_companions/Artwork.template.png
```

The JSON's image references resolve to the same published image assets. Animation
uses attachment changes for the existing frame images, including blank frames.
Slots representing hidden artwork stay transparent. Spine cannot represent all
OCA group/slot blend modes; companion limitations are reported without changing
the OCA document. No Spine editor import has been verified in this development
environment.

OCA retains native 8-bit PNG, 16-bit PNG and floating-point EXR assets. Scaling and
compositing use floating-point buffers without 8-bit intermediate conversions.
PNG colour metadata is carried from the source. Since Spine and a PNG template
need PNGs, a floating-point destination additionally writes display-referred
16-bit PNG previews when those companions are requested. Original EXR assets and
HDR values remain unchanged; the preview conversion is reported explicitly.

Retry Export Without Rendering applies the current destination controls to every
cached animation frame. Earlier frame snapshots retain their captured pixels and
precision, but cannot override current trim, scale, padding or companion options.
Save as Render controls cache colour management, independently of alpha trimming.

Existing Flatten Image publishes one visible composite. A `.merge` containing a
mixture of hidden and visible artwork cannot retain separately toggleable hidden
art inside one image: remove `.merge` or enable Ignore hidden layers. The export
reports this conflict instead of silently revealing or discarding that artwork.

Behaviour references: [Photoshop-to-Spine controls](https://github.com/EsotericSoftware/spine-scripts/blob/master/photoshop/README.md),
[OCA frames](https://oca.rxlab.guide/specs/frame.html),
[OCA layers](https://oca.rxlab.guide/specs/layer.html), and
[Spine JSON reader](https://github.com/EsotericSoftware/spine-runtimes/blob/4.2/spine-ts/spine-core/src/SkeletonJson.ts).
