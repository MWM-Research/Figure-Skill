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

`replace_text` uses an exact text match and defaults to exactly one expected match. `set_attribute` requires one exact element ID and accepts only the backend's visual-attribute allowlist. Unsupported formats or ambiguous selectors must remain unresolved or use an explicit external handoff.

Set `review_status` to `approved` only after checking source files and clearing every open question. Never use approval to conceal missing scientific information.
