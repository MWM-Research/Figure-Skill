#!/usr/bin/env python3
"""Prepare or execute a BYOK OpenAI-compatible scientific image request."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image


KEY_ENV = "FIGURE_IMAGE_API_KEY"
BASE_URL_ENV = "FIGURE_IMAGE_BASE_URL"
MODEL_ENV = "FIGURE_IMAGE_MODEL"
DEFAULT_BASE_URL = "https://right.codes/codex/v1"
DEFAULT_MODEL = "gpt-image-2"
MAX_IMAGE_BYTES = 50 * 1024 * 1024


def select_panel(plan: dict, panel_id: str | None = None) -> dict:
    panels = [panel for panel in plan.get("panels", []) if panel.get("type") == "raster-illustration"]
    if panel_id:
        panels = [panel for panel in panels if str(panel.get("id")) == panel_id]
    if len(panels) != 1:
        raise ValueError("select exactly one raster-illustration panel with --panel")
    return panels[0]


def endpoint_for(base_url: str) -> str:
    return base_url.rstrip("/") + "/images/generations"


def validate_public_endpoint(endpoint: str, allow_insecure_http: bool = False) -> None:
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme == "https" and parsed.netloc:
        return
    if allow_insecure_http and parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}:
        return
    raise ValueError("image generation endpoint must use HTTPS")


def build_prompt(plan: dict, panel: dict) -> str:
    entities = [str(value) for value in panel.get("entities", []) if str(value).strip()]
    relations = [
        f"{edge.get('from')} -> {edge.get('to')} ({edge.get('meaning', 'relationship')})"
        for edge in panel.get("edges", [])
        if edge.get("from") and edge.get("to")
    ]
    visible_labels = [str(value) for value in panel.get("visible_labels", []) if str(value).strip()]
    forbidden = [str(value) for value in panel.get("forbidden_content", []) if str(value).strip()]
    sections = [
        "Create a generated scientific illustration for conceptual communication, not empirical evidence.",
        f"Intent: {plan.get('brief') or panel.get('title') or 'Scientific illustration'}",
        f"Visual style: {panel.get('style', 'scientific-concept-art')}",
        f"Scientific description: {panel.get('scientific_description', '')}",
        "Required entities: " + (", ".join(entities) if entities else "none explicitly listed"),
        "Required relationships: " + ("; ".join(relations) if relations else "none explicitly listed"),
        "Visible text allowlist: " + (", ".join(visible_labels) if visible_labels else "no visible text"),
        "Forbidden content: " + ("; ".join(forbidden) if forbidden else "invented measurements, statistics, labels, or experimental observations"),
        "Do not add quantitative results, p-values, axes, microscopy evidence, medical findings, watermarks, or unapproved labels.",
        "Keep the composition suitable for later scientific annotation and human review.",
    ]
    return "\n".join(sections)


def prepare_request(
    plan: dict, panel: dict, output_dir: Path, base_url: str, model: str,
    size: str, quality: str, output_format: str = "png",
    allow_insecure_http: bool = False,
) -> dict:
    endpoint = endpoint_for(base_url)
    validate_public_endpoint(endpoint, allow_insecure_http)
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(plan, panel)
    output = output_dir / f"panel_{str(panel['id']).lower()}.png"
    return {
        "schema_version": "1.0",
        "adapter": "Figure Skill BYOK raster illustration",
        "panel": panel.get("id"),
        "evidence_role": panel.get("evidence_role", "illustrative"),
        "generated_content": True,
        "provider_protocol": "openai-compatible-images",
        "endpoint": endpoint,
        "model": model,
        "size": size,
        "quality": quality,
        "output_format": output_format,
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "expected_output": str(output.resolve()),
        "credential_environment": KEY_ENV,
        "credential_available": bool(os.environ.get(KEY_ENV)),
        "network_required": True,
        "request_body": {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "output_format": output_format,
        },
    }


def fetch_image_url(url: str) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("provider returned a non-HTTPS image URL")
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise RuntimeError("provider image exceeded the 50 MB safety limit")
    return data


def decode_response(payload: dict) -> bytes:
    data = payload.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise RuntimeError("provider response did not contain data[0]")
    item = data[0]
    if isinstance(item.get("b64_json"), str):
        try:
            return base64.b64decode(item["b64_json"], validate=True)
        except ValueError as exc:
            raise RuntimeError("provider returned invalid base64 image data") from exc
    if isinstance(item.get("url"), str):
        return fetch_image_url(item["url"])
    raise RuntimeError("provider response contained neither b64_json nor url")


def execute_request(request: dict, api_key: str, allow_insecure_http: bool = False) -> dict:
    endpoint = str(request["endpoint"])
    validate_public_endpoint(endpoint, allow_insecure_http)
    body = json.dumps(request["request_body"], ensure_ascii=False).encode("utf-8")
    http_request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=300) as response:
            response_bytes = response.read(MAX_IMAGE_BYTES + 1)
            request_id = response.headers.get("x-request-id")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"image provider returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"image provider connection failed: {exc.reason}") from exc
    if len(response_bytes) > MAX_IMAGE_BYTES:
        raise RuntimeError("provider response exceeded the 50 MB safety limit")
    try:
        payload = json.loads(response_bytes)
    except json.JSONDecodeError as exc:
        raise RuntimeError("image provider returned invalid JSON") from exc
    image_bytes = decode_response(payload)
    output = Path(str(request["expected_output"]))
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.load()
            width, height = image.size
            image_format = image.format
    except Exception as exc:
        raise RuntimeError("provider output was not a readable image") from exc
    if width < 300 or height < 200:
        raise RuntimeError(f"provider image is too small: {width}x{height}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image_bytes)
    return {
        "schema_version": "1.0",
        "status": "generated-awaiting-human-review",
        "generated_content": True,
        "evidence_role": request["evidence_role"],
        "model": request["model"],
        "endpoint": endpoint,
        "request_id": request_id,
        "prompt_sha256": request["prompt_sha256"],
        "output": str(output.resolve()),
        "output_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "width": width,
        "height": height,
        "format": image_format,
        "human_review_required": True,
    }


def write_manifest(request: dict, output_dir: Path) -> Path:
    manifest = output_dir / "raster-illustration-request.json"
    manifest.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--panel")
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--quality", default="medium")
    parser.add_argument("--output-format", default="png")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--allow-insecure-http", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    panel = select_panel(plan, args.panel)
    base_url = args.base_url or os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL
    model = args.model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL
    output_dir = args.output_dir.resolve()
    request = prepare_request(
        plan, panel, output_dir, base_url, model, args.size, args.quality,
        args.output_format, args.allow_insecure_http,
    )
    manifest = write_manifest(request, output_dir)
    if not args.execute:
        print(f"Prepared BYOK raster illustration request -> {manifest}")
        return 0
    if not args.allow_network:
        raise SystemExit("raster illustration execution requires explicit --allow-network")
    if plan.get("review_status") != "approved" or plan.get("open_questions"):
        raise SystemExit("approve the illustration plan and resolve open_questions before execution")
    key = os.environ.get(KEY_ENV)
    if not key:
        raise SystemExit(f"No credential found in {KEY_ENV}")
    provenance = execute_request(request, key, args.allow_insecure_http)
    provenance_path = output_dir / "generation-provenance.json"
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated raster illustration for human review -> {provenance['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
