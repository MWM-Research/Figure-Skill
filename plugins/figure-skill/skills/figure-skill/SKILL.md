---
name: figure-skill
description: Route research manuscripts, methods, captions, reference figures, and experiment outputs into reproducible scientific illustration, data-plot, figure-editing, and composite workflows. Use when Codex needs to plan, generate, edit, or quality-check publication figures; create architecture, mechanism, workflow, graphical-abstract, ablation, robustness, or multi-panel figures; or coordinate tools such as PaperBanana, AutoFigure-Edit, Matplotlib, draw.io, and image generation while preserving scientific evidence boundaries.
---

# Figure Skill

Turn heterogeneous research inputs into editable, reviewable figures. Treat scientific correctness and provenance as hard constraints.

## Workflow

1. Create a plan and stop for review:

   ```powershell
   python scripts/run_workflow.py `
     --input <input-root> `
     --brief "<figure intent>" `
     --output <output-root> `
     --stop-after-plan
   ```

   Use `--brief-file <utf8.txt>` instead of `--brief` when shell encoding is uncertain.
   For an SVG edit, pass `--edit-operations <operations.json>`. If operations are absent, the planner intentionally creates an unresolved question and prevents approval.

2. Inspect `inventory.json` and `figure-plan.json`. Resolve every `open_questions` item and verify inferred entities, arrows, columns, units, and chart forms against authoritative sources. Edit the plan directly when needed.

3. Resume only after explicit human approval:

   ```powershell
   python scripts/run_workflow.py `
     --plan <output-root>/figure-plan.json `
     --output <output-root> `
     --approve-plan
   ```

4. Confirm that the inferred route matches the evidence:
   - Use `data-plot` for CSV, TSV, JSON measurements, logs, metrics, statistics, and quantitative comparisons.
   - Use `illustration` for methods, architectures, mechanisms, workflows, and graphical abstracts without quantitative claims.
   - Use `edit` when the primary job is revising an existing SVG, draw.io file, or supplied figure.
   - Use `composite` when a figure combines evidence-backed plots with explanatory illustration panels.
   - Read [references/routes.md](references/routes.md) when choosing or combining backends.

5. Keep the generated structure intact:
   - `panels/`: editable panel SVGs and panel-specific exports
   - `sources/`: deterministic plotting source and render recipe
   - `final/`: assembled SVG, PDF, and PNG
   - `provenance/`: source hashes, row/column mappings, and inferred diagram relations
   - `reports/qa-report.json`: structural and evidence QA

6. Use `scripts/inventory_inputs.py`, `scripts/plan_figure.py`, backend scripts, or `scripts/assemble_figure.py` separately only when debugging or deliberately running one stage.

7. Re-run QA after manual edits:

   ```powershell
   python scripts/qa_figure.py <output-file-or-directory> --plan figure-plan.json --output qa-report.json
   ```

8. Visually inspect `final/figure.png` and an independently rendered `final/figure.pdf` at publication size. Read [references/qa-checklist.md](references/qa-checklist.md) before declaring completion. Iterate until structural, provenance, and visual QA pass.

## Deterministic backends

- Use `scripts/backends/matplotlib_backend.py` for bar, line, and scatter panels. It rejects duplicate categories without an explicit aggregation and records every plotted mark with source row and column.
- Use `scripts/backends/svg_diagram_backend.py` for 2-10 node architecture/workflow diagrams with explicit edges.
- Use `scripts/backends/native_edit_backend.py` only for reviewed SVG `replace_text` and allowlisted `set_attribute` operations. It requires exact selectors, retains the original, and records source/output hashes plus each applied operation.
- Use `scripts/assemble_figure.py` for single, horizontal, vertical, or 2-column grid assembly. It preserves SVG elements and uses local Edge/Chrome for PDF/PNG export.
- Install `requirements.txt` into the selected Python environment before rendering.
- Run `scripts/check_environment.py` to verify Python, Matplotlib, openpyxl, local browser export, optional repositories, and credential presence without printing secret values.

## Non-negotiable boundaries

- Never invent data points, axes, uncertainty, sample sizes, p-values, significance marks, baselines, or measured effects.
- Never replace microscopy, medical imagery, field photographs, or instrument evidence with generated imagery without conspicuous draft labeling and user approval.
- Do not copy scientific content from a reference figure. Transfer only layout, typography, color logic, line treatment, and visual hierarchy.
- Preserve units, conditions, method names, group names, and directionality exactly as supported by the source.
- Flag ambiguous arrows, causal claims, missing data definitions, and conflicting captions before finalization.
- Do not describe a raster-only artifact as editable or publication-ready.

## Tool behavior

- Treat PaperBanana, AutoFigure-Edit, Happy Figure, draw.io MCP, and image-generation services as optional backends. Detect availability before promising their use.
- The deterministic MVP does not call these external backends automatically; keep their future adapters isolated from the core evidence pipeline.
- Read [references/external-backends.md](references/external-backends.md) before preparing or executing draw.io, Happy Figure, PaperBanana, or AutoFigure-Edit requests.
- Read [references/backend-selection.md](references/backend-selection.md) before adding or replacing an external backend; it records the reviewed alternatives, licenses, and unavailable links from the team list.
- From the project checkout, run `scripts/setup_external_backends.ps1` to create fixed-version, isolated PaperBanana and AutoFigure-Edit runtimes. Execute each adapter with its matching external Python interpreter.
- Do not install, authenticate, upload unpublished material, or call paid services without user authorization.
- Keep API keys outside plans, prompts, logs, and generated artifacts.
- When no specialized backend is available, still deliver a figure brief, panel plan, deterministic plotting code where applicable, and an explicit handoff.
