import os
from pydantic import BaseModel

class Settings(BaseModel):
    JWT_SECRET: str = os.getenv("JWT_SECRET", "47a329ef3118cf94a0d923bc650630ba5239a04a5cf2b07e5cba4839de848aef")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./auth.db")

settings = Settings()
