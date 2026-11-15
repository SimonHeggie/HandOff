# Handoff

**Hit render, go home.**

Handoff is a Blender add-on in active development for preparing and delivering editable artwork and production assets. The current imported source is **Comp-IO v0.7.50 Alpha**, which retains its original `blend_psd_tools` Python package name and existing UI branding. This repository import does not rename or change its runtime behaviour.

## Product scope

- **Art Source:** Layered documents, source artwork, animation, rigs, and interchange.
- **Deployment:** Game development, asset delivery, packaging, publishing, servers, and web services.
- **Marketing:** Promotional graphics, campaign material, and other marketing deliverables.

## Current focus

1. Blender-to-Blender handoff: editable document scenes and standalone `.blend` delivery.
2. Animation isolation and evaluated-scene change detection.
3. Animation capture where native animation cannot be preserved.

External rig interchange work (including OCO, Rive, and Spine-specific rig formats) is deferred until Blender-native handoff and animation capture/isolation are reliable.

## Installation and source tree

The Blender add-on package is `blend_psd_tools/`. See [its existing README](blend_psd_tools/README.md) for current Comp-IO functionality and installation guidance.

The **source repository intentionally excludes six bundled Pillow wheel binaries** to avoid keeping approximately 33 MB of platform-specific third-party binaries in Git history. This checkout is therefore **not** the complete offline installation package. The ready-to-install ZIP is assembled with the bundled wheels; see [dependency inventory](docs/PILLOW_WHEELS.md) and `scripts/build_install_zip.py`.

Tests recovered from the original development archive are retained in the repository but excluded from installation archives. The add-on has **not been smoke-tested in Blender** as part of this initial repository import.

## Licensing

The vendored `psd_tools` source retains its upstream [MIT licence notice](blend_psd_tools/PSD_TOOLS_LICENSE.txt). A project-wide licence has **not yet been selected or added**; do not assume that the third-party licence applies to the entire add-on.
