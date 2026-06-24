from typing import Dict, Callable, Optional

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
        Create a simple graph with stub nodes. Useful for custom graph_def in requests.
        Nodes created here are placeholders and return a trivial log.
        """
        nodes = {name: Node(name, lambda state, _name=name: (state, {"node": _name, "info": "stub"}))
                 for name in d.get("nodes", {})}
        edges = d.get("edges", {})
        start = d.get("start")
        return cls(nodes, edges, start)
