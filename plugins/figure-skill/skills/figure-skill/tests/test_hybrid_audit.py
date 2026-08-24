from __future__ import annotations

import base64
import importlib.util
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def png_bytes(color: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (320, 240), color).save(buffer, format="PNG")
    return buffer.getvalue()


class HybridStructureAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.auditor = load_module("hybrid_svg_auditor", SCRIPTS / "audit_hybrid_svg.py")
        cls.qa = load_module("hybrid_qa", SCRIPTS / "qa_figure.py")
        cls.planner = load_module("hybrid_planner", SCRIPTS / "plan_figure.py")

    def test_planner_selects_hybrid_route_and_requires_contract_review(self):
        inventory = {
            "root": "C:/input", "category_counts": {"narrative": 1},
            "files": [{"path": "methods.txt", "text_preview": "Video frames flow to a Transformer."}],
        }
        plan = self.planner.build_plan(
            inventory,
            "Use raster video frames and a raster heatmap with vector Transformer modules, arrows, axes, and bar chart results.",
        )
        self.assertEqual(plan["route"], "hybrid-composite")
        self.assertEqual(plan["panels"][0]["type"], "hybrid-composite")
        self.assertTrue(plan["panels"][0]["representation_contract"]["roles"])
        self.assertTrue(plan["open_questions"])

    def fixture(self, root: Path) -> tuple[Path, Path, str, str]:
        assets = root / "assets"
        assets.mkdir()
        frame = assets / "frame-01.png"
        heatmap = assets / "heatmap.png"
        frame.write_bytes(png_bytes("#336699"))
        heatmap.write_bytes(png_bytes("#ddcc33"))
        frame_uri = "data:image/png;base64," + base64.b64encode(frame.read_bytes()).decode("ascii")
        heatmap_uri = "data:image/png;base64," + base64.b64encode(heatmap.read_bytes()).decode("ascii")
        plan = {
            "route": "hybrid-composite",
            "panels": [{
                "id": "A", "type": "hybrid-composite",
                "visible_labels": ["Hybrid Figure", "Module", "Result"],
                "representation_contract": {
                    "roles": [
                        {"role": "video-frame-raster", "kind": "raster", "svg_tag": "image", "expected_count": 1, "source_glob": "assets/frame-*.png"},
                        {"role": "attention-heatmap-raster", "kind": "raster", "svg_tag": "image", "expected_count": 1, "source_glob": "assets/heatmap.png"},
                        {"role": "transformer-module", "kind": "vector", "svg_tag": "rect", "expected_count": 1},
                        {"role": "data-flow-arrow", "kind": "vector", "svg_tag": "path", "expected_count": 1},
                        {"role": "result-bar", "kind": "vector", "svg_tag": "rect", "expected_count": 1},
                        {"role": "axis", "kind": "vector", "svg_tag": "line", "expected_count": 1},
                    ],
                    "unclassified_image_policy": "forbid",
                    "exact_visible_labels": True,
                },
            }],
        }
        plan_path = root / "figure-plan.json"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        return plan_path, assets, frame_uri, heatmap_uri

    def test_correct_raster_vector_routing_passes_and_hashes_match(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan_path, _, frame_uri, heatmap_uri = self.fixture(root)
            svg = root / "figure.svg"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg">'
                f'<image data-role="video-frame-raster" href="{frame_uri}"/>'
                f'<image data-role="attention-heatmap-raster" href="{heatmap_uri}"/>'
                '<rect data-role="transformer-module"/><path data-role="data-flow-arrow"/>'
                '<rect data-role="result-bar"/><line data-role="axis"/>'
                '<text>Hybrid Figure</text><text>Module</text><text>Result</text></svg>',
                encoding="utf-8",
            )
            report = self.auditor.audit(plan_path, svg, root)
            self.assertEqual(report["status"], "pass", report)
            self.assertEqual(len(report["image_mappings"]), 2)
            self.assertTrue(all(item["source"] for item in report["image_mappings"]))
            report_path = root / "hybrid-structure-audit.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.assertTrue(all(item["status"] == "pass" for item in self.qa.verify_hybrid_audit(report_path)))

    def test_vector_standin_for_required_raster_role_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan_path, _, _, heatmap_uri = self.fixture(root)
            svg = root / "wrong.svg"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg">'
                '<rect data-role="video-frame-raster"/>'
                f'<image data-role="attention-heatmap-raster" href="{heatmap_uri}"/>'
                '<rect data-role="transformer-module"/><path data-role="data-flow-arrow"/>'
                '<rect data-role="result-bar"/><line data-role="axis"/>'
                '<text>Hybrid Figure</text><text>Module</text><text>Result</text></svg>',
                encoding="utf-8",
            )
            report = self.auditor.audit(plan_path, svg, root)
            self.assertEqual(report["status"], "fail", report)
            failed = {item["check"] for item in report["checks"] if item["status"] == "fail"}
            self.assertIn("role-svg-tag:video-frame-raster", failed)
            self.assertIn("source-hash-match:video-frame-raster", failed)

    def test_identical_raster_sources_preserve_hash_multiplicity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan_path, assets, frame_uri, heatmap_uri = self.fixture(root)
            (assets / "frame-02.png").write_bytes((assets / "frame-01.png").read_bytes())
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["panels"][0]["representation_contract"]["roles"][0]["expected_count"] = 2
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            svg = root / "duplicate.svg"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg">'
                f'<image data-role="video-frame-raster" href="{frame_uri}"/>'
                f'<image data-role="video-frame-raster" href="{frame_uri}"/>'
                f'<image data-role="attention-heatmap-raster" href="{heatmap_uri}"/>'
                '<rect data-role="transformer-module"/><path data-role="data-flow-arrow"/>'
                '<rect data-role="result-bar"/><line data-role="axis"/>'
                '<text>Hybrid Figure</text><text>Module</text><text>Result</text></svg>',
                encoding="utf-8",
            )
            report = self.auditor.audit(plan_path, svg, root)
            self.assertEqual(report["status"], "pass", report)
            frame_sources = [item["source"] for item in report["image_mappings"] if item["role"] == "video-frame-raster"]
            self.assertEqual(len(set(frame_sources)), 2)


if __name__ == "__main__":
    unittest.main()
