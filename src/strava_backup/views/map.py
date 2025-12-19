"""Map visualization for strava-backup.

Generates interactive HTML maps using Leaflet.js with optional heatmap mode.
"""

from __future__ import annotations

import http.server
import json
import socketserver
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from strava_backup.lib.paths import iter_athlete_dirs, iter_session_dirs, parse_session_datetime
from strava_backup.models.activity import load_activity
from strava_backup.models.tracking import get_coordinates, load_tracking_manifest


def generate_map(
    data_dir: Path,
    after: datetime | None = None,
    before: datetime | None = None,
    activity_type: str | None = None,
    heatmap: bool = False,
) -> str:
    """Generate HTML map of activities.

    Args:
        data_dir: Base data directory.
        after: Only include activities after this date.
        before: Only include activities before this date.
        activity_type: Filter by activity type.
        heatmap: Generate heatmap instead of individual routes.

    Returns:
        HTML content as string.
    """
    # Collect all routes
    routes: list[dict[str, Any]] = []
    all_points: list[tuple[float, float]] = []

    for _username, athlete_dir in iter_athlete_dirs(data_dir):
        for session_key, session_dir in iter_session_dirs(athlete_dir):
            # Filter by date
            try:
                session_date = parse_session_datetime(session_key)
            except ValueError:
                continue

            if after and session_date < after:
                continue
            if before and session_date > before:
                continue

            # Check for GPS data
            manifest = load_tracking_manifest(session_dir)
            if not manifest or not manifest.has_gps:
                continue

            # Load activity metadata
            activity = load_activity(session_dir)
            if not activity:
                continue

            # Filter by type
            if activity_type and activity.type.lower() != activity_type.lower():
                continue

            # Get coordinates
            coords = get_coordinates(session_dir)
            if not coords:
                continue

            if heatmap:
                all_points.extend(coords)
            else:
                routes.append({
                    "name": activity.name,
                    "type": activity.type,
                    "date": session_date.strftime("%Y-%m-%d"),
                    "distance_km": round(activity.distance / 1000, 2) if activity.distance else 0,
                    "coords": coords,
                })

    if heatmap:
        return _generate_heatmap_html(all_points)
    else:
        return _generate_routes_html(routes)


def _generate_routes_html(routes: list[dict[str, Any]]) -> str:
    """Generate HTML with individual route polylines.

    Args:
        routes: List of route data dictionaries.

    Returns:
        HTML content.
    """
    # Calculate map bounds
    all_coords: list[tuple[float, float]] = []
    for route in routes:
        all_coords.extend(route["coords"])

    if not all_coords:
        center = [0, 0]
        zoom = 2
    else:
        lats = [c[0] for c in all_coords]
        lngs = [c[1] for c in all_coords]
        center = [(min(lats) + max(lats)) / 2, (min(lngs) + max(lngs)) / 2]
        # Rough zoom calculation based on bounds
        lat_span = max(lats) - min(lats)
        lng_span = max(lngs) - min(lngs)
        span = max(lat_span, lng_span)
        if span < 0.01:
            zoom = 15
        elif span < 0.1:
            zoom = 12
        elif span < 1:
            zoom = 10
        elif span < 10:
            zoom = 7
        else:
            zoom = 4

    # Color palette for activity types
    type_colors = {
        "Run": "#FF5722",
        "Ride": "#2196F3",
        "Hike": "#4CAF50",
        "Walk": "#9C27B0",
        "Swim": "#00BCD4",
        "Other": "#607D8B",
    }

    # Prepare route data for JavaScript
    routes_json = []
    for route in routes:
        color = type_colors.get(route["type"], type_colors["Other"])
        routes_json.append({
            "name": route["name"],
            "type": route["type"],
            "date": route["date"],
            "distance_km": route["distance_km"],
            "coords": route["coords"],
            "color": color,
        })

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Strava Activities Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        .info {{
            padding: 6px 8px;
            font: 14px/16px Arial, Helvetica, sans-serif;
            background: white;
            background: rgba(255,255,255,0.9);
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
            border-radius: 5px;
        }}
        .legend {{
            line-height: 18px;
            color: #555;
        }}
        .legend i {{
            width: 18px;
            height: 18px;
            float: left;
            margin-right: 8px;
            opacity: 0.7;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        var map = L.map('map', {{
            preferCanvas: true
        }}).setView({center}, {zoom});

        L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }}).addTo(map);

        var routes = {json.dumps(routes_json)};
        var bounds = L.latLngBounds();

        routes.forEach(function(route) {{
            if (route.coords.length === 0) return;

            var polyline = L.polyline(route.coords, {{
                color: route.color,
                weight: 3,
                opacity: 0.7
            }}).addTo(map);

            polyline.bindPopup(
                '<b>' + route.name + '</b><br>' +
                'Type: ' + route.type + '<br>' +
                'Date: ' + route.date + '<br>' +
                'Distance: ' + route.distance_km + ' km'
            );

            bounds.extend(polyline.getBounds());
        }});

        if (routes.length > 0) {{
            map.fitBounds(bounds, {{ padding: [20, 20] }});
        }}

        // Legend
        var legend = L.control({{position: 'bottomright'}});
        legend.onAdd = function(map) {{
            var div = L.DomUtil.create('div', 'info legend');
            var types = {json.dumps(type_colors)};
            div.innerHTML = '<b>Activity Types</b><br>';
            for (var type in types) {{
                div.innerHTML += '<i style="background:' + types[type] + '"></i> ' + type + '<br>';
            }}
            return div;
        }};
        legend.addTo(map);

        // Info control
        var info = L.control({{position: 'topright'}});
        info.onAdd = function(map) {{
            var div = L.DomUtil.create('div', 'info');
            div.innerHTML = '<b>Activities</b><br>' + routes.length + ' routes';
            return div;
        }};
        info.addTo(map);
    </script>
