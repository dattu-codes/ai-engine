from sqlalchemy.orm import Session
from typing import List, Optional
from app.projects.models.project_models import Project, Analysis, AnalysisFile, Report

class ProjectRepository:
    @staticmethod
    def get_project(db: Session, project_id: int, user_id: int) -> Optional[Project]:
        return db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()

    @staticmethod
    def get_projects_by_user(db: Session, user_id: int) -> List[Project]:
        return db.query(Project).filter(Project.user_id == user_id).order_by(Project.created_at.desc()).all()

    @staticmethod
    def create_project(db: Session, user_id: int, name: str) -> Project:
        project = Project(user_id=user_id, name=name)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def update_project_name(db: Session, project: Project, name: str) -> Project:
        project.name = name
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def delete_project(db: Session, project: Project) -> None:
        db.delete(project)
        db.commit()

    @staticmethod
    def create_analysis(db: Session, project_id: int, source_type: str, status: str = "pending") -> Analysis:
        analysis = Analysis(project_id=project_id, source_type=source_type, status=status)
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        return analysis

    @staticmethod
    def get_analysis(db: Session, analysis_id: int) -> Optional[Analysis]:
        return db.query(Analysis).filter(Analysis.id == analysis_id).first()

    @staticmethod
    def get_latest_analysis(db: Session, project_id: int) -> Optional[Analysis]:
        return db.query(Analysis).filter(Analysis.project_id == project_id).order_by(Analysis.created_at.desc()).first()

    @staticmethod
    def get_project_analyses(db: Session, project_id: int) -> List[Analysis]:
        return db.query(Analysis).filter(Analysis.project_id == project_id).order_by(Analysis.created_at.desc()).all()

    @staticmethod
    def create_analysis_file(
        db: Session, 
        analysis_id: int, 
        filename: str, 
        extension: str, 
        size: int, 
        language: str, 
        file_hash: str, 
        content: str
    ) -> AnalysisFile:
        analysis_file = AnalysisFile(
            analysis_id=analysis_id,
            filename=filename,
            extension=extension,
            size=size,
            language=language,
            hash=file_hash,
            content=content
        )
        db.add(analysis_file)
        db.commit()
        db.refresh(analysis_file)
        return analysis_file

    @staticmethod
    def get_analysis_files(db: Session, analysis_id: int) -> List[AnalysisFile]:
        return db.query(AnalysisFile).filter(AnalysisFile.analysis_id == analysis_id).all()

    @staticmethod
    def create_report(db: Session, analysis_id: int, score: int, summary: str, details_json: str) -> Report:
        report = Report(analysis_id=analysis_id, score=score, summary=summary, details_json=details_json)
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    @staticmethod
    def get_latest_report(db: Session, analysis_id: int) -> Optional[Report]:
        return db.query(Report).filter(Report.analysis_id == analysis_id).order_by(Report.created_at.desc()).first()
