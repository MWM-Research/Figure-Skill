from __future__ import annotations
from typing import Any

def provenance_marks(panel: dict, marks: list[dict[str, Any]], subplot_id: str | None = None) -> list[dict[str, Any]]:
    result = []
    for mark in marks:
        item: dict[str, Any] = {"transform": panel.get("transform", "none")}
        if subplot_id is not None: item["subplot"] = subplot_id
        if "source_row" in mark: item["source_row"] = mark["source_row"]
        if "source_rows" in mark: item["source_rows"] = mark["source_rows"]
        for key in ("x", "y", "value", "x2"):
            if key in mark:
                column = panel.get(key)
                item[key] = {"column": column, "value": mark[key]}
                if key in {"y", "value"}: item[key]["unit"] = panel.get("unit")
        if "group" in mark:
            item["group"] = {"column": panel.get("group") or panel.get("x"), "value": mark["group"]}
        if "uncertainty" in mark:
            item["uncertainty"] = mark["uncertainty"]
            if panel.get("error") and mark["uncertainty"]["mode"] == "symmetric-delta":
                item["error"] = {"column": panel["error"], "value": mark["uncertainty"]["values"]["error"], "semantics": "symmetric-absolute"}
        if "derived" in mark: item["derived"] = mark["derived"]
        if "precomputed" in mark: item["precomputed"] = mark["precomputed"]
        if "threshold" in mark: item["threshold"] = mark["threshold"]
        result.append(item)
    return result

