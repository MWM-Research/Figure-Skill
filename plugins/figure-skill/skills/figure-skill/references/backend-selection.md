# Backend selection record

Reviewed on 2026-07-31 against the links in the team infrastructure list.

## Default stack

| Candidate | Decision | Evidence and boundary |
|---|---|---|
| `dwzhu-pku/PaperBanana` | Primary optional generation backend | Author-maintained implementation, Apache-2.0. The adapter and setup script are pinned to commit `836455537e863b5a2f40dace487a782c0bc5ef94`. |
| `ResearAI/AutoFigure-Edit` | Primary raster-to-SVG reconstruction backend | MIT. The adapter and setup script are pinned to commit `16f3749e9d512bdf7b7b55c162307bc289750b7a`. |
| official draw.io MCP | Primary interactive vector handoff | Used for editable diagram review; deterministic `.drawio` generation remains available without the server. |
| `BAIKEMARK/happy-figure-skill` | Optional agent-skill handoff | Commit reviewed: `6292597250ed874d65756d13a492f6eefe07fb65`. CC BY-NC-SA 4.0 means it is not vendored and must not be assumed suitable for commercial use. |

## Alternatives not enabled by default

| Candidate | Decision | Reason |
|---|---|---|
| `llmsresearch/paperbanana` | Documented alternative, not a second default runtime | The screenshot link omitted the `s`; the live repository is `llmsresearch/paperbanana`. It is an unofficial MIT community implementation with its own CLI and MCP server. Running two PaperBanana implementations by default would duplicate dependencies, provider configuration, and validation responsibilities. Current HEAD reviewed: `8b4745ad302439eded5884c9ec77412d99931047`. |
| `paper-bananas.com` | Manual opt-in only | Hosted third-party service with account, pricing, and upload implications. Never upload unpublished text or figures automatically; require a separate user data-governance decision. |
| `BROOO/cs-experiment-figure-studio` | Unavailable | Both the GitHub page and `git ls-remote` returned repository-not-found on 2026-07-31. Do not make the workflow depend on it until a valid replacement URL is supplied and reviewed. |

## Re-evaluation rule

Re-run this review before changing the default backend. Compare license, repository availability, current CLI contract, editable output quality, provider/credential handling, reproducibility, and unpublished-data exposure. A visually attractive demo alone is not enough to replace the evidence-preserving deterministic path.
