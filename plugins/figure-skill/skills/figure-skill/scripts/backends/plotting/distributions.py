from __future__ import annotations
from typing import Any
from .common import STATS, calculation, finite_number, grouped_samples

def plot_box(ax, panel: dict, records: list[dict[str, Any]]) -> list[dict]:
    config = calculation(panel, "box-summary")
    labels, stats, marks = [], [], []
    if config["mode"] == "raw":
        grouped = grouped_samples(panel, records, str(panel["y"]))
        for label, (values, rows) in grouped.items():
            summary = STATS.box_summary(values, rows)
            labels.append(label)
            stats.append({
                "label": label, "q1": summary["q1"], "med": summary["median"], "q3": summary["q3"],
                "whislo": summary["whisker_low"], "whishi": summary["whisker_high"],
                "fliers": [item["value"] for item in summary["outliers"]],
            })
            marks.append({"group": label, "source_rows": rows, "derived": summary})
    else:
        x_name = str(panel["x"])
        fields = config["parameters"].get("columns", {
            "q1": "q1", "median": "median", "q3": "q3", "whisker_low": "whisker_low", "whisker_high": "whisker_high",
        })
        for record in records:
            row, label = int(record["__source_row__"]), str(record.get(x_name, ""))
            values = {key: finite_number(record.get(column), column=column, row=row) for key, column in fields.items()}
            if not values["whisker_low"] <= values["q1"] <= values["median"] <= values["q3"] <= values["whisker_high"]:
                raise ValueError(f"invalid precomputed box ordering at source row {row}")
            labels.append(label)
            stats.append({"label": label, "q1": values["q1"], "med": values["median"], "q3": values["q3"], "whislo": values["whisker_low"], "whishi": values["whisker_high"], "fliers": []})
            marks.append({"group": label, "source_row": row, "precomputed": {"columns": fields, "values": values}})
    ax.bxp(stats, showfliers=True, patch_artist=True, boxprops={"facecolor": "#b8c7d1", "edgecolor": "#222222"}, medianprops={"color": "#1d4ed8", "linewidth": 1.6})
    ax.set_xticks(range(1, len(labels) + 1), labels)
    ax.set_xlabel(str(panel.get("x") or panel.get("group") or "group"))
    ax.set_ylabel(str(panel["y"]))
    ax.grid(axis="y", color="#dddddd", linewidth=0.7)
    return marks


def plot_density_or_violin(ax, panel: dict, records: list[dict[str, Any]], *, violin: bool) -> list[dict]:
    config = calculation(panel, "kde")
    marks = []
    if config["mode"] == "raw":
        value_name = str(panel.get("value") or panel.get("y"))
        grouped = grouped_samples(panel, records, value_name)
        bandwidth = config["parameters"].get("bandwidth")
        if bandwidth is None:
            raise ValueError("raw KDE requires an explicit bandwidth: 'scott' or a positive number")
        for index, (label, (values, rows)) in enumerate(grouped.items(), start=1):
            derived = STATS.kde(values, rows, bandwidth=bandwidth)
            grid, density = derived["grid"], derived["density"]
            if violin:
                maximum = max(density) or 1.0
                scaled = [value / maximum * 0.38 for value in density]
                ax.fill_betweenx(grid, [index - value for value in scaled], [index + value for value in scaled], alpha=0.65, color="#7b9e87", edgecolor="#222222")
            else:
                ax.plot(grid, density, linewidth=1.6, label=label)
            marks.append({"group": label, "source_rows": rows, "derived": derived})
        if violin:
            ax.set_xticks(range(1, len(grouped) + 1), list(grouped))
            ax.set_ylabel(value_name)
        else:
            ax.set_xlabel(value_name)
            ax.set_ylabel("density")
            if len(grouped) > 1:
                ax.legend(frameon=False, title=str(panel.get("group") or panel.get("x") or "group"))
    else:
        x_name, y_name = str(panel["x"]), str(panel["y"])
        density_name = str(panel.get("value") or config["parameters"].get("density_column") or "density")
        group_name = panel.get("group")
        grouped_rows: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            grouped_rows.setdefault(str(record.get(group_name, "All")) if group_name else "All", []).append(record)
        for index, (label, items) in enumerate(grouped_rows.items(), start=1):
            points = sorted((finite_number(item.get(x_name), column=x_name, row=int(item["__source_row__"])), finite_number(item.get(density_name), column=density_name, row=int(item["__source_row__"])), int(item["__source_row__"])) for item in items)
            grid, density = [item[0] for item in points], [item[1] for item in points]
            if violin:
                maximum = max(density) or 1.0
                scaled = [value / maximum * 0.38 for value in density]
                ax.fill_betweenx(grid, [index - value for value in scaled], [index + value for value in scaled], alpha=0.65, color="#7b9e87", edgecolor="#222222")
            else:
                ax.plot(grid, density, label=label)
            marks.extend({"source_row": row, "x": x_value, "y": density_value, "group": label} for x_value, density_value, row in points)
        if violin:
            ax.set_xticks(range(1, len(grouped_rows) + 1), list(grouped_rows))
            ax.set_ylabel(y_name)
        elif len(grouped_rows) > 1:
            ax.legend(frameon=False)
    ax.grid(color="#dddddd", linewidth=0.7)
    return marks


def plot_histogram(ax, panel: dict, records: list[dict[str, Any]]) -> list[dict]:
    config = calculation(panel, "histogram")
    marks = []
    if config["mode"] == "raw":
        value_name = str(panel.get("value") or panel.get("x"))
        grouped = grouped_samples(panel, records, value_name)
        for label, (values, rows) in grouped.items():
            derived = STATS.histogram(values, rows, config["parameters"])
            edges, counts = derived["edges"], derived["counts"]
            ax.stairs(counts, edges, fill=len(grouped) == 1, alpha=0.45, linewidth=1.5, label=label)
            marks.append({"group": label, "source_rows": rows, "derived": derived})
        if len(grouped) > 1:
            ax.legend(frameon=False)
        ax.set_xlabel(value_name)
        ax.set_ylabel("density" if config["parameters"].get("density") else "count")
    else:
        left_name, right_name, height_name = str(panel["x"]), str(panel.get("x2") or "bin_right"), str(panel["y"])
        for record in records:
            row = int(record["__source_row__"])
            left = finite_number(record.get(left_name), column=left_name, row=row)
            right = finite_number(record.get(right_name), column=right_name, row=row)
            height = finite_number(record.get(height_name), column=height_name, row=row)
            if right <= left:
                raise ValueError(f"histogram bin right must exceed left at source row {row}")
            ax.bar((left + right) / 2, height, width=right - left, align="center", color="#8da9b8", edgecolor="#222222")
            marks.append({"source_row": row, "x": left, "x2": right, "y": height})
        ax.set_xlabel(left_name)
        ax.set_ylabel(height_name)
    ax.grid(axis="y", color="#dddddd", linewidth=0.7)
    return marks
