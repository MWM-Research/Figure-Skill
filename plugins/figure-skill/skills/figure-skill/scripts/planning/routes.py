from __future__ import annotations
from pathlib import Path

ROUTES = ("illustration", "raster-illustration", "hybrid-composite", "data-plot", "edit", "composite")
EDIT_SUFFIXES = {".svg", ".drawio", ".ai", ".eps"}
EDIT_WORDS = ("edit", "revise", "modify", "修改", "编辑", "调整", "重绘", "补充")
EDIT_OPERATIONS = {"replace_text", "set_attribute", "translate_element", "resize_element", "bind_graph_metadata", "add_node", "remove_node", "move_node", "resize_node", "add_edge", "remove_edge", "reconnect_edge", "align_nodes", "distribute_nodes", "resolve_overlaps", "auto_layout"}
FLOW_WORDS = ("flow", "flows", "followed by", "then", "from", "to", "流向", "依次", "然后", "经过", "到")
ENTITY_TERMS = (
    "input", "encoder", "decoder", "backbone", "embedding", "retrieval", "retriever",
    "classifier", "predictor", "generator", "discriminator", "attention", "transformer",
    "database", "knowledge graph", "feature extractor", "fusion", "output",
    "train/test split", "standard scaler", "logistic regression", "prediction", "accuracy",
    "输入", "编码器", "解码器", "骨干网络", "嵌入", "检索器", "检索模块", "分类器",
    "预测器", "生成器", "判别器", "注意力", "数据库", "知识图谱", "特征提取", "融合", "输出",
)
METRIC_PRIORITY = (
    "accuracy", "acc", "f1", "precision", "recall", "auc", "score", "performance",
    "throughput", "latency", "time", "memory", "loss", "error",
)
RASTER_ILLUSTRATION_WORDS = (
    "photorealistic", "photo style", "photo-style", "3d", "three-dimensional",
    "照片风格", "照片级", "写实", "三维", "3d科研", "科研插画", "概念插画",
)
HYBRID_RASTER_WORDS = ("raster", "栅格", "video frame", "视频帧", "heatmap", "热力图", "photo", "image")
HYBRID_VECTOR_WORDS = ("vector", "矢量", "module", "模块", "arrow", "箭头", "axis", "坐标轴", "bar chart", "柱状图")
HEATMAP_WORDS = ("heatmap", "heat map", "热力图", "confusion matrix", "混淆矩阵")
LINE_WORDS = ("line chart", "line plot", "curve", "training curve", "折线图", "曲线", "多系列", "multi-series")
ERROR_WORDS = ("error bar", "uncertainty", "confidence interval", "误差线", "误差棒", "不确定性", "置信区间")
UNCERTAINTY_COLUMN_WORDS = (
    "error", "stderr", "standard_error", "std", "stdev", "stddev", "standard_deviation",
    "sem", "uncertainty", "ci", "confidence",
)
HEATMAP_VALUE_WORDS = ("attention", "intensity", "value", "score", "count", "frequency", "probability", "weight")
HEATMAP_X_WORDS = ("frame", "time", "epoch", "pred", "column", "col")
HEATMAP_Y_WORDS = ("head", "actual", "true", "row", "class")
ADVANCED_FORMS = (
    (("box plot", "boxplot", "箱线图"), "box-plot"),
    (("violin", "小提琴图"), "violin-plot"),
    (("histogram", "直方图"), "histogram"),
    (("density plot", "density curve", "密度图", "密度曲线"), "density-plot"),
    (("confusion matrix", "混淆矩阵"), "confusion-matrix"),
    (("roc",), "roc-curve"),
    (("precision-recall", "precision recall", "pr curve", "pr曲线"), "pr-curve"),
)


def data_files(inventory: dict) -> list[dict]:
    return [item for item in inventory.get("files", []) if item.get("table_profile", {}).get("data_candidate")]


def choose_route(inventory: dict, brief: str, explicit: str = "auto") -> str:
    if explicit != "auto":
        return explicit
    counts = inventory.get("category_counts", {})
    paths = [Path(item.get("path", "")) for item in inventory.get("files", [])]
    has_data = bool(data_files(inventory) or counts.get("log"))
    has_context = bool(counts.get("narrative") or counts.get("raster") or counts.get("vector"))
    has_editable = any(path.suffix.lower() in EDIT_SUFFIXES for path in paths)
    wants_edit = any(word in brief.lower() for word in EDIT_WORDS)
    wants_hybrid = (
        "hybrid" in brief.lower() or "混合" in brief
        or (
            any(word in brief.lower() for word in HYBRID_RASTER_WORDS)
            and any(word in brief.lower() for word in HYBRID_VECTOR_WORDS)
        )
    )
    if wants_hybrid:
        return "hybrid-composite"
    wants_raster_illustration = any(word in brief.lower() for word in RASTER_ILLUSTRATION_WORDS)
    if wants_raster_illustration and not has_data:
        return "raster-illustration"
    if has_data and has_context:
        return "composite"
    if has_data:
        return "data-plot"
    if has_editable and wants_edit:
        return "edit"
    return "illustration"
