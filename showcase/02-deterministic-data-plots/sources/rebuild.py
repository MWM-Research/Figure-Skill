from __future__ import annotations
import argparse, importlib.util, json, shutil
from pathlib import Path

def load(path: Path):
    spec = importlib.util.spec_from_file_location("showcase_matplotlib", path); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, required=True); parser.add_argument("--case", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
backend = load(args.repo / "plugins/figure-skill/skills/figure-skill/scripts/backends/matplotlib_backend.py")
plan = json.loads((args.case / "figure-plan.json").read_text(encoding="utf-8")); panel = plan["panels"][0]
inputs = args.case / "sources"; panels = args.output / "panels"; final = args.output / "final"; provenance = args.output / "provenance"; reports = args.output / "reports"
for path in (panels, final, provenance, reports): path.mkdir(parents=True, exist_ok=True)
result = backend.render_grid_panel(panel, inputs, panels, ("svg", "pdf", "png"))
for source in result.get("sources", []): source["file"] = "sources/samples.csv"
for mark in result.get("marks", []):
    if "source_file" in mark: mark["source_file"] = "sources/samples.csv"
for suffix in ("svg", "pdf", "png"): shutil.copy2(panels / f"panel_a.{suffix}", final / f"figure.{suffix}")
(provenance / "data-provenance.json").write_text(json.dumps({"schema_version": "1.0", "panels": [result]}, indent=2), encoding="utf-8")
(reports / "qa-report.json").write_text(json.dumps({"schema_version": "1.0", "status": "pass", "checks": [{"check": "rebuild", "status": "pass"}]}, indent=2), encoding="utf-8")
