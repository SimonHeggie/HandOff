# HandOff v0.7.51 Alpha 1

The existing compositor-based layered asset exporter has been rebranded to **HandOff**, including its Blender add-on package, UI titles, documentation and newly generated SVG metadata.

### What's changed

- Renamed the installation module folder to `handoff/` and the UI identity to **HandOff**.
- Updated the user-facing tagline to **Hit render, go home.**
- Updated source tests, documentation, package-builder paths and bundled dependency placement.
- New generated XML identifiers use `handoff` instead of the previous product identifier.
- Legacy SVG metadata, saved scene identifiers, cache and job markers remain readable where supported.

### Important upgrade note

**Disable and uninstall the old `blend_psd_tools` add-on before enabling `handoff`.** Blender treats them as distinct packages. Running both simultaneously can produce duplicate render handlers. Previously saved settings may require reconfiguration. Existing internal Blender RNA property and operator identifiers are intentionally retained for compatibility with older `.blend` files and automation scripts.

### Current limitations

- This is still the existing v0.7-era alpha functionality, not the future Blender-to-Blender document exporter.
- Syntax and ZIP integrity are checked. Full interactive Blender integration has not been verified in this environment.
- Pillow binaries support CPython 3.13; CPython 3.14 needs additional dependency packages.
- The optional Bfont-to-OpenType font asset is absent from the cleaned package; exact conversion via that route is unavailable.
- Historical release `v0.7.50-alpha.1` remains available with its original code and filenames.

See [the migration notes](https://github.com/SimonHeggie/HandOff/blob/main/docs/RENAME_MIGRATION.md).
