import os
import sys
import time
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_DIR = os.path.join(REPO_ROOT, "app")
OUTPUT_DIR = os.path.join(REPO_ROOT, "ui-check")


class AppRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=APP_DIR, **kwargs)

    def log_message(self, format, *args):
        # Silence HTTP server logs
        pass


def run_server(server):
    server.serve_forever()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Start ephemeral HTTP server serving app directory
    server = HTTPServer(('127.0.0.1', 0), AppRequestHandler)
    port = server.server_port
    server_thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    server_thread.start()
    print(f"Started local static server on http://127.0.0.1:{port}")

    url = f"http://127.0.0.1:{port}/static/index.html"

    widths = [
        ("1920", 1920, 1080),
        ("1280", 1280, 800),
        ("390", 390, 844),
    ]

    themes = ["dark", "light"]

    views = [
        "dashboard",
        "deployment",
        "workspaces",
        "settings-llm",
        "settings-notifications",
        "settings-api",
        "settings-org"
    ]

    total = len(widths) * len(themes) * len(views)
    count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for width_name, w, h in widths:
            page.set_viewport_size({"width": w, "height": h})

            for theme in themes:
                page.goto(url, wait_until="networkidle")

                # Apply theme
                page.evaluate(f"""() => {{
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
                    localStorage.setItem('theme', '{theme}');
                    if (window.updateThresholdTrack) {{
                        const slider = document.getElementById('threshold');
                        if (slider) window.updateThresholdTrack(slider.value);
                    }}
                }}""")

                # Make sure sidebar user profile info is visible for screenshot verification
                page.evaluate("""() => {
                    const authHeader = document.getElementById('header-auth');
                    if (authHeader) authHeader.style.display = 'flex';
                    const nameSpan = document.getElementById('user-display-name');
                    if (nameSpan) nameSpan.textContent = 'Dattatreya Teella';
                    const roleSpan = document.getElementById('user-display-role');
                    if (roleSpan) roleSpan.textContent = 'Lead AI Architect';
                }""")

                for view in views:
                    if view.startswith("settings-"):
                        # Open Settings Modal and switch to the specific tab
                        tab_key = view.replace("settings-", "")
                        tab_id_map = {
                            "llm": ("settings-tab-llm-btn", "settings-pane-llm"),
                            "notifications": ("settings-tab-notifications-btn", "settings-pane-notifications"),
                            "api": ("settings-tab-api-btn", "settings-pane-api"),
                            "org": ("settings-tab-org-btn", "settings-pane-org")
                        }
                        btn_id, pane_id = tab_id_map[tab_key]

                        page.evaluate(f"""() => {{
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
                        # Switch to standard dashboard view pane and hide settings modal
                        pane_id = {
                            "dashboard": "view-dashboard",
                            "deployment": "view-deployment",
                            "workspaces": "view-workspace"
                        }[view]

                        page.evaluate(f"""() => {{
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

                    # Wait a moment for layout stabilization
                    page.wait_for_timeout(100)

                    filename = f"{view}_{theme}_{width_name}px.png"
                    filepath = os.path.join(OUTPUT_DIR, filename)
                    page.screenshot(path=filepath, full_page=False)
                    count += 1
                    print(f"[{count}/{total}] Saved {filename}")

        browser.close()

    server.shutdown()
    print(f"\nAll {count} screenshots captured successfully in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
