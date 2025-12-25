#!/usr/bin/env python3
"""Generate screenshots of the unified frontend for documentation.

This script uses Playwright to automate a browser walkthrough of the
MyKrok web interface, capturing screenshots at key points.
These screenshots are saved to docs/screenshots/ for use in README.md.

Usage:
    python scripts/generate_screenshots.py [--output-dir DIR] [--no-headless]

Requirements:
    - playwright (pip install playwright)
    - Browser installed (playwright install chromium)
"""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
import time
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tests" / "e2e" / "fixtures"))

# Screenshot settings - use smaller size and JPEG for smaller file sizes
VIEWPORT_WIDTH = 1024
VIEWPORT_HEIGHT = 640
SCREENSHOT_QUALITY = 80  # JPEG quality (0-100)


def generate_demo_data(output_dir: Path) -> None:
    """Generate demo data for screenshots."""
    from generate_fixtures import generate_fixtures

    random.seed(42)  # Reproducible fixtures
    generate_fixtures(output_dir)
    print(f"Generated demo data in {output_dir}")


def generate_html(data_dir: Path) -> Path:
    """Generate the HTML file and copy assets."""
    from mykrok.views.map import copy_assets_to_output, generate_lightweight_map

    html = generate_lightweight_map(data_dir)
    html_path = data_dir / "mykrok.html"
    html_path.write_text(html, encoding="utf-8")
    copy_assets_to_output(data_dir)
    print(f"Generated HTML at {html_path}")
    return html_path


