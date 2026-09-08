from __future__ import annotations
import base64
import copy
import math
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
from assemble_figure import qname, prefix_ids, svg_geometry, export_with_browser
from .contracts import read, write, sha, fresh, box
from .workflow import select

SCRIPTS = Path(__file__).resolve().parents[1]

def inspect_structure(brief, path):
    tree = ET.parse(path).getroot()
    elements = list(tree.iter())
    ids = [e.get("id") for e in elements if e.get("id")]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate SVG IDs")
    by_id = {e.get("id"): e for e in elements if e.get("id")}
    for node in brief.get("nodes", []):
        element = by_id.get(node["id"]+"-label")
        if element is None or element.tag != qname("text") or "".join(element.itertext()) != node["label"].replace("\n", ""):
            raise ValueError("Missing or changed editable label")
    for edge in brief.get("edges", []):
        element = by_id.get(edge["id"])
        if element is None or element.tag != qname("path") or element.get("data-from") != edge["from"] or element.get("data-to") != edge["to"] or element.get("marker-end") != "url(#arrow-head)":
            raise ValueError("Missing or changed scientific arrow")
    for panel in brief["panels"]:
        element = by_id.get(panel["id"])
        if element is None:
            raise ValueError("Missing panel")
        if panel["kind"] == "data" and any(e.tag == qname("image") for e in element.iter()):
            raise ValueError("Generated pixels in a data panel")
    return {"unique_ids": True, "editable_labels": True, "scientific_arrows": True, "vector_data_panels": True}

