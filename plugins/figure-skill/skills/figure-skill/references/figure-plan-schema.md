# Figure plan schema

Store plans as JSON with schema version `1.1`:

```json
{
  "schema_version": "1.1",
  "route": "data-plot | illustration | raster-illustration | hybrid-composite | edit | composite",
  "route_source": "user | inferred",
  "brief": "What the figure must communicate",
  "input_root": "absolute input directory",
  "inputs": [],
  "panels": [],
  "constraints": {
    "evidence_only": true,
    "forbid_invented_quantitative_claims": true,
    "editable_source_required": true
  },
  "required_outputs": ["editable-source", "svg", "pdf", "png", "provenance"],
  "review_status": "draft | approved",
  "open_questions": []
}
```

Use a data panel like:

```json
{
  "id": "B",
  "title": "accuracy comparison",
  "type": "data-plot",
  "source_files": ["results.csv"],
  "visual_form": "bar-chart",
  "x": "method",
  "y": "accuracy",
  "unit": "fraction",
  "transform": "none",
  "backend": "matplotlib"
}
```

Use long-form data for a multi-series line plot with symmetric absolute uncertainty:

```json
{
  "id": "B",
  "title": "Accuracy by epoch",
  "type": "data-plot",
  "source_files": ["training.csv"],
  "visual_form": "line-chart",
  "x": "epoch",
  "y": "accuracy",
  "group": "method",
  "error": "std",
  "error_semantics": "symmetric-absolute",
  "unit": "fraction",
  "transform": "none",
  "backend": "matplotlib"
}
```

Every `(x, group)` pair must be unique unless the reviewed plan defines an aggregation. Error values must be finite and non-negative; do not infer confidence level, standard deviation, or standard error semantics beyond the exact source column.

Use long-form data for a deterministic Heatmap:

```json
{
  "id": "C",
  "title": "Temporal attention map",
  "type": "data-plot",
  "source_files": ["attention.csv"],
  "visual_form": "heatmap",
  "x": "Frame",
  "y": "Head",
  "value": "Attention",
  "unit": "fraction",
  "colormap": "viridis",
  "annotate_values": true,
  "transform": "none",
  "backend": "matplotlib"
}
```

Every `(x, y)` coordinate must map to exactly one source row and the long-form table must define a complete rectangular grid. Each cell is recorded in provenance as `x`, `y`, and `value`; SVG cells and the colorbar remain vector elements.

Advanced deterministic forms use `visual_form` values `box-plot`, `violin-plot`, `histogram`, `density-plot`, `confusion-matrix`, `roc-curve`, or `pr-curve` and must include:

```json
{
  "calculation": {
    "mode": "precomputed | raw",
    "operation": "box-summary | kde | histogram | confusion-count | roc | pr",
    "parameters": {}
  },
  "uncertainty": {
    "mode": "symmetric-delta | asymmetric-delta | bounds",
    "error_column": "std",
    "lower_column": "ci_lower",
    "upper_column": "ci_upper"
  },
  "axis": {
    "x_scale": "linear | log | symlog",
    "y_scale": "linear | log | symlog",
    "x_limits": null,
    "y_limits": null,
    "baseline_justification": null,
    "break": {"axis": "y", "omit": [20, 80], "justification": "Reviewed reason"}
  }
}
```

Read [advanced-data-plots.md](advanced-data-plots.md) for required columns and calculation rules. Omit `uncertainty` or `axis` when they are not needed; do not populate high-risk options speculatively.

A shared Matplotlib Figure uses a `data-plot-grid` panel with `layout.rows/columns`, `share_x`, `share_y`, `shared_legend`, and reviewed `subplots` that each follow the data-panel schema.

Use an illustration panel like:

```json
{
  "id": "A",
  "title": "Method pipeline",
  "type": "illustration",
  "source_files": ["methods.txt"],
  "visual_form": "architecture-diagram",
  "entities": ["Encoder", "Retrieval", "Classifier"],
  "edges": [
    {"from": "Encoder", "to": "Retrieval", "meaning": "data-flow", "inferred": true}
  ],
  "reading_order": "left-to-right",
  "backend": "svg",
  "inference_requires_review": true
}
```

Use a generated raster illustration panel only for explicitly illustrative output:

```json
{
  "id": "A",
  "title": "3D method concept",
  "type": "raster-illustration",
  "style": "3d-render",
  "evidence_role": "illustrative",
  "scientific_description": "The encoder flows to retrieval and then to the classifier.",
  "entities": ["Encoder", "Retrieval", "Classifier"],
  "edges": [
    {"from": "Encoder", "to": "Retrieval", "meaning": "data-flow", "inferred": true}
  ],
  "visible_labels": [
    "3D method concept",
    "Encoder · Retrieval · Classifier",
    "Conceptual illustration — not quantitative evidence"
  ],
  "annotation_spec": {
    "mode": "deterministic-overlay",
    "title": {"text": "3D method concept", "position": [0.5, 0.055]},
    "subtitle": {"text": "Encoder · Retrieval · Classifier", "position": [0.5, 0.095]},
    "labels": [],
    "arrows": [],
    "legend": {},
    "footer": {"text": "Conceptual illustration — not quantitative evidence", "position": [0.5, 0.965]}
  },
  "forbidden_content": ["invented measurements", "watermarks"],
  "semantic_assertions": ["Exactly three response hotspots are visible"],
  "canvas": {"width": 1024, "height": 768},
  "backend": "byok-openai-compatible-images",
  "human_review_required": true
}
```

For this route, set `editable_source_required` to `false`, set `generated_content_must_be_labeled` to `true`, and require PNG, generation provenance, and QA outputs rather than claiming an editable vector source.

For a hybrid raster/vector Figure, add a `representation_contract` to its `hybrid-composite` panel. Read [hybrid-representation.md](hybrid-representation.md) for the full schema and audit requirements.

Use an edit panel only with explicit, reviewable operations:

```json
{
  "id": "A",
  "title": "Edited figure",
  "type": "edit",
  "source_files": ["existing.svg"],
  "visual_form": "preserve-source-format",
  "backend": "native-vector-editor",
  "operations": [
    {"op": "replace_text", "old": "Classifier", "new": "Retrieval", "expected_matches": 1},
    {"op": "set_attribute", "element_id": "module", "attribute": "fill", "value": "#333333"}
  ]
}
```

`replace_text` uses an exact text match and defaults to exactly one expected match. `set_attribute`, `translate_element`, and `resize_element` require one exact element ID. Metadata-backed semantic operations support nodes, edges, deterministic alignment/distribution/overlap repair, and layered auto-layout. Read [advanced-svg-editing.md](advanced-svg-editing.md) for the complete operation boundary. Unsupported formats, ambiguous selectors, legacy topology without explicit binding, and unsafe geometry must remain unresolved or use an external handoff.

Set `review_status` to `approved` only after checking source files and clearing every open question. Never use approval to conceal missing scientific information.
