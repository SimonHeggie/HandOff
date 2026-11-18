# Disabled View Layers and v0.7.42 validation

The reported exception was deterministic: `ViewLayer.use=False` prevented
Blender from producing Combined's PNG, while `psd_worker.find_inputs()` still
required it. PSD, PNG and SVG failed at the common resolver; FONTS succeeded
because its writer does not require rendered pixels. Concurrent script edits
could introduce separate reload issues, but are unnecessary to reproduce this.
Recovery exposed another independent error: the flattened still writer lacked
overlay although the layered writers and `.merge` compositor supported it.
Flattening now shares `merge_groups.over()` instead of duplicating blend maths.

## Behaviour

The selected current policy is to reuse the last rendered image, postponing
document importing and round-trip merging. No existing PSD/SVG is read.

Preparation records exact upstream Render Layers dependencies and whether any
are disabled. A composite depending on a disabled source holds its complete
last output image. Render-time state remains distinct from current state on
Retry, so a user can disable a source after rendering and retain its pixels.
The native render flag, graph links and socket order are unchanged.

Matching uses existing sync scene/View Layer UUIDs, source node/socket identity,
project filename, destination node, PNG8/PNG16/EXR32 cache kind, Save as Render
and actual canvas dimensions. Unsynced sources use their exact authored names.
Ambiguous branches are not guessed. Legacy jobs require an exact destination
and a unique matching source View Layer; arbitrary missing files never imply
that a source was disabled.

Only HandOff retained job folders are searched. The newest valid compatible
image is copied into the current job's `.compio-held-*` file without changing
its timestamp. This copy survives default cleanup of older job folders, while
remaining visibly older than a genuinely newer render. No vector file from a
different render is paired with held pixels: a disabled source exports its
last rendered pixels even when SVG/native PSD vectors are otherwise enabled.

Without compatible pixels, PNG8/PNG16 transparent caches are generated at the
native bit depth; EXR32 uses Blender's existing float writer. PSD, SVG and OCA
placeholders are hidden. Flattened and individual stills receive blank pixels;
JPEG has no transparency. Notices identify held images and missing history and
are retained in `result.json` and the collapsed Export Details UI.

Clearing all retained caches removes history. Changed dimensions/precision or
ambiguous legacy identity can require a fresh render. This is image reuse,
not preservation of edits made in another application. Normal Retry's existing
guard against incomplete coupled vector/raster preparation remains in force.

## Files

- `__init__.py`: source-state capture, Retry metadata, collapsed reports, font
  folder display and backwards-compatible chime volume.
- `disabled_layers.py`: shared cache identity, history selection, notices and
  native-depth transparent PNGs; no Blender import at module load.
- `psd_worker.py`: missing-input resolution, notices in results and hidden PSD/
  OCA placeholders. The same resolved pixels feed every existing writer.
- `layer_stack.py`, `merge_groups.py`, `svg_document.py`: hidden blank handling
  without changing reference tags, grouping, normal pixels or blend modes.

## Checks

`test_disabled_layers.py` reopens actual PSD/SVG/PNG outputs. It checks newest
image reuse, cache cleanup survival, timestamp preservation, strict enabled
missing-file errors, project/source/colour-setting/size/depth mismatch rejection,
legacy matching, selected-render Retry and PNG16 placeholder precision.

`development/test_disabled_layers_blender.py` uses the installed Blender 5.3
build, renders enabled/disabled View Layers, then renders both to establish
history and renders with one disabled again. It exercises six destinations,
including PSD8/16/32, SVG, flattened PNG and OCA, and confirms unchanged flags.

`development/test_ui_chime_blender.py` checks collapsed UI, actual font output
paths, old saved mute settings, volume persistence, zero-load guards, exact
linear sample gain and lifecycle cleanup using Blender's silent Null backend.
It produces no speaker sound.
