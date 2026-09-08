from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from planning.routes import choose_route


class RoutingRegressionTests(unittest.TestCase):
    def setUp(self):
        self.inventory = {"files": [{"path": "results.csv", "table_profile": {"data_candidate": True}},
                                    {"path": "README.md"}, {"path": "figure.svg"}],
                          "category_counts": {"table": 1, "narrative": 1, "vector": 1}}

    def test_quantitative_heatmap_is_not_raster_composition(self):
        for brief in ("Draw a heatmap with labeled axes and an axis title", "绘制热力图并标明坐标轴"):
            self.assertEqual(choose_route(self.inventory, brief), "data-plot")

    def test_incidental_readme_does_not_add_a_panel(self):
        self.assertEqual(choose_route(self.inventory, "Plot an accuracy line chart"), "data-plot")

    def test_edit_intent_precedes_incidental_data_and_hybrid_words(self):
        self.assertEqual(choose_route(self.inventory, "Edit the title in the hybrid figure.svg"), "edit")

    def test_explicit_composition_and_override_remain_available(self):
        self.assertEqual(choose_route(self.inventory, "accuracy and method figure"), "composite")
        self.assertEqual(choose_route(self.inventory, "raster video frames and vector modules"), "hybrid-composite")
        self.assertEqual(choose_route(self.inventory, "Edit figure.svg", "data-plot"), "data-plot")


class HybridWorkflowRegressionTests(unittest.TestCase):
    def test_authorized_exact_edit_runs_without_an_extra_plan_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = root / "inputs"
            inputs.mkdir()
            original = '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><text x="20" y="40">Old title</text></svg>'
            (inputs / "figure.svg").write_text(original)
            operations = root / "operations.json"
            operations.write_text(json.dumps([{"op": "replace_text", "old": "Old title", "new": "New title", "expected_matches": 1}]))
            result = subprocess.run([sys.executable, str(SCRIPTS / "run_workflow.py"), "--input", str(inputs),
                                     "--brief", "Edit title from Old title to New title", "--edit-operations", str(operations),
                                     "--approve-plan", "--output", str(root / "output"), "--formats", "svg"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("New title", (root / "output/final/figure.svg").read_text())
            self.assertEqual((inputs / "figure.svg").read_text(), original)

    def test_browser_exports_prepare_review_and_qa_updates_status(self):
        from assemble_figure import find_browser
        if find_browser() is None:
            self.skipTest("local browser unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, svg = self.fixture(root)
            output = root / "output"
            result = self.run_workflow(plan, output, "--hybrid-svg", str(svg), "--formats", "svg,png,pdf")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertTrue((output / "final/figure.pdf").read_bytes().startswith(b"%PDF-"))
            self.assertTrue((output / "final/figure.png").is_file())
            review = json.loads((output / "reports/scientific-review.json").read_text())
            self.assertEqual(review["human_approval"]["status"], "pending")
            # Tampering after export must fail QA and refresh the workflow status.
            (output / "final/figure.svg").write_text('<svg/>')
            result = subprocess.run([sys.executable, str(SCRIPTS / "qa_figure.py"), str(output),
                                     "--plan", str(output / "figure-plan.json"),
                                     "--output", str(output / "reports/qa-report.json")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            status = json.loads((output / "reports/workflow-status.json").read_text())
            self.assertEqual(status["status"], "qa-failed")
            self.assertFalse(status["complete"])

    def fixture(self, root):
        from PIL import Image
        asset = root / "frame.png"
        Image.new("RGB", (400, 300), "white").save(asset)
        uri = "data:image/png;base64," + base64.b64encode(asset.read_bytes()).decode()
        svg = root / "source.svg"
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">'
                       f'<image data-role="frame" href="{uri}" width="100" height="100"/>'
                       '<rect data-role="module" x="120" y="20" width="100" height="80"/></svg>', encoding="utf-8")
        plan = {"route": "hybrid-composite", "input_root": str(root), "open_questions": [],
                "constraints": {"forbid_invented_quantitative_claims": True},
                "panels": [{"id": "A", "type": "hybrid-composite", "canvas": {"width": 400, "height": 300},
                            "representation_contract": {"roles": [
                                {"role": "frame", "kind": "raster", "svg_tag": "image", "expected_count": 1, "source_glob": "frame.png"},
                                {"role": "module", "kind": "vector", "svg_tag": "rect", "expected_count": 1}],
                                "unclassified_image_policy": "forbid"}}]}
        path = root / "plan.json"
        path.write_text(json.dumps(plan), encoding="utf-8")
        return path, svg

    def run_workflow(self, plan, output, *extra):
        return subprocess.run([sys.executable, str(SCRIPTS / "run_workflow.py"), "--plan", str(plan),
                               "--output", str(output), "--approve-plan", "--formats", "svg", *extra],
                              capture_output=True, text=True)

    def test_handoff_resumes_to_audited_artifact_without_claiming_review_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, svg = self.fixture(root)
            output = root / "output"
            result = self.run_workflow(plan, output)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            status = json.loads((output / "reports/workflow-status.json").read_text())
            self.assertEqual(status["status"], "awaiting-hybrid-svg")
            self.assertFalse((output / "final/figure.svg").exists())
            result = self.run_workflow(output / "figure-plan.json", output, "--hybrid-svg", str(svg))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual((output / "final/figure.svg").read_bytes(), svg.read_bytes())
            audit = json.loads((output / "reports/hybrid-structure-audit.json").read_text())
            self.assertEqual(audit["status"], "pass")
            self.assertTrue(Path(audit["source"]).samefile(output / "final/figure.svg"))
            qa = json.loads((output / "reports/qa-report.json").read_text())
            self.assertEqual(qa["status"], "warn")
            self.assertFalse(any(item["status"] == "fail" for item in qa["checks"]), qa)
            # Existing renders cannot be silently overwritten on another resume.
            result = self.run_workflow(output / "figure-plan.json", output, "--hybrid-svg", str(svg))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not empty", result.stderr)

    def test_invalid_contract_fails_before_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, svg = self.fixture(root)
            svg.write_text(svg.read_text().replace('data-role="module"', 'data-role="wrong"'))
            result = self.run_workflow(plan, root / "output", "--hybrid-svg", str(svg))
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertFalse((root / "output/final/figure.svg").exists())

    def test_open_questions_still_block_authorized_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, svg = self.fixture(root)
            data = json.loads(plan.read_text())
            data["open_questions"] = ["Confirm arrow meaning"]
            plan.write_text(json.dumps(data))
            result = self.run_workflow(plan, root / "output", "--hybrid-svg", str(svg))
            self.assertEqual(result.returncode, 2)
            self.assertFalse((root / "output/final/figure.svg").exists())


if __name__ == "__main__":
    unittest.main()
