from __future__ import annotations
import copy
import tempfile
import unittest
import sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from mainfig.contracts import read, write, sha, validate, fresh
from mainfig.workflow import prepare, import_candidate, select
from mainfig.render import compose, export

class MainFigureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "run"
        source = self.base / "methods.md"
        source.write_text("Encoder flows to Memory.")
        self.brief = {"claim": "Encoding and memory", "caption": "Demonstration only.", "reading_order": ["A"],
            "visual_focus": "Memory", "forbidden_content": ["invented data"], "open_questions": [],
            "sources": [{"id": "methods", "path": str(source), "location": "line 1"}],
            "requirements": [{"id": "flow", "text": "Encoder flows to Memory", "source_ids": ["methods"]}],
            "panels": [{"id": "A", "kind": "concept", "box_mm": [5,5,170,90], "requirement_ids": ["flow"]}],
            "nodes": [{"id": "encoder", "label": "Encoder", "box_mm": [10,10,35,10], "requirement_ids": ["flow"]},
                      {"id": "memory", "label": "Memory", "box_mm": [100,10,35,10], "requirement_ids": ["flow"]}],
            "edges": [{"id": "flowedge", "from": "encoder", "to": "memory", "meaning": "data-flow", "requirement_ids": ["flow"]}]}
        self.path = self.base / "brief.json"
        write(self.path, self.brief)
        self.image = self.base / "image.png"
        Image.new("RGB", (2160,1200), "white").save(self.image)
        self.prompt = self.base / "prompt.txt"
        self.prompt.write_text("Source-backed diagram")
        self.report = {"image_sha256": sha(self.image), "reviewer": "test fixture", "selection_reason": "Clear flow",
                       "score": 3, "clean_background": True, "clean_background_evidence": "Synthetic blank fixture",
                       "assertions": {"flow": {"status": "pass", "evidence": "Fixture only"}},
                       "visual": {k: {"status": "pass", "evidence": "Fixture only"} for k in ("focus", "reading_order", "density", "legibility")}}
        self.assessment = self.base / "assessment.json"
        write(self.assessment, self.report)
        self.layout = self.base / "layout.json"
        write(self.layout, {"image_sha256": sha(self.image), "panels": {"A": [5,5,170,90]},
                           "nodes": {n["id"]: n["box_mm"] for n in self.brief["nodes"]}})

    def tearDown(self):
        self.temp.cleanup()

    def imported(self):
        prepare(self.root, self.path)
        import_candidate(self.root, "candidate-1", self.image, self.prompt, self.assessment)

    def test_call_reservations_bound_retries_and_resume(self):
        self.imported()
        prepare(self.root)
        with self.assertRaises(ValueError): prepare(self.root)
        for i in range(2): prepare(self.root, kind="revision", parent="candidate-1", instruction="Preserve flow; change spacing")
        prepare(self.root, kind="cleanup", parent="candidate-1", instruction="Remove labels only")
        with self.assertRaises(ValueError): prepare(self.root, kind="cleanup", parent="candidate-1", instruction="Again")
        import_candidate(self.root, "revision-1", None, None, None, failed=True)
        self.assertEqual(len(read(self.root / "state.json")["attempts"]), 5)

    def test_scientific_failure_cannot_win_by_visual_score(self):
        self.imported()
        prepare(self.root)
        self.report["assertions"]["flow"]["status"] = "fail"
        self.report["score"] = 100
        write(self.assessment, self.report)
        import_candidate(self.root, "candidate-2", self.image, self.prompt, self.assessment)
        brief,state = fresh(self.root)
        self.assertEqual(select(self.root, brief, state)[0], "candidate-1")

    def test_source_change_invalidates_run(self):
        self.imported()
        (self.base / "methods.md").write_text("Changed")
        with self.assertRaises(ValueError): fresh(self.root)

    def test_image_change_invalidates_review(self):
        self.imported()
        (self.root / "candidates/candidate-1/image.png").write_bytes(b"changed")
        with self.assertRaises(ValueError): fresh(self.root)

    def test_compose_keeps_labels_arrows_editable(self):
        self.imported()
        result = compose(self.root, self.layout)
        svg = (self.root / result["composition"]["path"] / "figure.svg").read_text()
        self.assertIn('id="encoder-label"', svg)
        self.assertIn('data-from="encoder"', svg)
        self.assertIn('data-to="memory"', svg)
        report = export(self.root, svg_only=True)
        self.assertEqual(report["status"], "needs-revision")

    def test_export_tampering_is_not_overwritten(self):
        self.imported()
        compose(self.root, self.layout)
        export(self.root, svg_only=True)
        (self.root / "compositions/v1/final/figure.svg").write_text("tampered")
        with self.assertRaises(ValueError): export(self.root, svg_only=True)

    def test_duplicate_ids_and_wrong_edge_are_rejected(self):
        self.brief["edges"][0]["to"] = "absent"
        with self.assertRaises(ValueError): validate(self.brief, self.base)

    def test_dirty_background_cannot_be_covered_with_labels(self):
        self.report["clean_background"] = False
        write(self.assessment, self.report)
        self.imported()
        with self.assertRaises(ValueError): compose(self.root, self.layout)

    def test_changed_layout_does_not_change_scientific_edges(self):
        self.imported()
        layout = read(self.layout)
        layout["nodes"]["invented"] = [1,1,2,2]
        write(self.layout, layout)
        with self.assertRaises(ValueError): compose(self.root, self.layout)

    def test_missing_source_and_unresolved_questions_block_generation(self):
        self.brief["open_questions"] = ["Unknown direction"]
        write(self.path, self.brief)
        with self.assertRaises(ValueError): prepare(self.root, self.path)
        self.assertFalse((self.root / "state.json").exists())

    def test_data_panel_uses_snapshotted_csv_and_stays_vector(self):
        csv = self.base / "results.csv"
        csv.write_text("Method,Accuracy\nA,61.8\nB,73.6\n")
        self.brief["sources"].append({"id": "data", "path": str(csv), "location": "rows 2-3"})
        self.brief["panels"].append({"id": "B", "kind": "data", "box_mm": [5,45,170,50], "requirement_ids": ["flow"],
            "plot": {"id": "B", "type": "data-plot", "visual_form": "bar-chart", "source_files": [str(csv)], "x": "Method", "y": "Accuracy", "title": "Demo"}})
        write(self.path,self.brief)
        self.report.update(data_regions_empty=True,data_regions_empty_evidence="Synthetic fixture has no pixels in data region")
        write(self.assessment,self.report)
        layout=read(self.layout);layout["panels"]["B"]=[5,45,170,50];write(self.layout,layout)
        self.imported()
        result=compose(self.root,self.layout)
        work=self.root/result["composition"]["path"]
        self.assertEqual((work/"inputs/0-results.csv").read_bytes(),csv.read_bytes())
        self.assertIn('data-role="data-panel"',(work/"figure.svg").read_text())
        self.assertTrue(all(c["status"] != "fail" for c in read(work/"data-qa.json")))
        (work/"inputs/0-results.csv").write_text("tampered")
        with self.assertRaises(ValueError): export(self.root,svg_only=True)

    def test_human_approval_cannot_complete_svg_only_export(self):
        self.imported();compose(self.root,self.layout)
        report=export(self.root,svg_only=True)
        approval=self.base/"human.json"
        write(approval,{"artifact_hashes":report["artifact_hashes"],"reviewer":"fixture","decision":"approved","user_confirmation":"fixture only"})
        with self.assertRaises(ValueError): export(self.root,approval_path=approval,svg_only=True)

if __name__ == "__main__": unittest.main()
