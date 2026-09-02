#!/usr/bin/env python3
"""Self-bootstrapping entry point for Figure Skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import venv
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_ROOT.parent
PLUGIN_ROOT = SKILL_ROOT.parents[1]
LOCK_FILE = SKILL_ROOT / "requirements-lock.txt"
MANIFEST_FILE = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"


def plugin_version() -> str:
    return str(json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))["version"])


def runtime_base() -> Path:
    override = os.environ.get("FIGURE_SKILL_RUNTIME_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    codex_root = os.environ.get("CODEX_HOME", "").strip()
    base = Path(codex_root).expanduser() if codex_root else Path.home() / ".codex"
    return (base / "runtimes" / "figure-skill").resolve()


def runtime_dir() -> Path:
    return runtime_base() / plugin_version()


def runtime_python(root: Path | None = None) -> Path:
    selected = runtime_dir() if root is None else root
    return selected / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def lock_digest() -> str:
    return hashlib.sha256(LOCK_FILE.read_bytes()).hexdigest()


def marker_path(root: Path | None = None) -> Path:
    return (runtime_dir() if root is None else root) / "figure-skill-runtime.json"


def runtime_ready() -> bool:
    python = runtime_python()
    marker = marker_path()
    if not python.is_file() or not marker.is_file():
        return False
    try:
        state = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return state.get("version") == plugin_version() and state.get("requirements_sha256") == lock_digest()


def bootstrap(*, quiet: bool = False) -> Path:
    root = runtime_dir()
    python = runtime_python(root)
    if runtime_ready():
        if not quiet:
            print(f"Figure Skill runtime ready: {root}")
        return python

    root.mkdir(parents=True, exist_ok=True)
    if not python.is_file():
        if sys.version_info < (3, 10):
            raise RuntimeError("Figure Skill requires Python 3.10 or newer")
        if not quiet:
            print(f"Creating isolated Figure Skill runtime: {root}")
        venv.EnvBuilder(with_pip=True, clear=False).create(root)

    if not quiet:
        print("Installing pinned Figure Skill dependencies (first run only)...")
    environment = os.environ.copy()
    environment.setdefault("PYTHONUTF8", "1")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--requirement", str(LOCK_FILE)],
        check=True,
        env=environment,
    )
    subprocess.run([str(python), "-m", "pip", "check"], check=True, env=environment)
    state = {
        "schema_version": "1.0",
        "skill": "figure-skill",
        "version": plugin_version(),
        "requirements_sha256": lock_digest(),
        "python": str(python),
    }
    temporary_marker = marker_path(root).with_suffix(".tmp")
    temporary_marker.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_marker.replace(marker_path(root))
    if not quiet:
        print(f"Figure Skill runtime ready: {root}")
    return python


def run_tool(tool: str, arguments: list[str]) -> int:
    python = bootstrap(quiet=True)
    environment = os.environ.copy()
    environment.setdefault("PYTHONUTF8", "1")
    command = [str(python), str(SCRIPT_ROOT / tool), *arguments]
    return subprocess.run(command, env=environment).returncode


def print_runtime_path() -> int:
    print(runtime_dir())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap and run Figure Skill without depending on the current working directory."
    )
    parser.add_argument("command", choices=("setup", "status", "bootstrap", "backends", "doctor", "workflow", "qa", "review", "runtime-path"))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command in {"setup", "status"}:
        command = [sys.executable, str(SCRIPT_ROOT / "capability_cli.py"), args.command, *args.arguments]
        return subprocess.run(command, env=os.environ.copy()).returncode
    if args.command == "bootstrap":
        if args.arguments:
            parser.error("bootstrap does not accept additional arguments")
        bootstrap()
        return 0
    if args.command == "runtime-path":
        if args.arguments:
            parser.error("runtime-path does not accept additional arguments")
        return print_runtime_path()
    tools = {
        "doctor": "check_environment.py",
        "workflow": "run_workflow.py",
        "qa": "qa_figure.py",
        "review": "review_generated_figure.py",
        "backends": "bootstrap_external_backends.py",
    }
    return run_tool(tools[args.command], args.arguments)


if __name__ == "__main__":
    raise SystemExit(main())
