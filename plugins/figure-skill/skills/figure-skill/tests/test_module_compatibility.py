from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
BACKENDS = SCRIPTS / "backends"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module); return module


class CompatibilityEntryPointTests(unittest.TestCase):
    def test_compatibility_entrypoints_are_thin_and_export_public_api(self):
        if str(SCRIPTS) not in sys.path: sys.path.insert(0, str(SCRIPTS))
        plotting = load("compat_plotting", BACKENDS / "matplotlib_backend.py")
        planning = load("compat_planning", SCRIPTS / "plan_figure.py")
        quality = load("compat_quality", SCRIPTS / "qa_figure.py")
        self.assertTrue(all(hasattr(plotting, name) for name in ("read_records", "render_panel", "render_grid_panel", "main")))
        self.assertTrue(all(hasattr(planning, name) for name in ("ROUTES", "choose_route", "choose_chart", "data_panels", "build_plan", "main")))
        self.assertTrue(all(hasattr(quality, name) for name in ("run_qa", "verify_data_provenance", "verify_edit_provenance", "verify_generation_provenance", "verify_hybrid_audit", "main")))
        for path in (BACKENDS / "matplotlib_backend.py", SCRIPTS / "plan_figure.py", SCRIPTS / "qa_figure.py"):
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 150, path)

    def test_internal_modules_stay_bounded_and_do_not_cross_domains(self):
        domains = {"plotting": BACKENDS / "plotting", "planning": SCRIPTS / "planning", "quality": SCRIPTS / "quality"}
        for domain, root in domains.items():
            for path in root.glob("*.py"):
                self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 300, path)
                tree = ast.parse(path.read_text(encoding="utf-8"))
                imports = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names] + [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
                forbidden = ({"plotting", "planning", "quality"} - {domain})
                self.assertFalse(any(any(name == value or name.startswith(value + ".") for value in forbidden) for name in imports), path)

    def test_copied_plot_source_runs_outside_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / "data.csv"; source.write_text("method,value\nA,1\nB,2\n", encoding="utf-8"); output = root / "first"; output.mkdir()
            panel = {"id": "A", "type": "data-plot", "title": "Values", "source_files": ["data.csv"], "visual_form": "bar-chart", "x": "method", "y": "value"}
            plan = {"input_root": str(root), "open_questions": [], "panels": [panel]}; plan_path = root / "plan.json"; plan_path.write_text(json.dumps(plan), encoding="utf-8")
            first = subprocess.run([sys.executable, str(BACKENDS / "matplotlib_backend.py"), str(plan_path), "--input-root", str(root), "--output-dir", str(output), "--formats", "svg"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            self.assertEqual(first.returncode, 0, first.stderr)
            second = root / "second"
            result = subprocess.run([sys.executable, str(output / "panel_a_source.py"), str(plan_path), "--input-root", str(root), "--output-dir", str(second), "--formats", "svg"], cwd=output, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr); self.assertTrue((second / "panel_a.svg").is_file()); self.assertTrue((output / "plotting" / "renderer.py").is_file()); self.assertTrue((output / "statistics_core.py").is_file())

    def test_original_cli_paths_still_have_help(self):
        for path in (BACKENDS / "matplotlib_backend.py", SCRIPTS / "plan_figure.py", SCRIPTS / "qa_figure.py"):
            result = subprocess.run([sys.executable, str(path), "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")


if __name__ == "__main__": unittest.main()
