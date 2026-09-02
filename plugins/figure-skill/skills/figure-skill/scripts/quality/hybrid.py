from __future__ import annotations
import json
from pathlib import Path
from .structural import check, sha256

def verify_hybrid_audit(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        source = Path(str(data.get("source", "")))
        plan_path = Path(str(data.get("plan", "")))
        source_valid = source.is_file() and data.get("source_sha256") == sha256(source)
        plan_valid = plan_path.is_file() and data.get("plan_sha256") == sha256(plan_path)
        checks_pass = bool(data.get("checks")) and all(item.get("status") == "pass" for item in data["checks"])
        return [
            check("hybrid-audit-readable", "pass", file=str(path)),
            check("hybrid-audit-source-hash", "pass" if source_valid else "fail", source=str(source)),
            check("hybrid-audit-plan-hash", "pass" if plan_valid else "fail", plan=str(plan_path)),
            check("hybrid-audit-contract", "pass" if data.get("status") == "pass" and checks_pass else "fail"),
        ]
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        return [check("hybrid-audit-readable", "fail", file=str(path), detail=str(exc))]
