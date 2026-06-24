# app/engine/runner.py
import asyncio
from typing import Optional

class Runner:
    """
    Executes a graph asynchronously, step by step.
    Supports:
    - sequential edges (graph.edges)
    - branching via state["next"]
    - looping until next is None or max_steps reached
    """

    def __init__(self, graph_store, run_store, max_steps: int = 200):
        self.graph_store = graph_store
        self.run_store = run_store
        self.max_steps = max_steps

    async def run(self, run_id: str):
        run = self.run_store.get_run(run_id)
        if run is None:
            return

        graph_id = run["graph_id"]
        graph = self.graph_store.get_graph(graph_id)

        if graph is None:
            # mark as error so the API shows failure
            self.run_store.update_run(run_id, status="error", log={"error": "graph_not_found"})
            return

        state = run["state"]
        current_node = graph.start
        steps = 0

        while current_node is not None and steps < self.max_steps:
            steps += 1
            node = graph.nodes.get(current_node)

            if node is None:
                # unknown node referenced by edge/next
                self.run_store.update_run(run_id, status="error", log={"error": f"node_not_found:{current_node}"})
                return

            try:
                # Execute node function (handles sync and async callables)
                if asyncio.iscoroutinefunction(node.fn):
                    state, log = await node.fn(state)
                else:
                    state, log = node.fn(state)

                # Add physical server timestamp to log
                import datetime
                if isinstance(log, dict):
                    log["timestamp"] = datetime.datetime.now().strftime("%I:%M:%S %p").lower()

                # Save update & log
                self.run_store.update_run(run_id, state=state, log=log)

                # Branching / dynamic next
                if "next" in state:
                    next_node = state.pop("next")  # consume it so it doesn't persist unintentionally
                    current_node = next_node
                else:
                    current_node = graph.edges.get(node.name)

                # yield control
                await asyncio.sleep(0)

            except Exception as e:
                # record exception and stop
                self.run_store.update_run(run_id, status="error", log={"error": str(e)})
                return

        final_status = "completed" if steps < self.max_steps else "max_steps_exceeded"
        self.run_store.update_run(run_id, status=final_status)
