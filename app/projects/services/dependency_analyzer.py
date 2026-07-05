from typing import List, Dict, Any, Set, Tuple
from sqlalchemy.orm import Session
from app.projects.models.project_models import Project, SemanticNode, SemanticEdge

class DependencyAnalyzer:
    @staticmethod
    def build_dependency_tree(db: Session, project_id: int) -> Dict[str, Any]:
        """
        Generates the file import dependency tree for rendering.
        """
        # Fetch file nodes
        files = db.query(SemanticNode).filter(
            SemanticNode.project_id == project_id,
            SemanticNode.node_type == "file"
        ).all()
        
        file_map = {f.id: f.file_path for f in files}
        
        # Fetch IMPORTS / DEPENDS_ON edges
        edges = db.query(SemanticEdge).filter(
            SemanticEdge.project_id == project_id,
            SemanticEdge.relationship.in_(["IMPORTS", "DEPENDS_ON"])
        ).all()

        adjacency = {fpath: [] for fpath in file_map.values()}
        for e in edges:
            source = file_map.get(e.source_node_id)
            target = file_map.get(e.target_node_id)
            if source and target:
                if target not in adjacency[source]:
                    adjacency[source].append(target)
                    
        return adjacency

    @classmethod
    def detect_circular_dependencies(cls, db: Session, project_id: int) -> List[List[str]]:
        """
        Detects loops in file dependencies using DFS cycle detection.
        """
        adjacency = cls.build_dependency_tree(db, project_id)
        visited = {}  # fpath -> 0 (unvisited), 1 (visiting), 2 (visited)
        for node in adjacency:
            visited[node] = 0

        cycles = []

        def dfs(node: str, path: List[str]):
            visited[node] = 1  # visiting
            path.append(node)

            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    continue
                if visited[neighbor] == 1:
                    # Cycle detected! Extract the path from neighbor to current
                    cycle_start_idx = path.index(neighbor)
                    cycle = path[cycle_start_idx:] + [neighbor]
                    cycles.append(cycle)
                elif visited[neighbor] == 0:
                    dfs(neighbor, path)

            path.pop()
            visited[node] = 2  # visited

        for node in adjacency:
            if visited[node] == 0:
                dfs(node, [])

        return cycles

    @classmethod
    def find_dead_or_unused_modules(cls, db: Session, project_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """
        Identifies orphan classes, functions, and unused files with no incoming connections.
        """
        # Fetch entry point
        project = db.query(Project).filter(Project.id == project_id).first()
        entry_point = project.entry_point or ""

        # Fetch all nodes
        nodes = db.query(SemanticNode).filter(SemanticNode.project_id == project_id).all()
        node_map = {n.id: n for n in nodes}

        # Fetch all incoming call/reference edges
        edges = db.query(SemanticEdge).filter(SemanticEdge.project_id == project_id).all()

        # Count incoming relationships
        inbound_counts = {nid: 0 for nid in node_map}
        for e in edges:
            if e.target_node_id in inbound_counts:
                inbound_counts[e.target_node_id] += 1

        unused_files = []
        dead_symbols = []

        for nid, count in inbound_counts.items():
            node = node_map[nid]
            
            # 1. Unused files: file nodes with 0 incoming dependencies
            if node.node_type == "file":
                # Exclude entry point
                if count == 0 and node.file_path != entry_point and not node.file_path.endswith("main.py"):
                    unused_files.append({
                        "file_path": node.file_path,
                        "name": node.name
                    })
            
            # 2. Dead symbols: classes or functions with 0 references
            elif node.node_type in ["class", "function", "method"]:
                # Exclude routes, db_models or constructors
                is_constructor = node.name.endswith(".__init__") or node.name.endswith(".constructor")
                if count == 0 and not is_constructor:
                    dead_symbols.append({
                        "id": node.id,
                        "name": node.name,
                        "node_type": node.node_type,
                        "file_path": node.file_path,
                        "line": node.start_line
                    })

        return {
            "unused_files": unused_files,
            "dead_symbols": dead_symbols
        }
