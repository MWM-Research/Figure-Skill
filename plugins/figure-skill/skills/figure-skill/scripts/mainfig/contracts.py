from __future__ import annotations
import hashlib
import json
import math
import re
from pathlib import Path

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", value):
        raise ValueError(f"Invalid ID: {value}")
    return value

def box(value, width, height):
    if len(value) != 4 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in value):
        raise ValueError("Box must contain four finite numbers in mm")
    x, y, w, h = value
    if min(x, y) < 0 or min(w, h) <= 0 or x+w > width or y+h > height:
        raise ValueError("Panel or node outside canvas")

def validate(brief, base):
    if brief.get("open_questions"):
        raise ValueError("Resolve scientific open_questions before generation")
    for key in ("claim", "caption", "reading_order", "visual_focus", "forbidden_content"):
        if not brief.get(key):
            raise ValueError(f"Missing design field: {key}")
    canvas = brief.setdefault("canvas", {})
    canvas.setdefault("width_mm", 180)
    canvas.setdefault("height_mm", 100)
    canvas.setdefault("min_font_pt", 8)
    canvas.setdefault("min_effective_dpi", 300)
    for value in canvas.values():
        if not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
            raise ValueError("Canvas values must be positive finite numbers")
    if canvas["min_font_pt"] < 8:
        raise ValueError("Main figure labels must be at least 8 pt")
    sources = brief.get("sources", [])
    source_ids = set()
    for item in sources:
        key = identifier(item["id"])
        if key in source_ids:
            raise ValueError("Duplicate source ID")
        source_ids.add(key)
        path = (base / item["path"]).resolve()
        if not path.is_file() or not item.get("location"):
            raise ValueError("Source needs a readable file and precise location")
        item["path"] = str(path)
        current = sha(path)
        if item.get("sha256") and item["sha256"] != current:
            raise ValueError("Source hash changed")
        item["sha256"] = current
    if not source_ids:
        raise ValueError("Scientific sources are required")
    requirements = brief.get("requirements", [])
    req_ids = set()
    for item in requirements:
        key = identifier(item["id"])
        if key in req_ids or not item.get("text") or not item.get("source_ids") or not set(item["source_ids"]) <= source_ids:
            raise ValueError("Every unique scientific requirement needs source references")
        req_ids.add(key)
    if not req_ids:
        raise ValueError("Scientific requirements are required")
    if not brief.get("panels"):
        raise ValueError("At least one panel is required")
    ids = set()
    for panel in brief["panels"]:
        pid = identifier(panel["id"])
        if pid in ids:
            raise ValueError("Duplicate panel ID")
        ids.add(pid)
        box(panel["box_mm"], canvas["width_mm"], canvas["height_mm"])
        if panel["kind"] not in {"concept", "data"}:
            raise ValueError("Panels must be concept or data")
        if not panel.get("requirement_ids") or not set(panel["requirement_ids"]) <= req_ids:
            raise ValueError("Panel lacks requirement references")
        if panel["kind"] == "data":
            plot = panel["plot"]
            if plot.get("type") not in {"data-plot", "data-plot-grid"}:
                raise ValueError("Use a deterministic data plot spec")
            plot["id"] = pid
            for spec in plot.get("subplots", [plot]):
                for source in spec.get("source_files", []):
                    if str((base / source).resolve()) not in {s["path"] for s in sources}:
                        raise ValueError("Data plot source not registered")
                spec["source_files"] = [str((base / p).resolve()) for p in spec.get("source_files", [])]
    for group in ("nodes", "edges"):
        seen = set()
        for item in brief.get(group, []):
            key = identifier(item["id"])
            if key in seen or key in ids:
                raise ValueError("Duplicate element ID")
            seen.add(key)
            if not item.get("requirement_ids") or not set(item["requirement_ids"]) <= req_ids:
                raise ValueError("Node/edge lacks scientific references")
            if group == "nodes":
                if not item.get("label"):
                    raise ValueError("Node needs exact label")
                box(item["box_mm"], canvas["width_mm"], canvas["height_mm"])
        ids |= seen
    node_ids = {n["id"] for n in brief.get("nodes", [])}
    for edge in brief.get("edges", []):
        if edge["from"] not in node_ids or edge["to"] not in node_ids or edge["from"] == edge["to"] or not edge.get("meaning"):
            raise ValueError("Invalid scientific edge")
    return brief

def fresh(root):
    state = read(root / "state.json")
    if sha(root / "brief.json") != state["brief_sha256"]:
        raise ValueError("Brief changed; prepare a new run")
    brief = read(root / "brief.json")
    for item in brief["sources"]:
        if not Path(item["path"]).is_file() or sha(item["path"]) != item["sha256"]:
            raise ValueError("Source changed; old review is invalid")
    for item in state["candidates"].values():
        for reference in item.get("references", []):
            if sha(root / reference["path"]) != reference["sha256"]:
                raise ValueError("Reference changed; old review is invalid")
        for key in ("image", "prompt", "assessment"):
            if item.get(key) and sha(root / item[key]) != item[key + "_sha256"]:
                raise ValueError(f"Candidate {key} changed")
    return brief, state

def assessment_pass(brief, report, image_hash):
    assertions = report.get("assertions", {})
    return (report.get("image_sha256") == image_hash
            and set(assertions) == {r["id"] for r in brief["requirements"]}
            and all(item.get("status") == "pass" and item.get("evidence") for item in assertions.values())
            and bool(report.get("reviewer"))
            and all(report.get("visual", {}).get(key, {}).get("status") == "pass"
                    and report["visual"][key].get("evidence")
                    for key in ("focus", "reading_order", "density", "legibility")))
