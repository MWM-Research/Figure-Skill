"""Resolve versioned external backend paths installed by Figure Skill."""

from __future__ import annotations

import json
import os
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = SKILL_ROOT.parents[1]
MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"


def plugin_version() -> str:
    return str(json.loads(MANIFEST.read_text(encoding="utf-8"))["version"])


def runtime_root() -> Path:
    override = os.environ.get("FIGURE_SKILL_RUNTIME_ROOT", "").strip()
    if override:
        base = Path(override).expanduser().resolve()
    else:
        codex_root = os.environ.get("CODEX_HOME", "").strip()
        root = Path(codex_root).expanduser() if codex_root else Path.home() / ".codex"
        base = (root / "runtimes" / "figure-skill").resolve()
    return base / plugin_version()


def backend_paths(name: str) -> dict[str, Path]:
    external = runtime_root() / "external"
    repo_names = {"paperbanana": "PaperBanana", "autofigure-edit": "AutoFigure-Edit"}
    entrypoints = {"paperbanana": "skill/run.py", "autofigure-edit": "autofigure2.py"}
    if name not in repo_names:
        raise ValueError(f"unknown external backend: {name}")
    environment = external / "venvs" / name
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    repo = external / "upstreams" / repo_names[name]
    return {"external": external, "repo": repo, "python": python, "entrypoint": repo / entrypoints[name]}
