#!/usr/bin/env python3
"""Render editable SVG architecture and workflow panels from a figure plan."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def qname(name: str) -> str:
    return f"{{{SVG_NS}}}{name}"


def safe_id(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-")
    return normalized or "node"


def render_diagram(panel: dict, output: Path) -> dict:
    entities = [str(item).strip() for item in panel.get("entities", []) if str(item).strip()]
    if not 2 <= len(entities) <= 10:
        raise ValueError(f"panel {panel.get('id')} requires 2-10 entities, got {len(entities)}")
    if len(set(entity.lower() for entity in entities)) != len(entities):
        raise ValueError(f"panel {panel.get('id')} contains duplicate entities")
    if any(len(entity) > 40 for entity in entities):
        raise ValueError(f"panel {panel.get('id')} contains a label longer than 40 characters")

    direction = panel.get("reading_order", "left-to-right")
    horizontal = direction != "top-to-bottom"
    box_width, box_height, gap, margin = 150, 72, 72, 46
    title_space, caption_space = 54, 44
    if horizontal:
        width = margin * 2 + len(entities) * box_width + (len(entities) - 1) * gap
        height = margin * 2 + title_space + box_height + caption_space
    else:
        width = margin * 2 + box_width + 220
        height = margin * 2 + title_space + len(entities) * box_height + (len(entities) - 1) * gap + caption_space

    root = ET.Element(qname("svg"), {
        "width": str(width),
        "height": str(height),
        "viewBox": f"0 0 {width} {height}",
        "role": "img",
        "aria-label": str(panel.get("title") or "Scientific diagram"),
    })
    defs = ET.SubElement(root, qname("defs"))
    marker = ET.SubElement(defs, qname("marker"), {
        "id": "arrowhead", "markerWidth": "10", "markerHeight": "8",
        "refX": "9", "refY": "4", "orient": "auto", "markerUnits": "strokeWidth",
    })
    ET.SubElement(marker, qname("path"), {"d": "M0,0 L10,4 L0,8 Z", "fill": "#222222"})
    ET.SubElement(root, qname("rect"), {"width": "100%", "height": "100%", "fill": "white"})
    title = ET.SubElement(root, qname("text"), {
        "x": str(margin), "y": "34", "font-family": "Arial, sans-serif",
        "font-size": "20", "font-weight": "700", "fill": "#111111",
    })
    title.text = f"{panel.get('id', '')}  {panel.get('title') or 'Method pipeline'}".strip()

    positions: dict[str, tuple[float, float]] = {}
    for index, entity in enumerate(entities):
        x = margin + index * (box_width + gap) if horizontal else margin + 110
        y = margin + title_space if horizontal else margin + title_space + index * (box_height + gap)
        positions[entity.lower()] = (x, y)
        group = ET.SubElement(root, qname("g"), {"id": f"node-{safe_id(entity)}", "data-entity": entity})
        ET.SubElement(group, qname("rect"), {
            "x": str(x), "y": str(y), "width": str(box_width), "height": str(box_height),
            "rx": "14", "fill": "#f2f2f2", "stroke": "#222222", "stroke-width": "2",
        })
        label = ET.SubElement(group, qname("text"), {
            "x": str(x + box_width / 2), "y": str(y + box_height / 2 + 6),
            "text-anchor": "middle", "font-family": "Arial, sans-serif",
            "font-size": "17", "fill": "#111111",
        })
        label.text = entity

    provenance_edges = []
    for index, edge in enumerate(panel.get("edges", []), start=1):
        source_name = str(edge.get("from", ""))
        target_name = str(edge.get("to", ""))
        source = positions.get(source_name.lower())
        target = positions.get(target_name.lower())
        if source is None or target is None:
            raise ValueError(f"edge references an unknown entity: {source_name!r} -> {target_name!r}")
        sx, sy = source
        tx, ty = target
        if horizontal:
            x1, y1 = sx + box_width, sy + box_height / 2
            x2, y2 = tx, ty + box_height / 2
        else:
            x1, y1 = sx + box_width / 2, sy + box_height
            x2, y2 = tx + box_width / 2, ty
        ET.SubElement(root, qname("line"), {
            "id": f"edge-{index}", "x1": str(x1), "y1": str(y1), "x2": str(x2), "y2": str(y2),
            "stroke": "#222222", "stroke-width": "2", "marker-end": "url(#arrowhead)",
            "data-meaning": str(edge.get("meaning", "unspecified")),
        })
        provenance_edges.append({
            "from": source_name,
            "to": target_name,
            "meaning": edge.get("meaning"),
            "inferred": bool(edge.get("inferred")),
        })

    if panel.get("inference_requires_review") and panel.get("_review_status") != "approved":
        caption = ET.SubElement(root, qname("text"), {
            "x": str(width / 2), "y": str(height - 20), "text-anchor": "middle",
            "font-family": "Arial, sans-serif", "font-size": "13", "fill": "#555555",
        })
        caption.text = "Editable vector diagram - confirm inferred relationships before publication"

    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    return {
        "panel": panel.get("id"),
        "source_files": panel.get("source_files", []),
        "output": output.name,
        "entities": entities,
        "edges": provenance_edges,
    }


def render_plan(plan: dict, output_dir: Path, selected: set[str] | None = None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    panels = [
        panel for panel in plan.get("panels", [])
        if panel.get("type") == "illustration" and (not selected or str(panel.get("id")) in selected)
    ]
    if not panels:
        raise ValueError("no matching illustration panels found in the plan")
    rendered = []
    for panel in panels:
        output = output_dir / f"panel_{str(panel['id']).lower()}.svg"
        panel_for_render = dict(panel, _review_status=plan.get("review_status"))
        rendered.append(render_diagram(panel_for_render, output))
    provenance = {"schema_version": "1.0", "panels": rendered}
    (output_dir / "diagram-provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--panel", action="append")
    parser.add_argument("--allow-open-questions", action="store_true")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if plan.get("open_questions") and not args.allow_open_questions:
        raise SystemExit("figure plan has unresolved open_questions; resolve them before rendering")
    provenance = render_plan(plan, args.output_dir.resolve(), set(args.panel or []))
    print(f"Rendered {len(provenance['panels'])} illustration panel(s) -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
