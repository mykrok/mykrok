"""Map visualization for strava-backup.

Generates interactive HTML maps using Leaflet.js with optional heatmap mode
and photo overlay support.
"""

from __future__ import annotations

import http.server
import importlib.resources
import json
import shutil
import socketserver
from datetime import datetime
from pathlib import Path
from typing import Any

from strava_backup.lib.paths import (
    ATHLETE_PREFIX,
    get_photos_dir,
    iter_athlete_dirs,
    iter_session_dirs,
    parse_session_datetime,
)
from strava_backup.models.activity import load_activity
from strava_backup.models.tracking import get_coordinates, load_tracking_manifest


def _get_assets_dir() -> Path:
    """Get path to bundled assets directory."""
    # Use importlib.resources for Python 3.9+
    try:
        files = importlib.resources.files("strava_backup")
        return Path(str(files / "assets"))
    except (AttributeError, TypeError):
        # Fallback for older Python or editable installs
        return Path(__file__).parent.parent / "assets"


def copy_assets_to_output(output_dir: Path) -> Path:
    """Copy bundled JS/CSS assets to output directory.

    Args:
        output_dir: Directory to copy assets to.

    Returns:
        Path to the assets subdirectory.
    """
    assets_src = _get_assets_dir()
    assets_dst = output_dir / "assets"
    assets_dst.mkdir(parents=True, exist_ok=True)

    # Copy Leaflet
    leaflet_src = assets_src / "leaflet"
    leaflet_dst = assets_dst / "leaflet"
    if leaflet_src.exists():
        if leaflet_dst.exists():
            shutil.rmtree(leaflet_dst)
        shutil.copytree(leaflet_src, leaflet_dst)

    # Copy hyparquet
    hyparquet_src = assets_src / "hyparquet"
    hyparquet_dst = assets_dst / "hyparquet"
    if hyparquet_src.exists():
        if hyparquet_dst.exists():
            shutil.rmtree(hyparquet_dst)
        shutil.copytree(hyparquet_src, hyparquet_dst)

    # Copy logo
    logo_src = assets_src / "strava-backup-icon.svg"
    if logo_src.exists():
        shutil.copy2(logo_src, assets_dst / "strava-backup-icon.svg")

    return assets_dst


def _collect_geotagged_photos(
    data_dir: Path,
    after: datetime | None = None,
    before: datetime | None = None,
    activity_type: str | None = None,
) -> list[dict[str, Any]]:
    """Collect all geotagged photos from activities.

    Args:
        data_dir: Base data directory.
        after: Only include photos from activities after this date.
        before: Only include photos from activities before this date.
        activity_type: Filter by activity type.

    Returns:
        List of photo data dictionaries with location info.
    """
    photos: list[dict[str, Any]] = []

    for username, athlete_dir in iter_athlete_dirs(data_dir):
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

            # Load activity metadata
            activity = load_activity(session_dir)
            if not activity:
                continue

            # Filter by type
            if activity_type and activity.type.lower() != activity_type.lower():
                continue

            # Check for photos with location data
            if not activity.photos:
                continue

            photos_dir = get_photos_dir(session_dir)

            for photo in activity.photos:
                location_raw = photo.get("location")
                if not location_raw or len(location_raw) == 0:
                    continue

                # Extract coordinates from nested structure: [["root", [lat, lng]]]
                try:
                    location = location_raw[0][1]
                    if not location or len(location) < 2:
                        continue
                except (IndexError, TypeError):
                    continue

                # Get photo file path (for local serving)
                photo_created = photo.get("created_at", "")
                local_path = None
                if photos_dir.exists() and photo_created:
                    # Parse created_at to match local filename format (YYYYMMDDTHHMMSS.jpg)
                    try:
                        # Handle ISO format with timezone: 2025-01-30T01:59:56+00:00
                        created_str = photo_created.replace("+00:00", "").replace("Z", "")
                        created_dt = datetime.fromisoformat(created_str)
                        expected_filename = created_dt.strftime("%Y%m%dT%H%M%S")

                        # Look for matching photo file
                        for photo_file in photos_dir.iterdir():
                            if photo_file.is_file() and photo_file.stem == expected_filename:
                                local_path = f"{ATHLETE_PREFIX}{username}/ses={session_key}/photos/{photo_file.name}"
                                break
                    except (ValueError, AttributeError):
                        pass  # Skip if can't parse timestamp

                photos.append({
                    "lat": location[0],
                    "lng": location[1],
                    "activity_name": activity.name,
                    "activity_type": activity.type,
                    "activity_date": session_date.strftime("%Y-%m-%d"),
                    "photo_date": photo_created,
                    "urls": photo.get("urls", {}),
                    "local_path": local_path,
                    "session_key": session_key,
                })

    return photos


def generate_map(
    data_dir: Path,
    after: datetime | None = None,
    before: datetime | None = None,
    activity_type: str | None = None,
    heatmap: bool = False,
    show_photos: bool = False,
) -> str:
    """Generate HTML map of activities.

    Args:
        data_dir: Base data directory.
        after: Only include activities after this date.
        before: Only include activities before this date.
        activity_type: Filter by activity type.
        heatmap: Generate heatmap instead of individual routes.
        show_photos: Include geotagged photos as markers.

    Returns:
        HTML content as string.
    """
    # Collect all routes
    routes: list[dict[str, Any]] = []
    all_points: list[tuple[float, float]] = []
    photos: list[dict[str, Any]] = []

    # Collect photos if requested
    if show_photos:
        photos = _collect_geotagged_photos(data_dir, after, before, activity_type)

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
        return _generate_heatmap_html(all_points, photos)
    else:
        return _generate_routes_html(routes, photos)


