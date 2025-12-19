"""Local activity browser for strava-backup.

Provides a web-based interface to browse backed-up activities offline.
"""

from __future__ import annotations

import html
import http.server
import json
import mimetypes
import socketserver
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from strava_backup.lib.paths import (
    get_photos_dir,
    get_session_dir,
    iter_athlete_dirs,
    iter_session_dirs,
    parse_session_datetime,
)
from strava_backup.models.activity import load_activity
from strava_backup.models.tracking import get_coordinates, load_tracking_manifest


class ActivityBrowserHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for activity browser."""

    data_dir: Path  # Set by start_browser()

    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_activity_list()
        elif path.startswith("/activity/"):
            session_key = path.split("/activity/")[1].rstrip("/")
            self._serve_activity_detail(session_key)
        elif path.startswith("/api/activities"):
            self._serve_activities_json()
        elif path.startswith("/api/activity/"):
            session_key = path.split("/api/activity/")[1].rstrip("/")
            self._serve_activity_json(session_key)
        elif path.startswith("/photos/"):
            self._serve_photo(path)
        elif path.startswith("/static/"):
            self._serve_static(path)
        else:
            self.send_error(404, "Not Found")

    def _serve_activity_list(self) -> None:
        """Serve the activity list page."""
        activities = self._get_all_activities()

        content = self._render_activity_list(activities)
        self._send_html(content)

    def _serve_activity_detail(self, session_key: str) -> None:
        """Serve an activity detail page."""
        activity_data = self._get_activity_data(session_key)
        if not activity_data:
            self.send_error(404, "Activity not found")
            return

        content = self._render_activity_detail(activity_data)
        self._send_html(content)

    def _serve_activities_json(self) -> None:
        """Serve activities as JSON."""
        activities = self._get_all_activities()
        self._send_json(activities)

    def _serve_activity_json(self, session_key: str) -> None:
        """Serve a single activity as JSON."""
        activity_data = self._get_activity_data(session_key)
        if not activity_data:
            self.send_error(404, "Activity not found")
            return
        self._send_json(activity_data)

    def _serve_photo(self, path: str) -> None:
        """Serve a photo file."""
        # Path format: /photos/{username}/{session_key}/{filename}
        parts = path.split("/photos/")[1].split("/")
        if len(parts) < 3:
            self.send_error(404, "Not Found")
            return

        username, session_key, filename = parts[0], parts[1], "/".join(parts[2:])

        # Find session directory
        for uname, _athlete_dir in iter_athlete_dirs(self.data_dir):
            if uname == username:
                try:
                    session_date = parse_session_datetime(session_key)
                    session_dir = get_session_dir(self.data_dir, username, session_date)
                    photos_dir = get_photos_dir(session_dir)
                    photo_path = photos_dir / filename

                    if photo_path.exists():
                        self._serve_file(photo_path)
                        return
                except (ValueError, FileNotFoundError):
                    pass

        self.send_error(404, "Photo not found")

    def _serve_static(self, _path: str) -> None:
        """Serve static content (CSS, JS)."""
        # For now, we embed everything in HTML
        self.send_error(404, "Not Found")

    def _serve_file(self, path: Path) -> None:
        """Serve a file."""
        content_type, _ = mimetypes.guess_type(str(path))
        if content_type is None:
            content_type = "application/octet-stream"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()

        with open(path, "rb") as f:
            self.wfile.write(f.read())

    def _send_html(self, content: str) -> None:
        """Send HTML response."""
        encoded = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, data: Any) -> None:
        """Send JSON response."""
        content = json.dumps(data, default=str)
        encoded = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _get_all_activities(self) -> list[dict[str, Any]]:
        """Get all activities for listing."""
        activities: list[dict[str, Any]] = []

        for username, athlete_dir in iter_athlete_dirs(self.data_dir):
            for session_key, session_dir in iter_session_dirs(athlete_dir):
                activity = load_activity(session_dir)
                if not activity:
                    continue

                manifest = load_tracking_manifest(session_dir)

                activities.append({
                    "session_key": session_key,
                    "username": username,
                    "name": activity.name,
                    "type": activity.type,
                    "date": activity.start_date.strftime("%Y-%m-%d %H:%M") if activity.start_date else "",
                    "distance_km": round(activity.distance / 1000, 2) if activity.distance else 0,
                    "moving_time": activity.moving_time or 0,
                    "has_gps": manifest.has_gps if manifest else False,
                    "has_photos": activity.has_photos,
                    "photo_count": activity.photo_count,
                })

        # Sort by date descending
        activities.sort(key=lambda a: a["date"], reverse=True)
        return activities

    def _get_activity_data(self, session_key: str) -> dict[str, Any] | None:
        """Get detailed activity data."""
        for username, athlete_dir in iter_athlete_dirs(self.data_dir):
            for skey, session_dir in iter_session_dirs(athlete_dir):
                if skey == session_key:
                    activity = load_activity(session_dir)
                    if not activity:
                        return None

                    manifest = load_tracking_manifest(session_dir)
                    coords = get_coordinates(session_dir) if manifest and manifest.has_gps else []

                    # Get photo filenames
                    photos_dir = get_photos_dir(session_dir)
                    photos: list[str] = []
                    if photos_dir.exists():
                        photos = [
                            f"/photos/{username}/{session_key}/{f.name}"
                            for f in photos_dir.iterdir()
                            if f.suffix.lower() in (".jpg", ".jpeg", ".png")
                        ]

                    return {
                        "session_key": session_key,
                        "username": username,
                        "activity": activity.to_dict(),
                        "has_gps": manifest.has_gps if manifest else False,
                        "coords": coords,
                        "photos": photos,
                    }

        return None

    def _render_activity_list(self, activities: list[dict[str, Any]]) -> str:
        """Render activity list HTML."""
        rows = []
        for act in activities:
            time_str = f"{act['moving_time'] // 60}m {act['moving_time'] % 60}s"
            gps_badge = '<span class="badge gps">GPS</span>' if act["has_gps"] else ""
            photo_badge = f'<span class="badge photo">{act["photo_count"]} photos</span>' if act["has_photos"] else ""

            rows.append(f"""
            <tr onclick="window.location='/activity/{act['session_key']}'">
                <td>{html.escape(act['date'])}</td>
                <td>{html.escape(act['type'])}</td>
                <td>{html.escape(act['name'])}</td>
                <td>{act['distance_km']:.2f} km</td>
                <td>{time_str}</td>
                <td>{gps_badge} {photo_badge}</td>
            </tr>
            """)

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Strava Backup Browser</title>
    <style>
        {self._get_common_css()}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background-color: #f5f5f5; cursor: pointer; }}
        th {{ background-color: #fc4c02; color: white; }}
        .badge {{ padding: 2px 6px; border-radius: 4px; font-size: 12px; margin-right: 4px; }}
        .gps {{ background: #4CAF50; color: white; }}
        .photo {{ background: #2196F3; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Strava Backup Browser</h1>
        <p>Found {len(activities)} activities</p>
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th>Name</th>
                    <th>Distance</th>
                    <th>Time</th>
                    <th>Data</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>
</body>
</html>"""

    def _render_activity_detail(self, data: dict[str, Any]) -> str:
        """Render activity detail HTML."""
        activity = data["activity"]
        coords = data["coords"]
        photos = data["photos"]

        # Format values
        distance_km = activity.get("distance", 0) / 1000
        moving_time = activity.get("moving_time", 0)
        time_str = f"{moving_time // 3600}h {(moving_time % 3600) // 60}m {moving_time % 60}s"
        elevation = activity.get("total_elevation_gain", 0) or 0

        # Map section
        map_html = ""
        if coords:
            coords_json = json.dumps(coords)
            map_html = f"""
            <div id="map"></div>
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <script>
                var map = L.map('map');
                L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19,
                    attribution: '&copy; OpenStreetMap'
                }}).addTo(map);
                var coords = {coords_json};
                var polyline = L.polyline(coords, {{color: '#fc4c02', weight: 3}}).addTo(map);
                map.fitBounds(polyline.getBounds(), {{padding: [20, 20]}});
            </script>
            """

        # Photos section
        photos_html = ""
        if photos:
            photo_items = "".join(
                f'<div class="photo"><img src="{p}" loading="lazy"></div>'
                for p in photos
            )
            photos_html = f"""
            <h2>Photos ({len(photos)})</h2>
            <div class="photos">{photo_items}</div>
            """

        # Comments section
        comments_html = ""
        comments = activity.get("comments", [])
        if comments:
            comment_items = "".join(
                f'<div class="comment"><strong>{html.escape(c.get("athlete_firstname", ""))} '
                f'{html.escape(c.get("athlete_lastname", ""))}</strong>: '
                f'{html.escape(c.get("text", ""))}</div>'
                for c in comments
            )
            comments_html = f"""
            <h2>Comments ({len(comments)})</h2>
            <div class="comments">{comment_items}</div>
            """

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(activity.get('name', 'Activity'))}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <style>
        {self._get_common_css()}
        #map {{ height: 400px; margin: 20px 0; border-radius: 8px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin: 20px 0; }}
        .stat {{ background: #f5f5f5; padding: 16px; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #fc4c02; }}
        .stat-label {{ color: #666; font-size: 14px; }}
        .photos {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }}
        .photo img {{ width: 100%; border-radius: 8px; }}
        .comments {{ background: #f9f9f9; padding: 16px; border-radius: 8px; }}
        .comment {{ padding: 8px 0; border-bottom: 1px solid #eee; }}
        .back {{ display: inline-block; margin-bottom: 20px; color: #fc4c02; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back">&larr; Back to activities</a>
        <h1>{html.escape(activity.get('name', 'Activity'))}</h1>
        <p>{html.escape(activity.get('type', ''))} - {activity.get('start_date_local', '')[:10]}</p>

        <div class="stats">
            <div class="stat">
                <div class="stat-value">{distance_km:.2f}</div>
                <div class="stat-label">Kilometers</div>
            </div>
            <div class="stat">
                <div class="stat-value">{time_str}</div>
                <div class="stat-label">Moving Time</div>
            </div>
            <div class="stat">
                <div class="stat-value">{elevation:.0f}</div>
                <div class="stat-label">Elevation (m)</div>
            </div>
            <div class="stat">
                <div class="stat-value">{activity.get('kudos_count', 0)}</div>
                <div class="stat-label">Kudos</div>
            </div>
        </div>

        {map_html}
        {photos_html}
        {comments_html}

        <h2>Details</h2>
        <p><strong>Description:</strong> {html.escape(activity.get('description', '') or 'No description')}</p>
        <p><strong>Device:</strong> {html.escape(activity.get('device_name', '') or 'Unknown')}</p>
        <p><strong>Gear ID:</strong> {html.escape(activity.get('gear_id', '') or 'None')}</p>
    </div>
</body>
</html>"""

    def _get_common_css(self) -> str:
        """Get common CSS styles."""
        return """
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               margin: 0; padding: 20px; background: #fff; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #fc4c02; }
        """

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default logging."""
        pass


def start_browser(
    data_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = True,
) -> None:
    """Start the activity browser server.

    Args:
        data_dir: Base data directory.
        host: Server host.
        port: Server port.
        open_browser: Open browser automatically.
    """
    ActivityBrowserHandler.data_dir = data_dir

    with socketserver.TCPServer((host, port), ActivityBrowserHandler) as httpd:
        url = f"http://{host}:{port}/"
        print(f"Activity browser available at {url}")
        print("Press Ctrl+C to stop")

        if open_browser:
            webbrowser.open(url)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nBrowser stopped")
