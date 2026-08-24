# Optional external backends

Keep external generation isolated from the deterministic evidence pipeline. Never replace a data-driven panel with generated pixels.

## Plugin-managed installation

The Figure Skill Plugin includes `$paperbanana` and `$autofigure-edit` wrapper Skills plus a cross-platform Bootstrap. After explicit approval for the large download:

```powershell
python "<SKILL_ROOT>/scripts/figure.py" backends install --backend all
```

Inspect without changing state:

```powershell
python "<SKILL_ROOT>/scripts/figure.py" backends status
```

Pinned repositories and separate virtual environments are stored under `~/.codex/runtimes/figure-skill/<version>/external/`. Adapters discover these paths automatically. Keys remain separate and are never installed by the Plugin.

## BYOK raster illustration

- Default base URL: `https://right.codes/codex/v1`
- Default model: `gpt-image-2`
- Credential: member-local `FIGURE_IMAGE_API_KEY`
- Protocol: `POST <base-url>/images/generations`
- The request manifest is prepared without the key. Execution requires an approved plan plus `--execute-raster --allow-network`.
- The generated PNG is labeled illustrative and remains subject to mandatory human review.

For maintainer development only, project-root `scripts/setup_external_backends.ps1` can still install the same pinned commits under the checkout's `.external/` directory.

## draw.io

- Official project: `https://github.com/jgraph/drawio-mcp`
- The deterministic adapter writes uncompressed `.drawio` XML and a handoff manifest for `create_diagram` or `open_drawio_xml`.
- `scripts/run_workflow.py` creates the draw.io source automatically for approved illustration panels.
- Opening the MCP handoff remains an agent action; file generation does not require a server or network connection.

## Happy Figure

- Upstream project: `https://github.com/BAIKEMARK/happy-figure-skill`
- License: CC BY-NC-SA 4.0. Do not vendor its instruction/reference content into this skill.
- `scripts/adapters/happy_figure_adapter.py` creates a constrained agent-skill request containing approved entities and a visible-label allowlist.
- A Codex/Claude environment with `$happy-figure-skill` installed must execute the handoff.

## PaperBanana

- Upstream project: `https://github.com/dwzhu-pku/PaperBanana`
- License: Apache-2.0.
- Prepare without network access:

  ```powershell
  python scripts/adapters/paperbanana_adapter.py figure-plan.json `
    --repo <PaperBanana-repo> --output-dir external/paperbanana --num-candidates 1
  ```

  In the project checkout, replace `python` with `.external/venvs/paperbanana/Scripts/python.exe` so the upstream process uses the verified isolated dependencies.

- Execute only after inspecting the manifest and authorizing provider usage:

  ```powershell
  python scripts/adapters/paperbanana_adapter.py figure-plan.json `
    --repo <PaperBanana-repo> --output-dir external/paperbanana `
    --num-candidates 1 --execute --allow-network
  ```

- Supply credentials only through `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, or an explicitly approved upstream config. Start with one candidate to control cost.
- The adapter validates the required upstream CLI flags offline and records the repository commit plus entrypoint SHA-256 in every request manifest.

## AutoFigure-Edit

- Upstream project: `https://github.com/ResearAI/AutoFigure-Edit`
- License: MIT.
- Prepare a redacted request first:

  ```powershell
  python scripts/adapters/autofigure_edit_adapter.py figure-plan.json `
    --repo <AutoFigure-Edit-repo> --output-dir external/autofigure `
    --provider openai_response --sam-backend local
  ```

- Execution requires `--execute --allow-network` and a provider-specific environment variable. The adapter injects the key in-process so it does not appear in the saved manifest or operating-system command line.
- In the project checkout, run this adapter with `.external/venvs/autofigure-edit/Scripts/python.exe`.
- OpenAI-compatible relays use `--provider custom`, `AUTOFIGURE_CUSTOM_BASE_URL`, `AUTOFIGURE_API_KEY`, and an explicit `--svg-model` or `AUTOFIGURE_SVG_MODEL`. Verify the selected model accepts image input, `max_tokens`, and standard Chat Completions `choices` before execution.
- Use `--sam-backend none` or `AUTOFIGURE_SAM_BACKEND=none` when paid segmentation services and gated local SAM3 are excluded. This intentionally enters AutoFigure's pure-SVG fallback: it performs no icon separation and must be labeled as reduced-fidelity reconstruction.
- Raster sources declared directly on an `edit` panel are selected automatically; `--input-figure` remains available as an override.
- The adapter validates the current upstream CLI contract offline and records the repository commit plus entrypoint SHA-256 in the request manifest.
- Treat SVGs containing a full-canvas embedded raster image as a fallback, not as fully editable vector output.
