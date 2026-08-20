#!/usr/bin/env python3
"""Run the deterministic scientific-figure workflow from inputs to QA."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from inventory_inputs import inventory
from plan_figure import ROUTES, build_plan


HERE = Path(__file__).resolve().parent


def run_checked(command: list[str]) -> None:
    result = subprocess.run(command)
    if result.returncode != 0:
        raise RuntimeError(f"command failed with exit code {result.returncode}: {' '.join(command)}")


def ensure_output_scope(output: Path, *, continuing: bool, force: bool) -> None:
    if not output.exists():
        output.mkdir(parents=True)
        return
    existing = list(output.iterdir())
    if not existing:
        return
    if force:
        return
    allowed = {"inventory.json", "figure-plan.json"} if continuing else set()
    unexpected = [path.name for path in existing if path.name not in allowed]
    if unexpected:
        raise FileExistsError(
            f"output directory is not empty ({', '.join(sorted(unexpected))}); choose another directory or pass --force"
        )


def collect_provenance(panels_dir: Path, provenance_dir: Path) -> None:
    provenance_dir.mkdir(parents=True, exist_ok=True)
    mappings = {
        "provenance.json": "data-provenance.json",
        "diagram-provenance.json": "diagram-provenance.json",
        "edit-provenance.json": "edit-provenance.json",
    }
    for source_name, target_name in mappings.items():
        source = panels_dir / source_name
        if source.is_file():
            shutil.move(str(source), provenance_dir / target_name)


def collect_sources(panels_dir: Path, sources_dir: Path) -> None:
    sources_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("panel_*_source.py", "panel_*_original.svg", "render-recipe.json"):
        for source in panels_dir.glob(pattern):
            shutil.move(str(source), sources_dir / source.name)


def create_plan(args, output: Path) -> tuple[dict, Path]:
    inventory_path = output / "inventory.json"
    plan_path = output / "figure-plan.json"
    if args.plan:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        return plan, plan_path

    result = inventory(args.input.resolve())
    inventory_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    brief = args.brief_file.read_text(encoding="utf-8-sig").strip() if args.brief_file else args.brief
    operations = json.loads(args.edit_operations.read_text(encoding="utf-8")) if args.edit_operations else None
    if operations is not None and not isinstance(operations, list):
        raise ValueError("--edit-operations must contain a JSON array")
    plan = build_plan(result, brief, args.route, operations)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan, plan_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Directory containing research inputs")
    source.add_argument("--plan", type=Path, help="Existing reviewed figure-plan.json")
    parser.add_argument("--brief", default="")
    parser.add_argument("--brief-file", type=Path)
    parser.add_argument("--route", choices=("auto",) + ROUTES, default="auto")
    parser.add_argument("--edit-operations", type=Path, help="JSON array of explicit SVG edit operations")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--formats", default="svg,pdf,png")
    parser.add_argument("--layout", choices=("auto", "single", "horizontal", "vertical", "grid"), default="auto")
    parser.add_argument("--stop-after-plan", action="store_true")
    parser.add_argument("--approve-plan", action="store_true", help="Confirm that the plan and inferred relationships were reviewed")
    parser.add_argument("--force", action="store_true", help="Allow overwriting files in the selected output directory")
    args = parser.parse_args()

    if args.input and not args.input.is_dir():
        parser.error(f"input directory does not exist: {args.input}")
    if args.plan and not args.plan.is_file():
        parser.error(f"plan does not exist: {args.plan}")
    output = args.output.resolve()
    ensure_output_scope(output, continuing=bool(args.plan), force=args.force)
    plan, plan_path = create_plan(args, output)
    print(f"Planned route {plan.get('route')} with {len(plan.get('panels', []))} panel(s): {plan_path}")
    if args.stop_after_plan:
        return 0
    if not args.approve_plan:
        print("Rendering stopped for human review. Re-run with --plan <figure-plan.json> --approve-plan.")
        return 2
    if plan.get("open_questions"):
        print("Cannot approve a plan with unresolved open_questions:")
        for question in plan["open_questions"]:
            print(f"- {question}")
        return 2
    plan["review_status"] = "approved"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    panels_dir = output / "panels"
    sources_dir = output / "sources"
    final_dir = output / "final"
    reports_dir = output / "reports"
    provenance_dir = output / "provenance"
    for directory in (panels_dir, sources_dir, final_dir, reports_dir, provenance_dir):
        directory.mkdir(parents=True, exist_ok=True)

    panel_types = {panel.get("type") for panel in plan.get("panels", [])}
    if "illustration" in panel_types:
        run_checked([
            sys.executable, str(HERE / "backends" / "svg_diagram_backend.py"), str(plan_path),
            "--output-dir", str(panels_dir),
        ])
        run_checked([
            sys.executable, str(HERE / "adapters" / "drawio_adapter.py"), str(plan_path),
            "--output-dir", str(sources_dir),
        ])
        run_checked([
            sys.executable, str(HERE / "adapters" / "happy_figure_adapter.py"), str(plan_path),
            "--output", str(sources_dir / "happy-figure-handoff.json"),
        ])
    if "data-plot" in panel_types:
        run_checked([
            sys.executable, str(HERE / "backends" / "matplotlib_backend.py"), str(plan_path),
            "--output-dir", str(panels_dir), "--formats", args.formats,
        ])
    if "edit" in panel_types:
        run_checked([
            sys.executable, str(HERE / "backends" / "native_edit_backend.py"), str(plan_path),
            "--output-dir", str(panels_dir),
        ])
    collect_sources(panels_dir, sources_dir)
    collect_provenance(panels_dir, provenance_dir)
    run_checked([
        sys.executable, str(HERE / "assemble_figure.py"), str(plan_path),
        "--panels-dir", str(panels_dir), "--output-dir", str(final_dir),
        "--layout", args.layout, "--formats", args.formats,
    ])
    run_checked([
        sys.executable, str(HERE / "qa_figure.py"), str(output),
        "--plan", str(plan_path), "--output", str(reports_dir / "qa-report.json"),
    ])
    print(f"Workflow complete -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
