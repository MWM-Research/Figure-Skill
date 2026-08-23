#!/usr/bin/env python3
"""Render evidence-linked data panels from a scientific figure plan."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any, Iterable


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError as exc:
        raise SystemExit("matplotlib is required; install the dependencies listed in this Skill's requirements.txt") from exc
    return plt


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_records(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            return [dict(row, __source_row__=index) for index, row in enumerate(csv.DictReader(handle, delimiter=delimiter), start=2)]
    if suffix == ".jsonl":
        records = []
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for index, line in enumerate(handle, start=1):
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError(f"JSONL line {index} is not an object")
                    records.append(dict(value, __source_row__=index))
        return records
    if suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(value, dict):
            value = next((value[key] for key in ("records", "data", "results", "metrics", "items") if isinstance(value.get(key), list)), [value])
        if not isinstance(value, list):
            raise ValueError("JSON input must be an object or a list of objects")
        return [dict(item, __source_row__=index) for index, item in enumerate(value, start=1) if isinstance(item, dict)]
    if suffix == ".xlsx":
        try:
            from openpyxl import load_workbook  # type: ignore
        except ImportError as exc:
            raise RuntimeError("openpyxl is required to render .xlsx data") from exc
        workbook = load_workbook(path, read_only=True, data_only=True)
        sheet = workbook[workbook.sheetnames[0]]
        iterator = sheet.iter_rows(values_only=True)
        headers = [str(value) if value is not None else f"column_{index + 1}" for index, value in enumerate(next(iterator, []))]
        try:
            return [dict(zip(headers, values), __source_row__=index) for index, values in enumerate(iterator, start=2)]
        finally:
            workbook.close()
    raise ValueError(f"unsupported data format: {path.suffix}")


def finite_number(value: Any, *, column: str, row: int) -> float:
    try:
        number = float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"non-numeric value in column {column!r}, source row {row}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"non-finite value in column {column!r}, source row {row}: {value!r}")
    return number


def panel_records(panel: dict, input_root: Path) -> tuple[Path, list[dict[str, Any]]]:
    sources = panel.get("source_files") or []
    if len(sources) != 1:
        raise ValueError(f"panel {panel.get('id')} must reference exactly one data source")
    source = (input_root / sources[0]).resolve()
    try:
        source.relative_to(input_root.resolve())
    except ValueError as exc:
        raise ValueError(f"source escapes input root: {sources[0]}") from exc
    if not source.is_file():
        raise FileNotFoundError(f"data source not found: {source}")
    return source, read_records(source)


def plot_bar(ax, panel: dict, records: list[dict[str, Any]]) -> list[dict]:
    x_name, y_name = panel["x"], panel["y"]
    group_name = panel.get("group")
    labels = [str(record.get(x_name, "")) for record in records]
    if not labels or any(not label for label in labels):
        raise ValueError(f"panel {panel['id']} contains an empty {x_name!r} category")
    if not group_name and len(set(labels)) != len(labels):
        raise ValueError(f"panel {panel['id']} has duplicate {x_name!r} categories; define an aggregation before plotting")
    values = [finite_number(record.get(y_name), column=y_name, row=int(record["__source_row__"])) for record in records]
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
        lookup = {pair: (value, record) for pair, value, record in zip(pairs, values, records)}
        width = 0.8 / len(group_labels)
        palette = ["#b8b8b8", "#3f6f8f", "#7f7f7f", "#7b9e87", "#8b6f8f"]
        for group_index, group in enumerate(group_labels):
            positions = [index - 0.4 + width / 2 + group_index * width for index in range(len(x_labels))]
            group_values = [lookup.get((label, group), (math.nan, None))[0] for label in x_labels]
            bars = ax.bar(
                positions, group_values, width=width, label=group,
                color=palette[group_index % len(palette)], edgecolor="#222222", linewidth=0.8,
            )
            for bar, label, value in zip(bars, x_labels, group_values):
                if not math.isnan(value):
                    ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:g}", ha="center", va="bottom", fontsize=7.5)
                    record = lookup[(label, group)][1]
                    marks.append({"source_row": int(record["__source_row__"]), "x": label, "group": group, "y": value})
        ax.set_xticks(range(len(x_labels)), x_labels)
        ax.legend(title=group_name, frameon=False)
    else:
        colors = ["#b8b8b8"] * len(values)
        if colors:
            colors[-1] = "#3f6f8f"
        bars = ax.bar(labels, values, width=0.62, color=colors, edgecolor="#222222", linewidth=0.9)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:g}", ha="center", va="bottom", fontsize=8.5)
        marks = [{"source_row": int(record["__source_row__"]), "x": label, "y": value} for record, label, value in zip(records, labels, values)]
    lower = min(0.0, min(values) * 1.16)
    upper = max(0.0, max(values) * 1.16)
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
    points = []
    for record in records:
        row = int(record["__source_row__"])
        x_value = finite_number(record.get(x_name), column=x_name, row=row)
        y_value = finite_number(record.get(y_name), column=y_name, row=row)
        points.append((x_value, y_value, row))
    points.sort(key=lambda point: point[0])
    xs, ys = [point[0] for point in points], [point[1] for point in points]
    if scatter:
        ax.scatter(xs, ys, s=34, color="#3f6f8f", edgecolor="#222222", linewidth=0.6)
    else:
        ax.plot(xs, ys, marker="o", color="#3f6f8f", linewidth=1.6, markersize=4.5)
    ax.set_xlabel(x_name)
    ax.set_ylabel(y_name if not panel.get("unit") else f"{y_name} ({panel['unit']})")
    ax.grid(color="#dddddd", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    return [{"source_row": row, "x": x, "y": y} for x, y, row in points]


def render_panel(panel: dict, input_root: Path, output_dir: Path, formats: Iterable[str]) -> dict:
    plt = require_matplotlib()
    source, records = panel_records(panel, input_root)
    if not records:
        raise ValueError(f"panel {panel.get('id')} data source is empty")
    if not panel.get("x") or not panel.get("y"):
        raise ValueError(f"panel {panel.get('id')} requires both x and y columns")
    visual_form = panel.get("visual_form")
    fig, ax = plt.subplots(figsize=(5.4, 3.7))
    try:
        if visual_form == "bar-chart":
            marks = plot_bar(ax, panel, records)
        elif visual_form == "line-chart":
            marks = plot_xy(ax, panel, records, scatter=False)
        elif visual_form == "scatter-plot":
            marks = plot_xy(ax, panel, records, scatter=True)
        else:
            raise ValueError(f"unsupported visual form: {visual_form}")
        ax.set_title(str(panel.get("title") or panel.get("id")), loc="left", fontsize=11, fontweight="bold", pad=10)
        fig.tight_layout()
        stem = f"panel_{str(panel['id']).lower()}"
        outputs = {}
        for fmt in formats:
            target = output_dir / f"{stem}.{fmt}"
            kwargs = {"dpi": 220} if fmt == "png" else {}
            fig.savefig(target, bbox_inches="tight", **kwargs)
            outputs[fmt] = target.name
    finally:
        plt.close(fig)

    provenance_marks = []
    for mark in marks:
        provenance_marks.append({
            "source_row": mark["source_row"],
            "x": {"column": panel["x"], "value": mark["x"]},
            "y": {"column": panel["y"], "value": mark["y"], "unit": panel.get("unit")},
            "transform": panel.get("transform", "none"),
        })
        if "group" in mark:
            provenance_marks[-1]["group"] = {"column": panel.get("group"), "value": mark["group"]}
    return {
        "panel": panel["id"],
        "visual_form": visual_form,
        "source_file": str(source),
        "source_sha256": sha256(source),
        "outputs": outputs,
        "marks": provenance_marks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--panel", action="append", help="Render only the selected panel id; may be repeated")
    parser.add_argument("--formats", default="svg,pdf,png")
    parser.add_argument("--allow-open-questions", action="store_true")
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if plan.get("open_questions") and not args.allow_open_questions:
        raise SystemExit("figure plan has unresolved open_questions; resolve them or pass --allow-open-questions for a draft")
    input_root = (args.input_root or Path(plan.get("input_root") or ".")).resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    formats = tuple(item.strip().lower() for item in args.formats.split(",") if item.strip())
    unsupported = set(formats) - {"svg", "pdf", "png"}
    if unsupported:
        parser.error(f"unsupported formats: {', '.join(sorted(unsupported))}")

    selected = set(args.panel or [])
    panels = [panel for panel in plan.get("panels", []) if panel.get("type") == "data-plot" and (not selected or str(panel.get("id")) in selected)]
    if not panels:
        raise SystemExit("no matching data-plot panels found in the plan")

    plt = require_matplotlib()
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.linewidth": 0.9,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    })
    rendered = [render_panel(panel, input_root, output_dir, formats) for panel in panels]
    provenance = {"schema_version": "1.0", "plan": str(args.plan.resolve()), "panels": rendered}
    provenance_path = output_dir / "provenance.json"
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    for panel in panels:
        target_source = output_dir / f"panel_{str(panel['id']).lower()}_source.py"
        if Path(__file__).resolve() != target_source.resolve():
            shutil.copy2(Path(__file__), target_source)
    recipe = {
        "command": "python panel_<id>_source.py <figure-plan.json> --output-dir <output-dir>",
        "input_root": str(input_root),
        "formats": list(formats),
    }
    (output_dir / "render-recipe.json").write_text(json.dumps(recipe, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Rendered {len(rendered)} data panel(s) -> {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
