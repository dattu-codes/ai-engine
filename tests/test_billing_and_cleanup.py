import os
from app.main import app

def test_no_billing_tab_or_stripe_in_html():
    """Verify index.html contains no Billing & Plans tab or stripe references."""
    index_html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "static", "index.html")
    assert os.path.exists(index_html_path)
    with open(index_html_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Billing & Plans" not in content, "Found 'Billing & Plans' tab in index.html"
    assert "data-tab=\"settings-billing\"" not in content, "Found settings-billing tab in index.html"
    assert "stripe" not in content.lower(), "Found stripe reference in index.html"


def test_no_stripe_or_billing_in_app_js():
    """Verify app.js contains no stripe checkout or billing integration references."""
    app_js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "static", "app.js")
    assert os.path.exists(app_js_path)
    with open(app_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "stripe" not in content.lower(), "Found stripe reference in app.js"
    assert "settings-billing" not in content, "Found settings-billing in app.js"


def test_no_billing_or_stripe_routes_in_fastapi():
    """Verify FastAPI application has no stripe or billing routes registered."""
    route_paths = [getattr(route, "path", "") for route in app.routes]
    for path in route_paths:
        if path:
            assert "billing" not in path.lower(), f"Found billing route: {path}"
            assert "stripe" not in path.lower(), f"Found stripe route: {path}"


def test_scratch_folder_and_run_bat_deleted():
    """Verify scratch/ folder and run.bat have been removed from the repository."""
    root_dir = os.path.dirname(os.path.dirname(__file__))
    scratch_dir = os.path.join(root_dir, "scratch")
    run_bat = os.path.join(root_dir, "run.bat")

    assert not os.path.exists(scratch_dir), "scratch/ folder still exists in repository"
    assert not os.path.exists(run_bat), "run.bat still exists in repository"