def start_server(data_dir: Path, port: int = 18081) -> subprocess.Popen:
    """Start HTTP server serving the data directory."""
    proc = subprocess.Popen(
        ["python", "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=data_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)  # Wait for server to start
    print(f"Started HTTP server on port {port}")
    return proc


def take_screenshot(page, path: Path, caption: str) -> tuple[str, str, int]:
    """Take a JPEG screenshot and return (filename, caption, size)."""
    # Use JPEG for smaller file sizes
    jpeg_path = path.with_suffix(".jpg")
    page.screenshot(path=jpeg_path, type="jpeg", quality=SCREENSHOT_QUALITY)
    size = jpeg_path.stat().st_size
    return (jpeg_path.name, caption, size)


def capture_screenshots(
    base_url: str,
    output_dir: Path,
    headless: bool = True,
) -> list[tuple[str, str]]:
    """Capture screenshots using Playwright.

    Returns list of (filename, caption) tuples.
    """
    from playwright.sync_api import sync_playwright

    screenshots: list[tuple[str, str, int]] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})

        # Capture console errors for debugging
        page.on(
            "console",
            lambda msg: print(f"  [CONSOLE {msg.type}] {msg.text}")
            if msg.type in ("error", "warning")
            else None,
        )
        page.on("pageerror", lambda exc: print(f"  [PAGE ERROR] {exc}"))

        print("\nCapturing screenshots...")

        # 1. Map View - Initial view with markers
        print("  1/9: Map view (overview)")
        page.goto(f"{base_url}/mykrok.html#/map", wait_until="networkidle")
        # Wait for the page to fully load
        page.wait_for_timeout(2000)
        # Check if map container exists
        if page.locator("#map").count() == 0:
            print("  ERROR: #map not found in page")
        page.wait_for_selector(".leaflet-marker-icon", timeout=30000)
        # Wait for all markers to load and let map settle
        page.wait_for_timeout(3000)
        screenshots.append(
            take_screenshot(page, output_dir / "01-map-overview", "Map view with activity markers")
        )

        # 2. Map View - Zoomed to activity cluster (California region)
        print("  2/9: Map view (zoomed)")
        # Wait for allMarkers to be populated
        page.wait_for_function(
            "window.MapView && window.MapView.allMarkers && window.MapView.allMarkers.length > 0",
            timeout=15000,
        )
        # Zoom to California region where multiple markers are clustered
        page.evaluate("""() => {
            // Zoom to California/West Coast area to show a regional cluster
            window.mapInstance.setView([36.5, -119.5], 6);
        }""")
        page.wait_for_timeout(2000)
        screenshots.append(
            take_screenshot(page, output_dir / "02-map-zoomed", "Activities zoomed to fit")
        )

        # 3. Map View - Marker popup
        print("  3/9: Map view (popup)")
        # Use MapView.allMarkers to zoom to first marker and open its popup
        page.evaluate("""() => {
            if (window.MapView && window.MapView.allMarkers && window.MapView.allMarkers.length > 0) {
                const firstMarkerData = window.MapView.allMarkers[0];
                const latlng = firstMarkerData.marker.getLatLng();
                // Zoom to the marker location
                window.mapInstance.setView(latlng, 13);
            }
        }""")
        page.wait_for_timeout(2000)
        # Open popup on the first marker
        page.evaluate("""() => {
            if (window.MapView && window.MapView.allMarkers && window.MapView.allMarkers.length > 0) {
                const firstMarkerData = window.MapView.allMarkers[0];
                firstMarkerData.marker.openPopup();
            }
        }""")
        page.wait_for_timeout(1000)
        page.wait_for_selector(".leaflet-popup", timeout=10000)
        page.wait_for_timeout(500)
        screenshots.append(
            take_screenshot(page, output_dir / "03-map-popup", "Activity popup with details")
        )

        # 4. Sessions View - Table with all sessions
        print("  4/9: Sessions view")
        page.locator(".nav-tab[data-view='sessions']").click()
        page.wait_for_selector("#view-sessions.active", timeout=5000)
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)
        page.wait_for_timeout(500)
        screenshots.append(
            take_screenshot(page, output_dir / "04-sessions-list", "Sessions list with filters")
        )

        # 5. Sessions View - Filtered by type
        print("  5/9: Sessions view (filtered)")
        page.select_option("#type-filter", "Run")
        page.wait_for_timeout(500)
        screenshots.append(
            take_screenshot(page, output_dir / "05-sessions-filtered", "Sessions filtered by type")
        )

        # Clear filter
        page.select_option("#type-filter", "")
        page.wait_for_timeout(300)

        # 6. Sessions View - Detail panel
        print("  6/9: Session detail panel")
        # Click the first row using JavaScript to ensure it works
        page.evaluate("""() => {
            const row = document.querySelector('#sessions-table tbody tr');
            if (row) row.click();
        }""")
        # Wait longer and check for panel
        page.wait_for_timeout(1000)
        # Try clicking again if panel didn't open
        if page.locator("#session-detail:not(.hidden)").count() == 0:
            page.locator("#sessions-table tbody tr").first.click(force=True)
        page.wait_for_selector("#session-detail:not(.hidden)", timeout=10000)
        page.wait_for_timeout(1500)  # Wait for map to load
        screenshots.append(
            take_screenshot(page, output_dir / "06-session-detail", "Session detail panel")
        )

        # 7. Full-screen Session View
        print("  7/10: Full-screen session view")
        expand_btn = page.locator("#expand-detail")
        if expand_btn.count() > 0:
            expand_btn.click()
            page.wait_for_selector("#view-session.active", timeout=5000)
            page.wait_for_timeout(2000)  # Wait for content to load
            screenshots.append(
                take_screenshot(page, output_dir / "07-session-full", "Full-screen session view")
            )
        else:
            print("    (skipped - expand button not found)")

        # 8. Full-screen Session View - Data Streams
        print("  8/10: Data streams visualization")
        # Wait for streams to load (they load async)
        page.wait_for_selector(".stream-header", timeout=10000)
        page.wait_for_timeout(500)  # Let charts render
        # Scroll the container (not window) to show data streams section
        page.evaluate("""() => {
            const container = document.querySelector('.full-session-container');
            const header = document.querySelector('.stream-header');
            if (container && header) {
                // Scroll container to put header at top with some padding
                const headerTop = header.offsetTop;
                container.scrollTo({ top: headerTop - 80, behavior: 'instant' });
            }
        }""")
        page.wait_for_timeout(500)  # Wait for scroll to complete
        # Check if charts exist
        if (
            page.locator("#elevation-chart").count() > 0
            or page.locator("#activity-chart").count() > 0
        ):
            screenshots.append(
                take_screenshot(page, output_dir / "08-data-streams", "Activity data streams")
            )
        else:
            print("    (no stream data available)")

        # 9. Stats View
        print("  9/10: Stats view")
        page.locator(".nav-tab[data-view='stats']").click()
        page.wait_for_selector("#view-stats.active", timeout=5000)
        page.wait_for_timeout(1000)  # Wait for charts to render
        screenshots.append(
            take_screenshot(page, output_dir / "09-stats-dashboard", "Statistics dashboard")
        )

        # 10. Stats View - Filtered by athlete
        print("  10/10: Stats view (filtered)")
        page.select_option("#athlete-selector", "alice")
        page.wait_for_timeout(500)
        screenshots.append(
            take_screenshot(page, output_dir / "10-stats-filtered", "Statistics by athlete")
        )

        browser.close()

    # QC: Validate screenshots
    print("\nValidating screenshots...")
    sizes = [s[2] for s in screenshots]
    min_size = 5000  # Minimum 5KB for a valid screenshot

    # Check for empty/degenerate files
    for filename, _caption, size in screenshots:
        if size < min_size:
            print(f"  WARNING: {filename} is suspiciously small ({size} bytes)")

    # Check for duplicate screenshots (same size often means identical)
    if len(sizes) != len(set(sizes)):
        print("  WARNING: Some screenshots have identical sizes (may be duplicates)")

    # Check that sizes vary reasonably (different content)
    size_variance = max(sizes) - min(sizes)
    if size_variance < 1000:
        print(f"  WARNING: Screenshot sizes too similar (variance: {size_variance} bytes)")

    total_size = sum(sizes)
    print(f"\nSaved {len(screenshots)} screenshots to {output_dir}")
    print(
        f"Total size: {total_size / 1024:.1f} KB (avg: {total_size / len(screenshots) / 1024:.1f} KB each)"
    )

    # Return without sizes for compatibility
    return [(f, c) for f, c, _ in screenshots]


