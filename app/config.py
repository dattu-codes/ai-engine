import os
from pydantic import BaseModel, Field

class Settings(BaseModel):
    # Database configurations
    DATABASE_URL: str = Field(default="sqlite:///./auth.db")

    # Redis configurations
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Security & Auth configurations
    JWT_SECRET: str = Field(default="47a329ef3118cf94a0d923bc650630ba5239a04a5cf2b07e5cba4839de848aef")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=2)

    # Integrations
    GEMINI_API_KEY: str = Field(default="")

    # Storage configurations
    STORAGE_PROVIDER: str = Field(default="local")  # local, s3, r2
    STORAGE_BUCKET: str = Field(default="ai-engine-uploads")
    STORAGE_REGION: str = Field(default="us-east-1")
    UPLOAD_DIRECTORY: str = Field(default="app/temp_clones")

    # System parameters
    LOG_LEVEL: str = Field(default="INFO")
    APP_ENVIRONMENT: str = Field(default="development")  # development, testing, production

    @classmethod
    def load_from_env(cls):
        # Allow loading environment variables dynamically
        return cls(
            DATABASE_URL=os.getenv("DATABASE_URL", "sqlite:///./auth.db"),
            REDIS_URL=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            JWT_SECRET=os.getenv("JWT_SECRET", "47a329ef3118cf94a0d923bc650630ba5239a04a5cf2b07e5cba4839de848aef"),
            JWT_ALGORITHM=os.getenv("JWT_ALGORITHM", "HS256"),
            ACCESS_TOKEN_EXPIRE_MINUTES=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")),
            REFRESH_TOKEN_EXPIRE_DAYS=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")),
            RATE_LIMIT_WINDOW_SECONDS=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "2")),
            GEMINI_API_KEY=os.getenv("GEMINI_API_KEY", ""),
            STORAGE_PROVIDER=os.getenv("STORAGE_PROVIDER", "local"),
            STORAGE_BUCKET=os.getenv("STORAGE_BUCKET", "ai-engine-uploads"),
            STORAGE_REGION=os.getenv("STORAGE_REGION", "us-east-1"),
            UPLOAD_DIRECTORY=os.getenv("UPLOAD_DIRECTORY", "app/temp_clones"),
            LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
            APP_ENVIRONMENT=os.getenv("APP_ENVIRONMENT", "development")
        )

settings = Settings.load_from_env()
