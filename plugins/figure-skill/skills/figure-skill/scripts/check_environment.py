#!/usr/bin/env python3
"""Check core and optional Figure Skill runtime capabilities."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Mapping


def module_status(name: str) -> dict:
    spec = importlib.util.find_spec(name)
    if spec is None:
        return {"available": False, "version": None}
    try:
        module = __import__(name)
        version = getattr(module, "__version__", None)
    except Exception as exc:  # dependency import errors are part of environment diagnosis
        return {"available": False, "version": None, "error": str(exc)}
    return {"available": True, "version": version}


def browser_path() -> str | None:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ]
    for command in ("msedge", "google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(command)
        if found:
            candidates.append(Path(found))
    found = next((path for path in candidates if path.is_file()), None)
    return str(found) if found else None


def windows_persistent_scopes(name: str) -> list[str]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []
    locations = (
        ("user", winreg.HKEY_CURRENT_USER, r"Environment"),
        ("machine", winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    )
    scopes = []
    for label, hive, subkey in locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, name)
            if isinstance(value, str) and value.strip():
                scopes.append(label)
        except OSError:
            continue
    return scopes


def credential_status(
    name: str,
    process_env: Mapping[str, str] | None = None,
    persistent_lookup: Callable[[str], list[str]] | None = None,
) -> dict:
    environment = os.environ if process_env is None else process_env
    lookup = windows_persistent_scopes if persistent_lookup is None else persistent_lookup
    scopes = []
    value = environment.get(name)
    if isinstance(value, str) and value.strip():
        scopes.append("process")
    for scope in lookup(name):
        if scope not in scopes:
            scopes.append(scope)
    return {"available": bool(scopes), "scopes": scopes}


def inspect(paperbanana_repo: Path | None, autofigure_repo: Path | None) -> dict:
    matplotlib = module_status("matplotlib")
    openpyxl = module_status("openpyxl")
    browser = browser_path()
    credential_names = (
        "OPENAI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY",
        "BIANXIE_API_KEY", "AUTOFIGURE_API_KEY", "FAL_KEY", "ROBOFLOW_API_KEY",
        "FIGURE_IMAGE_API_KEY",
    )
    credentials = {name: credential_status(name) for name in credential_names}
    paperbanana_available = bool(paperbanana_repo and (paperbanana_repo / "skill" / "run.py").is_file())
    autofigure_available = bool(autofigure_repo and (autofigure_repo / "autofigure2.py").is_file())
    external_root = Path(os.environ.get("FIGURE_SKILL_EXTERNAL_ROOT", "")).expanduser() if os.environ.get("FIGURE_SKILL_EXTERNAL_ROOT") else Path(sys.executable).resolve().parent.parent / "external"
    paper_python = external_root / "venvs" / "paperbanana" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    auto_python = external_root / "venvs" / "autofigure-edit" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    paperbanana_available = paperbanana_available and paper_python.is_file()
    autofigure_available = autofigure_available and auto_python.is_file()
    core_ready = sys.version_info >= (3, 10) and matplotlib["available"] and openpyxl["available"] and bool(browser)
    return {
        "schema_version": "1.0",
        "python": {
            "executable": sys.executable,
            "version": ".".join(str(part) for part in sys.version_info[:3]),
            "supported": sys.version_info >= (3, 10),
        },
        "core": {
            "ready": core_ready,
            "matplotlib": matplotlib,
            "openpyxl": openpyxl,
            "browser": {"available": bool(browser), "path": browser},
        },
        "optional": {
            "drawio_npx": {"available": bool(shutil.which("npx")), "command": shutil.which("npx")},
            "paperbanana_repo": {
                "available": paperbanana_available,
                "status": "ready" if paperbanana_available else "optional-not-installed",
                "path": str(paperbanana_repo.resolve()) if paperbanana_repo else None,
                "python": str(paper_python) if paper_python.is_file() else None,
            },
            "autofigure_edit_repo": {
                "available": autofigure_available,
                "status": "ready" if autofigure_available else "optional-not-installed",
                "path": str(autofigure_repo.resolve()) if autofigure_repo else None,
                "python": str(auto_python) if auto_python.is_file() else None,
            },
            "ai_enhancement": {
                "available": paperbanana_available or autofigure_available,
                "status": "ready" if (paperbanana_available or autofigure_available) else "optional-disabled",
                "blocks_core_workflow": False,
            },
            "byok_raster_illustration": {
                "available": credentials["FIGURE_IMAGE_API_KEY"]["available"],
                "status": "ready" if credentials["FIGURE_IMAGE_API_KEY"]["available"] else "optional-not-configured",
                "required_environment": ["FIGURE_IMAGE_API_KEY"],
                "optional_overrides": ["FIGURE_IMAGE_BASE_URL", "FIGURE_IMAGE_MODEL"],
                "default_protocol": "openai-compatible-images",
                "blocks_core_workflow": False,
            },
            "credential_presence": {
                name: status["available"] for name, status in credentials.items()
            },
            "credential_scopes": {name: status["scopes"] for name, status in credentials.items()},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paperbanana-repo", type=Path)
    parser.add_argument("--autofigure-repo", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    runtime_external = Path(os.environ.get("FIGURE_SKILL_EXTERNAL_ROOT", "")).expanduser() if os.environ.get("FIGURE_SKILL_EXTERNAL_ROOT") else Path(sys.executable).resolve().parent.parent / "external"
    paperbanana_repo = args.paperbanana_repo or runtime_external / "upstreams" / "PaperBanana"
    autofigure_repo = args.autofigure_repo or runtime_external / "upstreams" / "AutoFigure-Edit"
    report = inspect(paperbanana_repo, autofigure_repo)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if report["core"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
