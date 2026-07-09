import os
import sys
import unittest
from fastapi.testclient import TestClient

# Add root folder to sys path for modular imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.main import app
from app.config import settings
from app.startup_validator import run_startup_validation
from app.projects.services.redis_service import redis_service
from app.projects.services.storage_service import storage_service
from app.projects.services.security_service import SecurityService

class TestDeploymentReadiness(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_config_loading(self):
        print("[TEST] Verifying configuration loader...")
        self.assertIsNotNone(settings.DATABASE_URL)
        self.assertIsNotNone(settings.UPLOAD_DIRECTORY)
        self.assertEqual(settings.LOG_LEVEL, "INFO")

    def test_startup_validator(self):
        print("[TEST] Running startup validator checks...")
        report = run_startup_validation()
        self.assertIn("status", report)
        self.assertIn("database", report)
        self.assertIn("redis", report)
        self.assertIn("storage", report)

    def test_redis_service(self):
        print("[TEST] Checking Redis service connection pool...")
        # Ping must return True (either via live redis or mock fallback)
        self.assertTrue(redis_service.ping())
        
        # Test key set/get/delete
        self.assertTrue(redis_service.set("test_key", "test_value"))
        self.assertEqual(redis_service.get("test_key"), "test_value")
        self.assertTrue(redis_service.delete("test_key"))

    def test_storage_service(self):
        print("[TEST] Testing StorageService abstraction...")
        test_path = "test_dir/readiness_marker.txt"
        test_content = b"readiness-center-v2.6"
        
        # Save file
        saved_path = storage_service.save_file(test_path, test_content)
        self.assertIsNotNone(saved_path)
        
        # Get file
        retrieved = storage_service.get_file(test_path)
        self.assertEqual(retrieved, test_content)
        
        # Delete file
        self.assertTrue(storage_service.delete_file(test_path))

    def test_security_validation(self):
        print("[TEST] Asserting security service filters and sanitizers...")
        # Path traversal prevention
        with self.assertRaises(Exception):
            SecurityService.validate_safe_path("app/temp_clones", "../../sensitive_file.txt")
            
        # Extension whitelist checks
        self.assertTrue(SecurityService.is_allowed_extension("main.py"))
        self.assertTrue(SecurityService.is_allowed_extension("Service.java"))
        self.assertFalse(SecurityService.is_allowed_extension("exploit.exe"))
        self.assertFalse(SecurityService.is_allowed_extension("malware.sh"))

    def test_health_routes(self):
        print("[TEST] Calling /health, /ready, and /metrics API endpoints...")
        
        # 1. Health
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("database", data)
        self.assertIn("redis", data)
        
        # 2. Ready
        response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        
        # 3. Metrics
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("projects", data)
        self.assertIn("analyses", data)
        self.assertIn("queue_size", data)
        self.assertIn("failure_rate", data)

if __name__ == "__main__":
    print("=" * 60)
    print("   AI ENGINE DEPLOYMENT READINESS SERVICE VERIFICATION UNIT TESTS   ")
    print("=" * 60)
    unittest.main()
