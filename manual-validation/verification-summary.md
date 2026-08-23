# Figure Skill - Verification Summary

Date: 2026-07-31

## Result

Overall status: PASS

Release candidate: `manual-validation/release-candidate`

Edit release candidate: `manual-validation/edit-release-candidate`

## Route tests

| Case | Input | Expected | Actual | Result |
|---|---|---|---|---|
| Illustration | methods.txt | illustration | illustration | PASS |
| Data plot | results.csv | data-plot | data-plot | PASS |
| Edit | existing.svg plus revision request | edit | edit | PASS |
| Composite | methods.txt plus results.csv | composite | composite | PASS |

## Artifact tests

- Generated an editable Python source and draw.io source.
- Exported SVG, PDF, and PNG from the same authoritative CSV input.
- Confirmed the PDF contains one page and extractable figure text.
- Rendered the PDF independently with Poppler and visually compared it with the PNG export.
- Confirmed that labels, arrows, panels, values, and spacing are legible with no clipping or overlap.
- Confirmed that 0.81, 0.87, 24.0 ms, and 18.5 ms match results.csv.

## QA tests

| Scenario | Expected | Actual | Result |
|---|---|---|---|
| Complete editable/vector/preview output | pass | pass | PASS |
| SVG without PNG preview | warn | warn | PASS |
| Raster-only PNG | fail | fail | PASS |

## Environment note

The bundled `pdfinfo.cmd` and `pdftoppm.cmd` wrappers pointed to a missing internal path. Verification used the actual bundled Poppler executables under `dependencies/native/poppler/Library/bin`; PDF rendering succeeded.

## Deterministic MVP extension

- Added CSV, TSV, JSON, JSONL, XLSX, DOCX, and PDF-aware input analysis.
- Added executable illustration and data panel plans with a human approval gate.
- Added bar, line, and scatter rendering with per-mark source row/column provenance.
- Added editable SVG and draw.io diagram sources.
- Added multi-panel SVG assembly plus Edge/Chrome PDF and PNG export.
- Added source-hash and plotted-value verification in QA.
- Added safe handoffs for Happy Figure, PaperBanana, and AutoFigure-Edit.
- Added an approval-gated native SVG edit backend with exact text/attribute operations, retained original source, hashes, and per-operation provenance.
- Final release-candidate QA status: PASS.
- Edit release-candidate QA status: PASS; PNG visually inspected after replacing exactly one `Classifier` label with `Retrieval`.
- Automated test result: 24 tests passed.
- Final PDF: one page; independently rendered with Poppler and visually matched against the direct PNG export.

## External backend closure

- Pinned PaperBanana at commit `836455537e863b5a2f40dace487a782c0bc5ef94` and AutoFigure-Edit at `16f3749e9d512bdf7b7b55c162307bc289750b7a`.
- Added offline AST validation of all adapter-required upstream CLI flags; manifests record the upstream commit and entrypoint SHA-256.
- Added raster source selection directly from an `edit` panel for AutoFigure-Edit.
- Built two non-inheriting virtual environments; both `pip check` and upstream `--help` smoke tests passed.
- Generated real dry-run manifests using the pinned repositories and matching external Python runtimes.
- Verified four negative safety cases: each backend rejects missing `--allow-network`, and each rejects missing credentials before invoking the upstream model workflow.
- No paid or credentialed model request was made.
- Audited every external candidate from the original team list: selected the author PaperBanana implementation, documented the unofficial `llmsresearch` alternative, retained Happy Figure as a non-vendored noncommercial handoff, prohibited automatic hosted-site uploads, and confirmed the `BROOO/cs-experiment-figure-studio` URL is currently unavailable.
- Repaired a stale `openai-bundled` marketplace path from an old Codex AppX version, installed and enabled the official `drawio@drawio` plugin version 1.1.0, and added an idempotent setup script.
- Validated a native `.drawio` artifact with 3 vertices, 2 edges, complete edge geometry, valid XML, and no XML comments. draw.io Desktop is not installed, so desktop-only layout/export is intentionally unavailable while native editable delivery remains functional.
- Configured an OpenAI-compatible relay for AutoFigure-Edit without recording the credential, selected `claude-sonnet-4-6` after authenticated multimodal compatibility probes, added explicit relay base-URL/model support to the adapter, and verified a secret-free request manifest.
- Replaced the paid-SAM requirement with an explicit `none` backend that enters AutoFigure's pure-SVG fallback. A complete relay-only run produced a valid SVG with no embedded raster, preserved labels and arrow, and passed visual inspection; automated coverage increased to 26 tests.
- Public acceptance on 2026-08-20 used UCI Iris, the official scikit-learn Iris pipeline, and Wikimedia Commons CC0/public-domain diagrams. All four deterministic routes passed. Artificial-neuron pure SVG reconstruction passed; the more complex neural-network reconstruction received a visual warning. Scatter-axis selection, scatter titles, and embedded-raster false-success handling were fixed. Final automated coverage: 29 tests passed.
