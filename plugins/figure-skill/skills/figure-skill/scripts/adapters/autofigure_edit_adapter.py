#!/usr/bin/env python3
"""Prepare or explicitly execute an AutoFigure-Edit request without logging API keys."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

from upstream_contract import inspect_contract
from external_runtime import backend_paths


KEY_ENV = {
    "openai_response": ("OPENAI_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "bianxie": ("BIANXIE_API_KEY",),
    "custom": ("AUTOFIGURE_API_KEY",),
}
REQUIRED_FLAGS = {
    "--method_file", "--input_figure_path", "--output_dir", "--provider", "--api_key",
    "--base_url", "--svg_model", "--sam_backend", "--optimize_iterations",
}
RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def select_source(plan: dict, input_figure: Path | None) -> tuple[str, Path]:
    if input_figure:
        if not input_figure.is_file():
            raise FileNotFoundError(input_figure)
        return "input_figure_path", input_figure.resolve()
    input_root = Path(plan.get("input_root") or ".").resolve()
    for panel in plan.get("panels", []):
        if panel.get("type") != "edit":
            continue
        for source in panel.get("source_files", []):
            path = (input_root / source).resolve()
            if path.suffix.lower() in RASTER_SUFFIXES and path.is_file():
                return "input_figure_path", path
    for panel in plan.get("panels", []):
        if panel.get("type") != "illustration":
            continue
        for source in panel.get("source_files", []):
            path = (input_root / source).resolve()
            if path.suffix.lower() in {".txt", ".md", ".tex"} and path.is_file():
                return "method_file", path
    raise ValueError("AutoFigure-Edit requires an edit-panel raster image, a methods text file, or --input-figure")


def prepare(
    plan: dict, repo: Path, output_dir: Path, provider: str,
    input_figure: Path | None, sam_backend: str,
    base_url: str | None = None, svg_model: str | None = None,
    optimize_iterations: int = 0,
    backend_python: Path | None = None,
) -> dict:
    contract = inspect_contract(repo, repo / "autofigure2.py", REQUIRED_FLAGS)
    source_flag, source = select_source(plan, input_figure)
    output_dir.mkdir(parents=True, exist_ok=True)
    no_sam = sam_backend == "none"
    execution_entrypoint = (
        Path(__file__).resolve().with_name("autofigure_no_sam_runner.py")
        if no_sam else (repo / "autofigure2.py").resolve()
    )
    public_command = [
        str(backend_python or Path(sys.executable)), str(execution_entrypoint),
        f"--{source_flag}", str(source), "--output_dir", str(output_dir.resolve()),
        "--provider", provider, "--api_key", "<redacted-at-runtime>",
    ]
    if no_sam:
        public_command.extend(["--upstream-entry", str((repo / "autofigure2.py").resolve())])
    else:
        public_command.extend(["--sam_backend", sam_backend])
    public_command.extend(["--optimize_iterations", str(optimize_iterations)])
    if base_url:
        public_command.extend(["--base_url", base_url])
    if svg_model:
        public_command.extend(["--svg_model", svg_model])
    return {
        "schema_version": "1.0",
        "adapter": "AutoFigure-Edit",
        "upstream_repo": str(repo.resolve()),
        "upstream_cli": "autofigure2.py",
        "license": "MIT",
        "input_mode": source_flag,
        "input": str(source),
        "output_dir": str(output_dir.resolve()),
        "provider": provider,
        "base_url": base_url,
        "svg_model": svg_model,
        "optimize_iterations": optimize_iterations,
        "sam_backend": sam_backend,
        "segmentation_performed": not no_sam,
        "execution_entrypoint": str(execution_entrypoint),
        "display_command": public_command,
        "credential_environment": list(KEY_ENV[provider]),
        "network_required": True,
        "upstream_contract": contract,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--provider", choices=tuple(KEY_ENV), default="openai_response")
    parser.add_argument("--sam-backend", choices=("none", "local", "fal", "roboflow", "api"), help="Defaults to AUTOFIGURE_SAM_BACKEND or local")
    parser.add_argument("--base-url", help="OpenAI-compatible base URL; required for provider=custom unless AUTOFIGURE_CUSTOM_BASE_URL is set")
    parser.add_argument("--svg-model", help="Provider model id used for multimodal SVG reconstruction")
    parser.add_argument("--optimize-iterations", type=int, choices=range(0, 4), default=0)
    parser.add_argument("--input-figure", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    args = parser.parse_args()
    installed = backend_paths("autofigure-edit")
    repo = (args.repo or installed["repo"]).resolve()
    backend_python = installed["python"]
    entrypoint = repo / "autofigure2.py"
    if not entrypoint.is_file() or not backend_python.is_file():
        parser.error("AutoFigure-Edit backend is not installed; run figure.py backends install --backend autofigure-edit")
    if args.execute and Path(sys.executable).resolve() != backend_python.resolve():
        environment = os.environ.copy()
        result = subprocess.run([str(backend_python), str(Path(__file__).resolve()), *sys.argv[1:]], env=environment)
        return result.returncode
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    base_url = args.base_url or (os.environ.get("AUTOFIGURE_CUSTOM_BASE_URL") if args.provider == "custom" else None)
    svg_model = args.svg_model or os.environ.get("AUTOFIGURE_SVG_MODEL")
    if args.provider == "custom" and not base_url:
        parser.error("provider=custom requires --base-url or AUTOFIGURE_CUSTOM_BASE_URL")
    sam_backend = args.sam_backend or os.environ.get("AUTOFIGURE_SAM_BACKEND", "local")
    if sam_backend not in {"none", "local", "fal", "roboflow", "api"}:
        parser.error(f"unsupported AUTOFIGURE_SAM_BACKEND: {sam_backend}")
    request = prepare(
        plan, repo, args.output_dir.resolve(), args.provider,
        args.input_figure, sam_backend, base_url, svg_model, args.optimize_iterations, backend_python,
    )
    manifest = args.output_dir.resolve() / "autofigure-edit-request.json"
    manifest.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.execute:
        print(f"Prepared AutoFigure-Edit request -> {manifest}")
        return 0
    if request["network_required"] and not args.allow_network:
        raise SystemExit("AutoFigure-Edit execution requires explicit --allow-network for the selected configuration")
    key = next((os.environ.get(name) for name in request["credential_environment"] if os.environ.get(name)), None)
    if not key:
        raise SystemExit(f"No credential found in: {', '.join(request['credential_environment'])}")
    argv = request["display_command"][:]
    argv[argv.index("<redacted-at-runtime>")] = key
    previous_argv = sys.argv
    try:
        sys.argv = argv[1:]
        runpy.run_path(str(Path(request["execution_entrypoint"]).resolve()), run_name="__main__")
    finally:
        sys.argv = previous_argv
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
