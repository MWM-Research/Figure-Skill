from __future__ import annotations
from .routes import ENTITY_TERMS, FLOW_WORDS

def extract_entities(text: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    lowered = text.lower()
    for term in ENTITY_TERMS:
        position = lowered.find(term.lower())
        if position >= 0:
            original = text[position:position + len(term)]
            normalized = original.strip().title() if original.isascii() else original.strip()
            matches.append((position, normalized))
    matches.sort()
    result = []
    seen = set()
    for _, entity in matches:
        key = entity.lower()
        if key not in seen:
            seen.add(key)
            result.append(entity)
    return result[:10]


def illustration_panel(inventory: dict, panel_id: str = "A") -> tuple[dict | None, list[str]]:
    narratives = [item for item in inventory.get("files", []) if item.get("text_preview")]
    if not narratives:
        return None, ["Provide methods text or explicitly define the entities and arrow relationships."]
    source = narratives[0]
    text = str(source.get("text_preview", ""))
    entities = extract_entities(text)
    has_flow_evidence = any(word in text.lower() for word in FLOW_WORDS)
    edges = []
    if has_flow_evidence and len(entities) >= 2:
        edges = [
            {"from": left, "to": right, "meaning": "data-flow", "inferred": True}
            for left, right in zip(entities, entities[1:])
        ]
    questions = []
    if len(entities) < 2:
        questions.append(f"Confirm at least two diagram entities for panel {panel_id}.")
    if len(entities) >= 2 and not edges:
        questions.append(f"Confirm arrow direction and meaning for panel {panel_id}; no explicit flow statement was found.")
    return {
        "id": panel_id,
        "title": "Method pipeline",
        "type": "illustration",
        "source_files": [source.get("path")],
        "visual_form": "architecture-diagram",
        "entities": entities,
        "edges": edges,
        "reading_order": "left-to-right",
        "backend": "svg",
        "inference_requires_review": bool(entities or edges),
    }, questions