def _generate_routes_html(
    routes: list[dict[str, Any]],
    photos: list[dict[str, Any]] | None = None,
) -> str:
    """Generate HTML with individual route polylines and optional photo markers.

    Args:
        routes: List of route data dictionaries.
        photos: Optional list of geotagged photo data.

    Returns:
        HTML content.
    """
    if photos is None:
        photos = []
    # Calculate map bounds
    all_coords: list[tuple[float, float]] = []
    for route in routes:
        all_coords.extend(route["coords"])

    if not all_coords:
        center: list[float] = [0.0, 0.0]
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

    # Photo count for info display
    photo_count = len(photos)

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Strava Activities Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css">
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css">
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
        .photo-icon {{
            background: #E91E63;
            border: 2px solid white;
            border-radius: 50%;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        }}
        .photo-popup {{
            max-width: 350px;
        }}
        .photo-popup img {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            cursor: pointer;
        }}
        .photo-popup .photo-meta {{
            font-size: 12px;
            color: #666;
            margin-top: 8px;
        }}
        .photo-gallery {{
            max-height: 400px;
            overflow-y: auto;
        }}
        .photo-gallery .photo-item {{
            margin-bottom: 12px;
            padding-bottom: 12px;
            border-bottom: 1px solid #eee;
        }}
        .photo-gallery .photo-item:last-child {{
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }}
        .photo-gallery-header {{
            font-weight: bold;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 2px solid #E91E63;
        }}
        .layer-toggle {{
            background: white;
            padding: 8px 12px;
            border-radius: 5px;
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
        }}
        .layer-toggle label {{
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .photo-source-toggle {{
            background: white;
            padding: 8px 12px;
            border-radius: 5px;
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
            font: 12px/14px Arial, Helvetica, sans-serif;
        }}
        .photo-source-toggle label {{
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .toggle-switch {{
            position: relative;
            width: 40px;
            height: 20px;
        }}
        .toggle-switch input {{
            opacity: 0;
            width: 0;
            height: 0;
        }}
        .toggle-slider {{
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #4CAF50;
            border-radius: 20px;
            transition: 0.3s;
        }}
        .toggle-slider:before {{
            position: absolute;
            content: "";
            height: 14px;
            width: 14px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            border-radius: 50%;
            transition: 0.3s;
        }}
        .toggle-switch input:checked + .toggle-slider {{
            background-color: #2196F3;
        }}
        .toggle-switch input:checked + .toggle-slider:before {{
            transform: translateX(20px);
        }}
        .source-label {{
            font-size: 11px;
            color: #666;
        }}
        .source-label.active {{
            font-weight: bold;
            color: #333;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
    <script>
        var map = L.map('map', {{
            preferCanvas: true
        }}).setView({center}, {zoom});

        L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }}).addTo(map);

        var routes = {json.dumps(routes_json)};
        var photos = {json.dumps(photos)};
        var bounds = L.latLngBounds();

        // Photo source mode: 'local' or 'remote'
        var photoSourceMode = 'local';

        // Helper function to get photo URL based on current mode
        function getPhotoUrl(photo, size) {{
            if (photoSourceMode === 'local' && photo.local_path) {{
                return photo.local_path;
            }}
            // Fall back to remote URLs
            var urls = photo.urls || {{}};
            if (size === 'full') {{
                return urls['2048'] || urls['1024'] || urls['600'] || urls['256'] || Object.values(urls)[0] || '';
            }}
            return urls['600'] || urls['256'] || Object.values(urls)[0] || '';
        }}

        // Helper function to build popup content for a location's photos
        function buildPopupContent(locationPhotos) {{
            var popupContent;
            if (locationPhotos.length === 1) {{
                var photo = locationPhotos[0];
                var imgUrl = getPhotoUrl(photo, 'preview');
                var fullUrl = getPhotoUrl(photo, 'full');
                popupContent = '<div class="photo-popup">' +
                    (imgUrl ? '<a href="' + fullUrl + '" target="_blank"><img src="' + imgUrl + '" alt="Photo"></a>' : '<p>No image available</p>') +
                    '<div class="photo-meta">' +
                    '<strong>' + photo.activity_name + '</strong><br>' +
                    photo.activity_type + ' - ' + photo.activity_date +
                    '</div></div>';
            }} else {{
                popupContent = '<div class="photo-popup photo-gallery">' +
                    '<div class="photo-gallery-header">' + locationPhotos.length + ' photos at this location</div>';
                locationPhotos.forEach(function(photo, idx) {{
                    var imgUrl = getPhotoUrl(photo, 'preview');
                    var fullUrl = getPhotoUrl(photo, 'full');
                    popupContent += '<div class="photo-item">' +
                        (imgUrl ? '<a href="' + fullUrl + '" target="_blank"><img src="' + imgUrl + '" alt="Photo ' + (idx+1) + '"></a>' : '<p>No image available</p>') +
                        '<div class="photo-meta">' +
                        '<strong>' + photo.activity_name + '</strong><br>' +
                        photo.activity_type + ' - ' + photo.activity_date +
                        '</div></div>';
                }});
                popupContent += '</div>';
            }}
            return popupContent;
        }}

        // Routes layer
        var routesLayer = L.layerGroup();
        routes.forEach(function(route) {{
            if (route.coords.length === 0) return;

            var polyline = L.polyline(route.coords, {{
                color: route.color,
                weight: 3,
                opacity: 0.7
            }});

            polyline.bindPopup(
                '<b>' + route.name + '</b><br>' +
                'Type: ' + route.type + '<br>' +
                'Date: ' + route.date + '<br>' +
                'Distance: ' + route.distance_km + ' km'
            );

            routesLayer.addLayer(polyline);
            bounds.extend(polyline.getBounds());
        }});
        routesLayer.addTo(map);

        // Photo markers with clustering
        var photoCluster = L.markerClusterGroup({{
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: false,
            zoomToBoundsOnClick: true,
            maxClusterRadius: 50,
            iconCreateFunction: function(cluster) {{
                var count = cluster.getChildCount();
                return L.divIcon({{
                    html: '<div style="background:#E91E63;color:white;border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;font-weight:bold;border:2px solid white;box-shadow:0 2px 5px rgba(0,0,0,0.3);">' + count + '</div>',
                    className: 'photo-cluster-icon',
                    iconSize: [40, 40]
                }});
            }}
        }});

        // Group photos by location (for overlapping photos)
        var photosByLocation = {{}};
        photos.forEach(function(photo) {{
            var key = photo.lat.toFixed(5) + ',' + photo.lng.toFixed(5);
            if (!photosByLocation[key]) {{
                photosByLocation[key] = [];
            }}
            photosByLocation[key].push(photo);
        }});

        // Store markers for popup updates
        var photoMarkers = [];

        // Create markers for each unique location
        Object.keys(photosByLocation).forEach(function(key) {{
            var locationPhotos = photosByLocation[key];
            var firstPhoto = locationPhotos[0];

            var photoIcon = L.divIcon({{
                html: '<div class="photo-icon" style="width:24px;height:24px;display:flex;align-items:center;justify-content:center;">' +
                      '<svg width="14" height="14" viewBox="0 0 24 24" fill="white"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>' +
                      '</div>',
                className: '',
                iconSize: [28, 28],
                iconAnchor: [14, 14]
            }});

            var marker = L.marker([firstPhoto.lat, firstPhoto.lng], {{ icon: photoIcon }});
            marker._locationPhotos = locationPhotos;  // Store reference for popup updates

            marker.bindPopup(buildPopupContent(locationPhotos), {{ maxWidth: 350, maxHeight: 450 }});
            photoCluster.addLayer(marker);
            photoMarkers.push(marker);

            // Extend bounds to include photos
            bounds.extend([firstPhoto.lat, firstPhoto.lng]);
        }});

        // Function to update all photo popups when source mode changes
        function updatePhotoPopups() {{
            photoMarkers.forEach(function(marker) {{
                marker.setPopupContent(buildPopupContent(marker._locationPhotos));
            }});
            // Update toggle labels
            document.getElementById('local-label').className = 'source-label' + (photoSourceMode === 'local' ? ' active' : '');
            document.getElementById('remote-label').className = 'source-label' + (photoSourceMode === 'remote' ? ' active' : '');
        }}

        if (photos.length > 0) {{
            photoCluster.addTo(map);
        }}

        if (routes.length > 0 || photos.length > 0) {{
            map.fitBounds(bounds, {{ padding: [20, 20] }});
        }}

        // Layer control (if photos exist)
        if (photos.length > 0) {{
            var overlays = {{
                "Routes": routesLayer,
                "Photos": photoCluster
            }};
            L.control.layers(null, overlays, {{ position: 'topleft' }}).addTo(map);

            // Photo source toggle control
            var sourceToggle = L.control({{position: 'bottomleft'}});
            sourceToggle.onAdd = function(map) {{
                var div = L.DomUtil.create('div', 'photo-source-toggle');
                div.innerHTML = '<label>' +
                    '<span id="local-label" class="source-label active">Local</span>' +
                    '<span class="toggle-switch">' +
                    '<input type="checkbox" id="photo-source-toggle">' +
                    '<span class="toggle-slider"></span>' +
                    '</span>' +
                    '<span id="remote-label" class="source-label">Remote</span>' +
                    '</label>';
                L.DomEvent.disableClickPropagation(div);
                return div;
            }};
            sourceToggle.addTo(map);

            // Handle toggle change
            setTimeout(function() {{
                document.getElementById('photo-source-toggle').addEventListener('change', function() {{
                    photoSourceMode = this.checked ? 'remote' : 'local';
                    updatePhotoPopups();
                }});
            }}, 100);
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
            if ({photo_count} > 0) {{
                div.innerHTML += '<br><i style="background:#E91E63;border-radius:50%;"></i> Photos';
            }}
            return div;
        }};
        legend.addTo(map);

        // Info control
        var info = L.control({{position: 'topright'}});
        info.onAdd = function(map) {{
            var div = L.DomUtil.create('div', 'info');
            var html = '<b>Activities</b><br>' + routes.length + ' routes';
            if ({photo_count} > 0) {{
                html += '<br>' + {photo_count} + ' photos';
            }}
            div.innerHTML = html;
            return div;
        }};
        info.addTo(map);
    </script>
</body>
</html>"""


def _generate_heatmap_html(
    points: list[tuple[float, float]],
    photos: list[dict[str, Any]] | None = None,
) -> str:
    """Generate HTML with heatmap layer and optional photo markers.

    Args:
        points: List of (lat, lng) coordinate tuples.
        photos: Optional list of geotagged photo data.

    Returns:
        HTML content.
    """
    if photos is None:
        photos = []

    if not points and not photos:
        center: list[float] = [0.0, 0.0]
        zoom = 2
    else:
        # Combine point coordinates with photo coordinates for bounds calculation
        all_lats = [p[0] for p in points] + [ph["lat"] for ph in photos]
        all_lngs = [p[1] for p in points] + [ph["lng"] for ph in photos]

        if all_lats and all_lngs:
            center = [(min(all_lats) + max(all_lats)) / 2, (min(all_lngs) + max(all_lngs)) / 2]
            lat_span = max(all_lats) - min(all_lats)
            lng_span = max(all_lngs) - min(all_lngs)
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
        else:
            center = [0.0, 0.0]
            zoom = 2

    # Sample points if too many (for performance)
    max_points = 50000
    if len(points) > max_points:
        step = len(points) // max_points
        points = points[::step]

    # Convert to format for leaflet.heat [lat, lng, intensity]
    heat_data = [[p[0], p[1], 1.0] for p in points]
    photo_count = len(photos)

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Strava Activities Heatmap</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css">
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css">
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
        .photo-icon {{
            background: #E91E63;
            border: 2px solid white;
            border-radius: 50%;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        }}
        .photo-popup {{
            max-width: 350px;
        }}
        .photo-popup img {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            cursor: pointer;
        }}
        .photo-popup .photo-meta {{
            font-size: 12px;
            color: #666;
            margin-top: 8px;
        }}
        .photo-gallery {{
            max-height: 400px;
            overflow-y: auto;
        }}
        .photo-gallery .photo-item {{
            margin-bottom: 12px;
            padding-bottom: 12px;
            border-bottom: 1px solid #eee;
        }}
        .photo-gallery .photo-item:last-child {{
            border-bottom: none;
        }}
        .photo-gallery-header {{
            font-weight: bold;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 2px solid #E91E63;
        }}
        .photo-source-toggle {{
            background: white;
            padding: 8px 12px;
            border-radius: 5px;
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
            font: 12px/14px Arial, Helvetica, sans-serif;
        }}
        .photo-source-toggle label {{
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .toggle-switch {{
            position: relative;
            width: 40px;
            height: 20px;
        }}
        .toggle-switch input {{
            opacity: 0;
            width: 0;
            height: 0;
        }}
        .toggle-slider {{
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #4CAF50;
            border-radius: 20px;
            transition: 0.3s;
        }}
        .toggle-slider:before {{
            position: absolute;
            content: "";
            height: 14px;
            width: 14px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            border-radius: 50%;
            transition: 0.3s;
        }}
        .toggle-switch input:checked + .toggle-slider {{
            background-color: #2196F3;
        }}
        .toggle-switch input:checked + .toggle-slider:before {{
            transform: translateX(20px);
        }}
        .source-label {{
            font-size: 11px;
            color: #666;
        }}
        .source-label.active {{
            font-weight: bold;
            color: #333;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
    <script>
        var map = L.map('map').setView({center}, {zoom});

        L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }}).addTo(map);

        var heatData = {json.dumps(heat_data)};
        var photos = {json.dumps(photos)};

        // Photo source mode: 'local' or 'remote'
        var photoSourceMode = 'local';

        // Helper function to get photo URL based on current mode
        function getPhotoUrl(photo, size) {{
            if (photoSourceMode === 'local' && photo.local_path) {{
                return photo.local_path;
            }}
            // Fall back to remote URLs
            var urls = photo.urls || {{}};
            if (size === 'full') {{
                return urls['2048'] || urls['1024'] || urls['600'] || urls['256'] || Object.values(urls)[0] || '';
            }}
            return urls['600'] || urls['256'] || Object.values(urls)[0] || '';
        }}

        // Helper function to build popup content for a location's photos
        function buildPopupContent(locationPhotos) {{
            var popupContent;
            if (locationPhotos.length === 1) {{
                var photo = locationPhotos[0];
                var imgUrl = getPhotoUrl(photo, 'preview');
                var fullUrl = getPhotoUrl(photo, 'full');
                popupContent = '<div class="photo-popup">' +
                    (imgUrl ? '<a href="' + fullUrl + '" target="_blank"><img src="' + imgUrl + '" alt="Photo"></a>' : '<p>No image available</p>') +
                    '<div class="photo-meta">' +
                    '<strong>' + photo.activity_name + '</strong><br>' +
                    photo.activity_type + ' - ' + photo.activity_date +
                    '</div></div>';
            }} else {{
                popupContent = '<div class="photo-popup photo-gallery">' +
                    '<div class="photo-gallery-header">' + locationPhotos.length + ' photos at this location</div>';
                locationPhotos.forEach(function(photo, idx) {{
                    var imgUrl = getPhotoUrl(photo, 'preview');
                    var fullUrl = getPhotoUrl(photo, 'full');
                    popupContent += '<div class="photo-item">' +
                        (imgUrl ? '<a href="' + fullUrl + '" target="_blank"><img src="' + imgUrl + '" alt="Photo ' + (idx+1) + '"></a>' : '<p>No image available</p>') +
                        '<div class="photo-meta">' +
                        '<strong>' + photo.activity_name + '</strong><br>' +
                        photo.activity_type + ' - ' + photo.activity_date +
                        '</div></div>';
                }});
                popupContent += '</div>';
            }}
            return popupContent;
        }}

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

        // Photo markers with clustering
        var photoCluster = L.markerClusterGroup({{
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: false,
            zoomToBoundsOnClick: true,
            maxClusterRadius: 50,
            iconCreateFunction: function(cluster) {{
                var count = cluster.getChildCount();
                return L.divIcon({{
                    html: '<div style="background:#E91E63;color:white;border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;font-weight:bold;border:2px solid white;box-shadow:0 2px 5px rgba(0,0,0,0.3);">' + count + '</div>',
                    className: 'photo-cluster-icon',
                    iconSize: [40, 40]
                }});
            }}
        }});

        // Group photos by location
        var photosByLocation = {{}};
        photos.forEach(function(photo) {{
            var key = photo.lat.toFixed(5) + ',' + photo.lng.toFixed(5);
            if (!photosByLocation[key]) {{
                photosByLocation[key] = [];
            }}
            photosByLocation[key].push(photo);
        }});

        // Store markers for popup updates
        var photoMarkers = [];

        Object.keys(photosByLocation).forEach(function(key) {{
            var locationPhotos = photosByLocation[key];
            var firstPhoto = locationPhotos[0];

            var photoIcon = L.divIcon({{
                html: '<div class="photo-icon" style="width:24px;height:24px;display:flex;align-items:center;justify-content:center;">' +
                      '<svg width="14" height="14" viewBox="0 0 24 24" fill="white"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>' +
                      '</div>',
                className: '',
                iconSize: [28, 28],
                iconAnchor: [14, 14]
            }});

            var marker = L.marker([firstPhoto.lat, firstPhoto.lng], {{ icon: photoIcon }});
            marker._locationPhotos = locationPhotos;  // Store reference for popup updates

            marker.bindPopup(buildPopupContent(locationPhotos), {{ maxWidth: 350, maxHeight: 450 }});
            photoCluster.addLayer(marker);
            photoMarkers.push(marker);
        }});

        // Function to update all photo popups when source mode changes
        function updatePhotoPopups() {{
            photoMarkers.forEach(function(marker) {{
                marker.setPopupContent(buildPopupContent(marker._locationPhotos));
            }});
            // Update toggle labels
            document.getElementById('local-label').className = 'source-label' + (photoSourceMode === 'local' ? ' active' : '');
            document.getElementById('remote-label').className = 'source-label' + (photoSourceMode === 'remote' ? ' active' : '');
        }}

        if (photos.length > 0) {{
            photoCluster.addTo(map);
        }}

        // Fit bounds to data
        var bounds = L.latLngBounds();
        if (heatData.length > 0) {{
            heatData.forEach(function(p) {{
                bounds.extend([p[0], p[1]]);
            }});
        }}
        photos.forEach(function(p) {{
            bounds.extend([p.lat, p.lng]);
        }});
        if (bounds.isValid()) {{
            map.fitBounds(bounds, {{ padding: [20, 20] }});
        }}

        // Layer control (if photos exist)
        if (photos.length > 0) {{
            var overlays = {{
                "Heatmap": heat,
                "Photos": photoCluster
            }};
            L.control.layers(null, overlays, {{ position: 'topleft' }}).addTo(map);

            // Photo source toggle control
            var sourceToggle = L.control({{position: 'bottomleft'}});
            sourceToggle.onAdd = function(map) {{
                var div = L.DomUtil.create('div', 'photo-source-toggle');
                div.innerHTML = '<label>' +
                    '<span id="local-label" class="source-label active">Local</span>' +
                    '<span class="toggle-switch">' +
                    '<input type="checkbox" id="photo-source-toggle">' +
                    '<span class="toggle-slider"></span>' +
                    '</span>' +
                    '<span id="remote-label" class="source-label">Remote</span>' +
                    '</label>';
                L.DomEvent.disableClickPropagation(div);
                return div;
            }};
            sourceToggle.addTo(map);

            // Handle toggle change
            setTimeout(function() {{
                document.getElementById('photo-source-toggle').addEventListener('change', function() {{
                    photoSourceMode = this.checked ? 'remote' : 'local';
                    updatePhotoPopups();
                }});
            }}, 100);
        }}

        // Info control
        var info = L.control({{position: 'topright'}});
        info.onAdd = function(map) {{
            var div = L.DomUtil.create('div', 'info');
            var html = '<b>Heatmap</b><br>' + heatData.length.toLocaleString() + ' points';
            if ({photo_count} > 0) {{
                html += '<br>' + {photo_count} + ' photos';
            }}
            div.innerHTML = html;
            return div;
        }};
        info.addTo(map);
    </script>
</body>
</html>"""


def generate_lightweight_map(data_dir: Path) -> str:  # noqa: ARG001
    """Generate lightweight HTML SPA that loads data on demand.

    This version creates a full single-page application with:
    - App shell with header and tab navigation
    - Map view: fetches data from TSV/Parquet files
    - Sessions view: placeholder for session list
    - Stats view: placeholder for statistics

    Data sources:
    - athletes.tsv for athlete list
    - athl={username}/sessions.tsv for session metadata
    - athl={username}/ses={datetime}/tracking.parquet for track coordinates

    Track coordinates are loaded on-demand when clicking on a session marker.

    Args:
        data_dir: Base data directory.

    Returns:
        HTML content as string.
    """
    # Color palette for activity types
    type_colors = {
        "Run": "#FF5722",
        "Ride": "#2196F3",
        "Hike": "#4CAF50",
        "Walk": "#9C27B0",
        "Swim": "#00BCD4",
        "Other": "#607D8B",
    }

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Strava Backup</title>
    <link rel="stylesheet" href="assets/leaflet/leaflet.css">
    <style>
        /* ===== CSS Reset & Base ===== */
        * {{
            box-sizing: border-box;
        }}
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f5;
        }}

        /* ===== App Shell ===== */
        .app-header {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 56px;
            background: #fff;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            z-index: 1000;
            display: flex;
            align-items: center;
            padding: 0 16px;
        }}

        .app-logo {{
            font-size: 20px;
            font-weight: 600;
            color: #fc4c02;
            margin-right: 32px;
            white-space: nowrap;
            display: flex;
            align-items: center;
            gap: 8px;
            text-decoration: none;
        }}

        .app-logo:hover {{
            opacity: 0.8;
        }}

        .app-logo img {{
            height: 32px;
            width: auto;
        }}

        .app-nav {{
            display: flex;
            gap: 4px;
            flex: 1;
        }}

        .nav-tab {{
            padding: 8px 16px;
            border: none;
            background: transparent;
            font-size: 14px;
            font-weight: 500;
            color: #666;
            cursor: pointer;
            border-radius: 4px;
            transition: background 0.2s, color 0.2s;
        }}

        .nav-tab:hover {{
            background: #f0f0f0;
        }}

        .nav-tab.active {{
            color: #fc4c02;
            background: rgba(252, 76, 2, 0.1);
        }}

        .athlete-selector {{
            margin-left: auto;
            padding: 6px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            background: #fff;
            color: #333;
        }}

        /* ===== Main Content ===== */
        .app-main {{
            margin-top: 56px;
            height: calc(100vh - 56px);
            position: relative;
        }}

        .view {{
            display: none;
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
        }}

        .view.active {{
            display: block;
        }}

        /* ===== Map View ===== */
        #map {{
            width: 100%;
            height: 100%;
        }}

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

        .session-marker {{
            border: 2px solid white;
            border-radius: 50%;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            cursor: pointer;
        }}

        .photo-icon {{
            background: #E91E63;
            border: 2px solid white;
            border-radius: 50%;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        }}

        .photo-popup {{
            max-width: 350px;
        }}

        .photo-popup img {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            cursor: pointer;
        }}

        .photo-popup .photo-meta {{
            font-size: 12px;
            color: #666;
            margin-top: 8px;
        }}

        .loading {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            z-index: 1000;
        }}

        .loading.hidden {{
            display: none;
        }}

        /* ===== Sessions View ===== */
        .view-placeholder {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: #666;
            text-align: center;
            padding: 20px;
        }}

        .view-placeholder h2 {{
            margin: 0 0 8px 0;
            color: #333;
        }}

        .view-placeholder p {{
            margin: 0;
            font-size: 14px;
        }}

        /* ===== Mobile Bottom Navigation ===== */
        .mobile-nav {{
            display: none;
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            height: 56px;
            background: #fff;
            box-shadow: 0 -2px 4px rgba(0,0,0,0.1);
            z-index: 1000;
        }}

        .mobile-nav-inner {{
            display: flex;
            height: 100%;
        }}

        .mobile-nav-tab {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            border: none;
            background: transparent;
            color: #666;
            font-size: 12px;
            cursor: pointer;
            gap: 4px;
        }}

        .mobile-nav-tab svg {{
            width: 24px;
            height: 24px;
            fill: currentColor;
        }}

        .mobile-nav-tab.active {{
            color: #fc4c02;
        }}

        /* ===== Responsive ===== */
        @media (max-width: 767px) {{
            .app-nav {{
                display: none;
            }}

            .mobile-nav {{
                display: block;
            }}

            .app-main {{
                height: calc(100vh - 56px - 56px);
            }}

            .app-logo {{
                margin-right: 0;
            }}
        }}
    </style>
