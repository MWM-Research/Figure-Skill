#!/usr/bin/env python3
"""Apply exact deterministic text, callouts, arrows, and legends to a generated raster panel."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("annotation background must be a readable PNG")
    return struct.unpack(">II", header[16:24])


def browser_path() -> Path | None:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ]
    for command in ("msedge", "google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(command)
        if found:
            candidates.append(Path(found))
    return next((path for path in candidates if path.is_file()), None)


def select_panel(plan: dict, panel_id: str | None = None) -> dict:
    panels = [panel for panel in plan.get("panels", []) if panel.get("type") == "raster-illustration"]
    if panel_id:
        panels = [panel for panel in panels if str(panel.get("id")) == panel_id]
    if len(panels) != 1:
        raise ValueError("select exactly one raster-illustration panel with --panel")
    return panels[0]


def position(value: object, name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be [x, y] normalized coordinates")
    x, y = float(value[0]), float(value[1])
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise ValueError(f"{name} coordinates must be between 0 and 1")
    return x, y


def text_entries(spec: dict) -> list[str]:
    values = []
    for key in ("title", "subtitle", "footer"):
        item = spec.get(key)
        if isinstance(item, dict) and str(item.get("text", "")).strip():
            values.append(str(item["text"]))
    for item in spec.get("labels", []):
        if str(item.get("text", "")).strip():
            values.append(str(item["text"]))
    for item in spec.get("arrows", []):
        if str(item.get("text", "")).strip():
            values.append(str(item["text"]))
    for item in spec.get("legend", {}).get("items", []):
        if str(item.get("label", "")).strip():
            values.append(str(item["label"]))
    return values


def validate_spec(panel: dict) -> dict:
    spec = panel.get("annotation_spec")
    if not isinstance(spec, dict) or spec.get("mode") != "deterministic-overlay":
        raise ValueError("raster panel requires annotation_spec.mode=deterministic-overlay")
    planned = [str(value) for value in panel.get("visible_labels", []) if str(value).strip()]
    actual = text_entries(spec)
    if not planned or sorted(planned) != sorted(actual):
        raise ValueError("annotation text must exactly match the reviewed visible_labels allowlist")
    for key in ("title", "subtitle", "footer"):
        item = spec.get(key)
        if item:
            position(item.get("position"), f"annotation_spec.{key}.position")
            if item.get("text_anchor", "middle") not in {"start", "middle", "end"}:
                raise ValueError("annotation text_anchor must be start, middle, or end")
    for index, item in enumerate(spec.get("labels", []), start=1):
        position(item.get("position"), f"annotation_spec.labels[{index}].position")
        if item.get("anchor") is not None:
            position(item.get("anchor"), f"annotation_spec.labels[{index}].anchor")
        if item.get("style", "pill") not in {"pill", "plain", "section"}:
            raise ValueError("annotation label style must be pill, plain, or section")
        if item.get("text_anchor", "middle" if item.get("style", "pill") == "pill" else "start") not in {"start", "middle", "end"}:
            raise ValueError("annotation label text_anchor must be start, middle, or end")
    for index, item in enumerate(spec.get("arrows", []), start=1):
        position(item.get("from"), f"annotation_spec.arrows[{index}].from")
        position(item.get("to"), f"annotation_spec.arrows[{index}].to")
    legend = spec.get("legend", {})
    if legend:
        position(legend.get("position"), "annotation_spec.legend.position")
        for item in legend.get("items", []):
            if not COLOR.fullmatch(str(item.get("color", ""))):
                raise ValueError("legend colors must use #RRGGBB")
    return spec


def px(value: tuple[float, float], width: int, height: int) -> tuple[float, float]:
    return value[0] * width, value[1] * height


def svg_text(text: str) -> str:
    return html.escape(text, quote=True)


def render_text_item(item: dict, width: int, height: int, default_size: int, default_weight: int = 500) -> str:
    x, y = px(position(item["position"], "text.position"), width, height)
    size = int(item.get("font_size", default_size))
    weight = int(item.get("font_weight", default_weight))
    anchor = item.get("text_anchor", "middle")
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
        f'font-size="{size}" font-weight="{weight}">{svg_text(str(item["text"]))}</text>'
    )


def build_svg(background: Path, panel: dict, width: int, height: int) -> tuple[str, list[str]]:
    spec = validate_spec(panel)
    encoded = base64.b64encode(background.read_bytes()).decode("ascii")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs>',
        '<marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="#263238"/></marker>',
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="1" stdDeviation="2" flood-opacity="0.20"/></filter>',
        '</defs>',
        f'<image href="data:image/png;base64,{encoded}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="none"/>',
        '<g font-family="Arial, Helvetica, sans-serif" fill="#17212b">',
    ]
    if spec.get("title"):
        parts.append(render_text_item(spec["title"], width, height, 28, 650))
    if spec.get("subtitle"):
        parts.append(render_text_item(spec["subtitle"], width, height, 15, 500))
    for item in spec.get("labels", []):
        x, y = px(position(item["position"], "label.position"), width, height)
        size = int(item.get("font_size", 14))
        style = item.get("style", "pill")
        anchor = item.get("anchor")
        if anchor is not None:
            anchor_x, anchor_y = px(position(anchor, "label.anchor"), width, height)
            parts.append(f'<path d="M{x:.2f} {y + 7:.2f} L{anchor_x:.2f} {anchor_y:.2f}" stroke="#59636e" stroke-width="1.3" fill="none"/>')
        if style == "pill":
            box_width = max(62, len(str(item["text"])) * size * 0.57 + 18)
            parts.append(
                f'<g filter="url(#shadow)"><rect x="{x - box_width / 2:.2f}" y="{y - size - 6:.2f}" '
                f'width="{box_width:.2f}" height="{size + 13}" rx="7" fill="#ffffff" fill-opacity="0.94"/></g>'
            )
        text_anchor = item.get("text_anchor", "middle" if style == "pill" else "start")
        parts.append(
            f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{text_anchor}" font-size="{size}" '
            f'font-weight="{int(item.get("font_weight", 600 if style != "plain" else 500))}">{svg_text(str(item["text"]))}</text>'
        )
    for item in spec.get("arrows", []):
        start_x, start_y = px(position(item["from"], "arrow.from"), width, height)
        end_x, end_y = px(position(item["to"], "arrow.to"), width, height)
        parts.append(
            f'<path d="M{start_x:.2f} {start_y:.2f} L{end_x:.2f} {end_y:.2f}" '
            'stroke="#263238" stroke-width="1.8" fill="none" marker-end="url(#arrow)"/>'
        )
        if item.get("text"):
            parts.append(
                f'<text x="{(start_x + end_x) / 2:.2f}" y="{(start_y + end_y) / 2 - 10:.2f}" '
                f'text-anchor="middle" font-size="{int(item.get("font_size", 14))}">{svg_text(str(item["text"]))}</text>'
            )
    legend = spec.get("legend", {})
    if legend:
        x, y = px(position(legend["position"], "legend.position"), width, height)
        cursor = x
        for item in legend.get("items", []):
            parts.append(f'<circle cx="{cursor:.2f}" cy="{y:.2f}" r="8" fill="{item["color"]}" stroke="#56616b" stroke-width="0.6"/>')
            parts.append(f'<text x="{cursor + 15:.2f}" y="{y + 5:.2f}" font-size="13">{svg_text(str(item["label"]))}</text>')
            cursor += max(120, len(str(item["label"])) * 7 + 48)
    if spec.get("footer"):
        parts.append(render_text_item(spec["footer"], width, height, 13, 400))
    parts.extend(['</g>', '</svg>'])
    return "\n".join(parts), text_entries(spec)


def render_svg(svg: Path, png: Path, width: int, height: int) -> None:
    browser = browser_path()
    if not browser:
        raise RuntimeError("Edge or Chrome is required for deterministic raster annotations")
    with tempfile.TemporaryDirectory(prefix="figure-skill-raster-annotation-") as temp:
        temp_root = Path(temp)
        html_path = temp_root / "figure.html"
        profile = temp_root / "browser-profile"
        html_path.write_text(
            "<!doctype html><html><head><meta charset='utf-8'><style>"
            f"html,body{{margin:0;width:{width}px;height:{height}px;overflow:hidden;background:white}}"
            f"img{{display:block;width:{width}px;height:{height}px}}</style></head><body>"
            f"<img src='{svg.resolve().as_uri()}'></body></html>", encoding="utf-8"
        )
        result = subprocess.run([
            str(browser), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            f"--user-data-dir={profile}", f"--window-size={width},{height}", "--force-device-scale-factor=1",
            f"--screenshot={png.resolve()}", html_path.resolve().as_uri(),
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
        if result.returncode != 0 or not png.is_file():
            raise RuntimeError(f"raster annotation rendering failed: {result.stderr.strip()}")


def annotate(
    plan: dict, panel: dict, background: Path, output_dir: Path,
    generation_provenance_path: Path | None = None, source_dir: Path | None = None,
    annotation_provenance_path: Path | None = None,
) -> dict:
    canvas = panel.get("canvas", {})
    width, height = int(canvas.get("width", 0)), int(canvas.get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError("raster annotation canvas must contain positive width and height")
    source_width, source_height = png_dimensions(background)
    if abs((source_width / source_height) - (width / height)) > 0.01:
        raise ValueError("generated background aspect ratio differs from the approved canvas")
    output_dir.mkdir(parents=True, exist_ok=True)
    source_dir = source_dir or output_dir
    source_dir.mkdir(parents=True, exist_ok=True)
    original = source_dir / f"panel_{str(panel['id']).lower()}_unannotated.png"
    if background.resolve() != original.resolve():
        shutil.copy2(background, original)
    source_svg = source_dir / f"panel_{str(panel['id']).lower()}_annotation.svg"
    document, labels = build_svg(original, panel, width, height)
    source_svg.write_text(document, encoding="utf-8")
    rendered = source_dir / f"panel_{str(panel['id']).lower()}_annotated-preview.png"
    render_svg(source_svg, rendered, width, height)
    final_panel = output_dir / f"panel_{str(panel['id']).lower()}.png"
    shutil.copy2(rendered, final_panel)
    archived_source = source_dir / f"panel_{str(panel['id']).lower()}_annotation.svg.txt"
    source_svg.replace(archived_source)
    provenance = {
        "schema_version": "1.0",
        "panel": panel.get("id"),
        "mode": "deterministic-overlay",
        "background": str(original.resolve()),
        "background_sha256": sha256(original),
        "background_size": [source_width, source_height],
        "canvas": [width, height],
        "overlay_source": str(archived_source.resolve()),
        "overlay_source_sha256": sha256(archived_source),
        "output": str(final_panel.resolve()),
        "output_sha256": sha256(final_panel),
        "visible_labels": labels,
        "renderer": "Edge/Chrome SVG overlay rasterization",
        "resized_same_aspect": [source_width, source_height] != [width, height],
    }
    annotation_path = annotation_provenance_path or output_dir / "annotation-provenance.json"
    annotation_path.parent.mkdir(parents=True, exist_ok=True)
    annotation_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    if generation_provenance_path and generation_provenance_path.is_file():
        generation = json.loads(generation_provenance_path.read_text(encoding="utf-8"))
        generation["provider_output"] = str(original.resolve())
        generation["provider_output_sha256"] = sha256(original)
        generation["provider_output_size"] = [source_width, source_height]
        generation["annotation_provenance"] = str(annotation_path.resolve())
        generation["annotation_provenance_sha256"] = sha256(annotation_path)
        generation["output"] = str(final_panel.resolve())
        generation["output_sha256"] = sha256(final_panel)
        generation["width"] = width
        generation["height"] = height
        generation["requested_size"] = [width, height]
        generation["size_matches_request"] = True
        generation["status"] = "annotated-awaiting-scientific-and-human-review"
        generation_provenance_path.write_text(json.dumps(generation, ensure_ascii=False, indent=2), encoding="utf-8")
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generation-provenance", type=Path)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--annotation-provenance", type=Path)
    parser.add_argument("--panel")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    panel = select_panel(plan, args.panel)
    provenance = annotate(
        plan, panel, args.input.resolve(), args.output_dir.resolve(),
        args.generation_provenance.resolve() if args.generation_provenance else None,
        args.source_dir.resolve() if args.source_dir else None,
        args.annotation_provenance.resolve() if args.annotation_provenance else None,
    )
    print(f"Applied deterministic raster annotations -> {provenance['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
