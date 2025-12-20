"""Map visualization for strava-backup.

Generates interactive HTML maps using Leaflet.js with optional heatmap mode
and photo overlay support.
"""

from __future__ import annotations

import http.server
import json
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
