# Changelog

All notable project changes are recorded here.

## 0.12.0 - 2026-09-02

### Added

- Added interactive and non-interactive `setup` profiles for Core, Vectorize, Illustration, and All capabilities.
- Added a credential-safe `status` matrix, JSON reports, strict Profile exit codes, and atomic Runtime capability reports.
- Added compatibility tests for legacy script paths, public Python imports, copied plotting runtimes, and internal dependency boundaries.

### Changed

- Team installation now delegates Core/backend preparation to the unified Setup implementation while preserving existing PowerShell parameters.
- Split deterministic plotting into focused I/O, basic, distribution, classification, axis, provenance, and renderer modules.
- Split planning into route, data, illustration, raster, Hybrid, edit, and schema modules.
- Split QA into structural, data provenance, edit provenance, generated, Hybrid, and report modules.
- Kept `matplotlib_backend.py`, `plan_figure.py`, and `qa_figure.py` as thin backwards-compatible entry points.

### Validation

- 91 automated tests cover Setup/Status, public compatibility, copied-source execution, existing workflows, and all previous scientific QA gates.
- Five offline Showcase cases remain structurally and visually stable after the refactor.

## 0.11.0 - 2026-09-01

### Added

- Added deterministic Box, Violin, Histogram, Density, Confusion Matrix, ROC, and PR plots with explicit raw/precomputed calculation modes.
- Added asymmetric uncertainty, bounds, reviewed log/symlog axes, explicit axis breaks, non-zero baseline guards, and shared data-plot grids.
- Added formula-versioned derived provenance and QA recomputation for advanced statistics.
- Added exact-ID SVG translation/resize plus metadata-backed node, edge, alignment, distribution, overlap repair, and layered auto-layout operations.
- Added graph metadata to native SVG diagrams and schema-2.0 atomic edit provenance.
- Added five offline Showcase cases with structural and tolerant visual regression, diff artifacts, and release evidence.

### Changed

- Release verification now requires all Showcase cases to pass without Provider credentials or external network access.
- Release packages include Showcase manifests, regression summary, and contact sheet without bundling the full large Showcase tree.

### Validation

- 81 automated tests cover core workflows, advanced statistics, SVG semantic editing, and visual-regression failure modes.
- Five Showcase cases rebuild or reproduce from frozen inputs with no paid-service calls.

## 0.10.0 - 2026-09-01

### Added

- Added deterministic long-form Heatmap rendering with vector cells and vector colorbars.
- Added multi-series line/scatter rendering from explicit grouping columns.
- Added symmetric absolute error bars for bar, line, and scatter plots.
- Added per-cell Heatmap provenance and error-column provenance with QA verification.

### Changed

- Data planning now recognizes Heatmap/confusion-matrix, multi-series line, and explicit uncertainty requests.
- Duplicate Heatmap coordinates, incomplete Heatmap grids, duplicate per-series x values, negative uncertainty, and ambiguous uncertainty columns now block formal rendering.
- Loopback raster-adapter tests bypass configured HTTP proxies to remain local and deterministic.
- Release verification records the discovered test count instead of a hard-coded value.

### Validation

- 59 automated tests cover the expanded planner, renderer, provenance, QA, and local mock boundary.

## 0.9.0 - 2026-08-24

### Added

- Added `$paperbanana` and `$autofigure-edit` wrapper Skills to the Figure Skill Plugin.
- Added cross-platform, pinned, versioned, on-demand installation for both external backend repositories and isolated Python environments.
- Added backend status discovery, concurrent-install locking, atomic setup reports, and automatic Adapter runtime resolution.
- Added `scripts/install_team.ps1` for one-command Marketplace, Plugin, core runtime, and external backend setup.

### Changed

- External Adapters no longer require manually supplied repository paths after managed installation.
- AutoFigure execution automatically relaunches inside its isolated environment without exposing the key on the process command line.
- Plugin-only installations can now prepare both external backends instead of requiring a full development checkout.

## 0.8.0 - 2026-08-24

### Added

- Added a `hybrid-composite` route and reviewed raster/vector representation contracts.
- Added generic SVG source auditing with `data-role`, exact tag/count checks, embedded PNG decoding, and source-asset SHA-256 multiset matching.
- Added QA enforcement for current, passing hybrid audit reports bound to exact plan and SVG hashes.
- Added positive, wrong-tag, and duplicate-content raster routing tests.

### Changed

- Hybrid Figure acceptance now depends on SVG source structure rather than visual appearance.
- Raster roles represented by vector stand-ins and vector roles embedded as raster content fail the representation gate.

## 0.7.0 - 2026-08-24

### Added

- Added a generic deterministic annotation backend for generated raster figures.
- Added reviewed titles, key-concept subtitles, callouts, arrows, legends, and conceptual-evidence footers.
- Added annotation provenance, overlay-source retention, visible-label allowlist validation, and annotation QA.

### Changed

- Raster image models are now instructed to generate no text; all visible text is rendered deterministically after generation.
- New raster plans include a default explanatory title, key-concepts subtitle, and conceptual-illustration footer.
- Same-aspect provider images can be explicitly resized to the approved canvas by the annotation stage; aspect-ratio changes are rejected.

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
