# Deterministic plot style

- Read every quantitative mark from an authoritative source file at render time.
- Start bar-chart axes at zero unless the plan explicitly documents and justifies another baseline.
- Use exact source labels. Do not silently rename methods, groups, metrics, or units.
- Reject duplicate categorical x-values until an aggregation is explicitly defined.
- Keep SVG text editable with `svg.fonttype = none` and embed TrueType text in PDF where supported.
- Use restrained colors, dark outlines, visible contrast, and non-color cues when multiple series are added.
- Save SVG, PDF, PNG, the rendering source, a render recipe, and per-mark provenance.
- For grouped bars, require a unique `(x, group)` pair per source row unless the plan defines an aggregation.
