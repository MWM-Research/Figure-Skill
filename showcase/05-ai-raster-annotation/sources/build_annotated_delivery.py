#!/usr/bin/env python3
"""Overlay exact paper labels on the generated raster and rebuild the 1024x768 PNG delivery."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


WIDTH, HEIGHT = 1024, 768
LABELS = [
    "Temporal Multi-Head Attention",
    "Attention Head Channels (8)",
    "Video Frame Sequence (20)",
    "Frame 6", "Frame 12", "Frame 17",
    "Temporal Direction", "Low response", "High response",
    "Conceptual illustration — not quantitative attention values",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def browser_path() -> Path:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ]
    found = next((path for path in candidates if path.is_file()), None)
    if not found:
        raise RuntimeError("Edge or Chrome is required to render the annotation overlay")
    return found


def svg_document(background: Path) -> str:
    encoded = base64.b64encode(background.read_bytes()).decode("ascii")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="768" viewBox="0 0 1024 768">
  <defs>
    <marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="#263238"/></marker>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="1" stdDeviation="2" flood-opacity="0.20"/></filter>
  </defs>
  <image href="data:image/png;base64,{encoded}" x="0" y="0" width="1024" height="768"/>
  <g font-family="Arial, Helvetica, sans-serif" fill="#17212b">
    <text x="512" y="38" text-anchor="middle" font-size="27" font-weight="650">Temporal Multi-Head Attention</text>
    <g filter="url(#shadow)"><rect x="47" y="57" width="223" height="31" rx="8" fill="#ffffff" fill-opacity="0.92"/></g>
    <text x="59" y="78" font-size="16" font-weight="600">Attention Head Channels (8)</text>

    <g font-size="14" font-weight="600" text-anchor="middle">
      <g filter="url(#shadow)"><rect x="268" y="270" width="70" height="27" rx="7" fill="#ffffff" fill-opacity="0.94"/></g>
      <text x="303" y="289">Frame 6</text><path d="M303 297 L303 338" stroke="#59636e" stroke-width="1.4"/>
      <g filter="url(#shadow)"><rect x="544" y="270" width="72" height="27" rx="7" fill="#ffffff" fill-opacity="0.94"/></g>
      <text x="580" y="289">Frame 12</text><path d="M580 297 L580 318" stroke="#59636e" stroke-width="1.4"/>
      <g filter="url(#shadow)"><rect x="775" y="270" width="72" height="27" rx="7" fill="#ffffff" fill-opacity="0.94"/></g>
      <text x="811" y="289">Frame 17</text><path d="M811 297 L811 311" stroke="#59636e" stroke-width="1.4"/>
    </g>

    <text x="55" y="657" font-size="16" font-weight="600">Video Frame Sequence (20)</text>
    <path d="M330 653 L680 653" stroke="#263238" stroke-width="1.8" marker-end="url(#arrow)"/>
    <text x="505" y="642" text-anchor="middle" font-size="14">Temporal Direction</text>

    <g font-size="13">
      <circle cx="755" cy="653" r="8" fill="#4d3ba8"/><text x="770" y="658">Low response</text>
      <circle cx="889" cy="653" r="8" fill="#e8ef3d" stroke="#93a629"/><text x="904" y="658">High response</text>
    </g>
    <text x="512" y="735" text-anchor="middle" font-size="13" fill="#59636e">Conceptual illustration — not quantitative attention values</text>
  </g>
</svg>'''


def render(svg: Path, png: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="figure-skill-annotation-") as temp:
        temp_root = Path(temp)
        html = temp_root / "figure.html"
        profile = temp_root / "browser-profile"
        html.write_text(
            "<!doctype html><html><head><meta charset='utf-8'><style>"
            "html,body{margin:0;width:1024px;height:768px;overflow:hidden;background:white}"
            "img{display:block;width:1024px;height:768px}</style></head><body>"
            f"<img src='{svg.resolve().as_uri()}'></body></html>", encoding="utf-8"
        )
        result = subprocess.run([
            str(browser_path()), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            f"--user-data-dir={profile}", "--window-size=1024,768", "--force-device-scale-factor=1",
            f"--screenshot={png.resolve()}", html.resolve().as_uri(),
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
        if result.returncode != 0 or not png.is_file():
            raise RuntimeError(f"annotation render failed: {result.stderr.strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    root = args.output_root.resolve()
    final = root / "final" / "figure.png"
    unlabeled = root / "final" / "figure-unlabeled.png"
    if not unlabeled.is_file():
        shutil.copy2(final, unlabeled)
    overlay = root / "sources" / "annotation-overlay.svg"
    overlay.write_text(svg_document(unlabeled), encoding="utf-8")
    rendered = root / "final" / "figure-annotated.png"
    render(overlay, rendered)
    archived_overlay = root / "sources" / "annotation-overlay.svg.txt"
    overlay.replace(archived_overlay)
    shutil.copy2(rendered, final)
    panel = root / "panels" / "panel_a.png"
    shutil.copy2(rendered, panel)

    provenance_path = root / "provenance" / "generation-provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["unlabeled_background"] = str(unlabeled.resolve())
    provenance["unlabeled_background_sha256"] = sha256(unlabeled)
    provenance["annotation_overlay"] = str(archived_overlay.resolve())
    provenance["annotation_overlay_sha256"] = sha256(archived_overlay)
    provenance["approved_visible_labels"] = LABELS
    provenance["output"] = str(panel.resolve())
    provenance["output_sha256"] = sha256(panel)
    provenance["postprocess"] = (
        "aspect-preserving LANCZOS downscale followed by deterministic SVG annotation overlay; no crop"
    )
    provenance["status"] = "annotated-awaiting-scientific-and-human-review"
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")

    annotation_provenance = {
        "schema_version": "1.0",
        "background": str(unlabeled.resolve()),
        "background_sha256": sha256(unlabeled),
        "overlay": str(archived_overlay.resolve()),
        "overlay_sha256": sha256(archived_overlay),
        "output": str(final.resolve()),
        "output_sha256": sha256(final),
        "labels": LABELS,
        "renderer": "Edge/Chrome deterministic SVG overlay rasterization",
        "canvas": [WIDTH, HEIGHT],
    }
    (root / "provenance" / "annotation-provenance.json").write_text(
        json.dumps(annotation_provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Built annotated 1024x768 delivery -> {final}")


if __name__ == "__main__":
    main()
