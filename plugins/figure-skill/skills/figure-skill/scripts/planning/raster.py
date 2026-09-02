from __future__ import annotations
import re
from .illustration import extract_entities
from .routes import FLOW_WORDS

def raster_illustration_panel(inventory: dict, brief: str, panel_id: str = "A") -> tuple[dict, list[str]]:
    narratives = [item for item in inventory.get("files", []) if item.get("text_preview")]
    source = narratives[0] if narratives else None
    text = str(source.get("text_preview", "")) if source else ""
    entities = extract_entities(text)
    has_flow_evidence = any(word in text.lower() for word in FLOW_WORDS)
    edges = [
        {"from": left, "to": right, "meaning": "data-flow", "inferred": True}
        for left, right in zip(entities, entities[1:])
    ] if has_flow_evidence and len(entities) >= 2 else []
    lowered = brief.lower()
    style = "3d-render" if any(word in lowered for word in ("3d", "three-dimensional", "三维")) else (
        "photorealistic" if any(word in lowered for word in ("photorealistic", "photo", "照片", "写实"))
        else "scientific-concept-art"
    )
    title = re.sub(
        r"^(?:create|generate|make|draw)\s+(?:(?:an?|the)\s+)?", "", brief.strip(), flags=re.IGNORECASE
    )
    title = re.sub(r"^(?:生成|绘制|制作)(?:一张|一个)?", "", title).strip(" 。.")
    title = title[:72].strip() or "Scientific Concept Overview"
    subtitle = "Key concepts: " + " · ".join(entities[:4]) if entities else "Conceptual scientific illustration"
    footer = "Conceptual illustration — not quantitative evidence"
    visible_labels = [title, subtitle, footer]
    annotation_spec = {
        "mode": "deterministic-overlay",
        "allow_same_aspect_resize": True,
        "title": {"text": title, "position": [0.5, 0.055], "font_size": 28, "font_weight": 650},
        "subtitle": {"text": subtitle, "position": [0.5, 0.095], "font_size": 15, "font_weight": 500},
        "labels": [],
        "arrows": [],
        "legend": {},
        "footer": {"text": footer, "position": [0.5, 0.965], "font_size": 13, "font_weight": 400},
    }
    questions = []
    if not source:
        questions.append(f"Provide reviewed methods text for raster illustration panel {panel_id}.")
    if not entities:
        questions.append(f"Confirm the scientific entities that must appear in raster illustration panel {panel_id}.")
    if len(entities) >= 2 and not edges:
        questions.append(
            f"Confirm the spatial or directional relationships for raster illustration panel {panel_id}; "
            "no explicit flow statement was found."
        )
    return {
        "id": panel_id,
        "title": title,
        "type": "raster-illustration",
        "source_files": [source.get("path")] if source else [],
        "visual_form": "generated-raster",
        "style": style,
        "evidence_role": "illustrative",
        "scientific_description": text[:1500],
        "entities": entities,
        "edges": edges,
        "visible_labels": visible_labels,
        "annotation_spec": annotation_spec,
        "annotation_requires_review": True,
        "forbidden_content": [
            "invented measurements or statistics",
            "unapproved labels",
            "watermarks",
            "presentation as microscopy, medical, field, or instrument evidence",
        ],
        "backend": "byok-openai-compatible-images plus deterministic raster annotation overlay",
        "canvas": {"width": 1024, "height": 1024},
        "human_review_required": True,
    }, questions
