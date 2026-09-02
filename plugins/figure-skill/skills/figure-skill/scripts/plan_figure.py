#!/usr/bin/env python3
"""Compatibility entry point for evidence-linked Figure Skill planning."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from planning.data import choose_chart, data_panels
from planning.routes import ROUTES, choose_route
from planning.schema import build_plan

__all__ = ["ROUTES", "choose_route", "choose_chart", "data_panels", "build_plan", "main"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--brief", default="")
    parser.add_argument("--brief-file", type=Path, help="Read the figure brief from a UTF-8 text file")
    parser.add_argument("--route", choices=("auto",) + ROUTES, default="auto")
    parser.add_argument("--edit-operations", type=Path, help="JSON array of explicit edit operations")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    brief = args.brief_file.read_text(encoding="utf-8-sig").strip() if args.brief_file else args.brief
    operations = json.loads(args.edit_operations.read_text(encoding="utf-8")) if args.edit_operations else None
    if operations is not None and not isinstance(operations, list):
        parser.error("--edit-operations must contain a JSON array")
    plan = build_plan(inventory, brief, args.route, operations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Planned route: {plan['route']} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
