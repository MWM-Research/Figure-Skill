from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
BACKENDS = SKILL / "scripts" / "backends"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class StatisticsCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stats = load("statistics_core_phase2", BACKENDS / "statistics_core.py")

    def test_box_summary_is_deterministic_and_tracks_outlier(self):
        result = self.stats.box_summary([1, 2, 3, 4, 100], [2, 3, 4, 5, 6])
        self.assertEqual(result["median"], 3.0)
        self.assertEqual(result["outliers"], [{"value": 100.0, "source_row": 6}])
        self.assertEqual(result["formula_version"], "figure-statistics-1.0")

    def test_kde_uses_fixed_grid_and_explicit_bandwidth(self):
        first = self.stats.kde([0.1, 0.2, 0.4], [2, 3, 4], bandwidth="scott")
        second = self.stats.kde([0.1, 0.2, 0.4], [2, 3, 4], bandwidth="scott")
        self.assertEqual(len(first["grid"]), 128)
        self.assertEqual(first, second)

    def test_histogram_records_edges_and_bin_rows(self):
        result = self.stats.histogram([0, 1, 2, 3], [2, 3, 4, 5], {"strategy": "count", "count": 2})
        self.assertEqual(len(result["edges"]), 3)
        self.assertEqual(sorted(sum(result["bin_source_rows"], [])), [2, 3, 4, 5])

    def test_confusion_matrix_normalizes_explicitly(self):
        result = self.stats.confusion_matrix(["A", "A", "B"], ["A", "B", "B"], [2, 3, 4], "true")
        self.assertEqual(result["labels"], ["A", "B"])
        self.assertEqual(result["matrix"], [[0.5, 0.5], [0.0, 1.0]])

    def test_roc_and_pr_group_equal_thresholds(self):
        roc = self.stats.binary_curve([1, 0, 1, 0], [0.9, 0.8, 0.8, 0.1], [2, 3, 4, 5], 1, "roc", True)
        pr = self.stats.binary_curve([1, 0, 1, 0], [0.9, 0.8, 0.8, 0.1], [2, 3, 4, 5], 1, "pr", False)
        self.assertEqual(len(roc["points"]), 4)
        self.assertIsNotNone(roc["auc"])
        self.assertIsNone(pr["auc"])


class AdvancedMatplotlibTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("matplotlib unavailable")
        cls.backend = load("matplotlib_backend_phase2", BACKENDS / "matplotlib_backend.py")
        cls.qa = load("qa_figure_phase2", SKILL / "scripts" / "qa_figure.py")

    def render(self, csv_text: str, panel: dict, formats=("svg",)):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "data.csv").write_text(csv_text, encoding="utf-8")
        output = root / "output"; output.mkdir()
        panel = dict(panel, id="A", type=panel.get("type", "data-plot"), source_files=["data.csv"], title=panel.get("title", "Test"))
        result = self.backend.render_panel(panel, root, output, formats)
        return temp, root, output, result

    def test_raw_box_and_violin_render_vector_outputs(self):
        csv_text = "method,value\nA,1\nA,2\nA,3\nB,2\nB,3\nB,5\n"
        for form, operation, parameters in (("box-plot", "box-summary", {}), ("violin-plot", "kde", {"bandwidth": "scott"})):
            temp, _, output, result = self.render(csv_text, {"visual_form": form, "x": "method", "y": "value", "calculation": {"mode": "raw", "operation": operation, "parameters": parameters}})
            try:
                self.assertNotIn("<image", (output / "panel_a.svg").read_text(encoding="utf-8"))
                self.assertEqual(len(result["marks"]), 2)
                self.assertTrue(all("source_rows" in mark for mark in result["marks"]))
            finally:
                temp.cleanup()

    def test_raw_histogram_and_density_render(self):
        csv_text = "method,value\nA,1\nA,2\nA,3\nB,2\nB,3\nB,5\n"
        cases = [
            ("histogram", "histogram", {"strategy": "count", "count": 3}),
            ("density-plot", "kde", {"bandwidth": "scott"}),
        ]
        for form, operation, parameters in cases:
            temp, _, output, result = self.render(csv_text, {"visual_form": form, "value": "value", "group": "method", "calculation": {"mode": "raw", "operation": operation, "parameters": parameters}})
            try:
                self.assertTrue((output / "panel_a.svg").is_file())
                self.assertEqual(len(result["marks"]), 2)
            finally:
                temp.cleanup()

    def test_precomputed_advanced_forms_render(self):
        cases = [
            ("group,q1,median,q3,whisker_low,whisker_high\nA,1,2,3,0,4\n", {"visual_form": "box-plot", "x": "group", "y": "median", "calculation": {"mode": "precomputed", "operation": "box-summary", "parameters": {}}}),
            ("left,right,count\n0,1,3\n1,2,5\n", {"visual_form": "histogram", "x": "left", "x2": "right", "y": "count", "calculation": {"mode": "precomputed", "operation": "histogram", "parameters": {}}}),
            ("grid,density\n0,0.1\n1,0.5\n2,0.1\n", {"visual_form": "density-plot", "x": "grid", "y": "density", "value": "density", "calculation": {"mode": "precomputed", "operation": "kde", "parameters": {}}}),
            ("grid,density\n0,0.1\n1,0.5\n2,0.1\n", {"visual_form": "violin-plot", "x": "grid", "y": "grid", "value": "density", "calculation": {"mode": "precomputed", "operation": "kde", "parameters": {}}}),
            ("actual,predicted,value\nA,A,3\nA,B,1\nB,A,1\nB,B,4\n", {"visual_form": "confusion-matrix", "x": "predicted", "y": "actual", "value": "value", "calculation": {"mode": "precomputed", "operation": "confusion-count", "parameters": {}}}),
            ("fpr,tpr\n0,0\n0.2,0.8\n1,1\n", {"visual_form": "roc-curve", "x": "fpr", "y": "tpr", "calculation": {"mode": "precomputed", "operation": "roc", "parameters": {}}}),
            ("recall,precision\n0,1\n0.5,0.8\n1,0.5\n", {"visual_form": "pr-curve", "x": "recall", "y": "precision", "calculation": {"mode": "precomputed", "operation": "pr", "parameters": {}}}),
        ]
        for csv_text, panel in cases:
            temp, _, output, result = self.render(csv_text, panel)
            try:
                self.assertTrue((output / "panel_a.svg").is_file(), panel["visual_form"])
                self.assertTrue(result["marks"], panel["visual_form"])
            finally:
                temp.cleanup()

    def test_raw_confusion_matrix_and_curves_render(self):
        temp, _, output, confusion = self.render(
            "actual,predicted\nA,A\nA,B\nB,B\nB,A\n",
            {"visual_form": "confusion-matrix", "actual": "actual", "predicted": "predicted", "calculation": {"mode": "raw", "operation": "confusion-count", "parameters": {"normalization": "none"}}},
        )
        try:
            self.assertEqual(len(confusion["marks"]), 4)
            self.assertNotIn("<image", (output / "panel_a.svg").read_text(encoding="utf-8"))
        finally:
            temp.cleanup()
        curve_csv = "label,score\n1,0.9\n0,0.7\n1,0.6\n0,0.1\n"
        for form, operation in (("roc-curve", "roc"), ("pr-curve", "pr")):
            temp, _, output, curve = self.render(curve_csv, {"visual_form": form, "label": "label", "score": "score", "calculation": {"mode": "raw", "operation": operation, "parameters": {"positive_label": "1", "compute_auc": True}}})
            try:
                self.assertGreaterEqual(len(curve["marks"]), 3)
                self.assertTrue((output / "panel_a.svg").is_file())
            finally:
                temp.cleanup()

    def test_asymmetric_uncertainty_and_axis_guards(self):
        csv_text = "x,y,lo,hi\n1,10,2,3\n2,20,4,5\n"
        base = {"visual_form": "line-chart", "x": "x", "y": "y", "uncertainty": {"mode": "asymmetric-delta", "lower_column": "lo", "upper_column": "hi"}}
        temp, _, _, result = self.render(csv_text, base)
        try:
            self.assertEqual(result["marks"][0]["uncertainty"]["values"], {"lower": 2.0, "upper": 3.0})
        finally:
            temp.cleanup()
        for csv_text, panel, message in (
            ("name,y\nA,10\nB,12\n", {"visual_form": "bar-chart", "x": "name", "y": "y", "axis": {"y_limits": [9, 13]}}, "baseline_justification"),
            ("x,y\n1,0\n2,2\n", {"visual_form": "line-chart", "x": "x", "y": "y", "axis": {"y_scale": "log"}}, "positive"),
        ):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory); (root / "data.csv").write_text(csv_text, encoding="utf-8"); output = root / "out"; output.mkdir()
                configured = dict(panel, id="A", source_files=["data.csv"])
                with self.assertRaisesRegex(ValueError, message):
                    self.backend.render_panel(configured, root, output, ("svg",))

    def test_explicit_axis_break_and_data_grid(self):
        panel = {"visual_form": "line-chart", "x": "x", "y": "y", "axis": {"break": {"axis": "y", "omit": [20, 80], "justification": "Two separated operating regimes"}}}
        temp, _, output, _ = self.render("x,y\n1,10\n2,15\n3,90\n4,95\n", panel)
        try:
            self.assertTrue((output / "panel_a.svg").is_file())
        finally:
            temp.cleanup()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "data.csv").write_text("x,method,y\n1,A,1\n2,A,2\n1,B,2\n2,B,3\n", encoding="utf-8"); output = root / "out"; output.mkdir()
            subplot = {"id": "s", "type": "data-plot", "source_files": ["data.csv"], "visual_form": "line-chart", "x": "x", "y": "y", "group": "method"}
            grid = {"id": "G", "type": "data-plot-grid", "layout": {"rows": 1, "columns": 2}, "share_x": True, "share_y": True, "shared_legend": True, "subplots": [dict(subplot, id="S1"), dict(subplot, id="S2")]}
            result = self.backend.render_grid_panel(grid, root, output, ("svg", "png"))
            self.assertEqual(result["grid"]["shared_legend"], True)
            self.assertEqual(len(result["marks"]), 8)

    def test_qa_recomputes_and_rejects_tampered_box_summary(self):
        temp, root, _, provenance = self.render(
            "method,value\nA,1\nA,2\nA,3\nA,100\n",
            {"visual_form": "box-plot", "x": "method", "y": "value", "calculation": {"mode": "raw", "operation": "box-summary", "parameters": {}}},
        )
        try:
            path = root / "provenance.json"
            path.write_text(json.dumps({"schema_version": "1.0", "panels": [provenance]}), encoding="utf-8")
            plan = {"panels": [{"id": "A", "type": "data-plot", "source_files": ["data.csv"], "visual_form": "box-plot", "x": "method", "y": "value", "calculation": {"mode": "raw", "operation": "box-summary", "parameters": {}}}]}
            checks = self.qa.verify_data_provenance(path, plan)
            self.assertTrue(all(item["status"] == "pass" for item in checks), checks)
            data = json.loads(path.read_text(encoding="utf-8")); data["panels"][0]["marks"][0]["derived"]["median"] = 999
            path.write_text(json.dumps(data), encoding="utf-8")
            changed = self.qa.verify_data_provenance(path, plan)
            self.assertTrue(any(item["check"] == "provenance-derived-values" and item["status"] == "fail" for item in changed))
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
