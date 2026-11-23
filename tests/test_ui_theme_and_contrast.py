import os
import re
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STYLE_CSS = os.path.join(REPO_ROOT, "app", "static", "style.css")
INDEX_HTML = os.path.join(REPO_ROOT, "app", "static", "index.html")
APP_JS = os.path.join(REPO_ROOT, "app", "static", "app.js")


def srgb_to_lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_code):
    hex_code = hex_code.strip().lstrip('#')
    if len(hex_code) == 3:
        hex_code = ''.join([c * 2 for c in hex_code])
    r = int(hex_code[0:2], 16)
    g = int(hex_code[2:4], 16)
    b = int(hex_code[4:6], 16)
    return 0.2126 * srgb_to_lin(r) + 0.7152 * srgb_to_lin(g) + 0.0722 * srgb_to_lin(b)


def contrast_ratio(hex1, hex2):
    l1 = luminance(hex1)
    l2 = luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def parse_css_variables(block_text):
    tokens = {}
    for match in re.finditer(r'--([a-zA-Z0-9_-]+)\s*:\s*([^;]+);', block_text):
        name = match.group(1).strip()
        val = match.group(2).strip()
        tokens[name] = val
    return tokens


def test_theme_contrast_and_non_equal_tokens():
    """Test (a): text token must not equal bg token and contrast must be >= 4.5:1 (WCAG 2.1 AA)."""
    assert os.path.exists(STYLE_CSS), f"Missing {STYLE_CSS}"
    with open(STYLE_CSS, "r", encoding="utf-8") as f:
        css = f.read()

    # Extract dark theme block
    dark_match = re.search(r':root[^{]*\{([^}]*)\}', css)
    assert dark_match, "Could not find :root declaration in style.css"
    dark_tokens = parse_css_variables(dark_match.group(1))

    # Extract light theme block
    light_match = re.search(r'(?:body\.light-theme|\[data-theme="light"\])[^{]*\{([^}]*)\}', css)
    assert light_match, "Could not find light-theme declaration in style.css"
    light_tokens = parse_css_variables(light_match.group(1))

    # Required semantic tokens
    required_tokens = ['bg', 'surface', 'surface-raised', 'border', 'text', 'text-muted', 'accent']
    for req in required_tokens:
        assert req in dark_tokens, f"Dark theme missing semantic token --{req}"
        assert req in light_tokens, f"Light theme missing semantic token --{req}"

    # Check Dark Theme
    dark_text_tokens = [('text', dark_tokens['text']), ('text-muted', dark_tokens['text-muted'])]
    dark_bg_tokens = [('bg', dark_tokens['bg']), ('surface', dark_tokens['surface']), ('surface-raised', dark_tokens['surface-raised'])]

    for t_name, t_val in dark_text_tokens:
        for bg_name, bg_val in dark_bg_tokens:
            assert t_val.lower() != bg_val.lower(), f"Dark theme: {t_name} equals {bg_name} ({t_val})"
            if t_val.startswith('#') and bg_val.startswith('#'):
                cr = contrast_ratio(t_val, bg_val)
                assert cr >= 4.5, f"Dark theme {t_name} ({t_val}) vs {bg_name} ({bg_val}) contrast {cr:.2f}:1 is below 4.5:1"

    # Check Light Theme
    light_text_tokens = [('text', light_tokens['text']), ('text-muted', light_tokens['text-muted'])]
    light_bg_tokens = [('bg', light_tokens['bg']), ('surface', light_tokens['surface']), ('surface-raised', light_tokens['surface-raised'])]

    for t_name, t_val in light_text_tokens:
        for bg_name, bg_val in light_bg_tokens:
            assert t_val.lower() != bg_val.lower(), f"Light theme: {t_name} equals {bg_name} ({t_val})"
            if t_val.startswith('#') and bg_val.startswith('#'):
                cr = contrast_ratio(t_val, bg_val)
                assert cr >= 4.5, f"Light theme {t_name} ({t_val}) vs {bg_name} ({bg_val}) contrast {cr:.2f}:1 is below 4.5:1"


