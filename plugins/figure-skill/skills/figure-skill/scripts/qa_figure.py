#!/usr/bin/env python3
"""Run structural, provenance, and deliverable QA on scientific figures."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from review_generated_figure import validate_review  # noqa: E402


EDITABLE = {".svg", ".drawio", ".py", ".r", ".ipynb", ".ai", ".eps"}
PLACEHOLDER = re.compile(r"\b(?:todo|tbd|placeholder|lorem ipsum)\b", re.IGNORECASE)


def check(name: str, status: str, **details: Any) -> dict:
    return {"check": name, "status": status, **details}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_svg(path: Path) -> list[dict]:
    checks = []
    try:
        root = ET.parse(path).getroot()
        checks.append(check("svg-xml-valid", "pass", file=str(path)))
        has_size = bool(root.get("viewBox") or (root.get("width") and root.get("height")))
        checks.append(check("svg-has-canvas-size", "pass" if has_size else "fail", file=str(path)))
        text = " ".join(root.itertext())
        checks.append(check("svg-no-placeholders", "fail" if PLACEHOLDER.search(text) else "pass", file=str(path)))
        images = [element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "image"]
        checks.append(check(
            "svg-not-raster-only",
            "warn" if images else "pass",
            file=str(path),
            detail=f"contains {len(images)} embedded image element(s)" if images else "no embedded raster images",
        ))
    except (ET.ParseError, OSError) as exc:
        checks.append(check("svg-xml-valid", "fail", file=str(path), detail=str(exc)))
    return checks


def inspect_pdf(path: Path) -> list[dict]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return [check("pdf-readable", "fail", file=str(path), detail=str(exc))]
    valid = len(data) > 100 and data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:]
    return [check("pdf-readable", "pass" if valid else "fail", file=str(path), size_bytes=len(data))]


def inspect_png(path: Path) -> list[dict]:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
        valid = len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", header[16:24]) if valid else (0, 0)
        status = "pass" if valid and width >= 300 and height >= 200 else ("warn" if valid else "fail")
        return [check("png-valid-size", status, file=str(path), width=width, height=height)]
    except OSError as exc:
        return [check("png-valid-size", "fail", file=str(path), detail=str(exc))]


def png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
        if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return struct.unpack(">II", header[16:24])
    except OSError:
        return None


def equal_value(raw: Any, expected: Any) -> bool:
    try:
        return math.isclose(float(str(raw).replace(",", "")), float(expected), rel_tol=1e-9, abs_tol=1e-12)
    except (TypeError, ValueError):
        return str(raw) == str(expected)


def source_rows(path: Path) -> dict[int, dict[str, Any]]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            return {index: row for index, row in enumerate(csv.DictReader(handle, delimiter=delimiter), start=2)}
    if suffix == ".jsonl":
        result = {}
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for index, line in enumerate(handle, start=1):
                if line.strip():
                    value = json.loads(line)
                    if isinstance(value, dict):
                        result[index] = value
        return result
    if suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(value, dict):
            value = next((value[key] for key in ("records", "data", "results", "metrics", "items") if isinstance(value.get(key), list)), [value])
        return {index: item for index, item in enumerate(value, start=1) if isinstance(item, dict)} if isinstance(value, list) else {}
    if suffix == ".xlsx":
        from openpyxl import load_workbook  # type: ignore
        workbook = load_workbook(path, read_only=True, data_only=True)
        sheet = workbook[workbook.sheetnames[0]]
        iterator = sheet.iter_rows(values_only=True)
        headers = [str(value) if value is not None else f"column_{index + 1}" for index, value in enumerate(next(iterator, []))]
        try:
            return {index: dict(zip(headers, values)) for index, values in enumerate(iterator, start=2)}
        finally:
            workbook.close()
    raise ValueError(f"unsupported provenance source format: {suffix}")


def verify_data_provenance(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [check("provenance-readable", "fail", file=str(path), detail=str(exc))]
    checks = [check("provenance-readable", "pass", file=str(path))]
    for panel in data.get("panels", []):
        panel_id = panel.get("panel")
        source = Path(str(panel.get("source_file", "")))
        if not source.is_file():
            checks.append(check("provenance-source-exists", "fail", panel=panel_id, source=str(source)))
            continue
        expected_hash = panel.get("source_sha256")
        hash_status = "pass" if expected_hash and sha256(source) == expected_hash else "fail"
        checks.append(check("provenance-source-hash", hash_status, panel=panel_id, source=str(source)))
        try:
            rows = source_rows(source)
            mismatches = []
            for mark in panel.get("marks", []):
                row_number = int(mark.get("source_row"))
                row = rows.get(row_number)
                if row is None:
                    mismatches.append(f"missing source row {row_number}")
                    continue
                for axis in ("x", "y", "group"):
                    value = mark.get(axis, {})
                    if not value:
                        continue
                    column = value.get("column")
                    if column not in row or not equal_value(row.get(column), value.get("value")):
                        mismatches.append(f"row {row_number} column {column}")
            checks.append(check(
                "provenance-mark-values", "fail" if mismatches else "pass", panel=panel_id,
                detail=", ".join(mismatches) if mismatches else f"verified {len(panel.get('marks', []))} marks",
            ))
        except (OSError, csv.Error, ValueError, TypeError) as exc:
            checks.append(check("provenance-mark-values", "fail", panel=panel_id, detail=str(exc)))
    return checks


def verify_edit_provenance(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        source = Path(str(data.get("source_file", "")))
        valid_source = source.is_file() and data.get("source_sha256") == sha256(source)
        operations = data.get("operations", [])
        applied = bool(operations) and all(item.get("status") == "applied" for item in operations)
        return [
            check("edit-provenance-readable", "pass", file=str(path)),
            check("edit-source-hash", "pass" if valid_source else "fail", source=str(source)),
            check("edit-operations-applied", "pass" if applied else "fail", count=len(operations)),
        ]
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        return [check("edit-provenance-readable", "fail", file=str(path), detail=str(exc))]


def verify_generation_provenance(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        output = Path(str(data.get("output", "")))
        valid_output = output.is_file() and data.get("output_sha256") == sha256(output)
        labeled = data.get("generated_content") is True and data.get("evidence_role") == "illustrative"
        review_required = data.get("human_review_required") is True
        return [
            check("generation-provenance-readable", "pass", file=str(path)),
            check("generation-output-hash", "pass" if valid_output else "fail", output=str(output)),
            check("generated-content-labeled", "pass" if labeled else "fail"),
            check("generation-human-review-required", "pass" if review_required else "fail"),
        ]
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        return [check("generation-provenance-readable", "fail", file=str(path), detail=str(exc))]


def run_qa(target: Path, plan: dict | None) -> dict:
    files = [target] if target.is_file() else sorted(path for path in target.rglob("*") if path.is_file())
    suffixes = {path.suffix.lower() for path in files}
    raster_route = bool(plan and plan.get("route") == "raster-illustration")
    technical_checks = [
        check("target-has-files", "pass" if files else "fail"),
        check("files-nonempty", "pass" if files and all(path.stat().st_size > 0 for path in files) else "fail"),
        check(
            "editable-source-present",
            "pass" if raster_route or suffixes & EDITABLE else "fail",
            detail="not required for an explicitly generated raster illustration" if raster_route else "required",
        ),
        check(
            "vector-export-present",
            "pass" if raster_route or suffixes & {".svg", ".pdf", ".eps"} else "fail",
            detail="not required for raster-illustration route" if raster_route else "required",
        ),
        check("preview-present", "pass" if ".png" in suffixes else "warn"),
    ]
    for path in files:
        if path.suffix.lower() == ".svg":
            technical_checks.extend(inspect_svg(path))
        elif path.suffix.lower() == ".pdf":
            technical_checks.extend(inspect_pdf(path))
        elif path.suffix.lower() == ".png":
            technical_checks.extend(inspect_png(path))

    if plan:
        technical_checks.append(check(
            "plan-evidence-guard",
            "pass" if plan.get("constraints", {}).get("forbid_invented_quantitative_claims") is True else "fail",
        ))
        technical_checks.append(check("plan-open-questions-resolved", "pass" if not plan.get("open_questions") else "warn"))
        review_status = plan.get("review_status")
        technical_checks.append(check("plan-reviewed", "pass" if review_status == "approved" else "warn", value=review_status))
        planned = [
            (str(panel.get("id", "")).lower(), ".png" if panel.get("type") == "raster-illustration" else ".svg")
            for panel in plan.get("panels", [])
        ]
        missing_panels = [
            panel_id for panel_id, suffix in planned
            if not any(path.name.lower() == f"panel_{panel_id}{suffix}" for path in files)
        ]
        technical_checks.append(check(
            "planned-panels-present", "fail" if missing_panels else "pass",
            detail=f"missing: {', '.join(missing_panels)}" if missing_panels else f"found {len(planned)} panel(s)",
        ))
        has_data_panels = any(panel.get("type") == "data-plot" for panel in plan.get("panels", []))
        if has_data_panels:
            technical_checks.append(check("data-render-source-present", "pass" if ".py" in suffixes else "fail"))
            provenance_files = [path for path in files if path.name in {"data-provenance.json", "provenance.json"}]
            technical_checks.append(check("data-provenance-present", "pass" if provenance_files else "fail"))
            for path in provenance_files:
                technical_checks.extend(verify_data_provenance(path))
        has_edit_panels = any(panel.get("type") == "edit" for panel in plan.get("panels", []))
        if has_edit_panels:
            edit_files = [path for path in files if path.name == "edit-provenance.json"]
            technical_checks.append(check("edit-provenance-present", "pass" if edit_files else "fail"))
            for path in edit_files:
                technical_checks.extend(verify_edit_provenance(path))
        has_raster_panels = any(panel.get("type") == "raster-illustration" for panel in plan.get("panels", []))
        if has_raster_panels:
            generation_files = [path for path in files if path.name == "generation-provenance.json"]
            request_files = [path for path in files if path.name == "raster-illustration-request.json"]
            technical_checks.append(check("generation-provenance-present", "pass" if generation_files else "fail"))
            technical_checks.append(check("generation-request-present", "pass" if request_files else "fail"))
            for path in generation_files:
                technical_checks.extend(verify_generation_provenance(path))
            for panel in (panel for panel in plan.get("panels", []) if panel.get("type") == "raster-illustration"):
                panel_id = str(panel.get("id", "")).lower()
                panel_path = next((path for path in files if path.name.lower() == f"panel_{panel_id}.png"), None)
                canvas = panel.get("canvas", {})
                expected = (canvas.get("width"), canvas.get("height"))
                actual = png_dimensions(panel_path) if panel_path else None
                size_ok = bool(
                    actual and all(isinstance(value, int) and value > 0 for value in expected)
                    and actual == expected
                )
                technical_checks.append(check(
                    "raster-canvas-size-exact", "pass" if size_ok else "fail",
                    panel=panel.get("id"), expected=list(expected), actual=list(actual) if actual else None,
                ))
                final_path = next(
                    (path for path in files if path.name.lower() == "figure.png" and path.parent.name.lower() == "final"),
                    None,
                )
                final_matches = bool(
                    panel_path and final_path and sha256(panel_path) == sha256(final_path)
                )
                technical_checks.append(check(
                    "raster-final-matches-reviewed-panel", "pass" if final_matches else "fail",
                    panel=str(panel_path) if panel_path else None,
                    final=str(final_path) if final_path else None,
                ))

    scientific_status = "not-applicable"
    human_review_status = "not-required"
    scientific_checks: list[dict] = []
    if raster_route:
        review_files = [path for path in files if path.name == "scientific-review.json"]
        if len(review_files) == 1:
            try:
                review = json.loads(review_files[0].read_text(encoding="utf-8"))
                validation = validate_review(review)
                scientific_status = validation["scientific_status"]
                human_review_status = validation["human_review_status"]
                scientific_checks.extend(validation["checks"])
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                scientific_status = "fail"
                human_review_status = "rejected"
                scientific_checks.append(check("scientific-review-readable", "fail", detail=str(exc)))
        else:
            scientific_status = "pending" if not review_files else "fail"
            human_review_status = "pending" if not review_files else "rejected"
            scientific_checks.append(check(
                "scientific-review-present", "warn" if not review_files else "fail",
                detail="prepare reports/scientific-review.json and complete assessment plus human approval",
            ))

    technical_status = "fail" if any(item["status"] == "fail" for item in technical_checks) else (
        "warn" if any(item["status"] == "warn" for item in technical_checks) else "pass"
    )
    if technical_status == "fail" or scientific_status == "fail" or human_review_status == "rejected":
        status = "fail"
    elif technical_status == "warn" or scientific_status == "pending" or human_review_status == "pending":
        status = "warn"
    else:
        status = "pass"
    return {
        "schema_version": "1.2",
        "status": status,
        "technical_status": technical_status,
        "scientific_status": scientific_status,
        "human_review_status": human_review_status,
        "target": str(target.resolve()),
        "checks": technical_checks + scientific_checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.target.exists():
        parser.error(f"target does not exist: {args.target}")
    plan = json.loads(args.plan.read_text(encoding="utf-8")) if args.plan else None
    report = run_qa(args.target, plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"QA status: {report['status']} -> {args.output}")
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
