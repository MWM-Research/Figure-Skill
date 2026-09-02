from __future__ import annotations
import importlib.util, math
from pathlib import Path
from typing import Any

def load_statistics_core():
    path = Path(__file__).resolve().parent.parent / "statistics_core.py"
    spec = importlib.util.spec_from_file_location("figure_statistics_core", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load statistics core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STATS = load_statistics_core()


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError as exc:
        raise SystemExit("matplotlib is required; install the dependencies listed in this Skill's requirements.txt") from exc
    return plt


def configure_matplotlib(plt) -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.linewidth": 0.9, "svg.fonttype": "none", "pdf.fonttype": 42})

def finite_number(value: Any, *, column: str, row: int) -> float:
    try:
        number = float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"non-numeric value in column {column!r}, source row {row}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"non-finite value in column {column!r}, source row {row}: {value!r}")
    return number


def error_number(value: Any, *, column: str, row: int) -> float:
    number = finite_number(value, column=column, row=row)
    if number < 0:
        raise ValueError(f"negative uncertainty in column {column!r}, source row {row}: {value!r}")
    return number


def uncertainty_config(panel: dict) -> dict[str, Any] | None:
    configured = panel.get("uncertainty")
    legacy = panel.get("error")
    if configured and legacy:
        raise ValueError("use either uncertainty or legacy error, not both")
    if configured:
        if not isinstance(configured, dict):
            raise ValueError("uncertainty must be an object")
        return configured
    return {"mode": "symmetric-delta", "error_column": legacy} if legacy else None


def record_uncertainty(record: dict[str, Any], panel: dict, y_value: float) -> dict[str, Any] | None:
    config = uncertainty_config(panel)
    if not config:
        return None
    mode = config.get("mode")
    row = int(record["__source_row__"])
    if mode == "symmetric-delta":
        column = config.get("error_column")
        if not column:
            raise ValueError("symmetric-delta uncertainty requires error_column")
        value = error_number(record.get(column), column=str(column), row=row)
        return {"mode": mode, "lower": value, "upper": value, "columns": {"error": str(column)}, "values": {"error": value}}
    lower_column, upper_column = config.get("lower_column"), config.get("upper_column")
    if not lower_column or not upper_column:
        raise ValueError(f"{mode} uncertainty requires lower_column and upper_column")
    lower_value = finite_number(record.get(lower_column), column=str(lower_column), row=row)
    upper_value = finite_number(record.get(upper_column), column=str(upper_column), row=row)
    if mode == "asymmetric-delta":
        if lower_value < 0 or upper_value < 0:
            raise ValueError("asymmetric uncertainty deltas must be non-negative")
        lower_delta, upper_delta = lower_value, upper_value
    elif mode == "bounds":
        if not lower_value <= y_value <= upper_value:
            raise ValueError(f"uncertainty bounds must satisfy lower <= y <= upper at source row {row}")
        lower_delta, upper_delta = y_value - lower_value, upper_value - y_value
    else:
        raise ValueError("uncertainty mode must be symmetric-delta, asymmetric-delta, or bounds")
    return {
        "mode": mode, "lower": lower_delta, "upper": upper_delta,
        "columns": {"lower": str(lower_column), "upper": str(upper_column)},
        "values": {"lower": lower_value, "upper": upper_value},
    }

def calculation(panel: dict, operation: str) -> dict[str, Any]:
    value = panel.get("calculation") or {"mode": "precomputed", "operation": operation, "parameters": {}}
    if not isinstance(value, dict) or value.get("mode") not in {"precomputed", "raw"}:
        raise ValueError("calculation.mode must be precomputed or raw")
    if value.get("operation") not in {None, operation}:
        raise ValueError(f"visual form requires calculation.operation={operation}")
    parameters = value.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ValueError("calculation.parameters must be an object")
    return {"mode": value["mode"], "operation": operation, "parameters": parameters}


def grouped_samples(panel: dict, records: list[dict[str, Any]], value_name: str) -> dict[str, tuple[list[float], list[int]]]:
    group_name = panel.get("group") or panel.get("x")
    grouped: dict[str, tuple[list[float], list[int]]] = {}
    for record in records:
        row = int(record["__source_row__"])
        group = str(record.get(group_name, "All")) if group_name else "All"
        if not group:
            raise ValueError(f"panel {panel['id']} contains an empty group")
        values, rows = grouped.setdefault(group, ([], []))
        values.append(finite_number(record.get(value_name), column=value_name, row=row))
        rows.append(row)
    return grouped
