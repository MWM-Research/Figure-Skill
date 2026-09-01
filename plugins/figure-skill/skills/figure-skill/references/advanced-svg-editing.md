# Advanced native SVG editing

Read this reference before adding, removing, reconnecting, aligning, distributing, or auto-layouting SVG nodes and edges.

## Two support levels

Any SVG may use exact-ID `replace_text`, `set_attribute`, `translate_element`, and `resize_element`. Translation rejects an existing transform unless `compose_existing_transform` is explicitly true. Resize supports rect/image/svg width-height, circle radius, and ellipse radii.

Semantic operations require Figure Skill graph metadata:

- Node group: `data-role="node"` and `data-node-id`.
- Exactly one child `data-role="node-shape"` rect and one `data-role="node-label"` text.
- Edge line: `data-role="edge"`, unique ID, `data-from`, and `data-to`.

Legacy SVGs must use `bind_graph_metadata` with explicit element, shape, label, node, and edge mappings. Do not infer topology from proximity.

## Semantic operations

Supported operations are `add_node`, `remove_node`, `move_node`, `resize_node`, `add_edge`, `remove_edge`, `reconnect_edge`, `align_nodes`, `distribute_nodes`, `resolve_overlaps`, and `auto_layout`.

- Removing a node requires explicit `remove_connected_edges`.
- Alignment uses an explicit node list, axis, alignment, and optional coordinate.
- Distribution and overlap resolution use a non-negative gap and deterministic order.
- Auto-layout supports left-to-right or top-to-bottom layered layouts. A cyclic graph requires an explicit complete `node_order`.
- Nodes outside the current viewBox fail unless an operation explicitly sets `expand_viewbox`.

The backend applies operations atomically in memory, refreshes connected edge endpoints, rejects duplicate IDs, dangling edges, overlap, and out-of-bounds nodes, then writes SVG plus schema-2.0 edit provenance.
