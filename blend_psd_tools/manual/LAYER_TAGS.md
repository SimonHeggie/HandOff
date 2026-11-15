# Comp-IO - Layer Tag Compatibility

Reference for layer tags and their destination mappings.

## How to use this reference

**Tag Compatibility** belongs to each Additional Output entry. `Manual / No Conversion` is the default. Select Spine, Generator or OCA only when the destination requires it. `Manual / No Conversion` retains the authored expressions. Tag conversion changes exported names, never Blender Collection or socket names.

The entries below are sorted by **common workflow function**, not alphabetically. Each mapping is an explicit token or a structured metadata instruction. When a feature has no safe equivalent, the exporter preserves the original directive and **Check Export Status** reports it.

## Collection hierarchy and group names

Comp-IO uses Blender Collection ancestry to organise grouped exports. File Output socket order determines the final layer order. A Collection can appear in separate group instances when other artwork falls between its outputs.

When repeated groups need distinguishing names, Comp-IO uses a relevant child Collection or exported layer name. Original Collection names are preserved wherever the result remains unambiguous. Group and paint layers may share the same name.

PSD and PSB group colour labels follow Blender Collection colour tags. Paint layers follow their owning Collection label. An explicitly untagged Collection stops ancestor colour inheritance, including ancestors removed by `.ungroup`. SVG displays untagged highlights as white; PSD maps them to its native Grey label. The receiving PSD editor controls the brightness of that swatch. Colour labels affect document organisation only.

An output covering several Collections can remain at the document root. Check Export Status prints source Collection paths and a preview of the output hierarchy in the Blender terminal.

## Dot suffixes and blend modes

Comp-IO interprets recognised dot suffixes on authored output names. A suffix can specify a blend mode or an export operation. It is removed from the displayed layer name after the instruction is applied.

```text
Highlight.add -> Highlight (Add)
Shadow.multiply -> Shadow (Multiply)
```

If a strict majority of a group's direct pixel layers use the same non-Normal blend mode, Comp-IO can apply that mode to their group and set the affected children to Normal. Check the composite when mixing modes or working between editors.

OpenEXR commonly uses dot-separated channel identifiers such as `Layer.R`. Comp-IO's dot suffixes are authoring directives defined by Comp-IO; OpenEXR channel names have separate semantics.

## Collection export operations

A Collection with `.merge` is rasterised to one paint layer. The exported paint layer takes the Collection name with the suffix removed. Child outputs are composited in their File Output order.

```text
Artwork.merge
  Base
  Details

Export: Artwork (paint layer)
```

`.ungroup` removes a Collection container and promotes its children to the next retained ancestor. `.ignore` omits its subtree. `.ref` keeps reference artwork hidden in PSD and marked as reference in OCA.

Do not use `.merge` and `.ungroup` together on the same Collection. A merge applies to a consecutive group run, preserving the overall layer order. Merging layers with backdrop-dependent blends may change the composite.

## PSD/PSB colour handling

For 8-bit and 16-bit display-referred PSD/PSB exports, Comp-IO embeds the PNG source ICC profile when present and otherwise assigns sRGB. The 16-bit path preserves the PNG channel values during transfer.

32-bit exports preserve scene-linear HDR pixels. The standard Blender Rec.709 working space uses a corresponding linear RGB ICC profile. When a custom OCIO override is detected, the writer reports this and leaves the profile unassigned.

PSD and PSB support group and paint-layer colour labels. Comp-IO reads Collection colour tags and applies the nearest supported Photoshop label colour. Editor support for displaying those labels varies.

## Common functions - quick lookup

