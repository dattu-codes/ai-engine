import os
import sys
import time
import json
import socket
import urllib.request
import threading
import math
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
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
    username = f"inspect_user_{int(time.time())}"
    password = "DevPassword123!"

    signup_url = f"http://127.0.0.1:{port}/auth/signup"
    signup_payload = json.dumps({"username": username, "password": password, "role": "admin"}).encode("utf-8")
    req = urllib.request.Request(signup_url, data=signup_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        json.loads(resp.read().decode("utf-8"))

    login_url = f"http://127.0.0.1:{port}/auth/login"
    login_payload = json.dumps({"username": username, "password": password}).encode("utf-8")
    req = urllib.request.Request(login_url, data=login_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        login_res = json.loads(resp.read().decode("utf-8"))

    return username, login_res["access_token"], login_res["refresh_token"]


def lum(r, g, b):
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def parse_rgb(rgb_str):
    import re
    m = re.search(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', rgb_str or "")
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def contrast_ratio(c1_str, c2_str):
    c1 = parse_rgb(c1_str)
    c2 = parse_rgb(c2_str)
    if not c1 or not c2:
        return 0.0
    l1 = lum(*c1)
    l2 = lum(*c2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def run_checks():
    port = get_free_port()
    server = start_uvicorn(port)
    if not wait_for_server(port):
        raise RuntimeError("Server failed to start")

    username, access_token, refresh_token = create_and_login_user(port)
    dashboard_url = f"http://127.0.0.1:{port}/dashboard"

    findings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for width, height in [(1920, 1080), (1280, 800), (390, 844)]:
            for theme in ["dark", "light"]:
                tag = f"[{theme.upper()} {width}px]"

                # ------------------------------------------------------------------
                # 1. LOGIN PAGE CHECK
                # ------------------------------------------------------------------
                login_ctx = browser.new_context(viewport={"width": width, "height": height})
                login_p = login_ctx.new_page()
                login_p.goto(dashboard_url, wait_until="networkidle")

                login_p.evaluate(f"""() => {{
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
                login_p.wait_for_timeout(100)

                # Sign In button text color must be white
                auth_submit_info = login_p.evaluate("""() => {
                    const btn = document.getElementById('btn-auth-submit');
                    if (!btn) return null;
                    const st = window.getComputedStyle(btn);
                    return { text: btn.innerText.trim(), color: st.color, bg: st.backgroundColor };
                }""")
                if auth_submit_info:
                    cr = contrast_ratio(auth_submit_info['color'], auth_submit_info['bg'])
                    is_white = "255, 255, 255" in auth_submit_info['color']
                    findings.append(f"{tag} Sign In button: text='{auth_submit_info['text']}', color={auth_submit_info['color']}, bg={auth_submit_info['bg']}, is_white={is_white}, contrast={cr:.2f}:1")

                # Mobile brand
                if width <= 900:
                    mobile_brand = login_p.evaluate("""() => {
                        const el = document.querySelector('.auth-mobile-brand');
                        if (!el) return null;
                        const st = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return { display: st.display, w: r.width, h: r.height, text: el.innerText.trim() };
                    }""")
                    findings.append(f"{tag} Mobile brand: {mobile_brand}")

                login_ctx.close()

                # ------------------------------------------------------------------
                # 2. AUTHENTICATED DASHBOARD CHECKS
                # ------------------------------------------------------------------
                app_ctx = browser.new_context(viewport={"width": width, "height": height})
                app_p = app_ctx.new_page()
                app_p.goto(dashboard_url, wait_until="networkidle")

                app_p.evaluate(f"""() => {{
                    localStorage.setItem('access_token', '{access_token}');
                    localStorage.setItem('refresh_token', '{refresh_token}');
                    localStorage.setItem('theme', '{theme}');
                }}""")
                app_p.goto(dashboard_url, wait_until="networkidle")
                app_p.evaluate(f"""() => {{
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
                }}""")
                app_p.wait_for_timeout(300)

                # Check Sidebar logo & username
                sidebar_info = app_p.evaluate("""() => {
                    const sb = document.querySelector('.app-sidebar') || document.getElementById('sidebar-panel');
                    const sbBg = sb ? window.getComputedStyle(sb).backgroundColor : null;

                    const logo = document.querySelector('.sidebar-brand-name');
                    const logoSt = logo ? window.getComputedStyle(logo) : null;

                    const uname = document.getElementById('user-display-name');
                    const unameSt = uname ? window.getComputedStyle(uname) : null;

                    const openSettings = document.getElementById('btn-open-settings');
                    const sSt = openSettings ? window.getComputedStyle(openSettings) : null;
                    const sRect = openSettings ? openSettings.getBoundingClientRect() : null;

                    const icon = openSettings ? openSettings.querySelector('.action-icon') : null;
                    const label = openSettings ? openSettings.querySelector('.action-label') : null;
                    const iconRect = icon ? icon.getBoundingClientRect() : null;
                    const labelRect = label ? label.getBoundingClientRect() : null;

                    return {
                        sidebarBg: sbBg,
                        logoText: logo ? logo.innerText.trim() : null,
                        logoColor: logoSt ? logoSt.color : null,
                        unameText: uname ? uname.innerText.trim() : null,
                        unameColor: unameSt ? unameSt.color : null,
                        settingsBtn: openSettings ? {
                            w: sRect.width,
                            h: sRect.height,
                            display: sSt.display,
                            text: openSettings.innerText.trim(),
                            iconTop: iconRect ? iconRect.top : null,
                            labelTop: labelRect ? labelRect.top : null,
                            stacked: iconRect && labelRect ? Math.abs(iconRect.top - labelRect.top) > 5 : null
                        } : null
                    };
                }""")
                if sidebar_info['logoColor']:
                    cr_logo = contrast_ratio(sidebar_info['logoColor'], sidebar_info['sidebarBg'])
                    findings.append(f"{tag} Sidebar logo '{sidebar_info['logoText']}': color={sidebar_info['logoColor']}, bg={sidebar_info['sidebarBg']}, contrast={cr_logo:.2f}:1")
                if sidebar_info['unameColor']:
                    cr_uname = contrast_ratio(sidebar_info['unameColor'], sidebar_info['sidebarBg'])
                    findings.append(f"{tag} Username '{sidebar_info['unameText']}': color={sidebar_info['unameColor']}, bg={sidebar_info['sidebarBg']}, contrast={cr_uname:.2f}:1")
                if sidebar_info['settingsBtn']:
                    sb_btn = sidebar_info['settingsBtn']
                    findings.append(f"{tag} Settings button: size=({sb_btn['w']:.1f}x{sb_btn['h']:.1f}), stacked={sb_btn['stacked']}, text='{sb_btn['text']}'")

                # Check Model Engine dropdown
                model_info = app_p.evaluate("""() => {
                    const sel = document.getElementById('model');
                    if (!sel) return null;
                    const st = window.getComputedStyle(sel);
                    return { id: sel.id, color: st.color, bg: st.backgroundColor };
                }""")
                if model_info:
                    cr_model = contrast_ratio(model_info['color'], model_info['bg'])
                    findings.append(f"{tag} Model Engine dropdown: color={model_info['color']}, bg={model_info['bg']}, contrast={cr_model:.2f}:1")

                # Check Threshold slider
                threshold_info = app_p.evaluate("""() => {
                    const th = document.getElementById('threshold');
                    if (!th) return null;
                    const st = window.getComputedStyle(th);
                    return { accentColor: st.accentColor, bg: st.background, color: st.color };
                }""")
                findings.append(f"{tag} Threshold slider: {threshold_info}")

                # ------------------------------------------------------------------
                # 3. SETTINGS MODAL CHECKS
                # ------------------------------------------------------------------
                # Open modal
                app_p.evaluate("""() => {
                    const btn = document.getElementById('btn-open-settings');
                    if (btn) btn.click();
                }""")
                app_p.wait_for_timeout(200)

                modal_info = app_p.evaluate("""() => {
                    const tabs = Array.from(document.querySelectorAll('.settings-nav-tab')).map(t => {
                        const svg = t.querySelector('svg');
                        const label = t.querySelector('.tab-label');
                        const r = t.getBoundingClientRect();
                        const st = window.getComputedStyle(t);
                        return {
                            id: t.id,
                            label: label ? label.innerText.trim() : t.innerText.trim(),
                            w: r.width,
                            h: r.height,
                            hasSvg: !!svg,
                            svgStroke: svg ? window.getComputedStyle(svg).stroke : null,
                            color: st.color,
                            bg: st.backgroundColor
                        };
                    });

                    const testKeyBtn = document.getElementById('btn-test-gemini');
                    const testKeySt = testKeyBtn ? window.getComputedStyle(testKeyBtn) : null;

                    const revealBtn = document.getElementById('toggle-key-visibility');
                    const revealSvg = revealBtn ? revealBtn.querySelector('svg') : null;
                    const revealText = revealBtn ? revealBtn.innerText : '';

                    return {
                        tabs,
                        testKeyBtn: testKeyBtn ? {
                            text: testKeyBtn.innerText.trim(),
                            border: testKeySt.border,
                            padding: testKeySt.padding,
                            bg: testKeySt.backgroundColor,
                            color: testKeySt.color
                        } : null,
                        revealSvgPresent: !!revealSvg,
                        revealEmojiPresent: revealText.includes('👁')
                    };
                }""")
                findings.append(f"{tag} Settings tabs: {json.dumps(modal_info['tabs'])}")
                findings.append(f"{tag} Test & Save Key button: {json.dumps(modal_info['testKeyBtn'])}")
                findings.append(f"{tag} Reveal button: svgPresent={modal_info['revealSvgPresent']}, emojiPresent={modal_info['revealEmojiPresent']}")

                app_ctx.close()

        browser.close()

    print("\n================== FULL REPORT ==================")
    for f in findings:
        print(f)


if __name__ == "__main__":
    run_checks()
