# OCA frame-sequence foundation, v0.7.50

Use the existing `.OCA` destination and Blender **Render Animation**. Render
Image remains a still export. No new publishing UI or public manifest format
was added. The existing internal jobs.json retains per-frame cache references
for OCA retry; published output is standard OCA plus relative PNG/EXR assets.

OCA preparation runs at render_init so companion File Output nodes exist before
Blender evaluates the first compositor frame. Those nodes remain through the
animation. render_post records frame references, and render_complete publishes
once. Exact numeric frame matching prevents choosing another cached frame,
including negative frame numbers. Mixed PSD/PSB/SVG jobs refresh their deferred
sources for the final frame. Non-OCA render handling remains unchanged.

The sequence writer reuses the existing still OCA conversion for every frame,
including hierarchy, directives, blending, precision and flattening. It combines
standard frame arrays, marks animated paint layers, uses frame-unit durations
and an exclusive endTime, and checks completeness and stable layer structure
before replacing prior output. Frame Step is represented as exposure holds.
No deduplication, transform extraction, font conversion or rigging is included.

References inspected: the supplied OCA-master.zip specs under the character's
CutOut/ExampleTestFiles/1.3.0 folder; Bluik, OCO, DuBLF and DuPYF archive READMEs
under Repositories/Codeberg/Bluik. These libraries were not installed or changed.
OCO/Rigby2D integration remains a separate future extension.

Validation: 195 unit tests passed. A real Blender 5.3 CPU render of three frames
and two layers produced six OCA images with changing pixels and valid alpha,
correct fps, hierarchy, exposure numbers and relative paths. Simultaneous PSD
and SVG exports completed for the final frame and reopened in their readers.
Krita's installed OCA library loaded and sanitized the sequence successfully.
Full Krita GUI import was not verified: this execution environment lacks a
working headless Qt platform for that application.

Changes: __init__.py capture hooks/cache lifecycle and labels; psd_worker.py
exact frame selection and sequence routing; oca_sequence.py conversion wrapper;
version declarations, existing manual and tests. Pre-change backup and logs:
`/tmp/asset-parts-oca-animation-24d3o_lh`. The three-frame sample is packaged as
`OCA-three-frame-test.zip` there. No production project or artwork was modified.
