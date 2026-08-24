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

Keep `open_questions` non-empty until ambiguous entities and relationships are resolved. Generated content must never introduce measurements, statistics, causal claims, or experimental observations that are absent from authoritative inputs.

## BYOK configuration

The team defaults are an OpenAI-compatible Images endpoint at `https://right.codes/codex/v1/images/generations` and model `gpt-image-2`. A member supplies only their own `FIGURE_IMAGE_API_KEY`. `FIGURE_IMAGE_BASE_URL` and `FIGURE_IMAGE_MODEL` are optional overrides.

On Windows, run `scripts/configure_image_key.ps1` interactively. It does not print the key. Open a new Codex task afterward so the new user environment is inherited.

Never put a key in a plan, prompt, generated artifact, request manifest, command-line argument, or repository file.

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
