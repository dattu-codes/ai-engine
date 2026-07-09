import json
import uuid
import time
import logging
import threading
import asyncio
from app.projects.services.redis_service import redis_service
from app.config import settings

logger = logging.getLogger("worker_service")

# Task registry for mapping string names to executable functions
_task_registry = {}

def register_task(name):
    def decorator(func):
        _task_registry[name] = func
        return func
    return decorator

def enqueue_job(task_name: str, *args, **kwargs) -> str:
    job_id = str(uuid.uuid4())
    job_info = {
        "job_id": job_id,
        "task_name": task_name,
        "args": args,
        "kwargs": kwargs,
        "status": "PENDING",
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
        "error": None
    }
    
    # Store job status details in Redis
    redis_service.set(f"job:{job_id}", json.dumps(job_info), expire=86400)
    
    # Push job_id into task queue
    redis_service.client.rpush("task_queue", job_id)
    
    # Track metrics
    redis_service.client.set("metrics:last_queued_job", job_id)
    
    logger.info(f"Enqueued background job {job_id} for task '{task_name}'")
    return job_id

def run_async_task(coro):
    """Helper to run coroutines from synchronous threads safely."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # If the loop is already running (e.g. inside FastAPI thread), schedule safely
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    else:
        return loop.run_until_complete(coro)

def worker_loop():
    logger.info("Background job worker loop started.")
    # Track worker registration count
    redis_service.client.incr("metrics:active_workers")
    
    while True:
        try:
            # Pop job from Redis queue blocking-like
            res = redis_service.client.blpop("task_queue", timeout=2)
            if not res:
                continue
            
            _, job_id = res
            job_data = redis_service.get(f"job:{job_id}")
            if not job_data:
                continue
                
            job_info = json.loads(job_data)
            task_name = job_info["task_name"]
            args = job_info["args"]
            kwargs = job_info["kwargs"]
            
            # Transition to RUNNING
            job_info["status"] = "RUNNING"
            job_info["started_at"] = time.time()
            redis_service.set(f"job:{job_id}", json.dumps(job_info), expire=86400)
            
            task_func = _task_registry.get(task_name)
            if not task_func:
                raise ValueError(f"Task '{task_name}' is not registered.")
            
            logger.info(f"Executing background job {job_id} (task '{task_name}')")
            
            # Execute task
            start_time = time.time()
            task_func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Transition to COMPLETED
            job_info["status"] = "COMPLETED"
            job_info["finished_at"] = time.time()
            redis_service.set(f"job:{job_id}", json.dumps(job_info), expire=86400)
            
            # Record execution metrics
            redis_service.client.incr("metrics:total_jobs_run")
            redis_service.client.set("metrics:last_success_duration", str(duration))
            
            logger.info(f"Job {job_id} completed successfully in {duration:.2f}s")
            
        except Exception as e:
            logger.error(f"Error executing background job: {e}")
            redis_service.client.incr("metrics:total_jobs_failed")
            try:
                if 'job_id' in locals():
                    job_data = redis_service.get(f"job:{job_id}")
                    if job_data:
                        job_info = json.loads(job_data)
                        job_info["status"] = "FAILED"
                        job_info["finished_at"] = time.time()
                        job_info["error"] = str(e)
                        redis_service.set(f"job:{job_id}", json.dumps(job_info), expire=86400)
            except Exception as inner_e:
                logger.error(f"Failed to record FAILED status for job {job_id}: {inner_e}")

def start_worker():
    t = threading.Thread(target=worker_loop, daemon=True)
    t.start()
    logger.info("Background job worker thread successfully launched in background daemon mode.")
