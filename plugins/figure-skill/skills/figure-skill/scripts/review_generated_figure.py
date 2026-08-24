#!/usr/bin/env python3
"""Create, record, and validate scientific review gates for generated raster figures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ASSERTION_STATUSES = {"pending", "pass", "fail", "uncertain"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:40] or "item"


def select_panel(plan: dict) -> dict:
    panels = [panel for panel in plan.get("panels", []) if panel.get("type") == "raster-illustration"]
    if len(panels) != 1:
        raise ValueError("scientific raster review requires exactly one raster-illustration panel")
    return panels[0]


def required_assertions(panel: dict) -> list[dict]:
    assertions = []
    for index, entity in enumerate(panel.get("entities", []), start=1):
        assertions.append({
            "id": f"entity-{index}-{slug(str(entity))}",
            "category": "required-entity",
            "description": f"Required entity is visibly present and scientifically recognizable: {entity}",
            "status": "pending",
            "evidence": "",
        })
    for index, edge in enumerate(panel.get("edges", []), start=1):
        assertions.append({
            "id": f"relationship-{index}",
            "category": "required-relationship",
            "description": (
                f"Required relationship is visually supported: {edge.get('from')} -> {edge.get('to')} "
                f"({edge.get('meaning', 'relationship')})"
            ),
            "status": "pending",
            "evidence": "",
        })
    for index, item in enumerate(panel.get("forbidden_content", []), start=1):
        assertions.append({
            "id": f"forbidden-{index}-{slug(str(item))}",
            "category": "forbidden-content",
            "description": f"Forbidden content is absent: {item}",
            "status": "pending",
            "evidence": "",
        })
    labels = [str(value) for value in panel.get("visible_labels", []) if str(value).strip()]
    if labels:
        for index, label in enumerate(labels, start=1):
            assertions.append({
                "id": f"label-{index}-{slug(label)}",
                "category": "visible-label",
                "description": f"Approved visible label is present and readable exactly: {label}",
                "status": "pending",
                "evidence": "",
            })
    else:
        assertions.append({
            "id": "no-unapproved-visible-text",
            "category": "visible-label",
            "description": "No unapproved visible text, numbers, logos, or watermarks are present.",
            "status": "pending",
            "evidence": "",
        })
    assertions.append({
        "id": "illustrative-not-empirical",
        "category": "evidence-role",
        "description": "The image reads as a conceptual illustration and does not imply empirical evidence.",
        "status": "pending",
        "evidence": "",
    })
    assertions.append({
        "id": "no-prominent-unplanned-content",
        "category": "plan-conformance",
        "description": "No visually prominent unplanned objects, scenes, or scientific content substitutions are present.",
        "status": "pending",
        "evidence": "",
    })
    for index, item in enumerate(panel.get("semantic_assertions", []), start=1):
        assertions.append({
            "id": f"semantic-{index}-{slug(str(item))}",
            "category": "plan-specific",
            "description": str(item),
            "status": "pending",
            "evidence": "",
        })
    assertions.append({
        "id": "intended-use-fit",
        "category": "delivery-fit",
        "description": "The image is suitable for the intended paper role stated in the reviewed plan.",
        "status": "pending",
        "evidence": "",
    })
    return assertions


def prepare_review(plan_path: Path, image_path: Path) -> dict:
    if not plan_path.is_file() or not image_path.is_file():
        raise FileNotFoundError("plan and generated image must exist")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    panel = select_panel(plan)
    return {
        "schema_version": "1.0",
        "panel": panel.get("id"),
        "plan": str(plan_path.resolve()),
        "plan_sha256": sha256(plan_path),
        "image": str(image_path.resolve()),
        "image_sha256": sha256(image_path),
        "scientific_assessment": {
            "status": "pending",
            "reviewer": "",
            "reviewer_type": "agent-assisted",
            "reviewed_at": None,
            "assertions": required_assertions(panel),
            "notes": [],
        },
        "human_approval": {
            "status": "pending",
            "reviewer": "",
            "reviewed_at": None,
            "note": "",
        },
    }


def assessment_status(assertions: list[dict]) -> str:
    statuses = [item.get("status") for item in assertions]
    if any(status == "fail" for status in statuses):
        return "fail"
    if statuses and all(status == "pass" for status in statuses):
        return "pass"
    return "pending"


def apply_assessment(review: dict, results: list[str], reviewer: str, note: str | None = None) -> dict:
    by_id = {item["id"]: item for item in review["scientific_assessment"]["assertions"]}
    for assignment in results:
        assertion_id, separator, status = assignment.partition("=")
        if not separator or assertion_id not in by_id or status not in ASSERTION_STATUSES - {"pending"}:
            raise ValueError(f"invalid assessment result: {assignment}")
        by_id[assertion_id]["status"] = status
    assessment = review["scientific_assessment"]
    assessment["status"] = assessment_status(assessment["assertions"])
    assessment["reviewer"] = reviewer
    assessment["reviewed_at"] = timestamp()
    if note:
        assessment.setdefault("notes", []).append(note)
    if assessment["status"] != "pass":
        review["human_approval"] = {
            "status": "pending", "reviewer": "", "reviewed_at": None, "note": ""
        }
    return review


def apply_human_decision(review: dict, decision: str, reviewer: str, note: str, confirmed: bool) -> dict:
    if not confirmed:
        raise ValueError("human decision requires --confirm-reviewed")
    if decision == "approved" and review["scientific_assessment"].get("status") != "pass":
        raise ValueError("human approval requires a passing scientific assessment")
    review["human_approval"] = {
        "status": decision,
        "reviewer": reviewer,
        "reviewed_at": timestamp(),
        "note": note,
    }
    return review


def validate_review(review: dict, plan_path: Path | None = None, image_path: Path | None = None) -> dict:
    checks = []
    resolved_plan = plan_path or Path(str(review.get("plan", "")))
    resolved_image = image_path or Path(str(review.get("image", "")))
    plan_valid = resolved_plan.is_file() and review.get("plan_sha256") == sha256(resolved_plan)
    image_valid = resolved_image.is_file() and review.get("image_sha256") == sha256(resolved_image)
    checks.extend([
        {"check": "scientific-review-plan-hash", "status": "pass" if plan_valid else "fail"},
        {"check": "scientific-review-image-hash", "status": "pass" if image_valid else "fail"},
    ])
    assertions = review.get("scientific_assessment", {}).get("assertions", [])
    assessment = review.get("scientific_assessment", {})
    statuses_valid = bool(assertions) and all(item.get("status") in ASSERTION_STATUSES for item in assertions)
    computed_scientific = assessment_status(assertions) if statuses_valid else "fail"
    recorded_scientific = assessment.get("status")
    assessment_metadata_valid = bool(
        assessment.get("reviewer")
        and assessment.get("reviewed_at")
        and assessment.get("reviewer_type") in {"agent-assisted", "human"}
    )
    scientific_status = computed_scientific if computed_scientific == recorded_scientific else "fail"
    if scientific_status == "pass" and not assessment_metadata_valid:
        scientific_status = "fail"
    if not plan_valid or not image_valid:
        scientific_status = "fail"
    human = review.get("human_approval", {})
    human_status = human.get("status", "pending")
    if human_status not in {"pending", "approved", "rejected"}:
        human_status = "rejected"
    if human_status == "approved" and scientific_status != "pass":
        human_status = "rejected"
    if human_status in {"approved", "rejected"} and not (human.get("reviewer") and human.get("reviewed_at")):
        human_status = "rejected"
    checks.append({
        "check": "scientific-assertions",
        "status": "pass" if scientific_status == "pass" else ("warn" if scientific_status == "pending" else "fail"),
        "detail": {status: sum(1 for item in assertions if item.get("status") == status) for status in ASSERTION_STATUSES},
    })
    checks.append({
        "check": "scientific-reviewer-recorded",
        "status": "pass" if assessment_metadata_valid else ("warn" if scientific_status == "pending" else "fail"),
    })
    checks.append({
        "check": "human-approval",
        "status": "pass" if human_status == "approved" else ("warn" if human_status == "pending" else "fail"),
        "value": human_status,
    })
    checks.append({
        "check": "human-reviewer-recorded",
        "status": "pass" if human_status in {"approved", "rejected"} and human.get("reviewer") and human.get("reviewed_at") else "warn",
    })
    return {"scientific_status": scientific_status, "human_review_status": human_status, "checks": checks}


def write_review(review: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--plan", type=Path, required=True)
    prepare.add_argument("--image", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    assess = subparsers.add_parser("assess")
    assess.add_argument("review", type=Path)
    assess.add_argument("--result", action="append", default=[])
    assess.add_argument("--reviewer", required=True)
    assess.add_argument("--note")
    human = subparsers.add_parser("human")
    human.add_argument("review", type=Path)
    human.add_argument("--decision", choices=("approved", "rejected"), required=True)
    human.add_argument("--reviewer", required=True)
    human.add_argument("--note", default="")
    human.add_argument("--confirm-reviewed", action="store_true")
    validate = subparsers.add_parser("validate")
    validate.add_argument("review", type=Path)
    args = parser.parse_args()

    if args.command == "prepare":
        write_review(prepare_review(args.plan.resolve(), args.image.resolve()), args.output.resolve())
        print(f"Prepared scientific review template -> {args.output.resolve()}")
        return 0
    review = json.loads(args.review.read_text(encoding="utf-8"))
    if args.command == "assess":
        write_review(apply_assessment(review, args.result, args.reviewer, args.note), args.review)
        print(f"Recorded scientific assessment -> {args.review.resolve()}")
        return 0
    if args.command == "human":
        write_review(
            apply_human_decision(review, args.decision, args.reviewer, args.note, args.confirm_reviewed),
            args.review,
        )
        print(f"Recorded human decision -> {args.review.resolve()}")
        return 0
    result = validate_review(review)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["scientific_status"] == "pass" and result["human_review_status"] == "approved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
