from __future__ import annotations
import shutil
import json
from pathlib import Path
from PIL import Image
from .contracts import read, write, sha, validate, identifier, fresh, assessment_pass

KINDS = {"candidate": 2, "revision": 2, "cleanup": 1}

def prepare(root, brief_path=None, kind="candidate", parent=None, instruction=None):
    if not (root / "state.json").exists():
        if brief_path is None:
            raise ValueError("First prepare requires --brief")
        if root.exists() and any(root.iterdir()):
            raise ValueError("Use a new output directory")
        brief = validate(read(brief_path), brief_path.resolve().parent)
        root.mkdir(parents=True, exist_ok=True)
        write(root / "brief.json", brief)
        state = {"schema_version": "1.0", "brief_sha256": sha(root / "brief.json"),
                 "status": "awaiting-generation", "candidates": {}, "attempts": []}
        write(root / "state.json", state)
    brief, state = fresh(root)
    if kind not in KINDS:
        raise ValueError("Unknown generation kind")
    if kind != "candidate" and (parent not in state["candidates"] or not instruction):
        raise ValueError("Revision/cleanup needs an imported parent and explicit change/preserve instructions")
    if kind == "candidate" and parent:
        raise ValueError("Initial candidate cannot have a parent")
    count = sum(a["kind"] == kind for a in state["attempts"])
    if count >= KINDS[kind]:
        raise ValueError("Generation budget exhausted; retain current candidates for review")
    # Reserve before the agent calls the tool. Failed calls consume their reservation.
    number = len(state["attempts"]) + 1
    cid = f"{kind}-{count+1}"
    prompt = ("Design a scientific main figure. Follow only the source-backed design brief below. "
              "Use a white publication background; make the core contribution visually clear. "
              "Short labels and arrows are allowed in a draft; all critical labels/arrows will be editable in the final. "
              "Leave every data-panel box empty; never invent data marks or numerical results. "
              "No brand logos, watermarks, new scientific claims, or decorations obscuring the reading order.\n"
              + ("Composition direction: process-led overview.\n" if count == 0 else "Composition direction: emphasize the core mechanism with surrounding context.\n")
              + json.dumps(brief, ensure_ascii=False, indent=2))
    if instruction:
        prompt += "\nExplicit preserve/change instruction: " + instruction
    if kind == "cleanup":
        prompt += "\nRemove all text and all major arrows while preserving scientific objects and composition. Do not cover them with boxes."
    path = root / "requests" / f"{cid}.txt"
    path.parent.mkdir(exist_ok=True)
    path.write_text(prompt, encoding="utf-8")
    state["attempts"].append({"id": cid, "kind": kind, "parent": parent, "reservation": number,
                              "prompt": str(path.relative_to(root)), "status": "reserved"})
    state["status"] = "awaiting-generation"
    write(root / "state.json", state)
    return {"id": cid, "prompt_file": str(path.resolve()), "remaining_calls": 5-number}

def import_candidate(root, cid, image, prompt, assessment, failed=False):
    brief, state = fresh(root)
    attempt = next((a for a in state["attempts"] if a["id"] == cid), None)
    if not attempt or attempt["status"] != "reserved":
        raise ValueError("Candidate needs an unused call reservation")
    if failed:
        attempt["status"] = "failed"
        state["status"] = "needs-revision"
        write(root / "state.json", state)
        return state
    if not all((image, prompt, assessment)):
        raise ValueError("Import requires actual image, exact submitted prompt and assessment")
    report = read(assessment)
    image_hash = sha(image)
    if report.get("image_sha256") != image_hash or not report.get("selection_reason"):
        raise ValueError("Assessment must bind exact image and explain selection")
    if not prompt.read_text(encoding="utf-8-sig").strip():
        raise ValueError("Submitted prompt is empty")
    with Image.open(image) as im:
        im.load()
        if im.format != "PNG":
            raise ValueError("Import the actual PNG artifact")
        size = list(im.size)
    target = root / "candidates" / identifier(cid)
    target.mkdir(parents=True)
    record = {"id": cid, "parent": attempt["parent"], "kind": attempt["kind"], "size": size,
              "scientific_pass": assessment_pass(brief, report, image_hash),
              "provider": "codex-image-gen", "model": None}
    record["references"] = []
    for index, reference in enumerate(report.get("references", [])):
        source = Path(reference["path"])
        if reference.get("role") not in {"style", "edit-target", "data-preview"} or sha(source) != reference.get("sha256"):
            raise ValueError("References require explicit roles and current hashes")
        target_ref = target / f"reference-{index}{source.suffix}"
        shutil.copy2(source, target_ref)
        record["references"].append({"path": str(target_ref.relative_to(root)), "role": reference["role"], "sha256": sha(target_ref)})
    for key, source, name in (("image", image, "image.png"), ("prompt", prompt, "prompt.txt"),
                              ("assessment", assessment, "assessment.json")):
        shutil.copy2(source, target / name)
        record[key] = str((target / name).relative_to(root))
        record[key + "_sha256"] = sha(target / name)
    attempt["status"] = "imported"
    state["candidates"][cid] = record
    state["status"] = "needs-revision"  # Composition and delivery are separate gates.
    write(root / "state.json", state)
    return record

def select(root, brief, state, requested=None):
    eligible = []
    for cid, candidate in state["candidates"].items():
        report = read(root / candidate["assessment"])
        if assessment_pass(brief, report, candidate["image_sha256"]):
            eligible.append((cid, candidate, report))
    if not eligible:
        raise ValueError("No scientifically and visually passing candidate")
    if requested:
        chosen = next((c for c in eligible if c[0] == requested), None)
        if chosen is None:
            raise ValueError("Selected candidate has unresolved checks")
        return chosen
    # Scores rank only candidates whose scientific checks already pass.
    return max(eligible, key=lambda c: (float(c[2].get("score", 0)), c[0]))
