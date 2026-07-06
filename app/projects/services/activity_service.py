from sqlalchemy.orm import Session
from datetime import datetime
import json
from typing import Optional, Dict, Any
from app.projects.models.project_models import ActivityLog

class ActivityService:
    @staticmethod
    def log_activity(
        db: Session,
        workspace_id: Optional[int],
        project_id: Optional[int],
        user_id: Optional[int],
        activity_type: str,
        entity_type: str,
        entity_id: Optional[int],
        description: str,
        metadata_json: Optional[Dict[str, Any]] = None
    ) -> ActivityLog:
        meta_str = json.dumps(metadata_json) if metadata_json is not None else None
        log = ActivityLog(
            workspace_id=workspace_id,
            project_id=project_id,
            user_id=user_id,
            activity_type=activity_type,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            metadata_json=meta_str,
            created_at=datetime.utcnow()
        )
        db.add(log)
        db.commit()
        return log
