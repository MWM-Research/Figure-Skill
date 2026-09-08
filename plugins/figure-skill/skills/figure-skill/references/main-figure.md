# Generative scientific main figures

Use this explicit mode for near-paper-ready method overviews, mechanisms and mixed figures with real data. The agent performs scientific reading, tool calls and visual review; the CLI validates, tracks versions and composes editable artifacts. It does not generate images or certify scientific truth by itself. Preserve the user's source-supported claim and exact names.

## Design and generation

Read sources and prepare `design.json`. Required fields are `claim`, `caption`, `reading_order`, `visual_focus`, `forbidden_content`, `open_questions`, `sources`, `requirements`, `panels`, `nodes`, `edges`. A source contains `id`, readable `path` and precise `location`; a requirement has `id`, `text`, `source_ids`. Attach `requirement_ids` to each panel/node/edge. Use `box_mm: [x,y,width,height]` for placement, unique IDs, exact node `label`, and edge `from`, `to`, `meaning`. Nodes may use newline-separated labels. Panels have `kind: concept|data`, an editable panel `label`, and data panels contain an existing deterministic `plot` spec, including `source_files`, columns and any calculation/axis settings. The acceptance preparation script provides three executable examples.

Canvas defaults: `width_mm: 180`, `height_mm: 100`, `min_font_pt: 8`, `min_effective_dpi: 300`. Follow an existing target page size; avoid decoration that competes with the contribution. Sources are hash-bound at prepare. Any later content change requires a fresh run; geometric placement changes use a new composition version.

Run `figure.py main-figure prepare --brief <design.json> --output <run>` and then `figure.py main-figure prepare --output <run>` to reserve two candidates. Each writes a prompt under `requests/`. Refine it to communicate the actual visual design, retain the exact submitted prompt, and call the current built-in image tool via the installed imagegen skill. The tool's actual local artifact path is authoritative. Never request credentials or fall back to a paid API automatically.

Initial candidates may include short text/arrows to explore full composition. When the design is already clear, directly requesting a clean conceptual layer is allowed. Data-panel regions must remain empty or use registered deterministic previews only as references; generated data marks never become final evidence. Source-specific relationships and scientific correctness take precedence over visual scores.

Reserve every further call BEFORE execution: `prepare --kind revision|cleanup --parent <candidate-id> --instruction <preserve/change instruction> --output <run>`. Maximum: two candidates, two revisions and one cleanup, including failed calls. Record failures with `import --id <id> --failed --output <run>`. Do not create a new run merely to bypass the call budget. If tools are unavailable, retain the awaiting-generation run and explain the limitation.

## Candidate import and selection

Visually inspect every returned image, including all areas after an edit. Write an assessment with:

```json
{
  "image_sha256": "actual image hash",
  "reviewer": "agent reviewer identity",
  "selection_reason": "specific comparison with the other candidate",
  "score": 4,
  "assertions": {"requirement-id": {"status": "pass", "evidence": "visible source-consistent observation"}},
  "visual": {
    "focus": {"status": "pass", "evidence": "observation"},
    "reading_order": {"status": "pass", "evidence": "observation"},
    "density": {"status": "pass", "evidence": "observation"},
    "legibility": {"status": "pass", "evidence": "observation"}
  },
  "clean_background": true,
  "clean_background_evidence": "No text or major arrows remain in the conceptual layer",
  "data_regions_empty": true,
  "data_regions_empty_evidence": "No generated data marks occupy final data-panel boxes",
  "references": []
}
```

All requirement IDs must be assessed; `fail` or `uncertain` blocks selection. Scores rank passing candidates only; use the same 1–5 scale for both. Reference entries, if any, contain `path`, `sha256`, and `role: style|edit-target|data-preview`; references are copied and hash-bound. These are agent observations, not independent model certifications. Do not populate passing evidence without inspecting the image.

Import with `figure.py main-figure import --id candidate-1 --image <actual.png> --prompt <submitted.txt> --assessment <assessment.json> --output <run>`. Files are copied non-destructively; a candidate ID is immutable. A cleanup must preserve scientific structure and remove duplicate labels/arrows; do not hide failed cleanup with opaque patches.

## Editable composition

Create `layout.json` with `image_sha256`, optional `background_box_mm`, and complete `panels` and `nodes` maps from IDs to boxes in mm. Layout adjusts geometry only, not labels or scientific edges. Place labels in clear regions and check all major arrows for crossings. Include instruction inputs explicitly when required by the method. Preserve generated image aspect ratio and native resolution; upsampling does not satisfy DPI checks.

Run `figure.py main-figure compose --layout <layout.json> --output <run>`. This auto-selects the highest ranked passing candidate; `--candidate` may select another passing candidate with recorded reasoning. Composition requires a reviewed clean background and empty data regions. The result retains PNG pixels only for conceptual artwork; labels, arrows, panel IDs and plots are SVG elements. Existing Matplotlib plots are rerendered at panel physical size with isolated input snapshots and provenance. Caption, source mapping, plotting code and all composition hashes are retained under `compositions/vN/`.

## Export and review

Run `figure.py main-figure export --output <run>`. SVG is editable; PDF is exported at the requested physical size; PNG is separately rendered at 300 DPI. Inspect PNG and an independently rasterized PDF at paper size. Check source-correct content, exact labels, directions, duplicates, clipping, actual font sizes and caption consistency. Do not use pixel similarity as a quality score across stochastic generations.

Record a delivery review with `artifact_hashes` copied from `reports/delivery.json`, `reviewer`, and `checks` containing exactly: `scientific-content`, `exact-labels`, `arrow-directions`, `no-duplicate-labels`, `no-clipping`, `font-size`, `caption-consistency`, `pdf-render-inspected`, `paper-size-legibility`. Each check needs `status: pass` and specific evidence. Re-run `export --review <review.json> --output <run>` to reach `awaiting-user-review`. Failed or pending checks mean `needs-revision`. Existing exports are not silently overwritten, and changed artifacts invalidate review. Keep old composition versions during repairs.

Only after the user confirms the actual current image, pass `--human-approval <approval.json>` alongside the passing review. Approval contains exact `artifact_hashes`, `decision: approved`, `reviewer`, and the user's explicit `user_confirmation`. Never infer this from automatic QA. `complete` requires this final decision; otherwise deliver a clearly identified final candidate without repeatedly asking for intermediate permission.

CLI exit codes: 0 for successful stage operations or completed delivery, 2 for a pending workflow state, 1 for validation/execution failure. `--svg-only` is an offline technical test path and cannot complete delivery. Unknown tool model metadata stays null. No generation tool access is required to run offline tests.
