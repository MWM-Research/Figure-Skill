from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
from typing import Any, Iterable
from .axes import apply_axis_config
from .basic import plot_bar, plot_heatmap, plot_xy
from .classification import plot_confusion, plot_curve
from .common import STATS, configure_matplotlib, require_matplotlib
from .distributions import plot_box, plot_density_or_violin, plot_histogram
from .io import panel_records, sha256
from .provenance import provenance_marks

def render_to_axis(ax, fig, panel: dict, records: list[dict[str, Any]]) -> list[dict]:
    visual_form = panel.get("visual_form")
    if visual_form == "bar-chart": return plot_bar(ax, panel, records)
    if visual_form == "line-chart": return plot_xy(ax, panel, records, scatter=False)
    if visual_form == "scatter-plot": return plot_xy(ax, panel, records, scatter=True)
    if visual_form == "heatmap": return plot_heatmap(ax, fig, panel, records)
    if visual_form == "box-plot": return plot_box(ax, panel, records)
    if visual_form == "violin-plot": return plot_density_or_violin(ax, panel, records, violin=True)
    if visual_form == "histogram": return plot_histogram(ax, panel, records)
    if visual_form == "density-plot": return plot_density_or_violin(ax, panel, records, violin=False)
    if visual_form == "confusion-matrix": return plot_confusion(ax, fig, panel, records)
    if visual_form == "roc-curve": return plot_curve(ax, panel, records, curve="roc")
    if visual_form == "pr-curve": return plot_curve(ax, panel, records, curve="pr")
    raise ValueError(f"unsupported visual form: {visual_form}")

def render_panel(panel: dict, input_root: Path, output_dir: Path, formats: Iterable[str]) -> dict:
    plt = require_matplotlib()
    configure_matplotlib(plt)
    source, records = panel_records(panel, input_root)
    if not records:
        raise ValueError(f"panel {panel.get('id')} data source is empty")
    visual_form = panel.get("visual_form")
    axis_break = (panel.get("axis") or {}).get("break")
    if axis_break:
        fig, raw_axes = plt.subplots(2, 1, figsize=(5.4, 4.8), sharex=True, gridspec_kw={"height_ratios": [1, 1], "hspace": 0.08})
        axes = list(raw_axes)
    else:
        fig, ax = plt.subplots(figsize=(6.0, 4.4) if visual_form in {"heatmap", "confusion-matrix"} else (5.4, 3.7))
        axes = [ax]
    try:
        marks = render_to_axis(axes[0], fig, panel, records)
        for extra in axes[1:]: render_to_axis(extra, fig, panel, records)
        apply_axis_config(axes, panel, marks)
        axes[0].set_title(str(panel.get("title") or panel.get("id")), loc="left", fontsize=11, fontweight="bold", pad=10)
        if axis_break:
            fig.subplots_adjust(left=0.14, right=0.97, top=0.91, bottom=0.12, hspace=0.08)
        else:
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

    return {
        "panel": panel["id"],
        "visual_form": visual_form,
        "source_file": str(source),
        "source_sha256": sha256(source),
        "outputs": outputs,
        "marks": provenance_marks(panel, marks),
        "calculation": panel.get("calculation"), "axis": panel.get("axis"), "uncertainty": panel.get("uncertainty"),
    }


