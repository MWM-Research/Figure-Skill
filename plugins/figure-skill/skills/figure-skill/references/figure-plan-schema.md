# Figure plan schema

Store plans as JSON with schema version `1.1`:

```json
{
  "schema_version": "1.1",
  "route": "data-plot | illustration | edit | composite",
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

`replace_text` uses an exact text match and defaults to exactly one expected match. `set_attribute` requires one exact element ID and accepts only the backend's visual-attribute allowlist. Unsupported formats or ambiguous selectors must remain unresolved or use an explicit external handoff.

Set `review_status` to `approved` only after checking source files and clearing every open question. Never use approval to conceal missing scientific information.
