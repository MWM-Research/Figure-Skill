# Hybrid raster/vector representation contract

Use `hybrid-composite` when a single scientific Figure intentionally combines raster evidence or imagery with vector structure and annotation. Examples include video frames plus a model diagram, microscopy plus vector callouts, or a raster attention matrix surrounded by vector axes and result plots.

## Planning contract

Every hybrid panel must define `representation_contract`. Each role specifies its required SVG tag, count, and optional raster source glob:

```json
{
  "representation_contract": {
    "roles": [
      {"role": "video-frame-raster", "kind": "raster", "svg_tag": "image", "expected_count": 8, "source_glob": "assets/video-frame-*.png"},
      {"role": "attention-heatmap-raster", "kind": "raster", "svg_tag": "image", "expected_count": 1, "source_glob": "assets/attention-heatmap.png"},
      {"role": "transformer-module", "kind": "vector", "svg_tag": "rect", "expected_count": 7},
      {"role": "data-flow-arrow", "kind": "vector", "svg_tag": "path", "min_count": 1},
      {"role": "result-bar", "kind": "vector", "svg_tag": "rect", "min_count": 1},
      {"role": "axis", "kind": "vector", "svg_tag": "line", "min_count": 2}
    ],
    "unclassified_image_policy": "forbid",
    "exact_visible_labels": true
  }
}
```

Use exact `expected_count` whenever the user or source fixes the quantity. Use `min_count` only when the precise quantity is genuinely unconstrained. Every composed SVG element must carry the corresponding `data-role`.

## Source audit

After composing the hybrid SVG, run:

```powershell
python "<SKILL_ROOT>/scripts/audit_hybrid_svg.py" `
  --plan figure-plan.json `
  --svg hybrid-figure.svg `
  --asset-root <output-root> `
  --output reports/hybrid-structure-audit.json
```

The auditor:

- verifies every role uses the reviewed SVG tag and count;
- decodes every embedded PNG `<image>` payload;
- compares embedded bytes with source assets using SHA-256 multisets, preserving duplicate-content files;
- rejects unclassified `<image>` elements;
- verifies the exact visible-label set;
- binds the report to plan and SVG hashes.

QA requires one passing, hash-current `hybrid-structure-audit.json` whenever a representation contract is present. A shape that merely looks like a video frame or heatmap does not pass when the contract requires `<image>`.
