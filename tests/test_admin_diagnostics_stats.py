import os
import inspect
from fastapi.testclient import TestClient
from app.main import app
from app.auth.database.connection import SessionLocal
from app.auth.models.auth_models import User
from app.auth.services.auth_service import AuthService
from app.projects.models.project_models import ActivityLog, AnalysisFile
from app.projects.services.redis_service import redis_service
from app.projects.services.diagnostics_service import DiagnosticsService
import app.admin.routes.admin_routes as ar_module

client = TestClient(app)

def get_admin_token():
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == "admin_stats_test").first()
        if not admin_user:
            admin_user = User(
                username="admin_stats_test",
                hashed_password=AuthService.hash_password("adminpass123"),
                role="admin",
                is_active=True,
                is_verified=True
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
        access_token, _, _, _ = AuthService.create_jwt_pair(admin_user.id, admin_user.role)
        return access_token
    finally:
        db.close()


def test_no_hardcoded_fake_stats_or_mock_logs_in_source():
    """Verify admin_routes.py contains no hardcoded 102400 storage or 2026-07-09 mock logs."""
    source = inspect.getsource(ar_module)
    assert "102400" not in source, "Found hardcoded 102400 in admin_routes.py"
    assert "2026-07-09" not in source, "Found fake 2026-07-09 timestamp in admin_routes.py"
    assert "High Redis connection latency detected." not in source, "Found fake log string in admin_routes.py"


def test_admin_stats_reports_degraded_when_redis_is_mock():
    """Verify /admin/stats reports 'Degraded' when Redis is on in-memory mock fallback."""
    token = get_admin_token()
    orig_is_mock = getattr(redis_service, "is_mock", False)
    redis_service.is_mock = True

    try:
        res = client.get("/admin/stats", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["integrations"]["redis"] == "Degraded"
        assert data["storage_utilized_bytes"] != 102400 or data["total_files"] > 0
        # Check logs do not contain fake 2026-07-09 logs
        for log in data.get("errors_list", []):
            assert "2026-07-09" not in str(log.get("timestamp"))
    finally:
        redis_service.is_mock = orig_is_mock


def test_diagnostics_service_reports_degraded_when_redis_is_mock():
    """Verify DiagnosticsService reports Redis status as 'Degraded' on mock fallback."""
    db = SessionLocal()
    orig_is_mock = getattr(redis_service, "is_mock", False)
    redis_service.is_mock = True

    try:
        diag = DiagnosticsService.run_diagnostics(db)
        assert diag["checks"]["redis"]["status"] == "Degraded"
    finally:
        redis_service.is_mock = orig_is_mock
        db.close()


def test_health_and_metrics_reports_degraded_redis_and_real_latency():
    """Verify /health returns 'Degraded' for Redis on in-memory mock, and /metrics has real values without fake 4.5s."""
    orig_is_mock = getattr(redis_service, "is_mock", False)
    redis_service.is_mock = True

    try:
        health_resp = client.get("/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert health_data["redis"] == "Degraded"

        metrics_resp = client.get("/metrics")
        assert metrics_resp.status_code == 200
        metrics_data = metrics_resp.json()
        assert metrics_data["cache_hits"] != 182 or metrics_data["cache_misses"] != 27
        # Processing time must be a real float or "N/A"
        avg_time = metrics_data["average_processing_time"]
        assert isinstance(avg_time, (int, float)) or avg_time == "N/A"
        # Failure rate must be "N/A" when no jobs, or a real percentage
        fail_rate = metrics_data["failure_rate"]
        assert fail_rate == "N/A" or (isinstance(fail_rate, str) and fail_rate.endswith("%"))
    finally:
        redis_service.is_mock = orig_is_mock


def test_failure_rate_shows_na_when_no_job_data():
    """Verify /metrics returns 'N/A' for failure_rate when there is no job data, not '0.0%'."""
    from unittest.mock import patch

    with patch("app.projects.services.redis_service.redis_service.client.get", return_value=None):
        with patch("sqlalchemy.orm.Query.count", return_value=0):
            res = client.get("/metrics")
            assert res.status_code == 200
            data = res.json()
            assert data["failure_rate"] == "N/A"
            assert data["failure_rate"] != "0.0%"

