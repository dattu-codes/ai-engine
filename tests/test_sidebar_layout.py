import os
import re

STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "static"))
INDEX_HTML = os.path.join(STATIC_DIR, "index.html")
STYLE_CSS = os.path.join(STATIC_DIR, "style.css")


def test_sidebar_html_elements_and_ids_preserved():
    """Verify all sidebar user profile elements, IDs, and click triggers are present."""
    assert os.path.exists(INDEX_HTML), "index.html does not exist"
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    # Required sidebar elements and IDs
    assert 'id="sidebar-panel"' in html, "Missing #sidebar-panel"
    assert 'id="header-auth"' in html, "Missing #header-auth"
    assert 'id="user-display-name"' in html, "Missing #user-display-name"
    assert 'id="user-display-role"' in html, "Missing #user-display-role"
    assert 'id="btn-open-settings"' in html, "Missing #btn-open-settings"
    assert 'id="btn-logout"' in html, "Missing #btn-logout"
    assert 'id="sidebar-toggle-btn"' in html, "Missing #sidebar-toggle-btn"

    # User avatar container
    assert 'class="user-avatar"' in html, "Missing .user-avatar"
    assert 'toggleSidebar()' in html, "Missing toggleSidebar() handler call"


def test_sidebar_css_pinned_to_bottom_with_flex_and_fixed_100vh():
    """Verify sidebar CSS enforces position fixed, 100vh height, flex column, and profile margin-top: auto."""
    assert os.path.exists(STYLE_CSS), "style.css does not exist"
    with open(STYLE_CSS, "r", encoding="utf-8") as f:
        css = f.read()

    # Pinned fixed sidebar checks
    assert "position: fixed" in css, "Missing position: fixed in CSS"
    assert "height: 100vh" in css, "Missing height: 100vh in CSS"
    assert "flex-direction: column" in css, "Missing flex-direction: column in CSS"
    assert "margin-top: auto" in css, "Missing margin-top: auto for sidebar footer in CSS"
    assert "overflow-y: auto" in css, "Missing overflow-y: auto for main content or scrollable regions"


def test_sidebar_collapsed_state_icons_and_avatar():
    """Verify collapsed state styles show avatar and icons for Settings and Logout."""
    with open(STYLE_CSS, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".app-sidebar.collapsed" in css
    assert "action-icon" in css
    assert "action-label" in css
