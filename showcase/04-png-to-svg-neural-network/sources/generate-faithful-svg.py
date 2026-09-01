#!/usr/bin/env python3
"""Deterministically reconstruct the visible network topology from the reviewed PNG."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "input" / "neural-network.png"
OUTPUT = ROOT / "final-neural-network.svg"
PROVENANCE = ROOT / "vector-provenance.json"

WIDTH, HEIGHT = 900, 550
LAYERS = [
    {"id": "input", "label": "Input Layer", "x": 70, "count": 6, "color": "#fff1c7"},
    {"id": "hidden-6", "label": "6 neurons", "x": 205, "count": 6, "color": "#e6f0fa"},
    {"id": "hidden-100", "label": "100 neurons", "x": 350, "count": 8, "color": "#e6f0fa"},
    {"id": "hidden-500", "label": "500 neurons", "x": 495, "count": 9, "color": "#e6f0fa"},
    {"id": "hidden-200", "label": "200 neurons", "x": 640, "count": 8, "color": "#e6f0fa"},
    {"id": "hidden-50", "label": "50 neurons", "x": 785, "count": 6, "color": "#e6f0fa"},
]


def positions(count: int) -> list[float]:
    top, bottom = 70.0, 390.0
    if count == 1:
        return [(top + bottom) / 2]
    step = (bottom - top) / (count - 1)
    return [top + index * step for index in range(count)]


def build_svg() -> tuple[str, int, int]:
    coordinates = {layer["id"]: positions(layer["count"]) for layer in LAYERS}
    connection_count = 0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        '<title id="title">Neural network architecture</title>',
        '<desc id="desc">Six visible layers reconstructed from the supplied raster; adjacent visible layers are fully connected.</desc>',
        '<rect width="900" height="550" fill="#ffffff"/>',
        '<g id="connections" fill="none" stroke="#1f2933" stroke-width="0.85" stroke-opacity="0.48">',
    ]
    for left, right in zip(LAYERS, LAYERS[1:]):
        for left_y in coordinates[left["id"]]:
            for right_y in coordinates[right["id"]]:
                parts.append(
                    f'<line data-from="{left["id"]}" data-to="{right["id"]}" '
                    f'x1="{left["x"]}" y1="{left_y:.2f}" x2="{right["x"]}" y2="{right_y:.2f}"/>'
                )
                connection_count += 1
    parts.append('</g>')

    node_count = 0
    for layer in LAYERS:
        parts.append(f'<g id="{layer["id"]}" data-visible-count="{layer["count"]}">')
        for index, y in enumerate(coordinates[layer["id"]], start=1):
            parts.append(
                f'<circle id="{layer["id"]}-node-{index}" cx="{layer["x"]}" cy="{y:.2f}" r="16" '
                f'fill="{layer["color"]}" stroke="#9aa8b5" stroke-width="1.2"/>'
            )
            node_count += 1
        parts.append('</g>')

    parts.append('<g id="labels" font-family="Arial, Helvetica, sans-serif" font-size="18" fill="#111827" text-anchor="middle">')
    for layer in LAYERS:
        parts.append(f'<text x="{layer["x"]}" y="435">{layer["label"]}</text>')
    parts.extend([
        '</g>',
        '<path id="hidden-layers-bracket" d="M185 475 Q185 488 198 488 H792 Q805 488 805 475" fill="none" stroke="#374151" stroke-width="1.5"/>',
        '<text x="495" y="525" font-family="Arial, Helvetica, sans-serif" font-size="20" fill="#111827" text-anchor="middle">Hidden Layers</text>',
        '</svg>',
    ])
    return "\n".join(parts), node_count, connection_count


def main() -> None:
    svg, node_count, connection_count = build_svg()
    OUTPUT.write_text(svg, encoding="utf-8")
    PROVENANCE.write_text(json.dumps({
        "schema_version": "1.0",
        "source": str(SOURCE),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "output": str(OUTPUT),
        "reconstruction_scope": "visible content only",
        "source_limitations": [
            "left-side input annotations are cropped",
            "right-side content beyond the 50-neuron layer is cropped",
            "no cropped output layer or class labels were inferred",
        ],
        "visible_layer_counts": {layer["label"]: layer["count"] for layer in LAYERS},
        "node_count": node_count,
        "connection_count": connection_count,
        "embedded_raster_images": 0,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT} with {node_count} nodes and {connection_count} connections")


if __name__ == "__main__":
    main()
