"""FitTrackee export service for MyKrok.

Handles exporting activities to self-hosted FitTrackee instances
with sport type mapping and incremental sync.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from mykrok.lib.gpx import generate_gpx, get_gpx_size
from mykrok.lib.paths import (
    iter_athlete_dirs,
    iter_session_dirs,
    parse_session_datetime,
)
from mykrok.models.activity import load_activity
from mykrok.models.state import (
    load_fittrackee_export_state,
    save_fittrackee_export_state,
)
from mykrok.models.tracking import load_tracking_manifest
from mykrok.services.rate_limiter import create_fittrackee_limiter

if TYPE_CHECKING:
    from collections.abc import Callable


# Strava to FitTrackee sport type mapping
# FitTrackee sport IDs: https://samr1.github.io/FitTrackee/en/api/workouts.html
SPORT_TYPE_MAPPING: dict[str, int] = {
    # Running
    "Run": 1,
    "VirtualRun": 1,
    "TrailRun": 1,
    # Cycling
    "Ride": 2,
    "VirtualRide": 2,
    "EBikeRide": 2,
    "MountainBikeRide": 7,  # Mountain Biking
    "GravelRide": 2,
    # Walking/Hiking
    "Hike": 4,  # Hiking
    "Walk": 3,  # Walking
    # Swimming
    "Swim": 8,
    # Other
    "Workout": 9,  # Workout (General)
    "WeightTraining": 10,
}

# Fallback sport ID for unmapped types
DEFAULT_SPORT_ID = 9  # Workout (General)

# FitTrackee GPX file size limit (default 1MB)
MAX_GPX_SIZE = 1024 * 1024


class FitTrackeeExporter:
    """Service for exporting activities to FitTrackee."""

    def __init__(
        self,
        data_dir: Path,
        url: str,
        email: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize the FitTrackee exporter.

        Args:
            data_dir: Base data directory.
            url: FitTrackee instance URL.
            email: FitTrackee account email.
            password: FitTrackee account password.
        """
        self.data_dir = data_dir
        self.url = url.rstrip("/")
        self.email = email
        self.password = password
        self._token: str | None = None
        self._rate_limiter = create_fittrackee_limiter()

    def _authenticate(self) -> str:
        """Authenticate with FitTrackee and get bearer token.

        Returns:
            Bearer token.

        Raises:
            ValueError: If credentials are missing.
            RuntimeError: If authentication fails.
        """
        if self._token:
            return self._token

        if not self.email or not self.password:
            raise ValueError("FitTrackee email and password are required")

        response = requests.post(
            f"{self.url}/api/auth/login",
            json={"email": self.email, "password": self.password},
            timeout=30,
        )

        if response.status_code != 200:
            raise RuntimeError(f"FitTrackee authentication failed: {response.text}")

        data = response.json()
        self._token = data.get("auth_token")

        if not self._token:
            raise RuntimeError("No auth token in FitTrackee response")

        return self._token

    def _get_headers(self) -> dict[str, str]:
        """Get authorization headers."""
        token = self._authenticate()
        return {"Authorization": f"Bearer {token}"}

    def export(
        self,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int | None = None,
        force: bool = False,
        dry_run: bool = False,
        log_callback: Callable[[str, int], None] | None = None,
    ) -> dict[str, Any]:
        """Export activities to FitTrackee.

        Args:
            after: Only export activities after this date.
            before: Only export activities before this date.
            limit: Maximum number of activities to export.
            force: Re-export already exported activities.
            dry_run: Show what would be exported without uploading.
            log_callback: Optional callback for progress messages.

        Returns:
            Dictionary with export results.
        """

        def log(msg: str, level: int = 0) -> None:
            if log_callback:
                log_callback(msg, level)

        exported = 0
        skipped = 0
        failed = 0
        details: list[dict[str, Any]] = []

        # Process each athlete
        for username, athlete_dir in iter_athlete_dirs(self.data_dir):
            # Load export state
            state = load_fittrackee_export_state(self.data_dir, username)
            state.fittrackee_url = self.url

            activities_processed = 0

            for session_key, session_dir in iter_session_dirs(athlete_dir):
                if limit and activities_processed >= limit:
                    break

                # Filter by date
                try:
                    session_date = parse_session_datetime(session_key)
                except ValueError:
                    continue

                if after and session_date < after:
                    continue
                if before and session_date > before:
                    continue

                # Check if already exported
                if not force and state.is_exported(session_key):
                    skipped += 1
                    details.append(
                        {
                            "ses": session_key,
                            "status": "skipped",
                            "reason": "already_exported",
                        }
                    )
                    continue

                # Check for GPS data
                manifest = load_tracking_manifest(session_dir)
                if not manifest or not manifest.has_gps:
                    skipped += 1
                    details.append(
                        {
                            "ses": session_key,
                            "status": "skipped",
                            "reason": "no_gps",
                        }
                    )
                    log(f"  Skipping {session_key} (no GPS data)", 1)
                    continue

                # Load activity
                activity = load_activity(session_dir)
                if not activity:
                    skipped += 1
                    continue

                activities_processed += 1

                if dry_run:
                    sport_id = self._get_sport_id(activity.type)
                    log(f"  Would export: {activity.name} ({session_key}) as sport_id={sport_id}")
                    details.append(
                        {
                            "ses": session_key,
                            "status": "would_export",
                            "sport_id": sport_id,
                        }
                    )
                    continue

                # Export to FitTrackee
                try:
                    workout_id = self._upload_activity(session_dir, activity)
                    exported += 1

                    # Record export
                    state.record_export(session_key, workout_id)
                    save_fittrackee_export_state(self.data_dir, username, state)

                    details.append(
                        {
                            "ses": session_key,
                            "ft_workout_id": workout_id,
                            "status": "exported",
                        }
                    )
                    log(f"  Exported: {activity.name} ({session_key}) -> workout_id={workout_id}")

                except Exception as e:
                    failed += 1
                    details.append(
                        {
                            "ses": session_key,
                            "status": "failed",
                            "error": str(e),
                        }
                    )
                    log(f"  Failed: {activity.name} ({session_key}) - {e}")

        return {
            "exported": exported,
            "skipped": skipped,
            "failed": failed,
            "details": details,
        }

    def _upload_activity(self, session_dir: Path, activity: Any) -> int:
        """Upload a single activity to FitTrackee.

        Args:
            session_dir: Session partition directory.
            activity: Activity object.

        Returns:
            FitTrackee workout ID.
        """
        # Generate GPX
        gpx_content = generate_gpx(
            session_dir,
            include_hr=True,
            include_cadence=True,
            include_power=True,
        )

        # Check size and simplify if needed
        gpx_size = get_gpx_size(gpx_content)
        if gpx_size > MAX_GPX_SIZE:
            # TODO: Implement track simplification
            # For now, just warn
            pass

        # Get sport ID
        sport_id = self._get_sport_id(activity.type)

        # Prepare upload data
        title = activity.name[:255] if activity.name else "Activity"
        notes = (activity.description or "")[:500]

        # Wait for rate limit
        self._rate_limiter.acquire()

        # Upload to FitTrackee
        files = {"file": ("activity.gpx", gpx_content.encode("utf-8"), "application/gpx+xml")}
        data = {"data": f'{{"sport_id": {sport_id}, "title": "{title}", "notes": "{notes}"}}'}

        response = requests.post(
            f"{self.url}/api/workouts",
            headers=self._get_headers(),
            files=files,
            data=data,
            timeout=60,
        )

        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"FitTrackee upload failed: {response.status_code} - {response.text}"
            )

        result = response.json()

        # Extract workout ID from response
        if "data" in result and "workouts" in result["data"]:
            workouts = result["data"]["workouts"]
            if workouts:
                return int(workouts[0]["id"])

        raise RuntimeError("No workout ID in FitTrackee response")

    def _get_sport_id(self, strava_type: str) -> int:
        """Map Strava activity type to FitTrackee sport ID.

        Args:
            strava_type: Strava activity type.

        Returns:
            FitTrackee sport ID.
        """
        return SPORT_TYPE_MAPPING.get(strava_type, DEFAULT_SPORT_ID)

    def get_sport_mapping(self) -> dict[str, dict[str, Any]]:
        """Get the sport type mapping for reference.

        Returns:
            Dictionary of Strava type -> FitTrackee info.
        """
        return {
            strava_type: {
                "fittrackee_id": sport_id,
            }
            for strava_type, sport_id in SPORT_TYPE_MAPPING.items()
        }
