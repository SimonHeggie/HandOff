# HandOff: Development Instructions

## Project

This is an existing Blender 5.3 Python add-on that exports layered documents, including PSD functionality.

The primary source entry point is `__init__.py`.

## Development rules

1. Inspect the existing codebase and understand its architecture before changing anything.
2. Preserve all existing working functionality unless a change is explicitly requested.
3. Use the actual Blender 5.3 Python API. Do not invent API methods, classes, properties or operators.
4. Verify uncertain Blender API behaviour against the installed Blender version or authoritative source code/documentation.
5. Preserve backwards compatibility with existing saved Blender project files and add-on settings whenever possible.
6. Keep export output compatible with the formats and target applications supported by the existing implementation.
7. Preserve layer hierarchy, naming, opacity, blend modes, colour management, alpha and other supported document metadata.
8. Do not silently change output formats, file naming conventions or export behaviour.
9. Prefer minimal, focused modifications instead of large architectural rewrites.
10. Do not introduce unnecessary external dependencies.
11. Back up or version-control existing files before modifying production code.
12. Test modified functionality and report any behaviour that could not be verified.
13. Do not claim that an exporter works correctly simply because the Python code passes a syntax check.
14. Do not modify unrelated add-ons or Blender configuration.

## Workflow

- First investigate the requested feature or bug.
- Explain the relevant existing implementation and propose a solution.
- Identify the files requiring modification.
- Make focused changes only within the approved scope.
- Validate Python syntax and module imports.
- Where possible, run Blender in background mode to exercise the relevant functionality.
- Test exported documents in a suitable reader or parser when available.
- Inspect any errors and repair the underlying cause rather than applying speculative workarounds.
- Provide a concise changelog listing modified files, functionality added and tests performed.

## Important

This is an active production tool.

Preserving working behaviour is more important than rewriting the code to look cleaner.

Never replace established functionality with an untested approximation.
