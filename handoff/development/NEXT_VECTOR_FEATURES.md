# Shared artwork and compact Photoshop vector layers

Requested after the v0.7.43 optimisation pass; these features are not part of
v0.7.43. Sharing export preparation does not create editable linked instances.

## SVG instances

Preserve intentional Blender GP datablock sharing, including library identity.
Independent datablocks must remain independent even when their geometry matches.
A compatible object family can use a canonical editable source plus SVG `use`
references, keeping per-instance transforms and paint order. Inkscape clones
follow changes to the original; editing a clone's nodes requires selecting the
original, while position/size/rotation can remain instance-specific.

Camera-space paths currently contain evaluated object transforms. Before
sharing SVG geometry, factor out representable transforms and confirm stroke
radius, material UV mapping, modifiers and per-object materials still match.
Object-specific evaluated results may need separate definitions. Never link
unrelated artwork or discard differing modifier results to force sharing.

Tests should edit the master in a real Inkscape document, confirm all instances
update, validate mixed transforms/materials/gradients, and verify unlinking a
clone produces independent editable geometry.

## Photoshop vector-layer modes

Keep the existing native shape/type layers. Investigate optional embedded
Smart Objects and linked Smart Objects as compact alternatives: one outer layer
can preserve a complete internal vector document. An external file link is
optional; embedded content makes the PSD self-contained.

Shared Smart Object source identity could preserve instance edits across
copies, but needs verified placed-layer records and target-app round trips.
Confirm SVG payload support and the editor used for Edit Contents; a Smart
Object does not automatically expose native Photoshop shape nodes. Browser
editors such as PhotoCraft need separate support tests, particularly for links
and automatic external-file updates.

Authoritative references:
- https://inkscape-manuals.readthedocs.io/en/latest/cloning-objects.html
- https://helpx.adobe.com/photoshop/desktop/create-manage-layers/smart-objects/smart-objects-overview-and-benefits.html
- https://helpx.adobe.com/photoshop/desktop/create-manage-layers/smart-objects/edit-the-contents-of-a-smart-object.html
