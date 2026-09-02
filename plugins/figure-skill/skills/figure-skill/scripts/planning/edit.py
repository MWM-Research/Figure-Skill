from __future__ import annotations

from pathlib import Path
from typing import Any

from .routes import EDIT_OPERATIONS, EDIT_SUFFIXES


def edit_panel(inventory: dict, edit_operations: list[dict[str, Any]] | None, panel_id: str = "A") -> tuple[dict, list[str]]:
    editable = next((item for item in inventory.get("files", []) if Path(item.get("path", "")).suffix.lower() in EDIT_SUFFIXES), None)
    operations = edit_operations or []
    panel = {"id": panel_id, "title": "Edited figure", "type": "edit", "source_files": [editable.get("path")] if editable else [], "visual_form": "preserve-source-format", "backend": "native-vector-editor", "operations": operations}
    questions = []
    if not editable:
        questions.append("Provide an editable SVG, draw.io, AI, or EPS source file.")
    elif Path(editable.get("path", "")).suffix.lower() != ".svg":
        questions.append("Native deterministic editing currently supports SVG; use the external edit handoff for this format.")
    if not operations:
        questions.append("Define explicit edit operations for review before approval; see advanced-svg-editing.md for supported exact-ID and semantic SVG operations.")
    else:
        unsupported = sorted({str(item.get("op")) for item in operations if item.get("op") not in EDIT_OPERATIONS})
        if unsupported:
            questions.append("Replace unsupported edit operations before approval: " + ", ".join(unsupported) + ".")
    return panel, questions
