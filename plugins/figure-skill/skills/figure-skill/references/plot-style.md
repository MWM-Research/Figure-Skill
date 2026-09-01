# Deterministic plot style

- Read every quantitative mark from an authoritative source file at render time.
- Start bar-chart axes at zero unless the plan explicitly documents and justifies another baseline.
- Use exact source labels. Do not silently rename methods, groups, metrics, or units.
- Reject duplicate categorical x-values until an aggregation is explicitly defined.
- Keep SVG text editable with `svg.fonttype = none` and embed TrueType text in PDF where supported.
- Use restrained colors, dark outlines, visible contrast, and non-color cues when multiple series are added.
- Save SVG, PDF, PNG, the rendering source, a render recipe, and per-mark provenance.
- For grouped bars, require a unique `(x, group)` pair per source row unless the plan defines an aggregation.
- For multi-series line/scatter plots, use long-form `x/group/y` data and require a unique `(x, group)` pair unless the plan defines an aggregation.
- Use an error column only when the plan explicitly identifies it as a non-negative symmetric absolute uncertainty; record the source error value for every mark.
- For Heatmaps, use long-form `x/y/value` data, require one source row per coordinate and a complete rectangular grid, and keep both cells and colorbar vector in SVG.
- Keep advanced calculations explicit: record raw/precomputed mode, algorithm parameters, formula version, and all contributing source rows.
- Default to linear axes and a zero bar baseline. Require a visible, reviewed justification for non-zero bar baselines or omitted axis intervals.
