# Generated raster scientific illustrations

Use this route for explicitly illustrative, generated PNG assets such as photorealistic concepts, 3D-style scientific scenes, graphical abstracts, and cover art. Do not use it to replace microscopy, medical imagery, field photographs, instrument captures, or quantitative evidence.

## Planning contract

The reviewed `raster-illustration` panel must record:

- `evidence_role: illustrative`
- the scientific description and required entities
- reviewed relationships between entities
- a visible-text allowlist
- forbidden content
- the requested visual style
- `human_review_required: true`
- `annotation_spec.mode: deterministic-overlay`
- an exact `visible_labels` allowlist matching every title, subtitle, callout, arrow label, legend label, and footer

Keep `open_questions` non-empty until ambiguous entities and relationships are resolved. Generated content must never introduce measurements, statistics, causal claims, or experimental observations that are absent from authoritative inputs.

## BYOK configuration

The team defaults are an OpenAI-compatible Images endpoint at `https://right.codes/codex/v1/images/generations` and model `gpt-image-2`. A member supplies only their own `FIGURE_IMAGE_API_KEY`. `FIGURE_IMAGE_BASE_URL` and `FIGURE_IMAGE_MODEL` are optional overrides.

On Windows, run `scripts/configure_image_key.ps1` interactively. It does not print the key. Open a new Codex task afterward so the new user environment is inherited.

Never put a key in a plan, prompt, generated artifact, request manifest, command-line argument, or repository file.

## Deterministic text overlay

The image-generation prompt always requests no visible text. After generation, `scripts/backends/raster_annotation_backend.py` scales a same-aspect provider image to the approved canvas and adds exact text through a deterministic SVG overlay rendered back to PNG.

Every new raster plan receives a reviewed title, a key-concepts subtitle, and the footer `Conceptual illustration — not quantitative evidence`. Add normalized-position callouts, arrows, and legends when the image needs internal explanation. Coordinates use `[x, y]` values between `0` and `1`.

```json
{
  "visible_labels": ["Temporal Attention", "Video Frames", "Data flow", "Low", "High"],
  "annotation_spec": {
    "mode": "deterministic-overlay",
    "allow_same_aspect_resize": true,
    "title": {"text": "Temporal Attention", "position": [0.5, 0.055]},
    "subtitle": {"text": "Video Frames", "position": [0.5, 0.095]},
    "labels": [
      {"text": "Video Frames", "position": [0.08, 0.85], "style": "section"}
    ],
    "arrows": [
      {"text": "Data flow", "from": [0.3, 0.88], "to": [0.7, 0.88]}
    ],
    "legend": {
      "position": [0.72, 0.9],
      "items": [
        {"label": "Low", "color": "#443399"},
        {"label": "High", "color": "#ddee33"}
      ]
    },
    "footer": {"text": "Conceptual illustration — not quantitative evidence", "position": [0.5, 0.965]}
  }
}
```

The backend rejects text that is absent from `visible_labels`, invalid coordinates, non-hex legend colors, aspect-ratio changes, or missing annotation provenance. It preserves the unannotated PNG and the overlay source for revision.

## Execution

Generate and review the plan first. Then execute only with explicit network authorization:

```powershell
python "<SKILL_ROOT>/scripts/figure.py" workflow `
  --plan <output-root>/figure-plan.json `
  --output <output-root> `
  --approve-plan `
  --execute-raster `
  --allow-network
```

The adapter sends `model`, `prompt`, `size`, `quality`, and `output_format` to the OpenAI-compatible Images endpoint. It accepts `data[0].b64_json` or an HTTPS `data[0].url`, validates the resulting image, and writes generation provenance without the credential.

## Delivery status

Successful API completion is not scientific approval. The provenance status remains `generated-awaiting-human-review`. Visually verify entity counts, relationships, prohibited additions, labels, exact canvas size, resolution, and caption consistency before accepting the image.

QA reports three independent states:

- `technical_status`: file integrity, provenance, and exact canvas contract
- `scientific_status`: all plan-derived assertions are assessed and pass
- `human_review_status`: a named human explicitly approves or rejects the assessed image

Overall `pass` requires all three gates. Missing review produces `warn`; a size mismatch, failed scientific assertion, stale image/plan hash, or human rejection produces `fail`.

Prepare a review template after generation:

```powershell
python "<SKILL_ROOT>/scripts/figure.py" review prepare `
  --plan <output-root>/figure-plan.json `
  --image <output-root>/panels/panel_a.png `
  --output <output-root>/reports/scientific-review.json
```

Record an assessment by supplying every assertion result as `ID=pass|fail|uncertain`. After every assertion passes, record human approval only when the user explicitly confirms they reviewed the exact hashed image:

```powershell
python "<SKILL_ROOT>/scripts/figure.py" review human `
  <output-root>/reports/scientific-review.json `
  --decision approved `
  --reviewer "<human reviewer>" `
  --confirm-reviewed
```

Never infer human approval from API completion, an agent assessment, or a previous image version.
