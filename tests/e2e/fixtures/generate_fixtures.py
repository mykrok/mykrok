#!/usr/bin/env python3
"""Generate synthetic test fixtures for e2e testing.

Creates sample data for two athletes (alice and bob) with:
- Various activity types (Run, Ride, Swim, Hike)
- A shared run (same datetime)
- GPS tracks with heart rate, cadence, power data
- Photos, kudos, and comments
- Different date ranges for stats testing

Usage:
    python generate_fixtures.py [output_dir]

If output_dir is not specified, generates in the current directory.
"""

from __future__ import annotations

import base64
import csv
import json
import math
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

import pyarrow as pa
import pyarrow.parquet as pq


class ActivityParams(TypedDict, total=False):
    """Type for activity parameters."""

    sport: str
    distance_range: tuple[float, float]
    pace_range: tuple[float, float]
    hr_range: tuple[float, float]
    cadence_range: tuple[float, float]
    elevation_range: tuple[float, float]
    watts_range: tuple[float, float]


# Minimal valid JPEG - a small colored square (8x8 pixels)
# This is a real JPEG that will display in browsers
PLACEHOLDER_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkS"
    "Ew8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJ"
    "CQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjL/wAARCAAIAAgDASIAAhEBAxEB/8QAFgABAQEAAAAAAAAA"
    "AAAAAAAAAAMH/8QAIhAAAgEDAwUBAAAAAAAAAAAAAQIDAAQRBRIhBhMiMUFR/8QA"
    "FQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAZEQACAwEAAAAAAAAAAAAAAAABAgADESH/2gAM"
    "AwEAAhEDEQA/AKOm6Vp9np8NvBCqxoMD3z+1KUVB2TGSQF1HE//Z"
)


# Activity types with realistic parameters
ACTIVITY_TYPES: dict[str, ActivityParams] = {
    "Run": {
        "sport": "Run",
        "distance_range": (3000, 15000),  # meters
        "pace_range": (4.5, 7.0),  # min/km
        "hr_range": (120, 180),
        "cadence_range": (160, 190),
        "elevation_range": (20, 200),
    },
    "Ride": {
        "sport": "Ride",
        "distance_range": (15000, 80000),
        "pace_range": (1.5, 3.0),  # min/km (speed in cycling terms)
        "hr_range": (100, 170),
        "cadence_range": (70, 100),
        "elevation_range": (100, 1000),
        "watts_range": (100, 300),
    },
    "Swim": {
        "sport": "Swim",
        "distance_range": (500, 3000),
        "pace_range": (1.5, 3.0),  # min/100m
        "hr_range": (100, 160),
        "elevation_range": (0, 0),
    },
    "Hike": {
        "sport": "Hike",
        "distance_range": (5000, 20000),
        "pace_range": (8.0, 15.0),  # min/km
        "hr_range": (90, 140),
        "elevation_range": (200, 1500),
    },
}

# Sample locations for GPS tracks (lat, lng, name)
LOCATIONS = [
    (40.7128, -74.0060, "New York"),
    (34.0522, -118.2437, "Los Angeles"),
    (41.8781, -87.6298, "Chicago"),
    (37.7749, -122.4194, "San Francisco"),
    (47.6062, -122.3321, "Seattle"),
]

# Letter shapes for "DEMO" - normalized coordinates (0-1 range for x and y)
# Each letter is a list of (x, y) points that trace the letter shape
LETTER_SHAPES = {
    "D": [
        (0.0, 0.0),
        (0.0, 1.0),
        (0.5, 1.0),
        (0.7, 0.8),
        (0.7, 0.2),
        (0.5, 0.0),
        (0.0, 0.0),
    ],
    "E": [
        (0.7, 0.0),
        (0.0, 0.0),
        (0.0, 0.5),
        (0.5, 0.5),
        (0.0, 0.5),
        (0.0, 1.0),
        (0.7, 1.0),
    ],
    "M": [
        (0.0, 0.0),
        (0.0, 1.0),
        (0.35, 0.5),
        (0.7, 1.0),
        (0.7, 0.0),
    ],
    "O": [
        (0.35, 0.0),
        (0.1, 0.2),
        (0.0, 0.5),
        (0.1, 0.8),
        (0.35, 1.0),
        (0.55, 0.8),
        (0.7, 0.5),
        (0.55, 0.2),
        (0.35, 0.0),
    ],
}


