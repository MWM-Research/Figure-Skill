#!/usr/bin/env python3
"""Apply explicit, atomic, auditable edits to SVG sources."""

from __future__ import annotations

import argparse, hashlib, json, math, re, shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
ALLOWED_ATTRIBUTES = {"fill", "stroke", "stroke-width", "font-size", "font-family", "font-weight", "x", "y", "width", "height", "rx", "ry", "opacity", "transform"}
SEMANTIC_OPS = {"bind_graph_metadata", "add_node", "remove_node", "move_node", "resize_node", "add_edge", "remove_edge", "reconnect_edge", "align_nodes", "distribute_nodes", "resolve_overlaps", "auto_layout"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def qname(root: ET.Element, name: str) -> str:
    namespace = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else SVG_NS
    return f"{{{namespace}}}{name}"


def local_name(element: ET.Element) -> str: return element.tag.rsplit("}", 1)[-1]


def number(value: Any, name: str) -> float:
    try: result = float(value)
    except (TypeError, ValueError) as exc: raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(result): raise ValueError(f"{name} must be finite")
    return result


def all_ids(root: ET.Element) -> list[str]: return [str(element.get("id")) for element in root.iter() if element.get("id")]


def element_by_id(root: ET.Element, identifier: str) -> ET.Element:
    matches = [element for element in root.iter() if element.get("id") == identifier]
    if len(matches) != 1: raise ValueError(f"expected one element with id {identifier!r}, found {len(matches)}")
    return matches[0]


def parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]: return {child: parent for parent in root.iter() for child in parent}


def remove_element(root: ET.Element, element: ET.Element) -> None:
    parent = parent_map(root).get(element)
    if parent is None: raise ValueError("cannot remove the SVG root")
    parent.remove(element)


def resolve_source(plan: dict, panel: dict, plan_path: Path) -> Path:
    sources = panel.get("source_files") or []
    if len(sources) != 1: raise ValueError("an edit panel must identify exactly one source file")
    source = Path(str(sources[0]))
    if not source.is_absolute(): source = Path(str(plan.get("input_root") or plan_path.parent)) / source
    source = source.resolve()
    if not source.is_file(): raise FileNotFoundError(f"edit source does not exist: {source}")
    if source.suffix.lower() != ".svg": raise ValueError("native deterministic editing currently supports SVG only")
    return source


def viewbox(root: ET.Element) -> tuple[float, float, float, float]:
    raw = root.get("viewBox")
    if raw:
        values = [number(value, "viewBox") for value in re.split(r"[ ,]+", raw.strip())]
        if len(values) == 4 and values[2] > 0 and values[3] > 0: return tuple(values)  # type: ignore
    return 0.0, 0.0, number(root.get("width"), "SVG width"), number(root.get("height"), "SVG height")


def node_elements(root: ET.Element) -> dict[str, dict[str, ET.Element]]:
    result = {}
    for group in root.iter():
        node_id = group.get("data-node-id") if group.get("data-role") == "node" else None
        if not node_id: continue
        shapes = [child for child in group.iter() if child is not group and child.get("data-role") == "node-shape"]
        labels = [child for child in group.iter() if child is not group and child.get("data-role") == "node-label"]
        if len(shapes) != 1 or len(labels) != 1: raise ValueError(f"node {node_id!r} must have one node-shape and one node-label")
        if node_id in result: raise ValueError(f"duplicate data-node-id: {node_id}")
        result[node_id] = {"group": group, "shape": shapes[0], "label": labels[0]}
    return result


def node_bbox(node: dict[str, ET.Element]) -> dict[str, float]:
    shape = node["shape"]
    if local_name(shape) != "rect": raise ValueError("semantic nodes currently require rect node-shape elements")
    return {key: number(shape.get(key), key) for key in ("x", "y", "width", "height")}


