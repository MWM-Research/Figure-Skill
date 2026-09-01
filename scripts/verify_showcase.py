#!/usr/bin/env python3
"""Rebuild and regression-check Figure Skill showcase cases without network access."""

from __future__ import annotations

import argparse, json, math, os, shutil, subprocess, sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageOps, ImageDraw
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / "showcase"
DEFAULT_WORK = ROOT / "tmp" / "showcase-regression"
SECRET_ENV = {"OPENAI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "AUTOFIGURE_API_KEY", "FAL_KEY", "ROBOFLOW_API_KEY", "FIGURE_IMAGE_API_KEY"}


def local_name(tag: str) -> str: return tag.rsplit("}", 1)[-1]


def dhash(image: Image.Image, size: int = 8) -> int:
    data = np.asarray(ImageOps.grayscale(image).resize((size + 1, size), Image.Resampling.LANCZOS), dtype=np.int16)
    bits = data[:, 1:] > data[:, :-1]; value = 0
    for bit in bits.flat: value = (value << 1) | int(bit)
    return value


def visual_metrics(baseline: Path, generated: Path, diff_path: Path) -> dict:
    with Image.open(baseline) as left_image, Image.open(generated) as right_image:
        left, right = left_image.convert("RGB"), right_image.convert("RGB")
        if left.size != right.size: return {"status": "fail", "reason": "size-mismatch", "baseline_size": list(left.size), "generated_size": list(right.size)}
        left_array, right_array = np.asarray(left, dtype=np.float32), np.asarray(right, dtype=np.float32)
        delta = np.abs(left_array - right_array)
        thumb_left = np.asarray(left.resize((256, 256), Image.Resampling.LANCZOS), dtype=np.float32) / 255.0
        thumb_right = np.asarray(right.resize((256, 256), Image.Resampling.LANCZOS), dtype=np.float32) / 255.0
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        ImageChops.difference(left, right).save(diff_path)
        return {"status": "pass", "dhash_distance": (dhash(left) ^ dhash(right)).bit_count(), "thumbnail_rmse": float(np.sqrt(np.mean((thumb_left - thumb_right) ** 2))), "changed_pixel_ratio": float(np.mean(np.max(delta, axis=2) > 16)), "mean_absolute_error": float(delta.mean() / 255.0), "size": list(left.size)}


def compare_thresholds(metrics: dict, thresholds: dict) -> tuple[bool, list[str]]:
    failures = []
    for metric, threshold_key in (("dhash_distance", "max_dhash_distance"), ("thumbnail_rmse", "max_thumbnail_rmse"), ("changed_pixel_ratio", "max_changed_pixel_ratio")):
        if float(metrics.get(metric, math.inf)) > float(thresholds[threshold_key]): failures.append(f"{metric}={metrics.get(metric)} > {thresholds[threshold_key]}")
    return not failures, failures


def safe_environment() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key not in SECRET_ENV}
    environment.update({"NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost", "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9", "PYTHONDONTWRITEBYTECODE": "1", "FIGURE_SHOWCASE_OFFLINE": "1"})
    return environment


def substitute(command: list[str], case_root: Path, output_root: Path) -> list[str]:
    values = {"python": sys.executable, "repo": str(ROOT), "case": str(case_root), "output": str(output_root)}
    return [str(item).format(**values) for item in command]


def structural_checks(case_root: Path, output_root: Path, manifest: dict) -> list[dict]:
    checks = []
    for relative in manifest.get("expected_artifacts", []):
        path = output_root / relative; checks.append({"check": f"artifact:{relative}", "status": "pass" if path.is_file() and path.stat().st_size else "fail"})
    assertions = manifest.get("structural_assertions", {})
    svg_relative = assertions.get("svg")
    if svg_relative:
        path = output_root / svg_relative
        try:
            root = ET.parse(path).getroot(); tags = {}
            for element in root.iter(): tags[local_name(element.tag)] = tags.get(local_name(element.tag), 0) + 1
            for tag, minimum in assertions.get("min_tags", {}).items(): checks.append({"check": f"svg-tag:{tag}", "status": "pass" if tags.get(tag, 0) >= int(minimum) else "fail", "actual": tags.get(tag, 0), "minimum": minimum})
            if assertions.get("forbid_embedded_images"): checks.append({"check": "svg-no-image", "status": "pass" if tags.get("image", 0) == 0 else "fail", "actual": tags.get("image", 0)})
            visible = " ".join(text.strip() for text in root.itertext() if text.strip())
            for label in assertions.get("required_text", []): checks.append({"check": f"svg-text:{label}", "status": "pass" if label in visible else "fail"})
        except (OSError, ET.ParseError) as exc: checks.append({"check": "svg-readable", "status": "fail", "detail": str(exc)})
    png_relative = assertions.get("png")
    if png_relative and assertions.get("canvas"):
        try:
            with Image.open(output_root / png_relative) as image: size = list(image.size)
            checks.append({"check": "png-canvas", "status": "pass" if size == assertions["canvas"] else "fail", "actual": size})
        except OSError as exc: checks.append({"check": "png-readable", "status": "fail", "detail": str(exc)})
    pdf_relative = assertions.get("pdf")
    if pdf_relative:
        try: pages = len(PdfReader(output_root / pdf_relative).pages); checks.append({"check": "pdf-pages", "status": "pass" if pages == int(assertions.get("pdf_pages", 1)) else "fail", "actual": pages})
        except Exception as exc: checks.append({"check": "pdf-readable", "status": "fail", "detail": str(exc)})
    for item in assertions.get("json_status", []):
        try:
            data = json.loads((output_root / item["path"]).read_text(encoding="utf-8")); value = data
            for key in item["key"].split("."): value = value[key]
            checks.append({"check": f"json-status:{item['path']}", "status": "pass" if value == item["equals"] else "fail", "actual": value})
        except Exception as exc: checks.append({"check": f"json-status:{item['path']}", "status": "fail", "detail": str(exc)})
    return checks