</body>
</html>"""


def _generate_heatmap_html(points: list[tuple[float, float]]) -> str:
    """Generate HTML with heatmap layer.

    Args:
        points: List of (lat, lng) coordinate tuples.

    Returns:
        HTML content.
    """
    if not points:
        center = [0, 0]
        zoom = 2
    else:
        lats = [p[0] for p in points]
        lngs = [p[1] for p in points]
        center = [(min(lats) + max(lats)) / 2, (min(lngs) + max(lngs)) / 2]
        lat_span = max(lats) - min(lats)
        lng_span = max(lngs) - min(lngs)
        span = max(lat_span, lng_span)
        if span < 0.01:
            zoom = 15
        elif span < 0.1:
            zoom = 12
        elif span < 1:
            zoom = 10
        elif span < 10:
            zoom = 7
        else:
            zoom = 4

    # Sample points if too many (for performance)
    max_points = 50000
    if len(points) > max_points:
        step = len(points) // max_points
        points = points[::step]

    # Convert to format for leaflet.heat [lat, lng, intensity]
    heat_data = [[p[0], p[1], 1.0] for p in points]

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Strava Activities Heatmap</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        .info {{
            padding: 6px 8px;
            font: 14px/16px Arial, Helvetica, sans-serif;
            background: white;
            background: rgba(255,255,255,0.9);
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script>
        var map = L.map('map').setView({center}, {zoom});

        L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }}).addTo(map);

        var heatData = {json.dumps(heat_data)};

        var heat = L.heatLayer(heatData, {{
            radius: 15,
            blur: 20,
            maxZoom: 17,
            gradient: {{
                0.0: 'blue',
                0.25: 'cyan',
                0.5: 'lime',
                0.75: 'yellow',
                1.0: 'red'
            }}
        }}).addTo(map);

        // Fit bounds to data
        if (heatData.length > 0) {{
            var lats = heatData.map(function(p) {{ return p[0]; }});
            var lngs = heatData.map(function(p) {{ return p[1]; }});
            var bounds = [
                [Math.min.apply(null, lats), Math.min.apply(null, lngs)],
                [Math.max.apply(null, lats), Math.max.apply(null, lngs)]
            ];
            map.fitBounds(bounds, {{ padding: [20, 20] }});
        }}

        // Info control
        var info = L.control({{position: 'topright'}});
        info.onAdd = function(map) {{
            var div = L.DomUtil.create('div', 'info');
            div.innerHTML = '<b>Heatmap</b><br>' + heatData.length.toLocaleString() + ' points';
            return div;
        }};
        info.addTo(map);
    </script>
</body>
</html>"""


def serve_map(
    html_path: Path,
    port: int = 8080,
    host: str = "127.0.0.1",
    open_browser: bool = True,
) -> None:
    """Start a local HTTP server to serve the map.

    Args:
        html_path: Path to the HTML file.
        port: Server port.
        host: Server host.
        open_browser: Open browser automatically.
    """
    # Change to directory containing the HTML file
    directory = html_path.parent

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, format: str, *args: object) -> None:
            pass  # Suppress logging

    with socketserver.TCPServer((host, port), Handler) as httpd:
        url = f"http://{host}:{port}/{html_path.name}"
        print(f"Serving at {url}")
        print("Press Ctrl+C to stop")

        if open_browser:
            webbrowser.open(url)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped")
