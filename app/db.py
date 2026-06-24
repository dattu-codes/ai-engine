import uuid
from typing import Dict
from app.engine.graph import Graph

class GraphStore:
    def __init__(self):
        self._graphs: Dict[str, Graph] = {}

    def save_graph(self, graph: Graph) -> str:
        gid = str(uuid.uuid4())
        self._graphs[gid] = graph
        return gid

    def get_graph(self, graph_id: str):
        return self._graphs.get(graph_id)


class RunStore:
    def __init__(self):
        self._runs = {}

    def create_run(self, graph_id: str, initial_state: dict) -> str:
        run_id = str(uuid.uuid4())
        self._runs[run_id] = {
            "graph_id": graph_id,
            "state": dict(initial_state),
            "logs": [],
            "status": "pending"
        }
        return run_id

    def get_run(self, run_id: str):
        return self._runs.get(run_id)

    def update_run(self, run_id: str, state=None, log=None, status=None):
        run = self._runs.get(run_id)
        if run is None:
            return
        if state is not None:
            run["state"] = state
        if log is not None:
            run["logs"].append(log)
        if status is not None:
            run["status"] = status
