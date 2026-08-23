#!/usr/bin/env python3
"""Create editable draw.io files and optional MCP handoff requests from a figure plan."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-") or "node"


def render_drawio(panel: dict, output: Path) -> dict:
    entities = [str(item).strip() for item in panel.get("entities", []) if str(item).strip()]
    if not 2 <= len(entities) <= 10:
        raise ValueError(f"panel {panel.get('id')} requires 2-10 entities")
    root = ET.Element("mxfile", {
        "host": "figure-skill",
        "modified": datetime.now(timezone.utc).isoformat(),
        "agent": "Codex",
        "version": "24.7.17",
        "compressed": "false",
    })
    diagram = ET.SubElement(root, "diagram", {"id": f"panel-{panel.get('id', 'A')}", "name": str(panel.get("title") or "Figure")})
    model = ET.SubElement(diagram, "mxGraphModel", {
        "dx": "1000", "dy": "600", "grid": "1", "gridSize": "10", "guides": "1",
        "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1", "page": "1",
        "pageScale": "1", "pageWidth": "1169", "pageHeight": "827", "math": "0", "shadow": "0",
    })
    graph_root = ET.SubElement(model, "root")
    ET.SubElement(graph_root, "mxCell", {"id": "0"})
    ET.SubElement(graph_root, "mxCell", {"id": "1", "parent": "0"})
    horizontal = panel.get("reading_order", "left-to-right") != "top-to-bottom"
    positions = {}
    for index, entity in enumerate(entities):
        node_id = f"node-{safe_id(entity)}"
        x = 80 + index * 220 if horizontal else 250
        y = 140 if horizontal else 80 + index * 130
        positions[entity.lower()] = node_id
        cell = ET.SubElement(graph_root, "mxCell", {
            "id": node_id,
            "value": entity,
            "style": "rounded=1;whiteSpace=wrap;html=1;fillColor=#f2f2f2;strokeColor=#222222;fontSize=16;",
            "vertex": "1", "parent": "1",
        })
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": "150", "height": "72", "as": "geometry"})
    for index, edge in enumerate(panel.get("edges", []), start=1):
        source = positions.get(str(edge.get("from", "")).lower())
        target = positions.get(str(edge.get("to", "")).lower())
        if not source or not target:
            raise ValueError(f"edge references unknown draw.io entity: {edge}")
        cell = ET.SubElement(graph_root, "mxCell", {
            "id": f"edge-{index}", "value": "",
            "style": "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;endFill=1;strokeWidth=2;",
            "edge": "1", "parent": "1", "source": source, "target": target,
        })
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    return {"panel": panel.get("id"), "output": output.name, "entities": len(entities), "edges": len(panel.get("edges", []))}


def render_plan(plan: dict, output_dir: Path) -> dict:
    panels = [panel for panel in plan.get("panels", []) if panel.get("type") == "illustration"]
    if not panels:
        raise ValueError("no illustration panels found for draw.io export")
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    requests = []
    for panel in panels:
        target = output_dir / f"panel_{str(panel['id']).lower()}.drawio"
        rendered.append(render_drawio(panel, target))
        xml = target.read_text(encoding="utf-8")
        requests.append({
            "panel": panel.get("id"),
            "official_server": "jgraph/drawio-mcp",
            "preferred_tool": "create_diagram",
            "fallback_tool": "open_drawio_xml",
            "arguments": {"xml": xml},
        })
    manifest = {"schema_version": "1.0", "rendered": rendered, "mcp_handoffs": requests}
    (output_dir / "drawio-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    manifest = render_plan(plan, args.output_dir.resolve())
    print(f"Created {len(manifest['rendered'])} draw.io source file(s) -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
