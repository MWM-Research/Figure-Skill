#!/usr/bin/env python3
"""Assemble editable SVG panels and export a final SVG/PDF/PNG figure."""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def qname(name: str) -> str:
    return f"{{{SVG_NS}}}{name}"


def numeric_dimension(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"\s*([0-9.]+)", value)
    return float(match.group(1)) if match else None


def svg_geometry(root: ET.Element) -> tuple[float, float, str]:
    viewbox = root.get("viewBox")
    if viewbox:
        values = [float(value) for value in viewbox.replace(",", " ").split()]
        if len(values) == 4 and values[2] > 0 and values[3] > 0:
            return values[2], values[3], " ".join(f"{value:g}" for value in values)
    width = numeric_dimension(root.get("width"))
    height = numeric_dimension(root.get("height"))
    if width and height:
        return width, height, f"0 0 {width:g} {height:g}"
    raise ValueError("panel SVG lacks a valid viewBox or width/height")


def prefix_ids(root: ET.Element, prefix: str) -> None:
    mapping = {}
    for element in root.iter():
        identifier = element.get("id")
        if identifier:
            mapping[identifier] = f"{prefix}-{identifier}"
            element.set("id", mapping[identifier])
    for element in root.iter():
        for key, value in list(element.attrib.items()):
            for old, new in mapping.items():
                value = value.replace(f"url(#{old})", f"url(#{new})")
                if value == f"#{old}":
                    value = f"#{new}"
            element.set(key, value)


def panel_paths(plan: dict, panels_dir: Path) -> list[tuple[str, Path]]:
    result = []
    for panel in plan.get("panels", []):
        panel_id = str(panel.get("id", "")).strip()
        if not panel_id:
            continue
        path = panels_dir / f"panel_{panel_id.lower()}.svg"
        if not path.is_file():
            raise FileNotFoundError(f"missing SVG for panel {panel_id}: {path}")
        result.append((panel_id, path))
    if not result:
        raise ValueError("the plan contains no panels")
    return result


def assemble(plan: dict, panels_dir: Path, output_svg: Path, layout: str = "auto") -> dict:
    sources = panel_paths(plan, panels_dir)
    count = len(sources)
    if layout == "auto":
        layout = "single" if count == 1 else ("horizontal" if count == 2 else "grid")
    if layout == "single":
        columns = 1
    elif layout == "horizontal":
        columns = count
    elif layout == "vertical":
        columns = 1
    elif layout == "grid":
        columns = 2
    else:
        raise ValueError(f"unsupported layout: {layout}")
    rows = math.ceil(count / columns)
    cell_width, cell_height, gap, margin = 720, 440, 28, 24
    width = margin * 2 + columns * cell_width + (columns - 1) * gap
    height = margin * 2 + rows * cell_height + (rows - 1) * gap
    outer = ET.Element(qname("svg"), {
        "width": str(width), "height": str(height), "viewBox": f"0 0 {width} {height}",
        "role": "img", "aria-label": str(plan.get("brief") or "Scientific figure"),
    })
    ET.SubElement(outer, qname("rect"), {"width": "100%", "height": "100%", "fill": "white"})

    manifest_panels = []
    for index, (panel_id, path) in enumerate(sources):
        parsed = ET.parse(path).getroot()
        source_width, source_height, viewbox = svg_geometry(parsed)
        prefix_ids(parsed, f"panel-{panel_id.lower()}")
        row, column = divmod(index, columns)
        x = margin + column * (cell_width + gap)
        y = margin + row * (cell_height + gap)
        nested = ET.SubElement(outer, qname("svg"), {
            "x": str(x), "y": str(y), "width": str(cell_width), "height": str(cell_height),
            "viewBox": viewbox, "preserveAspectRatio": "xMidYMid meet", "data-panel": panel_id,
        })
        for child in list(parsed):
            nested.append(copy.deepcopy(child))
        manifest_panels.append({
            "id": panel_id,
            "source": str(path.resolve()),
            "source_width": source_width,
            "source_height": source_height,
            "cell": {"x": x, "y": y, "width": cell_width, "height": cell_height},
        })

    output_svg.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(outer).write(output_svg, encoding="utf-8", xml_declaration=True)
    return {
        "schema_version": "1.0",
        "layout": layout,
        "width": width,
        "height": height,
        "svg": output_svg.name,
        "panels": manifest_panels,
    }


def find_browser() -> Path | None:
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


def export_with_browser(svg: Path, width: int, height: int, *, png: Path | None, pdf: Path | None) -> None:
    browser = find_browser()
    if browser is None:
        raise RuntimeError("Edge/Chrome is required for PNG/PDF export; SVG assembly is still available")
    with tempfile.TemporaryDirectory(prefix="scientific-figure-export-") as temp:
        temp_root = Path(temp)
        html = temp_root / "figure.html"
        profile = temp_root / "browser-profile"
        html.write_text(
            "<!doctype html><html><head><meta charset='utf-8'><style>"
            f"@page{{size:{width}px {height}px;margin:0}}"
            f"html,body{{margin:0;width:{width}px;height:{height}px;overflow:hidden;background:white}}"
            f"img{{display:block;width:{width}px;height:{height}px}}"
            "</style></head><body>"
            f"<img src='{svg.resolve().as_uri()}'></body></html>",
            encoding="utf-8",
        )
        common = [
            str(browser), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            f"--user-data-dir={profile}", f"--window-size={width},{height}", "--force-device-scale-factor=1",
        ]
        if png:
            result = subprocess.run(
                common + [f"--screenshot={png.resolve()}", html.resolve().as_uri()],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60,
            )
            if result.returncode != 0 or not png.is_file():
                raise RuntimeError(f"browser PNG export failed: {result.stderr.strip()}")
        if pdf:
            result = subprocess.run(
                common + ["--print-to-pdf-no-header", f"--print-to-pdf={pdf.resolve()}", html.resolve().as_uri()],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60,
            )
            if result.returncode != 0 or not pdf.is_file():
                raise RuntimeError(f"browser PDF export failed: {result.stderr.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--panels-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--layout", choices=("auto", "single", "horizontal", "vertical", "grid"), default="auto")
    parser.add_argument("--formats", default="svg,pdf,png")
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    formats = {item.strip().lower() for item in args.formats.split(",") if item.strip()}
    unsupported = formats - {"svg", "pdf", "png"}
    if unsupported:
        parser.error(f"unsupported formats: {', '.join(sorted(unsupported))}")
    output_svg = output_dir / "figure.svg"
    manifest = assemble(plan, args.panels_dir.resolve(), output_svg, args.layout)
    export_with_browser(
        output_svg, manifest["width"], manifest["height"],
        png=output_dir / "figure.png" if "png" in formats else None,
        pdf=output_dir / "figure.pdf" if "pdf" in formats else None,
    ) if formats & {"png", "pdf"} else None
    (output_dir / "assembly-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Assembled {len(manifest['panels'])} panel(s) -> {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
