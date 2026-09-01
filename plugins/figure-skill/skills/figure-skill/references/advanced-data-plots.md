# Advanced deterministic data plots

Read this reference for box, violin, histogram, density, confusion-matrix, ROC/PR, asymmetric uncertainty, risky axes, or shared-subplot requests.

## Calculation boundary

Every advanced panel declares `calculation.mode` as `precomputed` or `raw`. Raw calculations record `formula_version`, parameters, and every contributing source row. Precomputed marks retain identity mappings to the supplied columns. Do not silently switch modes.

Supported operations are `box-summary`, `kde`, `histogram`, `confusion-count`, `roc`, and `pr`.

- Box: NumPy linear percentiles and Tukey 1.5-IQR whiskers.
- KDE: Gaussian KDE on exactly 128 points; bandwidth is `scott` or an explicit positive number.
- Histogram: explicit `fd`, `sturges`, positive `count`, or increasing `edges` strategy.
- Confusion: raw `actual`/`predicted` samples with explicit `none`, `true`, `pred`, or `all` normalization; or a complete precomputed matrix.
- ROC/PR: raw binary `label`/`score` data requires `positive_label`; equal scores are grouped. AUC is absent unless `compute_auc` is true.

## Forms

- `box-plot`: raw long-form `x/y`, or one precomputed summary row per `x`.
- `violin-plot`: raw sample `x/y`, or precomputed `x/value` density grid.
- `histogram`: raw `value` plus optional `group`, or precomputed `x/x2/y` bins.
- `density-plot`: raw `value` plus optional `group`, or precomputed `x/value` density points.
- `confusion-matrix`: raw `actual/predicted`, or precomputed `x/y/value` cells.
- `roc-curve` and `pr-curve`: raw `label/score`, or precomputed `x/y` points; both allow an explicit `group`.

## Uncertainty

Use `uncertainty.mode` values `symmetric-delta`, `asymmetric-delta`, or `bounds`. Delta values must be non-negative. Bounds must satisfy `lower <= y <= upper`. The legacy `error` field remains a symmetric-delta alias and cannot be combined with the new object.

## Axes

Axes default to linear. A bar y-limit whose lower bound is not zero requires `baseline_justification`. Log axes require positive marks and uncertainty endpoints. A y-axis break is allowed only for line/scatter panels, requires an increasing omitted interval plus justification, and fails if any point lies inside the omitted interval.

## Shared subplot grid

A `data-plot-grid` panel contains reviewed `subplots`, positive `layout.rows/columns`, and optional `share_x`, `share_y`, and `shared_legend`. Axis breaks are not supported inside a grid. The backend emits one SVG/PDF/PNG and retains a subplot identifier on every provenance mark.
