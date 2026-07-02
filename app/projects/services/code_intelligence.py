import re
import json
from typing import List, Dict, Any, Tuple

class CodeIntelligenceEngine:
    @staticmethod
    def parse_package_json(content: str) -> List[Dict[str, str]]:
        dependencies = []
        try:
            data = json.loads(content)
            for dep_type in ["dependencies", "devDependencies"]:
                deps = data.get(dep_type, {})
                for name, version in deps.items():
                    dependencies.append({
                        "name": name,
                        "version": str(version).strip("^~* ") or "any"
                    })
        except Exception:
            pass
        return dependencies

    @staticmethod
    def parse_requirements_txt(content: str) -> List[Dict[str, str]]:
        dependencies = []
        dep_regex = re.compile(r'^([a-zA-Z0-9_-]+)(?:==|>=|<=|~=|>|<)?(.*)$')
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-r") or line.startswith("-e"):
                continue
            match = dep_regex.match(line)
            if match:
                name = match.group(1).strip()
                version = match.group(2).strip() or "any"
                dependencies.append({"name": name, "version": version})
        return dependencies

    @staticmethod
    def parse_pyproject_toml(content: str) -> List[Dict[str, str]]:
        dependencies = []
        in_deps = False
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                sec = line[1:-1].lower()
                if "dependencies" in sec:
                    in_deps = True
                else:
                    in_deps = False
                continue
            if in_deps and "=" in line:
                parts = line.split("=", 1)
                name = parts[0].strip().strip('"\'')
                version = parts[1].strip().strip('"\'{} ')
                if "version" in version:
                    v_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', version)
                    version = v_match.group(1) if v_match else version
                dependencies.append({"name": name, "version": version})
        return dependencies

    @staticmethod
    def parse_pom_xml(content: str) -> List[Dict[str, str]]:
        dependencies = []
        dep_blocks = re.findall(r'<dependency>[\s\S]*?</dependency>', content)
        for block in dep_blocks:
            groupId = re.search(r'<groupId>(.*?)</groupId>', block)
            artifactId = re.search(r'<artifactId>(.*?)</artifactId>', block)
            version = re.search(r'<version>(.*?)</version>', block)
            
            if artifactId:
                name = f"{groupId.group(1)}:{artifactId.group(1)}" if groupId else artifactId.group(1)
                v = version.group(1) if version else "any"
                dependencies.append({"name": name, "version": v})
        return dependencies

    @staticmethod
    def parse_build_gradle(content: str) -> List[Dict[str, str]]:
        dependencies = []
        patterns = [
            r'(?:implementation|api|compile|testImplementation)\s+[\'"]([^\'"]+):([^\'"]+):([^\'"]+)[\'"]',
            r'(?:implementation|api|compile|testImplementation)\s+[\'"]([^\'"]+):([^\'"]+)[\'"]',
            r'group:\s*[\'"]([^\'"]+)[\'"],\s*name:\s*[\'"]([^\'"]+)[\'"],\s*version:\s*[\'"]([^\'"]+)[\'"]'
        ]
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("//") or line.startswith("/*"):
                continue
            for pattern in patterns:
                matches = re.findall(pattern, line)
                for m in matches:
                    if len(m) == 3:
                        dependencies.append({"name": f"{m[0]}:{m[1]}", "version": m[2]})
                    elif isinstance(m, tuple) and len(m) == 2:
                        dependencies.append({"name": f"{m[0]}:{m[1]}", "version": "any"})
                    elif isinstance(m, str):
                        # Single match in first group case (if any)
                        pass
        return dependencies

    @classmethod
    def analyze_project(cls, files: List[Any]) -> Dict[str, Any]:
        """
        Runs deterministic code intelligence checks on all files in the project.
        """
        total_files = len(files)
        total_lines = 0
        lang_loc = {}
        dependencies = []
        
        # 1. Language Detection & LOC counting
        for f in files:
            content = f.content or ""
            lines = content.splitlines()
            loc = len(lines)
            total_lines += loc
            
            lang = f.language or "Unknown"
            lang_loc[lang] = lang_loc.get(lang, 0) + loc
            
            # 2. Parse config dependency files
            filename_lower = f.filename.lower()
            if filename_lower == "package.json" or filename_lower.endswith("/package.json"):
                dependencies.extend(cls.parse_package_json(content))
            elif filename_lower == "requirements.txt" or filename_lower.endswith("/requirements.txt"):
                dependencies.extend(cls.parse_requirements_txt(content))
            elif filename_lower == "pyproject.toml" or filename_lower.endswith("/pyproject.toml"):
                dependencies.extend(cls.parse_pyproject_toml(content))
            elif filename_lower == "pom.xml" or filename_lower.endswith("/pom.xml"):
                dependencies.extend(cls.parse_pom_xml(content))
            elif filename_lower == "build.gradle" or filename_lower.endswith("/build.gradle"):
                dependencies.extend(cls.parse_build_gradle(content))

        # Compile language distribution percentage
        distribution = {}
        if total_lines > 0:
            for lang, loc in lang_loc.items():
                distribution[lang] = round((loc / total_lines) * 100, 1)
        else:
            distribution = {"Unknown": 100.0}

        # Deduplicate dependencies
        seen_deps = set()
        dedup_dependencies = []
        for d in dependencies:
            key = (d["name"], d["version"])
            if key not in seen_deps:
                seen_deps.add(key)
                dedup_dependencies.append(d)
        
        dep_names = {d["name"].lower() for d in dedup_dependencies}

        # 3. Framework & Project Type Detection
        frameworks = set()
        
        # Dependency check matches
        if "react" in dep_names or "react-dom" in dep_names:
            frameworks.add("React")
        if "next" in dep_names:
            frameworks.add("Next.js")
        if "express" in dep_names:
            frameworks.add("Express")
        if "@nestjs/core" in dep_names or any(d.startswith("@nestjs/") for d in dep_names):
            frameworks.add("NestJS")
        if "django" in dep_names:
            frameworks.add("Django")
        if "fastapi" in dep_names:
            frameworks.add("FastAPI")
        if "flask" in dep_names:
            frameworks.add("Flask")
        if "angular" in dep_names or "@angular/core" in dep_names:
            frameworks.add("Angular")
        if "vue" in dep_names:
            frameworks.add("Vue")
        if "spring-boot-starter-web" in dep_names or any("spring-boot" in d for d in dep_names):
            frameworks.add("Spring Boot")

        # Code content imports matches
        for f in files:
            content = f.content or ""
            filename = f.filename.lower()
            if f.extension == ".py":
                if "import fastapi" in content or "from fastapi" in content:
                    frameworks.add("FastAPI")
                if "import flask" in content or "from flask" in content:
                    frameworks.add("Flask")
                if "import django" in content or "from django" in content or filename == "manage.py":
                    frameworks.add("Django")
            elif f.extension == ".java":
                if "@springbootapplication" in content.lower():
                    frameworks.add("Spring Boot")
            elif f.extension in [".js", ".ts", ".jsx", ".tsx"]:
                if "require('express')" in content or "import express" in content:
                    frameworks.add("Express")
                if "@module" in content.lower() and "nestjs" in content:
                    frameworks.add("NestJS")
                if "react" in content.lower() and ("import react" in content or "from 'react'" in content):
                    frameworks.add("React")
                if "next/link" in content or "next/router" in content:
                    frameworks.add("Next.js")
                if "@angular" in content:
                    frameworks.add("Angular")
                if "vue" in content.lower() and "from 'vue'" in content:
                    frameworks.add("Vue")

        # Deduce primary project type
        if "Spring Boot" in frameworks:
            project_type = "Java Spring Boot Application"
        elif "FastAPI" in frameworks:
            project_type = "Python FastAPI Service"
        elif "Django" in frameworks:
            project_type = "Python Django Application"
        elif "Flask" in frameworks:
            project_type = "Python Flask Application"
        elif "Next.js" in frameworks:
            project_type = "Next.js Frontend Application"
        elif "React" in frameworks:
            project_type = "React Frontend SPA"
        elif "Express" in frameworks:
            project_type = "Node.js Express Server"
        elif "NestJS" in frameworks:
            project_type = "NestJS TypeScript Service"
        elif "Angular" in frameworks:
            project_type = "Angular Frontend App"
        elif "Vue" in frameworks:
            project_type = "Vue Frontend App"
        else:
            primary_lang = max(lang_loc, key=lang_loc.get) if lang_loc else "Python"
            project_type = f"{primary_lang} Project"

        framework_str = ", ".join(frameworks) if frameworks else "None"

        # 4. Entry Point Identification
        entry_point = "None Identified"
        filepaths = [f.filename for f in files]
        
        # Check Application.java (Spring Boot)
        for f in files:
            if f.extension == ".java" and "@springbootapplication" in (f.content or "").lower():
                entry_point = f.filename
                break
        
        if entry_point == "None Identified":
            # Check FastAPI entry points
            for path in filepaths:
                if path.endswith("main.py") or path.endswith("app.py"):
                    entry_point = path
                    break
                    
        if entry_point == "None Identified":
            # Check Next.js routers
            for path in filepaths:
                if "app/page.tsx" in path or "app/page.jsx" in path or "pages/index.tsx" in path or "pages/index.jsx" in path or "pages/index.js" in path:
                    entry_point = path
                    break

        if entry_point == "None Identified":
            # Check React App entry points
            for path in filepaths:
                if path.endswith("App.jsx") or path.endswith("App.tsx") or path.endswith("main.jsx") or path.endswith("main.tsx"):
                    entry_point = path
                    break

        if entry_point == "None Identified":
            # Check Express/Node entry points
            for path in filepaths:
                if path.endswith("server.js") or path.endswith("app.js") or path.endswith("index.js") or path.endswith("index.ts"):
                    entry_point = path
                    break

        # 5. Architecture Identification
        arch_patterns = []
        filepaths_lower = [f.filename.lower() for f in files]
        
        has_controllers = any("controller" in p or "route" in p or "api" in p for p in filepaths_lower)
        has_services = any("service" in p or "logic" in p for p in filepaths_lower)
        has_repositories = any("repository" in p or "db" in p or "dao" in p for p in filepaths_lower)
        has_models = any("model" in p or "schema" in p or "entity" in p for p in filepaths_lower)
        has_views = any("view" in p or "static" in p or "template" in p or "public" in p for p in filepaths_lower)

        if has_controllers and has_models and has_views:
            arch_patterns.append("MVC")
        if has_repositories:
            arch_patterns.append("Repository Pattern")
        if has_services:
            arch_patterns.append("Service Layer")
        if any("route" in p or "controller" in p or "api" in p for p in filepaths_lower):
            arch_patterns.append("REST API")
        if has_controllers and has_services and has_repositories:
            arch_patterns.append("Layered Architecture")
            
        has_frontend = any(x in f for x in ["react", "next", "angular", "vue", "html", "static"] for f in filepaths_lower)
        has_backend = any(x in f for x in ["fastapi", "django", "flask", "springboot", "express", "nestjs"] for f in filepaths_lower)
        if has_frontend and has_backend:
            arch_patterns.append("Monolith")
            
        architecture = ", ".join(arch_patterns) if arch_patterns else "Standard Architecture"

        # 6. File Prioritization
        file_priorities = {}
        for f in files:
            filename = f.filename
            filename_lower = filename.lower()
            
            if any(p in filename_lower for p in ["vendor", "lock", "dist", "build", "generated", "assets", "static", "public"]):
                priority = "low"
            elif any(p in filename_lower for p in ["controller", "service", "logic", "route", "auth", "db", "database", "repository"]) or filename_lower in ["main.py", "app.py", "index.js", "app.js", "server.js"]:
                priority = "high"
            else:
                priority = "medium"
                
            file_priorities[filename] = priority

        return {
            "project_type": project_type,
            "framework": framework_str,
            "architecture": architecture,
            "languages_distribution": distribution,
            "dependencies": dedup_dependencies,
            "entry_point": entry_point,
            "file_priorities": file_priorities,
            "total_lines": total_lines
        }
