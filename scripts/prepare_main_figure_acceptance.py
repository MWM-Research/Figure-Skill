"""Prepare three source-backed demonstration briefs; never generates images or approves them."""
from __future__ import annotations
import argparse
import shutil
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/figure-skill/skills/figure-skill/scripts"))
from mainfig.contracts import write
from mainfig.workflow import prepare

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = ROOT / "showcase/01-streambridge-cvpr-figure/sources"
    for name in ("overview", "mechanism", "mixed"):
        case = output / name
        case.mkdir()
        shutil.copy2(source / "methods.md", case / "methods.md")
        shutil.copy2(source / "results.csv", case / "results.csv")
        mechanisms = name == "mechanism"
        labels = ["Input visual\ntokens", "Memory\nCompressor", "Compressed\nvisual tokens"] if mechanisms else ["Video\nEncoder", "Memory\nCompressor", "Cross-modal\nMemory", "LLM"]
        width = 180
        count = len(labels)
        nodes = [{"id": f"node{i+1}", "label": label, "box_mm": [8+i*164/count, 12, 164/count-4, 10], "requirement_ids": ["method"]} for i,label in enumerate(labels)]
        brief = {"schema_version": "1.0", "claim": "Event-aware compression preserves key events while merging redundant tokens.",
            "caption": "StreamBridge++ demonstration adapted from the repository example, not a validated research result. " + ("Only the supplied memory-compression mechanism is illustrated." if mechanisms else "The supplied four-stage pipeline is illustrated.") + (" Panel B reproduces the CSV Accuracy column; its unit is unspecified, with no uncertainty estimates." if name == "mixed" else ""),
            "reading_order": ["A", "B"] if name == "mixed" else ["A"], "visual_focus": "Event-aware memory compression",
            "forbidden_content": ["brand logos", "invented data", "new training stages", "measured-looking photographs"], "open_questions": [],
            "canvas": {"width_mm": width, "height_mm": 145 if name == "mixed" else 100, "min_font_pt": 8, "min_effective_dpi": 300},
            "sources": [{"id": "methods", "path": "methods.md", "location": "lines 3-10"}],
            "requirements": [{"id": "method", "text": "Memory Compressor merges redundant visual tokens while preserving key events; this is conceptual and does not specify counts or compression ratios." if mechanisms else "Video Encoder -> Memory Compressor -> Cross-modal Memory -> LLM; compressed visual memory and user instructions support the LLM response.", "source_ids": ["methods"]}],
            "panels": [{"id": "A", "kind": "concept", "label": "a  Event-aware memory compression (demonstration)" if mechanisms else "a  StreamBridge++ method overview (demonstration)", "box_mm": [6,8,168,70], "requirement_ids": ["method"]}],
            "nodes": nodes, "edges": [{"id": f"edge{i+1}", "from": f"node{i+1}", "to": f"node{i+2}", "meaning": "conceptual processing flow", "requirement_ids": ["method"]} for i in range(count-1)]}
        if not mechanisms:
            brief["nodes"].append({"id": "instruction", "label": "User instructions", "box_mm": [136,25,38,8], "requirement_ids": ["method"]})
            brief["edges"].append({"id": "instructionedge", "from": "instruction", "to": "node4", "meaning": "instruction conditions response", "requirement_ids": ["method"]})
        if name == "mixed":
            brief["sources"].append({"id": "data", "path": "results.csv", "location": "Accuracy column, rows 2-6; demonstration values; units unspecified"})
            brief["requirements"].append({"id": "data", "text": "Panel B uses exactly the CSV Accuracy values without percentages, uncertainty, or significance claims.", "source_ids": ["data"]})
            brief["panels"].append({"id": "B", "kind": "data", "label": "b  Demonstration values (unit unspecified)", "box_mm": [7,96,166,45], "requirement_ids": ["data"],
                "plot": {"id": "B", "type": "data-plot", "visual_form": "bar-chart", "source_files": ["results.csv"], "x": "Method", "y": "Accuracy", "title": "Demonstration data", "unit": "unit unspecified"}})
        write(case / "design.json", brief)
        for _ in range(2): prepare(case / "run", case / "design.json")
    print(output)

if __name__ == "__main__": main()
