from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "adapters"))

import inventory_inputs  # noqa: E402
import plan_figure  # noqa: E402


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def load_backend():
    return load_module("matplotlib_backend", SCRIPTS / "backends" / "matplotlib_backend.py")


def load_edit_backend():
    return load_module("native_edit_backend", SCRIPTS / "backends" / "native_edit_backend.py")


def load_environment_checker():
    return load_module("check_environment", SCRIPTS / "check_environment.py")


class InventoryTests(unittest.TestCase):
    def test_profiles_csv_columns_and_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "results.csv").write_text(
                "method,accuracy,latency_ms\nBaseline,0.81,24.0\nProposed,0.87,18.5\n",
                encoding="utf-8",
            )
            result = inventory_inputs.inventory(root)
            self.assertEqual(result["data_file_count"], 1)
            profile = result["files"][0]["table_profile"]
            by_name = {column["name"]: column for column in profile["columns"]}
            self.assertEqual(by_name["method"]["type"], "categorical")
            self.assertEqual(by_name["accuracy"]["type"], "numeric")
            self.assertEqual(by_name["accuracy"]["min"], 0.81)
            self.assertEqual(by_name["accuracy"]["max"], 0.87)

    def test_profiles_json_record_list_as_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "metrics.json").write_text(
                json.dumps([{"epoch": 1, "loss": 0.8}, {"epoch": 2, "loss": 0.5}]),
                encoding="utf-8",
            )
            result = inventory_inputs.inventory(root)
            self.assertEqual(result["data_file_count"], 1)
            self.assertTrue(result["files"][0]["table_profile"]["data_candidate"])

    def test_profiles_first_xlsx_sheet(self):
        try:
            from openpyxl import Workbook
        except ImportError:
            self.skipTest("openpyxl is not installed")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Metrics"
            sheet.append(["method", "accuracy"])
            sheet.append(["Baseline", 0.81])
            sheet.append(["Proposed", 0.87])
            workbook.save(root / "results.xlsx")
            result = inventory_inputs.inventory(root)
            profile = result["files"][0]["table_profile"]
            self.assertEqual(profile["sheet"], "Metrics")
            self.assertTrue(profile["data_candidate"])
            self.assertEqual(profile["columns"][1]["type"], "numeric")

    def test_extracts_docx_text_for_illustration_planning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            document_xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>The encoder flows to the classifier.</w:t></w:r></w:p></w:body></w:document>'
            )
            with zipfile.ZipFile(root / "paper.docx", "w") as archive:
                archive.writestr("word/document.xml", document_xml)
            result = inventory_inputs.inventory(root)
            self.assertIn("encoder flows", result["files"][0]["text_preview"])


class EnvironmentCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checker = load_environment_checker()

    def test_credential_status_combines_process_and_persistent_scopes(self):
        status = self.checker.credential_status(
            "AUTOFIGURE_API_KEY",
            {"AUTOFIGURE_API_KEY": "configured"},
            lambda _: ["user"],
        )
        self.assertTrue(status["available"])
        self.assertEqual(status["scopes"], ["process", "user"])

    def test_credential_status_reports_missing_without_revealing_values(self):
        status = self.checker.credential_status("MISSING", {}, lambda _: [])
        self.assertEqual(status, {"available": False, "scopes": []})


class PluginPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = SKILL.parents[3]
        cls.plugin_root = SKILL.parents[1]

    def test_plugin_manifest_matches_skill_and_release_version(self):
        manifest = json.loads(
            (self.plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        version = (self.repo / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(manifest["name"], "figure-skill")
        self.assertEqual(manifest["version"], version)
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["interface"]["displayName"], "Figure Skill")
        self.assertEqual(manifest["author"]["name"], "MWM-Research")

    def test_team_marketplace_points_to_plugin(self):
        marketplace = json.loads(
            (self.repo / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
        )
        entries = [entry for entry in marketplace["plugins"] if entry["name"] == "figure-skill"]
        self.assertEqual(marketplace["name"], "mwm-research")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"]["path"], "./plugins/figure-skill")
        self.assertEqual(entries[0]["policy"]["installation"], "AVAILABLE")


class PlannerTests(unittest.TestCase):
    def inventory_for(self, files: dict[str, str]) -> dict:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        for name, content in files.items():
            (root / name).write_text(content, encoding="utf-8")
        return inventory_inputs.inventory(root)

    def tearDown(self):
        if hasattr(self, "temp"):
            self.temp.cleanup()

    def test_four_routes(self):
        methods = "The encoder flows to retrieval and then to the classifier."
        csv_text = "method,accuracy\nBaseline,0.81\nProposed,0.87\n"

        inventory = self.inventory_for({"methods.txt": methods})
        self.assertEqual(plan_figure.choose_route(inventory, "architecture"), "illustration")
        self.temp.cleanup()

        inventory = self.inventory_for({"results.csv": csv_text})
        self.assertEqual(plan_figure.choose_route(inventory, "performance"), "data-plot")
        self.temp.cleanup()

        inventory = self.inventory_for({"existing.svg": "<svg/>"})
        self.assertEqual(plan_figure.choose_route(inventory, "修改已有 SVG"), "edit")
        self.temp.cleanup()

        inventory = self.inventory_for({"methods.txt": methods, "results.csv": csv_text})
        self.assertEqual(plan_figure.choose_route(inventory, "combined figure"), "composite")

    def test_composite_plan_has_executable_panels(self):
        inventory = self.inventory_for({
            "methods.txt": "The encoder flows to retrieval and then to the classifier.",
            "results.csv": "method,accuracy\nBaseline,0.81\nProposed,0.87\n",
        })
        plan = plan_figure.build_plan(inventory, "accuracy and method figure")
        self.assertEqual(plan["route"], "composite")
        self.assertEqual(len(plan["panels"]), 2)
        diagram, plot = plan["panels"]
        self.assertEqual(diagram["entities"], ["Encoder", "Retrieval", "Classifier"])
        self.assertEqual(len(diagram["edges"]), 2)
        self.assertEqual(plot["visual_form"], "bar-chart")
        self.assertEqual(plot["x"], "method")
        self.assertEqual(plot["y"], "accuracy")
        self.assertEqual(plan["open_questions"], [])

    def test_explicit_route_overrides_inference(self):
        inventory = self.inventory_for({"results.csv": "method,accuracy\nA,0.8\n"})
        self.assertEqual(plan_figure.choose_route(inventory, "", "illustration"), "illustration")

    def test_public_sklearn_pipeline_entities_are_plannable(self):
        inventory = self.inventory_for({
            "methods.txt": (
                "Input Iris data flows to a train/test split, then to standard scaler, "
                "then to logistic regression, then to prediction, and finally to accuracy."
            )
        })
        plan = plan_figure.build_plan(inventory, "Iris classification pipeline", "illustration")
        panel = plan["panels"][0]
        self.assertEqual(panel["entities"], [
            "Input", "Train/Test Split", "Standard Scaler", "Logistic Regression",
            "Prediction", "Accuracy",
        ])
        self.assertEqual(len(panel["edges"]), 5)
        self.assertEqual(plan["open_questions"], [])

    def test_scatter_ignores_categorical_column_for_numeric_x_axis(self):
        inventory = self.inventory_for({
            "iris.csv": (
                "petal_length_cm,petal_width_cm,species\n"
                "1.4,0.2,Iris-setosa\n4.7,1.4,Iris-versicolor\n6.0,2.5,Iris-virginica\n"
            )
        })
        plan = plan_figure.build_plan(
            inventory,
            "Scatter plot of petal_length_cm against petal_width_cm.",
            "data-plot",
        )
        panel = plan["panels"][0]
        self.assertEqual(panel["visual_form"], "scatter-plot")
        self.assertEqual(panel["x"], "petal_width_cm")
        self.assertEqual(panel["y"], "petal_length_cm")
        self.assertEqual(panel["title"], "petal_length_cm vs petal_width_cm")

    def test_edit_plan_requires_explicit_operations(self):
        inventory = self.inventory_for({
            "existing.svg": '<svg xmlns="http://www.w3.org/2000/svg"><text>Encoder</text></svg>'
        })
        plan = plan_figure.build_plan(inventory, "修改已有 SVG，补充 Retrieval 模块")
        self.assertEqual(plan["route"], "edit")
        self.assertEqual(plan["panels"][0]["operations"], [])
        self.assertTrue(any("explicit edit operations" in item for item in plan["open_questions"]))

    def test_edit_plan_accepts_reviewable_operations(self):
        inventory = self.inventory_for({
            "existing.svg": '<svg xmlns="http://www.w3.org/2000/svg"><text>Classifier</text></svg>'
        })
        operations = [{"op": "replace_text", "old": "Classifier", "new": "Retrieval"}]
        plan = plan_figure.build_plan(inventory, "修改已有 SVG", edit_operations=operations)
        self.assertEqual(plan["open_questions"], [])
        self.assertEqual(plan["panels"][0]["operations"], operations)


class NativeEditBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = load_edit_backend()

    def test_applies_exact_svg_edits_and_records_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "existing.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
                '<text id="module" fill="#111">Classifier</text></svg>', encoding="utf-8",
            )
            panel = {
                "id": "A", "type": "edit", "source_files": ["existing.svg"],
                "operations": [
                    {"op": "replace_text", "old": "Classifier", "new": "Retrieval"},
                    {"op": "set_attribute", "element_id": "module", "attribute": "fill", "value": "#333333"},
                ],
            }
            plan = {"input_root": str(root), "panels": [panel]}
            output = root / "output"
            provenance = self.backend.render_panel(plan, panel, root / "figure-plan.json", output)
            rendered = (output / "panel_a.svg").read_text(encoding="utf-8")
            self.assertIn("Retrieval", rendered)
            self.assertIn("#333333", rendered)
            self.assertEqual([item["status"] for item in provenance["operations"]], ["applied", "applied"])
            self.assertTrue((output / "panel_a_original.svg").is_file())

    def test_rejects_missing_or_ambiguous_text_target(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring('<svg><text>A</text><text>A</text></svg>')
        with self.assertRaisesRegex(ValueError, "expected 1 exact match"):
            self.backend.apply_operation(root, {"op": "replace_text", "old": "A", "new": "B"})


class MatplotlibBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("matplotlib is not installed")
        cls.backend = load_backend()

    def test_render_bar_panel_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "output"
            output.mkdir()
            source = root / "results.csv"
            source.write_text(
                "method,accuracy\nBaseline,0.81\nProposed,0.87\n",
                encoding="utf-8",
            )
            panel = {
                "id": "A",
                "type": "data-plot",
                "title": "Accuracy comparison",
                "source_files": ["results.csv"],
                "visual_form": "bar-chart",
                "x": "method",
                "y": "accuracy",
                "unit": "fraction",
                "transform": "none",
            }
            provenance = self.backend.render_panel(panel, root, output, ("svg", "pdf", "png"))
            self.assertTrue((output / "panel_a.svg").is_file())
            self.assertTrue((output / "panel_a.pdf").is_file())
            self.assertTrue((output / "panel_a.png").is_file())
            self.assertEqual([mark["y"]["value"] for mark in provenance["marks"]], [0.81, 0.87])
            self.assertEqual([mark["source_row"] for mark in provenance["marks"]], [2, 3])

    def test_duplicate_categories_require_explicit_aggregation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "output"
            output.mkdir()
            (root / "results.csv").write_text("method,accuracy\nA,0.8\nA,0.9\n", encoding="utf-8")
            panel = {
                "id": "A",
                "source_files": ["results.csv"],
                "visual_form": "bar-chart",
                "x": "method",
                "y": "accuracy",
            }
            with self.assertRaisesRegex(ValueError, "aggregation"):
                self.backend.render_panel(panel, root, output, ("svg",))

    def test_line_and_scatter_forms_render_numeric_axes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "output"
            output.mkdir()
            (root / "training.csv").write_text("epoch,loss\n1,0.8\n2,0.5\n3,0.3\n", encoding="utf-8")
            base = {
                "id": "A", "title": "Training loss", "source_files": ["training.csv"],
                "x": "epoch", "y": "loss", "transform": "none",
            }
            line = self.backend.render_panel(dict(base, visual_form="line-chart"), root, output, ("svg",))
            scatter = self.backend.render_panel(dict(base, id="B", visual_form="scatter-plot"), root, output, ("svg",))
            self.assertEqual(len(line["marks"]), 3)
            self.assertEqual(len(scatter["marks"]), 3)
            self.assertTrue((output / "panel_a.svg").is_file())
            self.assertTrue((output / "panel_b.svg").is_file())

    def test_grouped_bar_uses_second_category_and_tracks_group_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "output"
            output.mkdir()
            (root / "results.csv").write_text(
                "dataset,method,accuracy\nD1,Baseline,0.70\nD1,Proposed,0.80\nD2,Baseline,0.75\nD2,Proposed,0.85\n",
                encoding="utf-8",
            )
            panel = {
                "id": "A", "title": "Grouped accuracy", "source_files": ["results.csv"],
                "visual_form": "bar-chart", "x": "dataset", "group": "method", "y": "accuracy",
            }
            provenance = self.backend.render_panel(panel, root, output, ("svg",))
            self.assertEqual(len(provenance["marks"]), 4)
            self.assertTrue(all(mark["group"]["column"] == "method" for mark in provenance["marks"]))
            self.assertEqual({mark["group"]["value"] for mark in provenance["marks"]}, {"Baseline", "Proposed"})


class DiagramAndAssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svg_backend = load_module("svg_diagram_backend", SCRIPTS / "backends" / "svg_diagram_backend.py")
        cls.assembler = load_module("assemble_figure", SCRIPTS / "assemble_figure.py")

    def test_svg_backend_renders_editable_nodes_and_edges(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "panel_a.svg"
            panel = {
                "id": "A",
                "title": "Method pipeline",
                "entities": ["Encoder", "Retrieval", "Classifier"],
                "edges": [
                    {"from": "Encoder", "to": "Retrieval", "meaning": "data-flow"},
                    {"from": "Retrieval", "to": "Classifier", "meaning": "data-flow"},
                ],
            }
            provenance = self.svg_backend.render_diagram(panel, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn("Encoder", text)
            self.assertIn("marker-end", text)
            self.assertEqual(len(provenance["edges"]), 2)

    def test_assembler_combines_two_svg_panels(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            panels = root / "panels"
            panels.mkdir()
            for panel_id, label in (("a", "Diagram"), ("b", "Plot")):
                (panels / f"panel_{panel_id}.svg").write_text(
                    f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 200 100"><text x="10" y="30">{label}</text></svg>',
                    encoding="utf-8",
                )
            plan = {"panels": [{"id": "A"}, {"id": "B"}], "brief": "Combined figure"}
            manifest = self.assembler.assemble(plan, panels, root / "figure.svg", "horizontal")
            text = (root / "figure.svg").read_text(encoding="utf-8")
            self.assertEqual(len(manifest["panels"]), 2)
            self.assertIn("Diagram", text)
            self.assertIn("Plot", text)


class QualityAssuranceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("matplotlib is not installed")
        cls.backend = load_backend()
        cls.qa = load_module("qa_figure", SCRIPTS / "qa_figure.py")

    def test_qa_verifies_data_hash_and_each_plotted_mark(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "results.csv"
            source.write_text("method,accuracy\nBaseline,0.81\nProposed,0.87\n", encoding="utf-8")
            panel = {
                "id": "A", "type": "data-plot", "title": "Accuracy",
                "source_files": ["results.csv"], "visual_form": "bar-chart",
                "x": "method", "y": "accuracy", "unit": "fraction", "transform": "none",
            }
            provenance = self.backend.render_panel(panel, root, root, ("svg", "pdf", "png"))
            (root / "panel_a_source.py").write_text("# reproducible plotting source\n", encoding="utf-8")
            provenance_path = root / "data-provenance.json"
            provenance_path.write_text(json.dumps({"schema_version": "1.0", "panels": [provenance]}), encoding="utf-8")
            plan = {
                "panels": [panel], "open_questions": [], "review_status": "approved",
                "constraints": {"forbid_invented_quantitative_claims": True},
            }
            report = self.qa.run_qa(root, plan)
            self.assertEqual(report["status"], "pass")
            source.write_text("method,accuracy\nBaseline,0.10\nProposed,0.20\n", encoding="utf-8")
            changed = self.qa.run_qa(root, plan)
            self.assertEqual(changed["status"], "fail")

    def test_qa_verifies_json_mark_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "results.json"
            source.write_text(json.dumps([
                {"method": "Baseline", "accuracy": 0.81},
                {"method": "Proposed", "accuracy": 0.87},
            ]), encoding="utf-8")
            panel = {
                "id": "A", "type": "data-plot", "title": "Accuracy",
                "source_files": ["results.json"], "visual_form": "bar-chart",
                "x": "method", "y": "accuracy", "unit": "fraction", "transform": "none",
            }
            provenance = self.backend.render_panel(panel, root, root, ("svg", "pdf", "png"))
            (root / "panel_a_source.py").write_text("# source\n", encoding="utf-8")
            (root / "data-provenance.json").write_text(
                json.dumps({"schema_version": "1.0", "panels": [provenance]}), encoding="utf-8"
            )
            plan = {
                "panels": [panel], "open_questions": [], "review_status": "approved",
                "constraints": {"forbid_invented_quantitative_claims": True},
            }
            self.assertEqual(self.qa.run_qa(root, plan)["status"], "pass")


class EndToEndWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("matplotlib is not installed")
        assembler = load_module("assemble_figure_e2e", SCRIPTS / "assemble_figure.py")
        if assembler.find_browser() is None:
            raise unittest.SkipTest("Edge/Chrome is not installed")

    def test_composite_workflow_creates_approved_passed_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = root / "inputs"
            output = root / "output"
            inputs.mkdir()
            (inputs / "methods.txt").write_text(
                "The encoder flows to retrieval and then to the classifier.", encoding="utf-8"
            )
            (inputs / "results.csv").write_text(
                "method,accuracy\nBaseline,0.81\nProposed,0.87\n", encoding="utf-8"
            )
            result = subprocess.run([
                sys.executable, str(SCRIPTS / "run_workflow.py"),
                "--input", str(inputs), "--brief", "Create a method and accuracy figure",
                "--output", str(output), "--approve-plan",
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
            self.assertTrue((output / "final" / "figure.svg").is_file())
            self.assertTrue((output / "final" / "figure.pdf").is_file())
            self.assertTrue((output / "final" / "figure.png").is_file())
            report = json.loads((output / "reports" / "qa-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "pass")
            plan = json.loads((output / "figure-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["review_status"], "approved")


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.drawio = load_module("drawio_adapter", SCRIPTS / "adapters" / "drawio_adapter.py")
        cls.happy = load_module("happy_figure_adapter", SCRIPTS / "adapters" / "happy_figure_adapter.py")
        cls.paperbanana = load_module("paperbanana_adapter", SCRIPTS / "adapters" / "paperbanana_adapter.py")
        cls.autofigure = load_module("autofigure_edit_adapter", SCRIPTS / "adapters" / "autofigure_edit_adapter.py")
        cls.no_sam = load_module("autofigure_no_sam_runner", SCRIPTS / "adapters" / "autofigure_no_sam_runner.py")

    def plan(self, root: Path) -> dict:
        (root / "methods.txt").write_text(
            "The encoder flows to retrieval and then to the classifier.", encoding="utf-8"
        )
        return {
            "brief": "Method figure", "input_root": str(root),
            "panels": [{
                "id": "A", "title": "Method pipeline", "type": "illustration",
                "source_files": ["methods.txt"],
                "entities": ["Encoder", "Retrieval", "Classifier"],
                "edges": [
                    {"from": "Encoder", "to": "Retrieval", "meaning": "data-flow"},
                    {"from": "Retrieval", "to": "Classifier", "meaning": "data-flow"},
                ],
            }],
        }

    def test_drawio_and_happy_handoffs_preserve_approved_structure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = self.plan(root)
            drawio_output = root / "panel_a.drawio"
            result = self.drawio.render_drawio(plan["panels"][0], drawio_output)
            xml = drawio_output.read_text(encoding="utf-8")
            self.assertEqual(result["edges"], 2)
            self.assertIn("Encoder", xml)
            self.assertIn("source=\"node-Encoder\"", xml)
            happy = self.happy.build_handoff(plan)
            prompt = happy["requests"][0]["prompt"]
            self.assertIn("Encoder, Retrieval, Classifier", prompt)
            self.assertIn("do not add quantitative claims", prompt)

    def test_external_request_manifests_do_not_contain_plaintext_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = self.plan(root)
            paper_repo = root / "paper-repo"
            (paper_repo / "skill").mkdir(parents=True)
            (paper_repo / "skill" / "run.py").write_text(
                "import argparse\np=argparse.ArgumentParser()\n" + "\n".join(
                    f"p.add_argument('{flag}')" for flag in sorted(self.paperbanana.REQUIRED_FLAGS)
                ), encoding="utf-8",
            )
            auto_repo = root / "auto-repo"
            auto_repo.mkdir()
            (auto_repo / "autofigure2.py").write_text(
                "import argparse\np=argparse.ArgumentParser()\n" + "\n".join(
                    f"p.add_argument('{flag}')" for flag in sorted(self.autofigure.REQUIRED_FLAGS)
                ), encoding="utf-8",
            )
            paper = self.paperbanana.prepare(plan, plan["panels"][0], root / "paper-out", paper_repo, 1)
            auto = self.autofigure.prepare(plan, auto_repo, root / "auto-out", "openai_response", None, "local")
            paper_text = json.dumps(paper)
            auto_text = json.dumps(auto)
            self.assertNotIn("sk-", paper_text)
            self.assertNotIn("sk-", auto_text)
            self.assertIn("<redacted-at-runtime>", auto_text)
            self.assertEqual(paper["credential_environment"], ["GOOGLE_API_KEY", "OPENROUTER_API_KEY"])
            self.assertEqual(paper["upstream_contract"]["status"], "verified")
            self.assertEqual(auto["upstream_contract"]["status"], "verified")

    def test_autofigure_custom_provider_records_public_endpoint_and_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = self.plan(root)
            repo = root / "auto-repo"
            repo.mkdir()
            (repo / "autofigure2.py").write_text(
                "import argparse\np=argparse.ArgumentParser()\n" + "\n".join(
                    f"p.add_argument('{flag}')" for flag in sorted(self.autofigure.REQUIRED_FLAGS)
                ), encoding="utf-8",
            )
            request = self.autofigure.prepare(
                plan, repo, root / "out", "custom", None, "fal",
                "https://relay.example/v1", "vision-model",
            )
            self.assertEqual(request["base_url"], "https://relay.example/v1")
            self.assertEqual(request["svg_model"], "vision-model")
            self.assertEqual(request["optimize_iterations"], 0)
            self.assertIn("--base_url", request["display_command"])
            self.assertIn("--svg_model", request["display_command"])

            optimized = self.autofigure.prepare(
                plan, repo, root / "optimized", "custom", None, "none",
                "https://relay.example/v1", "vision-model", 2,
            )
            index = optimized["display_command"].index("--optimize_iterations")
            self.assertEqual(optimized["display_command"][index + 1], "2")

    def test_autofigure_none_backend_uses_explicit_fallback_runner(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = self.plan(root)
            repo = root / "auto-repo"
            repo.mkdir()
            (repo / "autofigure2.py").write_text(
                "import argparse\np=argparse.ArgumentParser()\n" + "\n".join(
                    f"p.add_argument('{flag}')" for flag in sorted(self.autofigure.REQUIRED_FLAGS)
                ), encoding="utf-8",
            )
            request = self.autofigure.prepare(
                plan, repo, root / "out", "custom", None, "none",
                "https://relay.example/v1", "vision-model",
            )
            self.assertFalse(request["segmentation_performed"])
            self.assertTrue(request["execution_entrypoint"].endswith("autofigure_no_sam_runner.py"))
            self.assertNotIn("--sam_backend", request["display_command"])

    def test_no_sam_validation_rejects_embedded_raster_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            embedded = root / "embedded.svg"
            embedded.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/png;base64,AA=="/></svg>',
                encoding="utf-8",
            )
            vector = root / "vector.svg"
            vector.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>',
                encoding="utf-8",
            )
            self.assertFalse(self.no_sam.validate_pure_svg(embedded)["valid"])
            self.assertTrue(self.no_sam.validate_pure_svg(vector)["valid"])

    def test_autofigure_selects_raster_from_edit_panel(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / "existing.png"
            image.write_bytes(b"not-decoded-during-preparation")
            plan = {
                "input_root": str(root),
                "panels": [{"id": "A", "type": "edit", "source_files": ["existing.png"]}],
            }
            flag, source = self.autofigure.select_source(plan, None)
            self.assertEqual(flag, "input_figure_path")
            self.assertEqual(source, image.resolve())

    def test_upstream_contract_rejects_cli_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entrypoint = root / "autofigure2.py"
            entrypoint.write_text(
                "import argparse\np=argparse.ArgumentParser()\np.add_argument('--output_dir')\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "upstream CLI contract changed"):
                self.autofigure.inspect_contract(root, entrypoint, self.autofigure.REQUIRED_FLAGS)


if __name__ == "__main__":
    unittest.main()
