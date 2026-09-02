#!/usr/bin/env python3
"""Compatibility entry point for Figure Skill structural and provenance QA."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from quality.data_provenance import verify_data_provenance
from quality.edit_provenance import verify_edit_provenance
from quality.generated import verify_generation_provenance
from quality.hybrid import verify_hybrid_audit
from quality.report import run_qa

__all__ = ["run_qa", "verify_data_provenance", "verify_edit_provenance", "verify_generation_provenance", "verify_hybrid_audit", "main"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8")) if args.plan else None
    report = run_qa(args.target.resolve(), plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"QA status: {report['status']} -> {args.output}")
    return 0 if report["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
