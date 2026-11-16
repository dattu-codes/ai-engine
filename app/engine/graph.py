from typing import Dict, Callable, Optional, Set

ALLOWED_NODE_TYPES: Set[str] = {
    "extract",
    "complexity",
    "detect",
    "suggest_improvements",
    "stub"
}

class Node:
    def __init__(self, name: str, fn: Callable):
        self.name = name
        self.fn = fn

class Graph:
    def __init__(self, nodes: Dict[str, Node], edges: Dict[str, Optional[str]], start: str):
        self.nodes = nodes
        self.edges = edges
        self.start = start

    @classmethod
    def from_dict(cls, d: dict):
        """
        Create a graph with nodes restricted strictly to the built-in allowlist.
        Rejects arbitrary callables or unknown node types.
        """
        raw_nodes = d.get("nodes", {})
        if not isinstance(raw_nodes, (dict, list)):
            raise ValueError("nodes must be a dict or list")
            
        node_names = list(raw_nodes.keys()) if isinstance(raw_nodes, dict) else list(raw_nodes)
        for name in node_names:
            node_type = name
            if isinstance(raw_nodes, dict) and isinstance(raw_nodes[name], dict):
                node_type = raw_nodes[name].get("type", name)
            if node_type not in ALLOWED_NODE_TYPES:
                raise ValueError(f"Unknown node type '{node_type}'. Allowed node types: {sorted(list(ALLOWED_NODE_TYPES))}")

        nodes = {name: Node(name, lambda state, _name=name: (state, {"node": _name, "info": "stub"}))
                 for name in node_names}
        edges = d.get("edges", {})
        start = d.get("start")
        if start and start not in nodes:
            raise ValueError(f"Start node '{start}' not defined in nodes")
        return cls(nodes, edges, start)
