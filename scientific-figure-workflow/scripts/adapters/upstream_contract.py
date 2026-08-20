"""Offline validation helpers for optional upstream command-line contracts."""

from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def declared_flags(entrypoint: Path) -> set[str]:
    tree = ast.parse(entrypoint.read_text(encoding="utf-8-sig"), filename=str(entrypoint))
    flags: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "add_argument":
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str) and argument.value.startswith("--"):
                flags.add(argument.value)
    return flags


def git_commit(repo: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10,
        )
        commit = result.stdout.strip()
        return commit if result.returncode == 0 and len(commit) == 40 else None
    except (OSError, subprocess.SubprocessError):
        return None


def inspect_contract(repo: Path, entrypoint: Path, required_flags: set[str]) -> dict:
    if not entrypoint.is_file():
        raise FileNotFoundError(entrypoint)
    flags = declared_flags(entrypoint)
    missing = sorted(required_flags - flags)
    if missing:
        raise ValueError(f"upstream CLI contract changed; missing flags: {', '.join(missing)}")
    return {
        "status": "verified",
        "entrypoint_sha256": sha256(entrypoint),
        "git_commit": git_commit(repo),
        "required_flags": sorted(required_flags),
    }
