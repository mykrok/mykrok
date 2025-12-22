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

                photos.append(
                    {
                        "lat": location[0],
                        "lng": location[1],
                        "activity_name": activity.name,
                        "activity_type": activity.type,
                        "activity_date": session_date.strftime("%Y-%m-%d"),
                        "photo_date": photo_created,
                        "urls": photo.get("urls", {}),
                        "local_path": local_path,
                        "session_key": session_key,
                    }
                )

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
                routes.append(
                    {
                        "name": activity.name,
                        "type": activity.type,
                        "date": session_date.strftime("%Y-%m-%d"),
                        "distance_km": round(activity.distance / 1000, 2)
                        if activity.distance
                        else 0,
                        "coords": coords,
                    }
                )

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
        routes_json.append(
            {
                "name": route["name"],
                "type": route["type"],
                "date": route["date"],
                "distance_km": route["distance_km"],
                "coords": route["coords"],
                "color": color,
            }
        )

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


def generate_lightweight_map(_data_dir: Path) -> str:
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

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Strava Backup</title>
    <link rel="icon" type="image/svg+xml" href="assets/strava-backup-icon.svg">
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

        .info-link {{
            color: #FC4C02;
            text-decoration: none;
            font-weight: 500;
        }}

        .info-link:hover {{
            text-decoration: underline;
        }}

        /* Map info panel with integrated session list */
        .map-info-panel {{
            min-width: 160px;
            max-width: 280px;
        }}

        .info-header {{
            margin-bottom: 4px;
        }}

        .info-stats {{
            font-size: 13px;
            margin-bottom: 4px;
        }}

        .info-sessions-toggle {{
            color: #fc4c02;
            cursor: pointer;
            font-weight: 500;
        }}

        .info-sessions-toggle:hover {{
            text-decoration: underline;
        }}

        .info-session-list {{
            max-height: 300px;
            overflow-y: auto;
            margin-top: 8px;
            border-top: 1px solid #e0e0e0;
            padding-top: 8px;
            resize: vertical;
            min-height: 100px;
        }}

        .info-resize-handle {{
            height: 8px;
            background: linear-gradient(to bottom, transparent 0%, #e0e0e0 50%, transparent 100%);
            cursor: ns-resize;
            display: flex;
            justify-content: center;
            align-items: center;
            margin-top: 4px;
        }}

        .info-resize-handle::before {{
            content: '';
            width: 30px;
            height: 3px;
            background: #ccc;
            border-radius: 2px;
        }}

        .info-resize-handle:hover::before {{
            background: #fc4c02;
        }}

        .info-session-item {{
            padding: 6px 4px;
            border-radius: 4px;
            margin-bottom: 4px;
            border: 1px solid transparent;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .info-session-item:hover {{
            background: #f5f5f5;
            border-color: #fc4c02;
        }}

        .info-session-main {{
            flex: 1;
            min-width: 0;
            cursor: pointer;
        }}

        .info-session-link {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            text-decoration: none;
            color: #666;
            font-size: 16px;
            border-radius: 4px;
            transition: background 0.2s, color 0.2s;
        }}

        .info-session-link:hover {{
            background: #fc4c02;
            color: white;
        }}

        .info-session-date {{
            font-size: 11px;
            color: #666;
        }}

        .info-session-type {{
            font-size: 10px;
            background: #e8e8e8;
            padding: 1px 4px;
            border-radius: 3px;
            margin-left: 4px;
        }}

        .info-session-name {{
            font-size: 12px;
            font-weight: 500;
            color: #333;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .info-session-more {{
            text-align: center;
            padding: 8px;
            font-size: 12px;
        }}

        .info-session-more a {{
            color: #fc4c02;
        }}

        .info-hint {{
            font-size: 11px;
            color: #888;
            margin-top: 6px;
            border-top: 1px solid #e0e0e0;
            padding-top: 6px;
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

        /* Layers control */
        .layers-control {{
            background: white;
            padding: 8px 12px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            font-size: 13px;
            min-width: 140px;
        }}

        .layers-control-header {{
            font-weight: 600;
            margin-bottom: 8px;
            color: #333;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .layers-control-header svg {{
            width: 16px;
            height: 16px;
            fill: currentColor;
        }}

        .layers-section {{
            margin-bottom: 8px;
        }}

        .layers-section:last-child {{
            margin-bottom: 0;
        }}

        .layers-section-label {{
            font-size: 10px;
            text-transform: uppercase;
            color: #888;
            margin-bottom: 4px;
            letter-spacing: 0.5px;
        }}

        .layers-control label {{
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 4px 0;
            cursor: pointer;
            color: #444;
        }}

        .layers-control label:hover {{
            color: #fc4c02;
        }}

        .layers-control input[type="radio"],
        .layers-control input[type="checkbox"] {{
            accent-color: #fc4c02;
            cursor: pointer;
        }}

        .layers-divider {{
            border-top: 1px solid #e0e0e0;
            margin: 8px 0;
        }}

        .heatmap-gradient {{
            height: 10px;
            background: linear-gradient(to right, blue, cyan, lime, yellow, red);
            border-radius: 2px;
            margin-top: 4px;
        }}

        .heatmap-labels {{
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            color: #888;
            margin-top: 2px;
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

        .popup-activity-link {{
            display: inline-block;
            margin-top: 6px;
            color: #FC4C02;
            text-decoration: none;
            font-size: 12px;
            font-weight: 500;
        }}

        .popup-activity-link:hover {{
            text-decoration: underline;
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

        /* Loading spinner animation */
        .loading::before {{
            content: '';
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #fc4c02;
            border-radius: 50%;
            border-top-color: transparent;
            animation: spin 0.8s linear infinite;
            margin-right: 10px;
            vertical-align: middle;
        }}

        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}

        /* Skeleton loading animation */
        @keyframes shimmer {{
            0% {{ background-position: -200% 0; }}
            100% {{ background-position: 200% 0; }}
        }}

        .skeleton {{
            background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 4px;
        }}

        .skeleton-row {{
            display: flex;
            gap: 12px;
            padding: 12px 16px;
            border-bottom: 1px solid #eee;
        }}

        .skeleton-cell {{
            height: 16px;
            flex: 1;
        }}

        .skeleton-cell:first-child {{
            flex: 2;
        }}

        /* Empty state styling */
        .empty-state {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 60px 20px;
            text-align: center;
            color: #666;
        }}

        .empty-state svg {{
            width: 64px;
            height: 64px;
            margin-bottom: 16px;
            fill: #ccc;
        }}

        .empty-state h3 {{
            margin: 0 0 8px 0;
            color: #333;
            font-size: 18px;
        }}

        .empty-state p {{
            margin: 0;
            font-size: 14px;
            max-width: 300px;
        }}

        .empty-state .clear-filters-btn {{
            margin-top: 16px;
            padding: 8px 16px;
            background: #fc4c02;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }}

        .empty-state .clear-filters-btn:hover {{
            background: #e04400;
        }}

        /* Loading overlay for initial app load */
        .loading-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255, 255, 255, 0.95);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            transition: opacity 0.3s ease-out;
        }}

        .loading-overlay.hidden {{
            opacity: 0;
            pointer-events: none;
        }}

        .loading-overlay .spinner {{
            width: 48px;
            height: 48px;
            border: 4px solid #f0f0f0;
            border-top-color: #fc4c02;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}

        .loading-overlay p {{
            margin-top: 16px;
            color: #666;
            font-size: 14px;
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

        .sessions-container {{
            height: 100%;
            display: flex;
            flex-direction: column;
            background: #fff;
        }}

        .filter-bar {{
            display: flex;
            gap: 8px;
            padding: 12px 16px;
            background: #f5f5f5;
            border-bottom: 1px solid #ddd;
            flex-wrap: wrap;
        }}

        .filter-input, .filter-select {{
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            background: #fff;
        }}

        .filter-input:focus, .filter-select:focus {{
            outline: none;
            border-color: #fc4c02;
        }}

        #session-search {{
            flex: 1;
            min-width: 150px;
        }}

        .filter-date {{
            width: 130px;
        }}

        .filter-btn {{
            padding: 8px 16px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: #fff;
            cursor: pointer;
            font-size: 14px;
        }}

        .filter-btn:hover {{
            background: #f0f0f0;
        }}

        .sessions-table-container {{
            flex: 1;
            overflow: auto;
        }}

        #sessions-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}

        #sessions-table th {{
            position: sticky;
            top: 0;
            background: #f5f5f5;
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #ddd;
            white-space: nowrap;
        }}

        #sessions-table th.sortable {{
            cursor: pointer;
            user-select: none;
        }}

        #sessions-table th.sortable:hover {{
            background: #eee;
        }}

        #sessions-table th.sortable::after {{
            content: '';
            display: inline-block;
            width: 0;
            height: 0;
            margin-left: 6px;
            vertical-align: middle;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
        }}

        #sessions-table th.sorted-asc::after {{
            border-bottom: 6px solid #666;
        }}

        #sessions-table th.sorted-desc::after {{
            border-top: 6px solid #666;
        }}

        #sessions-table td {{
            padding: 12px 16px;
            border-bottom: 1px solid #eee;
        }}

        #sessions-table tbody tr {{
            cursor: pointer;
            transition: background 0.15s;
        }}

        #sessions-table tbody tr:hover {{
            background: #f9f9f9;
        }}

        #sessions-table tbody tr.selected {{
            background: rgba(252, 76, 2, 0.1);
        }}

        .session-type {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}

        .pagination {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            padding: 12px;
            background: #f5f5f5;
            border-top: 1px solid #ddd;
        }}

        .pagination button {{
            padding: 6px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: #fff;
            cursor: pointer;
        }}

        .pagination button:hover:not(:disabled) {{
            background: #f0f0f0;
        }}

        .pagination button:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}

        .pagination .page-info {{
            font-size: 14px;
            color: #666;
        }}

        /* Session Detail Panel */
        .session-detail {{
            position: absolute;
            top: 0;
            right: 0;
            width: 400px;
            height: 100%;
            background: #fff;
            box-shadow: -4px 0 20px rgba(0,0,0,0.15);
            z-index: 100;
            display: flex;
            flex-direction: column;
            transition: transform 0.3s ease;
        }}

        .session-detail.hidden {{
            transform: translateX(100%);
        }}

        .detail-header {{
            display: flex;
            align-items: center;
            padding: 16px;
            border-bottom: 1px solid #eee;
            gap: 12px;
        }}

        .close-btn {{
            width: 32px;
            height: 32px;
            border: none;
            background: #f0f0f0;
            border-radius: 50%;
            font-size: 20px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .close-btn:hover {{
            background: #ddd;
        }}

        .detail-header h2 {{
            margin: 0;
            font-size: 18px;
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .detail-content {{
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }}

        .detail-meta {{
            font-size: 14px;
            color: #666;
            margin-bottom: 16px;
        }}

        .detail-stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-bottom: 16px;
        }}

        .stat-card {{
            background: #f5f5f5;
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }}

        .stat-value {{
            font-size: 20px;
            font-weight: 600;
            color: #333;
        }}

        .stat-label {{
            font-size: 12px;
            color: #666;
            margin-top: 4px;
        }}

        .detail-map {{
            height: 200px;
            background: #eee;
            border-radius: 8px;
            margin-bottom: 16px;
            overflow: hidden;
        }}

        .detail-photos {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
        }}

        .detail-photos img {{
            width: 100%;
            aspect-ratio: 1;
            object-fit: cover;
            border-radius: 4px;
            cursor: pointer;
        }}

        .detail-photos img:hover {{
            opacity: 0.9;
        }}

        .detail-streams {{
            margin-top: 16px;
        }}

        .detail-streams h4 {{
            margin: 0 0 12px 0;
            font-size: 14px;
            color: #333;
        }}

        .streams-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }}

        .stream-card {{
            background: #f8f9fa;
            border-radius: 6px;
            padding: 10px;
        }}

        .stream-label {{
            font-size: 11px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            margin-bottom: 4px;
        }}

        .stream-values {{
            display: flex;
            gap: 12px;
            font-size: 13px;
        }}

        .stream-stat {{
            display: flex;
            flex-direction: column;
        }}

        .stream-stat-label {{
            font-size: 10px;
            color: #999;
        }}

        .stream-stat-value {{
            font-weight: 600;
            color: #333;
        }}

        .detail-social {{
            margin-top: 16px;
        }}

        .detail-social h4 {{
            margin: 0 0 8px 0;
            font-size: 14px;
            color: #333;
        }}

        .kudos-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 12px;
        }}

        .kudos-item {{
            display: inline-flex;
            align-items: center;
            padding: 4px 8px;
            background: #fff3e0;
            border-radius: 12px;
            font-size: 12px;
            color: #e65100;
        }}

        .comments-list {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .comment-item {{
            background: #f5f5f5;
            border-radius: 8px;
            padding: 10px;
            font-size: 13px;
        }}

        .comment-author {{
            font-weight: 600;
            color: #333;
            margin-bottom: 4px;
        }}

        .comment-text {{
            color: #555;
            line-height: 1.4;
        }}

        .view-on-map-btn {{
            display: block;
            width: 100%;
            padding: 12px;
            margin-top: 16px;
            background: #fc4c02;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
        }}

        .view-on-map-btn:hover {{
            background: #e04400;
        }}

        .detail-shared {{
            margin-top: 16px;
        }}

        .shared-runs {{
            background: #e3f2fd;
            border-radius: 8px;
            padding: 10px 12px;
            font-size: 13px;
            color: #1565c0;
        }}

        .shared-athlete-link {{
            color: #1565c0;
            font-weight: 600;
            text-decoration: none;
        }}

        .shared-athlete-link:hover {{
            text-decoration: underline;
        }}

        /* ===== Full-Screen Session View ===== */
        .full-session-container {{
            height: 100%;
            overflow-y: auto;
            background: #f5f5f5;
        }}

        .full-session-header {{
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 16px 24px;
            background: #fff;
            border-bottom: 1px solid #ddd;
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        .full-session-header .back-btn {{
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 8px 12px;
            background: #f5f5f5;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            color: #333;
        }}

        .full-session-header .back-btn:hover {{
            background: #e8e8e8;
        }}

        .full-session-header .back-btn svg {{
            fill: currentColor;
        }}

        .full-session-title {{
            flex: 1;
        }}

        .full-session-title h1 {{
            margin: 0;
            font-size: 20px;
            font-weight: 600;
        }}

        .full-session-meta {{
            font-size: 13px;
            color: #666;
            margin-top: 4px;
        }}

        .header-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 36px;
            height: 36px;
            background: #f0f0f0;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            margin-left: 8px;
            transition: background 0.15s;
        }}

        .header-btn:hover {{
            background: #e0e0e0;
        }}

        .header-btn svg {{
            fill: #555;
        }}

        .header-btn.copied {{
            background: #4CAF50;
        }}

        .header-btn.copied svg {{
            fill: white;
        }}

        .map-actions {{
            display: flex;
            justify-content: center;
            padding: 16px 0;
        }}

        .action-btn-primary {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            min-width: 160px;
            padding: 12px 24px;
            background: #fc4c02;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.15s;
        }}

        .action-btn-primary:hover {{
            background: #e04400;
        }}

        .action-btn-primary svg {{
            width: 18px;
            height: 18px;
            fill: currentColor;
        }}

        .full-session-content {{
            padding: 24px;
            max-width: 1200px;
            margin: 0 auto;
        }}

        .full-session-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .full-session-stats .stat-card {{
            background: #fff;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}

        .full-session-stats .stat-value {{
            font-size: 28px;
            font-weight: 700;
            color: #333;
        }}

        .full-session-stats .stat-label {{
            font-size: 13px;
            color: #888;
            margin-top: 4px;
        }}

        .full-session-map {{
            background: #fff;
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}

        #full-session-map-container {{
            height: 400px;
        }}

        .full-session-streams,
        .full-session-photos,
        .full-session-social,
        .full-session-shared {{
            background: #fff;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}

        .full-session-section-title {{
            font-size: 16px;
            font-weight: 600;
            margin: 0 0 16px 0;
            color: #333;
        }}

        /* Data Stream Charts */
        .stream-charts {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}

        .stream-chart-container {{
            position: relative;
            height: 150px;
            background: #fafafa;
            border-radius: 8px;
            padding: 12px;
        }}

        .stream-chart-container.elevation-chart {{
            height: 120px;
        }}

        .stream-chart-label {{
            position: absolute;
            top: 8px;
            left: 12px;
            font-size: 11px;
            font-weight: 500;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            z-index: 1;
        }}

        .stream-chart-canvas {{
            width: 100% !important;
            height: 100% !important;
        }}

        .stream-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 8px;
            font-size: 12px;
            color: #666;
        }}

        .stream-legend-item {{
            display: flex;
            align-items: center;
            gap: 4px;
            cursor: pointer;
            opacity: 1;
            transition: opacity 0.2s;
        }}

        .stream-legend-item.disabled {{
            opacity: 0.4;
        }}

        .stream-legend-color {{
            width: 12px;
            height: 3px;
            border-radius: 2px;
        }}

        .stream-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}

        .stream-header .full-session-section-title {{
            margin: 0;
        }}

        .xaxis-select {{
            padding: 4px 8px;
            font-size: 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            cursor: pointer;
        }}

        .xaxis-select:hover {{
            border-color: #bbb;
        }}

        .full-session-photos .photo-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 12px;
        }}

        .full-session-photos .photo-item img {{
            width: 100%;
            height: 200px;
            object-fit: cover;
            border-radius: 8px;
            cursor: pointer;
        }}

        .expand-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            background: transparent;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-left: 8px;
        }}

        .expand-btn:hover {{
            background: rgba(0,0,0,0.1);
        }}

        .expand-btn svg {{
            fill: #666;
        }}

        @media (max-width: 768px) {{
            .full-session-header {{
                padding: 12px 16px;
            }}
            .full-session-content {{
                padding: 16px;
            }}
            .full-session-stats {{
                grid-template-columns: repeat(2, 1fr);
            }}
            #full-session-map-container {{
                height: 300px;
            }}
        }}

        /* ===== Stats View ===== */
        .stats-container {{
            height: 100%;
            overflow-y: auto;
            padding: 16px;
            background: #f5f5f5;
        }}

        .stats-filters {{
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
        }}

        /* ===== Map Filter Bar (overlay) ===== */
        .map-filter-container {{
            position: absolute;
            top: 8px;
            left: 60px;
            right: 60px;
            z-index: 1000;
            display: flex;
            gap: 8px;
            pointer-events: none;
        }}

        .map-filter-container > * {{
            pointer-events: auto;
        }}

        .map-filter-bar {{
            display: flex;
            gap: 6px;
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            flex-wrap: wrap;
            align-items: center;
        }}

        .map-filter-bar .filter-input,
        .map-filter-bar .filter-select {{
            padding: 6px 10px;
            font-size: 13px;
        }}

        .map-filter-bar .filter-search {{
            width: 140px;
        }}

        .map-filter-bar .filter-date {{
            width: 130px;
        }}

        .map-filter-bar .filter-btn {{
            padding: 6px 12px;
            font-size: 13px;
        }}

        .map-filter-bar .filter-count {{
            font-size: 12px;
            color: #666;
            padding: 0 8px;
        }}

        /* Date navigation group */
        .date-nav-group {{
            display: flex;
            align-items: center;
        }}

        .date-nav-btn {{
            width: 28px;
            height: 32px;
            border: 1px solid #ced4da;
            background: #e9ecef;
            color: #495057;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background-color 0.15s ease;
            padding: 0;
        }}

        .date-nav-btn:hover:not(:disabled) {{
            background: #dee2e6;
        }}

        .date-nav-btn:active:not(:disabled) {{
            background: #ced4da;
        }}

        .date-nav-btn:disabled {{
            background: #f8f9fa;
            color: #adb5bd;
            cursor: not-allowed;
            opacity: 0.7;
        }}

        .date-nav-btn--prev {{
            border-radius: 4px 0 0 4px;
            border-right: none;
        }}

        .date-nav-btn--next {{
            border-radius: 0 4px 4px 0;
            border-left: none;
        }}

        .date-nav-group .filter-date-from {{
            border-radius: 0;
        }}

        .date-nav-group .filter-date-to {{
            border-radius: 0;
        }}

        .date-nav-btn svg {{
            width: 14px;
            height: 14px;
        }}

        /* Zoom to fit control - matches Leaflet style */
        .leaflet-control-fitbounds {{
            background: white;
            border-radius: 4px;
            box-shadow: 0 1px 5px rgba(0, 0, 0, 0.4);
        }}

        .leaflet-control-fitbounds button {{
            width: 30px;
            height: 30px;
            border: none;
            background: white;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 4px;
            padding: 0;
        }}

        .leaflet-control-fitbounds button:hover {{
            background: #f4f4f4;
        }}

        .leaflet-control-fitbounds svg {{
            width: 16px;
            height: 16px;
            color: #333;
        }}

        /* Popup links styling */
        .popup-links {{
            display: flex;
            gap: 12px;
            margin-top: 4px;
        }}

        .popup-zoom-link {{
            color: #2196F3;
            text-decoration: none;
            cursor: pointer;
        }}

        .popup-zoom-link:hover {{
            text-decoration: underline;
        }}

        /* ===== Session List Panel ===== */
        .session-list-panel {{
            position: absolute;
            top: 60px;
            right: 8px;
            width: 280px;
            max-height: calc(100% - 80px);
            background: rgba(255, 255, 255, 0.95);
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            z-index: 1000;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        .session-list-panel.collapsed .session-list-content {{
            display: none;
        }}

        .session-list-header {{
            display: flex;
            align-items: center;
            padding: 10px 12px;
            border-bottom: 1px solid #e0e0e0;
            background: #f8f8f8;
        }}

        .session-list-title {{
            font-weight: 600;
            font-size: 14px;
            flex: 1;
        }}

        .session-list-count {{
            font-size: 12px;
            color: #666;
            background: #e0e0e0;
            padding: 2px 8px;
            border-radius: 10px;
            margin-right: 8px;
        }}

        .session-list-toggle {{
            background: none;
            border: none;
            cursor: pointer;
            padding: 4px 8px;
            font-size: 12px;
            color: #666;
        }}

        .session-list-content {{
            flex: 1;
            overflow-y: auto;
            max-height: 400px;
        }}

        .session-list-items {{
            padding: 4px;
        }}

        .session-list-item {{
            padding: 10px 12px;
            border-radius: 6px;
            cursor: pointer;
            margin-bottom: 4px;
            background: #fff;
            border: 1px solid #e8e8e8;
        }}

        .session-list-item:hover {{
            background: #f5f5f5;
            border-color: #fc4c02;
        }}

        .session-list-item-header {{
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: #666;
            margin-bottom: 4px;
        }}

        .session-list-item-type {{
            font-size: 11px;
            background: #e8e8e8;
            padding: 1px 6px;
            border-radius: 3px;
        }}

        .session-list-item-name {{
            font-size: 14px;
            font-weight: 500;
            color: #333;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .session-list-item-stats {{
            font-size: 12px;
            color: #666;
            margin-top: 4px;
        }}

        .session-list-more {{
            width: 100%;
            padding: 8px;
            background: #f5f5f5;
            border: none;
            cursor: pointer;
            font-size: 13px;
            color: #fc4c02;
        }}

        .session-list-more:hover {{
            background: #eee;
        }}

        /* Stats view session list */
        .stats-session-panel {{
            margin-top: 24px;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            overflow: hidden;
        }}

        .stats-session-panel .session-list-content {{
            max-height: 300px;
        }}

        @media (max-width: 768px) {{
            .map-filter-container {{
                left: 8px;
                right: 8px;
                top: 4px;
            }}

            .map-filter-bar {{
                width: 100%;
            }}

            .map-filter-bar .filter-search {{
                width: 100%;
                min-width: 0;
            }}

            .session-list-panel {{
                top: auto;
                bottom: 60px;
                left: 8px;
                right: 8px;
                width: auto;
                max-height: 50vh;
            }}
        }}

        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }}

        .summary-card {{
            background: #fff;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        .summary-value {{
            font-size: 28px;
            font-weight: 700;
            color: #fc4c02;
            margin-bottom: 4px;
        }}

        .summary-label {{
            font-size: 13px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
        }}

        .chart-container {{
            background: #fff;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        .chart-container h3 {{
            margin: 0 0 16px 0;
            font-size: 16px;
            font-weight: 600;
            color: #333;
        }}

        .chart-container canvas {{
            width: 100% !important;
            height: 250px !important;
        }}

        @media (max-width: 900px) {{
            .summary-cards {{
                grid-template-columns: repeat(2, 1fr);
            }}
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        @media (max-width: 500px) {{
            .summary-cards {{
                grid-template-columns: 1fr;
            }}
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
    <!-- Loading Overlay -->
    <div id="loading-overlay" class="loading-overlay">
        <div class="spinner"></div>
        <p>Loading activity data...</p>
    </div>

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
            <div class="map-filter-container">
                <div id="map-filter-bar" class="filter-bar map-filter-bar"></div>
            </div>
            <div id="loading" class="loading">Loading sessions...</div>
        </div>

        <!-- Sessions View -->
        <div id="view-sessions" class="view">
            <div class="sessions-container">
                <div id="sessions-filter-bar" class="filter-bar"></div>
                <div class="sessions-table-container">
                    <table id="sessions-table">
                        <thead>
                            <tr>
                                <th data-sort="datetime" class="sortable sorted-desc">Date</th>
                                <th data-sort="name" class="sortable">Name</th>
                                <th data-sort="type" class="sortable">Type</th>
                                <th data-sort="distance" class="sortable">Distance</th>
                                <th data-sort="duration" class="sortable">Duration</th>
                            </tr>
                        </thead>
                        <tbody id="sessions-tbody"></tbody>
                    </table>
                </div>
                <div class="pagination" id="pagination"></div>
            </div>
            <div id="session-detail" class="session-detail hidden">
                <div class="detail-header">
                    <button id="close-detail" class="close-btn">&times;</button>
                    <h2 id="detail-name">Activity Name</h2>
                    <button id="expand-detail" class="expand-btn" title="Open full view">
                        <svg viewBox="0 0 24 24" width="18" height="18"><path d="M21 11V3h-8l3.29 3.29-10 10L3 13v8h8l-3.29-3.29 10-10L21 11z"/></svg>
                    </button>
                </div>
                <div class="detail-content">
                    <div class="detail-meta" id="detail-meta"></div>
                    <div class="detail-stats" id="detail-stats"></div>
                    <div class="detail-map" id="detail-map"></div>
                    <div class="detail-streams" id="detail-streams"></div>
                    <div class="detail-photos" id="detail-photos"></div>
                    <div class="detail-social" id="detail-social"></div>
                    <div class="detail-shared" id="detail-shared"></div>
                </div>
            </div>
        </div>

        <!-- Stats View -->
        <div id="view-stats" class="view">
            <div class="stats-container">
                <div id="stats-filter-bar" class="filter-bar stats-filters"></div>
                <div class="summary-cards" id="summary-cards">
                    <div class="summary-card">
                        <div class="summary-value" id="total-sessions">-</div>
                        <div class="summary-label">Sessions</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-value" id="total-distance">-</div>
                        <div class="summary-label">Total Distance</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-value" id="total-time">-</div>
                        <div class="summary-label">Total Time</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-value" id="total-elevation">-</div>
                        <div class="summary-label">Elevation Gain</div>
                    </div>
                </div>
                <div class="charts-grid">
                    <div class="chart-container">
                        <h3>Monthly Activity</h3>
                        <canvas id="monthly-chart"></canvas>
                    </div>
                    <div class="chart-container">
                        <h3>By Activity Type</h3>
                        <canvas id="type-chart"></canvas>
                    </div>
                </div>
                <div id="stats-session-list" class="stats-session-panel"></div>
            </div>
        </div>

        <!-- Full-Screen Session View -->
        <div id="view-session" class="view">
            <div class="full-session-container">
                <header class="full-session-header">
                    <button class="back-btn" onclick="history.back()">
                        <svg viewBox="0 0 24 24" width="20" height="20"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
                        Back
                    </button>
                    <div class="full-session-title">
                        <h1 id="full-session-name">Activity Name</h1>
                        <div class="full-session-meta" id="full-session-meta"></div>
                    </div>
                    <button id="full-session-share" class="header-btn" title="Copy permalink" aria-label="Share activity">
                        <svg viewBox="0 0 24 24" width="18" height="18"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z"/></svg>
                    </button>
                </header>
                <div class="full-session-content">
                    <section class="full-session-stats" id="full-session-stats"></section>
                    <section class="full-session-map">
                        <div id="full-session-map-container"></div>
                        <div class="map-actions">
                            <button id="full-session-map-btn" class="action-btn-primary">
                                <svg viewBox="0 0 24 24"><path d="M20.5 3l-.16.03L15 5.1 9 3 3.36 4.9c-.21.07-.36.25-.36.48V20.5c0 .28.22.5.5.5l.16-.03L9 18.9l6 2.1 5.64-1.9c.21-.07.36-.25.36-.48V3.5c0-.28-.22-.5-.5-.5zM15 19l-6-2.11V5l6 2.11V19z"/></svg>
                                View on Map
                            </button>
                        </div>
                    </section>
                    <section class="full-session-streams" id="full-session-streams"></section>
                    <section class="full-session-photos" id="full-session-photos"></section>
                    <section class="full-session-social" id="full-session-social"></section>
                    <section class="full-session-shared" id="full-session-shared"></section>
                </div>
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
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
    <script type="module">
        import {{ parquetReadObjects }} from './assets/hyparquet/index.js';

        // ===== URL State Manager =====
        const URLState = {{
            // Encode state to URL hash with query params
            encode(state) {{
                const params = new URLSearchParams();
                if (state.athlete) params.set('a', state.athlete);
                if (state.zoom) params.set('z', state.zoom);
                if (state.lat) params.set('lat', state.lat.toFixed(4));
                if (state.lng) params.set('lng', state.lng.toFixed(4));
                if (state.session) params.set('s', state.session);
                if (state.search) params.set('q', state.search);
                if (state.type) params.set('t', state.type);
                if (state.dateFrom) params.set('from', state.dateFrom);
                if (state.dateTo) params.set('to', state.dateTo);
                const queryStr = params.toString();
                return '#/' + state.view + (queryStr ? '?' + queryStr : '');
            }},

            // Decode state from URL hash
            decode() {{
                const hash = location.hash.slice(2) || 'map';
                const [path, queryStr] = hash.split('?');
                const params = new URLSearchParams(queryStr || '');
                return {{
                    view: path.split('/')[0] || 'map',
                    athlete: params.get('a') || '',
                    zoom: params.get('z') ? parseInt(params.get('z')) : null,
                    lat: params.get('lat') ? parseFloat(params.get('lat')) : null,
                    lng: params.get('lng') ? parseFloat(params.get('lng')) : null,
                    session: params.get('s') || '',
                    search: params.get('q') || '',
                    type: params.get('t') || '',
                    dateFrom: params.get('from') || '',
                    dateTo: params.get('to') || ''
                }};
            }},

            // Update URL without triggering navigation
            update(partialState) {{
                // Don't update URL if we're on a full-screen session route
                // Session routes use a different format: #/session/athlete/datetime
                const hash = location.hash;
                if (hash.startsWith('#/session/') && hash.split('/').length >= 3) {{
                    return; // Preserve session permalink
                }}

                const current = this.decode();
                const newState = {{ ...current, ...partialState }};
                const newHash = this.encode(newState);
                // Use replaceState to avoid cluttering browser history
                history.replaceState(null, '', newHash);
            }}
        }};

        // ===== Shared Filter State =====
        const FilterState = {{
            state: {{
                search: '',
                type: '',
                dateFrom: '',
                dateTo: ''
            }},
            listeners: [],

            get() {{
                return {{ ...this.state }};
            }},

            set(newState, skipNotify = false) {{
                const changed = Object.keys(newState).some(k => this.state[k] !== newState[k]);
                if (changed) {{
                    this.state = {{ ...this.state, ...newState }};
                    if (!skipNotify) this.notify();
                }}
            }},

            clear() {{
                this.set({{ search: '', type: '', dateFrom: '', dateTo: '' }});
            }},

            onChange(callback) {{
                this.listeners.push(callback);
                return () => {{ this.listeners = this.listeners.filter(l => l !== callback); }};
            }},

            notify() {{
                for (const listener of this.listeners) {{
                    try {{ listener(this.state); }} catch (e) {{ console.error('FilterState listener error:', e); }}
                }}
            }},

            // Sync with URL
            syncToURL() {{
                URLState.update({{
                    search: this.state.search,
                    type: this.state.type,
                    dateFrom: this.state.dateFrom,
                    dateTo: this.state.dateTo
                }});
            }},

            syncFromURL() {{
                const urlState = URLState.decode();
                this.set({{
                    search: urlState.search || '',
                    type: urlState.type || '',
                    dateFrom: urlState.dateFrom || '',
                    dateTo: urlState.dateTo || ''
                }}, true);  // Skip notify - caller will handle
            }},

            hasActiveFilters() {{
                return this.state.search || this.state.type || this.state.dateFrom || this.state.dateTo;
            }}
        }};

        // ===== Shared Filter Function =====
        function applyFilters(sessions, filters, athlete = '') {{
            return sessions.filter(s => {{
                // Athlete filter (global, from header selector)
                if (athlete && s.athlete !== athlete) return false;
                // Search filter
                if (filters.search && !s.name.toLowerCase().includes(filters.search.toLowerCase())) return false;
                // Type filter
                if (filters.type && s.type !== filters.type) return false;
                // Date filters
                if (filters.dateFrom) {{
                    const fromDate = filters.dateFrom.replace(/-/g, '');
                    if (s.datetime < fromDate) return false;
                }}
                if (filters.dateTo) {{
                    const toDate = filters.dateTo.replace(/-/g, '');
                    if (s.datetime.substring(0, 8) > toDate) return false;
                }}
                return true;
            }});
        }}

        // ===== Shared FilterBar Component =====
        const FilterBar = {{
            containerId: null,
            types: [],

            render(containerId, options = {{}}) {{
                this.containerId = containerId;
                const container = document.getElementById(containerId);
                if (!container) return;

                const showSearch = options.showSearch !== false;
                const showType = options.showType !== false;
                const showDates = options.showDates !== false;
                const showDatePresets = options.showDatePresets !== false;

                const state = FilterState.get();

                let html = '';
                if (showSearch) {{
                    html += `<input type="search" class="filter-input filter-search" placeholder="Search activities..." value="${{state.search}}">`;
                }}
                if (showType) {{
                    html += `<select class="filter-select filter-type"><option value="">All Types</option></select>`;
                }}
                if (showDatePresets) {{
                    html += `<select class="filter-select filter-date-preset">
                        <option value="">Date Range</option>
                        <option value="thisYear">This Year</option>
                        <option value="last12m">Last 12 Months</option>
                        <option value="last30d">Last 30 Days</option>
                        <option value="thisMonth">This Month</option>
                    </select>`;
                }}
                if (showDates) {{
                    const navDisabled = !state.dateFrom || !state.dateTo ? 'disabled' : '';
                    html += `<div class="date-nav-group">`;
                    html += `<button type="button" class="date-nav-btn date-nav-btn--prev" title="Previous period" aria-label="Move date range backward" ${{navDisabled}}>
                        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 12L6 8l4-4"/></svg>
                    </button>`;
                    html += `<input type="date" class="filter-input filter-date filter-date-from" title="From date" value="${{state.dateFrom}}">`;
                    html += `<input type="date" class="filter-input filter-date filter-date-to" title="To date" value="${{state.dateTo}}">`;
                    html += `<button type="button" class="date-nav-btn date-nav-btn--next" title="Next period" aria-label="Move date range forward" ${{navDisabled}}>
                        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 12l4-4-4-4"/></svg>
                    </button>`;
                    html += `</div>`;
                }}
                html += `<button class="filter-btn filter-clear">Clear</button>`;
                html += `<span class="filter-count"></span>`;

                container.innerHTML = html;
            }},

            init(containerId) {{
                const container = document.getElementById(containerId);
                if (!container) return;

                // Search input
                const searchInput = container.querySelector('.filter-search');
                if (searchInput) {{
                    let debounceTimer;
                    searchInput.addEventListener('input', (e) => {{
                        clearTimeout(debounceTimer);
                        debounceTimer = setTimeout(() => {{
                            FilterState.set({{ search: e.target.value }});
                            FilterState.syncToURL();
                        }}, 300);
                    }});
                }}

                // Type filter
                const typeSelect = container.querySelector('.filter-type');
                if (typeSelect) {{
                    typeSelect.addEventListener('change', (e) => {{
                        FilterState.set({{ type: e.target.value }});
                        FilterState.syncToURL();
                    }});
                }}

                // Date preset
                const presetSelect = container.querySelector('.filter-date-preset');
                if (presetSelect) {{
                    presetSelect.addEventListener('change', (e) => {{
                        const today = new Date();
                        let dateFrom = '', dateTo = '';
                        switch (e.target.value) {{
                            case 'thisYear':
                                dateFrom = `${{today.getFullYear()}}-01-01`;
                                dateTo = today.toISOString().split('T')[0];
                                break;
                            case 'last12m':
                                const last12m = new Date(today);
                                last12m.setMonth(last12m.getMonth() - 12);
                                dateFrom = last12m.toISOString().split('T')[0];
                                dateTo = today.toISOString().split('T')[0];
                                break;
                            case 'last30d':
                                const last30d = new Date(today);
                                last30d.setDate(last30d.getDate() - 30);
                                dateFrom = last30d.toISOString().split('T')[0];
                                dateTo = today.toISOString().split('T')[0];
                                break;
                            case 'thisMonth':
                                dateFrom = `${{today.getFullYear()}}-${{String(today.getMonth() + 1).padStart(2, '0')}}-01`;
                                dateTo = today.toISOString().split('T')[0];
                                break;
                        }}
                        FilterState.set({{ dateFrom, dateTo }});
                        FilterState.syncToURL();
                        // Update date inputs
                        const fromInput = container.querySelector('.filter-date-from');
                        const toInput = container.querySelector('.filter-date-to');
                        if (fromInput) fromInput.value = dateFrom;
                        if (toInput) toInput.value = dateTo;
                        // Update nav button states
                        this.updateDateNavButtons(container);
                    }});
                }}

                // Date from
                const dateFromInput = container.querySelector('.filter-date-from');
                if (dateFromInput) {{
                    dateFromInput.addEventListener('change', (e) => {{
                        FilterState.set({{ dateFrom: e.target.value }});
                        FilterState.syncToURL();
                        // Reset preset
                        const preset = container.querySelector('.filter-date-preset');
                        if (preset) preset.value = '';
                        // Update nav button states
                        this.updateDateNavButtons(container);
                    }});
                }}

                // Date to
                const dateToInput = container.querySelector('.filter-date-to');
                if (dateToInput) {{
                    dateToInput.addEventListener('change', (e) => {{
                        FilterState.set({{ dateTo: e.target.value }});
                        FilterState.syncToURL();
                        // Reset preset
                        const preset = container.querySelector('.filter-date-preset');
                        if (preset) preset.value = '';
                        // Update nav button states
                        this.updateDateNavButtons(container);
                    }});
                }}

                // Date navigation buttons
                const prevBtn = container.querySelector('.date-nav-btn--prev');
                const nextBtn = container.querySelector('.date-nav-btn--next');

                const navigateDates = (direction) => {{
                    const state = FilterState.get();
                    if (!state.dateFrom || !state.dateTo) return;

                    const fromDate = new Date(state.dateFrom);
                    const toDate = new Date(state.dateTo);
                    const intervalMs = toDate - fromDate;
                    // If same date, use 1 day interval
                    const dayMs = 24 * 60 * 60 * 1000;
                    const shiftMs = intervalMs > 0 ? intervalMs : dayMs;

                    if (direction === 'prev') {{
                        fromDate.setTime(fromDate.getTime() - shiftMs);
                        toDate.setTime(toDate.getTime() - shiftMs);
                    }} else {{
                        fromDate.setTime(fromDate.getTime() + shiftMs);
                        toDate.setTime(toDate.getTime() + shiftMs);
                    }}

                    const newFrom = fromDate.toISOString().split('T')[0];
                    const newTo = toDate.toISOString().split('T')[0];

                    FilterState.set({{ dateFrom: newFrom, dateTo: newTo }});
                    FilterState.syncToURL();

                    // Update inputs
                    if (dateFromInput) dateFromInput.value = newFrom;
                    if (dateToInput) dateToInput.value = newTo;

                    // Reset preset dropdown
                    const preset = container.querySelector('.filter-date-preset');
                    if (preset) preset.value = '';
                }};

                if (prevBtn) {{
                    prevBtn.addEventListener('click', () => navigateDates('prev'));
                }}
                if (nextBtn) {{
                    nextBtn.addEventListener('click', () => navigateDates('next'));
                }}

                // Clear button
                const clearBtn = container.querySelector('.filter-clear');
                if (clearBtn) {{
                    clearBtn.addEventListener('click', () => {{
                        FilterState.clear();
                        FilterState.syncToURL();
                        this.syncFromState(containerId);
                    }});
                }}
            }},

            populateTypes(containerId, sessions) {{
                const container = document.getElementById(containerId);
                if (!container) return;
                const typeSelect = container.querySelector('.filter-type');
                if (!typeSelect) return;

                const types = [...new Set(sessions.map(s => s.type).filter(Boolean))].sort();
                const currentValue = typeSelect.value;
                typeSelect.innerHTML = '<option value="">All Types</option>';
                for (const type of types) {{
                    const option = document.createElement('option');
                    option.value = type;
                    option.textContent = type;
                    typeSelect.appendChild(option);
                }}
                typeSelect.value = currentValue;
            }},

            syncFromState(containerId) {{
                const container = document.getElementById(containerId);
                if (!container) return;
                const state = FilterState.get();

                const searchInput = container.querySelector('.filter-search');
                if (searchInput) searchInput.value = state.search;

                const typeSelect = container.querySelector('.filter-type');
                if (typeSelect) typeSelect.value = state.type;

                const dateFromInput = container.querySelector('.filter-date-from');
                if (dateFromInput) dateFromInput.value = state.dateFrom;

                const dateToInput = container.querySelector('.filter-date-to');
                if (dateToInput) dateToInput.value = state.dateTo;

                // Update nav button states
                this.updateDateNavButtons(container);
            }},

            updateDateNavButtons(container) {{
                const state = FilterState.get();
                const hasBothDates = state.dateFrom && state.dateTo;
                const prevBtn = container.querySelector('.date-nav-btn--prev');
                const nextBtn = container.querySelector('.date-nav-btn--next');
                if (prevBtn) prevBtn.disabled = !hasBothDates;
                if (nextBtn) nextBtn.disabled = !hasBothDates;
            }},

            updateCount(containerId, filteredCount, totalCount) {{
                const container = document.getElementById(containerId);
                if (!container) return;
                const countEl = container.querySelector('.filter-count');
                if (countEl) {{
                    if (FilterState.hasActiveFilters()) {{
                        countEl.textContent = `${{filteredCount}} of ${{totalCount}}`;
                        countEl.style.display = 'inline';
                    }} else {{
                        countEl.textContent = '';
                        countEl.style.display = 'none';
                    }}
                }}
            }}
        }};

        // ===== Session List Panel Component =====
        const SessionListPanel = {{
            containerId: null,
            sessions: [],
            onSessionClick: null,
            displayLimit: 50,

            render(containerId, options = {{}}) {{
                this.containerId = containerId;
                this.onSessionClick = options.onSessionClick || null;
                const container = document.getElementById(containerId);
                if (!container) return;

                container.innerHTML = `
                    <div class="session-list-header">
                        <span class="session-list-title">Sessions</span>
                        <span class="session-list-count">0</span>
                        <button class="session-list-toggle" title="Toggle panel">▼</button>
                    </div>
                    <div class="session-list-content">
                        <div class="session-list-items"></div>
                        <button class="session-list-more" style="display: none;">Load more...</button>
                    </div>
                `;

                // Toggle button
                const toggle = container.querySelector('.session-list-toggle');
                const content = container.querySelector('.session-list-content');
                toggle.addEventListener('click', () => {{
                    container.classList.toggle('collapsed');
                    toggle.textContent = container.classList.contains('collapsed') ? '▲' : '▼';
                }});

                // Load more button
                const moreBtn = container.querySelector('.session-list-more');
                moreBtn.addEventListener('click', () => {{
                    this.displayLimit += 50;
                    this.updateList();
                }});
            }},

            setSessions(sessions) {{
                this.sessions = sessions;
                this.displayLimit = 50;
                this.updateList();
            }},

            updateList() {{
                const container = document.getElementById(this.containerId);
                if (!container) return;

                const countEl = container.querySelector('.session-list-count');
                if (countEl) countEl.textContent = this.sessions.length;

                const itemsEl = container.querySelector('.session-list-items');
                if (!itemsEl) return;

                const toShow = this.sessions.slice(0, this.displayLimit);
                itemsEl.innerHTML = toShow.map(s => {{
                    const dateStr = s.datetime ? `${{s.datetime.substring(0,4)}}-${{s.datetime.substring(4,6)}}-${{s.datetime.substring(6,8)}}` : '';
                    const distance = s.distance_m > 0 ? `${{(parseFloat(s.distance_m) / 1000).toFixed(1)}} km` : '';
                    return `
                        <div class="session-list-item" data-athlete="${{s.athlete}}" data-datetime="${{s.datetime}}">
                            <div class="session-list-item-header">
                                <span class="session-list-item-date">${{dateStr}}</span>
                                <span class="session-list-item-type">${{s.type || ''}}</span>
                            </div>
                            <div class="session-list-item-name">${{s.name || 'Untitled'}}</div>
                            <div class="session-list-item-stats">${{distance}}</div>
                        </div>
                    `;
                }}).join('');

                // Show/hide load more button
                const moreBtn = container.querySelector('.session-list-more');
                if (moreBtn) {{
                    moreBtn.style.display = this.sessions.length > this.displayLimit ? 'block' : 'none';
                }}

                // Add click handlers
                itemsEl.querySelectorAll('.session-list-item').forEach(item => {{
                    item.addEventListener('click', () => {{
                        const athlete = item.dataset.athlete;
                        const datetime = item.dataset.datetime;
                        if (this.onSessionClick) {{
                            this.onSessionClick(athlete, datetime);
                        }} else {{
                            location.hash = `#/session/${{athlete}}/${{datetime}}`;
                        }}
                    }});
                }});
            }}
        }};

        // ===== Router =====
        const Router = {{
            views: ['map', 'sessions', 'stats', 'session'],
            currentView: 'map',
            initialState: null,

            init() {{
                // Decode initial state from URL
                this.initialState = URLState.decode();

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
                const hash = location.hash.slice(2) || 'map';
                const parts = hash.split('/');
                const view = parts[0].split('?')[0];

                // Handle full-screen session route: #/session/athlete/datetime
                if (view === 'session' && parts.length >= 3) {{
                    const athlete = parts[1];
                    const datetime = parts[2].split('?')[0];
                    this.showView('session');
                    FullSessionView.show(athlete, datetime);
                    return;
                }}

                if (this.views.includes(view) && view !== 'session') {{
                    const state = URLState.decode();
                    this.showView(view);
                    // Apply state after view switch
                    this.applyState(state);
                }} else if (!this.views.includes(view)) {{
                    this.navigate('map');
                }}
            }},

            applyState(state) {{
                // Apply athlete filter if specified
                if (state.athlete) {{
                    const selector = document.getElementById('athlete-selector');
                    if (selector) {{
                        selector.value = state.athlete;
                        // Don't dispatch change event - we'll handle filtering below
                    }}
                }}

                // Apply map position if on map view
                if (state.view === 'map' && state.zoom && state.lat && state.lng) {{
                    if (MapView.map) {{
                        MapView.map.setView([state.lat, state.lng], state.zoom);
                    }}
                }}

                // Sync shared FilterState from URL (applies to all views)
                FilterState.syncFromURL();

                // Sync all filter bars from shared state
                FilterBar.syncFromState('map-filter-bar');
                FilterBar.syncFromState('sessions-filter-bar');
                FilterBar.syncFromState('stats-filter-bar');

                // Trigger re-render for current view
                if (state.view === 'map') {{
                    MapView.applyFiltersAndUpdateUI();
                }} else if (state.view === 'sessions') {{
                    SessionsView.applyFiltersAndRender();
                }} else if (state.view === 'stats') {{
                    StatsView.calculate();
                }}

                // Open session detail if specified
                if (state.session && state.athlete && state.view === 'sessions') {{
                    setTimeout(() => {{
                        SessionsView.showDetail(state.athlete, state.session);
                    }}, 500);
                }}
            }},

            navigate(view) {{
                // Preserve athlete and filter state when navigating between views
                const currentAthlete = document.getElementById('athlete-selector')?.value || '';
                const filters = FilterState.get();

                // Build new hash with preserved filter state
                const params = new URLSearchParams();
                if (currentAthlete) params.set('a', currentAthlete);
                if (filters.search) params.set('q', filters.search);
                if (filters.type) params.set('t', filters.type);
                if (filters.dateFrom) params.set('from', filters.dateFrom);
                if (filters.dateTo) params.set('to', filters.dateTo);
                const queryStr = params.toString();
                const newHash = '#/' + view + (queryStr ? '?' + queryStr : '');

                // Set location.hash directly to trigger hashchange event
                // Don't use URLState.update() as it uses replaceState which doesn't trigger hashchange
                location.hash = newHash;
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
            tracksBySession: {{}},  // Map of "athlete|session" -> polyline layer
            photosBySession: {{}},  // Map of "athlete|session" -> array of photo markers
            allMarkers: [],
            allSessions: [],
            filteredSessions: [],  // Sessions after applying filters
            sessionsByAthlete: {{}},
            athleteStats: {{}},
            currentAthlete: '',
            totalSessions: 0,
            loadedTrackCount: 0,
            totalPhotos: 0,
            infoControl: null,
            sessionListExpanded: false,
            sessionListHeight: 300,  // Default height, updated when user resizes
            AUTO_LOAD_ZOOM: 11,
            restoringFromURL: false,

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
                // Check if we should restore map position from URL
                const urlState = Router.initialState;
                let initialLat = 20, initialLng = 0, initialZoom = 3;
                if (urlState && urlState.zoom && urlState.lat && urlState.lng) {{
                    initialLat = urlState.lat;
                    initialLng = urlState.lng;
                    initialZoom = urlState.zoom;
                    this.restoringFromURL = true;
                }}

                // Initialize map with URL position or world view default
                this.map = L.map('map', {{ preferCanvas: true }}).setView([initialLat, initialLng], initialZoom);
                window.mapInstance = this.map;

                L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19,
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                    // Reduce tile requests to avoid rate limiting
                    keepBuffer: 4,           // Keep more tiles cached around viewport
                    updateWhenZooming: false, // Don't fetch during zoom animation
                    updateWhenIdle: true      // Only fetch when map stops moving
                }}).addTo(this.map);

                this.bounds = L.latLngBounds();
                this.sessionsLayer = L.layerGroup().addTo(this.map);
                this.tracksLayer = L.layerGroup().addTo(this.map);
                this.photosLayer = L.layerGroup().addTo(this.map);
                this.heatmapLayer = null;  // Created lazily when needed
                this.heatmapPoints = [];   // Collected from track data
                this.displayMode = 'tracks';  // 'tracks' or 'heatmap'

                // Set up legend
                this.setupLegend();

                // Set up custom layers control
                this.setupLayersControl();

                // Set up zoom-to-fit control
                const fitBoundsControl = L.control({{ position: 'topright' }});
                const self = this;
                fitBoundsControl.onAdd = function() {{
                    const div = L.DomUtil.create('div', 'leaflet-control-fitbounds leaflet-bar');
                    div.innerHTML = `
                        <button type="button" title="Fit all activities" aria-label="Zoom map to show all filtered activities">
                            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                                <path d="M2 5V2h3M11 2h3v3M14 11v3h-3M5 14H2v-3"/>
                                <path d="M5 5h6v6H5z"/>
                            </svg>
                        </button>
                    `;
                    L.DomEvent.disableClickPropagation(div);
                    div.querySelector('button').addEventListener('click', () => {{
                        self.fitToVisibleMarkers();
                    }});
                    return div;
                }};
                fitBoundsControl.addTo(this.map);

                // Set up auto-loading on zoom/pan
                this.map.on('moveend', () => this.loadVisibleTracks());
                this.map.on('zoomend', () => {{
                    this.loadVisibleTracks();
                    this.updateInfo();
                }});

                // Update URL when map position changes (debounced)
                let urlUpdateTimeout = null;
                this.map.on('moveend', () => {{
                    clearTimeout(urlUpdateTimeout);
                    urlUpdateTimeout = setTimeout(() => {{
                        const center = this.map.getCenter();
                        const zoom = this.map.getZoom();
                        URLState.update({{ zoom, lat: center.lat, lng: center.lng }});
                    }}, 500);
                }});

                // Set up athlete selector
                document.getElementById('athlete-selector').addEventListener('change', (e) => {{
                    this.filterByAthlete(e.target.value);
                    URLState.update({{ athlete: e.target.value }});
                    this.applyFiltersAndUpdateUI();
                }});

                // Initialize filter bar for map
                FilterBar.render('map-filter-bar', {{
                    showSearch: true,
                    showType: true,
                    showDatePresets: true,
                    showDates: true
                }});
                FilterBar.init('map-filter-bar');

                // Subscribe to filter changes
                FilterState.onChange(() => this.applyFiltersAndUpdateUI());

                // Start loading sessions
                this.loadSessions();
            }},

            // Apply filters and update UI (markers, info panel)
            applyFiltersAndUpdateUI() {{
                if (!this.allSessions.length) return;

                const athlete = this.currentAthlete;
                const filters = FilterState.get();
                const filtered = applyFilters(this.allSessions, filters, athlete);

                // Store filtered sessions sorted by date desc
                this.filteredSessions = [...filtered].sort((a, b) => (b.datetime || '').localeCompare(a.datetime || ''));

                // Build a set of visible session keys for quick lookup
                const visibleKeys = new Set(filtered.map(s => `${{s.athlete}}|${{s.datetime}}`));

                // Update marker visibility by adding/removing from layer
                // This is the proper Leaflet way to show/hide markers
                for (const data of this.allMarkers) {{
                    const key = `${{data.athlete}}|${{data.session}}`;
                    const visible = visibleKeys.has(key);
                    data.visible = visible;

                    if (visible) {{
                        if (!this.sessionsLayer.hasLayer(data.marker)) {{
                            data.marker.addTo(this.sessionsLayer);
                        }}
                    }} else {{
                        this.sessionsLayer.removeLayer(data.marker);
                    }}
                }}

                // Update track visibility - show/hide loaded tracks based on filter
                for (const [sessionKey, polyline] of Object.entries(this.tracksBySession)) {{
                    if (visibleKeys.has(sessionKey)) {{
                        if (!this.tracksLayer.hasLayer(polyline)) {{
                            polyline.addTo(this.tracksLayer);
                        }}
                    }} else {{
                        this.tracksLayer.removeLayer(polyline);
                    }}
                }}

                // Update photo visibility - show/hide loaded photos based on filter
                for (const [sessionKey, markers] of Object.entries(this.photosBySession)) {{
                    const visible = visibleKeys.has(sessionKey);
                    for (const marker of markers) {{
                        if (visible) {{
                            if (!this.photosLayer.hasLayer(marker)) {{
                                marker.addTo(this.photosLayer);
                            }}
                        }} else {{
                            this.photosLayer.removeLayer(marker);
                        }}
                    }}
                }}

                // Update info panel (which now includes session count and list)
                FilterBar.updateCount('map-filter-bar', filtered.length, this.allSessions.length);
                this.updateInfo();

                // Update legend to reflect active filter
                this.updateLegendContent();
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
                // Apply filters (includes athlete filter) and update markers
                this.applyFiltersAndUpdateUI();

                // Recalculate bounds for visible markers and fit
                this.fitToVisibleMarkers();
            }},

            fitToVisibleMarkers() {{
                this.bounds = L.latLngBounds();
                for (const data of this.allMarkers) {{
                    if (data.visible) {{
                        this.bounds.extend(data.marker.getLatLng());
                    }}
                }}
                if (this.bounds.isValid()) {{
                    // Use flyToBounds for smooth animation
                    this.map.flyToBounds(this.bounds, {{ padding: [20, 20], duration: 0.8 }});
                }}
            }},

            zoomToSession(athlete, session) {{
                const markerData = this.allMarkers.find(m => m.athlete === athlete && m.session === session);
                if (markerData && markerData.marker) {{
                    // Get the track bounds if available, otherwise use marker location
                    const sessionKey = `${{athlete}}|${{session}}`;
                    const track = this.tracksBySession[sessionKey];
                    if (track) {{
                        // Smooth animated zoom to track bounds
                        this.map.flyToBounds(track.getBounds(), {{ padding: [50, 50], maxZoom: 14, duration: 0.8 }});
                    }} else {{
                        // Smooth animated zoom to marker
                        this.map.flyTo(markerData.marker.getLatLng(), 13, {{ duration: 0.8 }});
                        // Load the track for better view
                        this.loadTrack(athlete, session, markerData.color);
                    }}
                }}
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
                            const polyline = L.polyline(coords, {{
                                color: color,
                                weight: 3,
                                opacity: 0.7
                            }}).addTo(this.tracksLayer);

                            // Store reference for filtering
                            const sessionKey = `${{athlete}}|${{session}}`;
                            this.tracksBySession[sessionKey] = polyline;

                            // Add points to heatmap data
                            this.addPointsToHeatmap(coords);

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

                    // Initialize array for this session's photos
                    const sessionKey = `${{athlete}}|${{session}}`;
                    this.photosBySession[sessionKey] = [];

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
                                    <div class="popup-links">
                                        <a href="javascript:void(0)" class="popup-zoom-link" onclick="MapView.zoomToSession('${{athlete}}', '${{session}}')">Zoom in</a>
                                        <a href="#/session/${{athlete}}/${{session}}" class="popup-activity-link">View Activity →</a>
                                    </div>
                                </div>
                            </div>
                        `, {{ maxWidth: 350 }});

                        marker.addTo(this.photosLayer);
                        this.photosBySession[sessionKey].push(marker);
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

                        // Initialize sessionsByAthlete for this athlete
                        this.sessionsByAthlete[username] = [];

                        try {{
                            const sessionsResp = await fetch(`athl=${{username}}/sessions.tsv`);
                            if (!sessionsResp.ok) continue;

                            const sessionsText = await sessionsResp.text();
                            const sessions = this.parseTSV(sessionsText);

                            for (const session of sessions) {{
                                const lat = parseFloat(session.start_lat);
                                const lng = parseFloat(session.start_lng);
                                const distance = parseFloat(session.distance_m || 0);

                                // Track athlete stats
                                this.athleteStats[username].sessions++;
                                this.athleteStats[username].distance += distance;

                                // Store full session data for SessionsView
                                const type = session.sport || session.type || 'Other';
                                const sessionData = {{
                                    athlete: username,
                                    datetime: session.datetime,
                                    name: session.name || 'Activity',
                                    type: type,
                                    distance_m: session.distance_m || '0',
                                    moving_time_s: session.moving_time_s || '0',
                                    elevation_gain_m: session.elevation_gain_m || '0',
                                    photo_count: session.photo_count || '0',
                                    has_gps: session.has_gps,
                                    start_lat: session.start_lat,
                                    start_lng: session.start_lng
                                }};
                                this.allSessions.push(sessionData);
                                this.sessionsByAthlete[username].push(sessionData);

                                if (isNaN(lat) || isNaN(lng)) continue;

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
                                    <div class="popup-links">
                                        <a href="javascript:void(0)" class="popup-zoom-link" onclick="MapView.zoomToSession('${{username}}', '${{session.datetime}}')">Zoom in</a>
                                        <a href="#/session/${{username}}/${{session.datetime}}" class="popup-activity-link">View Activity →</a>
                                    </div>
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

                    // Only fit bounds if not restoring from URL
                    if (this.bounds.isValid() && !this.restoringFromURL) {{
                        this.map.fitBounds(this.bounds, {{ padding: [20, 20] }});
                    }}
                    this.restoringFromURL = false;  // Reset flag after first load

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
                // Save scroll position and list height before updating
                let savedScrollTop = 0;
                if (this.infoControl) {{
                    const existingList = document.querySelector('.info-session-list');
                    if (existingList) {{
                        savedScrollTop = existingList.scrollTop;
                        // Save user's resized height if different from default
                        const height = existingList.offsetHeight;
                        if (height > 0) {{
                            this.sessionListHeight = height;
                        }}
                    }}
                    this.infoControl.remove();
                }}
                this.infoControl = L.control({{ position: 'topright' }});
                const self = this;
                this.infoControl.onAdd = function() {{
                    const div = L.DomUtil.create('div', 'info map-info-panel');

                    // Use filtered sessions count
                    const filteredCount = self.filteredSessions.length;
                    const totalCount = self.allSessions.length;
                    const hasFilter = FilterState.hasActiveFilters() || self.currentAthlete;

                    let html = '<div class="info-header"><b>Activities</b>';
                    if (self.currentAthlete) {{
                        const color = self.athleteColors[self.currentAthlete] || '#333';
                        html += ` <span style="color:${{color}}">${{self.currentAthlete}}</span>`;
                    }}
                    html += '</div>';

                    // Session count with filter indicator
                    const countText = hasFilter ? `${{filteredCount}} of ${{totalCount}}` : `${{filteredCount}}`;
                    html += `<div class="info-stats">`;
                    html += `<span class="info-sessions-toggle" title="Click to ${{self.sessionListExpanded ? 'collapse' : 'expand'}} session list">${{countText}} sessions ${{self.sessionListExpanded ? '▲' : '▼'}}</span>`;
                    if (self.loadedTrackCount > 0) {{
                        html += `<br>${{self.loadedTrackCount}} tracks`;
                    }}
                    if (self.totalPhotos > 0) {{
                        html += ` · ${{self.totalPhotos}} photos`;
                    }}
                    html += `</div>`;

                    // Collapsible session list
                    if (self.sessionListExpanded && self.filteredSessions.length > 0) {{
                        html += `<div class="info-session-list">`;
                        const toShow = self.filteredSessions.slice(0, 50);  // Show more sessions
                        for (const s of toShow) {{
                            const dateStr = s.datetime ? `${{s.datetime.substring(0,4)}}-${{s.datetime.substring(4,6)}}-${{s.datetime.substring(6,8)}}` : '';
                            const dist = s.distance_m > 0 ? ` · ${{(parseFloat(s.distance_m) / 1000).toFixed(1)}}km` : '';
                            html += `<div class="info-session-item" data-athlete="${{s.athlete}}" data-datetime="${{s.datetime}}">`;
                            html += `<div class="info-session-main">`;
                            html += `<span class="info-session-date">${{dateStr}}</span>`;
                            html += `<span class="info-session-type">${{s.type || ''}}</span>`;
                            html += `<div class="info-session-name">${{s.name || 'Untitled'}}${{dist}}</div>`;
                            html += `</div>`;
                            html += `<a href="#/session/${{s.athlete}}/${{s.datetime}}" class="info-session-link" title="View Activity">→</a>`;
                            html += `</div>`;
                        }}
                        if (self.filteredSessions.length > 50) {{
                            html += `<div class="info-session-more"><a href="#/sessions">View all ${{self.filteredSessions.length}} sessions</a></div>`;
                        }}
                        html += `</div>`;
                        html += `<div class="info-resize-handle" title="Drag to resize"></div>`;
                    }}

                    // Zoom hint
                    const zoom = self.map.getZoom();
                    if (zoom < self.AUTO_LOAD_ZOOM) {{
                        html += `<div class="info-hint">Zoom in to auto-load tracks</div>`;
                    }}

                    div.innerHTML = html;

                    // Set up event listeners after DOM is ready
                    setTimeout(() => {{
                        // Restore scroll position and height
                        const newList = div.querySelector('.info-session-list');
                        if (newList) {{
                            // Apply saved height if user has resized
                            if (self.sessionListHeight && self.sessionListHeight > 0) {{
                                newList.style.maxHeight = self.sessionListHeight + 'px';
                            }}
                            // Restore scroll position - use requestAnimationFrame for reliability
                            if (savedScrollTop > 0) {{
                                requestAnimationFrame(() => {{
                                    newList.scrollTop = savedScrollTop;
                                }});
                            }}
                            // Prevent scroll events from propagating to map (fixes touchpad scrolling)
                            newList.addEventListener('wheel', (e) => {{
                                e.stopPropagation();
                            }}, {{ passive: true }});
                        }}

                        // Prevent map interactions on the entire panel
                        L.DomEvent.disableScrollPropagation(div);
                        L.DomEvent.disableClickPropagation(div);

                        // Resize handle drag functionality
                        const resizeHandle = div.querySelector('.info-resize-handle');
                        if (resizeHandle && newList) {{
                            let startY, startHeight;
                            const onMouseMove = (e) => {{
                                const delta = e.clientY - startY;
                                // Allow expanding up to 80% of viewport height
                                const maxHeight = Math.min(800, window.innerHeight * 0.8);
                                const newHeight = Math.max(100, Math.min(maxHeight, startHeight + delta));
                                newList.style.maxHeight = newHeight + 'px';
                                // Save height for persistence
                                self.sessionListHeight = newHeight;
                            }};
                            const onMouseUp = () => {{
                                document.removeEventListener('mousemove', onMouseMove);
                                document.removeEventListener('mouseup', onMouseUp);
                                document.body.style.cursor = '';
                                document.body.style.userSelect = '';
                            }};
                            resizeHandle.addEventListener('mousedown', (e) => {{
                                e.preventDefault();
                                startY = e.clientY;
                                startHeight = newList.offsetHeight;
                                document.body.style.cursor = 'ns-resize';
                                document.body.style.userSelect = 'none';
                                document.addEventListener('mousemove', onMouseMove);
                                document.addEventListener('mouseup', onMouseUp);
                            }});
                        }}

                        // Toggle session list
                        const toggle = div.querySelector('.info-sessions-toggle');
                        if (toggle) {{
                            toggle.addEventListener('click', (e) => {{
                                e.preventDefault();
                                self.sessionListExpanded = !self.sessionListExpanded;
                                self.updateInfo();
                            }});
                        }}
                        // Session item clicks - zoom to session on map
                        div.querySelectorAll('.info-session-item').forEach(item => {{
                            // Click on main area zooms to session
                            const mainArea = item.querySelector('.info-session-main');
                            if (mainArea) {{
                                mainArea.style.cursor = 'pointer';
                                mainArea.addEventListener('click', (e) => {{
                                    e.preventDefault();
                                    e.stopPropagation();
                                    const athlete = item.dataset.athlete;
                                    const datetime = item.dataset.datetime;
                                    self.zoomToSession(athlete, datetime);
                                }});
                            }}
                            // Arrow link navigates to session (handled by href)
                        }});
                    }}, 0);

                    return div;
                }};
                this.infoControl.addTo(this.map);
            }},

            setupLegend() {{
                this.legendControl = L.control({{ position: 'bottomright' }});
                const self = this;
                this.legendControl.onAdd = function() {{
                    const div = L.DomUtil.create('div', 'info legend');
                    self.updateLegendContent(div);
                    return div;
                }};
                this.legendControl.addTo(this.map);
            }},

            updateLegendContent(div) {{
                if (!div) {{
                    div = document.querySelector('.info.legend');
                }}
                if (!div) return;

                if (this.displayMode === 'heatmap') {{
                    div.innerHTML = '<b>Activity Density</b><br>';
                    div.innerHTML += '<div class="heatmap-gradient"></div>';
                    div.innerHTML += '<div class="heatmap-labels"><span>Low</span><span>High</span></div>';
                    div.innerHTML += `<br>${{this.heatmapPoints.length.toLocaleString()}} GPS points`;
                }} else {{
                    const currentType = FilterState.get().type || '';
                    div.innerHTML = '<b>Activity Types</b><br>';
                    for (const [type, color] of Object.entries(this.typeColors)) {{
                        const isActive = currentType === type;
                        div.innerHTML += `<span class="legend-type-item${{isActive ? ' active' : ''}}" data-type="${{type}}" style="cursor:pointer;display:block;padding:2px 4px;margin:1px 0;border-radius:3px;${{isActive ? 'background:rgba(0,0,0,0.1);font-weight:bold;' : ''}}"><i style="background:${{color}}"></i> ${{type}}</span>`;
                    }}
                    // Clear filter option when a filter is active
                    if (currentType) {{
                        div.innerHTML += `<span class="legend-clear-filter" style="cursor:pointer;display:block;padding:2px 4px;margin-top:4px;color:#666;font-style:italic;">&times; Clear filter</span>`;
                    }}
                    div.innerHTML += '<br><i style="background:#E91E63;border-radius:50%;"></i> Photos';

                    // Add click handlers
                    div.querySelectorAll('.legend-type-item').forEach(item => {{
                        item.addEventListener('click', (e) => {{
                            e.preventDefault();
                            e.stopPropagation();
                            const clickedType = item.dataset.type;
                            const current = FilterState.get().type;
                            // Toggle: if clicking active type, clear it
                            const newType = current === clickedType ? '' : clickedType;
                            FilterState.set({{ type: newType }});
                            FilterState.syncToURL();
                            this.updateLegendContent(div);
                        }});
                        item.addEventListener('mouseenter', () => {{
                            if (!item.classList.contains('active')) {{
                                item.style.background = 'rgba(0,0,0,0.05)';
                            }}
                        }});
                        item.addEventListener('mouseleave', () => {{
                            if (!item.classList.contains('active')) {{
                                item.style.background = 'transparent';
                            }}
                        }});
                    }});
                    const clearBtn = div.querySelector('.legend-clear-filter');
                    if (clearBtn) {{
                        clearBtn.addEventListener('click', (e) => {{
                            e.preventDefault();
                            e.stopPropagation();
                            FilterState.set({{ type: '' }});
                            FilterState.syncToURL();
                            this.updateLegendContent(div);
                        }});
                        clearBtn.addEventListener('mouseenter', () => {{
                            clearBtn.style.background = 'rgba(0,0,0,0.05)';
                        }});
                        clearBtn.addEventListener('mouseleave', () => {{
                            clearBtn.style.background = 'transparent';
                        }});
                    }}
                }}
            }},

            setupLayersControl() {{
                const layersControl = L.control({{ position: 'topleft' }});
                const self = this;

                layersControl.onAdd = function() {{
                    const div = L.DomUtil.create('div', 'info layers-control');

                    div.innerHTML = `
                        <div class="layers-control-header">
                            <svg viewBox="0 0 24 24"><path d="M11.99 18.54l-7.37-5.73L3 14.07l9 7 9-7-1.63-1.27-7.38 5.74zM12 16l7.36-5.73L21 9l-9-7-9 7 1.63 1.27L12 16z"/></svg>
                            Layers
                        </div>
                        <div class="layers-section">
                            <div class="layers-section-label">Display Mode</div>
                            <label>
                                <input type="radio" name="displayMode" value="tracks" checked>
                                Tracks
                            </label>
                            <label>
                                <input type="radio" name="displayMode" value="heatmap">
                                Heatmap
                            </label>
                        </div>
                        <div class="layers-divider"></div>
                        <div class="layers-section">
                            <div class="layers-section-label">Overlays</div>
                            <label>
                                <input type="checkbox" name="showMarkers" checked>
                                Markers
                            </label>
                            <label>
                                <input type="checkbox" name="showPhotos" checked>
                                Photos
                            </label>
                        </div>
                    `;

                    // Prevent map interactions
                    L.DomEvent.disableClickPropagation(div);
                    L.DomEvent.disableScrollPropagation(div);

                    // Display mode radio buttons
                    div.querySelectorAll('input[name="displayMode"]').forEach(radio => {{
                        radio.addEventListener('change', (e) => {{
                            self.setDisplayMode(e.target.value);
                        }});
                    }});

                    // Overlay checkboxes
                    div.querySelector('input[name="showMarkers"]').addEventListener('change', (e) => {{
                        if (e.target.checked) {{
                            self.sessionsLayer.addTo(self.map);
                        }} else {{
                            self.map.removeLayer(self.sessionsLayer);
                        }}
                    }});

                    div.querySelector('input[name="showPhotos"]').addEventListener('change', (e) => {{
                        if (e.target.checked) {{
                            self.photosLayer.addTo(self.map);
                        }} else {{
                            self.map.removeLayer(self.photosLayer);
                        }}
                    }});

                    return div;
                }};

                layersControl.addTo(this.map);
            }},

            setDisplayMode(mode) {{
                this.displayMode = mode;

                if (mode === 'heatmap') {{
                    // Hide tracks, show heatmap
                    this.map.removeLayer(this.tracksLayer);
                    // Auto-load visible tracks for heatmap data
                    this.loadVisibleTracksForHeatmap();
                }} else {{
                    // Hide heatmap, show tracks
                    if (this.heatmapLayer) {{
                        this.map.removeLayer(this.heatmapLayer);
                        // Destroy the layer to avoid stale canvas issues
                        this.heatmapLayer = null;
                    }}
                    this.tracksLayer.addTo(this.map);
                }}

                // Update legend
                this.updateLegendContent();
            }},

            async loadVisibleTracksForHeatmap() {{
                // Load all visible tracks to populate heatmap data
                const bounds = this.map.getBounds();
                // Use allMarkers and filter by both visibility (from filters) and map bounds
                const visibleMarkers = (this.allMarkers || []).filter(m => {{
                    if (!m.visible) return false;
                    const pos = m.marker.getLatLng();
                    return bounds.contains(pos);
                }});

                // Load tracks for visible markers that aren't already loaded
                const loadPromises = [];
                for (const m of visibleMarkers) {{
                    const trackKey = `${{m.athlete}}/${{m.session}}`;
                    if (!this.loadedTracks.has(trackKey) && !this.loadingTracks.has(trackKey)) {{
                        loadPromises.push(this.loadTrack(m.athlete, m.session, m.color));
                    }}
                }}

                // Wait for some tracks to load before showing heatmap
                if (loadPromises.length > 0) {{
                    console.log(`Loading ${{loadPromises.length}} tracks for heatmap...`);
                    await Promise.all(loadPromises);
                }}

                // Now show the heatmap
                this.createOrShowHeatmap();
            }},

            createOrShowHeatmap() {{
                // Don't create heatmap with empty data - causes errors
                if (this.heatmapPoints.length === 0) {{
                    console.log('No heatmap points available yet.');
                    return;
                }}

                // Sample points if too many (for performance)
                let points = this.heatmapPoints;
                const maxPoints = 50000;
                if (points.length > maxPoints) {{
                    const step = Math.ceil(points.length / maxPoints);
                    points = points.filter((_, i) => i % step === 0);
                }}

                // Create or update heatmap layer
                const heatData = points.map(p => [p[0], p[1], 1.0]);

                // Always create a fresh layer to avoid stale canvas issues
                if (this.heatmapLayer) {{
                    try {{
                        this.map.removeLayer(this.heatmapLayer);
                    }} catch (e) {{
                        // Layer may already be removed
                    }}
                    this.heatmapLayer = null;
                }}

                this.heatmapLayer = L.heatLayer(heatData, {{
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
                }}).addTo(this.map);

                // Update legend with point count
                this.updateLegendContent();
            }},

            addPointsToHeatmap(points) {{
                // Called when tracks are loaded to add points to heatmap data
                this.heatmapPoints = this.heatmapPoints.concat(points);

                // If heatmap is active, update it
                if (this.displayMode === 'heatmap' && this.heatmapLayer) {{
                    this.createOrShowHeatmap();
                    this.updateLegendContent();
                }}
            }}
        }};
        window.MapView = MapView;

        // ===== Sessions View Module =====
        const SessionsView = {{
            sessions: [],
            filtered: [],
            sortBy: 'datetime',
            sortDir: 'desc',
            filters: {{ search: '', type: '', dateFrom: '', dateTo: '' }},
            page: 1,
            perPage: 50,
            typeColors: {json.dumps(type_colors)},
            selectedSession: null,

            init() {{
                // Initialize filter bar using shared FilterBar component
                FilterBar.render('sessions-filter-bar', {{
                    showSearch: true,
                    showType: true,
                    showDatePresets: true,
                    showDates: true
                }});
                FilterBar.init('sessions-filter-bar');

                // Subscribe to FilterState changes
                FilterState.onChange(() => {{
                    this.page = 1;
                    this.applyFiltersAndRender();
                }});

                // Set up sortable headers
                document.querySelectorAll('#sessions-table th.sortable').forEach(th => {{
                    th.addEventListener('click', () => this.handleSort(th.dataset.sort));
                }});

                // Set up detail panel close
                document.getElementById('close-detail').addEventListener('click', () => {{
                    this.closeDetail();
                }});

                // Set up expand button to open full-screen view
                document.getElementById('expand-detail').addEventListener('click', () => {{
                    if (this.selectedSession) {{
                        const athlete = this.selectedSession.athlete;
                        const datetime = this.selectedSession.datetime;
                        location.hash = '#/session/' + athlete + '/' + datetime;
                    }}
                }});

                // Set up swipe-to-close on detail panel (mobile touch gesture)
                const detailPanel = document.getElementById('session-detail');
                let touchStartX = 0;
                let touchStartY = 0;
                detailPanel.addEventListener('touchstart', (e) => {{
                    touchStartX = e.touches[0].clientX;
                    touchStartY = e.touches[0].clientY;
                }}, {{ passive: true }});
                detailPanel.addEventListener('touchend', (e) => {{
                    const touchEndX = e.changedTouches[0].clientX;
                    const touchEndY = e.changedTouches[0].clientY;
                    const deltaX = touchEndX - touchStartX;
                    const deltaY = Math.abs(touchEndY - touchStartY);
                    // Close if swiped right by at least 80px and mostly horizontal
                    if (deltaX > 80 && deltaY < 50) {{
                        this.closeDetail();
                    }}
                }}, {{ passive: true }});

                // Listen for athlete changes
                document.getElementById('athlete-selector').addEventListener('change', () => {{
                    this.page = 1;
                    this.applyFiltersAndRender();
                }});
            }},

            setSessions(sessions) {{
                this.sessions = sessions;
                // Use shared FilterBar component for type population and state sync
                FilterBar.populateTypes('sessions-filter-bar', sessions);
                FilterBar.syncFromState('sessions-filter-bar');
                this.applyFiltersAndRender();
            }},

            applyFiltersAndRender() {{
                const currentAthlete = document.getElementById('athlete-selector').value;
                const filters = FilterState.get();

                // Use shared applyFilters function
                this.filtered = applyFilters(this.sessions, filters, currentAthlete);

                // Update filter count display
                FilterBar.updateCount('sessions-filter-bar', this.filtered.length, this.sessions.length);

                this.sort();
                this.render();
            }},

            // Alias for external calls (e.g., from stats chart clicks)
            applyFilters() {{
                this.applyFiltersAndRender();
            }},

            handleSort(field) {{
                if (this.sortBy === field) {{
                    this.sortDir = this.sortDir === 'desc' ? 'asc' : 'desc';
                }} else {{
                    this.sortBy = field;
                    this.sortDir = 'desc';
                }}

                // Update header styles
                document.querySelectorAll('#sessions-table th.sortable').forEach(th => {{
                    th.classList.remove('sorted-asc', 'sorted-desc');
                    if (th.dataset.sort === field) {{
                        th.classList.add(this.sortDir === 'asc' ? 'sorted-asc' : 'sorted-desc');
                    }}
                }});

                this.sort();
                this.render();
            }},

            sort() {{
                this.filtered.sort((a, b) => {{
                    let valA, valB;
                    switch (this.sortBy) {{
                        case 'datetime':
                            valA = a.datetime || '';
                            valB = b.datetime || '';
                            break;
                        case 'name':
                            valA = (a.name || '').toLowerCase();
                            valB = (b.name || '').toLowerCase();
                            break;
                        case 'type':
                            valA = a.type || '';
                            valB = b.type || '';
                            break;
                        case 'distance':
                            valA = parseFloat(a.distance_m) || 0;
                            valB = parseFloat(b.distance_m) || 0;
                            break;
                        case 'duration':
                            valA = parseInt(a.moving_time_s) || 0;
                            valB = parseInt(b.moving_time_s) || 0;
                            break;
                        default:
                            valA = a[this.sortBy] || '';
                            valB = b[this.sortBy] || '';
                    }}
                    const cmp = valA > valB ? 1 : valA < valB ? -1 : 0;
                    return this.sortDir === 'desc' ? -cmp : cmp;
                }});
            }},

            formatDuration(seconds) {{
                if (!seconds) return '-';
                const h = Math.floor(seconds / 3600);
                const m = Math.floor((seconds % 3600) / 60);
                if (h > 0) return `${{h}}h ${{m}}m`;
                return `${{m}}m`;
            }},

            formatDate(datetime) {{
                if (!datetime || datetime.length < 8) return '-';
                const y = datetime.substring(0, 4);
                const m = datetime.substring(4, 6);
                const d = datetime.substring(6, 8);
                return `${{y}}-${{m}}-${{d}}`;
            }},

            render() {{
                const tbody = document.getElementById('sessions-tbody');
                const start = (this.page - 1) * this.perPage;
                const end = start + this.perPage;
                const pageData = this.filtered.slice(start, end);

                if (pageData.length === 0) {{
                    const hasFilters = this.filters.search || this.filters.type || this.filters.dateFrom || this.filters.dateTo;
                    tbody.innerHTML = `<tr><td colspan="5">
                        <div class="empty-state">
                            <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 14c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H9V5h6v2z"/></svg>
                            <h3>No sessions found</h3>
                            <p>${{hasFilters ? 'Try adjusting your filters or search terms' : 'No activity data available yet'}}</p>
                            ${{hasFilters ? '<button class="clear-filters-btn" onclick="FilterState.clear(); FilterState.syncToURL();">Clear Filters</button>' : ''}}
                        </div>
                    </td></tr>`;
                }} else {{
                    tbody.innerHTML = pageData.map(s => {{
                        const color = this.typeColors[s.type] || this.typeColors.Other || '#607D8B';
                        const distance = parseFloat(s.distance_m) || 0;
                        const duration = parseInt(s.moving_time_s) || 0;
                        return `
                            <tr data-athlete="${{s.athlete}}" data-session="${{s.datetime}}">
                                <td>${{this.formatDate(s.datetime)}}</td>
                                <td>${{s.name || 'Activity'}}</td>
                                <td><span class="session-type" style="background:${{color}}20;color:${{color}}">${{s.type || 'Other'}}</span></td>
                                <td>${{(distance / 1000).toFixed(2)}} km</td>
                                <td>${{this.formatDuration(duration)}}</td>
                            </tr>
                        `;
                    }}).join('');

                    // Add click handlers
                    tbody.querySelectorAll('tr').forEach(tr => {{
                        tr.addEventListener('click', () => {{
                            const athlete = tr.dataset.athlete;
                            const session = tr.dataset.session;
                            this.showDetail(athlete, session);

                            // Update selection style
                            tbody.querySelectorAll('tr').forEach(r => r.classList.remove('selected'));
                            tr.classList.add('selected');
                        }});
                    }});
                }}

                this.renderPagination();
            }},

            renderPagination() {{
                const totalPages = Math.ceil(this.filtered.length / this.perPage);
                const pagination = document.getElementById('pagination');

                if (totalPages <= 1) {{
                    pagination.innerHTML = `<span class="page-info">${{this.filtered.length}} sessions</span>`;
                    return;
                }}

                pagination.innerHTML = `
                    <button ${{this.page <= 1 ? 'disabled' : ''}} id="prev-page">Previous</button>
                    <span class="page-info">Page ${{this.page}} of ${{totalPages}} (${{this.filtered.length}} sessions)</span>
                    <button ${{this.page >= totalPages ? 'disabled' : ''}} id="next-page">Next</button>
                `;

                document.getElementById('prev-page')?.addEventListener('click', () => {{
                    if (this.page > 1) {{
                        this.page--;
                        this.render();
                    }}
                }});

                document.getElementById('next-page')?.addEventListener('click', () => {{
                    if (this.page < totalPages) {{
                        this.page++;
                        this.render();
                    }}
                }});
            }},

            showDetail(athlete, sessionId) {{
                const session = this.sessions.find(s => s.athlete === athlete && s.datetime === sessionId);
                if (!session) return;

                this.selectedSession = session;
                const panel = document.getElementById('session-detail');
                panel.classList.remove('hidden');

                // Update URL with session permalink
                URLState.update({{ session: sessionId, athlete: athlete }});

                document.getElementById('detail-name').textContent = session.name || 'Activity';

                const distance = parseFloat(session.distance_m) || 0;
                const duration = parseInt(session.moving_time_s) || 0;
                const elevation = parseFloat(session.elevation_gain_m) || 0;

                document.getElementById('detail-meta').innerHTML = `
                    <div>${{session.type || 'Activity'}} · ${{this.formatDate(session.datetime)}}</div>
                    <div style="font-size:12px;color:#999;margin-top:4px;">Athlete: ${{athlete}}</div>
                `;

                document.getElementById('detail-stats').innerHTML = `
                    <div class="stat-card">
                        <div class="stat-value">${{(distance / 1000).toFixed(2)}}</div>
                        <div class="stat-label">km</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${{this.formatDuration(duration)}}</div>
                        <div class="stat-label">Duration</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${{elevation.toFixed(0)}}</div>
                        <div class="stat-label">m elevation</div>
                    </div>
                `;

                // Load track for mini-map
                this.loadDetailMap(athlete, sessionId);

                // Load photos if available
                const photoCount = parseInt(session.photo_count) || 0;
                if (photoCount > 0) {{
                    this.loadDetailPhotos(athlete, sessionId);
                }} else {{
                    document.getElementById('detail-photos').innerHTML = '';
                }}

                // Load social data (kudos, comments)
                this.loadDetailSocial(athlete, sessionId);

                // Load data streams (heart rate, cadence, etc.)
                this.loadDetailStreams(athlete, sessionId);

                // Check for shared runs (same datetime, different athlete)
                this.loadSharedRuns(athlete, sessionId);
            }},

            async loadSharedRuns(currentAthlete, sessionId) {{
                const container = document.getElementById('detail-shared');
                if (!container) return;
                container.innerHTML = '';

                // Find sessions from other athletes with the same datetime
                const sharedWith = [];
                for (const [athleteUsername, sessions] of Object.entries(MapView.sessionsByAthlete || {{}})) {{
                    if (athleteUsername === currentAthlete) continue;

                    const match = sessions.find(s => s.datetime === sessionId);
                    if (match) {{
                        sharedWith.push({{
                            username: athleteUsername,
                            session: match
                        }});
                    }}
                }}

                if (sharedWith.length === 0) return;

                container.innerHTML = `
                    <div class="shared-runs">
                        <strong>Also with:</strong>
                        ${{sharedWith.map(s => `
                            <a href="#" class="shared-athlete-link" data-athlete="${{s.username}}" data-session="${{s.session.datetime}}">
                                ${{s.username}}
                            </a>
                        `).join(', ')}}
                    </div>
                `;

                // Add click handlers for cross-athlete navigation
                container.querySelectorAll('.shared-athlete-link').forEach(link => {{
                    link.addEventListener('click', (e) => {{
                        e.preventDefault();
                        const athlete = e.target.dataset.athlete;
                        const sessionDt = e.target.dataset.session;

                        // Switch athlete and show their version of the session
                        const athleteSelect = document.getElementById('athlete-select');
                        athleteSelect.value = athlete;
                        athleteSelect.dispatchEvent(new Event('change'));

                        // After a short delay to allow filter update, show the session
                        setTimeout(() => {{
                            const session = MapView.sessionsByAthlete[athlete]?.find(s => s.datetime === sessionDt);
                            if (session) {{
                                this.showDetail(session, athlete);
                            }}
                        }}, 200);
                    }});
                }});
            }},

            detailMapInstance: null,

            async loadDetailMap(athlete, sessionId) {{
                const mapContainer = document.getElementById('detail-map');

                // Destroy previous map instance if exists
                if (this.detailMapInstance) {{
                    this.detailMapInstance.remove();
                    this.detailMapInstance = null;
                }}

                // Remove any existing "View on Map" button
                document.querySelectorAll('.view-on-map-btn').forEach(btn => btn.remove());

                mapContainer.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#666;">Loading track...</div>';

                try {{
                    const url = `athl=${{athlete}}/ses=${{sessionId}}/tracking.parquet`;
                    const response = await fetch(url);
                    if (!response.ok) {{
                        // Hide container if no track data
                        mapContainer.style.display = 'none';
                        return;
                    }}

                    const arrayBuffer = await response.arrayBuffer();
                    const {{ parquetReadObjects }} = await import('./assets/hyparquet/index.js');
                    const rows = await parquetReadObjects({{ file: arrayBuffer, columns: ['lat', 'lng'] }});

                    const coords = rows ? rows.filter(r => r.lat && r.lng).map(r => [r.lat, r.lng]) : [];

                    if (coords.length > 0) {{
                        mapContainer.style.display = 'block';
                        mapContainer.innerHTML = '';
                        this.detailMapInstance = L.map(mapContainer, {{ zoomControl: false, attributionControl: false }});
                        L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(this.detailMapInstance);

                        const session = this.selectedSession;
                        const color = this.typeColors[session?.type] || '#fc4c02';
                        const polyline = L.polyline(coords, {{ color, weight: 3 }}).addTo(this.detailMapInstance);
                        this.detailMapInstance.fitBounds(polyline.getBounds(), {{ padding: [10, 10] }});

                        // Add "View on Map" button with proper navigation
                        const lat = coords[0][0];
                        const lng = coords[0][1];
                        const btn = document.createElement('button');
                        btn.className = 'view-on-map-btn';
                        btn.textContent = 'View on Map';
                        btn.onclick = () => {{
                            location.hash = '#/map';
                            setTimeout(() => {{
                                if (window.mapInstance) {{
                                    window.mapInstance.setView([lat, lng], 14);
                                }}
                            }}, 200);
                        }};
                        mapContainer.insertAdjacentElement('afterend', btn);
                    }} else {{
                        // Hide container if no GPS coords
                        mapContainer.style.display = 'none';
                    }}
                }} catch (e) {{
                    console.warn('Failed to load detail map:', e);
                    mapContainer.style.display = 'none';
                }}
            }},

            async loadDetailPhotos(athlete, sessionId) {{
                const container = document.getElementById('detail-photos');
                container.innerHTML = '<div style="color:#666;">Loading photos...</div>';

                try {{
                    const response = await fetch(`athl=${{athlete}}/ses=${{sessionId}}/info.json`);
                    if (!response.ok) {{
                        container.innerHTML = '';
                        return;
                    }}

                    const info = await response.json();
                    const photos = info.photos || [];

                    if (photos.length === 0) {{
                        container.innerHTML = '';
                        return;
                    }}

                    container.innerHTML = photos.map(photo => {{
                        const urls = photo.urls || {{}};
                        const thumbUrl = urls['256'] || urls['600'] || Object.values(urls)[0] || '';
                        const fullUrl = urls['2048'] || urls['1024'] || urls['600'] || thumbUrl;

                        // Try local path
                        const createdAt = photo.created_at || '';
                        let localPath = '';
                        if (createdAt) {{
                            const dt = createdAt.replace(/[-:]/g, '').replace(/\\+.*$/, '').substring(0, 15);
                            localPath = `athl=${{athlete}}/ses=${{sessionId}}/photos/${{dt}}.jpg`;
                        }}

                        const src = localPath || thumbUrl;
                        const href = localPath || fullUrl;

                        return src ? `<a href="${{href}}" target="_blank"><img src="${{src}}" alt="Photo"></a>` : '';
                    }}).join('');
                }} catch (e) {{
                    console.warn('Failed to load detail photos:', e);
                    container.innerHTML = '';
                }}
            }},

            async loadDetailSocial(athlete, sessionId) {{
                const container = document.getElementById('detail-social');
                container.innerHTML = '';

                try {{
                    const response = await fetch(`athl=${{athlete}}/ses=${{sessionId}}/info.json`);
                    if (!response.ok) return;

                    const info = await response.json();
                    const kudos = info.kudos || [];
                    const comments = info.comments || [];

                    if (kudos.length === 0 && comments.length === 0) return;

                    let html = '';

                    if (kudos.length > 0) {{
                        html += '<h4>Kudos (' + kudos.length + ')</h4>';
                        html += '<div class="kudos-list">';
                        html += kudos.map(k => `<span class="kudos-item">${{k.firstname || ''}} ${{k.lastname || ''}}</span>`).join('');
                        html += '</div>';
                    }}

                    if (comments.length > 0) {{
                        html += '<h4>Comments (' + comments.length + ')</h4>';
                        html += '<div class="comments-list">';
                        html += comments.map(c => `
                            <div class="comment-item">
                                <div class="comment-author">${{c.firstname || ''}} ${{c.lastname || ''}}</div>
                                <div class="comment-text">${{c.text || ''}}</div>
                            </div>
                        `).join('');
                        html += '</div>';
                    }}

                    container.innerHTML = html;
                }} catch (e) {{
                    console.warn('Failed to load social data:', e);
                }}
            }},

            async loadDetailStreams(athlete, sessionId) {{
                const container = document.getElementById('detail-streams');
                container.innerHTML = '';

                try {{
                    const url = `athl=${{athlete}}/ses=${{sessionId}}/tracking.parquet`;
                    const response = await fetch(url);
                    if (!response.ok) return;

                    const arrayBuffer = await response.arrayBuffer();
                    const {{ parquetReadObjects }} = await import('./assets/hyparquet/index.js');

                    // Try to get all available columns
                    const rows = await parquetReadObjects({{ file: arrayBuffer }});
                    if (!rows || rows.length === 0) return;

                    // Detect available streams from first row
                    const sampleRow = rows[0];
                    const streamConfigs = [
                        {{ key: 'hr', label: 'Heart Rate', unit: 'bpm' }},
                        {{ key: 'heartrate', label: 'Heart Rate', unit: 'bpm' }},
                        {{ key: 'cadence', label: 'Cadence', unit: 'rpm' }},
                        {{ key: 'watts', label: 'Power', unit: 'W' }},
                        {{ key: 'power', label: 'Power', unit: 'W' }},
                        {{ key: 'temp', label: 'Temperature', unit: '°C' }},
                        {{ key: 'temperature', label: 'Temperature', unit: '°C' }},
                        {{ key: 'altitude', label: 'Elevation', unit: 'm' }},
                        {{ key: 'ele', label: 'Elevation', unit: 'm' }}
                    ];

                    const availableStreams = [];
                    for (const config of streamConfigs) {{
                        if (sampleRow[config.key] !== undefined && sampleRow[config.key] !== null) {{
                            // Check if we already have this type of stream
                            const existingType = availableStreams.find(s => s.label === config.label);
                            if (!existingType) {{
                                availableStreams.push(config);
                            }}
                        }}
                    }}

                    if (availableStreams.length === 0) return;

                    // Calculate stats for each stream
                    const streamStats = [];
                    for (const config of availableStreams) {{
                        const values = rows.map(r => parseFloat(r[config.key])).filter(v => !isNaN(v) && v > 0);
                        if (values.length === 0) continue;

                        const avg = values.reduce((a, b) => a + b, 0) / values.length;
                        const max = Math.max(...values);
                        const min = Math.min(...values);

                        streamStats.push({{
                            label: config.label,
                            unit: config.unit,
                            avg: avg.toFixed(config.key === 'altitude' || config.key === 'ele' ? 0 : 0),
                            max: max.toFixed(0),
                            min: min.toFixed(0)
                        }});
                    }}

                    if (streamStats.length === 0) return;

                    // Render streams
                    let html = '<h4>Data Streams</h4><div class="streams-grid">';
                    for (const stream of streamStats) {{
                        html += `
                            <div class="stream-card">
                                <div class="stream-label">${{stream.label}}</div>
                                <div class="stream-values">
                                    <div class="stream-stat">
                                        <span class="stream-stat-label">Avg</span>
                                        <span class="stream-stat-value">${{stream.avg}} ${{stream.unit}}</span>
                                    </div>
                                    <div class="stream-stat">
                                        <span class="stream-stat-label">Max</span>
                                        <span class="stream-stat-value">${{stream.max}} ${{stream.unit}}</span>
                                    </div>
                                </div>
                            </div>
                        `;
                    }}
                    html += '</div>';
                    container.innerHTML = html;
                }} catch (e) {{
                    console.warn('Failed to load data streams:', e);
                }}
            }},

            closeDetail() {{
                document.getElementById('session-detail').classList.add('hidden');
                document.querySelectorAll('#sessions-tbody tr').forEach(r => r.classList.remove('selected'));
                this.selectedSession = null;

                // Clear session from URL
                URLState.update({{ session: '' }});

                // Clean up detail map instance
                if (this.detailMapInstance) {{
                    this.detailMapInstance.remove();
                    this.detailMapInstance = null;
                }}

                // Remove any "View on Map" button that was added
                document.querySelectorAll('.view-on-map-btn').forEach(btn => btn.remove());

                // Reset map container visibility for next session
                document.getElementById('detail-map').style.display = 'block';
            }}
        }};

        // ===== Full Session View Module =====
        const FullSessionView = {{
            map: null,
            currentAthlete: null,
            currentSession: null,
            retryCount: 0,
            maxRetries: 10,

            show(athlete, datetime) {{
                this.currentAthlete = athlete;
                this.currentSession = datetime;

                // Find session data
                const sessions = MapView.sessionsByAthlete?.[athlete] || [];
                const session = sessions.find(s => s.datetime === datetime);

                if (!session) {{
                    // Data might not be loaded yet, retry with limit
                    this.retryCount++;
                    if (this.retryCount <= this.maxRetries) {{
                        console.log('Session data not loaded yet, retrying... (' + this.retryCount + '/' + this.maxRetries + ')');
                        document.getElementById('full-session-name').textContent = 'Loading...';
                        document.getElementById('full-session-meta').textContent = 'Please wait while data loads';
                        setTimeout(() => this.show(athlete, datetime), 500);
                        return;
                    }} else {{
                        console.warn('Session not found after retries:', athlete, datetime);
                        document.getElementById('full-session-name').textContent = 'Session Not Found';
                        document.getElementById('full-session-meta').textContent = `Could not find session ${{datetime}} for ${{athlete}}`;
                        this.retryCount = 0;
                        return;
                    }}
                }}

                // Reset retry count on success
                this.retryCount = 0;

                // Update header
                document.getElementById('full-session-name').textContent = session.name || 'Activity';
                const dateStr = this.formatDate(datetime);
                document.getElementById('full-session-meta').innerHTML =
                    `${{dateStr}} &bull; ${{session.type || 'Activity'}} &bull; ${{athlete}}`;

                // Update share button with error handling and visual feedback
                const shareBtn = document.getElementById('full-session-share');
                shareBtn.onclick = async () => {{
                    const url = location.origin + location.pathname + '#/session/' + athlete + '/' + datetime;
                    try {{
                        await navigator.clipboard.writeText(url);
                        // Visual feedback - green checkmark
                        shareBtn.classList.add('copied');
                        shareBtn.title = 'Link copied!';
                        setTimeout(() => {{
                            shareBtn.classList.remove('copied');
                            shareBtn.title = 'Copy permalink';
                        }}, 2000);
                    }} catch (err) {{
                        // Fallback for browsers without clipboard API or insecure contexts
                        console.warn('Clipboard API failed, using fallback:', err);
                        // Create temporary input for copying
                        const input = document.createElement('input');
                        input.value = url;
                        document.body.appendChild(input);
                        input.select();
                        try {{
                            document.execCommand('copy');
                            shareBtn.classList.add('copied');
                            shareBtn.title = 'Link copied!';
                            setTimeout(() => {{
                                shareBtn.classList.remove('copied');
                                shareBtn.title = 'Copy permalink';
                            }}, 2000);
                        }} catch (e) {{
                            // Show URL in alert as last resort
                            alert('Copy this link:\\n' + url);
                        }}
                        document.body.removeChild(input);
                    }}
                }};

                // Update "View on Map" button
                const mapBtn = document.getElementById('full-session-map-btn');
                mapBtn.onclick = () => {{
                    // Navigate to map view centered on this session
                    const lat = parseFloat(session.start_lat);
                    const lng = parseFloat(session.start_lng);
                    if (!isNaN(lat) && !isNaN(lng)) {{
                        location.hash = `#/map?z=14&lat=${{lat}}&lng=${{lng}}`;
                    }} else {{
                        location.hash = '#/map';
                    }}
                }};

                // Render stats
                this.renderStats(session);

                // Load map
                this.loadMap(athlete, datetime);

                // Load streams (placeholder for Phase 8)
                this.loadStreams(athlete, datetime);

                // Load photos
                this.loadPhotos(athlete, datetime, session);

                // Load social
                this.loadSocial(athlete, datetime);

                // Load shared runs
                this.loadSharedRuns(athlete, datetime);
            }},

            formatDate(datetime) {{
                if (!datetime || datetime.length < 8) return '';
                const y = datetime.substring(0, 4);
                const m = datetime.substring(4, 6);
                const d = datetime.substring(6, 8);
                return `${{y}}-${{m}}-${{d}}`;
            }},

            formatDuration(seconds) {{
                if (!seconds) return '-';
                const h = Math.floor(seconds / 3600);
                const m = Math.floor((seconds % 3600) / 60);
                if (h > 0) return `${{h}}h ${{m}}m`;
                return `${{m}}m`;
            }},

            renderStats(session) {{
                const distance = parseFloat(session.distance_m) || 0;
                const duration = parseInt(session.moving_time_s) || 0;
                const elevation = parseFloat(session.elevation_gain_m) || 0;
                const avgHr = parseFloat(session.average_heartrate) || 0;
                const avgCadence = parseFloat(session.average_cadence) || 0;

                let html = `
                    <div class="stat-card">
                        <div class="stat-value">${{(distance / 1000).toFixed(2)}}</div>
                        <div class="stat-label">km</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${{this.formatDuration(duration)}}</div>
                        <div class="stat-label">Duration</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${{elevation.toFixed(0)}}</div>
                        <div class="stat-label">m elevation</div>
                    </div>
                `;

                if (avgHr > 0) {{
                    html += `
                        <div class="stat-card">
                            <div class="stat-value">${{avgHr.toFixed(0)}}</div>
                            <div class="stat-label">avg HR</div>
                        </div>
                    `;
                }}

                if (avgCadence > 0) {{
                    html += `
                        <div class="stat-card">
                            <div class="stat-value">${{avgCadence.toFixed(0)}}</div>
                            <div class="stat-label">avg cadence</div>
                        </div>
                    `;
                }}

                document.getElementById('full-session-stats').innerHTML = html;
            }},

            async loadMap(athlete, datetime) {{
                const container = document.getElementById('full-session-map-container');
                container.innerHTML = '';

                // Clean up previous map
                if (this.map) {{
                    this.map.remove();
                    this.map = null;
                }}

                // Create map
                this.map = L.map(container).setView([40, 0], 3);
                L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19,
                    attribution: '&copy; OpenStreetMap'
                }}).addTo(this.map);

                // Load track
                try {{
                    const response = await fetch(`athl=${{athlete}}/ses=${{datetime}}/tracking.parquet`);
                    if (!response.ok) return;
                    const buffer = await response.arrayBuffer();
                    const data = await parquetReadObjects({{ file: buffer }});

                    const coords = data
                        .filter(row => row.lat && row.lng)
                        .map(row => [row.lat, row.lng]);

                    if (coords.length > 0) {{
                        const polyline = L.polyline(coords, {{
                            color: MapView.typeColors[this.currentSession?.type] || '#fc4c02',
                            weight: 3
                        }}).addTo(this.map);
                        this.map.fitBounds(polyline.getBounds(), {{ padding: [20, 20] }});
                    }}
                }} catch (e) {{
                    console.warn('Could not load track:', e);
                }}
            }},

            streamCharts: [],  // Track Chart.js instances for cleanup

            // Downsample data for performance (max 500 points for display)
            downsampleData(data, maxPoints = 500) {{
                if (data.length <= maxPoints) return data;
                const step = Math.ceil(data.length / maxPoints);
                return data.filter((_, i) => i % step === 0);
            }},

            async loadStreams(athlete, datetime) {{
                const container = document.getElementById('full-session-streams');

                // Destroy existing charts
                this.streamCharts.forEach(chart => chart.destroy());
                this.streamCharts = [];

                try {{
                    const response = await fetch(`athl=${{athlete}}/ses=${{datetime}}/tracking.parquet`);
                    if (!response.ok) {{
                        container.innerHTML = '';
                        return;
                    }}
                    const buffer = await response.arrayBuffer();
                    const data = await parquetReadObjects({{ file: buffer }});

                    if (!data || data.length === 0) {{
                        container.innerHTML = '';
                        return;
                    }}

                    // Check what streams are available
                    const hasHr = data.some(r => r.heartrate);
                    const hasCadence = data.some(r => r.cadence);
                    const hasWatts = data.some(r => r.watts);
                    const hasElevation = data.some(r => r.altitude);
                    const hasSpeed = data.some(r => r.velocity_smooth);

                    if (!hasHr && !hasCadence && !hasWatts && !hasElevation) {{
                        container.innerHTML = '';
                        return;
                    }}

                    // Downsample for performance
                    const sampled = this.downsampleData(data);

                    // Check what X-axis options are available
                    const hasDistance = sampled.some(r => r.distance);
                    const hasTime = sampled.some(r => r.time !== undefined);

                    // Store data for re-rendering when X-axis changes
                    this.streamData = {{ sampled, hasElevation, hasHr, hasCadence, hasWatts, hasDistance, hasTime }};

                    // Build HTML with X-axis selector
                    let html = '<div class="stream-header">';
                    html += '<h3 class="full-session-section-title">Data Streams</h3>';
                    if (hasDistance && hasTime) {{
                        html += `<select id="xaxis-selector" class="xaxis-select">
                            <option value="distance">Distance (km)</option>
                            <option value="time">Time (min)</option>
                        </select>`;
                    }}
                    html += '</div>';
                    html += '<div class="stream-charts">';

                    // Elevation chart (area fill, always first if available)
                    if (hasElevation) {{
                        html += `
                            <div class="stream-chart-container elevation-chart">
                                <span class="stream-chart-label">Elevation</span>
                                <canvas id="elevation-chart" class="stream-chart-canvas"></canvas>
                            </div>
                        `;
                    }}

                    // Combined HR/Cadence/Power chart
                    if (hasHr || hasCadence || hasWatts) {{
                        html += `
                            <div class="stream-chart-container">
                                <span class="stream-chart-label">Activity Data</span>
                                <canvas id="activity-chart" class="stream-chart-canvas"></canvas>
                            </div>
                        `;
                    }}

                    html += '</div>';
                    container.innerHTML = html;

                    // Set up X-axis selector change handler
                    const xaxisSelector = document.getElementById('xaxis-selector');
                    if (xaxisSelector) {{
                        xaxisSelector.addEventListener('change', () => this.renderStreamCharts());
                    }}

                    // Render charts
                    this.renderStreamCharts();

                }} catch (e) {{
                    console.warn('Could not load streams:', e);
                    container.innerHTML = '';
                }}
            }},

            xAxisMode: 'distance',  // Default mode

            renderStreamCharts() {{
                if (!this.streamData) return;
                const {{ sampled, hasElevation, hasHr, hasCadence, hasWatts, hasDistance, hasTime }} = this.streamData;

                // Destroy existing charts
                this.streamCharts.forEach(chart => chart.destroy());
                this.streamCharts = [];

                // Determine X-axis mode
                const selector = document.getElementById('xaxis-selector');
                const useDistance = selector ? selector.value === 'distance' : hasDistance;

                // Calculate X-axis data
                const xData = sampled.map(r => {{
                    if (useDistance && r.distance) return Math.round(r.distance / 100) / 10;  // km, 1 decimal
                    return Math.round((r.time || 0) / 60);  // minutes, whole numbers
                }});
                const xLabel = useDistance ? 'Distance (km)' : 'Time (min)';

                // Create elevation chart
                if (hasElevation) {{
                        const elevData = sampled.map(r => r.altitude);
                        const minElev = Math.min(...elevData.filter(e => e != null));
                        const maxElev = Math.max(...elevData.filter(e => e != null));

                        const elevChart = new Chart(document.getElementById('elevation-chart'), {{
                            type: 'line',
                            data: {{
                                labels: xData,
                                datasets: [{{
                                    label: 'Elevation',
                                    data: elevData,
                                    borderColor: '#888',
                                    backgroundColor: 'rgba(100, 100, 100, 0.2)',
                                    fill: true,
                                    tension: 0.3,
                                    borderWidth: 1,
                                    pointRadius: 0,
                                }}]
                            }},
                            options: {{
                                responsive: true,
                                maintainAspectRatio: false,
                                interaction: {{
                                    mode: 'index',
                                    intersect: false
                                }},
                                plugins: {{
                                    legend: {{ display: false }},
                                    tooltip: {{
                                        callbacks: {{
                                            title: (items) => `${{items[0].parsed.x.toFixed(1)}} ${{useDistance ? 'km' : 'min'}}`,
                                            label: (item) => `${{item.parsed.y.toFixed(0)}} m`
                                        }}
                                    }}
                                }},
                                scales: {{
                                    x: {{
                                        display: true,
                                        title: {{ display: false }},
                                        ticks: {{ font: {{ size: 10 }}, maxTicksLimit: 8 }}
                                    }},
                                    y: {{
                                        display: true,
                                        min: Math.floor(minElev * 0.95),
                                        max: Math.ceil(maxElev * 1.05),
                                        ticks: {{ font: {{ size: 10 }} }},
                                        title: {{ display: true, text: 'm', font: {{ size: 10 }} }}
                                    }}
                                }}
                            }}
                        }});
                        this.streamCharts.push(elevChart);
                    }}

                    // Create combined activity data chart
                    if (hasHr || hasCadence || hasWatts) {{
                        const datasets = [];

                        if (hasHr) {{
                            // Filter out initial 0 HR readings (common sensor artifact)
                            const hrData = sampled.map((r, i) => {{
                                // Skip first point if HR is 0 or very low (sensor warming up)
                                if (i === 0 && (!r.heartrate || r.heartrate < 30)) return null;
                                return r.heartrate || null;
                            }});
                            datasets.push({{
                                label: 'Heart Rate',
                                data: hrData,
                                borderColor: '#e63946',
                                backgroundColor: 'rgba(230, 57, 70, 0.1)',
                                fill: false,
                                tension: 0.3,
                                borderWidth: 2,
                                pointRadius: 0,
                                yAxisID: 'yHr',
                                spanGaps: true  // Connect line across null gaps
                            }});
                        }}

                        if (hasCadence) {{
                            datasets.push({{
                                label: 'Cadence',
                                data: sampled.map(r => r.cadence),
                                borderColor: '#457b9d',
                                backgroundColor: 'rgba(69, 123, 157, 0.1)',
                                fill: false,
                                tension: 0.3,
                                borderWidth: 2,
                                pointRadius: 0,
                                yAxisID: 'yCadence'
                            }});
                        }}

                        if (hasWatts) {{
                            datasets.push({{
                                label: 'Power',
                                data: sampled.map(r => r.watts),
                                borderColor: '#f4a261',
                                backgroundColor: 'rgba(244, 162, 97, 0.1)',
                                fill: false,
                                tension: 0.3,
                                borderWidth: 2,
                                pointRadius: 0,
                                yAxisID: 'yPower'
                            }});
                        }}

                        // Configure scales based on available data
                        const scales = {{
                            x: {{
                                display: true,
                                title: {{ display: true, text: xLabel, font: {{ size: 10 }} }},
                                ticks: {{ font: {{ size: 10 }}, maxTicksLimit: 8 }}
                            }}
                        }};

                        if (hasHr) {{
                            scales.yHr = {{
                                type: 'linear',
                                position: 'left',
                                display: true,
                                title: {{ display: true, text: 'BPM', font: {{ size: 10 }}, color: '#e63946' }},
                                ticks: {{ font: {{ size: 10 }}, color: '#e63946' }},
                                grid: {{ display: hasHr && !hasCadence && !hasWatts }}
                            }};
                        }}

                        if (hasCadence) {{
                            scales.yCadence = {{
                                type: 'linear',
                                position: hasHr ? 'right' : 'left',
                                display: true,
                                title: {{ display: true, text: 'RPM', font: {{ size: 10 }}, color: '#457b9d' }},
                                ticks: {{ font: {{ size: 10 }}, color: '#457b9d' }},
                                grid: {{ display: !hasHr }}
                            }};
                        }}

                        if (hasWatts) {{
                            scales.yPower = {{
                                type: 'linear',
                                position: 'right',
                                display: true,
                                title: {{ display: true, text: 'W', font: {{ size: 10 }}, color: '#f4a261' }},
                                ticks: {{ font: {{ size: 10 }}, color: '#f4a261' }},
                                grid: {{ display: false }}
                            }};
                        }}

                        const activityChart = new Chart(document.getElementById('activity-chart'), {{
                            type: 'line',
                            data: {{
                                labels: xData,
                                datasets: datasets
                            }},
                            options: {{
                                responsive: true,
                                maintainAspectRatio: false,
                                interaction: {{
                                    mode: 'index',
                                    intersect: false
                                }},
                                plugins: {{
                                    legend: {{
                                        display: true,
                                        position: 'top',
                                        labels: {{ font: {{ size: 11 }}, usePointStyle: true, boxWidth: 6 }}
                                    }},
                                    tooltip: {{
                                        callbacks: {{
                                            title: (items) => `${{items[0].parsed.x.toFixed(1)}} ${{useDistance ? 'km' : 'min'}}`
                                        }}
                                    }}
                                }},
                                scales: scales
                            }}
                        }});
                        this.streamCharts.push(activityChart);
                    }}
            }},

            loadPhotos(athlete, datetime, session) {{
                const container = document.getElementById('full-session-photos');
                const photoCount = parseInt(session?.photo_count) || 0;

                if (photoCount === 0) {{
                    container.innerHTML = '';
                    return;
                }}

                container.innerHTML = `
                    <h3 class="full-session-section-title">Photos (${{photoCount}})</h3>
                    <div class="photo-grid" id="full-session-photo-grid"></div>
                `;

                // Load photos from directory
                fetch(`athl=${{athlete}}/ses=${{datetime}}/photos/`)
                    .then(response => response.text())
                    .then(html => {{
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(html, 'text/html');
                        const links = [...doc.querySelectorAll('a')];
                        const photoFiles = links
                            .map(a => a.getAttribute('href'))
                            .filter(href => href && /\\.(jpg|jpeg|png|gif)$/i.test(href));

                        const grid = document.getElementById('full-session-photo-grid');
                        grid.innerHTML = photoFiles.map(file => `
                            <div class="photo-item">
                                <img src="athl=${{athlete}}/ses=${{datetime}}/photos/${{file}}"
                                     onclick="window.open(this.src, '_blank')"
                                     alt="Activity photo">
                            </div>
                        `).join('');
                    }})
                    .catch(() => {{ container.innerHTML = ''; }});
            }},

            loadSocial(athlete, datetime) {{
                const container = document.getElementById('full-session-social');

                fetch(`athl=${{athlete}}/ses=${{datetime}}/info.json`)
                    .then(response => response.json())
                    .then(info => {{
                        const kudos = info.kudos || [];
                        const comments = info.comments || [];

                        if (kudos.length === 0 && comments.length === 0) {{
                            container.innerHTML = '';
                            return;
                        }}

                        let html = '<h3 class="full-session-section-title">Social</h3>';

                        if (kudos.length > 0) {{
                            html += `<div style="margin-bottom:16px;">
                                <strong>👍 ${{kudos.length}} kudos</strong>
                                <span style="color:#666;font-size:13px;margin-left:8px;">
                                    ${{kudos.slice(0, 5).map(k => k.firstname || 'Someone').join(', ')}}
                                    ${{kudos.length > 5 ? ` and ${{kudos.length - 5}} more` : ''}}
                                </span>
                            </div>`;
                        }}

                        if (comments.length > 0) {{
                            html += `<div>
                                <strong>💬 ${{comments.length}} comments</strong>
                                ${{comments.map(c => `
                                    <div style="margin-top:8px;padding:8px;background:#f5f5f5;border-radius:6px;">
                                        <strong style="font-size:13px;">${{c.athlete_firstname || 'Someone'}}</strong>
                                        <p style="margin:4px 0 0 0;font-size:14px;">${{c.text || ''}}</p>
                                    </div>
                                `).join('')}}
                            </div>`;
                        }}

                        container.innerHTML = html;
                    }})
                    .catch(() => {{ container.innerHTML = ''; }});
            }},

            loadSharedRuns(athlete, datetime) {{
                const container = document.getElementById('full-session-shared');
                container.innerHTML = '';

                const sharedWith = [];
                for (const [athleteUsername, sessions] of Object.entries(MapView.sessionsByAthlete || {{}})) {{
                    if (athleteUsername === athlete) continue;
                    const match = sessions.find(s => s.datetime === datetime);
                    if (match) {{
                        sharedWith.push({{ username: athleteUsername, session: match }});
                    }}
                }}

                if (sharedWith.length === 0) return;

                container.innerHTML = `
                    <h3 class="full-session-section-title">Shared Activity</h3>
                    <p style="color:#666;">
                        Also recorded by:
                        ${{sharedWith.map(s => `
                            <a href="#/session/${{s.username}}/${{datetime}}"
                               style="color:#fc4c02;font-weight:600;">${{s.username}}</a>
                        `).join(', ')}}
                    </p>
                `;
            }}
        }};

        // ===== Stats View Module =====
        const StatsView = {{
            sessions: [],
            filtered: [],
            typeColors: {json.dumps(type_colors)},
            monthlyChart: null,  // Chart.js instance
            typeChart: null,     // Chart.js instance

            init() {{
                // Initialize filter bar for stats
                FilterBar.render('stats-filter-bar', {{
                    showSearch: true,
                    showType: true,
                    showDatePresets: true,
                    showDates: true
                }});
                FilterBar.init('stats-filter-bar');

                // Initialize session list panel for stats
                SessionListPanel.render('stats-session-list', {{
                    onSessionClick: (athlete, datetime) => {{
                        location.hash = `#/session/${{athlete}}/${{datetime}}`;
                    }}
                }});

                // Subscribe to filter changes
                FilterState.onChange(() => this.calculate());

                // Listen for athlete changes
                document.getElementById('athlete-selector').addEventListener('change', () => {{
                    this.calculate();
                }});
                // Chart click handlers are set up in renderMonthlyChart/renderTypeChart
            }},

            handleMonthlyChartClick(month) {{
                // Navigate to sessions view with month filter via URL
                const [year, monthNum] = [month.substring(0, 4), month.substring(4, 6)];
                const dateFrom = `${{year}}-${{monthNum}}-01`;
                const lastDay = new Date(parseInt(year), parseInt(monthNum), 0).getDate();
                const dateTo = `${{year}}-${{monthNum}}-${{String(lastDay).padStart(2, '0')}}`;

                // Build URL with date filter params
                const params = new URLSearchParams();
                params.set('from', dateFrom);
                params.set('to', dateTo);
                // Preserve current athlete
                const athlete = document.getElementById('athlete-selector')?.value;
                if (athlete) params.set('a', athlete);

                location.hash = `#/sessions?${{params.toString()}}`;
            }},

            handleTypeChartClick(type) {{
                // Navigate to sessions view with type filter via URL
                const params = new URLSearchParams();
                params.set('t', type);
                // Preserve current athlete
                const athlete = document.getElementById('athlete-selector')?.value;
                if (athlete) params.set('a', athlete);

                location.hash = `#/sessions?${{params.toString()}}`;
            }},

            setSessions(sessions) {{
                this.sessions = sessions;
                this.calculate();
            }},

            calculate() {{
                const currentAthlete = document.getElementById('athlete-selector').value;
                const filters = FilterState.get();

                // Use shared applyFilters function
                const filtered = applyFilters(this.sessions, filters, currentAthlete);
                this.filtered = filtered;

                // Update session list panel
                const sortedFiltered = [...filtered].sort((a, b) => (b.datetime || '').localeCompare(a.datetime || ''));
                SessionListPanel.setSessions(sortedFiltered);
                FilterBar.updateCount('stats-filter-bar', filtered.length, this.sessions.length);

                // Calculate totals
                const totals = {{
                    sessions: filtered.length,
                    distance: filtered.reduce((sum, s) => sum + parseFloat(s.distance_m || 0), 0),
                    time: filtered.reduce((sum, s) => sum + parseInt(s.moving_time_s || 0), 0),
                    elevation: filtered.reduce((sum, s) => sum + parseFloat(s.elevation_gain_m || 0), 0)
                }};

                // Group by month
                const byMonth = {{}};
                for (const s of filtered) {{
                    if (!s.datetime || s.datetime.length < 6) continue;
                    const month = s.datetime.substring(0, 6);
                    if (!byMonth[month]) byMonth[month] = {{ count: 0, distance: 0 }};
                    byMonth[month].count++;
                    byMonth[month].distance += parseFloat(s.distance_m || 0);
                }}

                // Group by type
                const byType = {{}};
                for (const s of filtered) {{
                    const type = s.type || 'Other';
                    if (!byType[type]) byType[type] = {{ count: 0, distance: 0 }};
                    byType[type].count++;
                    byType[type].distance += parseFloat(s.distance_m || 0);
                }}

                this.renderSummary(totals);
                this.renderMonthlyChart(byMonth);
                this.renderTypeChart(byType);
            }},

            formatDuration(seconds) {{
                const h = Math.floor(seconds / 3600);
                const m = Math.floor((seconds % 3600) / 60);
                if (h >= 24) {{
                    const d = Math.floor(h / 24);
                    return `${{d}}d ${{h % 24}}h`;
                }}
                return `${{h}}h ${{m}}m`;
            }},

            renderSummary(totals) {{
                document.getElementById('total-sessions').textContent = totals.sessions.toLocaleString();
                document.getElementById('total-distance').textContent = (totals.distance / 1000).toFixed(0) + ' km';
                document.getElementById('total-time').textContent = this.formatDuration(totals.time);
                document.getElementById('total-elevation').textContent = totals.elevation.toFixed(0) + ' m';
            }},

            renderMonthlyChart(byMonth) {{
                const canvas = document.getElementById('monthly-chart');
                const months = Object.keys(byMonth).sort();

                // Destroy existing chart if any
                if (this.monthlyChart) {{
                    this.monthlyChart.destroy();
                    this.monthlyChart = null;
                }}

                if (!canvas) return; // Canvas may have been removed

                // Remove any existing "no data" message
                const existingMsg = canvas.parentElement.querySelector('.no-data-message');
                if (existingMsg) existingMsg.remove();

                if (months.length === 0) {{
                    canvas.style.display = 'none';
                    const msg = document.createElement('div');
                    msg.className = 'no-data-message';
                    msg.style.cssText = 'text-align:center;padding:100px 0;color:#999;';
                    msg.textContent = 'No data available';
                    canvas.parentElement.appendChild(msg);
                    return;
                }}

                canvas.style.display = 'block';

                const labels = months.map(m => m.substring(0, 4) + '-' + m.substring(4, 6));
                const data = months.map(m => byMonth[m].count);
                const monthKeys = months; // Store for click handler

                this.monthlyChart = new Chart(canvas, {{
                    type: 'bar',
                    data: {{
                        labels: labels,
                        datasets: [{{
                            label: 'Sessions',
                            data: data,
                            backgroundColor: '#fc4c02',
                            borderRadius: 4,
                            borderSkipped: false
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ display: false }},
                            tooltip: {{
                                backgroundColor: 'rgba(0,0,0,0.8)',
                                titleFont: {{ size: 13 }},
                                bodyFont: {{ size: 12 }},
                                padding: 10,
                                cornerRadius: 6,
                                callbacks: {{
                                    title: (items) => items[0].label,
                                    label: (item) => `${{item.raw}} sessions`
                                }}
                            }}
                        }},
                        scales: {{
                            x: {{
                                grid: {{ display: false }},
                                ticks: {{
                                    maxRotation: 45,
                                    minRotation: 45,
                                    font: {{ size: 10 }}
                                }}
                            }},
                            y: {{
                                beginAtZero: true,
                                grid: {{ color: '#eee' }},
                                ticks: {{ stepSize: 1 }},
                                title: {{
                                    display: true,
                                    text: 'Sessions',
                                    font: {{ size: 12 }}
                                }}
                            }}
                        }},
                        onClick: (event, elements) => {{
                            if (elements.length > 0) {{
                                const index = elements[0].index;
                                this.handleMonthlyChartClick(monthKeys[index]);
                            }}
                        }},
                        onHover: (event, elements) => {{
                            canvas.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                        }}
                    }}
                }});
            }},

            renderTypeChart(byType) {{
                const canvas = document.getElementById('type-chart');
                const types = Object.keys(byType).sort((a, b) => byType[b].count - byType[a].count);

                // Destroy existing chart if any
                if (this.typeChart) {{
                    this.typeChart.destroy();
                    this.typeChart = null;
                }}

                if (!canvas) return; // Canvas may have been removed

                // Remove any existing "no data" message
                const existingMsg = canvas.parentElement.querySelector('.no-data-message');
                if (existingMsg) existingMsg.remove();

                if (types.length === 0) {{
                    canvas.style.display = 'none';
                    const msg = document.createElement('div');
                    msg.className = 'no-data-message';
                    msg.style.cssText = 'text-align:center;padding:100px 0;color:#999;';
                    msg.textContent = 'No data available';
                    canvas.parentElement.appendChild(msg);
                    return;
                }}

                canvas.style.display = 'block';

                const data = types.map(t => byType[t].count);
                const colors = types.map(t => this.typeColors[t] || '#607D8B');
                const typeKeys = types; // Store for click handler

                this.typeChart = new Chart(canvas, {{
                    type: 'bar',
                    data: {{
                        labels: types,
                        datasets: [{{
                            label: 'Sessions',
                            data: data,
                            backgroundColor: colors,
                            borderRadius: 4,
                            borderSkipped: false
                        }}]
                    }},
                    options: {{
                        indexAxis: 'y',  // Horizontal bar chart
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ display: false }},
                            tooltip: {{
                                backgroundColor: 'rgba(0,0,0,0.8)',
                                titleFont: {{ size: 13 }},
                                bodyFont: {{ size: 12 }},
                                padding: 10,
                                cornerRadius: 6,
                                callbacks: {{
                                    title: (items) => items[0].label,
                                    label: (item) => `${{item.raw}} sessions`
                                }}
                            }}
                        }},
                        scales: {{
                            x: {{
                                beginAtZero: true,
                                grid: {{ color: '#eee' }},
                                ticks: {{ stepSize: 1 }}
                            }},
                            y: {{
                                grid: {{ display: false }},
                                ticks: {{ font: {{ size: 12 }} }}
                            }}
                        }},
                        onClick: (event, elements) => {{
                            if (elements.length > 0) {{
                                const index = elements[0].index;
                                this.handleTypeChartClick(typeKeys[index]);
                            }}
                        }},
                        onHover: (event, elements) => {{
                            canvas.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                        }}
                    }}
                }});
            }}
        }};

        // ===== Initialize App =====
        // Set up wrapper BEFORE MapView.init() since init() calls loadSessions()
        const originalLoadSessions = MapView.loadSessions.bind(MapView);
        MapView.loadSessions = async function() {{
            await originalLoadSessions();
            // Pass full session data to views
            SessionsView.setSessions(this.allSessions);
            StatsView.setSessions(this.allSessions);

            // Populate filter bar types for all views
            FilterBar.populateTypes('map-filter-bar', this.allSessions);
            FilterBar.populateTypes('sessions-filter-bar', this.allSessions);
            FilterBar.populateTypes('stats-filter-bar', this.allSessions);

            // Sync initial filter state from URL
            FilterState.syncFromURL();
            FilterBar.syncFromState('map-filter-bar');
            FilterBar.syncFromState('sessions-filter-bar');
            FilterBar.syncFromState('stats-filter-bar');

            // Apply initial filters
            MapView.applyFiltersAndUpdateUI();

            // Hide loading overlay
            const overlay = document.getElementById('loading-overlay');
            if (overlay) {{
                overlay.classList.add('hidden');
                // Remove from DOM after animation
                setTimeout(() => overlay.remove(), 300);
            }}
        }};

        Router.init();
        MapView.init();
        SessionsView.init();
        StatsView.init();
    </script>
</body>
</html>"""


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
