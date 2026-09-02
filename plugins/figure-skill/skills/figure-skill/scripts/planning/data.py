from __future__ import annotations
import re
from typing import Any
from .routes import ADVANCED_FORMS, ERROR_WORDS, HEATMAP_VALUE_WORDS, HEATMAP_WORDS, HEATMAP_X_WORDS, HEATMAP_Y_WORDS, LINE_WORDS, METRIC_PRIORITY, UNCERTAINTY_COLUMN_WORDS, data_files

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
