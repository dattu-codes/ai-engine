from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.auth.models.auth_models import User
from app.projects.models.project_models import Project

class BillingService:
    @staticmethod
    def get_plan_limits(plan: str) -> dict:
        """Returns the project and analysis file limits for a plan tier."""
        plan_lower = (plan or "Free").lower()
        if plan_lower == "pro":
            return {
                "max_projects": 5,
                "max_files": 20
            }
        elif plan_lower == "enterprise":
            return {
                "max_projects": 999999,
                "max_files": 999999
            }
        else: # Free / Default
            return {
                "max_projects": 1,
                "max_files": 3
            }

    @classmethod
    def check_billing_limit(cls, db: Session, user: User, limit_type: str, file_count: int = 0):
        """Raises HTTP 402 if billing plan limits are exceeded."""
        limits = cls.get_plan_limits(user.billing_plan)
        
        if limit_type == "projects":
            # Count user projects
            proj_count = db.query(Project).filter(Project.user_id == user.id).count()
            if proj_count >= limits["max_projects"]:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"Subscription limit reached: Your current '{user.billing_plan}' plan allows a maximum of {limits['max_projects']} projects. Please upgrade your plan."
                )
                
        elif limit_type == "files":
            if file_count > limits["max_files"]:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"Analysis file limit reached: Your current '{user.billing_plan}' plan allows a maximum of {limits['max_files']} source files per analysis. You provided {file_count} files. Please upgrade your plan."
                )
