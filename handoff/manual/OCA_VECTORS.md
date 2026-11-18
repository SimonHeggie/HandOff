# HandOff OCA vector artwork

An OCA destination can now publish supported Grease Pencil artwork using native
`vectorlayer` objects and SVG frame assets. One logical artwork layer corresponds
to one compositor input. Its SVG contains the supported evaluated GP objects for
that input, including editable strokes/fills and the existing internal source
hierarchy. It does not replace an entire Collection with one generic OCA folder.

Sources are traced to their actual Blender Scene and View Layer. Direct Render
Layers Image connections and reroutes are eligible. Compositor processing,
mixed 3D sources, unsupported masks, lighting or SVG raster components retain
rendered paint layers with a diagnostic. Existing `.merge` and Flatten Image
remain raster operations. Animation uses the captured source's animated scene at
each actual frame, not a frozen copy of the first frame's vector geometry.

**Rasterise Vector Layers** publishes the rendered image as the visible OCA
paint layer while retaining a supported editable SVG under `_vectors/`.
**Keep Rendered PNG Fallback** preserves the native rendered equivalent of each
visible SVG cel under `_raster/`. The existing Spine JSON and template options
also retain these PNGs when needed by their consumers. Only one representation
is inserted into the document stack, so artwork is never displayed twice.

OCA has no standard alternate-representation selector. HandOff therefore uses
ordinary companion assets and the standard frame `meta` extension point:

```json
"meta": {
  "handoff": {
    "raster": {
      "fileName": "Artwork/_raster/FX/Shine_00000.png",
      "width": 39,
      "height": 37,
      "position": [24.5, 95.5],
      "colorDepth": "U8"
    }
  }
}
```

For a rasterized layer the corresponding key is `editableSource`, describing
the SVG asset with the same size and centre. These are documented application
metadata, not new OCA layer/frame properties or extra visible layers. Readers
that ignore them can still load the standard visible SVG/PNG representation.
To use a PNG in a reader without SVG support, publish with Rasterise Vector
Layers enabled. Verified linked Grease Pencil clones, explicit source View Layer references and external nested OCA documents are available in v0.7.53; see [OCA authoring](OCA_AUTHORING.md).

Trimming, scale and padding use the existing OCA image processing path. The SVG
viewport and explicit pixel dimensions describe the same processed rectangle
as its PNG alternative; both use the same exact centre. Ordinary filenames are
`Name_00000.png` / `.svg`. Genuine collisions use `Name-2_00000`, including on
case-insensitive file systems. Group-relative directories and stack order stay
unchanged. IDs retain the existing deterministic hierarchy/order identity.

On the current Blender 5.3 Beta, Hatshepsut's full multi-View-Layer export produced
an empty Shine Image cache even though its source View Layer rendered visible
GP artwork in isolation. During an initial export HandOff can recover an empty
cache from its captured, directly traced GP-only scene, frame and camera using
Blender's native renderer with compositor processing disabled. It does not paint
an SVG into a PNG or change the production blend file. The recovered pixels are
reused by every destination. A native-confirmed blank frame remains blank.

**Retry Export Without Rendering never runs this recovery render.** It reuses
the repaired pixels or reports that another render is needed. A genuinely blank
frame confirmed by the initial native render is recorded in the owned cache so
retries do not mistake it for a failed render.

The exact internal Blender cause of the multi-view GP omission remains
unconfirmed. The isolated-native recovery is limited to the reproduced direct
GP-only condition; it never bypasses an authored compositor operation.

SVG and Blender rasterizers can differ in antialiasing, gradient interpolation,
colour management and overlapping transparency. Hatshepsut's exported Shine was
actually rasterized with CairoSVG and compared against its native PNG at test
resolution: matching dimensions, approximately 0.029 premultiplied RGBA RMSE on
a 0–1 scale. This is measured compatibility evidence, not pixel equivalence.
Use the native PNG representation when exact rendered appearance matters.

OCA colour labels restore the existing reference installation's numeric palette:
RED 1, ORANGE 2, YELLOW 3, GREEN 4, BLUE 5, VIOLET 6, MAGENTA 7, GRAY 8; unlabelled
is -1. The working baseline had stopped assigning these labels. The shared
Blender/PSD colour mapping and PSD group-label writer were not changed. Importers
may display their own numeric palettes.

For 32-bit EXR workflows, an SVG's optional PNG alternative is a 16-bit display
preview, reported during publishing. Native non-vector EXR cels retain their
floating-point precision. The seven existing controls are documented in
[OCA controls](OCA_CONTROLS.md).
