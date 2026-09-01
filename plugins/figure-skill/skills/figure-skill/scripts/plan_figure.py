#!/usr/bin/env python3
"""Create an evidence-linked scientific figure plan from an input inventory."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROUTES = ("illustration", "raster-illustration", "hybrid-composite", "data-plot", "edit", "composite")
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
HYBRID_RASTER_WORDS = ("raster", "栅格", "video frame", "视频帧", "heatmap", "热力图", "photo", "image")
HYBRID_VECTOR_WORDS = ("vector", "矢量", "module", "模块", "arrow", "箭头", "axis", "坐标轴", "bar chart", "柱状图")
HEATMAP_WORDS = ("heatmap", "heat map", "热力图", "confusion matrix", "混淆矩阵")
LINE_WORDS = ("line chart", "line plot", "curve", "training curve", "折线图", "曲线", "多系列", "multi-series")
ERROR_WORDS = ("error bar", "uncertainty", "confidence interval", "误差线", "误差棒", "不确定性", "置信区间")
UNCERTAINTY_COLUMN_WORDS = (
    "error", "stderr", "standard_error", "std", "stdev", "stddev", "standard_deviation",
    "sem", "uncertainty", "ci", "confidence",
)
HEATMAP_VALUE_WORDS = ("attention", "intensity", "value", "score", "count", "frequency", "probability", "weight")
HEATMAP_X_WORDS = ("frame", "time", "epoch", "pred", "column", "col")
HEATMAP_Y_WORDS = ("head", "actual", "true", "row", "class")
ADVANCED_FORMS = (
    (("box plot", "boxplot", "箱线图"), "box-plot"),
    (("violin", "小提琴图"), "violin-plot"),
    (("histogram", "直方图"), "histogram"),
    (("density plot", "density curve", "密度图", "密度曲线"), "density-plot"),
    (("confusion matrix", "混淆矩阵"), "confusion-matrix"),
    (("roc",), "roc-curve"),
    (("precision-recall", "precision recall", "pr curve", "pr曲线"), "pr-curve"),
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
    wants_hybrid = (
        "hybrid" in brief.lower() or "混合" in brief
        or (
            any(word in brief.lower() for word in HYBRID_RASTER_WORDS)
            and any(word in brief.lower() for word in HYBRID_VECTOR_WORDS)
        )
    )
    if wants_hybrid:
        return "hybrid-composite"
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


def contains_term(name: str, terms: tuple[str, ...]) -> bool:
    lowered = name.lower().replace("-", "_").replace(" ", "_")
    tokens = [token for token in re.split(r"[^a-z0-9]+", lowered) if token]
    for term in terms:
        normalized = term.replace("-", "_").replace(" ", "_")
        if len(normalized) <= 3:
            if normalized in tokens or (
                normalized == "ci" and any(re.fullmatch(r"ci\d+", token) for token in tokens)
            ):
                return True
        elif normalized in lowered:
            return True
    return False


def heatmap_value_rank(column: dict, brief: str) -> tuple[int, int, tuple[int, int]]:
    name = str(column.get("name", ""))
    lowered = name.lower()
    direct = 0 if lowered in brief.lower() else 1
    semantic = next((index for index, term in enumerate(HEATMAP_VALUE_WORDS) if term in lowered), len(HEATMAP_VALUE_WORDS))
    return direct, semantic, metric_rank(name, brief)


def heatmap_axis_rank(column: dict, *, x_axis: bool) -> tuple[int, str]:
    name = str(column.get("name", ""))
    if name.lower() == ("x" if x_axis else "y"):
        return 0, name.lower()
    if name.lower() == ("y" if x_axis else "x"):
        return 2, name.lower()
    preferred = HEATMAP_X_WORDS if x_axis else HEATMAP_Y_WORDS
    opposite = HEATMAP_Y_WORDS if x_axis else HEATMAP_X_WORDS
    if contains_term(name, preferred):
        return 0, name.lower()
    if contains_term(name, opposite):
        return 2, name.lower()
    return 1, name.lower()


def choose_chart(columns: list[dict], brief: str) -> dict[str, Any]:
    categorical = [column for column in columns if column.get("type") in {"categorical", "text", "datetime"}]
    numeric = [column for column in columns if column.get("type") == "numeric"]
    uncertainty = [column for column in numeric if contains_term(str(column.get("name", "")), UNCERTAINTY_COLUMN_WORDS)]
    measures = [column for column in numeric if column not in uncertainty]
    measures.sort(key=lambda column: metric_rank(str(column.get("name", "")), brief))
    if not measures:
        return {
            "visual_form": None, "x": None, "y": None, "value": None,
            "group": None, "error": None, "error_candidates": [], "error_requested": False, "unit": None,
        }

    brief_lower = brief.lower()
    advanced_form = next((form for words, form in ADVANCED_FORMS if any(word in brief_lower for word in words)), None)
    if advanced_form:
        base = {
            "visual_form": advanced_form, "x": None, "y": None, "value": None, "group": None,
            "error": None, "error_candidates": [], "error_requested": False, "unit": None,
            "calculation": None, "actual": None, "predicted": None, "label": None, "score": None,
        }
        if advanced_form in {"box-plot", "violin-plot"}:
            base.update({"x": categorical[0].get("name") if categorical else None, "y": measures[0].get("name"), "unit": infer_unit(str(measures[0].get("name", "")), measures[0].get("min"), measures[0].get("max")), "calculation": {"mode": "raw", "operation": "kde" if advanced_form == "violin-plot" else "box-summary", "parameters": {"bandwidth": "scott"} if advanced_form == "violin-plot" else {}}})
        elif advanced_form in {"histogram", "density-plot"}:
            base.update({"value": measures[0].get("name"), "group": categorical[0].get("name") if categorical else None, "calculation": {"mode": "raw", "operation": "histogram" if advanced_form == "histogram" else "kde", "parameters": {"strategy": "fd", "density": False} if advanced_form == "histogram" else {"bandwidth": "scott"}}})
        elif advanced_form == "confusion-matrix":
            base.update({"actual": categorical[0].get("name") if categorical else None, "predicted": categorical[1].get("name") if len(categorical) > 1 else None, "calculation": {"mode": "raw", "operation": "confusion-count", "parameters": {"normalization": "none"}}})
        else:
            base.update({"label": categorical[0].get("name") if categorical else None, "score": measures[0].get("name"), "group": categorical[1].get("name") if len(categorical) > 1 else None, "calculation": {"mode": "raw", "operation": "roc" if advanced_form == "roc-curve" else "pr", "parameters": {"positive_label": None, "compute_auc": False}}})
        return base
    wants_heatmap = any(word in brief_lower for word in HEATMAP_WORDS)
    if wants_heatmap:
        value = min(measures, key=lambda column: heatmap_value_rank(column, brief))
        axes = [column for column in columns if column is not value and column not in uncertainty]
        if len(axes) < 2:
            return {
                "visual_form": "heatmap", "x": None, "y": None, "value": value.get("name"),
                "group": None, "error": None, "error_candidates": [],
                "error_requested": False,
                "unit": infer_unit(str(value.get("name", "")), value.get("min"), value.get("max")),
            }
        x = min(axes, key=lambda column: heatmap_axis_rank(column, x_axis=True))
        remaining = [column for column in axes if column is not x]
        y = min(remaining, key=lambda column: heatmap_axis_rank(column, x_axis=False))
        return {
            "visual_form": "heatmap",
            "x": x.get("name"),
            "y": y.get("name"),
            "value": value.get("name"),
            "group": None,
            "error": None,
            "error_candidates": [],
            "error_requested": False,
            "unit": infer_unit(str(value.get("name", "")), value.get("min"), value.get("max")),
        }

    wants_scatter = any(word in brief_lower for word in ("scatter", "散点", "correlation", "相关"))
    wants_line = any(word in brief_lower for word in LINE_WORDS)
    wants_error = any(word in brief_lower for word in ERROR_WORDS)
    y = measures[0]
    remaining_numeric = [column for column in measures if column is not y]
    if (wants_scatter or wants_line) and remaining_numeric:
        x = remaining_numeric[0]
    else:
        x = categorical[0] if categorical else (remaining_numeric[0] if remaining_numeric else None)
    if wants_scatter and x and x.get("type") == "numeric":
        visual_form = "scatter-plot"
    elif x and x.get("type") in {"numeric", "datetime"}:
        visual_form = "line-chart"
    else:
        visual_form = "bar-chart"
    if visual_form == "line-chart" and categorical:
        group = categorical[0].get("name")
    elif visual_form == "bar-chart" and len(categorical) > 1:
        group = categorical[1].get("name")
    else:
        group = None
    error_candidates = [str(column.get("name")) for column in uncertainty] if wants_error else []
    return {
        "visual_form": visual_form,
        "x": x.get("name") if x else None,
        "y": y.get("name"),
        "value": None,
        "group": group,
        "error": error_candidates[0] if len(error_candidates) == 1 else None,
        "error_candidates": error_candidates,
        "error_requested": wants_error,
        "unit": infer_unit(str(y.get("name", "")), y.get("min"), y.get("max")),
    }


def data_panels(inventory: dict, brief: str, start_index: int = 0) -> tuple[list[dict], list[str]]:
    panels = []
    questions = []
    for offset, item in enumerate(data_files(inventory)):
        profile = item.get("table_profile", {})
        chart = choose_chart(profile.get("columns", []), brief)
        panel_id = chr(ord("A") + start_index + offset)
        if chart["visual_form"] == "heatmap" and chart["value"]:
            title = "Confusion matrix" if any(word in brief.lower() for word in ("confusion matrix", "混淆矩阵")) else f"{chart['value']} heatmap"
        elif chart["visual_form"] == "scatter-plot" and chart["x"] and chart["y"]:
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
            "value": chart.get("value"),
            "group": chart.get("group"),
            "error": chart.get("error"),
            "error_semantics": "symmetric-absolute" if chart.get("error") else None,
            "uncertainty": None,
            "calculation": chart.get("calculation"),
            "actual": chart.get("actual"),
            "predicted": chart.get("predicted"),
            "label": chart.get("label"),
            "score": chart.get("score"),
            "axis": {"x_scale": "linear", "y_scale": "linear"},
            "unit": chart["unit"],
            "transform": "none",
            "backend": "matplotlib",
        }
        panels.append(panel)
        if chart["visual_form"] in {"bar-chart", "line-chart", "scatter-plot", "box-plot", "violin-plot"} and not chart["y"]:
            questions.append(f"Choose a numeric metric for panel {panel_id} from {item.get('path')}.")
        if chart["visual_form"] in {"bar-chart", "line-chart", "scatter-plot", "heatmap", "box-plot", "violin-plot"} and not chart["x"]:
            questions.append(f"Choose an x-axis or grouping column for panel {panel_id} from {item.get('path')}.")
        if chart["visual_form"] in {"histogram", "density-plot"} and not chart.get("value"):
            questions.append(f"Choose a numeric sample column for panel {panel_id} from {item.get('path')}.")
        if chart["visual_form"] == "heatmap" and not chart.get("value"):
            questions.append(f"Choose the numeric heatmap value column for panel {panel_id} from {item.get('path')}.")
        if len(chart.get("error_candidates", [])) > 1:
            questions.append(
                f"Choose exactly one symmetric error column for panel {panel_id}: "
                + ", ".join(chart["error_candidates"]) + "."
            )
        if chart.get("error_requested") and not chart.get("error_candidates"):
            questions.append(
                f"Provide or choose one non-negative symmetric error column for panel {panel_id}; none was found."
            )
        if chart["visual_form"] in {"roc-curve", "pr-curve"}:
            questions.append(f"Set calculation.parameters.positive_label for panel {panel_id} before approval.")
        if chart["visual_form"] == "confusion-matrix" and (not chart.get("actual") or not chart.get("predicted")):
            questions.append(f"Choose actual and predicted columns for panel {panel_id} before approval.")
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
    title = re.sub(
        r"^(?:create|generate|make|draw)\s+(?:(?:an?|the)\s+)?", "", brief.strip(), flags=re.IGNORECASE
    )
    title = re.sub(r"^(?:生成|绘制|制作)(?:一张|一个)?", "", title).strip(" 。.")
    title = title[:72].strip() or "Scientific Concept Overview"
    subtitle = "Key concepts: " + " · ".join(entities[:4]) if entities else "Conceptual scientific illustration"
    footer = "Conceptual illustration — not quantitative evidence"
    visible_labels = [title, subtitle, footer]
    annotation_spec = {
        "mode": "deterministic-overlay",
        "allow_same_aspect_resize": True,
        "title": {"text": title, "position": [0.5, 0.055], "font_size": 28, "font_weight": 650},
        "subtitle": {"text": subtitle, "position": [0.5, 0.095], "font_size": 15, "font_weight": 500},
        "labels": [],
        "arrows": [],
        "legend": {},
        "footer": {"text": footer, "position": [0.5, 0.965], "font_size": 13, "font_weight": 400},
    }
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
        "title": title,
        "type": "raster-illustration",
        "source_files": [source.get("path")] if source else [],
        "visual_form": "generated-raster",
        "style": style,
        "evidence_role": "illustrative",
        "scientific_description": text[:1500],
        "entities": entities,
        "edges": edges,
        "visible_labels": visible_labels,
        "annotation_spec": annotation_spec,
        "annotation_requires_review": True,
        "forbidden_content": [
            "invented measurements or statistics",
            "unapproved labels",
            "watermarks",
            "presentation as microscopy, medical, field, or instrument evidence",
        ],
        "backend": "byok-openai-compatible-images plus deterministic raster annotation overlay",
        "canvas": {"width": 1024, "height": 1024},
        "human_review_required": True,
    }, questions


def hybrid_composite_panel(inventory: dict, brief: str, panel_id: str = "A") -> tuple[dict, list[str]]:
    lowered = brief.lower()
    roles = []
    if any(word in lowered for word in ("video frame", "视频帧")):
        roles.append({"role": "video-frame-raster", "kind": "raster", "svg_tag": "image", "min_count": 1})
    if any(word in lowered for word in ("heatmap", "热力图")):
        roles.append({"role": "attention-heatmap-raster", "kind": "raster", "svg_tag": "image", "min_count": 1})
    if any(word in lowered for word in ("transformer", "module", "模块", "架构")):
        roles.append({"role": "transformer-module", "kind": "vector", "svg_tag": "rect", "min_count": 1})
    if any(word in lowered for word in ("arrow", "箭头", "flow", "数据流")):
        roles.append({"role": "data-flow-arrow", "kind": "vector", "svg_tag": "path", "min_count": 1})
    if any(word in lowered for word in ("bar chart", "柱状图", "result", "结果图")):
        roles.extend([
            {"role": "result-bar", "kind": "vector", "svg_tag": "rect", "min_count": 1},
            {"role": "axis", "kind": "vector", "svg_tag": "line", "min_count": 2},
        ])
    contract = {"roles": roles, "unclassified_image_policy": "forbid", "exact_visible_labels": True}
    questions = [
        "Confirm exact visible labels and normalized layout before rendering the hybrid Figure.",
        "Set exact role counts and raster source_glob values in representation_contract before approval.",
    ]
    return {
        "id": panel_id,
        "title": "Hybrid scientific Figure",
        "type": "hybrid-composite",
        "source_files": [item.get("path") for item in inventory.get("files", [])],
        "visual_form": "hybrid-raster-vector-composite",
        "evidence_role": "review-required",
        "visible_labels": [],
        "annotation_spec": {"mode": "deterministic-overlay", "builder": "hybrid-composite"},
        "representation_contract": contract,
        "canvas": {"width": 2048, "height": 1280},
        "backend": "custom hybrid SVG compositor plus audit_hybrid_svg.py",
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
