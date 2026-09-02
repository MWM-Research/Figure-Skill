from __future__ import annotations
import json, re
from pathlib import Path
from review_generated_figure import validate_review
from .data_provenance import verify_data_provenance
from .edit_provenance import verify_edit_provenance
from .generated import verify_annotation_provenance, verify_generation_provenance
from .hybrid import verify_hybrid_audit
from .structural import check, inspect_pdf, inspect_png, inspect_svg, png_dimensions, sha256
EDITABLE = {'.svg', '.drawio', '.py', '.r', '.ipynb', '.ai', '.eps'}
PLACEHOLDER = re.compile(r'\b(?:todo|tbd|placeholder|lorem ipsum)\b', re.IGNORECASE)

def run_qa(target: Path, plan: dict | None) -> dict:
    files = [target] if target.is_file() else sorted(path for path in target.rglob("*") if path.is_file())
    suffixes = {path.suffix.lower() for path in files}
    raster_route = bool(plan and plan.get("route") in {"raster-illustration", "hybrid-composite"})
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
            (str(panel.get("id", "")).lower(), ".png" if panel.get("type") in {"raster-illustration", "hybrid-composite"} else ".svg")
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
                technical_checks.extend(verify_data_provenance(path, plan))
        has_edit_panels = any(panel.get("type") == "edit" for panel in plan.get("panels", []))
        if has_edit_panels:
            edit_files = [path for path in files if path.name == "edit-provenance.json"]
            technical_checks.append(check("edit-provenance-present", "pass" if edit_files else "fail"))
            for path in edit_files:
                edit_panel = next((panel for panel in plan.get("panels", []) if panel.get("type") == "edit"), None)
                technical_checks.extend(verify_edit_provenance(path, edit_panel))
        has_raster_panels = any(panel.get("type") in {"raster-illustration", "hybrid-composite"} for panel in plan.get("panels", []))
        if has_raster_panels:
            generation_files = [path for path in files if path.name == "generation-provenance.json"]
            request_files = [path for path in files if path.name == "raster-illustration-request.json"]
            technical_checks.append(check("generation-provenance-present", "pass" if generation_files else "fail"))
            technical_checks.append(check("generation-request-present", "pass" if request_files else "fail"))
            for path in generation_files:
                technical_checks.extend(verify_generation_provenance(path))
            for panel in (panel for panel in plan.get("panels", []) if panel.get("type") in {"raster-illustration", "hybrid-composite"}):
                if panel.get("annotation_spec", {}).get("mode") == "deterministic-overlay":
                    annotation_files = [path for path in files if path.name == "annotation-provenance.json"]
                    technical_checks.append(check(
                        "annotation-provenance-present", "pass" if len(annotation_files) == 1 else "fail",
                        count=len(annotation_files),
                    ))
                    for path in annotation_files:
                        technical_checks.extend(verify_annotation_provenance(path, panel))
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
        has_representation_contract = isinstance(plan.get("representation_contract"), dict) or any(
            isinstance(panel.get("representation_contract"), dict) for panel in plan.get("panels", [])
        )
        if has_representation_contract:
            audit_files = [path for path in files if path.name == "hybrid-structure-audit.json"]
            technical_checks.append(check(
                "hybrid-structure-audit-present", "pass" if len(audit_files) == 1 else "fail", count=len(audit_files)
            ))
            for path in audit_files:
                technical_checks.extend(verify_hybrid_audit(path))

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
