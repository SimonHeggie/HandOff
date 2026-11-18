# OCA 1.3 authoring and compatibility

Handoff's OCA output can be authored through the View Layer and Collection properties panels. These settings affect OCA only; they do not alter the PSD, PSB or standalone SVG writer. See [OCA controls](OCA_CONTROLS.md) for the seven destination controls and [vector assets](OCA_VECTORS.md) for SVG/PNG handling.

## Project structure and validation

- New destinations can use the canonical `.oca/` directory containing a single `.oca` root document, separate `_meta.json` and relative assets. Saved destinations can retain the explicit legacy layout.
- Stable source-derived IDs, uniqueness-preserving exported aliases, portable relative assets and a pre-publication validator protect consistency. Outputs are generated in a staging area before replacing existing documents; this is not a guarantee against power loss.
- The supported precision values are U8/U16 PNG and F16/F32 EXR. SVG is a separate vector representation, not a floating-point raster format.

## Source authoring

| Blender source control | OCA representation |
| --- | --- |
| View Layer visibility/background | Authored visible/background intent, not inferred from name or compositor stack position |
| Export Opacity / Frame Opacity | Distinct OCA layer opacity and keyed frame opacity, in addition to rendered source alpha |
| OCA Blend / Inherit Alpha | Standard 1.3 blending and alpha-inheritance flags; receiving programs may approximate the visual result |
| Linked Grease Pencil duplicates | Verified shared-datablock/appearance relationships can produce `clonelayer` references; unsupported rotations/styling become separate artwork |
| Keep Independent | Opt out of automatic cloning |
| Source View Layer / Offset / Time Offset | Explicit validated source reference, positional shift, and stepped exposure timing |
| Nested OCA Document | A portable `ocalayer` referencing a copied nested project, with optional source-layer ID |
| Collection opacity / blend / isolation | Standard group authoring, preserving the existing collection hierarchy |

OCA 1.3 does **not** define general pivot/rotation/scale animation, an exported Blender armature, or skeletal weights in this implementation. Selective frame deduplication and transform capture are roadmap items, not features of this release.

## Interoperability and limitations

Native image and SVG cels, nested projects, clones and time offsets have been exercised with Bluik development fixtures. The Bluik compatibility improvements are maintained separately and are **not** installed merely by installing Handoff. The receiving preview may still approximate complex multi-child isolated blending, Inherit Alpha clipping and some GP gradients; PNG alternatives can supply visual fallbacks. Photoshop, PhotoCraft and Krita graphical edit/save round-trips have not been certified by these Blender tests.
