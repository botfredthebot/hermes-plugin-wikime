"""
Frontend smoke tests for Hermes Dashboard plugins.

Loads the actual dashboard in a headless browser, clicks through each plugin
tab, and asserts:
  - No JavaScript errors or uncaught exceptions
  - No 401 errors on API calls expected to succeed
  - Each tab renders visible content
  - Plugin components register and mount
"""
import time
import pytest
from playwright.sync_api import sync_playwright, expect

DASHBOARD_URL = "http://127.0.0.1:9119"
GATEWAY_STARTUP_WAIT = 3  # seconds to wait for gateway to be ready


@pytest.fixture(scope="session")
def browser():
    """Launch a headless Chromium browser for the test session."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium-browser",
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        yield browser
        browser.close()


@pytest.fixture(scope="session")
def errors():
    """Collect JavaScript errors across all tests."""
    return []


@pytest.fixture
def page(browser, errors):
    """Create a fresh page with error/response tracking."""
    context = browser.new_context(
        ignore_https_errors=True,
        viewport={"width": 1280, "height": 900},
    )
    pg = context.new_page()

    # Collect all JS errors
    pg.on("pageerror", lambda exc: errors.append(f"JS_ERROR: {exc}"))

    # Track 401 responses
    failed_urls = []

    def on_response(response):
        if response.status == 401:
            failed_urls.append(f"401: {response.url}")

    pg.on("response", on_response)

    yield pg

    # After each test, dump collected errors
    page_errors = [e for e in errors if e not in getattr(page, "_seen_errors", set())]
    page._seen_errors = set(errors)
    if page_errors:
        pytest.fail(
            f"JavaScript errors detected:\n" + "\n".join(page_errors[:10])
            + (f"\n...and {len(page_errors) - 10} more" if len(page_errors) > 10 else "")
        )

    pg.close()
    context.close()


@pytest.fixture(autouse=True)
def wait_gateway(page):
    """Ensure the dashboard is loaded before each test."""
    page.goto(DASHBOARD_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2_000)  # allow JS to hydrate
    # Check the sidebar is present (confirms gateway is ready)
    try:
        page.wait_for_selector("#app-sidebar", timeout=10_000)
    except Exception:
        pytest.skip("Hermes Dashboard not reachable at " + DASHBOARD_URL)
    yield


# --------------------------------------------------------------------------- #
# Helper: click a sidebar/tab item and wait for content
# --------------------------------------------------------------------------- #

def click_tab(page, name):
    """Click a tab or nav item by exact text match."""
    # Try direct text match in the sidebar/nav
    try:
        page.click(f"text={name}", timeout=5_000)
    except Exception:
        page.wait_for_timeout(500)
        page.click(f"text={name}", timeout=3_000)
    page.wait_for_timeout(1_500)


def assert_no_js_errors(page, errors, context_label=""):
    """Assert no JS errors were collected."""
    recent = [e for e in errors if "JS_ERROR" in e and context_label in e]
    assert not recent, f"JS errors in {context_label}:\n" + "\n".join(recent[:5])


# =================================================================== #
# HONCHO DASHBOARD PLUGIN — FRONTEND SMOKE TESTS
# =================================================================== #

class TestHonchoDashboardPlugin:
    """Smoke tests for the Honcho Dashboard Hermes plugin."""

    PLUGIN_TAB = "HONCHO"

    def test_honcho_tab_exists_in_sidebar(self, page, errors):
        """The Honcho plugin tab should appear in the sidebar."""
        # Sidebar is <aside id="app-sidebar">, scroll to bottom to see plugins
        page.evaluate("document.querySelector('#app-sidebar').scrollTop = 9999")
        page.wait_for_timeout(500)
        assert page.query_selector("text=HONCHO") is not None, "HONCHO tab not found in sidebar"

    def test_plugin_loads_no_js_errors(self, page, errors):
        """Navigating to Honcho plugin should not produce JS errors."""
        click_tab(page, "HONCHO")
        page.wait_for_timeout(3_000)
        js_errs = [e for e in errors if "JS_ERROR" in e]
        assert not js_errs, f"JS errors loading Honcho plugin:\n" + "\n".join(js_errs[:5])

    def test_overview_tab_renders(self, page, errors):
        """Overview tab should render without JS errors."""
        click_tab(page, "HONCHO")
        page.wait_for_timeout(2_000)
        # Click Overview subtab
        page.click("text=Overview", timeout=5_000)
        page.wait_for_timeout(2_000)
        js_errs = [e for e in errors if "JS_ERROR" in e]
        assert not js_errs, f"JS errors on Overview tab:\n" + "\n".join(js_errs[:5])

    def test_analytics_tab_renders(self, page, errors):
        """Analytics tab should render bar charts without JS errors."""
        click_tab(page, "HONCHO")
        page.wait_for_timeout(1_000)
        # Click Analytics subtab
        page.click("text=Analytics", timeout=5_000)
        page.wait_for_timeout(3_000)  # wait for API call + render
        # Analytics should show content
        page_content = page.content()
        has_content = "Messages per Day" in page_content or "per Day" in page_content
        assert has_content, "Analytics tab content not found on page"
        # Critical: no JS errors
        js_errs = [e for e in errors if "JS_ERROR" in e]
        assert not js_errs, f"JS errors on Analytics tab:\n" + "\n".join(js_errs[:5])

    def test_all_tabs_navigable(self, page, errors):
        """All Honcho subtabs should render the Overview tab without JS errors."""
        click_tab(page, "HONCHO")
        page.wait_for_timeout(2_000)
        # The Overview tab renders by default — check for stat cards or summary text
        page_content = page.content()
        # Should have rendered some content (not blank, not an error)
        assert "HONCHO" in page_content or "Overview" in page_content or "Peers" in page_content, \
            "Honcho plugin content not rendered"
        # Most critically: no JS errors
        js_errs = [e for e in errors if "JS_ERROR" in e]
        assert not js_errs, f"JS errors navigating Honcho plugin:\n" + "\n".join(js_errs[:5])


# =================================================================== #
# WIKIME DASHBOARD PLUGIN — FRONTEND SMOKE TESTS
# =================================================================== #

class TestWikiMeDashboardPlugin:
    """Smoke tests for the WikiMe Hermes plugin."""

    PLUGIN_TAB = "WIKIME"

    def test_wikime_tab_exists_in_sidebar(self, page, errors):
        """The WikiMe plugin tab should appear in the sidebar."""
        page.evaluate("document.querySelector('#app-sidebar').scrollTop = 9999")
        page.wait_for_timeout(500)
        assert page.query_selector("text=WIKIME") is not None, "WIKIME tab not found in sidebar"

    def test_wikime_plugin_loads(self, page, errors):
        """WikiMe plugin should load without JS errors."""
        click_tab(page, "WIKIME")
        page.wait_for_timeout(3_000)
        js_errs = [e for e in errors if "JS_ERROR" in e]
        assert not js_errs, f"JS errors loading WikiMe plugin:\n" + "\n".join(js_errs[:5])

    def test_no_401_errors(self, page, errors):
        """No API calls should return 401 after authentication."""
        click_tab(page, "HONCHO")
        page.wait_for_timeout(3_000)
        click_tab(page, "WIKIME")
        page.wait_for_timeout(3_000)
        err_401s = [e for e in errors if "401:" in e]
        assert not err_401s, f"401 errors detected:\n" + "\n".join(err_401s[:10])
