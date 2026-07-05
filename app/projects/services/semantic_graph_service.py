import ast
import re
import json
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from app.projects.models.project_models import Project, Analysis, AnalysisFile, SemanticNode, SemanticEdge
from app.projects.repositories.project_repository import ProjectRepository

class SemanticGraphService:
    @staticmethod
    def invalidate_graph(db: Session, project_id: int) -> None:
        """
        Clears cached semantic graph nodes and edges for the specified project.
        """
        db.query(SemanticEdge).filter(SemanticEdge.project_id == project_id).delete()
        db.query(SemanticNode).filter(SemanticNode.project_id == project_id).delete()
        
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.has_semantic_graph = False
            project.graph_generated_at = None
            project.graph_statistics_json = None
        db.commit()

    @classmethod
    def generate_graph(cls, db: Session, project_id: int) -> Dict[str, Any]:
        """
        Parses project source files to construct the semantic graph.
        Does not use an LLM. Fully deterministic AST and lexical parsing.
        """
        cls.invalidate_graph(db, project_id)

        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError("Project not found.")

        # Retrieve files from latest version snapshot first, fallback to analysis run
        from app.projects.models.project_models import ProjectVersion, ProjectVersionFile
        latest_version = db.query(ProjectVersion).filter(
            ProjectVersion.project_id == project_id
        ).order_by(ProjectVersion.version_number.desc()).first()

        files = []
        if latest_version:
            files = db.query(ProjectVersionFile).filter(
                ProjectVersionFile.version_id == latest_version.id
            ).all()

        if not files:
            all_analyses = ProjectRepository.get_project_analyses(db, project_id)
            for anal in all_analyses:
                if anal.status == "completed":
                    files = ProjectRepository.get_analysis_files(db, anal.id)
                    if files:
                        break

        if not files:
            return {"status": "skipped", "reason": "No code files found to parse"}

        # Maps to help resolve references in the second pass
        # (file_path, symbol_name) -> node_id
        symbol_map = {}
        # file_path -> node_id
        file_map = {}

        # 1. First Pass: Create Nodes (Files, Classes, Methods, Functions, API Routes, DB Models)
        for f in files:
            file_path = f.filename.replace("\\", "/")
            # Create node for file itself
            file_node = SemanticNode(
                project_id=project_id,
                node_type="file",
                name=file_path.split("/")[-1],
                file_path=file_path,
                start_line=1,
                end_line=len(f.content.splitlines()) if f.content else 1,
                metadata_json=json.dumps({"size": f.size, "language": f.language})
            )
            db.add(file_node)
            db.flush()  # populate ID
            file_map[file_path] = file_node.id

            content = f.content or ""
            if f.language == "Python":
                cls._parse_python_nodes(content, file_path, project_id, db, symbol_map)
            elif f.language in ["JavaScript", "TypeScript"]:
                cls._parse_js_ts_nodes(content, file_path, project_id, db, symbol_map)
            elif f.language == "Java":
                cls._parse_java_nodes(content, file_path, project_id, db, symbol_map)
            else:
                # Basic generic fallback parser
                cls._parse_generic_nodes(content, file_path, project_id, db, symbol_map)

        # 2. Second Pass: Create Edges (Imports, Call Chains, Inheritance, API Routing)
        for f in files:
            file_path = f.filename.replace("\\", "/")
            content = f.content or ""
            source_file_node_id = file_map.get(file_path)
            if not source_file_node_id:
                continue

            if f.language == "Python":
                cls._parse_python_edges(content, file_path, project_id, db, source_file_node_id, symbol_map, file_map)
            elif f.language in ["JavaScript", "TypeScript"]:
                cls._parse_js_ts_edges(content, file_path, project_id, db, source_file_node_id, symbol_map, file_map)
            elif f.language == "Java":
                cls._parse_java_edges(content, file_path, project_id, db, source_file_node_id, symbol_map, file_map)
            else:
                cls._parse_generic_edges(content, file_path, project_id, db, source_file_node_id, symbol_map, file_map)

        # 3. Calculate statistics
        node_counts = db.query(SemanticNode.node_type).filter(SemanticNode.project_id == project_id).all()
        edge_counts = db.query(SemanticEdge.relationship).filter(SemanticEdge.project_id == project_id).all()
        
        stats = {
            "total_nodes": len(node_counts),
            "total_edges": len(edge_counts),
            "classes": sum(1 for n in node_counts if n[0] == "class"),
            "methods": sum(1 for n in node_counts if n[0] == "method"),
            "functions": sum(1 for n in node_counts if n[0] == "function"),
            "api_routes": sum(1 for n in node_counts if n[0] == "api_route"),
            "db_models": sum(1 for n in node_counts if n[0] == "db_model"),
            "files": sum(1 for n in node_counts if n[0] == "file")
        }

        project.has_semantic_graph = True
        project.graph_generated_at = datetime.utcnow()
        project.graph_statistics_json = json.dumps(stats)
        db.commit()

        return stats

    # --- PYTHON PARSERS ---

    @classmethod
    def _parse_python_nodes(cls, content: str, file_path: str, project_id: int, db: Session, symbol_map: dict):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it is a database model
                is_db_model = any(
                    isinstance(base, ast.Name) and base.id in ["Base", "Model"] or
                    isinstance(base, ast.Attribute) and base.attr in ["Base", "Model"]
                    for base in node.bases
                )
                node_type = "db_model" if is_db_model else "class"
                
                db_node = SemanticNode(
                    project_id=project_id,
                    node_type=node_type,
                    name=node.name,
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    metadata_json=json.dumps({"bases": [ast.unparse(b) for b in node.bases]})
                )
                db.add(db_node)
                db.flush()
                symbol_map[(file_path, node.name)] = db_node.id

                # Parse methods inside the class
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        method_node = SemanticNode(
                            project_id=project_id,
                            node_type="method",
                            name=f"{node.name}.{item.name}",
                            file_path=file_path,
                            start_line=item.lineno,
                            end_line=getattr(item, "end_lineno", item.lineno),
                            metadata_json=json.dumps({"args": [arg.arg for arg in item.args.args]})
                        )
                        db.add(method_node)
                        db.flush()
                        symbol_map[(file_path, f"{node.name}.{item.name}")] = method_node.id

            elif isinstance(node, ast.FunctionDef) and not any(isinstance(p, ast.ClassDef) for p in cls._get_parents(tree, node)):
                # Top level function (or route handler)
                # Check for API decorators (FastAPI/Flask)
                api_path = None
                api_method = "GET"
                for dec in node.decorator_list:
                    dec_str = ast.unparse(dec)
                    m = re.search(r"\.(get|post|put|delete|patch|options|head)\((['\"])(.*?)\2", dec_str)
                    if m:
                        api_method = m.group(1).upper()
                        api_path = m.group(3)
                        break

                if api_path:
                    api_node = SemanticNode(
                        project_id=project_id,
                        node_type="api_route",
                        name=f"{api_method} {api_path}",
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        metadata_json=json.dumps({"handler": node.name})
                    )
                    db.add(api_node)
                    db.flush()
                    symbol_map[(file_path, f"API:{api_method}:{api_path}")] = api_node.id
                
                func_node = SemanticNode(
                    project_id=project_id,
                    node_type="function",
                    name=node.name,
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    metadata_json=json.dumps({"args": [arg.arg for arg in node.args.args]})
                )
                db.add(func_node)
                db.flush()
                symbol_map[(file_path, node.name)] = func_node.id

    @classmethod
    def _parse_python_edges(cls, content: str, file_path: str, project_id: int, db: Session, source_file_node_id: int, symbol_map: dict, file_map: dict):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            # 1. Imports
            if isinstance(node, ast.Import):
                for name in node.names:
                    # Find target file if internal
                    cls._create_import_edge(db, project_id, source_file_node_id, name.name, file_map)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                cls._create_import_edge(db, project_id, source_file_node_id, module, file_map)

            # 2. Call chains
            elif isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name:
                    # Find calling node
                    caller_node_id = source_file_node_id
                    caller_line = node.lineno
                    
                    # Find closest enclosing function/method node
                    best_caller = cls._find_closest_enclosing_node(tree, caller_line, file_path, db, project_id)
                    if best_caller:
                        caller_node_id = best_caller.id

                    # Look up target node by function name in this file or across imports
                    target_node_id = cls._resolve_python_call_target(func_name, file_path, symbol_map)
                    if target_node_id:
                        cls._create_edge(db, project_id, caller_node_id, target_node_id, "CALLS")

            # 3. Inheritance
            elif isinstance(node, ast.ClassDef):
                cls_node_id = symbol_map.get((file_path, node.name))
                if cls_node_id:
                    for base in node.bases:
                        base_name = ast.unparse(base)
                        target_cls_id = cls._resolve_python_call_target(base_name, file_path, symbol_map)
                        if target_cls_id:
                            cls._create_edge(db, project_id, cls_node_id, target_cls_id, "INHERITS")

    # --- JS/TS PARSERS ---

    @classmethod
    def _parse_js_ts_nodes(cls, content: str, file_path: str, project_id: int, db: Session, symbol_map: dict):
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            # Class definition
            cls_match = re.search(r"class\s+(\w+)(?:\s+extends\s+(\w+))?", line)
            if cls_match:
                cls_name = cls_match.group(1)
                db_node = SemanticNode(
                    project_id=project_id,
                    node_type="class",
                    name=cls_name,
                    file_path=file_path,
                    start_line=idx,
                    end_line=idx + 10,  # rough approximation
                    metadata_json=json.dumps({"extends": cls_match.group(2)})
                )
                db.add(db_node)
                db.flush()
                symbol_map[(file_path, cls_name)] = db_node.id
                continue

            # Function definition
            func_match = re.search(r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*\((.*?)\)\s*=>)", line)
            if func_match:
                func_name = func_match.group(1) or func_match.group(2)
                db_node = SemanticNode(
                    project_id=project_id,
                    node_type="function",
                    name=func_name,
                    file_path=file_path,
                    start_line=idx,
                    end_line=idx + 5,
                    metadata_json=json.dumps({})
                )
                db.add(db_node)
                db.flush()
                symbol_map[(file_path, func_name)] = db_node.id
                continue

            # Express / Nest API routes
            api_match = re.search(r"(?:app|router|this\.router)\.(get|post|put|delete)\(\s*(['\"])(.*?)\2", line)
            if api_match:
                method = api_match.group(1).upper()
                path = api_match.group(3)
                db_node = SemanticNode(
                    project_id=project_id,
                    node_type="api_route",
                    name=f"{method} {path}",
                    file_path=file_path,
                    start_line=idx,
                    end_line=idx,
                    metadata_json=json.dumps({})
                )
                db.add(db_node)
                db.flush()
                symbol_map[(file_path, f"API:{method}:{path}")] = db_node.id

    @classmethod
    def _parse_js_ts_edges(cls, content: str, file_path: str, project_id: int, db: Session, source_file_node_id: int, symbol_map: dict, file_map: dict):
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            # Imports / Requires
            import_match = re.search(r"(?:import.*?from\s+['\"](.*?)['\"]|require\(\s*['\"](.*?)['\"]\s*\))", line)
            if import_match:
                target_path = import_match.group(1) or import_match.group(2)
                cls._create_import_edge(db, project_id, source_file_node_id, target_path, file_map)
                continue

            # Basic Call graph regex (heuristic)
            call_match = re.search(r"(\w+)\(", line)
            if call_match:
                func_name = call_match.group(1)
                if func_name not in ["if", "for", "while", "switch", "catch", "require"]:
                    # Find target
                    target_id = symbol_map.get((file_path, func_name))
                    if not target_id:
                        # Scan other files import candidates
                        for key, val in symbol_map.items():
                            if key[1] == func_name:
                                target_id = val
                                break
                    if target_id:
                        cls._create_edge(db, project_id, source_file_node_id, target_id, "CALLS")

    # --- JAVA PARSERS ---

    @classmethod
    def _parse_java_nodes(cls, content: str, file_path: str, project_id: int, db: Session, symbol_map: dict):
        lines = content.splitlines()
        current_class = None
        for idx, line in enumerate(lines, 1):
            # Class / Interface
            class_match = re.search(r"(?:public\s+|private\s+)?(?:class|interface)\s+(\w+)", line)
            if class_match:
                current_class = class_match.group(1)
                node_type = "interface" if "interface" in line else "class"
                db_node = SemanticNode(
                    project_id=project_id,
                    node_type=node_type,
                    name=current_class,
                    file_path=file_path,
                    start_line=idx,
                    end_line=idx + 20,
                    metadata_json=json.dumps({})
                )
                db.add(db_node)
                db.flush()
                symbol_map[(file_path, current_class)] = db_node.id
                continue

            # Method definition
            method_match = re.search(r"(?:public|private|protected|static)\s+[\w<>]+\s+(\w+)\s*\(", line)
            if method_match and current_class:
                method_name = method_match.group(1)
                if method_name not in ["main"]:
                    db_node = SemanticNode(
                        project_id=project_id,
                        node_type="method",
                        name=f"{current_class}.{method_name}",
                        file_path=file_path,
                        start_line=idx,
                        end_line=idx + 8,
                        metadata_json=json.dumps({})
                    )
                    db.add(db_node)
                    db.flush()
                    symbol_map[(file_path, f"{current_class}.{method_name}")] = db_node.id

    @classmethod
    def _parse_java_edges(cls, content: str, file_path: str, project_id: int, db: Session, source_file_node_id: int, symbol_map: dict, file_map: dict):
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            # Imports
            import_match = re.search(r"import\s+([\w\.]+);", line)
            if import_match:
                cls._create_import_edge(db, project_id, source_file_node_id, import_match.group(1), file_map)

    # --- GENERIC FALLBACKS ---

    @classmethod
    def _parse_generic_nodes(cls, content: str, file_path: str, project_id: int, db: Session, symbol_map: dict):
        # Basic scan for functions/classes using indentation or brackets
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            if "class " in line:
                m = re.search(r"class\s+(\w+)", line)
                if m:
                    db_node = SemanticNode(
                        project_id=project_id,
                        node_type="class",
                        name=m.group(1),
                        file_path=file_path,
                        start_line=idx,
                        end_line=idx,
                        metadata_json=json.dumps({})
                    )
                    db.add(db_node)
                    db.flush()
                    symbol_map[(file_path, m.group(1))] = db_node.id

    @classmethod
    def _parse_generic_edges(cls, content: str, file_path: str, project_id: int, db: Session, source_file_node_id: int, symbol_map: dict, file_map: dict):
        pass

    # --- CORE BUILDERS & HELPERS ---

    @staticmethod
    def _create_edge(db: Session, project_id: int, source_id: int, target_id: int, relationship: str) -> None:
        # Check if already exists to prevent duplicates
        exists = db.query(SemanticEdge).filter(
            SemanticEdge.project_id == project_id,
            SemanticEdge.source_node_id == source_id,
            SemanticEdge.target_node_id == target_id,
            SemanticEdge.relationship == relationship
        ).first()
        if not exists and source_id != target_id:
            edge = SemanticEdge(
                project_id=project_id,
                source_node_id=source_id,
                target_node_id=target_id,
                relationship=relationship
            )
            db.add(edge)
            db.flush()

    @classmethod
    def _create_import_edge(cls, db: Session, project_id: int, source_file_node_id: int, target_module: str, file_map: dict) -> None:
        # Resolve target module name to internal file path candidate
        normalized = target_module.replace(".", "/").strip("/")
        for fpath, fid in file_map.items():
            if normalized in fpath or fpath.endswith(normalized + ".py") or fpath.endswith(normalized + ".js") or fpath.endswith(normalized + ".java"):
                cls._create_edge(db, project_id, source_file_node_id, fid, "IMPORTS")
                cls._create_edge(db, project_id, source_file_node_id, fid, "DEPENDS_ON")
                break

    @staticmethod
    def _find_closest_enclosing_node(tree: ast.AST, line: int, file_path: str, db: Session, project_id: int) -> Optional[SemanticNode]:
        # Query db nodes for this file
        candidates = db.query(SemanticNode).filter(
            SemanticNode.project_id == project_id,
            SemanticNode.file_path == file_path,
            SemanticNode.start_line <= line,
            SemanticNode.end_line >= line,
            SemanticNode.node_type.in_(["method", "function"])
        ).all()
        if not candidates:
            return None
        # Return the one with smallest line span
        return min(candidates, key=lambda n: (n.end_line - n.start_line))

    @staticmethod
    def _resolve_python_call_target(name: str, file_path: str, symbol_map: dict) -> Optional[int]:
        # 1. Local resolution in same file
        if (file_path, name) in symbol_map:
            return symbol_map[(file_path, name)]
        
        # 2. Check class methods if format is class.method
        # 3. Scan other files symbols
        for key, val in symbol_map.items():
            if key[1] == name or key[1].endswith(f".{name}"):
                return val
        return None

    @staticmethod
    def _get_parents(tree: ast.AST, target_node: ast.AST) -> List[ast.AST]:
        parents = []
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                if child == target_node:
                    parents.append(node)
                    parents.extend(SemanticGraphService._get_parents(tree, node))
        return parents

    @classmethod
    def compare_version_graphs(cls, db: Session, base_version_id: int, target_version_id: int) -> Dict[str, Any]:
        """
        Compares semantic graphs between two versions by building temporary graphs
        in-memory (via transactions) and computing delta.
        """
        from app.projects.models.project_models import ProjectVersion, ProjectVersionFile, SemanticNode, SemanticEdge
        
        # 1. Fetch versions
        base_ver = db.query(ProjectVersion).filter(ProjectVersion.id == base_version_id).first()
        target_ver = db.query(ProjectVersion).filter(ProjectVersion.id == target_version_id).first()
        if not base_ver or not target_ver:
            raise ValueError("Invalid version IDs")
            
        # We start a nested transaction or savepoint so we can rollback
        db.begin_nested()
        try:
            # Helper to generate graph for a specific version's files and extract nodes/edges
            def get_graph_for_version(version_id: int):
                # Clear active graph for project first
                db.query(SemanticEdge).filter(SemanticEdge.project_id == base_ver.project_id).delete()
                db.query(SemanticNode).filter(SemanticNode.project_id == base_ver.project_id).delete()
                
                # Fetch version files
                v_files = db.query(ProjectVersionFile).filter(ProjectVersionFile.version_id == version_id).all()
                symbol_map = {}
                file_map = {}
                
                # First pass nodes
                for f in v_files:
                    file_path = f.filename.replace("\\", "/")
                    file_node = SemanticNode(
                        project_id=base_ver.project_id,
                        node_type="file",
                        name=file_path.split("/")[-1],
                        file_path=file_path,
                        start_line=1,
                        end_line=len(f.content.splitlines()) if f.content else 1,
                        metadata_json=json.dumps({"size": f.size, "language": f.language})
                    )
                    db.add(file_node)
                    db.flush()
                    file_map[file_path] = file_node.id
                    
                    content = f.content or ""
                    if f.language == "Python":
                        cls._parse_python_nodes(content, file_path, base_ver.project_id, db, symbol_map)
                    elif f.language in ["JavaScript", "TypeScript"]:
                        cls._parse_js_ts_nodes(content, file_path, base_ver.project_id, db, symbol_map)
                    elif f.language == "Java":
                        cls._parse_java_nodes(content, file_path, base_ver.project_id, db, symbol_map)
                    else:
                        cls._parse_generic_nodes(content, file_path, base_ver.project_id, db, symbol_map)
                        
                # Second pass edges
                for f in v_files:
                    file_path = f.filename.replace("\\", "/")
                    content = f.content or ""
                    sf_id = file_map.get(file_path)
                    if sf_id:
                        if f.language == "Python":
                            cls._parse_python_edges(content, file_path, base_ver.project_id, db, sf_id, symbol_map, file_map)
                        elif f.language in ["JavaScript", "TypeScript"]:
                            cls._parse_js_ts_edges(content, file_path, base_ver.project_id, db, sf_id, symbol_map, file_map)
                        elif f.language == "Java":
                            cls._parse_java_edges(content, file_path, base_ver.project_id, db, sf_id, symbol_map, file_map)
                        else:
                            cls._parse_generic_edges(content, file_path, base_ver.project_id, db, sf_id, symbol_map, file_map)
                            
                # Query nodes and edges
                nodes = db.query(SemanticNode).filter(SemanticNode.project_id == base_ver.project_id).all()
                edges = db.query(SemanticEdge).filter(SemanticEdge.project_id == base_ver.project_id).all()
                
                # Let's map by name and type to be robust
                node_set = { (n.name, n.node_type) for n in nodes }
                edge_set = set()
                # Resolve names
                n_map = {n.id: n for n in nodes}
                for e in edges:
                    src = n_map.get(e.source_node_id)
                    tgt = n_map.get(e.target_node_id)
                    if src and tgt:
                        edge_set.add((src.name, tgt.name, e.relationship))
                
                return node_set, edge_set

            # Generate for base and target
            base_nodes, base_edges = get_graph_for_version(base_version_id)
            target_nodes, target_edges = get_graph_for_version(target_version_id)
            
            # Compute difference
            added_nodes = target_nodes - base_nodes
            removed_nodes = base_nodes - target_nodes
            
            added_edges = target_edges - base_edges
            removed_edges = base_edges - target_edges
            
            # Categorize additions/removals
            added_classes = [n[0] for n in added_nodes if n[1] == "class"]
            removed_classes = [n[0] for n in removed_nodes if n[1] == "class"]
            
            added_apis = [n[0] for n in added_nodes if n[1] == "api_route"]
            removed_apis = [n[0] for n in removed_nodes if n[1] == "api_route"]
            
            added_deps = [f"{e[0]} -> {e[1]}" for e in added_edges if e[2] in ["IMPORTS", "DEPENDS_ON"]]
            removed_deps = [f"{e[0]} -> {e[1]}" for e in removed_edges if e[2] in ["IMPORTS", "DEPENDS_ON"]]
            
            drift = "Stable"
            total_changes = len(added_nodes) + len(removed_nodes)
            if total_changes > 10:
                drift = "High Architecture Drift"
            elif total_changes > 3:
                drift = "Medium Architecture Drift"
            elif total_changes > 0:
                drift = "Low Architecture Drift"
                
            return {
                "base_version": base_ver.version_number,
                "target_version": target_ver.version_number,
                "added_classes": added_classes,
                "removed_classes": removed_classes,
                "added_apis": added_apis,
                "removed_apis": removed_apis,
                "added_dependencies": added_deps,
                "removed_dependencies": removed_deps,
                "architecture_drift": drift
            }
        finally:
            # ALWAYS rollback nested transaction to restore current active graph!
            db.rollback()
