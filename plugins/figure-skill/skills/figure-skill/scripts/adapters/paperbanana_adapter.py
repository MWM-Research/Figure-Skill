#!/usr/bin/env python3
"""Prepare or explicitly execute a PaperBanana illustration request."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from upstream_contract import inspect_contract
from external_runtime import backend_paths


REQUIRED_FLAGS = {
    "--content-file", "--caption", "--task", "--output", "--num-candidates", "--exp-mode",
}


def select_panel(plan: dict, panel_id: str | None) -> dict:
    panels = [panel for panel in plan.get("panels", []) if panel.get("type") == "illustration"]
    if panel_id:
        panels = [panel for panel in panels if str(panel.get("id")) == panel_id]
    if len(panels) != 1:
        raise ValueError("select exactly one illustration panel with --panel")
    return panels[0]


def prepare(
    plan: dict, panel: dict, output_dir: Path, repo: Path, candidates: int,
    backend_python: Path | None = None,
) -> dict:
    contract = inspect_contract(repo, repo / "skill" / "run.py", REQUIRED_FLAGS)
    input_root = Path(plan.get("input_root") or ".").resolve()
    source_paths = [(input_root / source).resolve() for source in panel.get("source_files", [])]
    content_parts = []
    for source in source_paths:
        if source.suffix.lower() in {".txt", ".md", ".tex"} and source.is_file():
            content_parts.append(source.read_text(encoding="utf-8-sig", errors="replace"))
    if not content_parts:
        raise ValueError("PaperBanana requires readable TXT/MD/TEX source content")
    output_dir.mkdir(parents=True, exist_ok=True)
    content_file = output_dir / f"panel_{str(panel['id']).lower()}_paperbanana_content.txt"
    content_file.write_text("\n\n".join(content_parts), encoding="utf-8")
    target = output_dir / f"panel_{str(panel['id']).lower()}_paperbanana.png"
    command = [
        str(backend_python or Path(sys.executable)), str((repo / "skill" / "run.py").resolve()),
        "--content-file", str(content_file.resolve()),
        "--caption", str(panel.get("title") or plan.get("brief") or "Scientific illustration"),
        "--task", "diagram", "--output", str(target.resolve()),
        "--num-candidates", str(candidates), "--exp-mode", "demo_full",
    ]
    return {
        "schema_version": "1.0",
        "adapter": "PaperBanana",
        "upstream_repo": str(repo.resolve()),
        "upstream_cli": "skill/run.py",
        "license": "Apache-2.0",
        "panel": panel.get("id"),
        "content_file": str(content_file.resolve()),
        "expected_output": str(target.resolve()),
        "command": command,
        "network_required": True,
        "credential_environment": ["GOOGLE_API_KEY", "OPENROUTER_API_KEY"],
        "upstream_contract": contract,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--panel")
    parser.add_argument("--num-candidates", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--allow-config-credentials", action="store_true")
    args = parser.parse_args()
    installed = backend_paths("paperbanana")
    repo = (args.repo or installed["repo"]).resolve()
    backend_python = installed["python"]
    if not (repo / "skill" / "run.py").is_file() or not backend_python.is_file():
        parser.error("PaperBanana backend is not installed; run figure.py backends install --backend paperbanana")
    if not 1 <= args.num_candidates <= 4:
        parser.error("--num-candidates must be between 1 and 4")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    panel = select_panel(plan, args.panel)
    request = prepare(plan, panel, args.output_dir.resolve(), repo, args.num_candidates, backend_python)
    manifest = args.output_dir.resolve() / "paperbanana-request.json"
    manifest.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.execute:
        print(f"Prepared PaperBanana request -> {manifest}")
        return 0
    if not args.allow_network:
        raise SystemExit("PaperBanana execution requires explicit --allow-network")
    has_env_key = any(os.environ.get(name) for name in request["credential_environment"])
    if not has_env_key and not args.allow_config_credentials:
        raise SystemExit("No supported credential environment variable detected; config credentials require --allow-config-credentials")
    result = subprocess.run(request["command"], cwd=repo)
    if result.returncode != 0:
        return result.returncode
    if not Path(request["expected_output"]).is_file():
        raise SystemExit("PaperBanana completed without the expected output")
    print(request["expected_output"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