def generate_readme_section(screenshots: list[tuple[str, str]]) -> str:
    """Generate markdown for README.md screenshots section."""
    lines = [
        "## Screenshots",
        "",
        "The unified web frontend provides a complete activity browsing experience.",
        "Screenshots are auto-generated from the demo dataset (`tox -e screenshots`).",
        "",
    ]

    # Group screenshots by view
    views = {
        "Map View": ["01-", "02-", "03-"],
        "Sessions View": ["04-", "05-", "06-"],
        "Session Detail": ["07-", "08-"],
        "Statistics": ["09-", "10-"],
    }

    for view_name, prefixes in views.items():
        view_screenshots = [
            (f, c) for f, c in screenshots if any(f.startswith(p) for p in prefixes)
        ]
        if view_screenshots:
            lines.append(f"### {view_name}")
            lines.append("")
            for filename, caption in view_screenshots:
                lines.append(f"![{caption}](docs/screenshots/{filename})")
                lines.append(f"*{caption}*")
                lines.append("")

    lines.append("---")
    lines.append("*Screenshots generated with `tox -e screenshots`*")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate screenshots for documentation")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "docs" / "screenshots",
        help="Output directory for screenshots",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode (for debugging)",
    )
    parser.add_argument(
        "--print-readme",
        action="store_true",
        help="Print README markdown section after generating",
    )
    args = parser.parse_args()

    # Check playwright is available
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        print("Error: playwright not installed. Run: pip install playwright")
        return 1

    # Create temp directory for demo data
    import tempfile

    with tempfile.TemporaryDirectory(prefix="mykrok-screenshots-") as tmpdir:
        data_dir = Path(tmpdir)

        # Generate demo data and HTML
        generate_demo_data(data_dir)
        generate_html(data_dir)

        # Start server
        port = 18081
        proc = start_server(data_dir, port)

        try:
            # Capture screenshots
            screenshots = capture_screenshots(
                f"http://127.0.0.1:{port}",
                args.output_dir,
                headless=not args.no_headless,
            )

            # Print README section if requested
            if args.print_readme:
                print("\n" + "=" * 60)
                print("README.md section:")
                print("=" * 60)
                print(generate_readme_section(screenshots))

        finally:
            # Stop server
            proc.terminate()
            proc.wait(timeout=5)

    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
