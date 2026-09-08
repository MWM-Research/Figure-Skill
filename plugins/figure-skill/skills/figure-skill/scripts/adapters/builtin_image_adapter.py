"""Import a Codex-generated image; this module never calls an image API."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from PIL import Image


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_image(plan: dict, source: Path, prompt_file: Path, output_dir: Path) -> dict:
    panels = plan.get("panels", [])
    if (plan.get("review_status") != "approved" or plan.get("open_questions")
            or len(panels) != 1 or panels[0].get("type") != "raster-illustration"):
        raise ValueError("Builtin import requires one approved raster illustration with no open questions")
    panel = panels[0]
    if panel.get("evidence_role") != "illustrative" or panel.get("annotation_spec", {}).get("mode") != "deterministic-overlay":
        raise ValueError("Builtin import requires illustrative evidence role and deterministic overlay")
    panel_id = str(panel.get("id", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]+", panel_id):
        raise ValueError("Invalid panel ID")
    prompt = prompt_file.read_text(encoding="utf-8-sig")
    if not prompt.strip():
        raise ValueError("Save the exact prompt submitted to the builtin tool before importing")
    with Image.open(source) as image:
        image.load()
        if image.format != "PNG":
            raise ValueError("Builtin import currently requires a PNG artifact")
        width, height = image.size
    canvas = panel.get("canvas", {})
    requested = [canvas.get("width"), canvas.get("height")]
    if not all(type(value) is int and value > 0 for value in requested):
        raise ValueError("Reviewed canvas must contain positive integer dimensions")
    if width < 300 or height < 200 or width * requested[1] != height * requested[0]:
        raise ValueError("Builtin image must meet minimum dimensions and the reviewed aspect ratio")
    if [width, height] != requested and not panel["annotation_spec"].get("allow_same_aspect_resize", False):
        raise ValueError("Canvas resize was not authorized by the reviewed annotation plan")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"panel_{panel_id.lower()}.png"
    if output.exists():
        raise FileExistsError(f"Do not overwrite an imported image: {output}")
    shutil.copy2(source, output)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    request = {
        "schema_version": "1.0", "adapter": "Codex builtin image import",
        "provider_protocol": "codex-image-gen", "model": None, "endpoint": None,
        "metadata_note": "Tool identity and prompt are agent-recorded; backend model is not reported.",
        "panel": panel_id, "generated_content": True, "evidence_role": "illustrative",
        "prompt": prompt, "prompt_sha256": prompt_hash, "size": f"{requested[0]}x{requested[1]}",
        "expected_output": str(output.resolve()), "network_required": False,
        "execution": "local import of an already generated tool artifact",
    }
    provenance = {
        "schema_version": "1.0", "status": "generated-awaiting-human-review",
        "generated_content": True, "evidence_role": "illustrative", "human_review_required": True,
        "provider_protocol": "codex-image-gen", "model": None, "endpoint": None,
        "prompt_sha256": prompt_hash, "imported_from": str(source.resolve()),
        "imported_sha256": digest(source), "output": str(output.resolve()), "output_sha256": digest(output),
        "width": width, "height": height, "requested_size": requested,
        "size_matches_request": [width, height] == requested, "format": "PNG",
    }
    for name, data in (("raster-illustration-request.json", request), ("generation-provenance.json", provenance)):
        (output_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return provenance
