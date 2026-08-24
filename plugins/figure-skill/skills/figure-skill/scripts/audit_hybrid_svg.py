#!/usr/bin/env python3
"""Audit a hybrid SVG against a reviewed raster/vector representation contract."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def selected_contract(plan: dict) -> tuple[dict, dict]:
    contract = plan.get("representation_contract")
    if isinstance(contract, dict):
        return contract, plan
    panels = [panel for panel in plan.get("panels", []) if isinstance(panel.get("representation_contract"), dict)]
    if len(panels) != 1:
        raise ValueError("plan must contain exactly one representation_contract")
    return panels[0]["representation_contract"], panels[0]


def decode_embedded_png(element: ET.Element) -> bytes | None:
    href = element.get("href") or element.get("{http://www.w3.org/1999/xlink}href") or ""
    prefix = "data:image/png;base64,"
    if not href.startswith(prefix):
        return None
    return base64.b64decode(href[len(prefix):], validate=True)


def resolve_assets(pattern: str, asset_root: Path) -> list[Path]:
    decoded = urllib.parse.unquote(pattern)
    return sorted(path for path in asset_root.glob(decoded) if path.is_file())


def audit(plan_path: Path, svg_path: Path, asset_root: Path) -> dict:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    contract, owner = selected_contract(plan)
    root = ET.parse(svg_path).getroot()
    elements = list(root.iter())
    roles = Counter(element.get("data-role") for element in elements if element.get("data-role"))
    tags = Counter(local_name(element.tag) for element in elements)
    checks = []
    mappings = []
    allowed_image_roles = set()

    for rule in contract.get("roles", []):
        role = str(rule.get("role", ""))
        expected_tag = str(rule.get("svg_tag", ""))
        kind = str(rule.get("kind", ""))
        matching = [element for element in elements if element.get("data-role") == role]
        expected_count = rule.get("expected_count")
        minimum = int(rule.get("min_count", 0))
        maximum = rule.get("max_count")
        count_ok = len(matching) == int(expected_count) if expected_count is not None else (
            len(matching) >= minimum and (maximum is None or len(matching) <= int(maximum))
        )
        tag_ok = bool(matching) and all(local_name(element.tag) == expected_tag for element in matching)
        checks.extend([
            {"check": f"role-count:{role}", "status": "pass" if count_ok else "fail", "expected": expected_count if expected_count is not None else {"min": minimum, "max": maximum}, "actual": len(matching)},
            {"check": f"role-svg-tag:{role}", "status": "pass" if tag_ok else "fail", "expected": expected_tag, "actual": sorted({local_name(element.tag) for element in matching})},
        ])
        if kind == "raster":
            allowed_image_roles.add(role)
            embedded_hashes = []
            embedded_ok = True
            for index, element in enumerate(matching, start=1):
                try:
                    payload = decode_embedded_png(element)
                except ValueError:
                    payload = None
                if payload is None:
                    embedded_ok = False
                    continue
                embedded_hashes.append(sha256_bytes(payload))
                mappings.append({"role": role, "index": index, "embedded_sha256": embedded_hashes[-1], "source": None})
            checks.append({"check": f"embedded-png:{role}", "status": "pass" if embedded_ok and len(embedded_hashes) == len(matching) else "fail", "count": len(embedded_hashes)})
            pattern = rule.get("source_glob")
            if pattern:
                sources = resolve_assets(str(pattern), asset_root)
                source_hashes = [sha256(path) for path in sources]
                sources_by_hash: dict[str, list[Path]] = defaultdict(list)
                for source, source_hash in zip(sources, source_hashes):
                    sources_by_hash[source_hash].append(source)
                used_per_hash: Counter[str] = Counter()
                for mapping in (item for item in mappings if item["role"] == role):
                    candidates = sources_by_hash.get(mapping["embedded_sha256"], [])
                    offset = used_per_hash[mapping["embedded_sha256"]]
                    source = candidates[offset] if offset < len(candidates) else None
                    used_per_hash[mapping["embedded_sha256"]] += 1
                    mapping["source"] = str(source.resolve()) if source else None
                source_match = Counter(embedded_hashes) == Counter(source_hashes)
                checks.append({
                    "check": f"source-hash-match:{role}", "status": "pass" if source_match else "fail",
                    "embedded_count": len(embedded_hashes), "source_count": len(sources),
                })

    image_elements = [element for element in elements if local_name(element.tag) == "image"]
    unclassified_images = [element for element in image_elements if element.get("data-role") not in allowed_image_roles]
    image_policy = contract.get("unclassified_image_policy", "forbid")
    checks.append({
        "check": "unclassified-images", "status": "pass" if image_policy != "forbid" or not unclassified_images else "fail",
        "count": len(unclassified_images), "policy": image_policy,
    })

    if contract.get("exact_visible_labels"):
        planned = set(str(value) for value in owner.get("visible_labels", []))
        actual = set(
            "".join(element.itertext()).strip()
            for element in elements if local_name(element.tag) == "text" and "".join(element.itertext()).strip()
        )
        checks.append({
            "check": "visible-labels", "status": "pass" if planned == actual else "fail",
            "missing": sorted(planned - actual), "extra": sorted(actual - planned),
        })

    status = "pass" if checks and all(item["status"] == "pass" for item in checks) else "fail"
    return {
        "schema_version": "1.0",
        "status": status,
        "plan": str(plan_path.resolve()), "plan_sha256": sha256(plan_path),
        "source": str(svg_path.resolve()), "source_sha256": sha256(svg_path),
        "asset_root": str(asset_root.resolve()),
        "tag_counts": dict(tags), "role_counts": dict(roles),
        "image_mappings": mappings, "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--svg", type=Path, required=True)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.plan.resolve(), args.svg.resolve(), args.asset_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Hybrid SVG audit: {report['status']} -> {args.output.resolve()}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
