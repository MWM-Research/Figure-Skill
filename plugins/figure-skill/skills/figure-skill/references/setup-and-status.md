# Setup profiles and capability status

Use `scripts/figure.py setup` for installation and `scripts/figure.py status` for the team-facing capability matrix. Setup never requests or stores Provider credentials.

Profiles:

- `core`: deterministic plots, native SVG, Hybrid Figure, QA, and export runtime.
- `vectorize`: Core plus pinned AutoFigure-Edit.
- `illustration`: Core plus pinned PaperBanana; BYOK raster credential presence is reported separately.
- `all`: Core and both pinned external backends. This is the interactive default and may download several GB.

Interactive Setup confirms large downloads. Automation must specify `--profile` and `--yes`. Use `--dry-run` to inspect actions without creating a Runtime or downloading dependencies. Missing credentials do not fail installation; Status reports only their environment-variable names and presence.

Status values are `ready`, `installed-needs-credential`, `missing-credential`, `missing-dependency`, `optional-disabled`, and `degraded`. Ordinary Status succeeds when Core is ready. `--require-profile` returns code 2 until every capability required by that Profile is ready.
