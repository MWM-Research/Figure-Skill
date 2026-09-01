#!/usr/bin/env python3
"""Deterministic statistical transforms used by Figure Skill data plots."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


FORMULA_VERSION = "figure-statistics-1.0"


def finite(value: Any, *, name: str = "value") -> float:
    try:
        number = float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is not numeric: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} is not finite: {value!r}")
    return number


def box_summary(values: list[float], source_rows: list[int]) -> dict[str, Any]:
    if not values or len(values) != len(source_rows):
        raise ValueError("box summary requires matching non-empty values and source rows")
    data = np.asarray(values, dtype=float)
    q1, median, q3 = np.percentile(data, [25, 50, 75], method="linear")
    iqr = float(q3 - q1)
    low_fence, high_fence = float(q1 - 1.5 * iqr), float(q3 + 1.5 * iqr)
    inliers = data[(data >= low_fence) & (data <= high_fence)]
    whisker_low, whisker_high = float(inliers.min()), float(inliers.max())
    outliers = [
        {"value": float(value), "source_row": int(row)}
        for value, row in zip(values, source_rows)
        if value < whisker_low or value > whisker_high
    ]
    return {
        "operation": "box-summary",
        "formula_version": FORMULA_VERSION,
        "parameters": {"percentile_method": "linear", "whisker_iqr": 1.5},
        "source_rows": [int(row) for row in source_rows],
        "q1": float(q1), "median": float(median), "q3": float(q3),
        "whisker_low": whisker_low, "whisker_high": whisker_high,
        "outliers": outliers,
    }


def kde(values: list[float], source_rows: list[int], bandwidth: str | float = "scott", points: int = 128) -> dict[str, Any]:
    if len(values) < 2 or len(values) != len(source_rows):
        raise ValueError("KDE requires at least two values with matching source rows")
    if points != 128:
        raise ValueError("Figure Skill KDE uses exactly 128 grid points")
    data = np.asarray(values, dtype=float)
    std = float(np.std(data, ddof=1))
    if isinstance(bandwidth, str):
        if bandwidth != "scott":
            raise ValueError("bandwidth must be 'scott' or a positive number")
        width = std * len(values) ** (-1 / 5)
    else:
        width = float(bandwidth)
    if not math.isfinite(width) or width <= 0:
        raise ValueError("KDE bandwidth must be positive; constant data requires an explicit bandwidth")
    margin = 3 * width
    grid = np.linspace(float(data.min() - margin), float(data.max() + margin), points)
    scaled = (grid[:, None] - data[None, :]) / width
    density = np.exp(-0.5 * scaled * scaled).sum(axis=1) / (len(values) * width * math.sqrt(2 * math.pi))
    return {
        "operation": "kde",
        "formula_version": FORMULA_VERSION,
        "parameters": {"bandwidth": bandwidth, "resolved_bandwidth": width, "grid_points": points},
        "source_rows": [int(row) for row in source_rows],
        "grid": grid.tolist(), "density": density.tolist(),
    }


def histogram(values: list[float], source_rows: list[int], parameters: dict[str, Any]) -> dict[str, Any]:
    if not values or len(values) != len(source_rows):
        raise ValueError("histogram requires matching non-empty values and source rows")
    strategy = parameters.get("strategy")
    if strategy not in {"fd", "sturges", "count", "edges"}:
        raise ValueError("histogram strategy must be fd, sturges, count, or edges")
    if strategy == "count":
        count = parameters.get("count")
        if not isinstance(count, int) or count < 1:
            raise ValueError("histogram count strategy requires a positive integer count")
        bins: Any = count
    elif strategy == "edges":
        edges = parameters.get("edges")
        if not isinstance(edges, list) or len(edges) < 2:
            raise ValueError("histogram edges strategy requires at least two edges")
        bins = [finite(value, name="histogram edge") for value in edges]
        if any(right <= left for left, right in zip(bins, bins[1:])):
            raise ValueError("histogram edges must be strictly increasing")
    else:
        bins = strategy
    density = bool(parameters.get("density", False))
    counts, edges = np.histogram(np.asarray(values, dtype=float), bins=bins, density=density)
    memberships = []
    for index, (left, right) in enumerate(zip(edges[:-1], edges[1:])):
        rows = [
            int(row) for value, row in zip(values, source_rows)
            if ((left <= value <= right) if index == len(edges) - 2 else (left <= value < right))
        ]
        memberships.append(rows)
    return {
        "operation": "histogram",
        "formula_version": FORMULA_VERSION,
        "parameters": {**parameters, "strategy": strategy, "density": density},
        "source_rows": [int(row) for row in source_rows],
        "edges": edges.tolist(), "counts": counts.tolist(), "bin_source_rows": memberships,
    }


def confusion_matrix(
    actual: list[str], predicted: list[str], source_rows: list[int], normalization: str,
) -> dict[str, Any]:
    if not actual or len(actual) != len(predicted) or len(actual) != len(source_rows):
        raise ValueError("confusion matrix requires matching non-empty actual, predicted, and source rows")
    if normalization not in {"none", "true", "pred", "all"}:
        raise ValueError("confusion normalization must be none, true, pred, or all")
    labels = list(dict.fromkeys(actual + predicted))
    index = {label: position for position, label in enumerate(labels)}
    matrix = np.zeros((len(labels), len(labels)), dtype=float)
    cell_rows = [[[] for _ in labels] for _ in labels]
    for truth, guess, row in zip(actual, predicted, source_rows):
        y, x = index[truth], index[guess]
        matrix[y, x] += 1
        cell_rows[y][x].append(int(row))
    raw = matrix.copy()
    if normalization == "true":
        denominators = matrix.sum(axis=1, keepdims=True)
        matrix = np.divide(matrix, denominators, out=np.zeros_like(matrix), where=denominators != 0)
    elif normalization == "pred":
        denominators = matrix.sum(axis=0, keepdims=True)
        matrix = np.divide(matrix, denominators, out=np.zeros_like(matrix), where=denominators != 0)
    elif normalization == "all":
        matrix = matrix / matrix.sum()
    return {
        "operation": "confusion-count",
        "formula_version": FORMULA_VERSION,
        "parameters": {"normalization": normalization},
        "source_rows": [int(row) for row in source_rows],
        "labels": labels, "raw_counts": raw.tolist(), "matrix": matrix.tolist(), "cell_source_rows": cell_rows,
    }


def binary_curve(
    labels: list[Any], scores: list[float], source_rows: list[int], positive_label: Any,
    curve: str, compute_auc: bool = False,
) -> dict[str, Any]:
    if curve not in {"roc", "pr"}:
        raise ValueError("curve must be roc or pr")
    if not labels or len(labels) != len(scores) or len(labels) != len(source_rows):
        raise ValueError("binary curve requires matching non-empty labels, scores, and source rows")
    positives = [label == positive_label for label in labels]
    positive_count = sum(positives)
    negative_count = len(labels) - positive_count
    if positive_count == 0 or negative_count == 0:
        raise ValueError("binary curve requires both positive and negative samples")
    ordered = sorted(
        zip(scores, positives, source_rows), key=lambda item: -item[0]
    )
    tp = fp = 0
    points: list[dict[str, Any]] = []
    if curve == "roc":
        points.append({"x": 0.0, "y": 0.0, "threshold": None, "source_rows": []})
    else:
        points.append({"x": 0.0, "y": 1.0, "threshold": None, "source_rows": []})
    consumed: list[int] = []
    cursor = 0
    while cursor < len(ordered):
        threshold = ordered[cursor][0]
        tied = []
        while cursor < len(ordered) and ordered[cursor][0] == threshold:
            tied.append(ordered[cursor])
            cursor += 1
        for _, is_positive, row in tied:
            consumed.append(int(row))
            if is_positive:
                tp += 1
            else:
                fp += 1
        if curve == "roc":
            x, y = fp / negative_count, tp / positive_count
        else:
            x, y = tp / positive_count, tp / (tp + fp)
        points.append({"x": x, "y": y, "threshold": threshold, "source_rows": list(consumed)})
    xs = np.asarray([point["x"] for point in points], dtype=float)
    ys = np.asarray([point["y"] for point in points], dtype=float)
    auc = float(np.trapezoid(ys, xs)) if compute_auc else None
    return {
        "operation": curve,
        "formula_version": FORMULA_VERSION,
        "parameters": {"positive_label": positive_label, "compute_auc": bool(compute_auc), "tie_policy": "group-equal-scores"},
        "source_rows": [int(row) for row in source_rows],
        "points": points, "auc": auc,
    }
