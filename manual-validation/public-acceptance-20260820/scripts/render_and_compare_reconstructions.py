#!/usr/bin/env python3
"""Render public reconstruction SVGs and record reproducible comparison metrics."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SKILL = PROJECT / "plugins" / "figure-skill" / "skills" / "figure-skill"
ASSEMBLER = load_module("public_acceptance_assembler", SKILL / "scripts" / "assemble_figure.py")
NO_SAM = load_module(
    "public_acceptance_no_sam",
    SKILL / "scripts" / "adapters" / "autofigure_no_sam_runner.py",
)


CASES = (
    {
        "name": "artificial-neuron",
        "source": ROOT / "sources" / "raw" / "artificial-neuron-scheme.png",
        "output": ROOT / "outputs" / "reconstruction-artificial-neuron-retry-gemini",
    },
    {
        "name": "neural-network-ground-truth",
        "source": ROOT / "sources" / "raw" / "neural-network-ground-truth.png",
        "output": ROOT / "outputs" / "reconstruction-neural-network-ground-truth-retry-gemini",
    },
)


def rgb_array(path: Path, size: tuple[int, int] | None = None) -> np.ndarray:
    with Image.open(path) as image:
        converted = image.convert("RGB")
        if size and converted.size != size:
            converted = converted.resize(size, Image.Resampling.LANCZOS)
        return np.asarray(converted, dtype=np.float32)


def compare(source: Path, preview: Path) -> dict:
    with Image.open(source) as image:
        size = image.size
    left = rgb_array(source)
    right = rgb_array(preview, size)
    similarity = 1.0 - float(np.mean(np.abs(left - right)) / 255.0)
    left_fg = np.min(left, axis=2) < 245
    right_fg = np.min(right, axis=2) < 245
    union = np.logical_or(left_fg, right_fg).sum()
    intersection = np.logical_and(left_fg, right_fg).sum()
    return {
        "pixel_similarity": round(similarity, 6),
        "foreground_iou": round(float(intersection / union), 6) if union else 1.0,
        "reference_size": {"width": size[0], "height": size[1]},
    }


def main() -> int:
    failures = []
    for case in CASES:
        output = case["output"]
        svg = output / "final.svg"
        preview = output / "final-preview.png"
        root = ASSEMBLER.ET.parse(svg).getroot()
        width, height, _ = ASSEMBLER.svg_geometry(root)
        ASSEMBLER.export_with_browser(
            svg, int(round(width)), int(round(height)), png=preview, pdf=None
        )
        validation = NO_SAM.validate_pure_svg(svg)
        raw = svg.read_text(encoding="utf-8", errors="replace")
        report = {
            "schema_version": "1.0",
            "case": case["name"],
            "status": "pass" if validation["valid"] and not re.search(r"sk-[A-Za-z0-9]", raw) else "fail",
            "pure_svg_validation": validation,
            "contains_secret": bool(re.search(r"sk-[A-Za-z0-9]", raw)),
            "comparison": compare(case["source"], preview),
            "source": str(case["source"]),
            "svg": str(svg),
            "preview": str(preview),
        }
        (output / "verification-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if report["status"] != "pass":
            failures.append(case["name"])
        print(json.dumps(report, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
