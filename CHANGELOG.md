# Changelog

All notable project changes are recorded here.

## 0.1.0 - 2026-08-20

### Added

- Four evidence-aware routes: `data-plot`, `illustration`, `edit`, and `composite`.
- Human approval gate through `figure-plan.json` and `open_questions`.
- CSV, TSV, JSON, JSONL, XLSX, DOCX, PDF, Markdown, and text input inspection.
- Matplotlib bar, grouped-bar, line, and scatter outputs with per-mark provenance.
- Editable SVG and native draw.io architecture diagrams.
- Native SVG exact-text and allowlisted-attribute editing with source/output hashes.
- Multi-panel SVG assembly and local Edge/Chrome PDF/PNG export.
- Structural, data, provenance, editable-source, PDF, PNG, and secret QA.
- Isolated PaperBanana and AutoFigure-Edit adapters with upstream CLI contract checks.
- OpenAI-compatible relay support and explicit no-SAM pure-SVG fallback.
- Public acceptance suite based on UCI Iris, scikit-learn, and Wikimedia Commons materials.
- Release verification and packaging scripts.
- Clean-extraction verification bootstraps an isolated project virtual environment when one is absent.

### Fixed

- Scatter plots now select two numeric columns even when categorical columns are present.
- Scatter titles now use `y vs x` semantics.
- No-SAM runs now fail when upstream silently embeds the original raster in an SVG wrapper.
- Environment checks now detect Windows User and Machine credential scopes without printing values.
- draw.io setup repairs stale Codex AppX marketplace paths after desktop updates.

### Validation

- 31 automated tests pass.
- Four deterministic public-acceptance routes pass QA.
- Three final PDFs independently render with Poppler.
- Public acceptance secret scan finds zero key-like values.

### Known limitations

- No-SAM raster reconstruction does not separate icons and remains experimental.
- Model-based SVG optimization can regress layout and always requires visual review.
- PaperBanana requires a compatible text-and-image generation provider and remains optional.
- draw.io Desktop is required for local ELK layout and embedded-XML image/PDF export from the official plugin.
