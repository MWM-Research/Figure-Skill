#!/usr/bin/env python3
"""Apply explicit, auditable edits to an existing SVG without guessing intent."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


ALLOWED_ATTRIBUTES = {
    "fill", "stroke", "stroke-width", "font-size", "font-family", "font-weight",
    "x", "y", "width", "height", "rx", "ry", "opacity", "transform",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_source(plan: dict, panel: dict, plan_path: Path) -> Path:
    sources = panel.get("source_files") or []
    if len(sources) != 1:
        raise ValueError("an edit panel must identify exactly one source file")
    source = Path(str(sources[0]))
    if not source.is_absolute():
        input_root = Path(str(plan.get("input_root") or plan_path.parent))
        source = input_root / source
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"edit source does not exist: {source}")
    if source.suffix.lower() != ".svg":
        raise ValueError("native deterministic editing currently supports SVG only")
    return source


def elements_by_id(root: ET.Element, identifier: str) -> list[ET.Element]:
    return [element for element in root.iter() if element.get("id") == identifier]


def apply_operation(root: ET.Element, operation: dict[str, Any]) -> dict[str, Any]:
    kind = operation.get("op")
    if kind == "replace_text":
        old, new = operation.get("old"), operation.get("new")
        if not isinstance(old, str) or not isinstance(new, str) or not old:
            raise ValueError("replace_text requires non-empty string 'old' and string 'new'")
        matches = [element for element in root.iter() if element.text == old]
        expected = operation.get("expected_matches", 1)
        if len(matches) != expected:
            raise ValueError(f"replace_text expected {expected} exact match(es) for {old!r}, found {len(matches)}")
        for element in matches:
            element.text = new
        return {"op": kind, "old": old, "new": new, "matches": len(matches), "status": "applied"}
    if kind == "set_attribute":
        identifier = operation.get("element_id")
        attribute = operation.get("attribute")
        value = operation.get("value")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("set_attribute requires element_id")
        if attribute not in ALLOWED_ATTRIBUTES:
            raise ValueError(f"attribute is not allowed: {attribute}")
        if not isinstance(value, (str, int, float)):
            raise ValueError("set_attribute value must be a string or number")
        matches = elements_by_id(root, identifier)
        if len(matches) != 1:
            raise ValueError(f"set_attribute expected one element with id {identifier!r}, found {len(matches)}")
        previous = matches[0].get(attribute)
        matches[0].set(attribute, str(value))
        return {
            "op": kind, "element_id": identifier, "attribute": attribute,
            "previous": previous, "value": str(value), "matches": 1, "status": "applied",
        }
    raise ValueError(f"unsupported edit operation: {kind}")


def render_panel(plan: dict, panel: dict, plan_path: Path, output_dir: Path) -> dict[str, Any]:
    source = resolve_source(plan, panel, plan_path)
    operations = panel.get("operations") or []
    if not operations:
        raise ValueError("edit panel has no explicit operations")
    tree = ET.parse(source)
    applied = [apply_operation(tree.getroot(), operation) for operation in operations]
    output_dir.mkdir(parents=True, exist_ok=True)
    panel_id = str(panel.get("id", "A")).lower()
    output = output_dir / f"panel_{panel_id}.svg"
    tree.write(output, encoding="utf-8", xml_declaration=True)
    source_copy = output_dir / f"panel_{panel_id}_original.svg"
    shutil.copy2(source, source_copy)
    provenance = {
        "schema_version": "1.0", "panel": panel.get("id"),
        "source_file": str(source), "source_sha256": sha256(source),
        "source_copy": source_copy.name, "output_file": str(output.resolve()),
        "output_sha256": sha256(output), "operations": applied,
    }
    (output_dir / "edit-provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    plan_path = args.plan.resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    panels = [panel for panel in plan.get("panels", []) if panel.get("type") == "edit"]
    if len(panels) != 1:
        parser.error("the native edit backend requires exactly one edit panel")
    render_panel(plan, panels[0], plan_path, args.output_dir.resolve())
    print(f"Applied {len(panels[0].get('operations', []))} edit operation(s) -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
