#!/usr/bin/env python3
"""Install Figure Skill capability profiles and print a credential-safe status matrix."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import bootstrap_external_backends as external  # noqa: E402
import check_environment as environment_check  # noqa: E402
import figure as launcher  # noqa: E402


PROFILES = {
    "core": {"backends": [], "required": ["deterministic-plots", "native-svg", "hybrid-figure"]},
    "vectorize": {"backends": ["autofigure-edit"], "required": ["deterministic-plots", "native-svg", "hybrid-figure", "png-to-svg"]},
    "illustration": {"backends": ["paperbanana"], "required": ["deterministic-plots", "native-svg", "hybrid-figure", "paperbanana-illustration", "byok-raster-illustration"]},
    "all": {"backends": ["paperbanana", "autofigure-edit"], "required": ["deterministic-plots", "native-svg", "hybrid-figure", "png-to-svg", "paperbanana-illustration", "byok-raster-illustration"]},
}

CAPABILITY_LABELS = {
    "deterministic-plots": "Deterministic plots",
    "native-svg": "Native SVG diagrams",
    "hybrid-figure": "Hybrid Figure",
    "png-to-svg": "PNG to SVG",
    "paperbanana-illustration": "PaperBanana illustration",
    "byok-raster-illustration": "BYOK raster illustration",
}


def credential(name: str) -> dict[str, Any]:
    status = environment_check.credential_status(name)
    return {"name": name, "available": status["available"], "scopes": status["scopes"]}


def backend_state(name: str, credentials: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    backend = external.backend_status(name)
    if not backend["ready"]:
        state = "degraded" if backend.get("actual_commit") or backend.get("marker_valid") else "missing-dependency"
    elif any(item["available"] for item in credentials):
        state = "ready"
    else:
        state = "installed-needs-credential"
    return state, {"backend": name, "ready": backend["ready"], "required_credentials": [item["name"] for item in credentials], "credential_presence": {item["name"]: item["available"] for item in credentials}}


def capability_report() -> dict[str, Any]:
    browser = environment_check.browser_path()
    marker_exists = launcher.marker_path().is_file()
    core_ready = launcher.runtime_ready() and bool(browser)
    core_state = "ready" if core_ready else ("degraded" if marker_exists else "missing-dependency")
    auto_credentials = [credential("AUTOFIGURE_API_KEY")]
    paper_credentials = [credential("GOOGLE_API_KEY"), credential("OPENROUTER_API_KEY")]
    raster_credentials = [credential("FIGURE_IMAGE_API_KEY")]
    auto_state, auto_details = backend_state("autofigure-edit", auto_credentials)
    paper_state, paper_details = backend_state("paperbanana", paper_credentials)
    raster_state = "ready" if core_ready and raster_credentials[0]["available"] else ("missing-credential" if core_ready else core_state)
    capabilities = [
        {"id": "deterministic-plots", "label": CAPABILITY_LABELS["deterministic-plots"], "status": core_state, "details": {"runtime": str(launcher.runtime_dir()), "browser_available": bool(browser)}},
        {"id": "native-svg", "label": CAPABILITY_LABELS["native-svg"], "status": core_state, "details": {"runtime": str(launcher.runtime_dir())}},
        {"id": "hybrid-figure", "label": CAPABILITY_LABELS["hybrid-figure"], "status": core_state, "details": {"runtime": str(launcher.runtime_dir())}},
        {"id": "png-to-svg", "label": CAPABILITY_LABELS["png-to-svg"], "status": auto_state, "details": auto_details},
        {"id": "paperbanana-illustration", "label": CAPABILITY_LABELS["paperbanana-illustration"], "status": paper_state, "details": paper_details},
        {"id": "byok-raster-illustration", "label": CAPABILITY_LABELS["byok-raster-illustration"], "status": raster_state, "details": {"required_credentials": ["FIGURE_IMAGE_API_KEY"], "credential_presence": {"FIGURE_IMAGE_API_KEY": raster_credentials[0]["available"]}}},
    ]
    return {"schema_version": "1.0", "figure_skill_version": launcher.plugin_version(), "core_ready": core_ready, "runtime": str(launcher.runtime_dir()), "capabilities": capabilities}


def profile_ready(report: dict[str, Any], profile: str) -> bool:
    states = {item["id"]: item["status"] for item in report["capabilities"]}
    return all(states.get(capability) == "ready" for capability in PROFILES[profile]["required"])


def install_plan(profile: str, recreate: bool) -> dict[str, Any]:
    selected = PROFILES[profile]
    actions = [{"action": "bootstrap-core", "runtime": str(launcher.runtime_dir()), "recreate": False}]
    actions.extend({"action": "install-backend", "backend": backend, "recreate": recreate} for backend in selected["backends"])
    return {"schema_version": "1.0", "profile": profile, "default_profile": "all", "large_download_expected": bool(selected["backends"]), "credentials_are_never_written": True, "actions": actions}


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def print_status(report: dict[str, Any]) -> None:
    width = max(len(item["label"]) for item in report["capabilities"])
    print(f"{'Capability'.ljust(width)}  Status")
    print(f"{'-' * width}  --------------------------")
    for item in report["capabilities"]:
        print(f"{item['label'].ljust(width)}  {item['status']}")


def choose_profile_interactively() -> str:
    print("Figure Skill setup profiles:")
    print("  1. all (default) - Core, PaperBanana, AutoFigure-Edit")
    print("  2. core - deterministic features only")
    print("  3. vectorize - Core and AutoFigure-Edit")
    print("  4. illustration - Core and PaperBanana")
    try:
        selected = input("Select profile [1]: ").strip()
    except EOFError as exc:
        raise RuntimeError("interactive input is unavailable") from exc
    return {"": "all", "1": "all", "2": "core", "3": "vectorize", "4": "illustration"}.get(selected, selected)


def confirm(profile: str) -> bool:
    backends = PROFILES[profile]["backends"]
    print(f"Selected profile: {profile}")
    print("Large ML dependency download: " + ("yes (several GB possible)" if backends else "no"))
    print("Provider credentials will not be requested or stored.")
    try:
        return input("Proceed? [y/N]: ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def setup_command(arguments: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="figure setup")
    parser.add_argument("--profile", choices=tuple(PROFILES))
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(arguments)
    interactive = sys.stdin.isatty() and sys.stdout.isatty() and not os.environ.get("CI")
    profile = args.profile
    if profile is None:
        if not interactive:
            parser.error("non-interactive setup requires --profile and --yes; use --dry-run to inspect the plan")
        try:
            profile = choose_profile_interactively()
        except RuntimeError:
            parser.error("interactive input is unavailable; setup requires --profile and --yes")
        if profile not in PROFILES:
            parser.error(f"unknown profile: {profile}")
    plan = install_plan(profile, args.recreate)
    if args.dry_run:
        text = json.dumps(plan, ensure_ascii=False, indent=2)
        if args.output:
            write_json_atomic(args.output.resolve(), plan)
        print(text)
        return 0
    if not args.yes:
        if not interactive:
            parser.error("non-interactive setup requires --yes")
        if not confirm(profile):
            print("Setup cancelled; no changes made.")
            return 2
    launcher.bootstrap()
    backends = PROFILES[profile]["backends"]
    if backends:
        backend_arg = "all" if len(backends) == 2 else backends[0]
        command = [sys.executable, str(HERE / "bootstrap_external_backends.py"), "install", "--backend", backend_arg]
        if args.recreate:
            command.append("--recreate")
        subprocess.run(command, check=True)
    report = capability_report()
    report["setup"] = {"profile": profile, "status": "installed" if profile_ready(report, "core") else "degraded", "credentials_written": False, "plan": plan}
    report_path = launcher.runtime_dir() / "capability-report.json"
    write_json_atomic(report_path, report)
    if args.output:
        write_json_atomic(args.output.resolve(), report)
    print_status(report)
    print(f"Capability report: {report_path}")
    missing_credentials = [item["label"] for item in report["capabilities"] if item["status"] in {"installed-needs-credential", "missing-credential"}]
    if missing_credentials:
        print("Installed successfully. Credentials can be configured later for: " + ", ".join(missing_credentials))
    return 0 if report["core_ready"] else 1


def status_command(arguments: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="figure status")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-profile", choices=tuple(PROFILES))
    args = parser.parse_args(arguments)
    report = capability_report()
    if args.output:
        write_json_atomic(args.output.resolve(), report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_status(report)
    if not report["core_ready"]:
        return 1
    if args.require_profile and not profile_ready(report, args.require_profile):
        return 2
    return 0


def main(command: str | None = None, arguments: list[str] | None = None) -> int:
    selected = command or (sys.argv[1] if len(sys.argv) > 1 else None)
    rest = arguments if arguments is not None else sys.argv[2:]
    if selected == "setup":
        return setup_command(rest)
    if selected == "status":
        return status_command(rest)
    raise SystemExit("capability_cli.py requires setup or status")


if __name__ == "__main__":
    raise SystemExit(main())
