import os
import sys
import time
import json
import socket
import urllib.request
import threading
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.path.join(REPO_ROOT, "ui-check")

# Enforce development environment and bypass any system proxies for local test server
os.environ["APP_ENVIRONMENT"] = "development"
for _k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start_uvicorn(port):
    import uvicorn
    # Make sure repo root is in python path
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)

    config = uvicorn.Config("main:app", host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    return server


def wait_for_server(port, timeout=30):
    start = time.time()
    url = f"http://127.0.0.1:{port}/dashboard"
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def create_and_login_user(port):
    username = f"dev_qa_user_{int(time.time())}"
    password = "DevPassword123!"

    # 1. Sign up
    signup_url = f"http://127.0.0.1:{port}/auth/signup"
    signup_payload = json.dumps({
        "username": username,
        "password": password,
        "role": "admin"
    }).encode("utf-8")

    req = urllib.request.Request(
        signup_url,
        data=signup_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        signup_res = json.loads(resp.read().decode("utf-8"))

    # 2. Login
    login_url = f"http://127.0.0.1:{port}/auth/login"
    login_payload = json.dumps({
        "username": username,
        "password": password
    }).encode("utf-8")

    req = urllib.request.Request(
        login_url,
        data=login_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        login_res = json.loads(resp.read().decode("utf-8"))

    access_token = login_res.get("access_token")
    refresh_token = login_res.get("refresh_token")

    if not access_token or not refresh_token:
        raise RuntimeError(f"Authentication failed to return tokens: {login_res}")

    print(f"Created and authenticated throwaway user '{username}'")
    return username, access_token, refresh_token


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    port = get_free_port()
    print(f"Starting local development server on port {port}...")
    server = start_uvicorn(port)

    if not wait_for_server(port):
        raise RuntimeError(f"Server failed to start on port {port} within timeout.")
    print(f"Local server is responding at http://127.0.0.1:{port}")

    username, access_token, refresh_token = create_and_login_user(port)

    dashboard_url = f"http://127.0.0.1:{port}/dashboard"

    widths = [
        ("1920", 1920, 1080),
        ("1280", 1280, 800),
        ("390", 390, 844),
    ]

    themes = ["dark", "light"]

    dashboard_views = [
        "dashboard",
        "deployment",
        "workspaces",
        "settings-llm",
        "settings-notifications",
        "settings-api",
        "settings-org"
    ]

    total_expected = len(widths) * len(themes) * (len(dashboard_views) + 1)
    captured = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for width_name, w, h in widths:
            for theme in themes:
                # ------------------------------------------------------------------
                # A. CAPTURE UNAUTHENTICATED LOGIN PAGE (verify login fixes & mobile logo)
                # ------------------------------------------------------------------
                login_context = browser.new_context(viewport={"width": w, "height": h})
                login_page = login_context.new_page()
                login_page.goto(dashboard_url, wait_until="networkidle")

                # Apply theme
                login_page.evaluate(f"""() => {{
                    const isLight = '{theme}' === 'light';
                    if (isLight) {{
                        document.documentElement.classList.add('light-theme');
                        document.body.classList.add('light-theme');
                        document.documentElement.setAttribute('data-theme', 'light');
                        document.body.setAttribute('data-theme', 'light');
                    }} else {{
                        document.documentElement.classList.remove('light-theme');
                        document.body.classList.remove('light-theme');
                        document.documentElement.setAttribute('data-theme', 'dark');
                        document.body.setAttribute('data-theme', 'dark');
                    }}
                }}""")

                login_page.wait_for_timeout(100)
                login_shot = os.path.join(OUTPUT_DIR, f"login_{theme}_{width_name}px.png")
                login_page.screenshot(path=login_shot, full_page=False)
                captured += 1
                print(f"[{captured}/{total_expected}] Captured {os.path.basename(login_shot)}")
                login_context.close()

                # ------------------------------------------------------------------
                # B. CAPTURE AUTHENTICATED REAL APP PAGES
                # ------------------------------------------------------------------
                app_context = browser.new_context(viewport={"width": w, "height": h})
                app_page = app_context.new_page()

                # Open dashboard
                app_page.goto(dashboard_url, wait_until="networkidle")

                # Store tokens in localStorage exactly as app.js does
                app_page.evaluate(f"""() => {{
                    localStorage.setItem('access_token', '{access_token}');
                    localStorage.setItem('refresh_token', '{refresh_token}');
                    localStorage.setItem('theme', '{theme}');
                }}""")

                # Reload with authenticated tokens stored
                app_page.goto(dashboard_url, wait_until="networkidle")

                # Trigger session check and theme apply
                app_page.evaluate(f"""() => {{
                    const isLight = '{theme}' === 'light';
                    if (isLight) {{
                        document.documentElement.classList.add('light-theme');
                        document.body.classList.add('light-theme');
                        document.documentElement.setAttribute('data-theme', 'light');
                        document.body.setAttribute('data-theme', 'light');
                    }} else {{
                        document.documentElement.classList.remove('light-theme');
                        document.body.classList.remove('light-theme');
                        document.documentElement.setAttribute('data-theme', 'dark');
                        document.body.setAttribute('data-theme', 'dark');
                    }}
                    if (typeof checkUserSession === 'function') {{
                        checkUserSession();
                    }}
                    if (window.updateThresholdTrack) {{
                        const slider = document.getElementById('threshold');
                        if (slider) window.updateThresholdTrack(slider.value);
                    }}
                }}""")

                # Wait for authentication to resolve and hide auth overlay
                app_page.wait_for_timeout(300)

                # STRICT ASSERTION: verify dashboard-only element exists and auth overlay is hidden
                auth_overlay_hidden = app_page.evaluate("() => document.getElementById('auth-overlay').classList.contains('hidden')")
                has_sidebar = app_page.evaluate("() => !!document.getElementById('sidebar-panel')")
                has_threshold = app_page.evaluate("() => !!document.getElementById('threshold')")

                if not auth_overlay_hidden:
                    # Give it one more short wait
                    app_page.wait_for_timeout(500)
                    auth_overlay_hidden = app_page.evaluate("() => document.getElementById('auth-overlay').classList.contains('hidden')")

                if not auth_overlay_hidden:
                    raise AssertionError(f"FATAL: #auth-overlay is NOT hidden! Authenticated capture failed for {theme} {width_name}px.")

                if not (has_sidebar and has_threshold):
                    raise AssertionError(f"FATAL: Dashboard-only elements (#sidebar-panel: {has_sidebar}, #threshold: {has_threshold}) are missing!")

                for view in dashboard_views:
                    if view.startswith("settings-"):
                        tab_key = view.replace("settings-", "")
                        tab_id_map = {
                            "llm": ("settings-tab-llm-btn", "settings-pane-llm"),
                            "notifications": ("settings-tab-notifications-btn", "settings-pane-notifications"),
                            "api": ("settings-tab-api-btn", "settings-pane-api"),
                            "org": ("settings-tab-org-btn", "settings-pane-org")
                        }
                        btn_id, pane_id = tab_id_map[tab_key]

                        app_page.evaluate(f"""() => {{
                            const modal = document.getElementById('settings-modal');
                            if (modal) modal.classList.remove('hidden');

                            ['settings-tab-llm-btn', 'settings-tab-notifications-btn', 'settings-tab-api-btn', 'settings-tab-org-btn'].forEach(id => {{
                                const b = document.getElementById(id);
                                if (b) b.classList.remove('active');
                            }});
                            ['settings-pane-llm', 'settings-pane-notifications', 'settings-pane-api', 'settings-pane-org'].forEach(id => {{
                                const p = document.getElementById(id);
                                if (p) p.style.display = 'none';
                            }});

                            const targetBtn = document.getElementById('{btn_id}');
                            if (targetBtn) targetBtn.classList.add('active');
                            const targetPane = document.getElementById('{pane_id}');
                            if (targetPane) targetPane.style.display = 'block';
                        }}""")
                    else:
                        pane_id = {
                            "dashboard": "view-dashboard",
                            "deployment": "view-deployment",
                            "workspaces": "view-workspace"
                        }[view]

                        app_page.evaluate(f"""() => {{
                            const modal = document.getElementById('settings-modal');
                            if (modal) modal.classList.add('hidden');

                            document.querySelectorAll('.view-pane').forEach(p => {{
                                if (p.id === '{pane_id}') {{
                                    p.classList.add('active');
                                    p.style.display = 'block';
                                }} else {{
                                    p.classList.remove('active');
                                    p.style.display = 'none';
                                }}
                            }});
                        }}""")

                    app_page.wait_for_timeout(100)

                    # Re-verify dashboard element is still in DOM before saving
                    assert app_page.evaluate("() => !!document.getElementById('threshold')"), f"DASHBOARD ELEMENT MISSING BEFORE SAVING {view}"

                    filename = f"{view}_{theme}_{width_name}px.png"
                    filepath = os.path.join(OUTPUT_DIR, filename)
                    app_page.screenshot(path=filepath, full_page=False)
                    captured += 1
                    print(f"[{captured}/{total_expected}] Captured authenticated {filename}")

                app_context.close()

        browser.close()

    server.should_exit = True
    print(f"\nAll {captured} screenshots successfully captured in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
