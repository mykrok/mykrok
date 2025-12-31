"""Interactive browser generation for MyKrok.

Generates a single-page application (SPA) for browsing activities using Leaflet.js.
"""

from __future__ import annotations

import http.server
import importlib.resources
import shutil
import socketserver
from pathlib import Path
from typing import Any

from mykrok import __version__


def _get_assets_dir() -> Path:
    """Get path to bundled assets directory."""
    # Use importlib.resources for Python 3.9+
    try:
        files = importlib.resources.files("mykrok")
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

    # Copy map-browser JavaScript
    mapbrowser_src = assets_src / "map-browser"
    mapbrowser_dst = assets_dst / "map-browser"
    if mapbrowser_src.exists():
        if mapbrowser_dst.exists():
            shutil.rmtree(mapbrowser_dst)
        shutil.copytree(mapbrowser_src, mapbrowser_dst)

    # Copy logo/favicon
    logo_src = assets_src / "mykrok-icon.svg"
    if logo_src.exists():
        # Copy to assets/ for the <link rel="icon"> tag
        shutil.copy2(logo_src, assets_dst / "mykrok-icon.svg")
        # Also copy to root as favicon.svg for browsers that request /favicon.*
        shutil.copy2(logo_src, output_dir / "favicon.svg")

    return assets_dst



