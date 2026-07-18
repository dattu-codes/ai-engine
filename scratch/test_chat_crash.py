from app.auth.database.connection import SessionLocal
from app.auth.models.auth_models import User
from app.projects.services.retrieval_service import RetrievalService
db = SessionLocal()
try:
    context = RetrievalService.retrieve_context(db, 1, "Explain session check_session")
    print("Success:", len(context["files"]))
except Exception as e:
    import traceback
    traceback.print_exc()