def get_demo_path() -> list[tuple[float, float]]:
    """Generate path points that spell 'DEMO'."""
    word = "DEMO"
    path = []
    letter_width = 0.8  # Width of each letter
    spacing = 0.2  # Space between letters

    for i, letter in enumerate(word):
        if letter not in LETTER_SHAPES:
            continue
        x_offset = i * (letter_width + spacing)
        for x, y in LETTER_SHAPES[letter]:
            path.append((x * letter_width + x_offset, y))

    return path


def generate_gps_track(
    start_lat: float,
    start_lng: float,
    distance_m: float,
    duration_s: int,
    activity_type: str,
) -> list[dict[str, Any]]:
    """Generate a GPS track that spells 'DEMO' with sensor data."""
    # Get the DEMO path
    demo_path = get_demo_path()
    if not demo_path:
        return []

    # Activity-specific parameters
    params = ACTIVITY_TYPES.get(activity_type, ACTIVITY_TYPES["Run"])
    has_hr = random.random() > 0.1  # 90% have HR
    has_cadence = activity_type in ("Run", "Ride") and random.random() > 0.2
    has_power = activity_type == "Ride" and random.random() > 0.3

    # Scale the path to fit the desired distance
    # Calculate total path length in normalized units
    path_length = 0.0
    for i in range(1, len(demo_path)):
        dx = demo_path[i][0] - demo_path[i - 1][0]
        dy = demo_path[i][1] - demo_path[i - 1][1]
        path_length += math.sqrt(dx * dx + dy * dy)

    # Scale factor to convert normalized units to meters
    # Then convert to lat/lng degrees
    scale_m = distance_m / path_length if path_length > 0 else 100
    # Meters per degree of latitude
    lat_scale = scale_m / 111320
    # Meters per degree of longitude (adjusted for latitude)
    lng_scale = scale_m / (111320 * math.cos(math.radians(start_lat)))

    # Interpolate points along the path for smooth tracking
    points_needed = max(int(duration_s / 5), 20)
    track = []

    for i in range(points_needed):
        progress = i / (points_needed - 1) if points_needed > 1 else 0

        # Find position along the path
        target_dist = progress * path_length
        current_dist = 0.0
        px, py = demo_path[0]

        for j in range(1, len(demo_path)):
            dx = demo_path[j][0] - demo_path[j - 1][0]
            dy = demo_path[j][1] - demo_path[j - 1][1]
            seg_len = math.sqrt(dx * dx + dy * dy)

            if current_dist + seg_len >= target_dist:
                # Interpolate within this segment
                t = (target_dist - current_dist) / seg_len if seg_len > 0 else 0
                px = demo_path[j - 1][0] + dx * t
                py = demo_path[j - 1][1] + dy * t
                break
            current_dist += seg_len
            px, py = demo_path[j]

        # Convert to lat/lng with small noise for realism
        lat = start_lat + py * lat_scale + random.gauss(0, lat_scale * 0.01)
        lng = start_lng + px * lng_scale + random.gauss(0, lng_scale * 0.01)

        time_s = int(progress * duration_s)
        cumulative_dist = progress * distance_m  # Cumulative distance in meters

        point = {
            "time": time_s,
            "distance": round(cumulative_dist, 1),
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "altitude": round(50 + 20 * math.sin(progress * math.pi * 4), 1),
        }

        if has_hr:
            hr_base = (params["hr_range"][0] + params["hr_range"][1]) / 2
            hr_variation = (params["hr_range"][1] - params["hr_range"][0]) / 2
            hr = hr_base + hr_variation * math.sin(progress * math.pi)
            point["heartrate"] = int(hr + random.gauss(0, 5))

        if has_cadence:
            cad_base = (params["cadence_range"][0] + params["cadence_range"][1]) / 2
            point["cadence"] = int(cad_base + random.gauss(0, 5))

        if has_power and "watts_range" in params:
            watts_base = (params["watts_range"][0] + params["watts_range"][1]) / 2
            point["watts"] = int(watts_base + random.gauss(0, 30))

        track.append(point)

    return track


def track_to_parquet(track: list[dict[str, Any]], output_path: Path) -> None:
    """Convert track data to parquet file."""
    if not track:
        return

    # Build columns from available data
    columns = {
        "time": pa.array([p["time"] for p in track], type=pa.int32()),
        "distance": pa.array([p.get("distance", 0) for p in track], type=pa.float32()),
        "lat": pa.array([p["lat"] for p in track], type=pa.float64()),
        "lng": pa.array([p["lng"] for p in track], type=pa.float64()),
    }

    if "altitude" in track[0]:
        columns["altitude"] = pa.array([p.get("altitude", 0) for p in track], type=pa.float32())

    if "heartrate" in track[0]:
        columns["heartrate"] = pa.array([p.get("heartrate", 0) for p in track], type=pa.int32())

    if "cadence" in track[0]:
        columns["cadence"] = pa.array([p.get("cadence", 0) for p in track], type=pa.int32())

    if "watts" in track[0]:
        columns["watts"] = pa.array([p.get("watts", 0) for p in track], type=pa.int32())

    table = pa.table(columns)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, output_path)


