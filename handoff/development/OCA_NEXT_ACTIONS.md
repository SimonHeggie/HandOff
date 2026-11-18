# HandOff — next OCA tasks (ranked, avoiding reimplementation)

Grounded in the uploaded source snapshot and the official OCA 1.3.0 specification:
- https://oca.rxlab.guide/specs/folder-structure.html
- https://oca.rxlab.guide/specs/root.html
- https://oca.rxlab.guide/specs/layer.html
- https://oca.rxlab.guide/specs/frame.html
- https://oca.rxlab.guide/specs/meta.html
- https://oca.rxlab.guide/specs/layer-types.html
- https://oca.rxlab.guide/roadmap.html

**Already present — regression-check, DO NOT implement again:** seven OCA export controls; source Collection hierarchy, directives and blends; alpha trim/scale/padding; 8/16-bit PNG and 32-bit EXR; three-frame OCA sequences; GP vector SVG and optional raster fallback; numeric filename-prefix removal; deterministic IDs; OCA group/paint labels; no-render retry; companion Spine JSON/template. These are evidenced in source and the uploaded local validation report; the current machine has not rerun Blender.

## Pass A — can be attempted with existing Hatshepsut scene or a generated export

1. **Canonical OCA folder layout** — current writer publishes sibling `Character.oca` JSON + `Character/` assets; official spec defines a `.oca/` folder containing the one root data file and assets. Add or offer standard-folder output and verify importer behaviour. Retain legacy layout as needed for current consumers. This is a structural issue, not a request to redo layer ordering.
2. **Unique layer names in JSON** — specification says layer `name` is unique *within the document*. Current filename collision handling (`Eyes`, `Eyes-2`, `Eyes-3`) does not necessarily change duplicate JSON layer names. Distinguish exported names as required while maintaining scene identity and stacking.
3. **OCA document validator** — check spec version, unique layer/frame IDs, unique layer names, supported `type`/`fileType`, valid relative asset paths, exact pixel dimensions, frame positions, references and empty-frame rules. Emit actionable reasons without modifying the project.
4. **Reference-layer semantics** — verify `.ref` maps to native `reference=true` and remains non-rendering in receiving applications, not merely `visible=false`.
5. **Group pass-through/blend fidelity** — use existing nested groups to compare appearance of OCA's `passThrough` + `blendingMode` against Blender's native composite. Investigate *only* actual discrepancies.
6. **Preserved SVG/PNG alternatives** — test that a strict importer ignores `meta.handoff` when unsupported, SVG remains visible once (not twice), and fallback assets remain accessible to supported consumers. This convention is an extension metadata convention, not an official alternate-asset field.
7. **Precise position/dimensions after crop** — regression test existing arm, shine and overlapping groups, including negative/out-of-bounds artwork. Do not rebuild trim/scale/padding unless output is wrong.
8. **Stable IDs under layer reordering** — current UUIDs contain a position/index, so investigate whether changing compositor ordering changes identity despite the same source. Fix only with a reliable source-level identifier and migration tests.
9. **Colour label parity** — check actual numeric OCA labels against the official label values and receiving application's representation; do not touch working PSD palette code.
10. **File portability** — verify cross-platform path/name encoding, case-only collisions, Unicode, Windows reserved names and duplicate leaf paths. Keep local rendering intact.
11. **Safe interrupted exports** — inject an error between staging and publication and ensure prior `.oca` document/assets remain usable, including mixed SVG + PNG companion assets.
12. **Receiving application smoke tests** — open the same export in a current OCA reader (e.g. Bluik or OpenToonz) and check basic group/image/animation interpretation. Avoid requiring Krita OCA import; its official listed integration is export-focused.

## Pass B — simple fixtures only, where the source really supports it

13. **Separate standard metadata sidecar** — official `<document>_meta.json` can identify `exportedBy=HandOff`, exporter ID, originApp=Blender, version, optional warnings; do not put these fields in the root OCA JSON or assert user copyright/licence without input. Low risk.
14. **Frame opacity** — `frame.opacity` is standard; test genuine changing opacity on a three-frame source. Currently the still writer writes `opacity:1.0` for frames. Implement only if the evaluated Blender source provides independent frame opacity without already baking it into pixels (avoid double opacity).
15. **Layer/group opacity** — both standard, but current writer uses `opacity:1.0`. First demonstrate a source property that is not baked into rendered images, then pass it through once.
16. **Inherit alpha** — native OCA `inheritAlpha` exists and is currently hardcoded false. First create a minimal compositing fixture with demonstrable alpha inheritance; don't infer it from generic overlap.
17. **Background colour** — currently always transparent. Check whether a meaningful document background exists for each export mode, and ensure character artwork stays transparent when appropriate.
18. **Nonzero/negative frame starts, blank frames and frame-number changes** — use tiny fixtures; core three-frame export already exists. Do not add exposure holds or repeat optimisations as new features.
19. **Partial-opacity Grease Pencil SVG** — verify alpha, gradients and unsupported shader effects via rendered-vs-vector comparison; keep PNG as fidelity fallback and clearly report differences.
20. **Precision metadata** — standard `U8/U16/F16/F32`; present writer supports U8/U16/F32. `F16` is a potential optional addition only if a real need and EXR pipeline tests justify it.

## Pass C — defer until real projects need them

21. `clonelayer` references — OCA 1.3 supports them, but needs robust stable references and real repeated layer instances; otherwise preserve distinct paint/vector layers.
22. `ocalayer` nested documents — OCA 1.3 supports them, but requires recursion, portability and missing-source policy.
23. Frame exposure holds and drawing reuse — not currently a priority despite native OCA support.
24. GP-to-vector feature expansion for unsupported Blender shader effects — high effort, fall back to PNG until demanded.
25. Transform pivots/rotation/scale, masks, interpolation, loops, adjustment layers, zipped OCA — **roadmap proposals, not part of the published OCA 1.3 standard**; don't implement as standard OCA fields.

## Suggested Codex execution gate

Attempt items 1–12 against the existing Hatshepsut scene **in order of testability**, not all as speculative implementations. Use item 13 as a quick additive feature if the early passes are stable. Stop if a native Blender regression is found. Do not redo the seven controls, vector exporter, image trimming, or file-number cleanup without a reproduced failure. Record: test setup, actual outputs, pass/fail, change, re-test. Finish each small change before proceeding. Leave cloning, exposure holds and new skeletal formats aside.
