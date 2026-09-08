"""Local orchestration for agent-generated, editable scientific main figures."""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path
from mainfig.contracts import write, read
from mainfig.workflow import prepare, import_candidate
from mainfig.render import compose, export

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "import", "compose", "export"):
        p = sub.add_parser(name)
        p.add_argument("--output", type=Path, required=True)
        if name == "prepare":
            p.add_argument("--brief", type=Path)
            p.add_argument("--kind", choices=("candidate", "revision", "cleanup"), default="candidate")
            p.add_argument("--parent")
            p.add_argument("--instruction")
        elif name == "import":
            p.add_argument("--id", required=True)
            p.add_argument("--image", type=Path)
            p.add_argument("--prompt", type=Path)
            p.add_argument("--assessment", type=Path)
            p.add_argument("--failed", action="store_true")
        elif name == "compose":
            p.add_argument("--candidate")
            p.add_argument("--layout", type=Path, required=True)
        else:
            p.add_argument("--review", type=Path)
            p.add_argument("--human-approval", type=Path)
            p.add_argument("--svg-only", action="store_true", help="Technical test export; cannot complete delivery")
    a = parser.parse_args()
    root = a.output.resolve()
    try:
        if a.command == "prepare":
            result = prepare(root, a.brief, a.kind, a.parent, a.instruction)
        elif a.command == "import":
            result = import_candidate(root, a.id, a.image, a.prompt, a.assessment, a.failed)
        elif a.command == "compose":
            result = compose(root, a.layout, a.candidate)
        else:
            result = export(root, a.review, a.human_approval, a.svg_only)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("status") in {"awaiting-generation", "needs-revision", "awaiting-user-review"} else 0
    except (ValueError, OSError, KeyError, RuntimeError, subprocess.CalledProcessError) as exc:
        if root.is_dir():
            write(root / "reports" / "last-error.json", {"status": "failed", "error": str(exc)})
            if (root / "state.json").is_file():
                state = read(root / "state.json")
                state["status"] = "failed"
                write(root / "state.json", state)
        print(f"Main figure failed: {exc}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
