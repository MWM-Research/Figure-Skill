from __future__ import annotations
import math
from typing import Any
from .common import finite_number, record_uncertainty, uncertainty_config

def plot_bar(ax, panel: dict, records: list[dict[str, Any]]) -> list[dict]:
    x_name, y_name = panel["x"], panel["y"]
    group_name = panel.get("group")
    labels = [str(record.get(x_name, "")) for record in records]
    if not labels or any(not label for label in labels):
        raise ValueError(f"panel {panel['id']} contains an empty {x_name!r} category")
    if not group_name and len(set(labels)) != len(labels):
        raise ValueError(f"panel {panel['id']} has duplicate {x_name!r} categories; define an aggregation before plotting")
    values = [finite_number(record.get(y_name), column=y_name, row=int(record["__source_row__"])) for record in records]
    uncertainties = [record_uncertainty(record, panel, value) for record, value in zip(records, values)]
    marks = []
    if group_name:
        groups = [str(record.get(group_name, "")) for record in records]
        if any(not group for group in groups):
            raise ValueError(f"panel {panel['id']} contains an empty {group_name!r} group")
        pairs = list(zip(labels, groups))
        if len(set(pairs)) != len(pairs):
            raise ValueError(f"panel {panel['id']} has duplicate ({x_name}, {group_name}) pairs; define an aggregation")
        x_labels = list(dict.fromkeys(labels))
        group_labels = list(dict.fromkeys(groups))
        lookup = {pair: (value, uncertainty, record) for pair, value, uncertainty, record in zip(pairs, values, uncertainties, records)}
        width = 0.8 / len(group_labels)
        palette = ["#b8b8b8", "#3f6f8f", "#7f7f7f", "#7b9e87", "#8b6f8f"]
        for group_index, group in enumerate(group_labels):
            positions = [index - 0.4 + width / 2 + group_index * width for index in range(len(x_labels))]
            group_values = [lookup.get((label, group), (math.nan, None, None))[0] for label in x_labels]
            group_uncertainties = [lookup.get((label, group), (math.nan, None, None))[1] for label in x_labels]
            group_errors = [
                [item["lower"] if item else math.nan for item in group_uncertainties],
                [item["upper"] if item else math.nan for item in group_uncertainties],
            ]
            bars = ax.bar(
                positions, group_values, width=width, label=group,
                color=palette[group_index % len(palette)], edgecolor="#222222", linewidth=0.8,
                yerr=group_errors if uncertainty_config(panel) else None,
                capsize=3 if uncertainty_config(panel) else 0,
            )
            for bar, label, value, uncertainty in zip(bars, x_labels, group_values, group_uncertainties):
                if not math.isnan(value):
                    ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:g}", ha="center", va="bottom", fontsize=7.5)
                    record = lookup[(label, group)][2]
                    mark = {"source_row": int(record["__source_row__"]), "x": label, "group": group, "y": value}
                    if uncertainty is not None:
                        mark["uncertainty"] = uncertainty
                    marks.append(mark)
        ax.set_xticks(range(len(x_labels)), x_labels)
        ax.legend(title=group_name, frameon=False)
    else:
        colors = ["#b8b8b8"] * len(values)
        if colors:
            colors[-1] = "#3f6f8f"
        bars = ax.bar(
            labels, values, width=0.62, color=colors, edgecolor="#222222", linewidth=0.9,
            yerr=[
                [item["lower"] if item else 0.0 for item in uncertainties],
                [item["upper"] if item else 0.0 for item in uncertainties],
            ] if uncertainty_config(panel) else None,
            capsize=3 if uncertainty_config(panel) else 0,
        )
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:g}", ha="center", va="bottom", fontsize=8.5)
        marks = []
        for record, label, value, uncertainty in zip(records, labels, values, uncertainties):
            mark = {"source_row": int(record["__source_row__"]), "x": label, "y": value}
            if uncertainty is not None:
                mark["uncertainty"] = uncertainty
            marks.append(mark)
    lower_values = [value - (item["lower"] if item else 0.0) for value, item in zip(values, uncertainties)]
    upper_values = [value + (item["upper"] if item else 0.0) for value, item in zip(values, uncertainties)]
    lower = min(0.0, min(lower_values) * 1.16)
    upper = max(0.0, max(upper_values) * 1.16)
    if lower == upper:
        upper = lower + 1.0
    ax.set_ylim(lower, upper)
    ax.set_xlabel(x_name)
    ax.set_ylabel(y_name if not panel.get("unit") else f"{y_name} ({panel['unit']})")
    ax.grid(axis="y", color="#dddddd", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    return marks


def plot_xy(ax, panel: dict, records: list[dict[str, Any]], *, scatter: bool) -> list[dict]:
    x_name, y_name = panel["x"], panel["y"]
    group_name = panel.get("group")
    grouped: dict[str, list[tuple[float, float, dict[str, Any] | None, int]]] = {}
    for record in records:
        row = int(record["__source_row__"])
        x_value = finite_number(record.get(x_name), column=x_name, row=row)
        y_value = finite_number(record.get(y_name), column=y_name, row=row)
        uncertainty = record_uncertainty(record, panel, y_value)
        group = str(record.get(group_name, "")) if group_name else ""
        if group_name and not group:
            raise ValueError(f"panel {panel['id']} contains an empty {group_name!r} group")
        grouped.setdefault(group, []).append((x_value, y_value, uncertainty, row))
    palette = ["#3f6f8f", "#7b9e87", "#8b6f8f", "#c17c4f", "#6b7280"]
    marks = []
    for group_index, (group, points) in enumerate(grouped.items()):
        points.sort(key=lambda point: point[0])
        xs = [point[0] for point in points]
        if len(set(xs)) != len(xs):
            scope = f" within group {group!r}" if group_name else ""
            raise ValueError(f"panel {panel['id']} has duplicate {x_name!r} values{scope}; define an aggregation")
        ys = [point[1] for point in points]
        uncertainties = [point[2] for point in points]
        color = palette[group_index % len(palette)]
        if uncertainty_config(panel):
            ax.errorbar(
                xs, ys, yerr=[
                    [item["lower"] if item else 0.0 for item in uncertainties],
                    [item["upper"] if item else 0.0 for item in uncertainties],
                ], fmt="o",
                linestyle="none" if scatter else "-", color=color, ecolor=color,
                linewidth=1.6, markersize=4.5, capsize=3, label=group if group_name else None,
            )
        elif scatter:
            ax.scatter(xs, ys, s=34, color=color, edgecolor="#222222", linewidth=0.6, label=group if group_name else None)
        else:
            ax.plot(xs, ys, marker="o", color=color, linewidth=1.6, markersize=4.5, label=group if group_name else None)
        for x_value, y_value, uncertainty, row in points:
            mark = {"source_row": row, "x": x_value, "y": y_value}
            if group_name:
                mark["group"] = group
            if uncertainty is not None:
                mark["uncertainty"] = uncertainty
            marks.append(mark)
    ax.set_xlabel(x_name)
    ax.set_ylabel(y_name if not panel.get("unit") else f"{y_name} ({panel['unit']})")
    ax.grid(color="#dddddd", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    if group_name:
        ax.legend(title=group_name, frameon=False)
    return marks


def plot_heatmap(ax, fig, panel: dict, records: list[dict[str, Any]]) -> list[dict]:
    import numpy as np  # type: ignore

    x_name, y_name, value_name = panel["x"], panel["y"], panel["value"]
    x_labels = list(dict.fromkeys(str(record.get(x_name, "")) for record in records))
    y_labels = list(dict.fromkeys(str(record.get(y_name, "")) for record in records))
    if not x_labels or not y_labels or any(not label for label in x_labels + y_labels):
        raise ValueError(f"panel {panel['id']} contains an empty heatmap coordinate")
    x_index = {label: index for index, label in enumerate(x_labels)}
    y_index = {label: index for index, label in enumerate(y_labels)}
    matrix = np.full((len(y_labels), len(x_labels)), np.nan, dtype=float)
    seen: set[tuple[str, str]] = set()
    marks = []
    for record in records:
        row = int(record["__source_row__"])
        x_label = str(record.get(x_name, ""))
        y_label = str(record.get(y_name, ""))
        coordinate = (x_label, y_label)
        if coordinate in seen:
            raise ValueError(f"panel {panel['id']} has duplicate heatmap coordinate {coordinate}; define an aggregation")
        seen.add(coordinate)
        value = finite_number(record.get(value_name), column=value_name, row=row)
        matrix[y_index[y_label], x_index[x_label]] = value
        marks.append({"source_row": row, "x": x_label, "y": y_label, "value": value})
    missing = int(np.isnan(matrix).sum())
    if missing:
        raise ValueError(f"panel {panel['id']} heatmap grid is incomplete: {missing} coordinate(s) missing")
    mesh = ax.pcolormesh(
        np.arange(len(x_labels) + 1), np.arange(len(y_labels) + 1), matrix,
        cmap=str(panel.get("colormap") or "viridis"), shading="flat",
        edgecolors="#FFFFFF", linewidth=0.6, rasterized=False,
    )
    ax.set_xticks(np.arange(len(x_labels)) + 0.5, x_labels)
    ax.set_yticks(np.arange(len(y_labels)) + 0.5, y_labels)
    ax.invert_yaxis()
    ax.set_xlabel(x_name)
    ax.set_ylabel(y_name)
    colorbar = fig.colorbar(mesh, ax=ax, pad=0.025)
    if colorbar.solids is not None:
        colorbar.solids.set_rasterized(False)
    colorbar.set_label(value_name if not panel.get("unit") else f"{value_name} ({panel['unit']})")
    if panel.get("annotate_values", len(marks) <= 64):
        threshold = (float(matrix.min()) + float(matrix.max())) / 2
        for mark in marks:
            ax.text(
                x_index[mark["x"]] + 0.5, y_index[mark["y"]] + 0.5, f"{mark['value']:g}",
                ha="center", va="center", fontsize=7.5,
                color="#FFFFFF" if mark["value"] > threshold else "#111827",
            )
    return marks
