# Figure Skill - Public Acceptance Report

Date: 2026-08-20

Overall result: **CONDITIONAL PASS**

The deterministic core is suitable for a controlled team pilot. AI raster-to-SVG reconstruction remains experimental and must retain a mandatory visual review gate.

## Public materials

| Material | Source | License | Acceptance use |
|---|---|---|---|
| Iris dataset | UCI Machine Learning Repository, DOI `10.24432/C56C76` | CC BY 4.0 | Data plotting and per-mark provenance |
| Iris Pipeline | scikit-learn Getting Started | BSD documentation/code | Method architecture and composite figure |
| Neural Network.svg | Wikimedia Commons, QuantuMechaniX8 | CC0 1.0 | Native SVG edit and raster reconstruction ground truth |
| Artificial Neuron Scheme.png | Wikimedia Commons, Lightning13 | Public domain | Public PNG-to-SVG reconstruction |

Full URLs, attribution, license notes, and downloaded-file hashes are in `sources/SOURCES.md` and `sources/download-hashes.json`.

## Route acceptance

| Route | Result | Evidence |
|---|---|---|
| `data-plot` | PASS | 150 Iris samples rendered as a numeric scatter plot; every mark maps to source row and x/y columns; QA pass |
| `illustration` | PASS | Six pipeline entities and five directed edges; native SVG, draw.io, PDF, PNG; QA pass |
| `composite` | PASS | Method panel and data panel assembled into one editable SVG plus PDF/PNG; QA pass |
| `edit` | PASS | One exact ID-based SVG attribute edit; original retained; source/output hashes and applied operation recorded; QA pass |

## Raster reconstruction acceptance

### Artificial neuron

- Result: PASS
- Pure SVG: yes
- Embedded raster images: 0
- Vector shape elements: 33
- Pixel similarity: 0.936347
- Foreground IoU: 0.323942
- Visual review: core inputs, weights, summation, activation, bias, and outputs remain legible without clipping

### Neural network ground-truth benchmark

- Result: WARN
- Pure SVG: yes
- Embedded raster images: 0
- Vector shape elements: 66
- Pixel similarity: 0.917713
- Foreground IoU: 0.070087
- Visual review: main layer topology is recognizable, but the right-side `Output` label is clipped and layout fidelity is low

### Negative cases

1. The initially selected relay model returned HTTP 503. Upstream AutoFigure silently created an SVG containing the original PNG. This is not editable reconstruction and is classified as FAIL.
2. One model optimization iteration produced a black background and removed many edges and labels. The optimized result is classified as FAIL and did not replace the prior warning result.

## Defects found and fixed during acceptance

1. Scatter planning selected the categorical `species` column as x-axis even when two numeric columns were requested. Fixed and regression-tested.
2. Scatter titles used generic `comparison` wording. Fixed to `y vs x` and regression-tested.
3. No-SAM upstream fallback could return success while embedding the original raster. Added mandatory pure-SVG validation; embedded images and empty vector output now fail execution.
4. Added configurable AutoFigure optimization iterations so visual optimization can be tested without becoming an implicit success criterion.

## PDF and editable-source verification

- Three final PDFs created: data plot, illustration, composite
- All PDFs: one page, readable, text-extractable
- All PDFs independently rendered with Poppler
- No clipping or overlap found in the three accepted PDFs
- Illustration and composite draw.io files: 6 vertices, 5 edges, 5 edge geometries, 0 XML comments

## Security and reproducibility

- Secret-pattern matches in the complete acceptance directory: 0
- API key is not present in plans, manifests, SVGs, reports, or logs stored in this package
- Downloaded public inputs have SHA-256 hashes
- Data plot records source SHA-256 and 150 mark-level mappings
- Native edit records source and output SHA-256
- Automated unit/integration tests: 29 passed

## Decision

The following can move to team pilot:

- data-driven plots;
- method architecture diagrams;
- composite figures;
- explicit native SVG edits;
- draw.io handoff and deterministic exports.

The following must remain experimental:

- no-SAM raster-to-SVG reconstruction;
- automatic model-based SVG optimization.

Do not accept a reconstruction solely because the command exits successfully. Require pure-SVG validation, secret scan, structural QA, and human visual review.

## Recommended next step

Run the same matrix on one real, non-sensitive team project before promoting Figure Skill beyond internal pilot status.
