#!/usr/bin/env python3
"""Generate screenshots of the unified frontend for documentation.

This script uses Playwright to automate a browser walkthrough of the
strava-backup web interface, capturing screenshots at key points.
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


def generate_demo_data(output_dir: Path) -> None:
    """Generate demo data for screenshots."""
    from generate_fixtures import generate_fixtures

    random.seed(42)  # Reproducible fixtures
    generate_fixtures(output_dir)
    print(f"Generated demo data in {output_dir}")


def generate_html(data_dir: Path) -> Path:
    """Generate the HTML file and copy assets."""
    from strava_backup.views.map import copy_assets_to_output, generate_lightweight_map

    html = generate_lightweight_map(data_dir)
    html_path = data_dir / "strava-backup.html"
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


def capture_screenshots(
    base_url: str,
    output_dir: Path,
    headless: bool = True,
) -> list[tuple[str, str]]:
    """Capture screenshots using Playwright.

    Returns list of (filename, caption) tuples.
    """
    from playwright.sync_api import sync_playwright

    screenshots: list[tuple[str, str]] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        print("\nCapturing screenshots...")

        # 1. Map View - World view with all markers
        print("  1/9: Map view (world)")
        page.goto(f"{base_url}/strava-backup.html#/map")
        page.wait_for_selector(".leaflet-marker-icon", timeout=15000)
        # Wait for all markers to load and let map settle
        page.wait_for_timeout(3000)
        page.screenshot(path=output_dir / "01-map-world.png")
        screenshots.append(("01-map-world.png", "World map with activity markers"))

        # 2. Map View - Zoomed to activity cluster
        print("  2/9: Map view (zoomed)")
        # Use JavaScript to zoom to fit all markers in view
        page.evaluate("""() => {
            if (window.mapInstance && window.MapView && window.MapView.bounds) {
                // Fit to the bounds that contain all markers
                if (window.MapView.bounds.isValid()) {
                    window.mapInstance.fitBounds(window.MapView.bounds, {padding: [50, 50]});
                }
            }
        }""")
        page.wait_for_timeout(1500)
        page.screenshot(path=output_dir / "02-map-zoomed.png")
        screenshots.append(("02-map-zoomed.png", "Activity cluster with route details"))

        # 3. Map View - Marker popup
        print("  3/9: Map view (popup)")
        # Click a marker using JavaScript to trigger the popup
        page.evaluate("""() => {
            const markers = document.querySelectorAll('.leaflet-marker-icon');
            if (markers.length > 0) {
                // Find a marker that's visible in viewport
                for (const marker of markers) {
                    const rect = marker.getBoundingClientRect();
                    if (rect.top > 0 && rect.left > 0 &&
                        rect.bottom < window.innerHeight && rect.right < window.innerWidth) {
                        marker.click();
                        return;
                    }
                }
                // Fallback: click first marker anyway
                markers[0].click();
            }
        }""")
        page.wait_for_timeout(1000)
        # Check if popup appeared, if not try force click
        if page.locator(".leaflet-popup").count() == 0:
            page.locator(".leaflet-marker-icon").first.click(force=True)
        page.wait_for_selector(".leaflet-popup", timeout=5000)
        page.wait_for_timeout(500)
        page.screenshot(path=output_dir / "03-map-popup.png")
        screenshots.append(("03-map-popup.png", "Activity popup with details"))

        # 4. Sessions View - Table with all sessions
        print("  4/9: Sessions view")
        page.locator(".nav-tab[data-view='sessions']").click()
        page.wait_for_selector("#view-sessions.active", timeout=5000)
        page.wait_for_selector("#sessions-table tbody tr", timeout=10000)
        page.wait_for_timeout(500)
        page.screenshot(path=output_dir / "04-sessions-list.png")
        screenshots.append(("04-sessions-list.png", "Sessions list with filters"))

        # 5. Sessions View - Filtered by type
        print("  5/9: Sessions view (filtered)")
        page.select_option("#type-filter", "Run")
        page.wait_for_timeout(500)
        page.screenshot(path=output_dir / "05-sessions-filtered.png")
        screenshots.append(("05-sessions-filtered.png", "Sessions filtered by activity type"))

        # Clear filter
        page.select_option("#type-filter", "")
        page.wait_for_timeout(300)

        # 6. Sessions View - Detail panel
        print("  6/9: Session detail panel")
        page.locator("#sessions-table tbody tr").first.click()
        page.wait_for_selector(".detail-panel.open", timeout=5000)
        page.wait_for_timeout(1000)  # Wait for map to load
        page.screenshot(path=output_dir / "06-session-detail.png")
        screenshots.append(("06-session-detail.png", "Session detail panel with map"))

        # 7. Full-screen Session View
        print("  7/9: Full-screen session view")
        page.locator(".detail-expand-btn").click()
        page.wait_for_selector("#view-session.active", timeout=5000)
        page.wait_for_timeout(2000)  # Wait for content to load
        page.screenshot(path=output_dir / "07-session-full.png")
        screenshots.append(("07-session-full.png", "Full-screen session view"))

        # 8. Stats View
        print("  8/9: Stats view")
        page.locator(".nav-tab[data-view='stats']").click()
        page.wait_for_selector("#view-stats.active", timeout=5000)
        page.wait_for_timeout(1000)  # Wait for charts to render
        page.screenshot(path=output_dir / "08-stats-dashboard.png")
        screenshots.append(("08-stats-dashboard.png", "Statistics dashboard"))

        # 9. Stats View - Filtered by athlete
        print("  9/9: Stats view (filtered)")
        page.select_option("#athlete-select", "alice")
        page.wait_for_timeout(500)
        page.screenshot(path=output_dir / "09-stats-filtered.png")
        screenshots.append(("09-stats-filtered.png", "Statistics filtered by athlete"))

        browser.close()

    print(f"\nSaved {len(screenshots)} screenshots to {output_dir}")
    return screenshots


def generate_readme_section(screenshots: list[tuple[str, str]]) -> str:
    """Generate markdown for README.md screenshots section."""
    lines = [
        "## Screenshots",
        "",
        "The unified web frontend provides a complete activity browsing experience.",
        "Screenshots are auto-generated from the demo dataset.",
        "",
    ]

    # Group screenshots by view
    views = {
        "Map View": ["01-", "02-", "03-"],
        "Sessions View": ["04-", "05-", "06-"],
        "Session Detail": ["07-"],
        "Statistics": ["08-", "09-"],
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

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate screenshots for documentation"
    )
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

    with tempfile.TemporaryDirectory(prefix="strava-screenshots-") as tmpdir:
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
