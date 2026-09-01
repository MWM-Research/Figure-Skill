from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
BACKENDS = SKILL / "scripts" / "backends"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module); return module


class AdvancedSvgEditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.edit = load("native_edit_phase2", BACKENDS / "native_edit_backend.py")
        cls.diagram = load("svg_diagram_phase2", BACKENDS / "svg_diagram_backend.py")

    def fixture(self, root: Path) -> Path:
        output = root / "source.svg"
        self.diagram.render_diagram({"id": "A", "title": "Graph", "entities": ["A", "B", "C"], "edges": [{"from": "A", "to": "B", "meaning": "flow"}, {"from": "B", "to": "C", "meaning": "flow"}], "_review_status": "approved"}, output)
        return output

    def test_generated_svg_contains_semantic_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = ET.parse(self.fixture(Path(temp))).getroot()
            nodes, edges = self.edit.node_elements(root), self.edit.edge_elements(root)
            self.assertEqual(set(nodes), {"A", "B", "C"})
            self.assertEqual(edges["edge-1"].get("data-from"), "A")
            self.assertEqual(edges["edge-1"].get("data-to"), "B")

    def test_generic_translate_and_resize_require_exact_ids(self):
        root = ET.fromstring('<svg width="100" height="100"><rect id="r" x="1" y="2" width="10" height="20"/></svg>')
        translated = self.edit.apply_operation(root, {"op": "translate_element", "element_id": "r", "dx": 5, "dy": 6})
        resized = self.edit.apply_operation(root, {"op": "resize_element", "element_id": "r", "width": 30, "height": 40})
        self.assertEqual(translated["status"], "applied"); self.assertEqual(resized["values"], {"width": 30.0, "height": 40.0})
        with self.assertRaisesRegex(ValueError, "compose_existing_transform"):
            self.edit.apply_operation(root, {"op": "translate_element", "element_id": "r", "dx": 1, "dy": 1})

    def test_semantic_node_and_edge_operations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = ET.parse(self.fixture(Path(temp))).getroot()
            self.edit.apply_operation(root, {"op": "move_node", "node_id": "B", "x": 300, "y": 180})
            self.edit.apply_operation(root, {"op": "resize_node", "node_id": "B", "width": 170, "height": 80})
            self.edit.apply_operation(root, {"op": "add_node", "node_id": "D", "label": "D", "x": 760, "y": 100, "width": 150, "height": 72})
            self.edit.apply_operation(root, {"op": "add_edge", "edge_id": "edge-d", "from": "C", "to": "D", "meaning": "flow"})
            reconnected = self.edit.apply_operation(root, {"op": "reconnect_edge", "edge_id": "edge-1", "to": "C"})
            self.assertEqual(reconnected["after"], {"from": "A", "to": "C"})
            self.edit.apply_operation(root, {"op": "remove_edge", "edge_id": "edge-2"})
            removed = self.edit.apply_operation(root, {"op": "remove_node", "node_id": "D", "remove_connected_edges": True})
            self.assertEqual(removed["removed_edges"], ["edge-d"])

    def test_alignment_distribution_overlap_and_auto_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = ET.parse(self.fixture(Path(temp))).getroot()
            self.edit.apply_operation(root, {"op": "align_nodes", "node_ids": ["A", "B", "C"], "axis": "y", "alignment": "top"})
            distributed = self.edit.apply_operation(root, {"op": "distribute_nodes", "node_ids": ["A", "B", "C"], "axis": "x", "gap": 50})
            self.assertEqual(distributed["status"], "applied")
            self.edit.apply_operation(root, {"op": "move_node", "node_id": "B", "x": 46, "y": 100})
            resolved = self.edit.apply_operation(root, {"op": "resolve_overlaps", "axis": "x", "gap": 40})
            self.assertEqual(resolved["status"], "applied")
            layout = self.edit.apply_operation(root, {"op": "auto_layout", "orientation": "left-to-right"})
            self.assertTrue(layout["layers"])
            self.edit.ensure_graph_valid(root, expand=True)

    def test_cyclic_auto_layout_requires_explicit_order(self):
        with tempfile.TemporaryDirectory() as temp:
            root = ET.parse(self.fixture(Path(temp))).getroot()
            self.edit.apply_operation(root, {"op": "add_edge", "edge_id": "cycle", "from": "C", "to": "A"})
            with self.assertRaisesRegex(ValueError, "node_order"):
                self.edit.apply_operation(root, {"op": "auto_layout"})
            result = self.edit.apply_operation(root, {"op": "auto_layout", "node_order": ["A", "B", "C"]})
            self.assertEqual(result["layers"], [["A"], ["B"], ["C"]])

    def test_explicit_legacy_metadata_binding(self):
        root = ET.fromstring('<svg width="300" height="100"><g id="g1"><rect id="r1" x="10" y="10" width="80" height="50"/><text id="t1">A</text></g><g id="g2"><rect id="r2" x="150" y="10" width="80" height="50"/><text id="t2">B</text></g><line id="l1"/></svg>')
        result = self.edit.apply_operation(root, {"op": "bind_graph_metadata", "nodes": [{"element_id": "g1", "shape_id": "r1", "label_id": "t1", "node_id": "A"}, {"element_id": "g2", "shape_id": "r2", "label_id": "t2", "node_id": "B"}], "edges": [{"element_id": "l1", "from": "A", "to": "B"}]})
        self.assertEqual(result["nodes"], 2); self.edit.ensure_graph_valid(root)

    def test_render_is_atomic_and_provenance_has_graph_snapshots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = self.fixture(root); output = root / "out"
            panel = {"id": "A", "type": "edit", "source_files": [source.name], "operations": [{"op": "auto_layout", "orientation": "left-to-right", "expand_viewbox": True}, {"op": "move_node", "node_id": "missing", "x": 1, "y": 1}]}
            plan = {"input_root": str(root), "panels": [panel]}
            with self.assertRaisesRegex(ValueError, "unknown node"):
                self.edit.render_panel(plan, panel, root / "figure-plan.json", output)
            self.assertFalse((output / "panel_a.svg").exists())
            panel["operations"] = [{"op": "auto_layout", "orientation": "left-to-right", "expand_viewbox": True}]
            provenance = self.edit.render_panel(plan, panel, root / "figure-plan.json", output)
            self.assertEqual(provenance["schema_version"], "2.0"); self.assertTrue(provenance["graph_before"]["nodes"]); self.assertTrue(provenance["graph_after"]["edges"])


if __name__ == "__main__": unittest.main()