def test_no_hardcoded_hex_colors_outside_theme_blocks():
    """Test (b): assert style.css contains zero hardcoded hex colors outside :root and theme blocks."""
    assert os.path.exists(STYLE_CSS), f"Missing {STYLE_CSS}"
    with open(STYLE_CSS, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_theme_block = False
    violations = []

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        # Theme blocks are where palette hex variables are permitted
        if ':root' in line or 'light-theme' in line or '[data-theme' in line:
            in_theme_block = True
        if in_theme_block and stripped.startswith('}'):
            in_theme_block = False
            continue

        if not in_theme_block:
            # Look for hex color patterns like #fff, #111318, #6f61f6
            hex_matches = re.findall(r'#(?:[0-9a-fA-F]{3,8})\b', line)
            if hex_matches:
                violations.append((line_num, stripped, hex_matches))

    msg = "\n".join([f"Line {v[0]}: {v[1]} (Found: {v[2]})" for v in violations[:10]])
    assert len(violations) == 0, f"Found {len(violations)} lines with hardcoded hex colors outside theme blocks:\n{msg}"


def test_missing_element_ids_needed_by_app_js():
    """Test (c): verify all element IDs used in app.js exist in index.html."""
    assert os.path.exists(INDEX_HTML), f"Missing {INDEX_HTML}"
    assert os.path.exists(APP_JS), f"Missing {APP_JS}"

    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    with open(APP_JS, "r", encoding="utf-8") as f:
        js = f.read()

    # Extract all getElementById targets from app.js
    js_ids = set(re.findall(r'getElementById\(\s*[\'"]([a-zA-Z0-9_-]+)[\'"]\s*\)', js))

    # Extract all defined IDs from index.html
    html_ids = set(re.findall(r'\bid\s*=\s*[\'"]([a-zA-Z0-9_-]+)[\'"]', html))

    # Explicit critical UI component IDs from bug descriptions and requirements
    critical_ids = [
        "settings-modal",
        "btn-open-settings",
        "btn-settings-close",
        "settings-tab-llm-btn",
        "settings-tab-notifications-btn",
        "settings-tab-api-btn",
        "settings-tab-org-btn",
        "settings-pane-llm",
        "settings-pane-notifications",
        "settings-pane-api",
        "settings-pane-org",
        "status-gemini-connection",
        "settings-gemini-key",
        "btn-test-gemini",
        "status-openai-connection",
        "settings-openai-key",
        "btn-test-openai",
        "status-anthropic-connection",
        "settings-anthropic-key",
        "btn-test-anthropic",
        "threshold",
        "threshold-val",
        "model",
        "sidebar-panel",
        "header-auth",
        "user-display-name",
        "user-display-role",
        "btn-logout",
        "sidebar-toggle-btn",
    ]

    for cid in critical_ids:
        assert cid in html_ids, f"Critical UI Element ID '{cid}' is missing from index.html"

    # IDs that may be dynamically generated or rendered conditionally in JS templates
    dynamic_whitelist = {
        'repo-search-input', 'repo-visibility-filter', 'repo-sort-select', 'repos-container',
        'create-repo-name', 'create-repo-desc', 'create-repo-private', 'create-repo-init',
        'create-repo-submit', 'repo-detail-name', 'repo-detail-desc', 'repo-detail-visibility',
        'repo-detail-default-branch', 'repo-detail-created', 'repo-detail-updated',
        'repo-detail-branches-count', 'repo-detail-commits-count', 'repo-branches-list',
        'repo-commits-list', 'repo-webhook-secret', 'repo-webhook-events', 'repo-webhook-submit',
        'active-webhooks-list', 'branch-name-input', 'create-branch-submit',
        'toast-container', 'login-btn', 'signup-btn', 'user-menu', 'dynamic-content',
        'assistant-stream-temp-content', 'chat-empty-notice', 'finding-detail-modal', 'improvements-list'
    }

    missing_ids = (js_ids - html_ids) - dynamic_whitelist
    # Filter out anything not matched
    assert len(missing_ids) == 0, f"Missing element IDs in index.html needed by app.js: {sorted(list(missing_ids))}"
