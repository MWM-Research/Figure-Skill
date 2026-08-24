#!/usr/bin/env python3
"""Create an evidence-linked scientific figure plan from an input inventory."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROUTES = ("illustration", "raster-illustration", "data-plot", "edit", "composite")
EDIT_SUFFIXES = {".svg", ".drawio", ".ai", ".eps"}
EDIT_WORDS = ("edit", "revise", "modify", "修改", "编辑", "调整", "重绘", "补充")
FLOW_WORDS = ("flow", "flows", "followed by", "then", "from", "to", "流向", "依次", "然后", "经过", "到")
ENTITY_TERMS = (
    "input", "encoder", "decoder", "backbone", "embedding", "retrieval", "retriever",
    "classifier", "predictor", "generator", "discriminator", "attention", "transformer",
    "database", "knowledge graph", "feature extractor", "fusion", "output",
    "train/test split", "standard scaler", "logistic regression", "prediction", "accuracy",
    "输入", "编码器", "解码器", "骨干网络", "嵌入", "检索器", "检索模块", "分类器",
    "预测器", "生成器", "判别器", "注意力", "数据库", "知识图谱", "特征提取", "融合", "输出",
)
METRIC_PRIORITY = (
    "accuracy", "acc", "f1", "precision", "recall", "auc", "score", "performance",
    "throughput", "latency", "time", "memory", "loss", "error",
)
RASTER_ILLUSTRATION_WORDS = (
    "photorealistic", "photo style", "photo-style", "3d", "three-dimensional",
    "照片风格", "照片级", "写实", "三维", "3d科研", "科研插画", "概念插画",
)


def data_files(inventory: dict) -> list[dict]:
    return [item for item in inventory.get("files", []) if item.get("table_profile", {}).get("data_candidate")]


def choose_route(inventory: dict, brief: str, explicit: str = "auto") -> str:
    if explicit != "auto":
        return explicit
    counts = inventory.get("category_counts", {})
    paths = [Path(item.get("path", "")) for item in inventory.get("files", [])]
    has_data = bool(data_files(inventory) or counts.get("log"))
    has_context = bool(counts.get("narrative") or counts.get("raster") or counts.get("vector"))
    has_editable = any(path.suffix.lower() in EDIT_SUFFIXES for path in paths)
    wants_edit = any(word in brief.lower() for word in EDIT_WORDS)
    wants_raster_illustration = any(word in brief.lower() for word in RASTER_ILLUSTRATION_WORDS)
    if wants_raster_illustration and not has_data:
        return "raster-illustration"
    if has_data and has_context:
        return "composite"
    if has_data:
        return "data-plot"
    if has_editable and wants_edit:
        return "edit"
    return "illustration"


def metric_rank(name: str, brief: str) -> tuple[int, int]:
    lowered = name.lower()
    brief_lower = brief.lower()
    direct = 0 if lowered in brief_lower else 1
    priority = next((index for index, term in enumerate(METRIC_PRIORITY) if term in lowered), len(METRIC_PRIORITY))
    return direct, priority


def infer_unit(name: str, minimum: float | None, maximum: float | None) -> str | None:
    lowered = name.lower()
    if lowered.endswith("_ms") or "latency_ms" in lowered:
        return "ms"
    if lowered.endswith("_s") or lowered in {"time", "runtime", "duration"}:
        return "s"
    if any(term in lowered for term in ("memory_mb", "ram_mb")):
        return "MB"
    if any(term in lowered for term in ("accuracy", "precision", "recall", "f1", "auc")):
        if minimum is not None and maximum is not None and 0 <= minimum <= maximum <= 1:
            return "fraction"
        if minimum is not None and maximum is not None and 0 <= minimum <= maximum <= 100:
            return "%"
    return None


def choose_chart(columns: list[dict], brief: str) -> dict[str, Any]:
    categorical = [column for column in columns if column.get("type") in {"categorical", "text", "datetime"}]
    numeric = [column for column in columns if column.get("type") == "numeric"]
    numeric.sort(key=lambda column: metric_rank(str(column.get("name", "")), brief))
    if not numeric:
        return {"visual_form": None, "x": None, "y": None, "unit": None}

    brief_lower = brief.lower()
    wants_scatter = any(word in brief_lower for word in ("scatter", "散点", "correlation", "相关"))
    y = numeric[0]
    if wants_scatter and len(numeric) > 1:
        x = numeric[1]
    else:
        x = categorical[0] if categorical else (numeric[1] if len(numeric) > 1 else None)
    if wants_scatter and x and x.get("type") == "numeric":
        visual_form = "scatter-plot"
    elif x and x.get("type") in {"numeric", "datetime"}:
        visual_form = "line-chart"
    else:
        visual_form = "bar-chart"
    return {
        "visual_form": visual_form,
        "x": x.get("name") if x else None,
        "y": y.get("name"),
        "group": categorical[1].get("name") if visual_form == "bar-chart" and len(categorical) > 1 else None,
        "unit": infer_unit(str(y.get("name", "")), y.get("min"), y.get("max")),
    }


def data_panels(inventory: dict, brief: str, start_index: int = 0) -> tuple[list[dict], list[str]]:
    panels = []
    questions = []
    for offset, item in enumerate(data_files(inventory)):
        profile = item.get("table_profile", {})
        chart = choose_chart(profile.get("columns", []), brief)
        panel_id = chr(ord("A") + start_index + offset)
        if chart["visual_form"] == "scatter-plot" and chart["x"] and chart["y"]:
            title = f"{chart['y']} vs {chart['x']}"
        elif chart["visual_form"] == "line-chart" and chart["x"] and chart["y"]:
            title = f"{chart['y']} by {chart['x']}"
        else:
            title = f"{chart['y']} comparison" if chart["y"] else "Data summary"
        panel = {
            "id": panel_id,
            "title": title,
            "type": "data-plot",
            "source_files": [item.get("path")],
            "visual_form": chart["visual_form"],
            "x": chart["x"],
            "y": chart["y"],
            "group": chart.get("group"),
            "unit": chart["unit"],
            "transform": "none",
            "backend": "matplotlib",
        }
        panels.append(panel)
        if not chart["y"]:
            questions.append(f"Choose a numeric metric for panel {panel_id} from {item.get('path')}.")
        if not chart["x"]:
            questions.append(f"Choose an x-axis or grouping column for panel {panel_id} from {item.get('path')}.")
    return panels, questions


def extract_entities(text: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    lowered = text.lower()
    for term in ENTITY_TERMS:
        position = lowered.find(term.lower())
        if position >= 0:
            original = text[position:position + len(term)]
            normalized = original.strip().title() if original.isascii() else original.strip()
            matches.append((position, normalized))
    matches.sort()
    result = []
    seen = set()
    for _, entity in matches:
        key = entity.lower()
        if key not in seen:
            seen.add(key)
            result.append(entity)
    return result[:10]


def illustration_panel(inventory: dict, panel_id: str = "A") -> tuple[dict | None, list[str]]:
    narratives = [item for item in inventory.get("files", []) if item.get("text_preview")]
    if not narratives:
        return None, ["Provide methods text or explicitly define the entities and arrow relationships."]
    source = narratives[0]
    text = str(source.get("text_preview", ""))
    entities = extract_entities(text)
    has_flow_evidence = any(word in text.lower() for word in FLOW_WORDS)
    edges = []
    if has_flow_evidence and len(entities) >= 2:
        edges = [
            {"from": left, "to": right, "meaning": "data-flow", "inferred": True}
            for left, right in zip(entities, entities[1:])
        ]
    questions = []
    if len(entities) < 2:
        questions.append(f"Confirm at least two diagram entities for panel {panel_id}.")
    if len(entities) >= 2 and not edges:
        questions.append(f"Confirm arrow direction and meaning for panel {panel_id}; no explicit flow statement was found.")
    return {
        "id": panel_id,
        "title": "Method pipeline",
        "type": "illustration",
        "source_files": [source.get("path")],
        "visual_form": "architecture-diagram",
        "entities": entities,
        "edges": edges,
        "reading_order": "left-to-right",
        "backend": "svg",
        "inference_requires_review": bool(entities or edges),
    }, questions


def raster_illustration_panel(inventory: dict, brief: str, panel_id: str = "A") -> tuple[dict, list[str]]:
    narratives = [item for item in inventory.get("files", []) if item.get("text_preview")]
    source = narratives[0] if narratives else None
    text = str(source.get("text_preview", "")) if source else ""
    entities = extract_entities(text)
    has_flow_evidence = any(word in text.lower() for word in FLOW_WORDS)
    edges = [
        {"from": left, "to": right, "meaning": "data-flow", "inferred": True}
        for left, right in zip(entities, entities[1:])
    ] if has_flow_evidence and len(entities) >= 2 else []
    lowered = brief.lower()
    style = "3d-render" if any(word in lowered for word in ("3d", "three-dimensional", "三维")) else (
        "photorealistic" if any(word in lowered for word in ("photorealistic", "photo", "照片", "写实"))
        else "scientific-concept-art"
    )
    questions = []
    if not source:
        questions.append(f"Provide reviewed methods text for raster illustration panel {panel_id}.")
    if not entities:
        questions.append(f"Confirm the scientific entities that must appear in raster illustration panel {panel_id}.")
    if len(entities) >= 2 and not edges:
        questions.append(
            f"Confirm the spatial or directional relationships for raster illustration panel {panel_id}; "
            "no explicit flow statement was found."
        )
    return {
        "id": panel_id,
        "title": "Generated scientific illustration",
        "type": "raster-illustration",
        "source_files": [source.get("path")] if source else [],
        "visual_form": "generated-raster",
        "style": style,
        "evidence_role": "illustrative",
        "scientific_description": text[:1500],
        "entities": entities,
        "edges": edges,
        "visible_labels": [],
        "forbidden_content": [
            "invented measurements or statistics",
            "unapproved labels",
            "watermarks",
            "presentation as microscopy, medical, field, or instrument evidence",
        ],
        "backend": "byok-openai-compatible-images",
        "human_review_required": True,
    }, questions


def build_plan(
    inventory: dict, brief: str, explicit_route: str = "auto",
    edit_operations: list[dict[str, Any]] | None = None,
) -> dict:
    route = choose_route(inventory, brief, explicit_route)
    backend_map = {
        "data-plot": ["project-native plotting stack", "Python/Matplotlib"],
        "illustration": ["native SVG or draw.io", "PaperBanana-style pipeline", "image generator draft"],
        "raster-illustration": ["BYOK OpenAI-compatible Images API", "deterministic 3D renderer when available"],
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
    if route in {"data-plot", "composite"}:
        data_start = len(panels)
        generated, data_questions = data_panels(inventory, brief, data_start)
        panels.extend(generated)
        questions.extend(data_questions)
        if not generated:
            questions.append("No structured data table could be planned; convert logs or unsupported tables to CSV, JSON, or XLSX.")
    if route == "edit":
        editable = next((item for item in inventory.get("files", []) if Path(item.get("path", "")).suffix.lower() in EDIT_SUFFIXES), None)
        operations = edit_operations or []
        panels.append({
            "id": "A",
            "title": "Edited figure",
            "type": "edit",
            "source_files": [editable.get("path")] if editable else [],
            "visual_form": "preserve-source-format",
            "backend": "native-vector-editor",
            "operations": operations,
        })
        if not editable:
            questions.append("Provide an editable SVG, draw.io, AI, or EPS source file.")
        elif Path(editable.get("path", "")).suffix.lower() != ".svg":
            questions.append("Native deterministic editing currently supports SVG; use the external edit handoff for this format.")
        if not operations:
            questions.append(
                "Define explicit edit operations before approval; supported SVG operations are replace_text and set_attribute."
            )

    raster_route = route == "raster-illustration"
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--brief", default="")
    parser.add_argument("--brief-file", type=Path, help="Read the figure brief from a UTF-8 text file")
    parser.add_argument("--route", choices=("auto",) + ROUTES, default="auto")
    parser.add_argument("--edit-operations", type=Path, help="JSON array of explicit edit operations")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.inventory.read_text(encoding="utf-8"))
    brief = args.brief_file.read_text(encoding="utf-8-sig").strip() if args.brief_file else args.brief
    operations = json.loads(args.edit_operations.read_text(encoding="utf-8")) if args.edit_operations else None
    if operations is not None and not isinstance(operations, list):
        parser.error("--edit-operations must contain a JSON array")
    plan = build_plan(data, brief, args.route, operations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Selected route: {plan['route']}; planned {len(plan['panels'])} panel(s) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
