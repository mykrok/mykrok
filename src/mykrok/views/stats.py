"""Statistics calculation and display for MyKrok.

Calculates activity statistics with filtering by date range and activity type.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from mykrok.lib.paths import iter_athlete_dirs, iter_session_dirs, parse_session_datetime
from mykrok.models.activity import load_activity


def calculate_stats(
    data_dir: Path,
    year: int | None = None,
    month: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    activity_type: str | None = None,
    by_month: bool = False,
    by_type: bool = False,
) -> dict[str, Any]:
    """Calculate activity statistics.

    Args:
        data_dir: Base data directory.
        year: Filter by year.
        month: Filter by month (YYYY-MM format).
        after: Filter activities after this date.
        before: Filter activities before this date.
        activity_type: Filter by activity type.
        by_month: Break down by month.
        by_type: Break down by activity type.

    Returns:
        Dictionary with statistics.
    """
    # Parse month if provided
    if month:
        try:
            year_part, month_part = month.split("-")
            after = datetime(int(year_part), int(month_part), 1)
            # Calculate end of month
            if int(month_part) == 12:
                before = datetime(int(year_part) + 1, 1, 1)
            else:
                before = datetime(int(year_part), int(month_part) + 1, 1)
        except (ValueError, IndexError):
            pass

    # Handle year filter
    if year and not month:
        after = datetime(year, 1, 1)
        before = datetime(year + 1, 1, 1)

    # Collect activities
    activities: list[dict[str, Any]] = []

    for _username, athlete_dir in iter_athlete_dirs(data_dir):
        for session_key, session_dir in iter_session_dirs(athlete_dir):
            try:
                session_date = parse_session_datetime(session_key)
            except ValueError:
                continue

            # Apply date filters
            if after and session_date < after:
                continue
            if before and session_date >= before:
                continue

            # Load activity
            activity = load_activity(session_dir)
            if not activity:
                continue

            # Apply type filter
            if activity_type and activity.type.lower() != activity_type.lower():
                continue

            activities.append(
                {
                    "date": session_date,
                    "type": activity.type,
                    "sport_type": activity.sport_type,
                    "distance": activity.distance or 0,
                    "moving_time": activity.moving_time or 0,
                    "elapsed_time": activity.elapsed_time or 0,
                    "elevation_gain": activity.total_elevation_gain or 0,
                    "calories": activity.calories or 0,
                }
            )

    # Calculate totals
    totals = _calculate_totals(activities)

    result: dict[str, Any] = {
        "period": {},
        "totals": totals,
    }

    # Set period info
    if year:
        result["period"]["year"] = year
    if month:
        result["period"]["month"] = month
    if after and not year and not month:
        result["period"]["after"] = after.isoformat()
    if before and not year and not month:
        result["period"]["before"] = before.isoformat()
    if activity_type:
        result["period"]["type"] = activity_type

    # Break down by month
    if by_month:
        monthly: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for act in activities:
            month_key = act["date"].strftime("%Y-%m")
            monthly[month_key].append(act)

        result["by_month"] = {
            month_key: _calculate_totals(acts) for month_key, acts in sorted(monthly.items())
        }

    # Break down by type
    if by_type:
        by_activity_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for act in activities:
            by_activity_type[act["type"]].append(act)

        result["by_type"] = {
            act_type: _calculate_totals(acts) for act_type, acts in sorted(by_activity_type.items())
        }

    return result


def _calculate_totals(activities: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate totals for a list of activities.

    Args:
        activities: List of activity dictionaries.

    Returns:
        Totals dictionary.
    """
    if not activities:
        return {
            "activities": 0,
            "distance_km": 0,
            "time_hours": 0,
            "elevation_m": 0,
            "calories": 0,
        }

    total_distance = sum(a["distance"] for a in activities)
    total_time = sum(a["moving_time"] for a in activities)
    total_elevation = sum(a["elevation_gain"] for a in activities)
    total_calories = sum(a["calories"] for a in activities)

    return {
        "activities": len(activities),
        "distance_km": round(total_distance / 1000, 1),
        "time_hours": round(total_time / 3600, 2),
        "elevation_m": round(total_elevation, 0),
        "calories": total_calories,
    }


def format_stats(stats: dict[str, Any]) -> str:
    """Format statistics as human-readable text.

    Args:
        stats: Statistics dictionary from calculate_stats.

    Returns:
        Formatted text.
    """
    lines: list[str] = []

    # Header
    period = stats.get("period", {})
    if period.get("year") and period.get("month"):
        lines.append(f"Statistics for {period['month']}:")
    elif period.get("year"):
        lines.append(f"Statistics for {period['year']}:")
    elif period.get("after") or period.get("before"):
        date_range = []
        if period.get("after"):
            date_range.append(f"after {period['after'][:10]}")
        if period.get("before"):
            date_range.append(f"before {period['before'][:10]}")
        lines.append(f"Statistics ({', '.join(date_range)}):")
    else:
        lines.append("Overall Statistics:")

    if period.get("type"):
        lines.append(f"  Filtered by type: {period['type']}")

    lines.append("")

    # Totals
    totals = stats.get("totals", {})
    lines.append(f"  Total Activities: {totals.get('activities', 0):,}")
    lines.append(f"  Total Distance: {totals.get('distance_km', 0):,.1f} km")
    lines.append(f"  Total Time: {_format_hours(totals.get('time_hours', 0))}")
    lines.append(f"  Total Elevation: {totals.get('elevation_m', 0):,.0f} m")
    if totals.get("calories"):
        lines.append(f"  Total Calories: {totals.get('calories', 0):,}")

    # By month
    if "by_month" in stats:
        lines.append("")
        lines.append("  By Month:")
        for month_key, month_totals in stats["by_month"].items():
            lines.append(
                f"    {month_key}: {month_totals['activities']} activities, "
                f"{month_totals['distance_km']:.1f} km, "
                f"{_format_hours(month_totals['time_hours'])}"
            )

    # By type
    if "by_type" in stats:
        lines.append("")
        lines.append("  By Type:")
        for act_type, type_totals in stats["by_type"].items():
            lines.append(
                f"    {act_type}: {type_totals['activities']} activities, "
                f"{type_totals['distance_km']:.1f} km"
            )

    return "\n".join(lines)


def _format_hours(hours: float) -> str:
    """Format hours as human-readable string.

    Args:
        hours: Number of hours.

    Returns:
        Formatted string (e.g., "12h 30m").
    """
    total_minutes = int(hours * 60)
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h}h {m}m"
