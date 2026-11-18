# v0.7.43 performance investigation

Benchmarked using the installed Blender 5.3 Python, the same retained character
renders, a frozen v0.7.42 code copy and isolated export processes. The character
is 2048 × 2729, with 21 raster layers and a 16-bit PSD. Times below measure
assembly only: a fresh full character render was not performed. Source project
and production artwork were read only; benchmark files are under `/tmp`.

## Before and after

| Approach | Before | After | Interpretation |
|---|---|---|---|
| Stage instrumentation | No structured stage report | Total/stage time, call counts, process peak RSS; ~1.10 µs overhead per stage call | Observability, not a speed optimisation |
| Streaming flattened PNG | Warm ~7.55 s; ~2310 MiB peak RSS | Warm ~7.53 s; ~605 MiB | Essentially unchanged warm time; ~74% lower memory |
| Conservative raster cropping, character with RLE | 117.8 s; 722.1 MB | 125.7 s; 709.7 MB | No demonstrated speed benefit on this character; many transparent pixels contain hidden RGB |
| Conservative cropping, controlled sparse fixture | 1.808 s; 2.711 MB | 0.354 s; 2.374 MB | ~5.1× faster on five sparse 1024 × 768 layers with genuinely empty RGBA borders |
| Shared GP preparation, three compatible outputs | 0.340 s; 3 snapshots; 55.57 MB written | 0.225 s; 1 snapshot; 18.52 MB written | ~34% less preparation time, ~67% fewer snapshot bytes |
| Lossless compression, same cropped character | RLE: 125.7 s; 709.7 MB | ZIP: 56.6 s; 71.56 MB | ZIP wins substantially; timings include decoding and saving |
| Entire PSD, warm v0.7.42 vs final Automatic | 117.8 s; 722.1 MB; 1813 MiB | 56.6 s; 71.56 MB; 1106 MiB | ~2.08× faster, ~90.1% smaller, ~39% less peak memory |
| SVG assembly | 0.94 s | 0.98 s | Essentially unchanged; byte-identical output |

The initial full-run PSD took 201.7 s and its PNG took 54.1 s. Separate early
PNG processes took 70.0 s and 41.4 s. Later warmed baseline PNG runs took
7.548–7.554 s; streaming runs took 7.319–7.533 s. These large cold/pressure
variations are why headline comparisons use warmed runs instead of attributing
all observed change to code. This is a practical single-machine benchmark,
not a statistical guarantee for other projects or computers.

The crop stage itself took about 0.067 s across the final character's 21 layers.
The RLE crop-only run did not establish an end-to-end speed gain, so none is
claimed. A fast edge check avoids full-array scans when the outer bounds are
already occupied. Cropping is conservative: RGB hidden under zero alpha,
negative/HDR values and the smallest nonzero alpha are preserved. Only wholly
zero RGBA borders are removed. Raster PSD layer offsets and alpha-mask bounds
move together. SVG and still-image geometry are unchanged.

## Compression choices

RLE, ZIP, ZIP with Prediction and RAW were benchmarked on sparse and noisy
8/16/32-bit fixtures and reopened with exact layer-pixel comparisons. The
character's ZIP-with-prediction result was 57.49 s / 65.21 MB; plain ZIP was
56.64 s / 71.56 MB in the final run. Plain ZIP is Automatic because it gives
strong gains without the additional predictor stage; other codecs remain
selectable, including legacy RLE. Preview and raster-channel compression are
set through the bundled writer's existing public API. Native shape/type records
are preserved; their compatibility previews retain the established writer path.
Old jobs without the new field still default to RLE until Retry refreshes them.

In v0.7.44 the document preview returned to RLE because Dolphin/KDE rejects ZIP
at that level. Raster channels retain ZIP and the optimisation. The same
character is 75.47 MB with the portable preview, versus 71.56 MB with the
ZIP-only preview; the v0.7.43 timing above describes the earlier ZIP preview.
This compatibility correction was exercised through KDE's installed PSD reader.

## Validation

- 158 unit/regression tests and 17 compatibility/manual tests passed.
- Native Blender UI/chime test passed with the consolidated Diagnostics control;
  saved report data and legacy settings remain available. Sound tests used the
  silent Null device.
- Native render/disabled-layer test passed for six destinations, including
  PSD8/16/32, SVG, PNG and OCA. It checks real render flags, cached-image reuse,
  and the production dispatch manifest's preparation/render timing fields.
- Native shared-vector test confirms three compatible destinations reference one
  source, different flat-material settings remain separate, and source
  resolution is idempotent. Real-project source checksums were unchanged.
- All 21 raster layer arrays, their names/kinds/opacity/blend/visibility/colour
  labels, ICC profile and stored composite preview match the baseline exactly
  after reopening the final PSD and restoring cropped layers to canvas space.
- Sparse 8-bit crop fixtures also compare alpha masks and placement.
- Final PNG and SVG files are byte-for-byte identical to their baseline outputs.
- Photoshop and PhotoCraft GUI validation was unavailable. Compression choices
  were verified through actual exported files, the bundled reader, and native
  Blender fixtures; inspect the first file in the target editor after upgrading.

The new timings show PNG16 decoding now accounts for about 41.3 of the final
PSD's 56.6 seconds. No replacement decoder was attempted in this pass.

## Diagnostics and files

One collapsed **Diagnostics** disclosure contains Input Sync, Export Notices,
Performance and Collections. Existing reports are retained; old individual
expansion properties are kept for loading older projects. Dynamic line wrapping
uses the sidebar width. Export controls and Check Export Status remain accessible.

Changed: `__init__.py`, `psd_worker.py`, `psd_vectors.py`, `svg_hybrid.py`, README,
and native UI/disabled-render tests. Added `export_performance.py`,
`raster_bounds.py`, fidelity tests and a native shared-source test. Detailed
portable numerical evidence is in `performance-v0743.json`.

Raw benchmark scripts, frozen baseline, full logs, output documents, checksums,
backups and diffs are in `/tmp/compio-performance-46urt0jh`. That temporary
folder will not survive all OS cleanup/reboot policies. `before-v0742.tar.gz`
is the rollback backup. Production project outputs were not replaced.

The next proposed feature is documented in `NEXT_VECTOR_FEATURES.md`: preserve
shared GP data as Inkscape clones, and investigate compact embedded/linked
Smart Objects. Sharing preparation in this release does not implement either.