def set_node_bbox(node: dict[str, ET.Element], bbox: dict[str, float]) -> None:
    shape, label = node["shape"], node["label"]
    for key in ("x", "y", "width", "height"): shape.set(key, f"{bbox[key]:g}")
    label.set("x", f"{bbox['x'] + bbox['width'] / 2:g}"); label.set("y", f"{bbox['y'] + bbox['height'] / 2 + 6:g}")


def edge_elements(root: ET.Element) -> dict[str, ET.Element]:
    result = {}
    for element in root.iter():
        if element.get("data-role") != "edge": continue
        identifier = element.get("id")
        if not identifier: raise ValueError("semantic edge requires id")
        if identifier in result: raise ValueError(f"duplicate edge id: {identifier}")
        result[identifier] = element
    return result


def edge_endpoints(source: dict[str, float], target: dict[str, float]) -> tuple[float, float, float, float]:
    sx, sy = source["x"] + source["width"] / 2, source["y"] + source["height"] / 2
    tx, ty = target["x"] + target["width"] / 2, target["y"] + target["height"] / 2
    if abs(tx - sx) >= abs(ty - sy): return source["x"] + source["width"] if tx >= sx else source["x"], sy, target["x"] if tx >= sx else target["x"] + target["width"], ty
    return sx, source["y"] + source["height"] if ty >= sy else source["y"], tx, target["y"] if ty >= sy else target["y"] + target["height"]


def refresh_edges(root: ET.Element) -> list[str]:
    nodes, edges, changed = node_elements(root), edge_elements(root), []
    for identifier, edge in edges.items():
        source_id, target_id = edge.get("data-from"), edge.get("data-to")
        if source_id not in nodes or target_id not in nodes: raise ValueError(f"dangling edge {identifier}: {source_id!r} -> {target_id!r}")
        if local_name(edge) != "line": raise ValueError("semantic edge currently requires a line element")
        for key, value in zip(("x1", "y1", "x2", "y2"), edge_endpoints(node_bbox(nodes[source_id]), node_bbox(nodes[target_id]))): edge.set(key, f"{value:g}")
        changed.append(identifier)
    return changed


def graph_snapshot(root: ET.Element) -> dict[str, Any]:
    return {"nodes": {identifier: node_bbox(node) for identifier, node in node_elements(root).items()}, "edges": {identifier: {"from": edge.get("data-from"), "to": edge.get("data-to")} for identifier, edge in edge_elements(root).items()}}


def ensure_graph_valid(root: ET.Element, expand: bool = False) -> None:
    identifiers = all_ids(root)
    if len(identifiers) != len(set(identifiers)): raise ValueError("SVG contains duplicate ids")
    nodes = node_elements(root); refresh_edges(root); boxes = {identifier: node_bbox(node) for identifier, node in nodes.items()}
    keys = list(boxes)
    for index, left_id in enumerate(keys):
        left = boxes[left_id]
        for right_id in keys[index + 1:]:
            right = boxes[right_id]
            if left["x"] < right["x"] + right["width"] and right["x"] < left["x"] + left["width"] and left["y"] < right["y"] + right["height"] and right["y"] < left["y"] + left["height"]: raise ValueError(f"semantic nodes overlap: {left_id}, {right_id}")
    vx, vy, vw, vh = viewbox(root)
    min_x = min([vx] + [box["x"] for box in boxes.values()]); min_y = min([vy] + [box["y"] for box in boxes.values()]); max_x = max([vx + vw] + [box["x"] + box["width"] for box in boxes.values()]); max_y = max([vy + vh] + [box["y"] + box["height"] for box in boxes.values()])
    outside = min_x < vx or min_y < vy or max_x > vx + vw or max_y > vy + vh
    if outside and not expand: raise ValueError("semantic node lies outside viewBox; set expand_viewbox=true")
    if outside: root.set("viewBox", f"{min_x:g} {min_y:g} {max_x - min_x:g} {max_y - min_y:g}")


