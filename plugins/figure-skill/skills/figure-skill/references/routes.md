# Route selection

## Data plot

Choose for measured or computed results: performance curves, bar charts, ablations, scalability, robustness, distributions, resource use, and statistical comparisons.

- Primary implementation: Python with Matplotlib/Seaborn or the project's existing plotting stack.
- Require: source file mapping, exact filters/transforms, units, aggregation method, uncertainty definition, and deterministic seed when sampling.
- Useful upstream pattern: CS Experiment Figure Studio.
- Reject generated pixels as a substitute for data-driven marks.
- Current deterministic backend: `scripts/backends/matplotlib_backend.py` for bar, multi-series line, scatter, and long-form Heatmap plots with per-mark/per-cell provenance and optional symmetric absolute error columns.

## Illustration

Choose for model architecture, method pipeline, mechanism, experimental setup schematic, graphical abstract, or conceptual overview.

- PaperBanana pattern: retrieve references, plan, style, visualize, critique, then iterate.
- Happy Figure pattern: compile research content into a model-aware structured prompt; it does not itself create the final figure.
- Prefer short visible labels and keep detailed explanation in the caption.
- Record every scientific entity and arrow in the brief before rendering.
- Current deterministic backend: `scripts/backends/svg_diagram_backend.py` for editable architecture and workflow diagrams.

## Raster illustration

Choose only for explicitly generated conceptual imagery: photorealistic scientific concepts, 3D-style scenes, graphical abstracts, or cover art.

- Mark the evidence role as `illustrative` and require human review.
- Record entities, relationships, visible labels, forbidden content, model, endpoint, prompt hash, and output hash.
- Use the member's `FIGURE_IMAGE_API_KEY`; do not persist or log it.
- Do not use generated imagery as microscopy, medical, field, instrument, or quantitative evidence.
- Current backend: `scripts/adapters/raster_illustration_adapter.py` using an OpenAI-compatible Images protocol.

## Edit

Choose when an existing figure is the authoritative starting point.

- AutoFigure-Edit pattern: segment a raster draft, reconstruct an SVG, edit, and export.
- draw.io pattern: preserve explicit shapes, connectors, grouping, and text for manual revision.
- For an existing SVG, edit native elements directly when practical instead of rasterizing and regenerating.

## Composite

Choose for multi-panel figures that combine plots and diagrams.

1. Generate quantitative panels independently from source data.
2. Generate or draw explanatory panels independently.
3. Assemble panels using a vector or layout tool.
4. Apply a shared type scale, panel labels, spacing system, and color semantics.
5. Preserve a provenance entry for every panel.

Use `scripts/assemble_figure.py` to preserve panel SVGs in the final SVG and export review PDF/PNG files through a detected local Edge/Chrome browser.

## Hybrid composite

Choose when raster and vector representations intentionally coexist inside one Figure. Define a role-by-role `representation_contract`, compose a hybrid SVG with `data-role` attributes, and run `scripts/audit_hybrid_svg.py`. Read [hybrid-representation.md](hybrid-representation.md) for the contract and hash-audit workflow.

## Backend decision order

1. Existing project-native plotting or vector source.
2. Deterministic plotting/drawing code.
3. draw.io or native SVG construction.
4. Specialized illustration pipeline.
5. Raster image generation as a draft or asset source.