def compose(root, layout_path, requested=None):
    brief, state = fresh(root)
    cid, candidate, report = select(root, brief, state, requested)
    if report.get("clean_background") is not True or not report.get("clean_background_evidence"):
        raise ValueError("Background still needs text/arrow cleanup and visual confirmation")
    if any(p["kind"] == "data" for p in brief["panels"]) and (report.get("data_regions_empty") is not True or not report.get("data_regions_empty_evidence")):
        raise ValueError("Confirm generated pixels contain no marks in final data regions")
    layout = read(layout_path)
    if layout.get("image_sha256") != candidate["image_sha256"]:
        raise ValueError("Layout must bind selected image")
    canvas = brief["canvas"]
    width, height = canvas["width_mm"], canvas["height_mm"]
    boxes = layout.get("panels", {})
    nodes = layout.get("nodes", {})
    if set(boxes) != {p["id"] for p in brief["panels"]} or set(nodes) != {n["id"] for n in brief.get("nodes", [])}:
        raise ValueError("Layout must contain every panel and node exactly once")
    for value in list(boxes.values()) + list(nodes.values()):
        box(value, width, height)
    bg_box = layout.get("background_box_mm", [0, 0, width, height])
    box(bg_box, width, height)
    # A figure may use transparent margins; never distort the generated scientific asset.
    actual_w, actual_h = candidate["size"]
    if abs(actual_w / actual_h / (bg_box[2] / bg_box[3]) - 1) > .01:
        raise ValueError("Background aspect ratio does not match layout")
    effective_dpi = min(actual_w * 25.4 / bg_box[2], actual_h * 25.4 / bg_box[3])
    if effective_dpi < canvas["min_effective_dpi"]:
        raise ValueError(f"Insufficient native raster resolution: {effective_dpi:.1f} DPI")
    revision = len(state.get("compositions", [])) + 1
    while (root / "compositions" / f"v{revision}").exists():
        revision += 1
    work = root / "compositions" / f"v{revision}"
    work.mkdir(parents=True)
    tree = ET.Element(qname("svg"), {"width": f"{width}mm", "height": f"{height}mm", "viewBox": f"0 0 {width} {height}"})
    ET.SubElement(tree, qname("rect"), {"width": str(width), "height": str(height), "fill": "white"})
    ET.SubElement(tree, qname("image"), {"id": "concept-background", "data-role": "illustrative-raster",
        "x": str(bg_box[0]), "y": str(bg_box[1]), "width": str(bg_box[2]), "height": str(bg_box[3]),
        "href": "data:image/png;base64," + base64.b64encode((root / candidate["image"]).read_bytes()).decode()})
    data_specs = []
    for panel in brief["panels"]:
        if panel["kind"] == "data":
            spec = copy.deepcopy(panel["plot"])
            spec["figure_size_inches"] = [boxes[panel["id"]][2]/25.4, boxes[panel["id"]][3]/25.4]
            data_specs.append(spec)
    if data_specs:
        inputs = work / "inputs"
        inputs.mkdir()
        source_map = {}
        for panel in data_specs:
            for spec in panel.get("subplots", [panel]):
                copies = []
                for original in spec["source_files"]:
                    if original not in source_map:
                        target = inputs / f"{len(source_map)}-{Path(original).name}"
                        shutil.copy2(original, target)
                        source_map[original] = str(target.resolve())
                    copies.append(source_map[original])
                spec["source_files"] = copies
        write(work / "source-mapping.json", source_map)
        plan = {"input_root": str(inputs.resolve()), "open_questions": [], "panels": data_specs}
        write(work / "data-plan.json", plan)
        subprocess.run([sys.executable, str(SCRIPTS / "backends/matplotlib_backend.py"), str(work / "data-plan.json"),
                        "--output-dir", str(work / "panels"), "--formats", "svg"], check=True)
        from quality.data_provenance import verify_data_provenance
        checks = verify_data_provenance(work / "panels/provenance.json", plan)
        if any(c["status"] == "fail" for c in checks):
            raise ValueError("Data provenance failed")
        write(work / "data-qa.json", checks)
    for panel in brief["panels"]:
        x, y, w, h = boxes[panel["id"]]
        if panel["kind"] == "data":
            source = work / "panels" / f"panel_{panel['id'].lower()}.svg"
            subtree = ET.parse(source).getroot()
            if any(e.tag == qname("image") for e in subtree.iter()):
                raise ValueError("Data panel must remain vector")
            _, _, vb = svg_geometry(subtree)
            prefix_ids(subtree, panel["id"])
            element = ET.SubElement(tree, qname("svg"), {"id": panel["id"], "data-role": "data-panel",
                "x": str(x), "y": str(y), "width": str(w), "height": str(h), "viewBox": vb})
            element.extend(list(subtree))
        else:
            ET.SubElement(tree, qname("g"), {"id": panel["id"], "data-role": "concept-panel"})
        text = ET.SubElement(tree, qname("text"), {"id": f"panel-label-{panel['id']}", "x": str(x), "y": str(max(3, y-1)),
                            "font-size": str(canvas["min_font_pt"]*25.4/72), "font-family": "Arial"})
        text.text = panel.get("label", panel["id"])
    defs = ET.SubElement(tree, qname("defs"))
    marker = ET.SubElement(defs, qname("marker"), {"id": "arrow-head", "viewBox": "0 0 10 10", "refX": "9", "refY": "5", "markerWidth": "5", "markerHeight": "5", "orient": "auto-start-reverse"})
    ET.SubElement(marker, qname("path"), {"d": "M 0 0 L 10 5 L 0 10 z", "fill": "#263b40"})
    for edge in brief.get("edges", []):
        a, b = nodes[edge["from"]], nodes[edge["to"]]
        if abs((b[0]+b[2]/2)-(a[0]+a[2]/2)) >= abs((b[1]+b[3]/2)-(a[1]+a[3]/2)):
            right = b[0] > a[0]
            start = [a[0]+(a[2] if right else 0), a[1]+a[3]/2]
            end = [b[0]+(0 if right else b[2]), b[1]+b[3]/2]
        else:
            down = b[1] > a[1]
            start = [a[0]+a[2]/2, a[1]+(a[3] if down else 0)]
            end = [b[0]+b[2]/2, b[1]+(0 if down else b[3])]
        ET.SubElement(tree, qname("path"), {"id": edge["id"], "data-role": "scientific-arrow", "data-from": edge["from"], "data-to": edge["to"],
            "d": f"M {start[0]} {start[1]} L {end[0]} {end[1]}", "fill": "none", "stroke": "#263b40", "stroke-width": ".4", "marker-end": "url(#arrow-head)"})
    for node in brief.get("nodes", []):
        x,y,w,h = nodes[node["id"]]
        group = ET.SubElement(tree, qname("g"), {"id": node["id"], "data-role": "scientific-node"})
        text = ET.SubElement(group, qname("text"), {"id": node["id"]+"-label", "x": str(x+w/2), "y": str(y+h/2),
             "text-anchor": "middle", "font-family": "Arial", "font-size": str(canvas["min_font_pt"]*25.4/72), "fill": "#182e34"})
        for i, line in enumerate(node["label"].split("\n")):
            ET.SubElement(text, qname("tspan"), {"x": str(x+w/2), "dy": "0" if i == 0 else "1.2em"}).text = line
    ET.ElementTree(tree).write(work / "figure.svg", encoding="utf-8", xml_declaration=True)
    write(work / "layout.json", layout)
    (work / "caption.md").write_text(brief["caption"], encoding="utf-8")
    # Bind all intermediate code, data provenance and vector panels, not only final pixels.
    hashes = {str(p.relative_to(work)): sha(p) for p in work.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    composition = {"path": str(work.relative_to(root)), "candidate": cid, "hashes": hashes, "effective_dpi": effective_dpi}
    state.setdefault("compositions", []).append(composition)
    state["status"] = "needs-revision"
    write(root / "state.json", state)
    return {"status": "needs-revision", "composition": composition}

def export(root, review_path=None, approval_path=None, svg_only=False):
    brief, state = fresh(root)
    if not state.get("compositions"):
        raise ValueError("Compose before export")
    composition = state["compositions"][-1]
    work = root / composition["path"]
    for relative, digest in composition["hashes"].items():
        if not (work / relative).is_file() or sha(work / relative) != digest:
            raise ValueError("Composition changed; recompose and review")
    out = work / "final"
    out.mkdir(exist_ok=True)
    svg = out / "figure.svg"
    structural = inspect_structure(brief, work / "figure.svg")
    existing = composition.get("export_hashes")
    if existing:
        if {p.name: sha(p) for p in out.iterdir() if p.is_file()} != existing:
            raise ValueError("Export changed; old review invalid")
    else:
        shutil.copy2(work / "figure.svg", svg)
    canvas = brief["canvas"]
    if not svg_only and not existing:
        # PDF physical size is controlled at 96 CSS px/in; PNG is a separate 300-DPI render.
        export_with_browser(svg, round(canvas["width_mm"]*96/25.4), round(canvas["height_mm"]*96/25.4), png=None, pdf=out/"figure.pdf")
        export_with_browser(svg, math.ceil(canvas["width_mm"]*300/25.4), math.ceil(canvas["height_mm"]*300/25.4), png=out/"figure.png", pdf=None)
    hashes = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
    composition["export_hashes"] = hashes
    review = read(review_path) if review_path else {}
    required = {"scientific-content", "exact-labels", "arrow-directions", "no-duplicate-labels", "no-clipping", "font-size", "caption-consistency", "pdf-render-inspected", "paper-size-legibility"}
    passed = (not svg_only and {"figure.svg", "figure.pdf", "figure.png"} <= set(hashes) and review.get("artifact_hashes") == hashes
              and bool(review.get("reviewer")) and set(review.get("checks", {})) == required
              and all(c.get("status") == "pass" and c.get("evidence") for c in review["checks"].values()))
    status = "awaiting-user-review" if passed else "needs-revision"
    if approval_path:
        approval = read(approval_path)
        if not passed or approval.get("artifact_hashes") != hashes or approval.get("decision") != "approved" or not approval.get("reviewer") or not approval.get("user_confirmation"):
            raise ValueError("Human approval must bind passing current artifacts and an explicit user confirmation")
        status = "complete"
        write(work / "human-approval.json", approval)
    if review_path:
        write(work / "delivery-review.json", review)
    report = {"status": status, "technical_status": "pass", "scientific_visual_status": "pass" if passed else "pending",
              "human_review_status": "approved" if status == "complete" else "pending", "artifact_hashes": hashes,
              "effective_dpi": composition["effective_dpi"], "editable": ["critical labels", "major arrows", "vector data panels"],
              "raster": ["generated conceptual background"], "selected_candidate": composition["candidate"], "structural_checks": structural}
    state["status"] = status
    write(root / "state.json", state)
    write(root / "reports/delivery.json", report)
    return report