def generate_browser(_data_dir: Path) -> str:
    """Generate interactive browser SPA that loads data on demand.

    Creates a single-page application with:
    - App shell with header and tab navigation
    - Map view: interactive map with activity markers and tracks
    - Sessions view: filterable list of all activities
    - Stats view: activity statistics and charts

    Data sources:
    - athletes.tsv for athlete list
    - athl={username}/sessions.tsv for session metadata
    - athl={username}/ses={datetime}/tracking.parquet for track coordinates

    Track coordinates are loaded on-demand when clicking on a session marker.

    Args:
        _data_dir: Base data directory (unused, kept for API compatibility).

    Returns:
        HTML content as string.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MyKrok</title>
    <link rel="icon" type="image/svg+xml" href="assets/mykrok-icon.svg">
    <link rel="icon" type="image/svg+xml" href="favicon.svg">
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

        .app-logo-text {{
            display: flex;
            flex-direction: column;
            line-height: 1.1;
        }}

        .app-version {{
            font-size: 10px;
            font-weight: 400;
            color: #888;
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

        .info-session-item.focused {{
            background: #fff3e0;
            border-color: #fc4c02;
            animation: focus-pulse 0.5s ease-out;
        }}

        @keyframes focus-pulse {{
            0% {{ box-shadow: 0 0 0 0 rgba(252, 76, 2, 0.4); }}
            100% {{ box-shadow: 0 0 0 6px rgba(252, 76, 2, 0); }}
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
            cursor: pointer;
            padding: 1px 3px;
            border-radius: 3px;
        }}
        .info-session-date:hover {{
            background: #e8e8e8;
            color: #333;
        }}

        .info-session-type {{
            font-size: 10px;
            background: #e8e8e8;
            padding: 1px 4px;
            border-radius: 3px;
            margin-left: 4px;
        }}

        .info-session-photo {{
            margin-left: 4px;
            vertical-align: middle;
            display: inline-flex;
            align-items: center;
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

        .photo-popup .photo-nav-row {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-top: 8px;
            margin-bottom: 4px;
        }}

        .photo-popup .photo-counter {{
            font-size: 12px;
            color: #666;
            min-width: 50px;
            text-align: center;
        }}

        .photo-popup .photo-nav-btn {{
            background: #f5f5f5;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 28px;
            height: 28px;
            font-size: 18px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #333;
            transition: background 0.2s;
        }}

        .photo-popup .photo-nav-btn:hover:not(:disabled) {{
            background: #e8e8e8;
        }}

        .photo-popup .photo-nav-btn:disabled {{
            opacity: 0.3;
            cursor: default;
        }}

        /* Floating photo popup for charts */
        .photo-popup-floating {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
            padding: 8px;
            pointer-events: auto;
        }}

        .photo-popup-floating .photo-popup {{
            max-width: 280px;
        }}

        .photo-popup-floating .photo-popup img {{
            max-width: 100%;
            max-height: 200px;
            object-fit: contain;
        }}

        /* Photo Viewer Modal */
        .photo-viewer-modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 10000;
            align-items: center;
            justify-content: center;
        }}

        .photo-viewer-overlay {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
        }}

        .photo-viewer-content {{
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            max-width: 95vw;
            max-height: 95vh;
        }}

        .photo-viewer-image-container {{
            display: flex;
            align-items: center;
            justify-content: center;
            max-width: 90vw;
            max-height: 80vh;
            cursor: pointer;
            user-select: none;
            -webkit-user-select: none;
        }}

        .photo-viewer-image {{
            max-width: 100%;
            max-height: 80vh;
            object-fit: contain;
            border-radius: 4px;
            pointer-events: none;
            -webkit-user-drag: none;
            user-select: none;
            -webkit-user-select: none;
        }}

        .photo-viewer-close {{
            position: absolute;
            top: -40px;
            right: 0;
            background: none;
            border: none;
            color: white;
            font-size: 36px;
            cursor: pointer;
            padding: 0 10px;
            line-height: 1;
        }}

        .photo-viewer-close:hover {{
            color: #FC4C02;
        }}

        .photo-viewer-prev,
        .photo-viewer-next {{
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(255, 255, 255, 0.1);
            border: none;
            color: white;
            font-size: 48px;
            cursor: pointer;
            padding: 20px 15px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s;
        }}

        .photo-viewer-prev:hover:not(:disabled),
        .photo-viewer-next:hover:not(:disabled) {{
            background: rgba(255, 255, 255, 0.2);
        }}

        .photo-viewer-prev:disabled,
        .photo-viewer-next:disabled {{
            opacity: 0.3;
            cursor: default;
        }}

        .photo-viewer-prev {{
            left: -80px;
        }}

        .photo-viewer-next {{
            right: -80px;
        }}

        .photo-viewer-footer {{
            display: flex;
            align-items: center;
            gap: 16px;
            margin-top: 16px;
            color: white;
        }}

        .photo-viewer-counter {{
            font-size: 14px;
            opacity: 0.8;
        }}

        .photo-viewer-open {{
            background: none;
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 6px 10px;
            border-radius: 4px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            transition: background 0.2s, border-color 0.2s;
        }}

        .photo-viewer-open:hover {{
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.5);
        }}

        @media (max-width: 768px) {{
            .photo-viewer-prev,
            .photo-viewer-next {{
                position: fixed;
                top: auto;
                bottom: 80px;
                transform: none;
                font-size: 36px;
                padding: 15px 20px;
            }}

            .photo-viewer-prev {{
                left: 20px;
            }}

            .photo-viewer-next {{
                right: 20px;
            }}
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

        .detail-description {{
            font-size: 14px;
            color: #444;
            line-height: 1.5;
            margin-bottom: 16px;
            padding: 12px;
            background: #f8f9fa;
            border-left: 3px solid #fc4c02;
            border-radius: 4px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}

        .detail-description:empty {{
            display: none;
        }}

        .detail-description a {{
            color: #fc4c02;
            text-decoration: none;
            word-break: break-all;
        }}

        .detail-description a:hover {{
            text-decoration: underline;
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

        .full-session-description {{
            font-size: 15px;
            color: #444;
            line-height: 1.6;
            margin-bottom: 24px;
            padding: 16px 20px;
            background: #fff;
            border-left: 4px solid #fc4c02;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            white-space: pre-wrap;
            word-wrap: break-word;
        }}

        .full-session-description:empty {{
            display: none;
        }}

        .full-session-description a {{
            color: #fc4c02;
            text-decoration: none;
            word-break: break-all;
        }}

        .full-session-description a:hover {{
            text-decoration: underline;
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

        /* Viewport filter control - filter activities list to map view */
        .leaflet-control-viewport {{
            background: white;
            border-radius: 4px;
            box-shadow: 0 1px 5px rgba(0, 0, 0, 0.4);
            margin-top: 5px;
        }}

        .leaflet-control-viewport button {{
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
            transition: background-color 0.2s, color 0.2s;
        }}

        .leaflet-control-viewport button:hover {{
            background: #f4f4f4;
        }}

        .leaflet-control-viewport button.active {{
            background: #3388ff;
            color: white;
        }}

        .leaflet-control-viewport button.active:hover {{
            background: #2277ee;
        }}

        .leaflet-control-viewport svg {{
            width: 16px;
            height: 16px;
        }}

        .leaflet-control-viewport button.active svg {{
            color: white;
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

        .popup-date-link {{
            color: #666;
            text-decoration: none;
            cursor: pointer;
            border-bottom: 1px dashed #999;
        }}

        .popup-date-link:hover {{
            color: #2196F3;
            border-bottom-color: #2196F3;
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

        /* Heatmap specific styles */
        .heatmap-container {{
            grid-column: 1 / -1;
        }}

        .heatmap-scroll-wrapper {{
            overflow-x: auto;
        }}

        /* Unified heatmap grid table (both timing and calendar) */
        .heatmap-grid-table {{
            border-collapse: separate;
            border-spacing: 2px;
            font-size: 9px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}

        .heatmap-grid-table .heatmap-col-label {{
            font-weight: normal;
            color: #666;
            text-align: left;
            padding: 0 2px 2px 0;
            font-size: 9px;
        }}

        .heatmap-grid-table .heatmap-header-clickable {{
            cursor: pointer;
        }}

        .heatmap-grid-table .heatmap-header-clickable:hover {{
            color: #fc4c02;
            text-decoration: underline;
        }}

        .heatmap-grid-table .heatmap-day-label {{
            color: #666;
            text-align: right;
            padding-right: 4px;
            font-size: 9px;
            white-space: nowrap;
        }}

        .heatmap-grid-table .heatmap-cell {{
            width: 10px;
            height: 10px;
            min-width: 10px;
            min-height: 10px;
            border-radius: 2px;
        }}

        .heatmap-grid-table .heatmap-cell-clickable {{
            cursor: pointer;
        }}

        .heatmap-grid-table .heatmap-cell-clickable:hover {{
            outline: 1px solid #fc4c02;
        }}

        .heatmap-grid-table .heatmap-cell-empty {{
            opacity: 0.4;
        }}

        .heatmap-grid-table .heatmap-footer-row td {{
            border-top: 2px solid #ccc;
        }}

        .heatmap-grid-table .heatmap-footer-row .heatmap-day-label {{
            font-weight: 600;
        }}

        .heatmap-legend {{
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 8px;
            margin-top: 8px;
            font-size: 12px;
            color: #666;
        }}

        .legend-scale {{
            width: 80px;
            height: 10px;
            background: linear-gradient(to right, #ebedf0, #fc4c02);
            border-radius: 2px;
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
        <a href="https://github.com/mykrok/mykrok" class="app-logo" target="_blank">
            <img src="assets/mykrok-icon.svg" alt="Logo">
            <span class="app-logo-text">
                MyKrok
                <span class="app-version">v{__version__}</span>
            </span>
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
                                <th data-sort="photos" class="sortable">Photos</th>
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
                    <div class="detail-description" id="detail-description"></div>
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
                    <div class="chart-container heatmap-container">
                        <h3>Activity Timing</h3>
                        <div id="heatmap-wrapper" class="heatmap-scroll-wrapper"></div>
                        <div class="heatmap-legend" id="heatmap-legend">
                            <span class="legend-min">0</span>
                            <div class="legend-scale"></div>
                            <span class="legend-max"></span>
                        </div>
                    </div>
                    <div class="chart-container heatmap-container">
                        <h3>Activity Calendar</h3>
                        <div id="calendar-heatmap-wrapper" class="heatmap-scroll-wrapper"></div>
                        <div class="heatmap-legend" id="calendar-heatmap-legend">
                            <span class="legend-min">0</span>
                            <div class="legend-scale"></div>
                            <span class="legend-max"></span>
                        </div>
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
                    <section class="full-session-description" id="full-session-description"></section>
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
    <script type="module" src="assets/map-browser/map-browser.js"></script>
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
