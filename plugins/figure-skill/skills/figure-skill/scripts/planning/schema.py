from __future__ import annotations
from pathlib import Path
from typing import Any
from .data import data_panels
from .hybrid import hybrid_composite_panel
from .illustration import illustration_panel
from .raster import raster_illustration_panel
from .routes import EDIT_OPERATIONS, EDIT_SUFFIXES, ROUTES, choose_route
from .edit import edit_panel

def build_plan(
    inventory: dict, brief: str, explicit_route: str = "auto",
    edit_operations: list[dict[str, Any]] | None = None,
) -> dict:
    route = choose_route(inventory, brief, explicit_route)
    backend_map = {
        "data-plot": ["project-native plotting stack", "Python/Matplotlib"],
        "illustration": ["native SVG or draw.io", "PaperBanana-style pipeline", "image generator draft"],
        "raster-illustration": ["BYOK OpenAI-compatible Images API", "deterministic 3D renderer when available"],
        "hybrid-composite": ["hybrid SVG compositor", "Draw.io for architecture", "audit_hybrid_svg.py"],
        "edit": ["native SVG editor or draw.io", "AutoFigure-Edit for raster-to-SVG reconstruction"],
        "composite": ["Python/Matplotlib for evidence panels", "SVG or draw.io for assembly"],
    }
    questions = []
    panels: list[dict] = []
    if not brief.strip():
        questions.append("What single claim or research question must the figure communicate?")

    if route in {"illustration", "composite"}:
        illustration, illustration_questions = illustration_panel(inventory, "A")
        if illustration:
            panels.append(illustration)
        questions.extend(illustration_questions)
    if route == "raster-illustration":
        raster_panel, raster_questions = raster_illustration_panel(inventory, brief, "A")
        panels.append(raster_panel)
        questions.extend(raster_questions)
    if route == "hybrid-composite":
        hybrid_panel, hybrid_questions = hybrid_composite_panel(inventory, brief, "A")
        panels.append(hybrid_panel)
        questions.extend(hybrid_questions)
    if route in {"data-plot", "composite"}:
        data_start = len(panels)
        generated, data_questions = data_panels(inventory, brief, data_start)
        panels.extend(generated)
        questions.extend(data_questions)
        if not generated:
            questions.append("No structured data table could be planned; convert logs or unsupported tables to CSV, JSON, or XLSX.")
    if route == "edit":
        generated, edit_questions = edit_panel(inventory, edit_operations, "A")
        panels.append(generated)
        questions.extend(edit_questions)

    raster_route = route in {"raster-illustration", "hybrid-composite"}
    return {
        "schema_version": "1.1",
        "route": route,
        "route_source": "user" if explicit_route != "auto" else "inferred",
        "brief": brief,
        "input_root": inventory.get("root"),
        "inputs": [item.get("path") for item in inventory.get("files", [])],
        "panels": panels,
        "constraints": {
            "evidence_only": True,
            "forbid_invented_quantitative_claims": True,
            "editable_source_required": not raster_route,
            "generated_content_must_be_labeled": raster_route,
        },
        "recommended_backends": backend_map[route],
        "required_outputs": (
            ["png", "generation-provenance", "qa-report"] if raster_route
            else ["editable-source", "svg", "pdf", "png", "provenance"]
        ),
        "review_status": "draft",
        "open_questions": list(dict.fromkeys(questions)),
    }
