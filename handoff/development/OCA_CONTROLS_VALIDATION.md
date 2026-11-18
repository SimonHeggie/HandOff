# OCA controls: implementation and validation

The existing working `blend_psd_tools` package was the baseline. The neighbouring
`handoff` package, repositories and releases were not used as replacement code or
modified. No version bump was made. Original modified files are backed up at
`.backups/oca-controls-tijoaen9`; `baseline-sha256.json` records the original
Python source hashes.

## Changes

- `__init__.py`: seven destination-local properties and controls; capture options,
  source visibility and explicit background designation; refresh current options
  for cached retries. The stable `trim_empty_pixels` setting name is retained.
- `psd_worker.py`: OCA-only eligibility filtering, alpha crop/scale/padding,
  floating-point centre coordinates, visibility and blank frames, companions.
  Existing document hierarchy, naming, directives, blend promotion and label
  values are retained.
- `oca_sequence.py`: every frame receives current parent destination options;
  captured frame number, pixels and precision stay intact. Companions are written
  once for the completed sequence, before publishing the staged assets.
- New `oca_controls.py`, `oca_images.py`, `oca_companions.py`: isolated OCA policy,
  image processing and minimal artwork companions. No new dependency.
- Regression tests and [user documentation](../manual/OCA_CONTROLS.md), linked
  from the existing text manual.

The baseline OCA writer copied full document-sized images and used document
centres. It did not physically trim image alpha. Animation conversion also used
captured frame-job settings without explicitly giving current destination
settings precedence. These two paths are now covered independently: image bytes
are cropped and retries override every frame snapshot's publishing options.

## Verified

The final full Python suite passes **207 tests** in Blender's bundled Python
3.13 environment. See `oca-controls-results/full-unit-final.log`.

Real Blender **5.3.0 Beta**, hash `2ebd15112ac6`, CPU Cycles renders exercise the
production render handlers, compositor File Output nodes, cache capture,
conversion and retry functions. Fixtures intercept only asynchronous worker
launch, then run the actual conversion on the resulting job data.

1. Three animation frames, four isolated View Layers, changing bounds/motion and
   an actually transparent middle frame. An actual viewport-hidden Collection
   still produces nonempty cached pixels, retained with OCA visibility off.
2. All **18 combinations** of trim on/off, scale 50/100/200%, padding 0/1/4.
   Physical image dimensions, document size and frame centres checked against
   actual native cache alpha bounds. Trimmed/untrimmed composites are pixel
   identical at 100%. Rounded dimensions and exact centres are also checked for
   odd sizes/noninteger scaling; no claim of identical interpolation at other
   scales.
3. Current UI retry values override deliberately stale animation-frame options,
   without rerendering. Layer order, hierarchy, visibility, blend and existing
   numeric label values stay stable.
4. Hidden groups and descendants omitted when requested. Explicitly marked
   background omitted, while the unmarked bottommost `Combined` remains.
   Reference directives remain hidden and can be omitted with hidden layers.
5. Spine JSON attachments use existing images/coordinates and correct draw
   order. Hidden slots stay transparent and blank frames detach artwork.
   Template PNG contains visible art and does not reveal native hidden pixels.
   Turning both companion controls off removes their previous generated files.
6. Separate native Save as Render on/off caches under AgX show different RGB
   with identical alpha, cropped dimensions and positions.
7. Another actual odd-sized native render tests **18 combinations** across
   16-bit PNG / 32-bit EXR, scale 50/100/200 and padding 0/1/4. At 100%, crop
   interiors preserve source 16-bit samples exactly and EXR samples within
   `1e-6`. Native sub-8-bit channel detail and HDR values greater than one remain.
   Companion PNG previews do not replace floating-point OCA assets.
8. The reported large regression is reproduced as a 1536 x 2048 source with
   hidden RGB outside its occupied alpha: trim with padding zero physically
   writes **1164 x 696**, centre `[655, 845]`.
9. Existing three-frame animation test exports/reopens final-frame PSD with
   `psd-tools`, parses SVG, and checks native OCA assets/fps/order/exposures.
   PSD/PSB and SVG worker function bodies are unchanged (scope-check.json).
10. The installed Krita OCA reader library loads and sanitizes four generated
    documents (8/16/32-bit and animation) without modifying frame metadata;
    referenced assets exist. See `oca-controls-results/krita-reader.log`.

Machine-readable native evidence is under:

- `oca-controls-results/reproduction/controls/native-results.json`
- `oca-controls-results/reproduction/precision/precision-results.json`
- `oca-controls-results/reproduction/process-results.json`
- `oca-controls-results/scope-check.json`

## Reproduce

Run from the package directory:

```sh
python3 development/run_oca_controls.py \
  --blender /home/simon/.Applications/Blender/beta/blender/blender
```

This creates isolated Blender preferences/cache paths under the results folder,
never production preferences. Each fixture has a bounded process timeout. The
runner separately records functional assertion results and natural shutdown and
returns nonzero if either fails. It does not use `os._exit` to mask shutdown.

To repeat the Python suite using the Pillow extraction created by that runner:

```sh
LAYERED_EXPORT_CACHE="$PWD/development/oca-controls-results/reproduction/.runtime/pillow" \
  /home/simon/.Applications/Blender/beta/blender/5.3/python/bin/python3.13 -c \
  'import sys,unittest; from pillow_loader import ensure_pillow; ensure_pillow(); sys.path.insert(0,"vendor"); result=unittest.TextTestRunner().run(unittest.defaultTestLoader.discover(".",pattern="test_*.py")); sys.exit(not result.wasSuccessful())'
```

The optional installed-reader check:

```sh
python3 development/test_oca_reader.py \
  /home/simon/.Applications/Krita/squashfs-root/usr/share/krita/pykrita/OCA/oca_core \
  development/oca-controls-results/reproduction/controls/exports/Controls.oca
```

## Unverified and environment blockers

**Natural Blender process shutdown is not verified.** Functional assertions and
unregistration complete, then the installed Blender hangs with
`pa_write() failed while trying to wake up the mainloop: Operation not permitted`.
The same failure occurs with factory startup, `-noaudio`, and a print-only script
that never imports the add-on. The runner records each as `clean_shutdown=false`
and terminates its own test process after the bounded wait. Its nonzero exit is
intentional evidence of this remaining environment blocker, not a passing
shutdown test. No production audio workaround was added.

**Krita GUI import/playback/save-reopen and Spine editor import are not verified.**
Krita's installed AppRun aborts before opening a document: it cannot connect to
display `:0`, and its only available Qt platform plugin is `xcb` even when
offscreen is requested. See `oca-controls-results/krita-help.log`. Reader-library
validation is not represented as a GUI import test. No other application or
plugin was installed or reconfigured.

This validation used isolated fixtures, not the user's production blend file.
