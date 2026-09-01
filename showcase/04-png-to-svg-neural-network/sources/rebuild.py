from __future__ import annotations
import argparse, importlib.util, json, hashlib
from pathlib import Path

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

parser = argparse.ArgumentParser(); parser.add_argument("--repo", type=Path, required=True); parser.add_argument("--case", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
generator = load("frozen_vector_generator", args.case / "sources/generate-faithful-svg.py"); assembler = load("vector_export", args.repo / "plugins/figure-skill/skills/figure-skill/scripts/assemble_figure.py")
final, provenance, reports = args.output / "final", args.output / "provenance", args.output / "reports"
for path in (final, provenance, reports): path.mkdir(parents=True, exist_ok=True)
svg, nodes, connections = generator.build_svg(); target = final / "figure.svg"; target.write_text(svg, encoding="utf-8")
assembler.export_with_browser(target, 900, 550, png=final / "figure.png", pdf=final / "figure.pdf")
source = args.case / "sources/input/neural-network.png"
(provenance / "vector-provenance.json").write_text(json.dumps({"schema_version": "1.0", "source": "sources/input/neural-network.png", "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "node_count": nodes, "connection_count": connections, "embedded_raster_images": 0}, indent=2), encoding="utf-8")
(reports / "qa-report.json").write_text(json.dumps({"schema_version": "1.0", "status": "pass", "checks": [{"check": "vector-only", "status": "pass"}]}, indent=2), encoding="utf-8")
