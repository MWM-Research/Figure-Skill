#!/usr/bin/env python3
"""Prepare a safe Codex handoff for the optional Happy Figure skill."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_handoff(plan: dict) -> dict:
    illustration_panels = [panel for panel in plan.get("panels", []) if panel.get("type") == "illustration"]
    if not illustration_panels:
        raise ValueError("the plan has no illustration panels")
    requests = []
    for panel in illustration_panels:
        visible = [str(entity) for entity in panel.get("entities", [])]
        requests.append({
            "panel": panel.get("id"),
            "skill": "$happy-figure-skill",
            "source_files": panel.get("source_files", []),
            "prompt": (
                "Use $happy-figure-skill to prepare a model-neutral scientific illustration prompt for "
                f"panel {panel.get('id')}: {panel.get('title')}. "
                f"Figure brief: {plan.get('brief')}. "
                f"Allowed visible labels: {', '.join(visible)}. "
                "Preserve the approved entities and arrow directions; do not add quantitative claims, "
                "experimental evidence, or labels outside the allowlist. Return only the final prompt and a short QA reminder."
            ),
        })
    return {
        "schema_version": "1.0",
        "adapter": "happy-figure-skill",
        "execution": "agent-skill-handoff",
        "note": "This adapter prepares requests only; a Codex/Claude agent with the skill installed must execute them.",
        "requests": requests,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    handoff = build_handoff(plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(handoff['requests'])} Happy Figure handoff(s) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
