import re
import json
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from app.projects.models.project_models import Project, ProjectVersion, ProjectVersionFile, Report, Analysis

class RetrievalService:
    @staticmethod
    def retrieve_context(db: Session, project_id: int, query: str) -> Dict[str, Any]:
        """
        Extracts relevant files, reports, and version details based on query keyword matching.
        Capped to prevent context window overflow.
        """
        # 1. Fetch latest version
        latest_version = db.query(ProjectVersion).filter(
            ProjectVersion.project_id == project_id
        ).order_by(ProjectVersion.version_number.desc()).first()

        if not latest_version:
            return {
                "files": [],
                "report": None,
                "version_history": [],
                "version_number": 0
            }

        # Retrieve all snapshot files at this version
        files = db.query(ProjectVersionFile).filter(
            ProjectVersionFile.version_id == latest_version.id
        ).all()

        # 2. Score and rank files based on query keywords
        tokens = re.findall(r'\b\w+\b', query.lower())
        stopwords = {
            "a", "an", "the", "and", "or", "in", "of", "to", "for", "with", "is", "at", "by", "from",
            "how", "what", "why", "where", "who", "explain", "describe", "show", "suggest", "find",
            "on", "this", "project", "code", "file", "function", "class", "method"
        }
        query_keywords = [t for t in tokens if t not in stopwords]
        if not query_keywords:
            query_keywords = tokens

        scored_files = []
        is_architectural = any(kw in ["architecture", "structure", "framework", "onboarding", "main", "entry", "onboard", "setup", "explain", "README", "document"] for kw in query_keywords)

        for f in files:
            score = 0
            filename_lower = f.filename.lower()
            content_lower = (f.content or "").lower()

            # Boost file name match
            for kw in query_keywords:
                if kw in filename_lower:
                    score += 50

            # Boost content occurrences
            for kw in query_keywords:
                occurrences = content_lower.count(kw)
                score += min(occurrences * 5, 100)

            # Boost entry points for architectural queries
            if is_architectural:
                if any(x in filename_lower for x in ["main.py", "app.py", "index.js", "server.js", "package.json", "requirements.txt", "readme.md"]):
                    score += 30
                if any(x in filename_lower for x in ["auth", "route", "controller", "config", "model"]):
                    score += 15

            scored_files.append((score, f))

        # Sort files by relevance score descending
        scored_files.sort(key=lambda x: x[0], reverse=True)

        # Retrieve top relevant files within character limit (approx 60K chars / 15K tokens)
        retrieved_files = []
        total_chars = 0
        max_chars = 60000

        for score, f in scored_files:
            if score == 0 and len(retrieved_files) >= 2:
                # If file has zero match and we already have some context, skip it
                break

            content_len = len(f.content or "")
            if total_chars + content_len > max_chars:
                if len(retrieved_files) == 0:
                    # Truncate very large file if it's the only match
                    f.content = (f.content or "")[:max_chars]
                    retrieved_files.append(f)
                break

            retrieved_files.append(f)
            total_chars += content_len

            if len(retrieved_files) >= 5:
                break

        # 3. Retrieve latest analysis Report
        report = db.query(Report).join(Analysis).filter(
            Analysis.project_id == project_id,
            Analysis.status == "completed"
        ).order_by(Analysis.id.desc()).first()

        # 4. Retrieve version history overview (last 3 versions)
        versions = db.query(ProjectVersion).filter(
            ProjectVersion.project_id == project_id
        ).order_by(ProjectVersion.version_number.desc()).limit(3).all()

        return {
            "files": retrieved_files,
            "report": report,
            "version_history": versions,
            "version_number": latest_version.version_number
        }