def render_grid_panel(panel: dict, input_root: Path, output_dir: Path, formats: Iterable[str]) -> dict:
    plt = require_matplotlib()
    configure_matplotlib(plt)
    subplots = panel.get("subplots") or []
    layout = panel.get("layout") or {}
    rows, columns = layout.get("rows"), layout.get("columns")
    if not isinstance(rows, int) or not isinstance(columns, int) or rows < 1 or columns < 1 or rows * columns < len(subplots):
        raise ValueError("data-plot-grid requires positive rows/columns covering every subplot")
    if not subplots:
        raise ValueError("data-plot-grid requires subplots")
    fig, raw_axes = plt.subplots(rows, columns, figsize=(5.2 * columns, 3.7 * rows), squeeze=False, sharex=bool(panel.get("share_x")), sharey=bool(panel.get("share_y")))
    flattened = list(raw_axes.flat)
    provenance = []
    sources = []
    legend_handles, legend_labels = [], []
    try:
        for index, subplot in enumerate(subplots):
            if (subplot.get("axis") or {}).get("break"):
                raise ValueError("axis breaks are not supported inside data-plot-grid")
            source, records = panel_records(subplot, input_root)
            sources.append({"file": str(source), "sha256": sha256(source)})
            ax = flattened[index]
            marks = render_to_axis(ax, fig, subplot, records)
            apply_axis_config([ax], subplot, marks)
            ax.set_title(str(subplot.get("title") or subplot.get("id") or index + 1), loc="left", fontsize=10, fontweight="bold")
            subplot_marks = provenance_marks(subplot, marks, str(subplot.get("id") or index + 1))
            for item in subplot_marks: item["source_file"] = str(source)
            provenance.extend(subplot_marks)
            handles, labels = ax.get_legend_handles_labels()
            for handle, label in zip(handles, labels):
                if label and label not in legend_labels:
                    legend_handles.append(handle); legend_labels.append(label)
            if panel.get("shared_legend") and ax.get_legend() is not None:
                ax.get_legend().remove()
        for ax in flattened[len(subplots):]: ax.set_visible(False)
        if panel.get("shared_legend") and legend_handles:
            fig.legend(legend_handles, legend_labels, loc="upper center", ncol=max(1, len(legend_labels)), frameon=False)
            fig.subplots_adjust(top=0.86)
        else:
            fig.tight_layout()
        stem = f"panel_{str(panel['id']).lower()}"; outputs = {}
        for fmt in formats:
            target = output_dir / f"{stem}.{fmt}"; fig.savefig(target, **({"dpi": 220} if fmt == "png" else {})); outputs[fmt] = target.name
    finally:
        plt.close(fig)
    return {"panel": panel["id"], "visual_form": "data-plot-grid", "sources": sources, "outputs": outputs, "marks": provenance, "grid": {"rows": rows, "columns": columns, "share_x": bool(panel.get("share_x")), "share_y": bool(panel.get("share_y")), "shared_legend": bool(panel.get("shared_legend"))}}


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
    panels = [panel for panel in plan.get("panels", []) if panel.get("type") in {"data-plot", "data-plot-grid"} and (not selected or str(panel.get("id")) in selected)]
    if not panels:
        raise SystemExit("no matching data-plot panels found in the plan")

    plt = require_matplotlib()
    configure_matplotlib(plt)
    rendered = [render_grid_panel(panel, input_root, output_dir, formats) if panel.get("type") == "data-plot-grid" else render_panel(panel, input_root, output_dir, formats) for panel in panels]
    provenance = {"schema_version": "1.0", "plan": str(args.plan.resolve()), "panels": rendered}
    provenance_path = output_dir / "provenance.json"
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    for panel in panels:
        target_source = output_dir / f"panel_{str(panel['id']).lower()}_source.py"
        compatibility_source = Path(__file__).resolve().parent.parent / "matplotlib_backend.py"
        if not compatibility_source.is_file():
            candidates = sorted(Path(__file__).resolve().parent.parent.glob("panel_*_source.py"))
            if not candidates:
                raise FileNotFoundError("copied plotting runtime is missing its compatibility source")
            compatibility_source = candidates[0]
        if compatibility_source.resolve() != target_source.resolve():
            shutil.copy2(compatibility_source, target_source)
    plotting_target = output_dir / "plotting"
    if plotting_target.exists():
        shutil.rmtree(plotting_target)
    shutil.copytree(Path(__file__).resolve().parent, plotting_target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    core_target = output_dir / "statistics_core.py"
    if Path(STATS.__file__).resolve() != core_target.resolve():
        shutil.copy2(Path(STATS.__file__), core_target)
    recipe = {
        "command": "python panel_<id>_source.py <figure-plan.json> --output-dir <output-dir>",
        "input_root": str(input_root),
        "formats": list(formats),
    }
    (output_dir / "render-recipe.json").write_text(json.dumps(recipe, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Rendered {len(rendered)} data panel(s) -> {output_dir}")
    return 0
