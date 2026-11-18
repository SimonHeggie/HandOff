# Update Inputs to ViewLayers (v0.7.41)

Select a native File Output node. In the Node sidebar, open **HandOff - Additional
Exports** and press **Update Inputs to ViewLayers**. The action is explicit and
undoable; ordinary exports do not require it.

The implementation is `view_layer_sync.py`; registration, operator and panel UI
are in `__init__.py`. Native Blender 5.3 APIs are used: compositor_effects,
CompositorNodeRLayers, file_output_items, node-group interface sockets and links.
No render, project save, export, compositor activation or datablock deletion runs.

## Behavior

- Syncs all View Layers in the current scene's single compositor effect, including
  disabled layers. Render enable/pass flags stay as authored and produce warnings.
- Searches the effect and nested compositor groups for existing Render Layers
  nodes. Adds a node at the root only when none references that scene/layer.
- Existing File Output connections remain authoritative: denoising, corrections,
  masks and other processing stay connected. Native input identifiers, relative
  order, per-input formats, export destinations and paths are preserved.
- Missing connections follow the Image branch to its processed result. Existing
  file destinations are preferred over unfinished branches. Auxiliary scalar
  passes do not become image inputs. Multiple equally plausible results and
  results that mix sources require manual wiring and produce a warning.
- Unique nested groups can expose an output or input to carry the image to the
  selected File Output. Shared/linked group definitions are not given new ports.
- New inputs append at the end, preserving the authored document stack. Names
  include the current View Layer suffix, such as `Shine.add`.
- Render Layers nodes receive the parent Collection's theme swatch, inheriting
  the nearest tagged ancestor. Unresolved Collection ownership preserves the
  existing node colour and is reported; an approximate camera footprint is not
  used as proof of parent ownership. Existing nodes are never repositioned.

## Identity and deletion

Blender updates Render Layers node.layer when a View Layer is renamed, but can
retarget it to another layer when a View Layer is deleted. Current node.layer
alone is therefore insufficient to identify a deleted input.

The explicit sync gives each View Layer a durable custom-property UUID. A JSON
record on the File Output maps its stable socket identifiers to those UUIDs.
A rename updates the input without replacing it. A deleted UUID removes only its
previously managed input; the UI report and console name every removed input.
Processing nodes, Render Layers nodes, scenes, collections and output files are
never deleted. Duplicate copied UUIDs are regenerated.

The first press adopts existing inputs with an identifiable source or exact View
Layer name. Unknown inputs, scalar utility passes and additional branches remain
manual and are reported. Deletions predating the first sync cannot always be
identified honestly; those unknown inputs remain intact. Existing processing
links with missing or different traced sources are preserved with a warning.

The latest report remains under the button. Full names and warnings also print to
the system console. Undo restores the graph and bookkeeping with Blender's normal
undo mechanism. There is no automatic sync or render-time graph mutation.

## Current scope and validation

Multiple nonempty scene-effect stacks, linked scenes and effects shared by scenes
are rejected before modification. Unassigned editor groups and File Outputs in
multiple instances of the same group also require manual resolution. These cases
are deliberately deferred until the single-effect workflow is established.

`development/test_view_layer_sync_blender.py` checks the actual Blender 5.3 API:
new sources, processed endpoints, idempotence, rename/suffix propagation, deletion
retargeting, duplicate identities, name swaps, simultaneous add/delete/rename,
manual depth inputs, native input formats and identifiers, competing branches,
disabled layers, nested source/destination routing, shared groups, multiple
scene effects, Collection colours, registration, operator execution in a native
node-editor context and native Undo restoration. Background undo states are
explicitly bracketed because no interactive event loop is running.

File Output items are backed by a reallocating native C array. Retaining their
Python RNA wrappers across new/remove/move can crash this Blender build. The
implementation retains stable socket identifiers and reacquires each item before
reading or modifying it. Bulk-mutation fixtures cover this behavior.

A private read-only load of the supplied v38 project preserved all 21 existing
input connections and their order. The first sync updated `Collar` to `Collar_FG`
and `Head_Back` to `Hood_BG`. Repeated sync added nothing; renaming `Shine` to
`Shine.add`, adding a processed test layer and deleting it behaved as expected.
The source project was never saved and its SHA-256 was checked afterward.
