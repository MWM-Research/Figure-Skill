from __future__ import annotations

def hybrid_composite_panel(inventory: dict, brief: str, panel_id: str = "A") -> tuple[dict, list[str]]:
    lowered = brief.lower()
    roles = []
    if any(word in lowered for word in ("video frame", "视频帧")):
        roles.append({"role": "video-frame-raster", "kind": "raster", "svg_tag": "image", "min_count": 1})
    if any(word in lowered for word in ("heatmap", "热力图")):
        roles.append({"role": "attention-heatmap-raster", "kind": "raster", "svg_tag": "image", "min_count": 1})
    if any(word in lowered for word in ("transformer", "module", "模块", "架构")):
        roles.append({"role": "transformer-module", "kind": "vector", "svg_tag": "rect", "min_count": 1})
    if any(word in lowered for word in ("arrow", "箭头", "flow", "数据流")):
        roles.append({"role": "data-flow-arrow", "kind": "vector", "svg_tag": "path", "min_count": 1})
    if any(word in lowered for word in ("bar chart", "柱状图", "result", "结果图")):
        roles.extend([
            {"role": "result-bar", "kind": "vector", "svg_tag": "rect", "min_count": 1},
            {"role": "axis", "kind": "vector", "svg_tag": "line", "min_count": 2},
        ])
    contract = {"roles": roles, "unclassified_image_policy": "forbid", "exact_visible_labels": True}
    questions = [
        "Confirm exact visible labels and normalized layout before rendering the hybrid Figure.",
        "Set exact role counts and raster source_glob values in representation_contract before approval.",
    ]
    return {
        "id": panel_id,
        "title": "Hybrid scientific Figure",
        "type": "hybrid-composite",
        "source_files": [item.get("path") for item in inventory.get("files", [])],
        "visual_form": "hybrid-raster-vector-composite",
        "evidence_role": "review-required",
        "visible_labels": [],
        "annotation_spec": {"mode": "deterministic-overlay", "builder": "hybrid-composite"},
        "representation_contract": contract,
        "canvas": {"width": 2048, "height": 1280},
        "backend": "custom hybrid SVG compositor plus audit_hybrid_svg.py",
        "human_review_required": True,
    }, questions
