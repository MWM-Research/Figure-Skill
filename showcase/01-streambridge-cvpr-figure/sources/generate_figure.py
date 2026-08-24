#!/usr/bin/env python3
"""Deterministically generate the StreamBridge++ CVPR hybrid figure."""

from __future__ import annotations

import base64
import csv
import hashlib
import html
import json
import platform
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources"
ORIGINALS = SRC / "originals"
ASSETS = SRC / "assets"
FINAL = ROOT / "final"
PANELS = ROOT / "panels"
PROV = ROOT / "provenance"
REPORTS = ROOT / "reports"

W, H = 672, 442
BLUE = "#2563EB"
BLUE_DARK = "#1D4ED8"
BLUE_LIGHT = "#DBEAFE"
INK = "#1F2937"
MID = "#6B7280"
LIGHT = "#E5E7EB"
PALE = "#F8FAFC"
WHITE = "#FFFFFF"

VISIBLE_LABELS: set[str] = set()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def text(x: float, y: float, value: object, *, size: float = 10.5,
         weight: int = 400, fill: str = INK, anchor: str = "start",
         role: str = "label", rotate: int | None = None) -> str:
    label = str(value)
    VISIBLE_LABELS.add(label)
    transform = f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ""
    return (
        f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}" data-role="{role}"{transform}>{esc(label)}</text>'
    )


def rect(x: float, y: float, w: float, h: float, *, fill: str = WHITE,
         stroke: str = LIGHT, sw: float = 1, rx: float = 5,
         role: str = "panel-border", extra: str = "") -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
        f'data-role="{role}" {extra}/>'
    )


def line(x1: float, y1: float, x2: float, y2: float, *, stroke: str = MID,
         sw: float = 1, role: str = "axis", dash: str | None = None) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{stroke}" stroke-width="{sw}" data-role="{role}"{d}/>'
    )


def arrow(x1: float, y1: float, x2: float, y2: float, *, stroke: str = INK,
          sw: float = 1.5, dash: str | None = None) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<path d="M {x1} {y1} L {x2} {y2}" fill="none" stroke="{stroke}" '
        f'stroke-width="{sw}" marker-end="url(#arrow)" data-role="data-flow-arrow"{d}/>'
    )


def image_tag(path: Path, x: float, y: float, w: float, h: float, role: str) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        f'<image x="{x}" y="{y}" width="{w}" height="{h}" '
        f'preserveAspectRatio="xMidYMid slice" href="data:image/png;base64,{payload}" '
        f'data-role="{role}"/>'
    )


def svg_doc(width: float, height: float, body: str, *, view_x: float = 0,
            view_y: float = 0, metadata: dict | None = None,
            physical_width_mm: float | None = None,
            physical_height_mm: float | None = None) -> str:
    meta = ""
    if metadata:
        meta = f'<metadata id="provenance">{esc(json.dumps(metadata, ensure_ascii=False))}</metadata>'
    physical_width_mm = physical_width_mm if physical_width_mm is not None else width / 3.78
    physical_height_mm = physical_height_mm if physical_height_mm is not None else height / 3.78
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{physical_width_mm}mm" height="{physical_height_mm}mm" viewBox="{view_x} {view_y} {width} {height}">
  <defs>
    <marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L7,3.5 L0,7 Z" fill="{INK}"/>
    </marker>
  </defs>
  {meta}
  <rect x="{view_x}" y="{view_y}" width="{width}" height="{height}" fill="#FFFFFF" data-role="canvas"/>
  {body}
