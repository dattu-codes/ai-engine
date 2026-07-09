import json
import logging
from app.config import settings

logger = logging.getLogger("redis_service")

class MockRedis:
    """Mock Redis backend that runs in memory when Redis is offline or during local testing."""
    def __init__(self):
        self._store = {}
        self._queues = {}
        logger.info("Initialized in-memory Mock Redis service fallback.")

    def ping(self):
        return True

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, ex=None):
        self._store[key] = value
        return True

    def delete(self, key):
        if key in self._store:
            del self._store[key]
            return 1
        return 0

    def rpush(self, name, value):
        if name not in self._queues:
            self._queues[name] = []
        self._queues[name].append(value)
        return len(self._queues[name])

    def lpop(self, name):
        if name in self._queues and len(self._queues[name]) > 0:
            return self._queues[name].pop(0)
        return None

    def blpop(self, keys, timeout=0):
        import time
        start_time = time.time()
        names = [keys] if isinstance(keys, str) else keys
        while True:
            for name in names:
                val = self.lpop(name)
                if val is not None:
                    return name, val
            if timeout > 0 and (time.time() - start_time) >= timeout:
                return None
            time.sleep(0.1)

    def incr(self, key, amount=1):
        val = self._store.get(key, 0)
        try:
            val = int(val) + amount
        except (ValueError, TypeError):
            val = amount
        self._store[key] = str(val)
        return val

    def llen(self, name):
        if name in self._queues:
            return len(self._queues[name])
        return 0

    def pipeline(self):
        return MockPipeline(self)

class MockPipeline:
    def __init__(self, mock_redis):
        self.mock_redis = mock_redis
        
    def incr(self, key, amount=1):
        self.mock_redis.incr(key, amount)
        return self
        
    def expire(self, key, time_secs):
        return self
        
    def execute(self):
        return []

class RedisService:

    def __init__(self):
        self.client = None
        self.is_mock = False
        try:
            import redis
            # Connection pooling configuration
            self.pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)
            self.client = redis.Redis(connection_pool=self.pool)
            self.client.ping()
            logger.info("Connected to Redis server successfully.")
        except Exception as e:
            if settings.APP_ENVIRONMENT == "production":
                raise e
            self.client = MockRedis()
            self.is_mock = True

    def ping(self) -> bool:
        try:
            return self.client.ping()
        except Exception:
            return False

    def get(self, key: str):
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Redis get failed: {e}")
            return None

    def set(self, key: str, value: str, expire: int = None) -> bool:
        try:
            self.client.set(key, value, ex=expire)
            return True
        except Exception as e:
            logger.error(f"Redis set failed: {e}")
            return False

    def delete(self, key: str) -> bool:
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete failed: {e}")
            return False

    def cache_ai_response(self, key: str, data: dict, expire: int = 3600) -> bool:
        return self.set(f"ai_response:{key}", json.dumps(data), expire=expire)

    def get_cached_ai_response(self, key: str) -> dict:
        val = self.get(f"ai_response:{key}")
        if val:
            try:
                return json.loads(val)
            except Exception:
                return None
        return None

redis_service = RedisService()
