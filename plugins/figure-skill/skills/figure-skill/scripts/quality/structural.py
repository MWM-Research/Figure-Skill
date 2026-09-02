from __future__ import annotations
import hashlib, re, struct, xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

PLACEHOLDER = re.compile(r"\b(?:todo|tbd|placeholder|lorem ipsum)\b", re.IGNORECASE)

def check(name: str, status: str, **details: Any) -> dict:
    return {"check": name, "status": status, **details}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_svg(path: Path) -> list[dict]:
    checks = []
    try:
        root = ET.parse(path).getroot()
        checks.append(check("svg-xml-valid", "pass", file=str(path)))
        has_size = bool(root.get("viewBox") or (root.get("width") and root.get("height")))
        checks.append(check("svg-has-canvas-size", "pass" if has_size else "fail", file=str(path)))
        text = " ".join(root.itertext())
        checks.append(check("svg-no-placeholders", "fail" if PLACEHOLDER.search(text) else "pass", file=str(path)))
        images = [element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "image"]
        checks.append(check(
            "svg-not-raster-only",
            "warn" if images else "pass",
            file=str(path),
            detail=f"contains {len(images)} embedded image element(s)" if images else "no embedded raster images",
        ))
    except (ET.ParseError, OSError) as exc:
        checks.append(check("svg-xml-valid", "fail", file=str(path), detail=str(exc)))
    return checks


def inspect_pdf(path: Path) -> list[dict]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return [check("pdf-readable", "fail", file=str(path), detail=str(exc))]
    valid = len(data) > 100 and data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:]
    return [check("pdf-readable", "pass" if valid else "fail", file=str(path), size_bytes=len(data))]


def inspect_png(path: Path) -> list[dict]:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
        valid = len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", header[16:24]) if valid else (0, 0)
        status = "pass" if valid and width >= 300 and height >= 200 else ("warn" if valid else "fail")
        return [check("png-valid-size", status, file=str(path), width=width, height=height)]
    except OSError as exc:
        return [check("png-valid-size", "fail", file=str(path), detail=str(exc))]


def png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
        if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return struct.unpack(">II", header[16:24])
    except OSError:
        return None