def bind_graph_metadata(root: ET.Element, operation: dict[str, Any]) -> dict[str, Any]:
    for item in operation.get("nodes", []):
        group, shape, label = element_by_id(root, item["element_id"]), element_by_id(root, item["shape_id"]), element_by_id(root, item["label_id"])
        group.set("data-role", "node"); group.set("data-node-id", str(item["node_id"])); shape.set("data-role", "node-shape"); label.set("data-role", "node-label")
    for item in operation.get("edges", []):
        edge = element_by_id(root, item["element_id"]); edge.set("data-role", "edge"); edge.set("data-from", str(item["from"])); edge.set("data-to", str(item["to"]))
    return {"op": "bind_graph_metadata", "nodes": len(operation.get("nodes", [])), "edges": len(operation.get("edges", [])), "status": "applied"}


def add_node(root: ET.Element, operation: dict[str, Any]) -> dict[str, Any]:
    node_id, label = str(operation.get("node_id") or ""), str(operation.get("label") or "")
    if not node_id or not label: raise ValueError("add_node requires node_id and label")
    if node_id in node_elements(root): raise ValueError(f"node already exists: {node_id}")
    bbox = {key: number(operation.get(key), key) for key in ("x", "y", "width", "height")}
    if bbox["width"] <= 0 or bbox["height"] <= 0: raise ValueError("node width and height must be positive")
    group_id = str(operation.get("element_id") or f"node-{node_id}")
    if group_id in all_ids(root): raise ValueError(f"element id already exists: {group_id}")
    group = ET.SubElement(root, qname(root, "g"), {"id": group_id, "data-role": "node", "data-node-id": node_id}); style = operation.get("style") or {}
    shape = ET.SubElement(group, qname(root, "rect"), {"id": f"{group_id}-shape", "data-role": "node-shape", "rx": str(style.get("rx", 12)), "fill": str(style.get("fill", "#f2f2f2")), "stroke": str(style.get("stroke", "#222222")), "stroke-width": str(style.get("stroke-width", 2))})
    text = ET.SubElement(group, qname(root, "text"), {"id": f"{group_id}-label", "data-role": "node-label", "text-anchor": "middle", "font-family": "Arial, sans-serif", "font-size": str(style.get("font-size", 17)), "fill": str(style.get("text-fill", "#111111"))}); text.text = label
    set_node_bbox({"group": group, "shape": shape, "label": text}, bbox)
    return {"op": "add_node", "node_id": node_id, "element_id": group_id, "after": bbox, "status": "applied"}


def layout_nodes(root: ET.Element, operation: dict[str, Any]) -> dict[str, Any]:
    kind = operation["op"]; nodes = node_elements(root); node_ids = [str(value) for value in operation.get("node_ids", list(nodes))]
    if any(value not in nodes for value in node_ids): raise ValueError("layout operation references unknown node")
    before = {value: node_bbox(nodes[value]) for value in node_ids}; axis = operation.get("axis", "x")
    if axis not in {"x", "y"}: raise ValueError("layout axis must be x or y")
    if kind == "align_nodes":
        alignment = operation.get("alignment", "center"); first = before[node_ids[0]]; size_key = "width" if axis == "x" else "height"; coordinate = operation.get("coordinate")
        if coordinate is None: coordinate = first[axis] + (first[size_key] / 2 if alignment in {"center", "middle"} else first[size_key] if alignment in {"right", "bottom"} else 0)
        coordinate = number(coordinate, "coordinate")
        for node_id in node_ids:
            box = node_bbox(nodes[node_id]); size = box[size_key]; box[axis] = coordinate - (size / 2 if alignment in {"center", "middle"} else size if alignment in {"right", "bottom"} else 0); set_node_bbox(nodes[node_id], box)
    else:
        gap = number(operation.get("gap", 24), "gap")
        if gap < 0: raise ValueError("gap must be non-negative")
        ordered = node_ids if kind == "distribute_nodes" else sorted(node_ids, key=lambda value: node_bbox(nodes[value])[axis]); cursor = node_bbox(nodes[ordered[0]])[axis]
        for index, node_id in enumerate(ordered):
            box = node_bbox(nodes[node_id]); size_key = "width" if axis == "x" else "height"
            if index: box[axis] = cursor
            set_node_bbox(nodes[node_id], box); cursor = box[axis] + box[size_key] + gap
    affected = refresh_edges(root); return {"op": kind, "node_ids": node_ids, "before": before, "after": {value: node_bbox(nodes[value]) for value in node_ids}, "affected_edges": affected, "status": "applied"}


