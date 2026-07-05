from typing import List, Dict, Any, Set
from sqlalchemy.orm import Session
from app.projects.models.project_models import SemanticNode, SemanticEdge

class ImpactAnalysisService:
    @staticmethod
    def analyze_impact(
        db: Session, 
        project_id: int, 
        file_path: str, 
        symbol_name: str = None
    ) -> Dict[str, Any]:
        """
        Calculates downstream dependents, calls, reverse calls, and architectural risk scoring.
        """
        # 1. Resolve Target Node
        target_node = None
        if symbol_name:
            target_node = db.query(SemanticNode).filter(
                SemanticNode.project_id == project_id,
                SemanticNode.file_path == file_path,
                SemanticNode.name == symbol_name
            ).first()
            if not target_node:
                # search by matching subclass method
                target_node = db.query(SemanticNode).filter(
                    SemanticNode.project_id == project_id,
                    SemanticNode.file_path == file_path,
                    SemanticNode.name.endswith("." + symbol_name)
                ).first()
        else:
            target_node = db.query(SemanticNode).filter(
                SemanticNode.project_id == project_id,
                SemanticNode.file_path == file_path,
                SemanticNode.node_type == "file"
            ).first()

        if not target_node:
            return {
                "risk_score": 0,
                "risk_rating": "Low Risk",
                "dependent_files": [],
                "call_chain": [],
                "reverse_call_chain": [],
                "impacted_nodes_count": 0
            }

        # Query all nodes and edges for in-memory graph traversal
        all_nodes = db.query(SemanticNode).filter(SemanticNode.project_id == project_id).all()
        all_edges = db.query(SemanticEdge).filter(SemanticEdge.project_id == project_id).all()

        node_map = {n.id: n for n in all_nodes}

        # Build adjacency maps
        outgoing = {nid: [] for nid in node_map}
        incoming = {nid: [] for nid in node_map}

        for e in all_edges:
            src = e.source_node_id
            tgt = e.target_node_id
            rel = e.relationship
            if src in node_map and tgt in node_map:
                outgoing[src].append((tgt, rel))
                incoming[tgt].append((src, rel))

        # 2. Call Chain (Downstream calls/uses from target)
        call_chain = []
        visited_out = set()
        
        def traverse_outgoing(nid: int, depth: int):
            if nid in visited_out or depth > 4:  # limit traversal depth
                return
            visited_out.add(nid)
            for target_id, rel in outgoing.get(nid, []):
                target_node_obj = node_map[target_id]
                call_chain.append({
                    "name": target_node_obj.name,
                    "file_path": target_node_obj.file_path,
                    "node_type": target_node_obj.node_type,
                    "relationship": rel,
                    "depth": depth
                })
                traverse_outgoing(target_id, depth + 1)

        traverse_outgoing(target_node.id, 1)

        # 3. Reverse Call Chain (Upstream callers/references to target)
        reverse_call_chain = []
        visited_in = set()

        def traverse_incoming(nid: int, depth: int):
            if nid in visited_in or depth > 4:
                return
            visited_in.add(nid)
            for src_id, rel in incoming.get(nid, []):
                src_node_obj = node_map[src_id]
                reverse_call_chain.append({
                    "name": src_node_obj.name,
                    "file_path": src_node_obj.file_path,
                    "node_type": src_node_obj.node_type,
                    "relationship": rel,
                    "depth": depth
                })
                traverse_incoming(src_id, depth + 1)

        traverse_incoming(target_node.id, 1)

        # 4. Dependent Files
        dependent_files = set()
        for item in reverse_call_chain:
            dependent_files.add(item["file_path"])
        # Exclude self file
        dependent_files.discard(file_path)

        # 5. Risk Score Calculation
        # Base count on total incoming relationships
        inbound_count = len(reverse_call_chain)
        # Impact factors: classes/API routes have more weight
        weights = {
            "class": 12,
            "method": 8,
            "function": 6,
            "api_route": 20,
            "db_model": 25,
            "file": 15
        }
        base_weight = weights.get(target_node.node_type, 10)
        risk_score = min(100, base_weight + (inbound_count * 8))

        # Risk rating
        if risk_score > 70:
            risk_rating = "High Risk"
        elif risk_score > 30:
            risk_rating = "Medium Risk"
        else:
            risk_rating = "Low Risk"

        return {
            "risk_score": risk_score,
            "risk_rating": risk_rating,
            "dependent_files": list(dependent_files),
            "call_chain": call_chain[:20],  # cap at 20 for API size
            "reverse_call_chain": reverse_call_chain[:20],
            "impacted_nodes_count": len(reverse_call_chain)
        }
