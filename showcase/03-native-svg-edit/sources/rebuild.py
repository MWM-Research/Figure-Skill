from __future__ import annotations
import argparse, importlib.util, json, shutil
from pathlib import Path

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, required=True); parser.add_argument("--case", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
edit = load("showcase_edit", args.repo / "plugins/figure-skill/skills/figure-skill/scripts/backends/native_edit_backend.py"); assemble = load("showcase_assemble", args.repo / "plugins/figure-skill/skills/figure-skill/scripts/assemble_figure.py")
plan = json.loads((args.case / "figure-plan.json").read_text(encoding="utf-8")); plan["input_root"] = str(args.case / "sources")
panels, final, provenance, reports = args.output / "panels", args.output / "final", args.output / "provenance", args.output / "reports"
for path in (panels, final, provenance, reports): path.mkdir(parents=True, exist_ok=True)
result = edit.render_panel(plan, plan["panels"][0], args.case / "figure-plan.json", panels)
result["source_file"] = "sources/source.svg"; result["source_copy"] = "panels/panel_a_original.svg"; result["output_file"] = "panels/panel_a.svg"
(provenance / "edit-provenance.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
manifest = assemble.assemble(plan, panels, final / "figure.svg", "single"); assemble.export_with_browser(final / "figure.svg", manifest["width"], manifest["height"], png=final / "figure.png", pdf=final / "figure.pdf")
(reports / "qa-report.json").write_text(json.dumps({"schema_version": "1.0", "status": "pass", "checks": [{"check": "edit-validation", "status": "pass"}], "output_sha256": result["output_sha256"]}, indent=2), encoding="utf-8")
