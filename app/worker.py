import logging
from app.projects.services.worker_service import worker_loop

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
)
logger = logging.getLogger("worker_process")

if __name__ == "__main__":
    logger.info("Starting standalone background worker process...")
    
    # Import connection to trigger model registrations and DB mappings
    from app.auth.database.connection import Base, engine
    Base.metadata.create_all(bind=engine)
    
    # Execute the blocking pop queue loop
    worker_loop()
