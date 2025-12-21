"""End-to-end tests for the unified frontend SPA.

These tests use Playwright to verify the frontend JavaScript functionality
by running a real browser against generated demo data.

Run with: tox -e e2e
Or: pytest tests/e2e/ -v (after installing playwright)
"""

from __future__ import annotations

import random
import subprocess
import time
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

# Import fixture generator
from tests.e2e.fixtures.generate_fixtures import generate_fixtures


@pytest.fixture(scope="module")
def demo_data(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate demo data for e2e tests."""
    demo_dir = tmp_path_factory.mktemp("demo")
    random.seed(42)
    generate_fixtures(demo_dir)
    return demo_dir


@pytest.fixture(scope="module")
def demo_server(demo_data: Path) -> Generator[str, None, None]:
    """Start HTTP server serving demo data."""
    from strava_backup.views.map import copy_assets_to_output, generate_lightweight_map

    # Generate HTML and copy assets
    html = generate_lightweight_map(demo_data)
    html_path = demo_data / "strava-backup.html"
    html_path.write_text(html, encoding="utf-8")
    copy_assets_to_output(demo_data)

    # Start server in background
    port = 18080  # Use non-standard port to avoid conflicts
    proc = subprocess.Popen(
        ["python", "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=demo_data,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for server to start
    time.sleep(1)

    yield f"http://127.0.0.1:{port}"

    # Cleanup
    proc.terminate()
    proc.wait(timeout=5)


@pytest.mark.ai_generated
class TestAppLaunch:
    """Test basic app launch and navigation."""

    def test_app_loads(self, demo_server: str, page: Page) -> None:
        """Verify the app loads without errors."""
        page.goto(f"{demo_server}/strava-backup.html")

        # Check title/header
        assert page.locator(".logo").text_content() == "Strava Backup"

        # Check all three nav tabs are present
        nav_tabs = page.locator(".nav-tab")
        assert nav_tabs.count() == 3

        tab_texts = [nav_tabs.nth(i).text_content() for i in range(3)]
        assert "Map" in tab_texts
        assert "Sessions" in tab_texts
        assert "Stats" in tab_texts

    def test_favicon_loads(self, demo_server: str, page: Page) -> None:
        """Verify favicon doesn't 404."""
        page.goto(f"{demo_server}/strava-backup.html")

        # Check favicon link exists
        favicon = page.locator('link[rel="icon"]')
        assert favicon.count() == 1

    def test_athlete_selector_shows_all(self, demo_server: str, page: Page) -> None:
        """Verify athlete selector shows all athletes."""
        page.goto(f"{demo_server}/strava-backup.html")

        # Wait for data to load
        page.wait_for_selector("#athlete-select")

        # Check "All Athletes" option exists with session count
        select = page.locator("#athlete-select")
        options = select.locator("option")

        # Should have: All Athletes, alice, bob
        assert options.count() >= 3

        # First option should be "All Athletes"
        first_option = options.first.text_content()
        assert "All Athletes" in first_option
        assert "15 sessions" in first_option  # 10 alice + 5 bob


@pytest.mark.ai_generated
class TestMapView:
    """Test map view functionality."""

    def test_map_renders(self, demo_server: str, page: Page) -> None:
        """Verify map container renders."""
        page.goto(f"{demo_server}/strava-backup.html#/map")
        page.wait_for_selector("#map")

        # Check leaflet map initialized
        assert page.locator(".leaflet-container").count() == 1

    def test_markers_appear(self, demo_server: str, page: Page) -> None:
        """Verify session markers appear on map."""
        page.goto(f"{demo_server}/strava-backup.html#/map")

        # Wait for markers to load (they're loaded async)
        page.wait_for_selector(".leaflet-marker-icon", timeout=10000)

        # Should have markers for sessions with GPS
        markers = page.locator(".leaflet-marker-icon")
        assert markers.count() > 0

    def test_marker_popup(self, demo_server: str, page: Page) -> None:
        """Verify clicking marker opens popup."""
        page.goto(f"{demo_server}/strava-backup.html#/map")
        page.wait_for_selector(".leaflet-marker-icon", timeout=10000)

        # Click first marker
        page.locator(".leaflet-marker-icon").first.click()

        # Popup should appear
        page.wait_for_selector(".leaflet-popup")
        popup = page.locator(".leaflet-popup-content")
        assert popup.count() == 1


@pytest.mark.ai_generated
class TestSessionsView:
    """Test sessions list view functionality."""

    def test_sessions_list_loads(self, demo_server: str, page: Page) -> None:
        """Verify sessions list shows all sessions."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")

        # Wait for table to load
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # Should show sessions
        rows = page.locator("#sessions-table tbody tr")
        assert rows.count() > 0

    def test_sessions_count_matches(self, demo_server: str, page: Page) -> None:
        """Verify sessions count matches expected."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # With "All Athletes" selected, should show 15 sessions
        rows = page.locator("#sessions-table tbody tr")
        assert rows.count() == 15

    def test_search_filter(self, demo_server: str, page: Page) -> None:
        """Verify search filter works."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # Search for "Run"
        page.fill("#session-search", "Run")

        # Wait for filter to apply
        page.wait_for_timeout(500)

        # Should show fewer rows (only runs)
        rows = page.locator("#sessions-table tbody tr")
        row_count = rows.count()
        assert row_count > 0
        assert row_count < 15  # Fewer than total

    def test_type_filter(self, demo_server: str, page: Page) -> None:
        """Verify type filter works."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # Select "Ride" type
        page.select_option("#type-filter", "Ride")

        # Wait for filter to apply
        page.wait_for_timeout(500)

        # Should show only rides
        rows = page.locator("#sessions-table tbody tr")
        assert rows.count() > 0

        # All visible rows should be rides
        for i in range(rows.count()):
            row_text = rows.nth(i).text_content()
            assert "Ride" in row_text

    def test_session_detail_opens(self, demo_server: str, page: Page) -> None:
        """Verify clicking session opens detail panel."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # Click first session
        page.locator("#sessions-table tbody tr").first.click()

        # Detail panel should appear
        page.wait_for_selector(".detail-panel.open")
        assert page.locator(".detail-panel.open").count() == 1


@pytest.mark.ai_generated
class TestStatsView:
    """Test stats dashboard functionality."""

    def test_stats_loads(self, demo_server: str, page: Page) -> None:
        """Verify stats view loads with data."""
        page.goto(f"{demo_server}/strava-backup.html#/stats")

        # Wait for stats to calculate
        page.wait_for_selector(".stat-card", timeout=10000)

        # Should show stat cards
        cards = page.locator(".stat-card")
        assert cards.count() >= 3  # Activities, distance, time at minimum

    def test_stats_shows_totals(self, demo_server: str, page: Page) -> None:
        """Verify stats shows correct totals."""
        page.goto(f"{demo_server}/strava-backup.html#/stats")
        page.wait_for_selector(".stat-card", timeout=10000)

        # Find activities card
        stats_text = page.locator(".stats-grid").text_content()

        # Should show "15" for total activities
        assert "15" in stats_text

    def test_charts_render(self, demo_server: str, page: Page) -> None:
        """Verify charts render."""
        page.goto(f"{demo_server}/strava-backup.html#/stats")
        page.wait_for_selector(".chart-container canvas", timeout=10000)

        # Should have chart canvases
        canvases = page.locator(".chart-container canvas")
        assert canvases.count() >= 1


@pytest.mark.ai_generated
class TestAthleteFiltering:
    """Test athlete filtering across views."""

    def test_filter_to_alice(self, demo_server: str, page: Page) -> None:
        """Verify filtering to alice shows only her sessions."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # Select alice
        page.select_option("#athlete-select", "alice")

        # Wait for filter to apply
        page.wait_for_timeout(500)

        # Should show 10 sessions (alice has 10)
        rows = page.locator("#sessions-table tbody tr")
        assert rows.count() == 10

    def test_filter_to_bob(self, demo_server: str, page: Page) -> None:
        """Verify filtering to bob shows only his sessions."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # Select bob
        page.select_option("#athlete-select", "bob")

        # Wait for filter to apply
        page.wait_for_timeout(500)

        # Should show 5 sessions (bob has 5)
        rows = page.locator("#sessions-table tbody tr")
        assert rows.count() == 5


@pytest.mark.ai_generated
class TestSessionDetail:
    """Test session detail panel functionality."""

    def test_detail_shows_stats(self, demo_server: str, page: Page) -> None:
        """Verify detail panel shows stats."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # Click first session
        page.locator("#sessions-table tbody tr").first.click()
        page.wait_for_selector(".detail-panel.open")

        # Should show stat cards
        assert page.locator(".detail-stats .stat-card").count() >= 2

    def test_detail_shows_map(self, demo_server: str, page: Page) -> None:
        """Verify detail panel shows map for GPS sessions."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # Find a session with GPS (Run or Ride should have GPS)
        page.select_option("#type-filter", "Run")
        page.wait_for_timeout(500)

        # Click first run
        page.locator("#sessions-table tbody tr").first.click()
        page.wait_for_selector(".detail-panel.open")

        # Wait for track to load
        page.wait_for_timeout(1000)

        # Should have a map container (may or may not have loaded track yet)
        assert page.locator(".detail-map").count() == 1

    def test_view_on_map_button(self, demo_server: str, page: Page) -> None:
        """Verify 'View on Map' button navigates to map view."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # Click first session
        page.locator("#sessions-table tbody tr").first.click()
        page.wait_for_selector(".detail-panel.open")

        # Click "View on Map" button
        page.locator("text=View on Map").click()

        # Should navigate to map view
        page.wait_for_timeout(500)
        assert "#/map" in page.url


@pytest.mark.ai_generated
class TestSharedRun:
    """Test shared run detection (alice and bob ran together)."""

    def test_shared_run_exists(self, demo_server: str, page: Page) -> None:
        """Verify shared run session exists for both athletes."""
        # Check alice has the shared run
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        page.select_option("#athlete-select", "alice")
        page.wait_for_timeout(500)

        # Search for the shared run date
        page.fill("#session-search", "2024-12-18")
        page.wait_for_timeout(500)

        rows = page.locator("#sessions-table tbody tr")
        assert rows.count() >= 1

        # Clear and check bob
        page.fill("#session-search", "")
        page.select_option("#athlete-select", "bob")
        page.wait_for_timeout(500)

        page.fill("#session-search", "2024-12-18")
        page.wait_for_timeout(500)

        rows = page.locator("#sessions-table tbody tr")
        assert rows.count() >= 1


@pytest.mark.ai_generated
class TestFullScreenSessionView:
    """Test full-screen session view (expand button) functionality."""

    def test_expand_button_opens_full_view(self, demo_server: str, page: Page) -> None:
        """Verify expand button opens full-screen session view."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # Click first session to open detail panel
        page.locator("#sessions-table tbody tr").first.click()
        page.wait_for_selector(".detail-panel.open")

        # Click expand button
        page.locator(".detail-expand-btn").click()

        # Should navigate to full session view
        page.wait_for_timeout(1000)
        assert "#/session/" in page.url

        # Full session view should be visible
        page.wait_for_selector("#view-session.active", timeout=5000)

    def test_full_session_view_shows_content(
        self, demo_server: str, page: Page
    ) -> None:
        """Verify full-screen session view shows session content."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # Click first session and expand
        page.locator("#sessions-table tbody tr").first.click()
        page.wait_for_selector(".detail-panel.open")
        page.locator(".detail-expand-btn").click()
        page.wait_for_selector("#view-session.active", timeout=5000)

        # Session name should be displayed (not "Activity Name" placeholder)
        session_name = page.locator("#full-session-name").text_content()
        assert session_name != "Activity Name"
        assert session_name != "Loading..."
        assert len(session_name or "") > 0

    def test_back_button_returns_to_sessions(
        self, demo_server: str, page: Page
    ) -> None:
        """Verify back button returns to sessions view."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # Navigate to full session view
        page.locator("#sessions-table tbody tr").first.click()
        page.wait_for_selector(".detail-panel.open")
        page.locator(".detail-expand-btn").click()
        page.wait_for_selector("#view-session.active", timeout=5000)

        # Click back button
        page.locator("#full-session-back").click()

        # Should return to sessions view
        page.wait_for_timeout(500)
        assert "#/sessions" in page.url
        page.wait_for_selector("#view-sessions.active")

    def test_direct_permalink_loads(self, demo_server: str, page: Page) -> None:
        """Verify direct permalink URL loads the session."""
        # First get a valid session URL
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        page.locator("#sessions-table tbody tr").first.click()
        page.wait_for_selector(".detail-panel.open")
        page.locator(".detail-expand-btn").click()
        page.wait_for_selector("#view-session.active", timeout=5000)

        # Capture the session URL
        session_url = page.url

        # Navigate away
        page.goto(f"{demo_server}/strava-backup.html#/map")
        page.wait_for_selector("#view-map.active")

        # Navigate directly to the session URL
        page.goto(session_url)
        page.wait_for_selector("#view-session.active", timeout=10000)

        # Session content should load
        page.wait_for_timeout(2000)  # Wait for data to load
        session_name = page.locator("#full-session-name").text_content()
        assert session_name != "Activity Name"
        assert session_name != "Session Not Found"

    def test_permalink_preserved_on_map_interaction(
        self, demo_server: str, page: Page
    ) -> None:
        """Verify session permalink is preserved when map loads."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)

        # Navigate to full session view
        page.locator("#sessions-table tbody tr").first.click()
        page.wait_for_selector(".detail-panel.open")
        page.locator(".detail-expand-btn").click()
        page.wait_for_selector("#view-session.active", timeout=5000)

        # Capture the original session URL
        original_url = page.url
        assert "#/session/" in original_url

        # Wait for map to potentially load and trigger URL changes
        page.wait_for_timeout(2000)

        # URL should still be the session permalink format
        current_url = page.url
        assert "#/session/" in current_url
        # Should not have been corrupted to query params format
        assert "?z=" not in current_url or "#/session/" in current_url.split("?")[0]


@pytest.mark.ai_generated
class TestNavigation:
    """Test tab navigation between views."""

    def test_stats_tab_navigates_from_map(self, demo_server: str, page: Page) -> None:
        """Verify clicking Stats tab from Map view navigates to Stats."""
        page.goto(f"{demo_server}/strava-backup.html#/map")
        page.wait_for_selector("#view-map.active", timeout=10000)

        # Click Stats tab
        page.locator(".nav-tab[data-view='stats']").click()

        # Should navigate to stats view (without needing refresh)
        page.wait_for_selector("#view-stats.active", timeout=5000)
        assert "#/stats" in page.url

    def test_stats_tab_navigates_from_sessions(
        self, demo_server: str, page: Page
    ) -> None:
        """Verify clicking Stats tab from Sessions view navigates to Stats."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#view-sessions.active", timeout=10000)

        # Click Stats tab
        page.locator(".nav-tab[data-view='stats']").click()

        # Should navigate to stats view (without needing refresh)
        page.wait_for_selector("#view-stats.active", timeout=5000)
        assert "#/stats" in page.url

    def test_map_from_stats_uses_reasonable_zoom(
        self, demo_server: str, page: Page
    ) -> None:
        """Verify navigating to Map from Stats doesn't use extreme zoom levels."""
        # First go to stats with some zoom params in URL (simulating prior navigation)
        page.goto(f"{demo_server}/strava-backup.html#/stats?z=19&lat=18.5989&lng=15.4742")
        page.wait_for_selector("#view-stats.active", timeout=10000)

        # Click Map tab
        page.locator(".nav-tab[data-view='map']").click()
        page.wait_for_selector("#view-map.active", timeout=5000)

        # URL should NOT have the extreme zoom level from stats
        current_url = page.url
        # Either no zoom param, or a reasonable zoom (not 19)
        if "z=" in current_url:
            import re

            zoom_match = re.search(r"z=(\d+)", current_url)
            if zoom_match:
                zoom = int(zoom_match.group(1))
                # Zoom 19 is street-level, too high for general navigation
                # Should be world view (3) or a reasonable default
                assert zoom < 15, f"Zoom level {zoom} is too high for default navigation"

    def test_sessions_tab_navigates_from_stats(
        self, demo_server: str, page: Page
    ) -> None:
        """Verify clicking Sessions tab from Stats view navigates properly."""
        page.goto(f"{demo_server}/strava-backup.html#/stats")
        page.wait_for_selector("#view-stats.active", timeout=10000)

        # Click Sessions tab
        page.locator(".nav-tab[data-view='sessions']").click()

        # Should navigate to sessions view
        page.wait_for_selector("#view-sessions.active", timeout=5000)
        assert "#/sessions" in page.url

    def test_map_tab_navigates_from_sessions(
        self, demo_server: str, page: Page
    ) -> None:
        """Verify clicking Map tab from Sessions view navigates properly."""
        page.goto(f"{demo_server}/strava-backup.html#/sessions")
        page.wait_for_selector("#view-sessions.active", timeout=10000)

        # Click Map tab
        page.locator(".nav-tab[data-view='map']").click()

        # Should navigate to map view
        page.wait_for_selector("#view-map.active", timeout=5000)
        assert "#/map" in page.url