</head>
<body>
    <!-- App Header -->
    <header class="app-header">
        <a href="https://github.com/yarikoptic/strava-backup" class="app-logo" target="_blank">
            <img src="assets/strava-backup-icon.svg" alt="Logo">
            Strava Backup
        </a>
        <nav class="app-nav">
            <button class="nav-tab active" data-view="map">Map</button>
            <button class="nav-tab" data-view="sessions">Sessions</button>
            <button class="nav-tab" data-view="stats">Stats</button>
        </nav>
        <select class="athlete-selector" id="athlete-selector">
            <option value="">All Athletes</option>
        </select>
    </header>

    <!-- Main Content -->
    <main class="app-main">
        <!-- Map View -->
        <div id="view-map" class="view active">
            <div id="map"></div>
            <div id="loading" class="loading">Loading sessions...</div>
        </div>

        <!-- Sessions View -->
        <div id="view-sessions" class="view">
            <div class="view-placeholder">
                <h2>Sessions</h2>
                <p>Session list coming soon.</p>
            </div>
        </div>

        <!-- Stats View -->
        <div id="view-stats" class="view">
            <div class="view-placeholder">
                <h2>Statistics</h2>
                <p>Statistics dashboard coming soon.</p>
            </div>
        </div>
    </main>

    <!-- Mobile Bottom Navigation -->
    <nav class="mobile-nav">
        <div class="mobile-nav-inner">
            <button class="mobile-nav-tab active" data-view="map">
                <svg viewBox="0 0 24 24"><path d="M20.5 3l-.16.03L15 5.1 9 3 3.36 4.9c-.21.07-.36.25-.36.48V20.5c0 .28.22.5.5.5l.16-.03L9 18.9l6 2.1 5.64-1.9c.21-.07.36-.25.36-.48V3.5c0-.28-.22-.5-.5-.5zM15 19l-6-2.11V5l6 2.11V19z"/></svg>
                Map
            </button>
            <button class="mobile-nav-tab" data-view="sessions">
                <svg viewBox="0 0 24 24"><path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z"/></svg>
                Sessions
            </button>
            <button class="mobile-nav-tab" data-view="stats">
                <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/></svg>
                Stats
            </button>
        </div>
    </nav>

    <script src="assets/leaflet/leaflet.js"></script>
    <script type="module">
        import {{ parquetReadObjects }} from './assets/hyparquet/index.js';

        // ===== Router =====
        const Router = {{
            views: ['map', 'sessions', 'stats'],
            currentView: 'map',

            init() {{
                // Handle hash changes
                window.addEventListener('hashchange', () => this.handleRoute());

                // Handle initial route
                this.handleRoute();

                // Set up tab click handlers
                document.querySelectorAll('[data-view]').forEach(tab => {{
                    tab.addEventListener('click', (e) => {{
                        const view = e.currentTarget.dataset.view;
                        this.navigate(view);
                    }});
                }});
            }},

            handleRoute() {{
                const hash = window.location.hash.slice(1) || '/map';
                const view = hash.replace('/', '') || 'map';

                if (this.views.includes(view)) {{
                    this.showView(view);
                }} else {{
                    this.navigate('map');
                }}
            }},

            navigate(view) {{
                window.location.hash = '/' + view;
            }},

            showView(view) {{
                this.currentView = view;

                // Update view visibility
                document.querySelectorAll('.view').forEach(v => {{
                    v.classList.remove('active');
                }});
                const viewEl = document.getElementById('view-' + view);
                if (viewEl) {{
                    viewEl.classList.add('active');
                }}

                // Update desktop nav tabs
                document.querySelectorAll('.nav-tab').forEach(tab => {{
                    tab.classList.toggle('active', tab.dataset.view === view);
                }});

                // Update mobile nav tabs
                document.querySelectorAll('.mobile-nav-tab').forEach(tab => {{
                    tab.classList.toggle('active', tab.dataset.view === view);
                }});

                // Trigger resize for map when switching to map view
                if (view === 'map' && window.mapInstance) {{
                    setTimeout(() => window.mapInstance.invalidateSize(), 100);
                }}
            }}
        }};

        // ===== Map Module =====
        const MapView = {{
            map: null,
            typeColors: {json.dumps(type_colors)},
            athleteColors: {{}},
            bounds: null,
            sessionsLayer: null,
            tracksLayer: null,
            photosLayer: null,
            loadedTracks: new Set(),
            loadingTracks: new Set(),
            loadedPhotos: new Set(),
            allMarkers: [],
            athleteStats: {{}},
            currentAthlete: '',
            totalSessions: 0,
            loadedTrackCount: 0,
            totalPhotos: 0,
            infoControl: null,
            AUTO_LOAD_ZOOM: 11,

            // Color palette for athletes
            ATHLETE_PALETTE: ['#2196F3', '#4CAF50', '#9C27B0', '#FF9800', '#00BCD4', '#E91E63', '#795548', '#607D8B'],

            getAthleteColor(username) {{
                if (!this.athleteColors[username]) {{
                    const idx = Object.keys(this.athleteColors).length % this.ATHLETE_PALETTE.length;
                    this.athleteColors[username] = this.ATHLETE_PALETTE[idx];
                }}
                return this.athleteColors[username];
            }},

            init() {{
                // Initialize map
                this.map = L.map('map', {{ preferCanvas: true }}).setView([40, -100], 4);
                window.mapInstance = this.map;

                L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19,
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }}).addTo(this.map);

                this.bounds = L.latLngBounds();
                this.sessionsLayer = L.layerGroup().addTo(this.map);
                this.tracksLayer = L.layerGroup().addTo(this.map);
                this.photosLayer = L.layerGroup().addTo(this.map);

                // Set up legend
                this.setupLegend();

                // Set up layer control
                L.control.layers(null, {{
                    'Sessions': this.sessionsLayer,
                    'Tracks': this.tracksLayer,
                    'Photos': this.photosLayer
                }}, {{ position: 'topleft' }}).addTo(this.map);

                // Set up auto-loading on zoom/pan
                this.map.on('moveend', () => this.loadVisibleTracks());
                this.map.on('zoomend', () => {{
                    this.loadVisibleTracks();
                    this.updateInfo();
                }});

                // Set up athlete selector
                document.getElementById('athlete-selector').addEventListener('change', (e) => {{
                    this.filterByAthlete(e.target.value);
                }});

                // Start loading sessions
                this.loadSessions();
            }},

            parseTSV(text) {{
                const lines = text.trim().replace(/\\r/g, '').split('\\n');
                if (lines.length < 2) return [];
                const headers = lines[0].split('\\t');
                return lines.slice(1).map(line => {{
                    const values = line.split('\\t');
                    return Object.fromEntries(headers.map((h, i) => [h, values[i] || '']));
                }});
            }},

            filterByAthlete(username) {{
                this.currentAthlete = username;

                // Update marker visibility
                for (const data of this.allMarkers) {{
                    const visible = !username || data.athlete === username;
                    if (visible) {{
                        if (!this.sessionsLayer.hasLayer(data.marker)) {{
                            data.marker.addTo(this.sessionsLayer);
                        }}
                    }} else {{
                        this.sessionsLayer.removeLayer(data.marker);
                    }}
                }}

                // Recalculate bounds for visible markers
                this.bounds = L.latLngBounds();
                for (const data of this.allMarkers) {{
                    if (!username || data.athlete === username) {{
                        this.bounds.extend(data.marker.getLatLng());
                    }}
                }}

                // Fit to new bounds if valid
                if (this.bounds.isValid()) {{
                    this.map.fitBounds(this.bounds, {{ padding: [20, 20] }});
                }}

                this.updateInfo();
            }},

            populateAthleteSelector() {{
                const selector = document.getElementById('athlete-selector');
                // Clear existing options except "All Athletes"
                while (selector.options.length > 1) {{
                    selector.remove(1);
                }}

                // Add options with stats
                const athletes = Object.keys(this.athleteStats).sort();
                for (const username of athletes) {{
                    const stats = this.athleteStats[username];
                    const distanceKm = (stats.distance / 1000).toFixed(0);
                    const option = document.createElement('option');
                    option.value = username;
                    option.textContent = `${{username}} (${{stats.sessions}} sessions, ${{distanceKm}} km)`;
                    option.style.color = this.athleteColors[username] || '#333';
                    selector.appendChild(option);
                }}

                // Update "All Athletes" option with total
                const totalSessions = Object.values(this.athleteStats).reduce((sum, s) => sum + s.sessions, 0);
                const totalDistance = Object.values(this.athleteStats).reduce((sum, s) => sum + s.distance, 0);
                selector.options[0].textContent = `All Athletes (${{totalSessions}} sessions, ${{(totalDistance / 1000).toFixed(0)}} km)`;
            }},

            async loadTrack(athlete, session, color) {{
                const trackKey = `${{athlete}}/${{session}}`;
                if (this.loadedTracks.has(trackKey) || this.loadingTracks.has(trackKey)) return;
                this.loadingTracks.add(trackKey);

                try {{
                    const url = `athl=${{athlete}}/ses=${{session}}/tracking.parquet`;
                    const response = await fetch(url);
                    if (!response.ok) {{
                        this.loadingTracks.delete(trackKey);
                        return;
                    }}

                    const arrayBuffer = await response.arrayBuffer();
                    const rows = await parquetReadObjects({{
                        file: arrayBuffer,
                        columns: ['lat', 'lng']
                    }});

                    if (rows && rows.length > 0) {{
                        const coords = [];
                        for (const row of rows) {{
                            if (row.lat != null && row.lng != null) {{
                                coords.push([row.lat, row.lng]);
                            }}
                        }}
                        if (coords.length > 0) {{
                            L.polyline(coords, {{
                                color: color,
                                weight: 3,
                                opacity: 0.7
                            }}).addTo(this.tracksLayer);
                            this.loadedTracks.add(trackKey);
                            this.loadedTrackCount++;
                            this.updateInfo();
                        }}
                    }}
                }} catch (e) {{
                    console.warn(`Failed to load track ${{trackKey}}:`, e);
                }} finally {{
                    this.loadingTracks.delete(trackKey);
                }}
            }},

            async loadPhotos(athlete, session, sessionName) {{
                const photoKey = `${{athlete}}/${{session}}`;
                if (this.loadedPhotos.has(photoKey)) return;
                this.loadedPhotos.add(photoKey);

                // Find and update the session marker to remove photo badge
                const markerData = this.allMarkers.find(m => m.athlete === athlete && m.session === session);
                if (markerData && markerData.hasPhotos) {{
                    const newMarker = L.circleMarker(markerData.marker.getLatLng(), {{
                        radius: 6,
                        fillColor: markerData.color,
                        color: 'white',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.8,
                        className: 'session-marker'
                    }});
                    newMarker.bindPopup(markerData.marker.getPopup());
                    newMarker.on('click', () => {{
                        this.loadTrack(athlete, session, markerData.color);
                        this.loadPhotos(athlete, session, sessionName);
                    }});
                    this.sessionsLayer.removeLayer(markerData.marker);
                    newMarker.addTo(this.sessionsLayer);
                    markerData.marker = newMarker;
                }}

                try {{
                    const url = `athl=${{athlete}}/ses=${{session}}/info.json`;
                    const response = await fetch(url);
                    if (!response.ok) return;

                    const info = await response.json();
                    const photos = info.photos || [];

                    for (const photo of photos) {{
                        const locationRaw = photo.location;
                        if (!locationRaw || !locationRaw[0] || !locationRaw[0][1]) continue;

                        const [lat, lng] = locationRaw[0][1];
                        if (lat == null || lng == null) continue;

                        const urls = photo.urls || {{}};
                        const previewUrl = urls['600'] || urls['256'] || urls['1024'] || urls['2048'] || Object.values(urls)[0] || '';
                        const fullUrl = urls['2048'] || urls['1024'] || urls['600'] || Object.values(urls)[0] || '';

                        const createdAt = photo.created_at || '';
                        let localPath = '';
                        if (createdAt) {{
                            const dt = createdAt.replace(/[-:]/g, '').replace(/\\+.*$/, '').substring(0, 15);
                            localPath = `athl=${{athlete}}/ses=${{session}}/photos/${{dt}}.jpg`;
                        }}

                        const photoIcon = L.divIcon({{
                            html: '<div class="photo-icon" style="width:24px;height:24px;display:flex;align-items:center;justify-content:center;">' +
                                  '<svg width="14" height="14" viewBox="0 0 24 24" fill="white"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>' +
                                  '</div>',
                            className: '',
                            iconSize: [28, 28],
                            iconAnchor: [14, 14]
                        }});

                        const marker = L.marker([lat, lng], {{ icon: photoIcon }});
                        const imgSrc = localPath || previewUrl;
                        const linkHref = localPath || fullUrl;

                        marker.bindPopup(`
                            <div class="photo-popup">
                                ${{imgSrc ? `<a href="${{linkHref}}" target="_blank"><img src="${{imgSrc}}" alt="Photo"></a>` : '<p>No image available</p>'}}
                                <div class="photo-meta">
                                    <strong>${{sessionName}}</strong><br>
                                    ${{session.substring(0, 8)}}
                                </div>
                            </div>
                        `, {{ maxWidth: 350 }});

                        marker.addTo(this.photosLayer);
                        this.totalPhotos++;
                    }}

                    this.updateInfo();
                }} catch (e) {{
                    console.warn(`Failed to load photos for ${{photoKey}}:`, e);
                }}
            }},

            loadVisibleTracks() {{
                if (this.map.getZoom() < this.AUTO_LOAD_ZOOM) return;

                const mapBounds = this.map.getBounds();
                for (const {{marker, athlete, session, color, hasPhotos, sessionName}} of this.allMarkers) {{
                    if (mapBounds.contains(marker.getLatLng())) {{
                        this.loadTrack(athlete, session, color);
                        if (hasPhotos) {{
                            this.loadPhotos(athlete, session, sessionName);
                        }}
                    }}
                }}
            }},

            async loadSessions() {{
                const loading = document.getElementById('loading');

                try {{
                    let athletes = [];
                    try {{
                        const athletesResp = await fetch('athletes.tsv');
                        if (athletesResp.ok) {{
                            const athletesText = await athletesResp.text();
                            athletes = this.parseTSV(athletesText);
                        }}
                    }} catch (e) {{
                        console.warn('Could not load athletes.tsv, scanning directories...');
                    }}

                    if (athletes.length === 0) {{
                        loading.textContent = 'Looking for sessions...';
                    }}

                    // Initialize athlete stats
                    for (const athlete of athletes) {{
                        const username = athlete.username;
                        if (username) {{
                            this.athleteStats[username] = {{ sessions: 0, distance: 0 }};
                            // Assign color for each athlete
                            this.getAthleteColor(username);
                        }}
                    }}

                    for (const athlete of athletes) {{
                        const username = athlete.username;
                        if (!username) continue;

                        try {{
                            const sessionsResp = await fetch(`athl=${{username}}/sessions.tsv`);
                            if (!sessionsResp.ok) continue;

                            const sessionsText = await sessionsResp.text();
                            const sessions = this.parseTSV(sessionsText);

                            for (const session of sessions) {{
                                const lat = parseFloat(session.center_lat);
                                const lng = parseFloat(session.center_lng);
                                const distance = parseFloat(session.distance_m || 0);

                                // Track athlete stats
                                this.athleteStats[username].sessions++;
                                this.athleteStats[username].distance += distance;

                                if (isNaN(lat) || isNaN(lng)) continue;

                                const type = session.sport || session.type || 'Other';
                                const color = this.typeColors[type] || this.typeColors.Other;
                                const hasPhotos = parseInt(session.photo_count || '0') > 0;
                                const photoCount = parseInt(session.photo_count || '0');

                                let marker;
                                if (hasPhotos) {{
                                    const icon = L.divIcon({{
                                        html: `<div style="position:relative;">
                                            <div style="width:12px;height:12px;background:${{color}};border:2px solid white;border-radius:50%;box-shadow:0 2px 5px rgba(0,0,0,0.3);"></div>
                                            <div style="position:absolute;top:-6px;right:-8px;width:14px;height:14px;background:#E91E63;border:1.5px solid white;border-radius:50%;display:flex;align-items:center;justify-content:center;">
                                                <svg width="8" height="8" viewBox="0 0 24 24" fill="white"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>
                                            </div>
                                        </div>`,
                                        className: '',
                                        iconSize: [20, 20],
                                        iconAnchor: [8, 8]
                                    }});
                                    marker = L.marker([lat, lng], {{ icon: icon }});
                                }} else {{
                                    marker = L.circleMarker([lat, lng], {{
                                        radius: 6,
                                        fillColor: color,
                                        color: 'white',
                                        weight: 2,
                                        opacity: 1,
                                        fillOpacity: 0.8,
                                        className: 'session-marker'
                                    }});
                                }}

                                const photoInfo = hasPhotos ? `<br>Photos: ${{photoCount}}` : '';
                                marker.bindPopup(`
                                    <b>${{session.name || 'Activity'}}</b><br>
                                    Type: ${{type}}<br>
                                    Date: ${{session.datetime?.substring(0, 8) || ''}}${{photoInfo}}<br>
                                    Distance: ${{(parseFloat(session.distance_m || 0) / 1000).toFixed(2)}} km
                                `);

                                this.allMarkers.push({{
                                    marker: marker,
                                    athlete: username,
                                    session: session.datetime,
                                    color: color,
                                    hasGps: session.has_gps === 'true',
                                    hasPhotos: hasPhotos,
                                    sessionName: session.name || 'Activity'
                                }});

                                marker.on('click', () => {{
                                    this.loadTrack(username, session.datetime, color);
                                    if (hasPhotos) {{
                                        this.loadPhotos(username, session.datetime, session.name || 'Activity');
                                    }}
                                }});

                                marker.addTo(this.sessionsLayer);
                                this.bounds.extend([lat, lng]);
                                this.totalSessions++;
                            }}
                        }} catch (e) {{
                            console.warn(`Failed to load sessions for ${{username}}:`, e);
                        }}
                    }}

                    if (this.bounds.isValid()) {{
                        this.map.fitBounds(this.bounds, {{ padding: [20, 20] }});
                    }}

                    // Populate athlete selector with stats
                    this.populateAthleteSelector();

                    loading.classList.add('hidden');
                    this.updateInfo();

                }} catch (e) {{
                    loading.textContent = 'Error loading data: ' + e.message;
                    console.error('Error loading sessions:', e);
                }}
            }},

            updateInfo() {{
                if (this.infoControl) {{
                    this.infoControl.remove();
                }}
                this.infoControl = L.control({{ position: 'topright' }});
                const self = this;
                this.infoControl.onAdd = function() {{
                    const div = L.DomUtil.create('div', 'info');

                    // Calculate visible stats
                    let visibleSessions = 0;
                    for (const data of self.allMarkers) {{
                        if (!self.currentAthlete || data.athlete === self.currentAthlete) {{
                            visibleSessions++;
                        }}
                    }}

                    let html = '<b>Activities</b>';
                    if (self.currentAthlete) {{
                        const color = self.athleteColors[self.currentAthlete] || '#333';
                        html += `<br><span style="color:${{color}}">${{self.currentAthlete}}</span>`;
                    }}
                    html += `<br>${{visibleSessions}} sessions`;
                    if (self.loadedTrackCount > 0) {{
                        html += `<br>${{self.loadedTrackCount}} tracks loaded`;
                    }}
                    if (self.totalPhotos > 0) {{
                        html += `<br>${{self.totalPhotos}} photos`;
                    }}
                    const zoom = self.map.getZoom();
                    if (zoom < self.AUTO_LOAD_ZOOM) {{
                        html += `<br><small>Zoom in to auto-load<br>(current: ${{zoom}}, need: ${{self.AUTO_LOAD_ZOOM}})</small>`;
                    }} else {{
                        html += `<br><small>Click marker or pan to load</small>`;
                    }}
                    div.innerHTML = html;
                    return div;
                }};
                this.infoControl.addTo(this.map);
            }},

            setupLegend() {{
                const legend = L.control({{ position: 'bottomright' }});
                const self = this;
                legend.onAdd = function() {{
                    const div = L.DomUtil.create('div', 'info legend');
                    div.innerHTML = '<b>Activity Types</b><br>';
                    for (const [type, color] of Object.entries(self.typeColors)) {{
                        div.innerHTML += `<i style="background:${{color}}"></i> ${{type}}<br>`;
                    }}
                    div.innerHTML += '<br><i style="background:#E91E63;border-radius:50%;"></i> Photos';
                    return div;
                }};
                legend.addTo(this.map);
            }}
        }};

        // ===== Initialize App =====
        Router.init();
        MapView.init();
    </script>
</body>
</html>'''


def serve_map(
    html_path: Path,
    port: int = 8080,
    host: str = "127.0.0.1",
) -> None:
    """Start a local HTTP server to serve the map.

    Args:
        html_path: Path to the HTML file.
        port: Server port.
        host: Server host.
    """
    # Change to directory containing the HTML file
    directory = html_path.parent

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, format: str, *args: object) -> None:
            pass  # Suppress logging

    # Allow port reuse to avoid "Address already in use" errors
    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer((host, port), Handler) as httpd:
        url = f"http://{host}:{port}/{html_path.name}"
        print(f"Serving at {url}")
        print("Press Ctrl+C to stop")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped")
