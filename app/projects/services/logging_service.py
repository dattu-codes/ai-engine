import json
import logging
import os
from datetime import datetime
from app.config import settings

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "filename": record.filename,
            "lineno": record.lineno
        }
        
        # Pull extra context fields if passed
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_obj["user_id"] = record.user_id
        if hasattr(record, "project_id"):
            log_obj["project_id"] = record.project_id
        if hasattr(record, "duration"):
            log_obj["duration"] = record.duration
            
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)

def setup_structured_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    root_logger = logging.getLogger()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    
    # Remove existing default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # Console JSON output stream
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(console_handler)
    
    # 1. Main application.log
    app_handler = logging.FileHandler(os.path.join(log_dir, "application.log"), encoding="utf-8")
    app_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(app_handler)
    
    # 2. Critical error.log
    error_handler = logging.FileHandler(os.path.join(log_dir, "error.log"), encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)
    
    # 3. Security logs handler
    security_logger = logging.getLogger("security")
    security_logger.setLevel(logging.INFO)
    security_logger.propagate = False  # Avoid duplicates in parent logs
    sec_handler = logging.FileHandler(os.path.join(log_dir, "security.log"), encoding="utf-8")
    sec_handler.setFormatter(JSONFormatter())
    security_logger.addHandler(sec_handler)
    
    # 4. Background workers handler
    worker_logger = logging.getLogger("worker")
    worker_logger.setLevel(logging.INFO)
    worker_logger.propagate = False
    work_handler = logging.FileHandler(os.path.join(log_dir, "worker.log"), encoding="utf-8")
    work_handler.setFormatter(JSONFormatter())
    worker_logger.addHandler(work_handler)

# Initialize logging on load
setup_structured_logging()
