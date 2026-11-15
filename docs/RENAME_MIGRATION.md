# HandOff naming and compatibility migration

The product name is **HandOff** (capital H and O); the Python package/install folder is **`handoff/`**.
The change was made after the historical v0.7.50 Alpha 1 prerelease; that prerelease is not retroactively modified.

- **Important:** Before installing the renamed add-on, disable and remove the old `blend_psd_tools` add-on in Blender. It is a different package identifier, and installing both can cause duplicate render handlers.
- Some saved Blender RNA property identifiers and `blend_psd.*` operator IDs are intentionally unchanged to keep old project settings and scripts functional. These are internal API keys, not displayed brand names.
- Previously generated SVG `data-compio-*` metadata and `_compio_*` properties are historical interchange/persistence keys. The new build emits `data-handoff-*` and reads retained legacy forms where implemented.
- Blender preferences stored for the old package may need to be configured again for `handoff`.
- Old cache directories, temporary-job markers and environment overrides remain readable. New environment overrides: `HANDOFF_CACHE` and `HANDOFF_JOB_ROOT`.
- No automated `.blend` file conversion or Blender integration smoke test is claimed as part of this rename. Keep a backup before upgrading an existing production project.
