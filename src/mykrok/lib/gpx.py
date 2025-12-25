"""GPX generation and export for MyKrok.

Generates GPX files with optional Garmin TrackPoint extensions for
heart rate, cadence, and power data.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mykrok.lib.paths import (
    iter_athlete_dirs,
    iter_session_dirs,
    parse_session_datetime,
)
from mykrok.models.activity import load_activity
from mykrok.models.tracking import iter_track_points, load_tracking_manifest

if TYPE_CHECKING:
    from collections.abc import Callable


# XML namespaces
GPX_NS = "http://www.topografix.com/GPX/1/1"
GARMIN_TPX_NS = "http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def generate_gpx(
    session_dir: Path,
    include_hr: bool = True,
    include_cadence: bool = True,
    include_power: bool = True,
) -> str:
    """Generate GPX XML from tracking data.

    Args:
        session_dir: Session partition directory.
        include_hr: Include heart rate in extensions.
        include_cadence: Include cadence in extensions.
        include_power: Include power in extensions.

    Returns:
        GPX XML as string.
    """
    # Load activity metadata
    activity = load_activity(session_dir)
    if not activity:
        raise ValueError(f"No activity found in {session_dir}")

    # Load tracking manifest to check available data
    manifest = load_tracking_manifest(session_dir)
    if not manifest or manifest.row_count == 0:
        raise ValueError(f"No tracking data in {session_dir}")

    # Get track points
    points = iter_track_points(session_dir)
    if not points:
        raise ValueError(f"No track points in {session_dir}")

    # Create GPX root element
    gpx = ET.Element("gpx")
    gpx.set("xmlns", GPX_NS)
    gpx.set("xmlns:gpxtpx", GARMIN_TPX_NS)
    gpx.set("xmlns:xsi", XSI_NS)
    gpx.set("version", "1.1")
    gpx.set("creator", "mykrok")

    # Add metadata
    metadata = ET.SubElement(gpx, "metadata")
    name_elem = ET.SubElement(metadata, "name")
    name_elem.text = activity.name
    time_elem = ET.SubElement(metadata, "time")
    time_elem.text = activity.start_date.isoformat()

    # Create track
    trk = ET.SubElement(gpx, "trk")
    trk_name = ET.SubElement(trk, "name")
    trk_name.text = activity.name
    trk_type = ET.SubElement(trk, "type")
    trk_type.text = activity.type

    # Create track segment
    trkseg = ET.SubElement(trk, "trkseg")

    # Calculate actual timestamps from activity start and relative time
    start_time = activity.start_date

    for point in points:
        if not point.has_location:
            continue

        trkpt = ET.SubElement(trkseg, "trkpt")
        trkpt.set("lat", f"{point.lat:.7f}")
        trkpt.set("lon", f"{point.lng:.7f}")

        # Elevation
        if point.altitude is not None:
            ele = ET.SubElement(trkpt, "ele")
            ele.text = f"{point.altitude:.1f}"

        # Time
        point_time = start_time + timedelta(seconds=point.time)
        time_elem = ET.SubElement(trkpt, "time")
        time_elem.text = point_time.isoformat()

        # Extensions (Garmin TrackPoint Extension)
        has_extensions = False
        ext_data: dict[str, int | None] = {}

        if include_hr and manifest.has_hr and point.heartrate is not None:
            ext_data["hr"] = point.heartrate
            has_extensions = True

        if include_cadence and manifest.has_cadence and point.cadence is not None:
            ext_data["cad"] = point.cadence
            has_extensions = True

        if include_power and manifest.has_power and point.watts is not None:
            # Power is stored as watts but Garmin uses power element
            ext_data["power"] = point.watts
            has_extensions = True

        if has_extensions:
            extensions = ET.SubElement(trkpt, "extensions")
            tpx = ET.SubElement(extensions, f"{{{GARMIN_TPX_NS}}}TrackPointExtension")

            if "hr" in ext_data:
                hr_elem = ET.SubElement(tpx, f"{{{GARMIN_TPX_NS}}}hr")
                hr_elem.text = str(ext_data["hr"])

            if "cad" in ext_data:
                cad_elem = ET.SubElement(tpx, f"{{{GARMIN_TPX_NS}}}cad")
                cad_elem.text = str(ext_data["cad"])

            # Power is not in standard Garmin TPX, use separate element
            if "power" in ext_data:
                # Some tools expect power in a different namespace or element
                power_elem = ET.SubElement(extensions, "power")
                power_elem.text = str(ext_data["power"])

    # Convert to string with proper declaration
    ET.register_namespace("", GPX_NS)
    ET.register_namespace("gpxtpx", GARMIN_TPX_NS)
    ET.register_namespace("xsi", XSI_NS)

    xml_str = ET.tostring(gpx, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'


def save_gpx(
    session_dir: Path,
    output_path: Path,
    include_hr: bool = True,
    include_cadence: bool = True,
    include_power: bool = True,
) -> Path:
    """Generate and save GPX file.

    Args:
        session_dir: Session partition directory.
        output_path: Output file path.
        include_hr: Include heart rate.
        include_cadence: Include cadence.
        include_power: Include power.

    Returns:
        Path to saved GPX file.
    """
    gpx_content = generate_gpx(
        session_dir,
        include_hr=include_hr,
        include_cadence=include_cadence,
        include_power=include_power,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(gpx_content, encoding="utf-8")
    return output_path


def export_activities_to_gpx(
    data_dir: Path,
    output_dir: Path,
    sessions: list[str] | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    include_hr: bool = True,
    include_cadence: bool = True,
    include_power: bool = True,
    log_callback: Callable[[str, int], None] | None = None,
) -> dict[str, Any]:
    """Export multiple activities to GPX files.

    Args:
        data_dir: Base data directory.
        output_dir: Output directory for GPX files.
        sessions: Specific session keys to export (optional).
        after: Only export activities after this date.
        before: Only export activities before this date.
        include_hr: Include heart rate.
        include_cadence: Include cadence.
        include_power: Include power.
        log_callback: Optional callback for progress messages.

    Returns:
        Dictionary with export results.
    """

    def log(msg: str, level: int = 0) -> None:
        if log_callback:
            log_callback(msg, level)

    output_dir.mkdir(parents=True, exist_ok=True)

    exported = 0
    skipped = 0
    errors: list[dict[str, str]] = []

    # Convert sessions list to set for quick lookup
    session_set = set(sessions) if sessions else None

    for _username, athlete_dir in iter_athlete_dirs(data_dir):
        for session_key, session_dir in iter_session_dirs(athlete_dir):
            # Filter by session list
            if session_set is not None and session_key not in session_set:
                continue

            # Filter by date
            try:
                session_date = parse_session_datetime(session_key)
            except ValueError:
                continue

            if after and session_date < after:
                continue
            if before and session_date > before:
                continue

            # Check if activity has GPS data
            manifest = load_tracking_manifest(session_dir)
            if not manifest or not manifest.has_gps:
                skipped += 1
                log(f"  Skipping {session_key} (no GPS data)", 1)
                continue

            # Load activity for name
            activity = load_activity(session_dir)
            if not activity:
                skipped += 1
                continue

            # Generate output filename
            safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in activity.name)
            safe_name = safe_name[:50]  # Limit length
            output_file = output_dir / f"{session_key}_{safe_name}.gpx"

            try:
                save_gpx(
                    session_dir,
                    output_file,
                    include_hr=include_hr,
                    include_cadence=include_cadence,
                    include_power=include_power,
                )
                exported += 1
                log(f"  Exported {activity.name} to {output_file.name}")
            except Exception as e:
                errors.append({"session": session_key, "error": str(e)})
                log(f"  Error exporting {session_key}: {e}")

    return {
        "exported": exported,
        "skipped": skipped,
        "errors": errors,
        "output_dir": str(output_dir),
    }


def get_gpx_size(gpx_content: str) -> int:
    """Get size of GPX content in bytes.

    Args:
        gpx_content: GPX XML string.

    Returns:
        Size in bytes.
    """
    return len(gpx_content.encode("utf-8"))


def simplify_track(
    points: list[dict[str, Any]],
    max_points: int = 10000,
) -> list[dict[str, Any]]:
    """Simplify a track by reducing number of points.

    Uses simple uniform sampling. For production use, consider
    implementing Ramer-Douglas-Peucker algorithm.

    Args:
        points: List of track points.
        max_points: Maximum number of points.

    Returns:
        Simplified list of points.
    """
    if len(points) <= max_points:
        return points

    # Simple uniform sampling
    step = len(points) / max_points
    indices = [int(i * step) for i in range(max_points)]
    indices[-1] = len(points) - 1  # Always include last point

    return [points[i] for i in indices]
