# Bundled Pillow 12.0.0 wheels

The release archive bundles these six third-party Pillow 12.0.0 wheels for CPython 3.13 across supported host platforms. The source repository omits the binaries; add them to `handoff/pillow/` before building an installable ZIP. `scripts/build_install_zip.py` validates every SHA-256 digest against `docs/pillow-wheels.json`.

```sh
python scripts/build_install_zip.py --wheels-from /path/to/pillow --output dist/handoff_install.zip
```

Wheels should be obtained from trusted package sources or extracted from a previously validated installable ZIP. This inventory does not imply compatibility with Blender versions using other Python ABI versions.
