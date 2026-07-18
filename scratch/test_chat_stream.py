import asyncio
import json
from app.auth.database.connection import SessionLocal
from app.auth.models.auth_models import User
from app.projects.services.project_chat_service import ProjectChatService

async def main():
    db = SessionLocal()
    try:
        generator = ProjectChatService.chat_stream(
            db=db,
            project_id=1,
            user_query="Explain the session mechanism and function names in auth.py",
            api_key=None,
            user_id=1,
            model="gemini-2.5-flash"
        )
        async for chunk in generator:
            print("Chunk:", chunk)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
