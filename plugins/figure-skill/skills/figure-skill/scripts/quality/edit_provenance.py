from __future__ import annotations
import json
from pathlib import Path
from .structural import check, sha256

def verify_edit_provenance(path: Path, panel: dict | None = None) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        source = Path(str(data.get("source_file", "")))
        output = Path(str(data.get("output_file", "")))
        valid_source = source.is_file() and data.get("source_sha256") == sha256(source)
        valid_output = output.is_file() and data.get("output_sha256") == sha256(output)
        operations = data.get("operations", [])
        applied = bool(operations) and all(item.get("status") == "applied" for item in operations)
        count_matches = panel is None or len(operations) == len(panel.get("operations", []))
        validations = data.get("validation", {})
        graph_valid = data.get("schema_version") != "2.0" or bool(validations) and all(value is True for value in validations.values())
        return [
            check("edit-provenance-readable", "pass", file=str(path)),
            check("edit-source-hash", "pass" if valid_source else "fail", source=str(source)),
            check("edit-output-hash", "pass" if valid_output else "fail", output=str(output)),
            check("edit-operations-applied", "pass" if applied and count_matches else "fail", count=len(operations)),
            check("edit-graph-validation", "pass" if graph_valid else "fail"),
        ]
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        return [check("edit-provenance-readable", "fail", file=str(path), detail=str(exc))]
