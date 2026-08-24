# Changelog

All notable project changes are recorded here.

## 0.6.0 - 2026-08-24

### Added

- Added plan-derived scientific review templates for generated raster figures.
- Added separate technical, scientific, and human-review status gates.
- Added exact raster canvas validation and plan/image hash binding.
- Added explicit assessment and human approval commands through the self-bootstrapping launcher.

### Changed

- Generated raster output without completed scientific assessment and explicit human approval can no longer receive overall `pass`.
- Provider output that differs from the approved canvas is recorded as a size mismatch and fails technical QA.

## 0.5.0 - 2026-08-24

### Added

- Added a reviewed `raster-illustration` route for photorealistic concepts and 3D-style scientific illustrations.
- Added a BYOK OpenAI-compatible Images adapter with redacted manifests, base64/HTTPS output handling, image validation, and generation provenance.
- Added secure interactive Windows configuration for each member's `FIGURE_IMAGE_API_KEY`.
- Added raster-specific QA and simulated HTTP generation tests.

### Changed

- Team defaults now target `https://right.codes/codex/v1` with `gpt-image-2`; members can override the public endpoint and model locally.
- Generated raster outputs are explicitly labeled illustrative and remain awaiting mandatory human review.

## 0.4.0 - 2026-08-23

### Added

- Added a current-working-directory-independent launcher for bootstrap, health checks, workflows, and QA.
- Added a fully pinned dependency lock and a versioned runtime under the user's Codex directory.
- Added runtime bootstrap and path-independence tests.

### Changed

- First use now installs core dependencies without modifying the research project's Python environment.
- Missing optional AI repositories and credentials now report a non-blocking disabled state.

## 0.3.0 - 2026-08-23

### Added

- Added the `mwm-research` private Codex Marketplace manifest.
- Added a validated `figure-skill` Codex Plugin manifest.
- Added Plugin and Marketplace checks to release verification.

### Changed

- Moved the canonical Skill source to `plugins/figure-skill/skills/figure-skill`.
- Team installation now uses `codex plugin marketplace add` and `codex plugin add` instead of manual folder copying.
- Release archives now include the complete Marketplace and Plugin structure.

### Validation

- 33 automated tests pass, including Plugin/Marketplace manifest consistency checks.

## 0.2.0 - 2026-08-23

### Changed

- Renamed the Codex Skill from `scientific-figure-workflow` to `figure-skill`.
- Changed the display name from `Scientific Figure Workflow` to `Figure Skill`.
- Changed the invocation from `$scientific-figure-workflow` to `$figure-skill`.
- Renamed source, CI, verification, and release-package paths to `figure-skill`.
- Renamed the internal release archive to `figure-skill-v0.2.0.zip`.

### Migration

- Install the new Skill at `$CODEX_HOME/skills/figure-skill`.
- Remove or deactivate the old `$CODEX_HOME/skills/scientific-figure-workflow` copy after verifying the new installation.
- Existing figure plans and generated outputs remain compatible.

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
