import os
import uvicorn
from app.main import app

# Expose app for ASGI servers running 'main:app' or 'uvicorn main:app'
__all__ = ["app"]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