def auto_layout(root: ET.Element, operation: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = node_elements(root), edge_elements(root); orientation = operation.get("orientation", "left-to-right")
    if orientation not in {"left-to-right", "top-to-bottom"}: raise ValueError("auto_layout orientation is invalid")
    adjacency = {node_id: [] for node_id in nodes}; indegree = {node_id: 0 for node_id in nodes}
    for edge in edges.values(): adjacency[edge.get("data-from")].append(edge.get("data-to")); indegree[edge.get("data-to")] += 1
    queue = [node_id for node_id in nodes if indegree[node_id] == 0]; layers = []
    while queue:
        layer = list(queue); layers.append(layer); queue = []
        for node_id in layer:
            for target in adjacency[node_id]:
                indegree[target] -= 1
                if indegree[target] == 0: queue.append(target)
    if sum(len(layer) for layer in layers) != len(nodes):
        order = operation.get("node_order")
        if not isinstance(order, list) or set(order) != set(nodes): raise ValueError("cyclic graph requires explicit node_order")
        layers = [[str(value)] for value in order]
    gap_x, gap_y, margin = number(operation.get("gap_x", 72), "gap_x"), number(operation.get("gap_y", 48), "gap_y"), number(operation.get("margin", 46), "margin"); before = {value: node_bbox(node) for value, node in nodes.items()}
    for layer_index, layer in enumerate(layers):
        for row_index, node_id in enumerate(layer):
            box = node_bbox(nodes[node_id])
            if orientation == "left-to-right": box["x"], box["y"] = margin + layer_index * (box["width"] + gap_x), margin + row_index * (box["height"] + gap_y)
            else: box["x"], box["y"] = margin + row_index * (box["width"] + gap_x), margin + layer_index * (box["height"] + gap_y)
            set_node_bbox(nodes[node_id], box)
    affected = refresh_edges(root); return {"op": "auto_layout", "orientation": orientation, "layers": layers, "before": before, "after": {value: node_bbox(node) for value, node in nodes.items()}, "affected_edges": affected, "status": "applied"}


def semantic_operation(root: ET.Element, operation: dict[str, Any]) -> dict[str, Any]:
    kind = operation["op"]
    if kind == "bind_graph_metadata": return bind_graph_metadata(root, operation)
    if kind == "add_node": return add_node(root, operation)
    if kind in {"align_nodes", "distribute_nodes", "resolve_overlaps"}: return layout_nodes(root, operation)
    if kind == "auto_layout": return auto_layout(root, operation)
    nodes, edges = node_elements(root), edge_elements(root)
    if kind in {"move_node", "resize_node"}:
        node_id = str(operation.get("node_id")); node = nodes.get(node_id)
        if node is None: raise ValueError(f"unknown node: {node_id}")
        before = node_bbox(node); after = dict(before); keys = ("x", "y") if kind == "move_node" else ("width", "height")
        for key in keys: after[key] = number(operation.get(key), key)
        if after["width"] <= 0 or after["height"] <= 0: raise ValueError("node dimensions must be positive")
        set_node_bbox(node, after); affected = refresh_edges(root); return {"op": kind, "node_id": node_id, "before": before, "after": after, "affected_edges": affected, "status": "applied"}
    if kind == "remove_node":
        node_id = str(operation.get("node_id")); node = nodes.get(node_id)
        if node is None: raise ValueError(f"unknown node: {node_id}")
        connected = [identifier for identifier, edge in edges.items() if edge.get("data-from") == node_id or edge.get("data-to") == node_id]
        if "remove_connected_edges" not in operation: raise ValueError("remove_node requires explicit remove_connected_edges")
        if connected and not operation["remove_connected_edges"]: raise ValueError(f"node has connected edges: {connected}")
        for identifier in connected: remove_element(root, edges[identifier])
        before = node_bbox(node); remove_element(root, node["group"]); return {"op": kind, "node_id": node_id, "before": before, "removed_edges": connected, "status": "applied"}
    if kind == "add_edge":
        source_id, target_id = str(operation.get("from")), str(operation.get("to"))
        if source_id not in nodes or target_id not in nodes: raise ValueError("add_edge references unknown node")
        edge_id = str(operation.get("edge_id") or f"edge-{len(edges) + 1}")
        if edge_id in all_ids(root): raise ValueError(f"edge id already exists: {edge_id}")
        ET.SubElement(root, qname(root, "line"), {"id": edge_id, "data-role": "edge", "data-from": source_id, "data-to": target_id, "data-meaning": str(operation.get("meaning", "unspecified")), "stroke": str(operation.get("stroke", "#222222")), "stroke-width": str(operation.get("stroke-width", 2)), "marker-end": str(operation.get("marker-end", "url(#arrowhead)"))}); refresh_edges(root)
        return {"op": kind, "edge_id": edge_id, "from": source_id, "to": target_id, "status": "applied"}
    if kind == "remove_edge":
        edge_id = str(operation.get("edge_id")); edge = edges.get(edge_id)
        if edge is None: raise ValueError(f"unknown edge: {edge_id}")
        before = {"from": edge.get("data-from"), "to": edge.get("data-to")}; remove_element(root, edge); return {"op": kind, "edge_id": edge_id, "before": before, "status": "applied"}
    if kind == "reconnect_edge":
        edge_id = str(operation.get("edge_id")); edge = edges.get(edge_id)
        if edge is None: raise ValueError(f"unknown edge: {edge_id}")
        source_id, target_id = str(operation.get("from", edge.get("data-from"))), str(operation.get("to", edge.get("data-to")))
        if source_id not in nodes or target_id not in nodes: raise ValueError("reconnect_edge references unknown node")
        before = {"from": edge.get("data-from"), "to": edge.get("data-to")}; edge.set("data-from", source_id); edge.set("data-to", target_id)
        if "meaning" in operation: edge.set("data-meaning", str(operation["meaning"]))
        refresh_edges(root); return {"op": kind, "edge_id": edge_id, "before": before, "after": {"from": source_id, "to": target_id}, "status": "applied"}
    raise ValueError(f"unsupported semantic edit operation: {kind}")


def apply_operation(root: ET.Element, operation: dict[str, Any]) -> dict[str, Any]:
    kind = operation.get("op")
    if kind == "replace_text":
        old, new = operation.get("old"), operation.get("new")
        if not isinstance(old, str) or not isinstance(new, str) or not old: raise ValueError("replace_text requires non-empty string 'old' and string 'new'")
        matches = [element for element in root.iter() if element.text == old]; expected = operation.get("expected_matches", 1)
        if len(matches) != expected: raise ValueError(f"replace_text expected {expected} exact match(es) for {old!r}, found {len(matches)}")
        for element in matches: element.text = new
        return {"op": kind, "old": old, "new": new, "matches": len(matches), "status": "applied"}
    if kind == "set_attribute":
        identifier, attribute, value = operation.get("element_id"), operation.get("attribute"), operation.get("value")
        if not isinstance(identifier, str) or not identifier: raise ValueError("set_attribute requires element_id")
        if attribute not in ALLOWED_ATTRIBUTES: raise ValueError(f"attribute is not allowed: {attribute}")
        if not isinstance(value, (str, int, float)): raise ValueError("set_attribute value must be a string or number")
        element = element_by_id(root, identifier); previous = element.get(attribute); element.set(attribute, str(value)); return {"op": kind, "element_id": identifier, "attribute": attribute, "previous": previous, "value": str(value), "matches": 1, "status": "applied"}
    if kind == "translate_element":
        identifier = str(operation.get("element_id") or ""); element = element_by_id(root, identifier); dx, dy = number(operation.get("dx"), "dx"), number(operation.get("dy"), "dy"); previous = element.get("transform")
        if previous and not operation.get("compose_existing_transform"): raise ValueError("existing transform requires compose_existing_transform=true")
        element.set("transform", f"translate({dx:g} {dy:g})" + (f" {previous}" if previous else "")); return {"op": kind, "element_id": identifier, "dx": dx, "dy": dy, "previous_transform": previous, "status": "applied"}
    if kind == "resize_element":
        identifier = str(operation.get("element_id") or ""); element = element_by_id(root, identifier); tag = local_name(element); allowed = {"rect": ("width", "height"), "image": ("width", "height"), "svg": ("width", "height"), "circle": ("r",), "ellipse": ("rx", "ry")}
        if tag not in allowed: raise ValueError(f"resize_element does not support {tag}")
        previous = {key: element.get(key) for key in allowed[tag]}; values = {}
        for key in allowed[tag]:
            if key not in operation: raise ValueError(f"resize_element requires {key}")
            value = number(operation[key], key)
            if value <= 0: raise ValueError(f"{key} must be positive")
            element.set(key, f"{value:g}"); values[key] = value
        return {"op": kind, "element_id": identifier, "previous": previous, "values": values, "status": "applied"}
    if kind in SEMANTIC_OPS: return semantic_operation(root, operation)
    raise ValueError(f"unsupported edit operation: {kind}")


def render_panel(plan: dict, panel: dict, plan_path: Path, output_dir: Path) -> dict[str, Any]:
    source = resolve_source(plan, panel, plan_path); operations = panel.get("operations") or []
    if not operations: raise ValueError("edit panel has no explicit operations")
    tree = ET.parse(source); root = tree.getroot(); before = graph_snapshot(root); applied = [apply_operation(root, operation) for operation in operations]
    ensure_graph_valid(root, expand=any(bool(operation.get("expand_viewbox")) for operation in operations)); after = graph_snapshot(root)
    output_dir.mkdir(parents=True, exist_ok=True); panel_id = str(panel.get("id", "A")).lower(); output = output_dir / f"panel_{panel_id}.svg"; tree.write(output, encoding="utf-8", xml_declaration=True); source_copy = output_dir / f"panel_{panel_id}_original.svg"; shutil.copy2(source, source_copy)
    provenance = {"schema_version": "2.0", "panel": panel.get("id"), "source_file": str(source), "source_sha256": sha256(source), "source_copy": source_copy.name, "output_file": str(output.resolve()), "output_sha256": sha256(output), "operations": applied, "graph_before": before, "graph_after": after, "validation": {"unique_ids": True, "no_dangling_edges": True, "no_node_overlap": True, "nodes_within_viewbox": True}}
    (output_dir / "edit-provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"); return provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("plan", type=Path); parser.add_argument("--output-dir", type=Path, required=True); args = parser.parse_args(); plan_path = args.plan.resolve(); plan = json.loads(plan_path.read_text(encoding="utf-8")); panels = [panel for panel in plan.get("panels", []) if panel.get("type") == "edit"]
    if len(panels) != 1: parser.error("the native edit backend requires exactly one edit panel")
    render_panel(plan, panels[0], plan_path, args.output_dir.resolve()); print(f"Applied {len(panels[0].get('operations', []))} edit operation(s) -> {args.output_dir}"); return 0


if __name__ == "__main__": raise SystemExit(main())