</svg>
'''


def prepare_assets() -> dict:
    ASSETS.mkdir(parents=True, exist_ok=True)
    transforms: list[dict] = []
    for name in ("frame_t-3", "frame_t-2", "frame_t-1", "frame_t"):
        src = ORIGINALS / f"{name}.jpg"
        dst = ASSETS / f"{name}.png"
        with Image.open(src) as im:
            im.convert("RGB").save(dst, format="PNG", optimize=False)
            dims = [im.width, im.height]
        transforms.append({
            "source": str(src.relative_to(ROOT)), "source_sha256": sha256(src),
            "derived": str(dst.relative_to(ROOT)), "derived_sha256": sha256(dst),
            "operation": "lossless container conversion JPEG decode to RGB PNG; SVG uses xMidYMid slice",
            "source_dimensions": dims,
        })

    heat_src = ORIGINALS / "attention_source.jpg"
    crop_boxes = {
        "attention_baseline.png": [40, 35, 439, 422],
        "attention_streambridgepp.png": [527, 35, 927, 422],
    }
    with Image.open(heat_src) as im:
        for name, box in crop_boxes.items():
            dst = ASSETS / name
            im.crop(tuple(box)).convert("RGB").save(dst, format="PNG", optimize=False)
            transforms.append({
                "source": str(heat_src.relative_to(ROOT)), "source_sha256": sha256(heat_src),
                "derived": str(dst.relative_to(ROOT)), "derived_sha256": sha256(dst),
                "operation": "pixel-preserving crop followed by RGB PNG encoding",
                "crop_box_xyxy": box,
            })
    return {"schema_version": "1.0", "asset_transforms": transforms}


def panel_a() -> str:
    out = [rect(0, 0, 648, 180, fill=WHITE, stroke="#CBD5E1", sw=1.1, rx=7)]
    out += [text(10, 17, "(a)", size=11.5, weight=700),
            text(34, 17, "Streaming architecture", size=11.5, weight=700)]

    frame_specs = [
        (ASSETS / "frame_t-3.png", 8, 48, "t−3"),
        (ASSETS / "frame_t-2.png", 47, 48, "t−2"),
        (ASSETS / "frame_t-1.png", 8, 86, "t−1"),
        (ASSETS / "frame_t.png", 47, 86, "t"),
    ]
    for path, x, y, label in frame_specs:
        out.append(image_tag(path, x, y, 34, 25, "video-frame-raster"))
        out.append(rect(x, y, 34, 25, fill="none", stroke="#334155", sw=.7, rx=1, role="frame-border"))
        out.append(text(x + 17, y + 34, label, size=8.8, anchor="middle", fill=MID))
    out.append(text(44, 38, "Streaming video", size=9.5, weight=600, anchor="middle"))
    out.append(arrow(84, 78, 99, 78))

    modules = [
        (99, 48, 79, 74, "Video Encoder", ["frame-level", "visual tokens"]),
        (205, 42, 99, 86, "Memory Compressor", ["adaptive merge", "preserve events"]),
        (331, 48, 96, 74, "Cross-modal Memory", ["retrieve historical", "context"]),
        (466, 48, 68, 74, "LLM", ["compressed", "visual memory"]),
    ]
    for x, y, w, h, title, detail in modules:
        fill = BLUE_LIGHT if title == "Memory Compressor" else PALE
        stroke = BLUE if title == "Memory Compressor" else "#94A3B8"
        out.append(rect(x, y, w, h, fill=fill, stroke=stroke, sw=1.2, rx=6, role="transformer-module"))
        out.append(text(x + w/2, y + 18, title, size=9.5, weight=700,
                        fill=BLUE_DARK if title == "Memory Compressor" else INK, anchor="middle"))
        out.append(text(x + w/2, y + 37, detail[0], size=8.2, fill=MID, anchor="middle"))
        out.append(text(x + w/2, y + 49, detail[1], size=8.2, fill=MID, anchor="middle"))

    # Editable vector token glyphs clarify event-aware merging without quantitative claims.
    for x in (215, 226, 237, 248, 259):
        out.append(f'<circle cx="{x}" cy="111" r="2.3" fill="{MID}" data-role="visual-token"/>')
    out.append(arrow(266, 111, 276, 111, stroke=BLUE, sw=1.1))
    for x, r in ((282, 2.6), (291, 4.0)):
        out.append(f'<circle cx="{x}" cy="111" r="{r}" fill="{BLUE}" data-role="compressed-token"/>')

    for yy in (98, 104, 110):
        out.append(line(346, yy, 412, yy, stroke="#94A3B8", sw=.9, role="memory-slot"))
    out.append(arrow(178, 78, 204, 78))
    out.append(arrow(304, 78, 330, 78))
    out.append(arrow(427, 78, 465, 78))
    out.append(arrow(534, 78, 558, 78))

    out.append(rect(452, 12, 96, 23, fill=WHITE, stroke=BLUE, sw=1, rx=11, role="instruction-chip"))
    out.append(text(500, 27, "User instruction", size=9.0, weight=600, anchor="middle", fill=BLUE_DARK))
    out.append(arrow(500, 35, 500, 47, stroke=BLUE, sw=1.2))

    out.append(rect(559, 52, 78, 54, fill=WHITE, stroke="#94A3B8", sw=1.1, rx=8, role="response-box"))
    out.append(text(598, 72, "Response", size=9.5, weight=700, anchor="middle"))
    out.append(text(598, 88, "stream-aware", size=8.2, fill=MID, anchor="middle"))
    out.append(text(253, 149, "Event-aware compression", size=9.3, weight=700, fill=BLUE_DARK, anchor="middle"))
    out.append(text(253, 162, "redundant tokens merge; salient events persist", size=8.4, fill=MID, anchor="middle"))
    return "\n".join(out)


def panel_b() -> str:
    out = [rect(0, 0, 180, 225, fill=WHITE, stroke="#CBD5E1", sw=1.1, rx=7),
           text(9, 17, "(b)", size=11.5, weight=700),
           text(32, 17, "Attention allocation", size=11.5, weight=700)]
    out += [text(49, 46, "Baseline", size=9.2, weight=600, anchor="middle"),
            text(129, 46, "StreamBridge++", size=9.2, weight=700, fill=BLUE_DARK, anchor="middle")]
    out.append(image_tag(ASSETS / "attention_baseline.png", 15, 57, 68, 78, "attention-heatmap-raster"))
    out.append(image_tag(ASSETS / "attention_streambridgepp.png", 95, 57, 68, 78, "attention-heatmap-raster"))
    for x in (15, 95):
        out.append(rect(x, 57, 68, 78, fill="none", stroke="#334155", sw=.7, rx=0, role="heatmap-border"))
        out.append(line(x, 142, x + 68, 142, stroke=INK, sw=1, role="axis"))
        out.append(f'<path d="M {x+68} 142 l -4 -2 l 0 4 z" fill="{INK}" data-role="axis-arrow"/>')
        out.append(text(x + 34, 156, "Block", size=8.7, anchor="middle", fill=MID))
    out.append(line(8, 135, 8, 57, stroke=INK, sw=1, role="axis"))
    out.append('<path d="M 8 57 l -2 4 l 4 0 z" fill="#1F2937" data-role="axis-arrow"/>')
    out.append(text(4, 96, "Head", size=8.7, anchor="middle", fill=MID, rotate=-90))
    out.append(text(90, 181, "Raster heatmaps; vector labels and axes", size=8.5, fill=MID, anchor="middle"))
    return "\n".join(out)


def read_results() -> list[dict[str, str]]:
    with (SRC / "results.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def panel_c(results: list[dict[str, str]], marks: list[dict]) -> str:
    out = [rect(0, 0, 280, 225, fill=WHITE, stroke="#CBD5E1", sw=1.1, rx=7),
           text(9, 17, "(c)", size=11.5, weight=700),
           text(32, 17, "Main comparison", size=11.5, weight=700)]
    metrics = [("Accuracy", "↑", 76), ("FLOPs", "↓", 145), ("Latency", "↓", 214)]
    rows_y = [65, 91, 117, 143, 169]
    # Highlight ours using both color and outline for grayscale robustness.
    out.append(rect(3, 155, 274, 26, fill="#EFF6FF", stroke=BLUE, sw=.8, rx=3, role="method-highlight"))
    for name, arrow_dir, x in metrics:
        out.append(text(x + 27, 43, f"{name} {arrow_dir}", size=9.1, weight=700, anchor="middle"))
        out.append(line(x, 51, x + 54, 51, stroke="#94A3B8", sw=.8, role="axis"))

    for idx, row in enumerate(results):
        y = rows_y[idx]
        ours = row["Method"] == "StreamBridge++"
        out.append(text(7, y + 3, row["Method"], size=8.4, weight=700 if ours else 400,
                        fill=BLUE_DARK if ours else INK))
    for metric, _, x in metrics:
        values = [float(row[metric]) for row in results]
        lo, hi = min(values), max(values)
        for idx, (row, value) in enumerate(zip(results, values)):
            y = rows_y[idx]
            ours = row["Method"] == "StreamBridge++"
            pos = x + 3 + (value - lo) / (hi - lo) * 31 if hi > lo else x + 18
            out.append(line(x + 3, y, x + 34, y, stroke=LIGHT, sw=1.2, role="axis"))
            out.append(f'<circle cx="{pos:.2f}" cy="{y}" r="{3.5 if ours else 2.8}" fill="{BLUE if ours else MID}" '
                       f'stroke="{BLUE_DARK if ours else WHITE}" stroke-width="0.8" data-role="main-result-mark"/>')
            display = row[metric]
            out.append(text(x + 53, y + 3, display, size=8.2, weight=700 if ours else 400,
                            fill=BLUE_DARK if ours else INK, anchor="end"))
            marks.append({
                "panel": "c", "role": "main-result-mark", "method": row["Method"],
                "metric": metric, "value": value, "display_value": display,
                "source": "sources/results.csv", "source_row": idx + 2, "source_column": metric,
                "transform": "identity; linear position within metric min/max",
            })
    out.append(text(140, 201, "All values shown exactly as provided", size=8.3, fill=MID, anchor="middle"))
    return "\n".join(out)


def read_ablation() -> list[dict[str, str]]:
    with (SRC / "ablation.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def panel_d(rows: list[dict[str, str]], marks: list[dict]) -> str:
    out = [rect(0, 0, 176, 225, fill=WHITE, stroke="#CBD5E1", sw=1.1, rx=7),
           text(9, 17, "(d)", size=11.5, weight=700),
           text(32, 17, "Ablation", size=11.5, weight=700),
           text(134, 43, "Accuracy ↑", size=9.0, weight=700, anchor="middle")]
    labels = [
        ["Baseline"], ["+ Memory", "Compressor"],
        ["+ Cross-modal", "Memory"], ["+ Event-aware", "Compression"],
    ]
    ys = [68, 101, 134, 167]
    lo, hi = 60.0, 75.0
    x0, span = 93, 70
    for idx, (row, y, lines_) in enumerate(zip(rows, ys, labels)):
        for j, label in enumerate(lines_):
            offset = 0 if len(lines_) == 1 else (-4 + j * 10)
            out.append(text(6, y + 3 + offset, label, size=8.0, weight=600 if idx == 3 else 400,
                            fill=BLUE_DARK if idx == 3 else INK))
        value = float(row["Accuracy"])
        width = (value - lo) / (hi - lo) * span
        fill = BLUE if idx == 3 else "#64748B"
        out.append(rect(x0, y - 6, width, 12, fill=fill, stroke=fill, sw=0, rx=2, role="ablation-result-bar"))
        out.append(text(min(x0 + width - 3, 162), y + 3, row["Accuracy"], size=8.1, weight=700,
                        fill=WHITE, anchor="end"))
        marks.append({
            "panel": "d", "role": "ablation-result-bar", "module": row["Module"],
            "metric": "Accuracy", "value": value, "display_value": row["Accuracy"],
            "source": "sources/ablation.csv", "source_row": idx + 2,
            "source_column": "Accuracy", "transform": "identity; bar begins at displayed axis minimum 60",
        })
    out.append(line(x0, 188, x0 + span, 188, stroke=INK, sw=.9, role="axis"))
    out.append(line(x0, 185, x0, 191, stroke=INK, sw=.9, role="axis"))
    out.append(line(x0 + span, 185, x0 + span, 191, stroke=INK, sw=.9, role="axis"))
    out.append(text(x0, 204, "60", size=8.0, fill=MID, anchor="middle"))
    out.append(text(x0 + span, 204, "75", size=8.0, fill=MID, anchor="middle"))
    return "\n".join(out)


def write_outputs() -> None:
    for directory in (FINAL, PANELS, PROV, REPORTS):
        directory.mkdir(parents=True, exist_ok=True)
    asset_prov = prepare_assets()
    marks: list[dict] = []
    a = panel_a()
    b = panel_b()
    c = panel_c(read_results(), marks)
    d = panel_d(read_ablation(), marks)

    composed = "\n".join([
        '<g id="panel-a" transform="translate(12 12)">' + a + '</g>',
        '<g id="panel-b" transform="translate(12 205)">' + b + '</g>',
        '<g id="panel-c" transform="translate(198 205)">' + c + '</g>',
        '<g id="panel-d" transform="translate(484 205)">' + d + '</g>',
    ])
    metadata = {
        "title": "StreamBridge++: Event-aware memory for streaming video",
        "route": "hybrid-composite", "generated_by": "sources/generate_figure.py",
        "quantitative_sources": ["sources/results.csv", "sources/ablation.csv"],
        "raster_sources": [str(p.relative_to(ROOT)) for p in sorted(ORIGINALS.glob("*.jpg"))],
    }
    final_svg = svg_doc(W, H, composed, metadata=metadata,
                        physical_width_mm=177.8, physical_height_mm=116.8)
    (FINAL / "figure.svg").write_text(final_svg, encoding="utf-8")
    (PANELS / "panel-a-pipeline.svg").write_text(svg_doc(648, 180, a), encoding="utf-8")
    (PANELS / "panel-b-attention.svg").write_text(svg_doc(180, 225, b), encoding="utf-8")
    (PANELS / "panel-c-results.svg").write_text(svg_doc(280, 225, c), encoding="utf-8")
    (PANELS / "panel-d-ablation.svg").write_text(svg_doc(176, 225, d), encoding="utf-8")
    # Canonical names consumed by Figure Skill QA.
    (PANELS / "panel_a.svg").write_text(svg_doc(648, 180, a), encoding="utf-8")
    (PANELS / "panel_b.svg").write_text(svg_doc(180, 225, b), encoding="utf-8")
    (PANELS / "panel_c.svg").write_text(svg_doc(280, 225, c), encoding="utf-8")
    (PANELS / "panel_d.svg").write_text(svg_doc(176, 225, d), encoding="utf-8")

    contract = {
        "roles": [
            {"role": "video-frame-raster", "kind": "raster", "svg_tag": "image", "expected_count": 4,
             "source_glob": "sources/assets/frame_*.png"},
            {"role": "attention-heatmap-raster", "kind": "raster", "svg_tag": "image", "expected_count": 2,
             "source_glob": "sources/assets/attention_*.png"},
            {"role": "transformer-module", "kind": "vector", "svg_tag": "rect", "expected_count": 4},
            {"role": "data-flow-arrow", "kind": "vector", "svg_tag": "path", "min_count": 7},
            {"role": "main-result-mark", "kind": "vector", "svg_tag": "circle", "expected_count": 15},
            {"role": "ablation-result-bar", "kind": "vector", "svg_tag": "rect", "expected_count": 4},
            {"role": "axis", "kind": "vector", "svg_tag": "line", "min_count": 10},
            {"role": "label", "kind": "vector", "svg_tag": "text", "min_count": 1},
        ],
        "unclassified_image_policy": "forbid", "exact_visible_labels": True,
    }
    plan = {
        "schema_version": "1.0", "title": "StreamBridge++ CVPR Figure",
        "route": "composite", "representation_mode": "hybrid-composite", "status": "approved",
        "review_status": "approved",
        "approval_basis": "User-approved implementation plan in the Codex task",
        "canvas": {"width_mm": 177.8, "height_mm": 116.8, "viewBox": [0, 0, W, H]},
        "layout": "full-width pipeline above three evidence panels; derived from content density",
        "panels": [
            {"id": "a", "title": "Streaming architecture", "type": "illustration"},
            {"id": "b", "title": "Attention allocation", "type": "illustration"},
            {"id": "c", "title": "Main comparison", "type": "data-plot"},
            {"id": "d", "title": "Ablation", "type": "data-plot"},
        ],
        "representation_contract": contract,
        "visible_labels": sorted(VISIBLE_LABELS),
        "open_questions": [],
        "constraints": {"forbid_invented_quantitative_claims": True},
        "data_policy": "identity values only; no invented units, uncertainty, or significance",
    }
    (ROOT / "figure-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    source_hashes = []
    for path in sorted([SRC / "methods.md", SRC / "results.csv", SRC / "ablation.csv", *ORIGINALS.glob("*.jpg")]):
        source_hashes.append({"path": str(path.relative_to(ROOT)), "sha256": sha256(path), "bytes": path.stat().st_size})
    provenance = {
        "schema_version": "1.0", "source_files": source_hashes,
        "frame_order": ["frame_t-3.jpg", "frame_t-2.jpg", "frame_t-1.jpg", "frame_t.jpg"],
        "frame_semantics": "user-confirmed same-video temporal order using folder enumeration",
        "method_relations": [
            {"from": "Streaming video", "to": "Video Encoder", "relation": "frame input"},
            {"from": "Video Encoder", "to": "Memory Compressor", "relation": "frame-level visual tokens"},
            {"from": "Memory Compressor", "to": "Cross-modal Memory", "relation": "compressed visual memory"},
            {"from": "Cross-modal Memory", "to": "LLM", "relation": "retrieved historical context"},
            {"from": "User instruction", "to": "LLM", "relation": "instruction input"},
            {"from": "LLM", "to": "Response", "relation": "generated response"},
        ],
        "label_substitution": {"source": "w/ ours", "vector_label": "StreamBridge++", "basis": "user-approved"},
        **asset_prov,
    }
    (PROV / "source-provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    (PROV / "plot-mark-provenance.json").write_text(json.dumps({"schema_version": "1.0", "marks": marks}, ensure_ascii=False, indent=2), encoding="utf-8")
    data_panels = []
    for panel_id, source_name in (("c", "results.csv"), ("d", "ablation.csv")):
        source_path = (SRC / source_name).resolve()
        panel_marks = []
        for mark in (item for item in marks if item["panel"] == panel_id):
            group_column = "Method" if panel_id == "c" else "Module"
            group_value = mark.get("method") if panel_id == "c" else mark.get("module")
            panel_marks.append({
                "source_row": mark["source_row"],
                "x": {"column": mark["source_column"], "value": mark["value"]},
                "group": {"column": group_column, "value": group_value},
            })
        data_panels.append({
            "panel": panel_id, "source_file": source_path.relative_to(ROOT).as_posix(),
            "source_sha256": sha256(source_path), "marks": panel_marks,
        })
    (PROV / "data-provenance.json").write_text(
        json.dumps({"schema_version": "1.0", "panels": data_panels}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    environment = {
        "python": platform.python_version(), "platform": platform.platform(),
        "pillow": Image.__version__, "generator_sha256": sha256(Path(__file__)),
    }
    (PROV / "environment.json").write_text(json.dumps(environment, indent=2), encoding="utf-8")

    # Chromium wrapper fixes the PDF page size and keeps the SVG vector-based.
    html_wrapper = f'''<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: 177.8mm 116.8mm; margin: 0; }}
html, body {{ margin: 0; width: 177.8mm; height: 116.8mm; overflow: hidden; background: white; }}
img {{ display: block; width: 177.8mm; height: 116.8mm; }}
</style></head><body><img src="figure.svg" alt="StreamBridge++ CVPR figure"></body></html>'''
    (FINAL / "render.html").write_text(html_wrapper, encoding="utf-8")


if __name__ == "__main__":
    write_outputs()