def generate_activity(
    activity_id: int,
    start_date: datetime,
    activity_type: str,
    has_gps: bool = True,
    has_photos: bool = False,
    kudos_from: list[str] | None = None,
    comments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate a single activity with all metadata."""
    params = ACTIVITY_TYPES.get(activity_type, ACTIVITY_TYPES["Run"])

    # Generate realistic values
    distance = random.uniform(*params["distance_range"])
    pace = random.uniform(*params["pace_range"])

    if activity_type == "Swim":
        # Pace is per 100m for swimming
        moving_time = int((distance / 100) * pace * 60)
    else:
        # Pace is per km
        moving_time = int((distance / 1000) * pace * 60)

    elapsed_time = moving_time + random.randint(0, 300)  # Add rest time
    elevation = random.uniform(*params["elevation_range"])

    avg_hr = (
        random.uniform(*params["hr_range"])
        if "hr_range" in params and random.random() > 0.2
        else None
    )
    max_hr = int(avg_hr * 1.1) if avg_hr else None

    avg_cadence = None
    if "cadence_range" in params and random.random() > 0.3:
        avg_cadence = random.uniform(*params["cadence_range"])

    avg_watts = None
    max_watts = None
    if "watts_range" in params and random.random() > 0.4:
        avg_watts = random.uniform(*params["watts_range"])
        max_watts = int(avg_watts * 1.3)

    # Activity names
    time_of_day = (
        "Morning" if start_date.hour < 12 else "Afternoon" if start_date.hour < 17 else "Evening"
    )
    names = [
        f"{time_of_day} {activity_type}",
        f"{activity_type} workout",
        f"Easy {activity_type.lower()}",
        f"Long {activity_type.lower()}",
        f"{activity_type} with friends",
    ]

    activity = {
        "id": activity_id,
        "name": random.choice(names),
        "description": f"A great {activity_type.lower()} session!"
        if random.random() > 0.7
        else None,
        "type": activity_type,
        "sport_type": params["sport"],
        "start_date": start_date.isoformat() + "Z",
        "start_date_local": start_date.isoformat(),
        "timezone": "(GMT-05:00) America/New_York",
        "distance": round(distance, 1),
        "moving_time": moving_time,
        "elapsed_time": elapsed_time,
        "total_elevation_gain": round(elevation, 1) if elevation > 0 else None,
        "calories": int(moving_time * 0.15) if random.random() > 0.3 else None,
        "average_speed": round(distance / moving_time, 2) if moving_time > 0 else None,
        "max_speed": round(distance / moving_time * 1.3, 2) if moving_time > 0 else None,
        "average_heartrate": round(avg_hr, 1) if avg_hr else None,
        "max_heartrate": max_hr,
        "average_watts": round(avg_watts, 1) if avg_watts else None,
        "max_watts": max_watts,
        "average_cadence": round(avg_cadence, 1) if avg_cadence else None,
        "gear_id": None,
        "device_name": random.choice(
            ["Garmin Forerunner 945", "Apple Watch", "Wahoo ELEMNT", None]
        ),
        "trainer": False,
        "commute": False,
        "private": False,
        "kudos_count": len(kudos_from) if kudos_from else random.randint(0, 15),
        "comment_count": len(comments) if comments else random.randint(0, 3),
        "athlete_count": 1,
        "achievement_count": random.randint(0, 5),
        "pr_count": random.randint(0, 2),
        "has_gps": has_gps,
        "has_photos": has_photos,
        "photo_count": random.randint(1, 5) if has_photos else 0,
        "comments": comments or [],
        "kudos": [
            {
                "firstname": k.split()[0] if " " in k else k,
                "lastname": k.split()[1] if " " in k else "",
                "username": k.lower().replace(" ", ""),
            }
            for k in (kudos_from or [])
        ],
        "laps": [],
        "segment_efforts": [],
        "photos": [],
    }

    return activity


def generate_sessions_tsv_row(activity: dict[str, Any], session_key: str) -> dict[str, Any]:
    """Convert activity dict to sessions.tsv row format."""
    return {
        "datetime": session_key,
        "type": activity["type"],
        "sport": activity["sport_type"],
        "name": activity["name"],
        "distance_m": activity["distance"],
        "moving_time_s": activity["moving_time"],
        "elapsed_time_s": activity["elapsed_time"],
        "elevation_gain_m": activity.get("total_elevation_gain") or "",
        "calories": activity.get("calories") or "",
        "avg_hr": activity.get("average_heartrate") or "",
        "max_hr": activity.get("max_heartrate") or "",
        "avg_watts": activity.get("average_watts") or "",
        "gear_id": activity.get("gear_id") or "",
        "athletes": activity.get("athlete_count", 1),
        "kudos_count": activity.get("kudos_count", 0),
        "comment_count": activity.get("comment_count", 0),
        "has_gps": "true" if activity.get("has_gps") else "false",
        "photos_path": f"ses={session_key}/photos/" if activity.get("has_photos") else "",
        "photo_count": activity.get("photo_count", 0),
        "start_lat": "",  # Will be filled from GPS data
        "start_lng": "",
    }


def generate_fixtures(output_dir: Path) -> None:
    """Generate complete fixture dataset."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define athletes
    athletes = [
        {"username": "alice", "firstname": "Alice", "lastname": "Runner"},
        {"username": "bob", "firstname": "Bob", "lastname": "Cyclist"},
    ]

    # Write athletes.tsv
    athletes_path = output_dir / "athletes.tsv"
    with open(athletes_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["username", "firstname", "lastname"], delimiter="\t")
        writer.writeheader()
        writer.writerows(athletes)

    print(f"Created {athletes_path}")

    # Define session TSV columns
    sessions_columns = [
        "datetime",
        "type",
        "sport",
        "name",
        "distance_m",
        "moving_time_s",
        "elapsed_time_s",
        "elevation_gain_m",
        "calories",
        "avg_hr",
        "max_hr",
        "avg_watts",
        "gear_id",
        "athletes",
        "kudos_count",
        "comment_count",
        "has_gps",
        "photos_path",
        "photo_count",
        "start_lat",
        "start_lng",
    ]

    # Shared run datetime (both alice and bob did this together)
    shared_run_dt = datetime(2024, 12, 18, 6, 30, 0)
    shared_run_key = shared_run_dt.strftime("%Y%m%dT%H%M%S")

    # Generate activities for alice (10 sessions)
    alice_dir = output_dir / "athl=alice"
    alice_dir.mkdir(parents=True, exist_ok=True)

    alice_sessions = []
    alice_id = 1000

    # Shared run with bob
    shared_activity = generate_activity(
        alice_id,
        shared_run_dt,
        "Run",
        has_gps=True,
        has_photos=True,
        kudos_from=["Bob Cyclist", "Charlie Walker"],
        comments=[
            {"text": "Great run today!", "firstname": "Bob", "lastname": "Cyclist"},
            {"text": "Love this route", "firstname": "Charlie", "lastname": "Walker"},
        ],
    )
    shared_activity["athlete_count"] = 2
    alice_sessions.append((shared_run_dt, shared_activity))
    alice_id += 1

    # Generate more sessions for alice
    activity_schedule = [
        (datetime(2024, 12, 15, 7, 0, 0), "Run", True, False),
        (datetime(2024, 12, 12, 18, 30, 0), "Ride", True, True),
        (datetime(2024, 12, 10, 6, 0, 0), "Swim", False, False),
        (datetime(2024, 12, 8, 8, 0, 0), "Hike", True, True),
        (datetime(2024, 11, 28, 7, 30, 0), "Run", True, False),
        (datetime(2024, 11, 20, 17, 0, 0), "Ride", True, False),
        (datetime(2024, 10, 15, 9, 0, 0), "Run", True, False),
        (datetime(2024, 9, 1, 8, 0, 0), "Hike", True, True),
        (datetime(2024, 8, 10, 6, 30, 0), "Run", True, False),
    ]

    for dt, activity_type, has_gps, has_photos in activity_schedule:
        activity = generate_activity(
            alice_id,
            dt,
            activity_type,
            has_gps=has_gps,
            has_photos=has_photos,
            kudos_from=["Bob Cyclist"] if random.random() > 0.5 else None,
        )
        alice_sessions.append((dt, activity))
        alice_id += 1

    # Write alice's sessions
    alice_tsv_rows = []
    for dt, activity in alice_sessions:
        session_key = dt.strftime("%Y%m%dT%H%M%S")
        session_dir = alice_dir / f"ses={session_key}"
        session_dir.mkdir(parents=True, exist_ok=True)

        # Write info.json
        with open(session_dir / "info.json", "w", encoding="utf-8") as f:
            json.dump(activity, f, indent=2)

        # Generate GPS track if has_gps
        if activity["has_gps"]:
            loc = random.choice(LOCATIONS)
            track = generate_gps_track(
                loc[0],
                loc[1],
                activity["distance"],
                activity["moving_time"],
                activity["type"],
            )
            track_to_parquet(track, session_dir / "tracking.parquet")

            # Update center coords
            row = generate_sessions_tsv_row(activity, session_key)
            row["start_lat"] = track[0]["lat"]
            row["start_lng"] = track[0]["lng"]
        else:
            row = generate_sessions_tsv_row(activity, session_key)

        alice_tsv_rows.append(row)

        # Create photos directory if needed
        if activity["has_photos"]:
            photos_dir = session_dir / "photos"
            photos_dir.mkdir(exist_ok=True)
            # Create placeholder photo files (actual valid JPEGs)
            for i in range(activity["photo_count"]):
                (photos_dir / f"photo_{i+1}.jpg").write_bytes(PLACEHOLDER_JPEG)

    # Sort by datetime and write sessions.tsv
    alice_tsv_rows.sort(key=lambda r: r["datetime"])
    with open(alice_dir / "sessions.tsv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sessions_columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(alice_tsv_rows)

    print(f"Created {len(alice_sessions)} sessions for alice")

    # Generate activities for bob (5 sessions, mostly cycling)
    bob_dir = output_dir / "athl=bob"
    bob_dir.mkdir(parents=True, exist_ok=True)

    bob_sessions = []
    bob_id = 2000

    # Shared run with alice
    bob_shared = generate_activity(
        bob_id,
        shared_run_dt,
        "Run",
        has_gps=True,
        has_photos=False,
        kudos_from=["Alice Runner"],
        comments=[{"text": "Thanks for the company!", "firstname": "Alice", "lastname": "Runner"}],
    )
    bob_shared["athlete_count"] = 2
    bob_sessions.append((shared_run_dt, bob_shared))
    bob_id += 1

    bob_schedule = [
        (datetime(2024, 12, 16, 7, 0, 0), "Ride", True, False),
        (datetime(2024, 12, 14, 8, 0, 0), "Ride", True, True),
        (datetime(2024, 12, 5, 17, 30, 0), "Ride", True, False),
        (datetime(2024, 11, 25, 9, 0, 0), "Run", True, False),
    ]

    for dt, activity_type, has_gps, has_photos in bob_schedule:
        activity = generate_activity(
            bob_id,
            dt,
            activity_type,
            has_gps=has_gps,
            has_photos=has_photos,
        )
        bob_sessions.append((dt, activity))
        bob_id += 1

    # Write bob's sessions
    bob_tsv_rows = []
    for dt, activity in bob_sessions:
        session_key = dt.strftime("%Y%m%dT%H%M%S")
        session_dir = bob_dir / f"ses={session_key}"
        session_dir.mkdir(parents=True, exist_ok=True)

        with open(session_dir / "info.json", "w", encoding="utf-8") as f:
            json.dump(activity, f, indent=2)

        if activity["has_gps"]:
            loc = random.choice(LOCATIONS)
            track = generate_gps_track(
                loc[0],
                loc[1],
                activity["distance"],
                activity["moving_time"],
                activity["type"],
            )
            track_to_parquet(track, session_dir / "tracking.parquet")

            row = generate_sessions_tsv_row(activity, session_key)
            row["start_lat"] = track[0]["lat"]
            row["start_lng"] = track[0]["lng"]
        else:
            row = generate_sessions_tsv_row(activity, session_key)

        bob_tsv_rows.append(row)

        if activity["has_photos"]:
            photos_dir = session_dir / "photos"
            photos_dir.mkdir(exist_ok=True)
            for i in range(activity["photo_count"]):
                (photos_dir / f"photo_{i+1}.jpg").write_bytes(PLACEHOLDER_JPEG)

    bob_tsv_rows.sort(key=lambda r: r["datetime"])
    with open(bob_dir / "sessions.tsv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sessions_columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(bob_tsv_rows)

    print(f"Created {len(bob_sessions)} sessions for bob")
    print(f"\nFixtures generated in: {output_dir}")
    print(f"Total: {len(alice_sessions) + len(bob_sessions)} sessions for 2 athletes")
    print(f"Shared run: {shared_run_key} (alice and bob)")


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    random.seed(42)  # Reproducible fixtures
    generate_fixtures(output)