def make_contact_sheet(images: list[tuple[str, Path]], output: Path) -> None:
    cards = []
    for title, path in images:
        with Image.open(path) as image: thumb = image.convert("RGB"); thumb.thumbnail((420, 260))
        card = Image.new("RGB", (440, 310), "white"); card.paste(thumb, ((440 - thumb.width) // 2, 36)); ImageDraw.Draw(card).text((12, 10), title, fill="black"); cards.append(card)
    sheet = Image.new("RGB", (880, math.ceil(len(cards) / 2) * 310), "white")
    for index, card in enumerate(cards): sheet.paste(card, ((index % 2) * 440, (index // 2) * 310))
    output.parent.mkdir(parents=True, exist_ok=True); sheet.save(output)


def run_case(case_root: Path, work_root: Path, accept: bool) -> dict:
    manifest = json.loads((case_root / "showcase-case.json").read_text(encoding="utf-8")); case_id = manifest["id"]; output_root = work_root / case_id
    if output_root.exists(): shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    command = manifest.get("rebuild_command") or []
    if command:
        completed = subprocess.run(substitute(command, case_root, output_root), cwd=case_root, env=safe_environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=int(manifest.get("timeout_seconds", 180)))
        execution = {"status": "pass" if completed.returncode == 0 else "fail", "returncode": completed.returncode, "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:]}
    else:
        for relative in manifest.get("expected_artifacts", []):
            source, target = case_root / relative, output_root / relative; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
        execution = {"status": "pass", "mode": "frozen-copy"}
    checks = structural_checks(case_root, output_root, manifest) if execution["status"] == "pass" else []
    visual = {}; visual_config = manifest.get("visual_regression")
    if visual_config and execution["status"] == "pass":
        baseline, generated = case_root / visual_config["baseline"], output_root / visual_config["generated"]
        if accept:
            if os.environ.get("CI"): raise RuntimeError("--accept is forbidden in CI")
            baseline.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(generated, baseline)
        visual = visual_metrics(baseline, generated, work_root / "diffs" / f"{case_id}.png")
        passed, failures = compare_thresholds(visual, manifest["visual_thresholds"]); visual["status"] = "pass" if passed else "fail"; visual["failures"] = failures
    status = "pass" if execution["status"] == "pass" and all(item["status"] == "pass" for item in checks) and (not visual or visual["status"] == "pass") else "fail"
    return {"id": case_id, "status": status, "execution": execution, "checks": checks, "visual": visual, "generated_preview": str(output_root / visual_config["generated"]) if visual_config else None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--showcase-root", type=Path, default=SHOWCASE); parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK); parser.add_argument("--case", action="append"); parser.add_argument("--accept", action="store_true"); parser.add_argument("--output", type=Path); args = parser.parse_args()
    showcase_root, work_root = args.showcase_root.resolve(), args.work_root.resolve(); work_root.mkdir(parents=True, exist_ok=True)
    selected = set(args.case or []); cases = [path.parent for path in sorted(showcase_root.glob("*/showcase-case.json")) if not selected or path.parent.name in selected or json.loads(path.read_text(encoding="utf-8"))["id"] in selected]
    if not cases: raise SystemExit("no showcase manifests found")
    results = [run_case(case, work_root, args.accept) for case in cases]
    previews = [(item["id"], Path(item["generated_preview"])) for item in results if item.get("generated_preview") and Path(item["generated_preview"]).is_file()]
    contact_sheet = work_root / "showcase-contact-sheet.png"
    if previews: make_contact_sheet(previews, contact_sheet)
    report = {"schema_version": "1.0", "status": "pass" if all(item["status"] == "pass" for item in results) else "fail", "offline": True, "cases": results, "contact_sheet": str(contact_sheet) if contact_sheet.is_file() else None}
    output = (args.output or work_root / "showcase-regression.json").resolve(); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"); print(f"Showcase regression: {report['status']} -> {output}"); return 0 if report["status"] == "pass" else 1


if __name__ == "__main__": raise SystemExit(main())
