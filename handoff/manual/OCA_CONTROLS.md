# OCA export controls

These seven controls apply only to the selected OCA destination, not PSD, PSB or SVG.

| Control | Default | Effect |
| --- | --- | --- |
| Ignore hidden layers | Off | Omit source layers and Collection descendants explicitly hidden for OCA; when disabled retain visibility metadata |
| Ignore background layer | On | Omit only a View Layer marked as background; no name or stack heuristics |
| Trim whitespace | On | Crop artwork to nonzero-alpha bounds while retaining centre placement |
| Write Spine JSON | Off | Optional image-attachment/slot companion, **not a skeletal rig** |
| Write template image | Off | Optional document-size preview |
| Scale (%) | 100 | Scale dimensions and placement (greater than 0 up to 400%) |
| Padding (px) | 1 | Apply transparent padding after crop/scale without shifting the image centre |

Use the View Layer custom property `handoff_oca_background=True` to mark a background, or author it in the OCA source controls. Frame Step is represented as exposure holds. Blank frames use standard empty-frame behavior. Retry Export (No Render) applies current OCA controls to retained captured frames but cannot regenerate missing renders.

For supported GP artwork, Rasterise Vector Layers selects the rendered representation; Keep Alternative Artwork retains an optional SVG or PNG companion without adding a second visible OCA layer. See [OCA authoring](OCA-authoring) for clone, opacity and nesting controls and [OCA vectors](OCA-vector-artwork) for the editable SVG limitations.
