#!/usr/bin/env python3
"""Install and verify pinned PaperBanana and AutoFigure-Edit runtimes on demand."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import venv
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = SKILL_ROOT.parents[1]
MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
BACKENDS = {
    "paperbanana": {
        "url": "https://github.com/dwzhu-pku/PaperBanana.git",
        "commit": "836455537e863b5a2f40dace487a782c0bc5ef94",
        "repo_name": "PaperBanana",
        "entrypoint": "skill/run.py",
    },
    "autofigure-edit": {
        "url": "https://github.com/ResearAI/AutoFigure-Edit.git",
        "commit": "16f3749e9d512bdf7b7b55c162307bc289750b7a",
        "repo_name": "AutoFigure-Edit",
        "entrypoint": "autofigure2.py",
    },
}


def plugin_version() -> str:
    return str(json.loads(MANIFEST.read_text(encoding="utf-8"))["version"])


def runtime_base() -> Path:
    override = os.environ.get("FIGURE_SKILL_RUNTIME_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    codex_root = os.environ.get("CODEX_HOME", "").strip()
    base = Path(codex_root).expanduser() if codex_root else Path.home() / ".codex"
    return (base / "runtimes" / "figure-skill").resolve()


def external_root() -> Path:
    return runtime_base() / plugin_version() / "external"


def venv_python(path: Path) -> Path:
    return path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paths_for(name: str) -> dict:
    config = BACKENDS[name]
    root = external_root()
    repo = root / "upstreams" / str(config["repo_name"])
    environment = root / "venvs" / name
    return {
        "repo": repo,
        "python": venv_python(environment),
        "venv": environment,
        "entrypoint": repo / str(config["entrypoint"]),
        "marker": environment / "figure-backend-runtime.json",
    }


def run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def ensure_git() -> str:
    executable = shutil.which("git")
    if not executable:
        raise RuntimeError("Git is required to install external Figure Skill backends")
    return executable


def current_commit(repo: Path) -> str | None:
    if not (repo / ".git").is_dir():
        return None
    result = subprocess.run(
        [ensure_git(), "-C", str(repo), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def ensure_repo(name: str) -> Path:
    config = BACKENDS[name]
    paths = paths_for(name)
    repo = paths["repo"]
    repo.parent.mkdir(parents=True, exist_ok=True)
    git = ensure_git()
    if not (repo / ".git").is_dir():
        if repo.exists() and any(repo.iterdir()):
            raise RuntimeError(f"external backend path exists but is not a Git repository: {repo}")
        run([git, "clone", "--filter=blob:none", "--no-checkout", str(config["url"]), str(repo)])
    if current_commit(repo) != config["commit"]:
        run([git, "-C", str(repo), "fetch", "--depth", "1", "origin", str(config["commit"])])
        run([git, "-C", str(repo), "checkout", "--detach", str(config["commit"])])
    return repo


def ensure_environment(name: str, recreate: bool = False) -> Path:
    paths = paths_for(name)
    python = paths["python"]
    if recreate or not python.is_file():
        paths["venv"].parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True, clear=recreate).create(paths["venv"])
    return python


def install_backend(name: str, recreate: bool = False) -> dict:
    config = BACKENDS[name]
    repo = ensure_repo(name)
    python = ensure_environment(name, recreate)
    requirements = repo / "requirements.txt"
    if not requirements.is_file():
        raise RuntimeError(f"requirements.txt is missing for {name}")
    environment = os.environ.copy()
    environment.setdefault("PYTHONUTF8", "1")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)],
        check=True, env=environment,
    )
    subprocess.run([str(python), "-m", "pip", "check"], check=True, env=environment)
    subprocess.run(
        [str(python), str(repo / str(config["entrypoint"])), "--help"],
        check=True, stdout=subprocess.DEVNULL, env=environment,
    )
    state = {
        "schema_version": "1.0",
        "backend": name,
        "commit": config["commit"],
        "requirements_sha256": sha256(requirements),
        "python": str(python),
    }
    marker = paths_for(name)["marker"]
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(marker)
    return backend_status(name)


def backend_status(name: str) -> dict:
    config = BACKENDS[name]
    paths = paths_for(name)
    commit = current_commit(paths["repo"])
    requirements = paths["repo"] / "requirements.txt"
    try:
        state = json.loads(paths["marker"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    marker_valid = bool(
        requirements.is_file()
        and state.get("backend") == name
        and state.get("commit") == config["commit"]
        and state.get("requirements_sha256") == sha256(requirements)
        and state.get("python") == str(paths["python"])
    )
    ready = (
        commit == config["commit"]
        and paths["python"].is_file()
        and paths["entrypoint"].is_file()
        and marker_valid
    )
    return {
        "name": name,
        "ready": ready,
        "status": "ready" if ready else "not-installed",
        "repo": str(paths["repo"]),
        "python": str(paths["python"]),
        "entrypoint": str(paths["entrypoint"]),
        "expected_commit": config["commit"],
        "actual_commit": commit,
        "install_marker": str(paths["marker"]),
        "marker_valid": marker_valid,
    }


def status_report() -> dict:
    return {
        "schema_version": "1.0",
        "figure_skill_version": plugin_version(),
        "external_root": str(external_root()),
        "backends": {name: backend_status(name) for name in BACKENDS},
    }


def acquire_lock() -> Path:
    root = external_root()
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".install.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        age = time.time() - lock.stat().st_mtime
        raise RuntimeError(f"another backend installation may be running (lock age {age:.0f}s): {lock}") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"pid": os.getpid(), "created_at": time.time()}))
    return lock


def write_report(report: dict) -> Path:
    path = external_root() / "setup-report.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    install = subparsers.add_parser("install")
    install.add_argument("--backend", choices=("all",) + tuple(BACKENDS), default="all")
    install.add_argument("--recreate", action="store_true")
    subparsers.add_parser("status")
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(status_report(), ensure_ascii=False, indent=2))
        return 0
    selected = list(BACKENDS) if args.backend == "all" else [args.backend]
    lock = acquire_lock()
    try:
        for name in selected:
            print(f"Installing pinned backend: {name}")
            install_backend(name, args.recreate)
        report = status_report()
        report_path = write_report(report)
    finally:
        lock.unlink(missing_ok=True)
    missing = [name for name in selected if not report["backends"][name]["ready"]]
    if missing:
        raise SystemExit(f"backend installation incomplete: {', '.join(missing)}")
    print(f"External Figure Skill backends ready -> {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
