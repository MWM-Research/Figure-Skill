from __future__ import annotations
import math
from typing import Any
from .common import STATS, calculation, finite_number

def plot_confusion(ax, fig, panel: dict, records: list[dict[str, Any]]) -> list[dict]:
    import numpy as np  # type: ignore
    config = calculation(panel, "confusion-count")
    if config["mode"] == "raw":
        actual_name, predicted_name = str(panel["actual"]), str(panel["predicted"])
        rows = [int(record["__source_row__"]) for record in records]
        derived = STATS.confusion_matrix(
            [str(record.get(actual_name, "")) for record in records],
            [str(record.get(predicted_name, "")) for record in records], rows,
            str(config["parameters"].get("normalization", "none")),
        )
        labels, matrix = derived["labels"], np.asarray(derived["matrix"], dtype=float)
        marks = []
        for y, actual in enumerate(labels):
            for x, predicted in enumerate(labels):
                marks.append({"x": predicted, "y": actual, "value": float(matrix[y, x]), "source_rows": derived["cell_source_rows"][y][x], "derived": derived})
    else:
        x_name, y_name, value_name = str(panel["x"]), str(panel["y"]), str(panel["value"])
        x_labels = list(dict.fromkeys(str(record.get(x_name, "")) for record in records))
        y_labels = list(dict.fromkeys(str(record.get(y_name, "")) for record in records))
        matrix = np.full((len(y_labels), len(x_labels)), np.nan)
        marks = []
        for record in records:
            row = int(record["__source_row__"]); x = str(record.get(x_name, "")); y = str(record.get(y_name, ""))
            if not math.isnan(matrix[y_labels.index(y), x_labels.index(x)]):
                raise ValueError(f"duplicate confusion coordinate {(x, y)}")
            value = finite_number(record.get(value_name), column=value_name, row=row)
            matrix[y_labels.index(y), x_labels.index(x)] = value
            marks.append({"source_row": row, "x": x, "y": y, "value": value})
        if np.isnan(matrix).any():
            raise ValueError("precomputed confusion matrix must be rectangular and complete")
        labels = x_labels
        if x_labels != y_labels:
            raise ValueError("precomputed confusion matrix must use the same ordered actual/predicted labels")
    mesh = ax.pcolormesh(np.arange(len(labels) + 1), np.arange(len(labels) + 1), matrix, cmap=str(panel.get("colormap") or "Blues"), edgecolors="#ffffff", linewidth=0.6, rasterized=False)
    ax.set_xticks(np.arange(len(labels)) + 0.5, labels, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(labels)) + 0.5, labels); ax.invert_yaxis(); ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
    colorbar = fig.colorbar(mesh, ax=ax, pad=0.025)
    if colorbar.solids is not None: colorbar.solids.set_rasterized(False)
    return marks


def plot_curve(ax, panel: dict, records: list[dict[str, Any]], *, curve: str) -> list[dict]:
    config = calculation(panel, curve)
    marks = []
    if config["mode"] == "raw":
        label_name, score_name = str(panel["label"]), str(panel["score"])
        positive_label = config["parameters"].get("positive_label")
        if positive_label is None:
            raise ValueError("raw ROC/PR requires positive_label")
        group_name = panel.get("group")
        grouped: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            grouped.setdefault(str(record.get(group_name, "All")) if group_name else "All", []).append(record)
        for group, items in grouped.items():
            rows = [int(item["__source_row__"]) for item in items]
            derived = STATS.binary_curve(
                [item.get(label_name) for item in items],
                [finite_number(item.get(score_name), column=score_name, row=int(item["__source_row__"])) for item in items],
                rows, positive_label, curve, bool(config["parameters"].get("compute_auc", False)),
            )
            label = group + (f" (AUC={derived['auc']:.3f})" if derived["auc"] is not None else "")
            ax.plot([point["x"] for point in derived["points"]], [point["y"] for point in derived["points"]], marker="o", markersize=3, label=label)
            marks.extend({"x": point["x"], "y": point["y"], "group": group, "source_rows": point["source_rows"], "threshold": point["threshold"], "derived": derived} for point in derived["points"])
        if group_name or bool(config["parameters"].get("compute_auc", False)): ax.legend(frameon=False)
    else:
        x_name, y_name, group_name = str(panel["x"]), str(panel["y"]), panel.get("group")
        grouped: dict[str, list[tuple[float, float, int]]] = {}
        for record in records:
            row = int(record["__source_row__"]); group = str(record.get(group_name, "All")) if group_name else "All"
            x = finite_number(record.get(x_name), column=x_name, row=row); y = finite_number(record.get(y_name), column=y_name, row=row)
            if not 0 <= x <= 1 or not 0 <= y <= 1: raise ValueError(f"ROC/PR points must lie in [0,1] at source row {row}")
            grouped.setdefault(group, []).append((x, y, row))
        for group, points in grouped.items():
            points.sort();
            if any(right[0] < left[0] for left, right in zip(points, points[1:])): raise ValueError("curve x values must be nondecreasing")
            ax.plot([point[0] for point in points], [point[1] for point in points], marker="o", label=group if group_name else None)
            marks.extend({"source_row": row, "x": x, "y": y, "group": group} for x, y, row in points)
        if group_name: ax.legend(frameon=False)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xlabel("False Positive Rate" if curve == "roc" else "Recall")
    ax.set_ylabel("True Positive Rate" if curve == "roc" else "Precision")
    ax.grid(color="#dddddd", linewidth=0.7)
    return marks
