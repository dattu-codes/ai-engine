import sys
import os
import json
import hashlib
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import project setup
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.main import app
from app.auth.database.connection import SessionLocal, Base, engine
from app.auth.models.auth_models import User, ApiKey, NotificationPreference
from app.projects.models.project_models import Project, Analysis
from app.auth.services.auth_service import AuthService
from app.billing.services.billing_service import BillingService
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
        # 1. Login redirect
        login_resp = client.get("/auth/github/login?mock=true", follow_redirects=False)
        assert login_resp.status_code == 307
        assert "auth/github/callback" in login_resp.headers["location"]
        
        # 2. Callback code exchange
        callback_resp = client.get("/auth/github/callback?code=mock_oauth_code", follow_redirects=False)
        assert callback_resp.status_code == 307
        redirect_url = callback_resp.headers["location"]
        assert "access_token=" in redirect_url
        assert "mock_github_user" in redirect_url
        
        # Get tokens from redirected URL fragment
        url_hash = redirect_url.split("#")[1]
        params = dict(x.split("=") for x in url_hash.split("&"))
        access_token = params["access_token"]
        
        # 3. Retrieve repositories
        repos_resp = client.get("/auth/github/repositories", headers={"Authorization": f"Bearer {access_token}"})
        assert repos_resp.status_code == 200
        repos = repos_resp.json()
        assert len(repos) > 0
        assert repos[0]["name"] == "ai-engine-demo"
        
        # 4. Trigger push webhook
        # Create project first
        user = db.query(User).filter(User.username == "mock_github_user").first()
        proj = Project(name="Test Webhook Proj", repo_url="https://github.com/insights_tester/ai-engine-demo", user_id=user.id)
        db.add(proj)
        db.commit()
        db.refresh(proj)
        
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
        
        webhook_resp = client.post(
            "/projects/github/webhook",
            json=webhook_payload,
            headers={"X-GitHub-Event": "push"}
        )
        assert webhook_resp.status_code == 200
        wb_data = webhook_resp.json()
        assert wb_data["status"] == "triggered"
        assert wb_data["project_id"] == proj.id
        
        print("[OK] Test 1 Passed successfully!")
    finally:
        db.close()

def test_stripe_billing_limits():
    print("Running Test 2: Stripe Billing Plan Limits & Sessions...")
    db = SessionLocal()
    try:
        # Create users on different plans
        free_user = User(username="free_user", hashed_password=AuthService.hash_password("password"), billing_plan="Free")
        pro_user = User(username="pro_user", hashed_password=AuthService.hash_password("password"), billing_plan="Pro")
        db.add_all([free_user, pro_user])
        db.commit()
        
        # 1. Test limits on projects
        # Free allows 1, Pro allows 5
        # Under Free: adding 1st project should pass, 2nd should fail
        # Pro allows up to 5 projects
        proj1 = Project(name="Free Proj 1", user_id=free_user.id)
        db.add(proj1)
        db.commit()
        
        # Gating project check for free user (should raise HTTP 402)
        try:
            BillingService.check_billing_limit(db, free_user, "projects")
            assert False, "Free user did not fail creating > 1 project"
        except Exception as e:
            assert e.status_code == 402
            assert "allows a maximum of 1 projects" in e.detail

        # Gating project check for pro user (should pass)
        for i in range(4):
            db.add(Project(name=f"Pro Proj {i}", user_id=pro_user.id))
        db.commit()
        
        # Pro user has 4, checking limit should pass
        BillingService.check_billing_limit(db, pro_user, "projects")
        
        # Pro user adds 5th, checking limit should raise 402 next time
        db.add(Project(name="Pro Proj 5", user_id=pro_user.id))
        db.commit()
        try:
            BillingService.check_billing_limit(db, pro_user, "projects")
            assert False, "Pro user did not fail creating > 5 projects"
        except Exception as e:
            assert e.status_code == 402
            assert "allows a maximum of 5 projects" in e.detail
            
        # 2. Test limits on files per review
        # Free allows max 3 files
        BillingService.check_billing_limit(db, free_user, "files", file_count=3)
        try:
            BillingService.check_billing_limit(db, free_user, "files", file_count=4)
            assert False, "Free user did not fail scanning > 3 files"
        except Exception as e:
            assert e.status_code == 402
            assert "allows a maximum of 3 source files" in e.detail
            
        # Pro allows max 20 files
        BillingService.check_billing_limit(db, pro_user, "files", file_count=20)
        try:
            BillingService.check_billing_limit(db, pro_user, "files", file_count=21)
            assert False, "Pro user did not fail scanning > 20 files"
        except Exception as e:
            assert e.status_code == 402
            
        # 3. Test Stripe Session mocks
        access_token, _, _, _ = AuthService.create_jwt_pair(pro_user.id, pro_user.role)
        auth_header = {"Authorization": f"Bearer {access_token}"}
        
        checkout_resp = client.post("/billing/checkout-session?plan_type=pro", headers=auth_header)
        assert checkout_resp.status_code == 200
        assert "checkout_url" in checkout_resp.json()
        assert "mock-activate" in checkout_resp.json()["checkout_url"]
        
        portal_resp = client.post("/billing/portal-session", headers=auth_header)
        assert portal_resp.status_code == 200
        assert "portal_url" in portal_resp.json()
        
        print("[OK] Test 2 Passed successfully!")
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
    test_stripe_billing_limits()
    test_notification_preferences()
    test_saas_analytics_summary()
    test_admin_portal_endpoints()
    test_public_api_v1_and_api_keys()
    
    print("==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")
    sys.exit(0)