| Function | Spine PSD | Photoshop Generator | OCA for Krita |
|:--|:--|:--|:--|
| [Ignore / omit on export](#exclude) | `[ignore]` | - | `_ignore_` |
| [Reference / guide artwork](#reference) | `[ignore]` | - | `_reference_` |
| [Merge a group into one paint layer](#merge) | `[merge]` | - | `_merge_` |
| [Preserve layer hierarchy](#group) | - | - | - |
| [Hidden / initial visibility](#hidden) | - | - | - |
| [Layer / group blend mode](#blend) | - | - | - |
| [Asset image subfolder](#folder) | `[folder]` | `icons/Icon.png` | - |
| [Generate named asset / file format](#asset-format) | - | `Icon.png` | - |
| [Multiple assets from a single layer](#asset-multiple) | - | `Icon.png,Icon.jpg` | - |
| [Generated asset relative scale](#asset-scale) | - | `200% Logo.png` | - |
| [Absolute asset dimensions](#asset-dimensions) | - | `100x100 Icon.png` | - |
| [JPEG quality](#asset-quality) | - | `Hero.jpg80%` | - |
| [PNG variant](#asset-depth) | - | `Icon.png24` | - |
| [Slot assignment](#slot) | `[slot]` | - | - |
| [Bone assignment](#bone) | `[bone]` | - | - |
| [Skin / placeholder assignment](#skin) | `[skin]` | - | - |
| [Mesh attachment](#mesh) | `[mesh]` | - | - |
| [Spine attachment image path](#attachment-path) | `[path:name]` | - | - |
| [Trim whitespace / canvas / mask](#trim) | `[trim]` | - | - |
| [Attachment padding](#padding) | `[pad:number]` | - | - |
| [Attachment inverse rotation](#rotation) | `[rotate:degrees]` | - | - |
| [Spine origin marker](#origin) | `[origin]` | - | - |
| [Spine overlay mask](#overlay) | `[overlay]` | - | - |
| [Create bones for group immediate children](#child-bones) | `[bones]` | - | - |
| [Create slots for group immediate children](#child-slots) | `[slots]` | - | - |
| [Pattern rename for name, path, bone and slot](#group-pattern) | `[name:prefix*suffix]` | - | - |

## Detailed functions by topic


### Group and export operations

<a id="exclude"></a>
#### Ignore / omit on export

Do not include a layer or group in the target export.

**Where applicable:** layer,group.

**Spine** - native

- Syntax / property: `[ignore]`
- Direct emission template: `[ignore]`
- Representation: layer-name
- Meaning / caveat: Spine import ignores target and descendants.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: Generator has no standalone ignore directive. An ordinary layer name without asset filename will not itself trigger an asset.

**OCA for Krita / native OCA** - native

- Syntax / property: `_ignore_`
- Direct emission template: `_ignore_`
- Representation: Krita layer-name / OCA writer
- Meaning / caveat: Krita exporter excludes the layer; native OCA writer omits it.

**Blender authoring syntax:** `.ignore`

**Important:** Spine [ignore] can preserve a visible PSD reference, whereas excluding a layer from the PSD removes it completely.

<a id="reference"></a>
#### Reference / guide artwork

Keep for the artist but mark non-rendering/non-exporting downstream.

**Where applicable:** layer,group.

**Spine** - approximation

- Syntax / property: `[ignore]`
- Direct emission template: `[ignore]`
- Representation: layer-name + metadata
- Meaning / caveat: Spine has no reference tag; [ignore] stops importer from creating an attachment.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No Generator reference directive; keep a normal hidden layer without a Generator filename.

**OCA for Krita / native OCA** - native

- Syntax / property: `_reference_`
- Direct emission template: `_reference_`
- Representation: Krita layer-name / OCA JSON
- Meaning / caveat: Krita OCA exporter marks a reference; native OCA layer.reference=true.

**Blender authoring syntax:** `.ref`

**Important:** Reference artwork can remain available as a guide. Spine [ignore] omits it on import, while OCA marks it as reference content.

<a id="merge"></a>
#### Merge a group into one paint layer

Comp-IO rasterizes a tagged Blender Collection into one PSD/OCA pixel layer. Its name comes from the group, with .merge removed. Multiple child render layers are composited in their stack order.

**Where applicable:** group,layer.

**Spine** - partial

- Syntax / property: `[merge]`
- Direct emission template: `[merge]`
- Representation: group-name
- Meaning / caveat: Spine [merge] asks its importer to flatten an existing PSD group. Comp-IO .merge is applied during PSD creation, resulting in one paint layer.

**Photoshop Generator** - approximation

- Syntax / property: -
- Direct emission template: -
- Representation: group asset filename
- Meaning / caveat: Generator flattens a group only into a generated asset file; it does not change the PSD layer hierarchy.

**OCA for Krita / native OCA** - native

- Syntax / property: `_merge_`
- Direct emission template: `_merge_`
- Representation: Krita layer-name / OCA preprocessing
- Meaning / caveat: Krita OCA export can flatten tagged groups. Comp-IO writes already merged pixels in native OCA.

**Blender authoring syntax:** `.merge`

**Important:** Comp-IO merges cached pixels without changing Blender geometry. Mixed group blend modes can look different after flattening when they depend on backdrop artwork outside the group. Test complex compositing before delivery.

<a id="group"></a>
#### Preserve layer hierarchy

Keep authored parent/child grouping.

**Where applicable:** group.

**Spine** - metadata

- Syntax / property: -
- Direct emission template: -
- Representation: PSD hierarchy
- Meaning / caveat: Spine [folder] controls the attachment output directory. PSD groups retain their own hierarchy.

**Photoshop Generator** - metadata

- Syntax / property: -
- Direct emission template: -
- Representation: PSD hierarchy
- Meaning / caveat: Generator can use any group for compositing but does not use arbitrary folder names as paths.

**OCA for Krita / native OCA** - metadata

- Syntax / property: -
- Direct emission template: -
- Representation: OCA JSON
- Meaning / caveat: Native OCA expresses groups structurally; no naming tag required.

**Blender authoring syntax:** `.ungroup`

**Important:** Group membership must preserve original draw order; noncontiguous hierarchy needs split group instances.

<a id="hidden"></a>
#### Hidden / initial visibility

Preserve artwork but open it hidden.

**Where applicable:** layer,group.

**Spine** - metadata

- Syntax / property: -
- Direct emission template: -
- Representation: PSD metadata
- Meaning / caveat: Spine can optionally ignore hidden layers on import.

**Photoshop Generator** - metadata

- Syntax / property: -
- Direct emission template: -
- Representation: PSD metadata
- Meaning / caveat: Photoshop Generator follows the normal layer visibility settings when producing assets.

**OCA for Krita / native OCA** - metadata

- Syntax / property: -
- Direct emission template: -
- Representation: OCA JSON
- Meaning / caveat: No OCA name tag needed.

**Blender authoring syntax:** `.hidden`


### EXR-style suffixes and blend modes

<a id="blend"></a>
#### Layer / group blend mode

Preserve blending behaviour where known to be compatible.

**Where applicable:** layer,group.

**Spine** - metadata

- Syntax / property: -
- Direct emission template: -
- Representation: PSD metadata
- Meaning / caveat: Spine only recognises these four imported modes.

**Photoshop Generator** - metadata

- Syntax / property: -
- Direct emission template: -
- Representation: PSD metadata / generated pixels
- Meaning / caveat: No name tag; asset generation renders composite.

**OCA for Krita / native OCA** - metadata

- Syntax / property: -
- Direct emission template: -
- Representation: OCA JSON
- Meaning / caveat: See canonical blending table; OCA uses Krita semantics.

**Blender authoring syntax:** `.normal`

**Important:** Unrecognised modes produce warnings. Check the appearance of nested blend groups after export.


### Group and export operations

<a id="folder"></a>
#### Asset image subfolder

Place extracted image assets within a directory structure.

**Where applicable:** layer,group.

**Spine** - native

- Syntax / property: `[folder]`
- Direct emission template: `[folder:{name}]`
- Representation: layer/group-name
- Meaning / caveat: Spine attachment output paths and hierarchy.

**Photoshop Generator** - partial

- Syntax / property: `icons/Icon.png`
- Direct emission template: -
- Representation: generated asset filename
- Meaning / caveat: Generator creates subfolder paths only as part of an asset filename.

**OCA for Krita / native OCA** - metadata

- Syntax / property: -
- Direct emission template: -
- Representation: OCA JSON / folder structure
- Meaning / caveat: Folder structure from group and layer metadata; not a name directive.

**Blender authoring syntax:** `.folder`

**Important:** Grouping folders can organise artwork without creating an asset output directory.


### Photoshop Generator

<a id="asset-format"></a>
#### Generate named asset / file format

Generate one asset file with an explicit image format.

**Where applicable:** layer,group.

**Spine** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**Photoshop Generator** - native

- Syntax / property: `Icon.png`
- Direct emission template: -
- Representation: generator filename
- Meaning / caveat: These names activate Generator when enabled and PSD saved.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**Important:** SVG generation from raster content does not create genuinely editable vector artwork.

<a id="asset-multiple"></a>
#### Multiple assets from a single layer

Export alternative formats/sizes from one layer.

**Where applicable:** layer,group.

**Spine** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**Photoshop Generator** - native

- Syntax / property: `Icon.png,Icon.jpg`
- Direct emission template: -
- Representation: generator filename
- Meaning / caveat: Comma and plus both separate asset specifications.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

<a id="asset-scale"></a>
#### Generated asset relative scale

Resize output asset while leaving PSD source pixels unchanged.

**Where applicable:** layer,group.

**Spine** - none

- Syntax / property: -
- Direct emission template: -
- Representation: Spine attachment transform
- Meaning / caveat: Spine inverse attachment scale controls the attachment transform. Generator asset sizing is set through filenames.

**Photoshop Generator** - native

- Syntax / property: `200% Logo.png`
- Direct emission template: -
- Representation: generator filename
- Meaning / caveat: Percentage prefix followed by space.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

<a id="asset-dimensions"></a>
#### Absolute asset dimensions

Set generated asset width, height or proportional wildcard dimensions.

**Where applicable:** layer,group.

**Spine** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**Photoshop Generator** - native

- Syntax / property: `100x100 Icon.png`
- Direct emission template: -
- Representation: generator filename
- Meaning / caveat: Units px/in/cm/mm; cannot combine absolute and percentage size.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

<a id="asset-quality"></a>
#### JPEG quality

Encode JPEG output quality in a generated filename.

**Where applicable:** layer,group.

**Spine** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**Photoshop Generator** - native

- Syntax / property: `Hero.jpg80%`
- Direct emission template: -
- Representation: generator filename
- Meaning / caveat: JPEG 1-10 or 1%-100%; no suffix defaults to 90%.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

<a id="asset-depth"></a>
#### PNG variant

Select PNG-8 indexed, PNG-24 RGB or PNG-32 RGBA Generator asset.

**Where applicable:** layer,group.

**Spine** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**Photoshop Generator** - native

- Syntax / property: `Icon.png24`
- Direct emission template: -
- Representation: generator filename
- Meaning / caveat: Default png32. These options control PNG channel variants and do not specify per-channel bit depth.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**Important:** Never translate png32 to 32-bit-float; Generator png32 is 32 total bits (8 RGBA).


### Spine directives

<a id="slot"></a>
#### Slot assignment

Assign attachments to named Spine slots.

**Where applicable:** layer,group.

**Spine** - native

- Syntax / property: `[slot]`
- Direct emission template: `[slot:{name}]`
- Representation: layer/group-name
- Meaning / caveat: Closest ancestor slot applies.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**Blender authoring syntax:** `.slot:name`

<a id="bone"></a>
#### Bone assignment

Create or assign Spine bones.

**Where applicable:** layer,group.

**Spine** - native

- Syntax / property: `[bone]`
- Direct emission template: `[bone:{name}]`
- Representation: layer/group-name
- Meaning / caveat: Bone positioned using first visible layer center.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**Blender authoring syntax:** `.bone:name`

<a id="skin"></a>
#### Skin / placeholder assignment

Create Spine skin placeholders.

**Where applicable:** layer,group.

**Spine** - native

- Syntax / property: `[skin]`
- Direct emission template: `[skin:{name}]`
- Representation: layer/group-name
- Meaning / caveat: Closest skin defines skin name; ancestor tags affect folders.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**Blender authoring syntax:** `.skin:name`

<a id="mesh"></a>
#### Mesh attachment

Create/link mesh attachment in Spine.

**Where applicable:** layer.

**Spine** - native

- Syntax / property: `[mesh]`
- Direct emission template: `[mesh:{name}]`
- Representation: layer-name
- Meaning / caveat: Documentation restricts these to layers or merged groups.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**Blender authoring syntax:** `.mesh:name`

<a id="attachment-path"></a>
#### Spine attachment image path

Override attachment image path independently from layer name.

**Where applicable:** layer,merged-group.

**Spine** - native

- Syntax / property: `[path:name]`
- Direct emission template: `[path:{name}]`
- Representation: layer-name
- Meaning / caveat: Slash at start makes path absolute relative to image root; different from Generator asset path.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: generator filename
- Meaning / caveat: Generator paths are full output filename specifications, with file extensions.

**OCA for Krita / native OCA** - metadata

- Syntax / property: -
- Direct emission template: -
- Representation: OCA JSON
- Meaning / caveat: OCA stores the frame image path in metadata.

<a id="trim"></a>
#### Trim whitespace / canvas / mask

Control trimming of exported attachments.

**Where applicable:** layer,group.

**Spine** - native

- Syntax / property: `[trim]`
- Direct emission template: `[trim:{mode}]`
- Representation: layer/group-name
- Meaning / caveat: Spine switches whitespace removal, canvas size, or mask trim.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No standard direct trim flag; preprocessing would be required.

<a id="padding"></a>
#### Attachment padding

Add padding pixels for imported attachment.

**Where applicable:** layer,group.

**Spine** - native

- Syntax / property: `[pad:number]`
- Direct emission template: `[pad:{number}]`
- Representation: layer/group-name
- Meaning / caveat: Spine PSD importer-specific padding.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

<a id="rotation"></a>
#### Attachment inverse rotation

Rotate extracted attachment inversely for atlas use.

**Where applicable:** layer,group.

**Spine** - native

- Syntax / property: `[rotate:degrees]`
- Direct emission template: `[rotate:{degrees}]`
- Representation: layer/group-name
- Meaning / caveat: Spine attachment inverse rotation.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

<a id="origin"></a>
#### Spine origin marker

Use layer center as origin and do not export marker image.

**Where applicable:** layer.

**Spine** - native

- Syntax / property: `[origin]`
- Direct emission template: `[origin]`
- Representation: layer-name
- Meaning / caveat: Spine layer origin marker; guides are another way to set origin.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

<a id="overlay"></a>
#### Spine overlay mask

Clipping-like overlay for underlying layers.

**Where applicable:** layer,group.

**Spine** - native

- Syntax / property: `[overlay]`
- Direct emission template: `[overlay]`
- Representation: layer/group-name
- Meaning / caveat: Spine overlay behavior; not a general PSD clipping mask.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

<a id="child-bones"></a>
#### Create bones for group immediate children

Automatically add bone tags to immediate children.

**Where applicable:** group.

**Spine** - native

- Syntax / property: `[bones]`
- Direct emission template: `[bones]`
- Representation: group-name
- Meaning / caveat: Group auto-tag and suppression.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

<a id="child-slots"></a>
#### Create slots for group immediate children

Automatically add slot tags to immediate children.

**Where applicable:** group.

**Spine** - native

- Syntax / property: `[slots]`
- Direct emission template: `[slots]`
- Representation: group-name
- Meaning / caveat: Group auto-tag and suppression.

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

<a id="group-pattern"></a>
#### Pattern rename for name, path, bone and slot

Apply wildcard-based propagation to group child directives.

**Where applicable:** group.

**Spine** - native

- Syntax / property: `[name:prefix*suffix]`
- Direct emission template: `[name:{pattern}]`
- Representation: group-name
- Meaning / caveat: Suppress with [!name] / [!path] / [!bone] / [!slot].

**Photoshop Generator** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: Do not attempt to transfer Spine wildcard patterns to Generator.

**OCA for Krita / native OCA** - none

- Syntax / property: -
- Direct emission template: -
- Representation: none
- Meaning / caveat: No direct equivalent; preserve original expression and warn.

## Photoshop Generator syntax

Generator asset names are *filename expressions*, not Spine tags and not OCA metadata. These must remain intact when you select **Photoshop Generator**. The add-on does not itself run Photoshop Generator.

| Purpose | Valid example |
|:--|:--|
| JPEG quality | `Photo.jpg5`, `Hero.jpg80%` |
| PNG asset depth (total bits) | `Icon.png8`, `Icon.png24`, `Icon.png32` |
| GIF / SVG | `Animation.gif`, `Shape.svg` |
| Percentage resize | `200% Logo.png`, `50% Icon.jpg` |
| Absolute / mixed units | `100x80 Thumb.png`, `4in x 100 Banner.jpg` |
| Proportional wildcard | `100x? Logo.png`, `?x60in Banner.jpg` |
| Multiple outputs | `Icon.png8, Icon.jpg90%` |
| Subfolder | `icons/Icon.png`, `@2x/Hero.jpg` |

**Invalid:** `100x100foo.png` (missing separator), `80x100 60% foo.png` (mixed scaling), `30nm x20 Image.png` (invalid unit). Generator does not allow colons or asterisks in asset names.

### Schema-defined recognizers

This table records the **explicit grammar** available to validation code. Conversion never searches arbitrary filenames for keywords.

| System | Recognizer | Example |
|:--|:--|:--|
| spine | `bracket-tag` | `[slot:Eye]` |
| oca | `krita-tag` | `_reference_` |
| generator | `generator-spec` | `200% Icon.png8` |
| image-node-plus-internal | `suffix-dot` | `.ref` |

## OpenEXR - channel and pass naming

EXR layers are sets of named pixel channels, not PSD paint layers. OpenEXR has **no standard layer blend-mode, draw-order, ignore or merge name tag**. The following data is a **channel naming reference**, not a tag converter.

| Channel | Category | Definition | Standard status |
|:--|:--|:--|:--|
| `R` | color | Red channel | defined |
| `G` | color | Green channel | defined |
| `B` | color | Blue channel | defined |
| `A` | alpha | Opacity/alpha; normally premultiplied colors | defined |
| `Y` | luminance | Luminance in Y/RY/BY representation | recommended |
| `RY` | chroma | Red relative to luminance | recommended |
| `BY` | chroma | Blue relative to luminance | recommended |
| `AR` | alpha | Per-channel red alpha | recommended |
| `AG` | alpha | Per-channel green alpha | recommended |
| `AB` | alpha | Per-channel blue alpha | recommended |
| `Z` | depth | Front depth; special meaning in deep samples | reserved-deep |
| `ZBack` | depth | Back depth of deep sample | reserved-deep |
| `RA` | alpha | Per-channel red alpha in deep samples | reserved-deep |
| `GA` | alpha | Per-channel green alpha in deep samples | reserved-deep |
| `BA` | alpha | Per-channel blue alpha in deep samples | reserved-deep |
| `id` | identifier | Deep sample object identifier | reserved-deep |

### Layer naming patterns

| Structure | Meaning |
|:--|:--|
| `R \| G \| B \| A` | Base layer colour channels |
| `{layer}.R \| {layer}.G \| {layer}.B \| {layer}.A` | Layer name is everything before the final dot |
| `{outer}.{inner}.R` | Dot-delimited channel prefix encodes nested EXR layer names |
| `{layer}.{view}.R` | Single-part multi-view channels; view position is penultimate |
| `part name / view attribute` | Multipart files identify parts and optionally views via header attributes |
| `CryptoObject00.R \| CryptoMaterial00.G` | Cryptomatte identifies masks through layer channels and EXR header metadata |

### Blender Render Passes - examples, not official EXR tags

| Blender pass family | Blender render pass |
|:--|:--|
| image | `Combined` |
| image | `Alpha` |
| data | `Depth (Z)` |
| data | `Mist` |
| data | `Position` |
| data | `Normal` |
| data | `Vector` |
| data | `UV` |
| data | `Object Index` |
| data | `Material Index` |
| diffuse | `Diffuse Direct` |
| diffuse | `Diffuse Indirect` |
| diffuse | `Diffuse Color` |
| glossy | `Glossy Direct` |
| glossy | `Glossy Indirect` |
| glossy | `Glossy Color` |
| transmission | `Transmission Direct` |
| transmission | `Transmission Indirect` |
| transmission | `Transmission Color` |
| volume | `Volume Direct` |
| volume | `Volume Indirect` |
| other-light | `Emission` |
| other-light | `Environment` |
| other-light | `Ambient Occlusion` |
| other-light | `Shadow Catcher` |
| mask | `Cryptomatte Object` |
| mask | `Cryptomatte Material` |
| mask | `Cryptomatte Asset` |
| custom | `Shader AOV Color` |
| custom | `Shader AOV Value` |
| denoising | `Denoising Normal` |
| denoising | `Denoising Albedo` |

Exact EXR channel prefixes depend on the writing application, View Layer and output settings. OpenEXR channel names do not prescribe how to composite passes.


## Conversion and fallback policy

1. Match **only tokens explicitly declared** under `sourceTokens` in `tags.xml`; parameterised tokens use `{value}`.
2. Look up the behaviour ID, then its destination profile and `emit` template. Do not infer a template from prose.
3. If the mapping is unavailable, retain the original token and emit a warning. Preservation is not a guarantee that all third-party applications will ignore the token.
4. `Manual / No Conversion` is the default. Flattened outputs disable tag compatibility. Legacy Automatic profiles now resolve to No Conversion.
5. Native `.oca` uses structured fields (`reference`, `visible`, `blendingMode`); `_reference_` etc. are **Krita OCA-exporter name tags**, not native OCA JSON tags.
6. Layer/Collection identity, raster content and alpha processing are separate from translated output labels.

## Credits and source documentation

- **[Esoteric Software](https://us.esotericsoftware.com/spine-import-psd)** - Spine User Guide - Import PSD.
- **[Adobe](https://helpx.adobe.com/photoshop/desktop/automate-tasks/automation-settings-and-presets/image-asset-generator-naming-syntax.html)** - Photoshop - Image asset generator naming syntax (2026-10-04).
- **[Nicolas Dufresne (Duduf) / RxLaboratorio](https://rxlab.guide/oca-krita/layer-tags.html)** - OCA for Krita - Layer tags.
- **[Nicolas Dufresne (Duduf) / RxLaboratorio](https://oca.rxlab.guide/specs/layer.html)** - Open Cel Animation - Layer Object specification.
- **[Academy Software Foundation / OpenEXR](https://openexr.com/en/latest/TechnicalIntroduction.html)** - Technical Introduction to OpenEXR.
- **[Academy Software Foundation / OpenEXR](https://openexr.com/en/latest/InterpretingDeepPixels.html)** - Deep Image Channels and Layer Names.
- **[Academy Software Foundation / OpenEXR](https://openexr.com/en/rb-3.1/MultiViewOpenEXR.html)** - Storing Multi-View Images.
- **[Blender Foundation](https://docs.blender.org/manual/en/dev/render/layers/passes.html)** - Render Passes Reference.
- **[Psyop / Cryptomatte contributors](https://github.com/Psyop/Cryptomatte)** - Cryptomatte Specification.

The OCA conventions and source material are credited to **Nicolas Dufresne (Duduf)** and **RxLaboratorio**. This registry is an independently authored compatibility mapping rather than a verbatim copy of vendor manuals.
