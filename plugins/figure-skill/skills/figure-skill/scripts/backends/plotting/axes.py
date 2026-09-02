from __future__ import annotations
from typing import Any

def apply_axis_config(axes: list[Any], panel: dict, marks: list[dict[str, Any]]) -> None:
    config = panel.get("axis") or {}
    if not isinstance(config, dict): raise ValueError("axis must be an object")
    x_scale, y_scale = config.get("x_scale", "linear"), config.get("y_scale", "linear")
    if x_scale not in {"linear", "log", "symlog"} or y_scale not in {"linear", "log", "symlog"}:
        raise ValueError("axis scale must be linear, log, or symlog")
    numeric_x = [float(mark["x"]) for mark in marks if isinstance(mark.get("x"), (int, float))]
    numeric_y = [float(mark["y"]) for mark in marks if isinstance(mark.get("y"), (int, float))]
    if x_scale == "log" and any(value <= 0 for value in numeric_x): raise ValueError("log x axis requires positive values")
    if y_scale == "log":
        if any(value <= 0 for value in numeric_y): raise ValueError("log y axis requires positive values")
        for mark in marks:
            uncertainty = mark.get("uncertainty")
            if uncertainty and float(mark["y"]) - uncertainty["lower"] <= 0:
                raise ValueError("log y axis uncertainty may not cross zero")
    if "x_scale" in config:
        if not numeric_x and x_scale != "linear": raise ValueError("non-linear x scale requires numeric x values")
        if numeric_x:
            for ax in axes: ax.set_xscale(x_scale, **({"linthresh": config.get("x_linthresh", 1.0)} if x_scale == "symlog" else {}))
    if "y_scale" in config:
        if not numeric_y and y_scale != "linear": raise ValueError("non-linear y scale requires numeric y values")
        if numeric_y:
            for ax in axes: ax.set_yscale(y_scale, **({"linthresh": config.get("y_linthresh", 1.0)} if y_scale == "symlog" else {}))
    if config.get("x_limits") is not None:
        for ax in axes: ax.set_xlim(*config["x_limits"])
    if config.get("y_limits") is not None and len(axes) == 1:
        limits = config["y_limits"]
        if panel.get("visual_form") == "bar-chart" and float(limits[0]) != 0 and not str(config.get("baseline_justification", "")).strip():
            raise ValueError("non-zero bar baseline requires baseline_justification")
        axes[0].set_ylim(*limits)
    axis_break = config.get("break")
    if axis_break:
        if panel.get("visual_form") not in {"line-chart", "scatter-plot"}:
            raise ValueError("axis breaks are supported only for line and scatter plots")
        if not str(axis_break.get("justification", "")).strip(): raise ValueError("axis break requires justification")
        omit = axis_break.get("omit")
        if axis_break.get("axis") != "y" or not isinstance(omit, list) or len(omit) != 2 or float(omit[1]) <= float(omit[0]):
            raise ValueError("axis break requires axis='y' and increasing omit bounds")
        low, high = map(float, omit)
        if any(low < value < high for value in numeric_y): raise ValueError("data point lies inside omitted axis interval")
        bottom, top = axes[1], axes[0]
        overall_low = min(numeric_y) if numeric_y else low - 1
        overall_high = max(numeric_y) if numeric_y else high + 1
        bottom.set_ylim(overall_low - max(1e-9, abs(overall_low) * 0.05), low)
        top.set_ylim(high, overall_high + max(1e-9, abs(overall_high) * 0.05))
        top.spines["bottom"].set_visible(False); bottom.spines["top"].set_visible(False)
        top.tick_params(labeltop=False, bottom=False); bottom.xaxis.tick_bottom()
        kwargs = dict(marker=[(-1, -0.5), (1, 0.5)], markersize=8, linestyle="none", color="k", mec="k", mew=1, clip_on=False)
        top.plot([0, 1], [0, 0], transform=top.transAxes, **kwargs); bottom.plot([0, 1], [1, 1], transform=bottom.transAxes, **kwargs)

