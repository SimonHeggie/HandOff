# Worker startup and short status — v0.7.45

The v0.7.44 change added imports of `runtime_paths` and `branding` before
`psd_worker.py` established its own Python search path. Blender's `--python`
launcher does not automatically add the script directory to `sys.path`.
Consequently conversion stopped before it could write `result.json`.

The worker now establishes its root and vendor paths before sibling imports.
The frontend shows **Exporting assets…** during conversion. If the process
stops without a valid result, it shows **Export failed - Retry available**,
clears stale timing details and puts the exit code and actual conversion/retry
log location inside Diagnostics. Previous result files are invalidated before a
new launch. The completion chime remains success-only; an import failure never
reaches the success notification.

The worker starts with `-noaudio`: only the Blender UI needs to play a chime.
This avoids opening an unnecessary audio device in a conversion subprocess.

The new default cache folder is `asset-parts`. History, retry and cleanup still
recognise the previous `layered-document-export` and `blend-psd-tools` roots.
Existing saved paths and override environment variables remain valid.

Modified production files: `psd_worker.py`, `__init__.py`, `runtime_paths.py`,
`branding.py`. Tests: `test_runtime_paths.py`, `test_blender_reload.py`, the new
`test_worker_startup.py` and `development/test_worker_startup_blender.py`.
README and generated manual versions were updated.

Validation:

- 174 unit tests and 17 compatibility/manual tests pass.
- The real worker executes in isolated Python (`-I`) from an unrelated directory
  and completes PSD, SVG and PNG exports, without preloading add-on helpers.
- Native Blender launches the production child command from `/tmp` with no
  `PYTHONPATH`. The child produces all three documents and a successful report;
  PSD pixels, PNG pixels and SVG structure are independently checked.
- The installed Blender can hang during PulseAudio shutdown inside this tool
  sandbox after writing its successful result. The fixture explicitly reports
  that limitation, terminates only its completed child, and simulates process
  completion for monitor/chime callback tests. Normal desktop process exit was
  not verified in this sandbox; it is not treated as a successful exit test.
- Native monitor tests verify the running label, successful notification,
  failure-without-report label, retry log location and clearing stale details.
- The native chime fixture verifies zero-volume guards, saved mute settings and
  linear gain through a Null device, without playing through speakers.
- The actual retained character job completed all four destinations (PSD, PNG,
  SVG and fonts) in the private recovery copy. KDE read the recovered PSD
  thumbnail, the PNG verified, and the SVG retained four ShineSprite clones.

Audit and immutable pre-change backups:
`/tmp/asset-parts-startup-7ay1msli/`.
The latest failed character job was copied into its `recovery` directory for
conversion checks, with private output destinations and source snapshot. No
project file, original cached source or production destination was changed.
