"""Backup orchestration service for strava-backup.

Handles incremental sync of Strava activities, including metadata,
GPS tracks, photos, comments, and kudos.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from strava_backup.config import Config, ensure_data_dir

logger = logging.getLogger("strava_backup.backup")
from strava_backup.lib.paths import (
    ensure_photos_dir,
    ensure_session_dir,
    format_session_datetime,
    get_photo_path,
)
from strava_backup.models.activity import (
    Activity,
    activity_exists,
    save_activity,
    update_sessions_tsv,
)
from strava_backup.models.athlete import Athlete, update_gear_from_strava
from strava_backup.models.state import load_sync_state, save_sync_state
from strava_backup.models.tracking import save_tracking_data
from strava_backup.services.strava import StravaClient

if TYPE_CHECKING:
    from collections.abc import Callable


class BackupService:
    """Service for backing up Strava activities."""

    def __init__(self, config: Config) -> None:
        """Initialize the backup service.

        Args:
            config: Application configuration.
        """
        self.config = config
        self.strava = StravaClient(config)
        self.data_dir = ensure_data_dir(config)

    def sync(
        self,
        full: bool = False,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int | None = None,
        activity_id_filter: list[int] | None = None,
        include_photos: bool = True,
        include_streams: bool = True,
        include_comments: bool = True,
        dry_run: bool = False,
        log_callback: Callable[[str, int], None] | None = None,
    ) -> dict[str, Any]:
        """Synchronize activities from Strava.

        Args:
            full: Force full sync, ignoring last sync time.
            after: Only sync activities after this date.
            before: Only sync activities before this date.
            limit: Maximum number of activities to sync.
            activity_id_filter: Only sync these specific activity IDs.
            include_photos: Download activity photos.
            include_streams: Download GPS/sensor streams.
            include_comments: Download comments and kudos.
            dry_run: Show what would be synced without downloading.
            log_callback: Optional callback for progress messages.

        Returns:
            Dictionary with sync results.
        """

        def log(msg: str, level: int = 0) -> None:
            if log_callback:
                log_callback(msg, level)

        logger.info("Starting sync")

        # Get athlete info
        logger.debug("Fetching athlete info")
        athlete_data = self.strava.get_athlete()
        athlete = Athlete.from_strava_athlete(athlete_data)
        username = athlete.username

        logger.info("Syncing for athlete: %s", username)
        log(f"Syncing activities for {username}...")

        # Load sync state
        state = load_sync_state(self.data_dir, username)

        # Determine sync window
        sync_after: float | None = None
        if after:
            sync_after = after.timestamp()
        elif not full and state.last_activity_date:
            # Sync from last activity date (with some overlap for safety)
            sync_after = state.last_activity_date.timestamp() - 86400  # 1 day overlap

        sync_before: float | None = None
        if before:
            sync_before = before.timestamp()

        # Fetch activities
        activities_synced = 0
        activities_new = 0
        activities_updated = 0
        photos_downloaded = 0
        errors: list[dict[str, str]] = []

        if dry_run:
            log("Dry run mode - no changes will be made")

        # Get activities from Strava
        logger.debug("Fetching activities (after=%s, before=%s, limit=%s)",
                     sync_after, sync_before, limit)
        activities = self.strava.get_activities(
            after=sync_after,
            before=sync_before,
            limit=limit,
        )

        activity_list = list(activities)

        # Filter by activity IDs if specified
        if activity_id_filter:
            logger.info("Filtering to activity IDs: %s", activity_id_filter)
            activity_list = [a for a in activity_list if a.id in activity_id_filter]

        total = len(activity_list)
        logger.info("Found %d activities to process", total)
        log(f"Found {total} activities to process")

        latest_activity_date: datetime | None = None

        for i, strava_activity in enumerate(activity_list, 1):
            try:
                logger.debug("[%d/%d] Processing activity %d", i, total, strava_activity.id)
                # Get detailed activity
                detailed = self.strava.get_activity(strava_activity.id)
                activity = Activity.from_strava_activity(detailed)
                logger.debug("Activity: %s (%s)", activity.name, activity.start_date)

                # Track latest activity
                if latest_activity_date is None or activity.start_date > latest_activity_date:
                    latest_activity_date = activity.start_date

                # Check if activity already exists
                is_new = not activity_exists(self.data_dir, username, activity.start_date)

                if dry_run:
                    status = "NEW" if is_new else "UPDATE"
                    log(f"  [{i}/{total}] {status}: {activity.name} ({format_session_datetime(activity.start_date)})")
                    activities_synced += 1
                    if is_new:
                        activities_new += 1
                    else:
                        activities_updated += 1
                    continue

                # Create session directory
                session_dir = ensure_session_dir(self.data_dir, username, activity.start_date)

                # Fetch and save streams
                if include_streams:
                    try:
                        logger.debug("Fetching streams for activity %d", activity.id)
                        streams = self.strava.get_activity_streams(activity.id)
                        if streams:
                            _, manifest = save_tracking_data(session_dir, streams)
                            activity.has_gps = manifest.has_gps
                            logger.debug("Saved tracking data (%d points, GPS=%s)",
                                        manifest.row_count, manifest.has_gps)
                            log(f"    Saved tracking data ({manifest.row_count} points)", 2)
                    except Exception as e:
                        logger.warning("Failed to get streams for activity %d: %s",
                                      activity.id, e, exc_info=True)
                        log(f"    Warning: Failed to get streams: {e}", 1)

                # Fetch photos
                if include_photos:
                    try:
                        logger.debug("Fetching photos for activity %d", activity.id)
                        photos = self.strava.get_activity_photos(activity.id)
                        if photos:
                            activity.photos = photos
                            activity.has_photos = True
                            activity.photo_count = len(photos)

                            # Download photos
                            downloaded = self._download_photos(
                                session_dir, photos, log
                            )
                            photos_downloaded += downloaded
                            logger.debug("Downloaded %d photos", downloaded)
                    except Exception as e:
                        logger.warning("Failed to get photos for activity %d: %s",
                                      activity.id, e)
                        log(f"    Warning: Failed to get photos: {e}", 1)

                # Fetch comments and kudos
                if include_comments:
                    try:
                        comments = self.strava.get_activity_comments(activity.id)
                        activity.comments = comments
                        activity.comment_count = len(comments)
                    except Exception:
                        pass

                    try:
                        kudos = self.strava.get_activity_kudos(activity.id)
                        activity.kudos = kudos
                        activity.kudos_count = len(kudos)
                    except Exception:
                        pass

                # Save activity metadata
                save_activity(self.data_dir, username, activity)

                activities_synced += 1
                if is_new:
                    activities_new += 1
                else:
                    activities_updated += 1

                distance_km = activity.distance / 1000 if activity.distance else 0
                log(f"  [{i}/{total}] {activity.name} ({format_session_datetime(activity.start_date)}) - {distance_km:.1f} km")

            except Exception as e:
                error_msg = str(e)
                logger.error("Error processing activity %d: %s",
                           strava_activity.id, error_msg, exc_info=True)
                errors.append({
                    "activity_id": str(strava_activity.id),
                    "error": error_msg,
                })
                log(f"  [{i}/{total}] Error: {error_msg}")

        # Update gear catalog
        if not dry_run:
            try:
                gear_list = self.strava.get_athlete_gear()
                if gear_list:
                    update_gear_from_strava(self.data_dir, username, gear_list)
                    log(f"Updated gear catalog ({len(gear_list)} items)", 1)
            except Exception as e:
                log(f"Warning: Failed to update gear: {e}", 1)

            # Update sessions.tsv
            update_sessions_tsv(self.data_dir, username)

            # Update sync state
            state.last_sync = datetime.now()
            if latest_activity_date:
                state.last_activity_date = latest_activity_date
            state.total_activities = activities_synced
            save_sync_state(self.data_dir, username, state)

        logger.info("Sync complete: %d activities (%d new, %d updated), %d photos, %d errors",
                   activities_synced, activities_new, activities_updated,
                   photos_downloaded, len(errors))

        return {
            "athlete": username,
            "activities_synced": activities_synced,
            "activities_new": activities_new,
            "activities_updated": activities_updated,
            "photos_downloaded": photos_downloaded,
            "errors": errors,
        }

    def _download_photos(
        self,
        session_dir: Path,
        photos: list[dict[str, Any]],
        log: Callable[[str, int], None],
    ) -> int:
        """Download photos for an activity.

        Args:
            session_dir: Session partition directory.
            photos: List of photo metadata.
            log: Logging callback.

        Returns:
            Number of photos downloaded.
        """
        if not photos:
            return 0

        photos_dir = ensure_photos_dir(session_dir)
        downloaded = 0

        for photo in photos:
            urls = photo.get("urls", {})
            if not urls:
                continue

            # Get the largest available size
            url = None
            for size in ["2048", "1024", "600", "256"]:
                if size in urls:
                    url = urls[size]
                    break

            if not url:
                continue

            # Determine photo timestamp and filename
            created_at = photo.get("created_at")
            if created_at:
                try:
                    if isinstance(created_at, str):
                        photo_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    else:
                        photo_dt = created_at
                except (ValueError, TypeError):
                    photo_dt = datetime.now()
            else:
                photo_dt = datetime.now()

            # Determine extension from URL or default to jpg
            ext = "jpg"
            if ".png" in url.lower():
                ext = "png"

            photo_path = get_photo_path(photos_dir, photo_dt, ext)

            # Skip if already downloaded
            if photo_path.exists():
                continue

            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                with open(photo_path, "wb") as f:
                    f.write(response.content)

                downloaded += 1
                log(f"    Downloaded photo: {photo_path.name}", 2)

            except Exception as e:
                log(f"    Warning: Failed to download photo: {e}", 1)

            # Small delay to be nice to servers
            time.sleep(0.1)

        return downloaded

    def sync_single_activity(
        self,
        activity_id: int,
        username: str,
        include_photos: bool = True,
        include_streams: bool = True,
        include_comments: bool = True,
    ) -> Activity:
        """Sync a single activity by ID.

        Args:
            activity_id: Strava activity ID.
            username: Athlete username.
            include_photos: Download photos.
            include_streams: Download streams.
            include_comments: Download comments/kudos.

        Returns:
            Synced Activity instance.
        """
        # Get detailed activity
        detailed = self.strava.get_activity(activity_id)
        activity = Activity.from_strava_activity(detailed)

        # Create session directory
        session_dir = ensure_session_dir(self.data_dir, username, activity.start_date)

        # Fetch and save streams
        if include_streams:
            streams = self.strava.get_activity_streams(activity.id)
            if streams:
                _, manifest = save_tracking_data(session_dir, streams)
                activity.has_gps = manifest.has_gps

        # Fetch photos
        if include_photos:
            photos = self.strava.get_activity_photos(activity.id)
            if photos:
                activity.photos = photos
                activity.has_photos = True
                activity.photo_count = len(photos)
                self._download_photos(session_dir, photos, lambda _msg, _lvl: None)

        # Fetch comments and kudos
        if include_comments:
            activity.comments = self.strava.get_activity_comments(activity.id)
            activity.comment_count = len(activity.comments)
            activity.kudos = self.strava.get_activity_kudos(activity.id)
            activity.kudos_count = len(activity.kudos)

        # Save activity
        save_activity(self.data_dir, username, activity)

        return activity
