#!/usr/bin/env python3
"""Run AutoFigure's explicit no-icon SVG fallback without a SAM service."""

from __future__ import annotations

import argparse
import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def load_upstream(path: Path):
    spec = importlib.util.spec_from_file_location("autofigure_no_sam_upstream", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load AutoFigure entrypoint: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def segment_without_sam(image_path: str, output_dir: str, text_prompts: str = "", **_: object):
    from PIL import Image

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    source = Path(image_path)
    samed = output / "samed.png"
    with Image.open(source) as image:
        image.convert("RGB").save(samed, format="PNG")
        width, height = image.size
    boxlib = output / "boxlib.json"
    boxlib.write_text(json.dumps({
        "image_size": {"width": width, "height": height},
        "prompts_used": [],
        "boxes": [],
        "no_icon_mode": True,
        "segmentation_backend": "none",
        "fidelity_note": "No icon segmentation was performed; output uses AutoFigure's pure SVG fallback.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(samed), str(boxlib), []


def validate_pure_svg(path: Path) -> dict:
    if not path.is_file():
        return {"valid": False, "reason": "final SVG is missing", "embedded_images": None, "vector_shapes": 0}
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return {"valid": False, "reason": f"invalid SVG XML: {exc}", "embedded_images": None, "vector_shapes": 0}
    images = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "image"]
    shapes = [
        node for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] in {"rect", "circle", "ellipse", "path", "line", "polyline", "polygon"}
    ]
    if images:
        return {
            "valid": False,
            "reason": "output embeds raster image data instead of reconstructing pure SVG",
            "embedded_images": len(images),
            "vector_shapes": len(shapes),
        }
    if not shapes:
        return {"valid": False, "reason": "output contains no vector shape elements", "embedded_images": 0, "vector_shapes": 0}
    return {"valid": True, "reason": None, "embedded_images": 0, "vector_shapes": len(shapes)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--method_file", type=Path)
    input_group.add_argument("--input_figure_path", type=Path)
    parser.add_argument("--upstream-entry", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--provider", default="custom")
    parser.add_argument("--api_key", required=True)
    parser.add_argument("--base_url")
    parser.add_argument("--svg_model")
    parser.add_argument("--optimize_iterations", type=int, default=0)
    args = parser.parse_args()

    upstream = load_upstream(args.upstream_entry.resolve())
    upstream.segment_with_sam3 = segment_without_sam
    method_text = args.method_file.read_text(encoding="utf-8-sig") if args.method_file else None
    result = upstream.method_to_svg(
        method_text=method_text,
        output_dir=str(args.output_dir.resolve()),
        api_key=args.api_key,
        base_url=args.base_url,
        provider=args.provider,
        svg_gen_model=args.svg_model,
        sam_backend="local",
        optimize_iterations=args.optimize_iterations,
        enable_upscale=False,
        input_figure_path=str(args.input_figure_path.resolve()) if args.input_figure_path else None,
    )
    final_svg = Path(str(result.get("final_svg_path") or args.output_dir.resolve() / "final.svg"))
    validation = validate_pure_svg(final_svg)
    result_path = args.output_dir.resolve() / "no-sam-result.json"
    result_path.write_text(json.dumps({
        "schema_version": "1.0",
        "status": "pass" if validation["valid"] else "fail",
        "segmentation_backend": "none",
        "segmentation_performed": False,
        "fidelity": "pure-svg-fallback",
        "pure_svg_validation": validation,
        "upstream_result": result,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    if not validation["valid"]:
        raise SystemExit(f"No-SAM reconstruction failed validation: {validation['reason']}")
    print(f"No-SAM AutoFigure run complete -> {result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
