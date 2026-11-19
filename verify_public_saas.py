import sys
import os
import json
import hashlib
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import project setup
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.main import app
from app.config import settings
from app.auth.database.connection import SessionLocal, Base, engine
from app.auth.models.auth_models import User, ApiKey, NotificationPreference
from app.projects.models.project_models import Project, Analysis
from app.auth.services.auth_service import AuthService
from app.notifications.services.notification_service import NotificationService, sent_notifications_log

client = TestClient(app)

def setup_database():
    """Initializes schema and clears test databases."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def test_github_oauth_and_webhooks():
    print("Running Test 1: GitHub OAuth & Webhooks...")
    db = SessionLocal()
    try:
        # 1. Login fails closed when OAuth is unconfigured
        orig_cid = settings.GITHUB_CLIENT_ID
        settings.GITHUB_CLIENT_ID = ""
        try:
            login_resp = client.get("/auth/github/login", follow_redirects=False)
            assert login_resp.status_code == 503
        finally:
            settings.GITHUB_CLIENT_ID = orig_cid
        
        # 2. Callback rejects missing state/code
        cb_resp = client.get("/auth/github/callback?code=test", follow_redirects=False)
        assert cb_resp.status_code == 400
        
        # 3. Create test user and auth token for webhook tests
        user = User(
            username="saas_test_user",
            hashed_password=AuthService.hash_password("Pass123!"),
            role="developer",
            is_active=True,
            is_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        access_token, _, _, _ = AuthService.create_jwt_pair(user.id, user.role)
        
        # 4. Trigger push webhook
        proj = Project(name="Test Webhook Proj", repo_url="https://github.com/insights_tester/ai-engine-demo", user_id=user.id)
        db.add(proj)
        db.commit()
        db.refresh(proj)
        
        import hmac, hashlib
        original_secret = settings.GITHUB_WEBHOOK_SECRET
        settings.GITHUB_WEBHOOK_SECRET = "test_saas_webhook_secret"
        
        try:
            webhook_payload = {
                "ref": "refs/heads/main",
                "head_commit": {
                    "id": "commit_sha_12345",
                    "message": "Update code"
                },
                "repository": {
                    "clone_url": "https://github.com/insights_tester/ai-engine-demo"
                }
            }
            raw_payload = json.dumps(webhook_payload).encode("utf-8")
            sig = hmac.new(b"test_saas_webhook_secret", raw_payload, hashlib.sha256).hexdigest()
            
            webhook_resp = client.post(
                "/projects/github/webhook",
                content=raw_payload,
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "push",
                    "X-Hub-Signature-256": f"sha256={sig}"
                }
            )
            assert webhook_resp.status_code == 200
            wb_data = webhook_resp.json()
            assert wb_data["status"] == "triggered"
            assert wb_data["project_id"] == proj.id
        finally:
            settings.GITHUB_WEBHOOK_SECRET = original_secret
        
        print("[OK] Test 1 Passed successfully!")
    finally:
        db.close()

def test_unrestricted_self_hosted_projects():
    print("Running Test 2: Unrestricted Self-Hosted Project Creation...")
    db = SessionLocal()
    try:
        user = User(username="self_hosted_user", hashed_password=AuthService.hash_password("password"))
        db.add(user)
        db.commit()
        
        # Verify self-hosted user can create multiple projects without plan limitations
        for i in range(10):
            proj = Project(name=f"Project_{i}", user_id=user.id)
            db.add(proj)
        db.commit()
        
        user_projects = db.query(Project).filter(Project.user_id == user.id).all()
        assert len(user_projects) == 10
        print("[OK] Test 2 Passed successfully: Unrestricted project creation verified!")
    finally:
        db.close()

def test_notification_preferences():
    print("Running Test 3: Email Notification Preferences & Delivery...")
    db = SessionLocal()
    try:
        user = User(username="notified_user", hashed_password=AuthService.hash_password("password"))
        db.add(user)
        db.commit()
        
        access_token, _, _, _ = AuthService.create_jwt_pair(user.id, user.role)
        auth_header = {"Authorization": f"Bearer {access_token}"}
        
        # 1. Fetch default notifications preferences
        get_resp = client.get("/auth/notifications", headers=auth_header)
        assert get_resp.status_code == 200
        prefs = get_resp.json()
        assert prefs["email_analysis_completed"] is True
        
        # 2. Update preferences
        update_payload = {
            "email_analysis_completed": False,
            "email_fix_completed": True,
            "email_tests_completed": False
        }
        put_resp = client.put("/auth/notifications", json=update_payload, headers=auth_header)
        assert put_resp.status_code == 200
        
        # Confirm saved in DB
        db.refresh(user)
        prefs_rec = db.query(NotificationPreference).filter(NotificationPreference.user_id == user.id).first()
        assert prefs_rec.email_analysis_completed is False
        assert prefs_rec.email_fix_completed is True
        
        # 3. Verify notification filters
        # Clear mock delivery log
        sent_notifications_log.clear()
        
        # Sending analysis completed should fail to send due to preference set to False
        NotificationService.send_notification(db, user.id, "analysis_completed", "Analysis Run done", "Details...")
        assert len(sent_notifications_log) == 0
        
        # Sending fix completed should pass due to preference set to True
        NotificationService.send_notification(db, user.id, "fix_completed", "Fix applied", "Code refactored successfully.")
        assert len(sent_notifications_log) == 1
        assert sent_notifications_log[0]["event_type"] == "fix_completed"
        assert sent_notifications_log[0]["subject"] == "Fix applied"
        
        print("[OK] Test 3 Passed successfully!")
    finally:
        db.close()

def test_saas_analytics_summary():
    print("Running Test 4: SaaS Analytics Aggregation summary...")
    db = SessionLocal()
    try:
        # Create test records
        user = User(username="analyzer_user", hashed_password=AuthService.hash_password("password"))
        db.add(user)
        db.commit()
        
        p = Project(name="Analytics Proj", user_id=user.id)
        db.add(p)
        db.commit()
        
        # Create completed analysis run
        a = Analysis(project_id=p.id, status="completed", duration=5.8, source_type="manual")
        db.add(a)
        db.commit()
        
        access_token, _, _, _ = AuthService.create_jwt_pair(user.id, user.role)
        
        res = client.get("/analytics/summary", headers={"Authorization": f"Bearer {access_token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["total_projects"] >= 1
        assert data["total_analyses"] >= 1
        assert data["avg_review_time_seconds"] > 0
        assert len(data["common_findings"]) > 0
        assert "Go" in data["language_distribution"]
        
        print("[OK] Test 4 Passed successfully!")
    finally:
        db.close()

def test_admin_portal_endpoints():
    print("Running Test 5: Administrative Stats & Suspensions...")
    db = SessionLocal()
    try:
        # Create regular user and admin user
        regular = User(username="regular_usr", hashed_password=AuthService.hash_password("password"), role="user")
        admin = User(username="admin_usr", hashed_password=AuthService.hash_password("password"), role="admin")
        db.add_all([regular, admin])
        db.commit()
        
        reg_token, _, _, _ = AuthService.create_jwt_pair(regular.id, regular.role)
        admin_token, _, _, _ = AuthService.create_jwt_pair(admin.id, admin.role)
        
        # 1. Regular user trying to fetch admin stats should get 403
        bad_res = client.get("/admin/stats", headers={"Authorization": f"Bearer {reg_token}"})
        assert bad_res.status_code == 403
        
        # 2. Admin should get stats successfully
        good_res = client.get("/admin/stats", headers={"Authorization": f"Bearer {admin_token}"})
        assert good_res.status_code == 200
        stats = good_res.json()
        assert stats["total_users"] >= 2
        assert "errors_list" in stats
        
        # 3. List users
        users_res = client.get("/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert users_res.status_code == 200
        users_list = users_res.json()
        assert len(users_list) >= 2
        
        # 4. Suspend user status
        toggle_res = client.post(f"/admin/users/{regular.id}/toggle-status", headers={"Authorization": f"Bearer {admin_token}"})
        assert toggle_res.status_code == 200
        
        db.refresh(regular)
        assert regular.is_active is False
        
        # Suspended user login should now fail with 403
        suspended_login = client.get("/projects", headers={"Authorization": f"Bearer {reg_token}"})
        assert suspended_login.status_code == 403
        
        print("[OK] Test 5 Passed successfully!")
    finally:
        db.close()

def test_public_api_v1_and_api_keys():
    print("Running Test 6: API Keys generation and Public REST API v1...")
    db = SessionLocal()
    try:
        user = User(username="developer_usr", hashed_password=AuthService.hash_password("password"))
        db.add(user)
        db.commit()
        
        access_token, _, _, _ = AuthService.create_jwt_pair(user.id, user.role)
        auth_header = {"Authorization": f"Bearer {access_token}"}
        
        # 1. Generate new API Key
        gen_res = client.post("/auth/api-key?name=TerminalToken", headers=auth_header)
        assert gen_res.status_code == 200
        key_data = gen_res.json()
        assert "api_key" in key_data
        raw_key = key_data["api_key"]
        
        # 2. Access projects using public REST API header
        v1_headers = {"X-API-KEY": raw_key}
        v1_res = client.get("/api/v1/projects", headers=v1_headers)
        assert v1_res.status_code == 200
        projects_list = v1_res.json()
        assert len(projects_list) == 0
        
        # 3. Create project via public API
        create_res = client.post("/api/v1/projects?name=CLI_Project", headers=v1_headers)
        assert create_res.status_code == 200
        proj_data = create_res.json()
        assert proj_data["name"] == "CLI_Project"
        
        # Confirm listed now
        v1_res_2 = client.get("/api/v1/projects", headers=v1_headers)
        assert len(v1_res_2.json()) == 1
        
        print("[OK] Test 6 Passed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    print("==================================================")
    print("Starting AI Engine Public SaaS Launch Verification Suite")
    print("==================================================")
    setup_database()
    
    test_github_oauth_and_webhooks()
    test_unrestricted_self_hosted_projects()
    test_notification_preferences()
    test_saas_analytics_summary()
    test_admin_portal_endpoints()
    test_public_api_v1_and_api_keys()
    
    print("==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")
    sys.exit(0)
