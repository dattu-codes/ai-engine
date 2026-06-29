from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.auth.config.settings import settings

# Configure connection arguments (required for SQLite multi-thread checking)
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# Create SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args
)

# Configure session maker
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Declarative base model class
Base = declarative_base()

# FastAPI db connection dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
