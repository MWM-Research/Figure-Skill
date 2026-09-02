from __future__ import annotations
import json
from pathlib import Path
from .structural import check, sha256

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


def verify_annotation_provenance(path: Path, panel: dict) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        output = Path(str(data.get("output", "")))
        overlay = Path(str(data.get("overlay_source", "")))
        valid_output = output.is_file() and data.get("output_sha256") == sha256(output)
        valid_overlay = overlay.is_file() and data.get("overlay_source_sha256") == sha256(overlay)
        planned_labels = sorted(str(value) for value in panel.get("visible_labels", []))
        actual_labels = sorted(str(value) for value in data.get("visible_labels", []))
        labels_match = bool(planned_labels) and planned_labels == actual_labels
        canvas = panel.get("canvas", {})
        canvas_match = data.get("canvas") == [canvas.get("width"), canvas.get("height")]
        return [
            check("annotation-provenance-readable", "pass", file=str(path)),
            check("annotation-output-hash", "pass" if valid_output else "fail", output=str(output)),
            check("annotation-source-hash", "pass" if valid_overlay else "fail", source=str(overlay)),
            check("annotation-visible-labels", "pass" if labels_match else "fail", count=len(actual_labels)),
            check("annotation-canvas", "pass" if canvas_match else "fail", value=data.get("canvas")),
        ]
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        return [check("annotation-provenance-readable", "fail", file=str(path), detail=str(exc))]
