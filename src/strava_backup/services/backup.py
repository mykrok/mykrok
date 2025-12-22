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
from strava_backup.models.state import (
    FailureType,
    load_retry_queue,
    load_sync_state,
    save_retry_queue,
    save_sync_state,
)
from strava_backup.models.tracking import save_tracking_data
from strava_backup.services.strava import StravaClient

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger("strava_backup.backup")


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

        # Load sync state and retry queue
        state = load_sync_state(self.data_dir, username)
        retry_queue = load_retry_queue(self.data_dir, username)

        # Determine sync window
        sync_after: float | None = None
        if after:
            sync_after = after.timestamp()
        elif not full and state.last_activity_date:
            # Use last activity date as cutoff
            # Only add overlap if last sync was more than 1 day ago (to catch late uploads)
            sync_after = state.last_activity_date.timestamp()
            if (
                state.last_sync is None
                or (datetime.now() - state.last_sync).total_seconds() > 86400
            ):
                # Add 1-day overlap for safety when sync hasn't run recently
                sync_after -= 86400
                logger.debug("Adding 1-day overlap (last sync was old or never ran)")

        sync_before: float | None = None
        if before:
            sync_before = before.timestamp()

        # Fetch activities
        activities_synced = 0
        activities_new = 0
        activities_updated = 0
        photos_downloaded = 0
        errors: list[dict[str, Any]] = []

        if dry_run:
            log("Dry run mode - no changes will be made")

        # Get activities from Strava
        logger.debug(
            "Fetching activities (after=%s, before=%s, limit=%s)", sync_after, sync_before, limit
        )
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

        # Add activities from retry queue that are due for retry
        due_retries = retry_queue.get_due_retries()
        retry_activity_ids = {f.activity_id for f in due_retries}
        existing_activity_ids = {a.id for a in activity_list}

        # Only add retry activities that aren't already in the list
        retry_ids_to_add = retry_activity_ids - existing_activity_ids
        if retry_ids_to_add:
            logger.info("Adding %d activities from retry queue", len(retry_ids_to_add))
            log(f"Retrying {len(retry_ids_to_add)} previously failed activities...")

        total = len(activity_list)
        retry_count = len(retry_ids_to_add)
        logger.info(
            "Found %d activities to process (%d new/updated, %d retries)",
            total + retry_count,
            total,
            retry_count,
        )
        log(
            f"Found {total} activities to process"
            + (f" + {retry_count} retries" if retry_count else "")
        )

        latest_activity_date: datetime | None = None
        retries_succeeded = 0
        retries_failed = 0

        # Process regular activities first
        for i, strava_activity in enumerate(activity_list, 1):
            activity_id = strava_activity.id
            is_retry = activity_id in retry_activity_ids

            try:
                logger.debug(
                    "[%d/%d] Processing activity %d%s",
                    i,
                    total,
                    activity_id,
                    " (retry)" if is_retry else "",
                )
                # Get detailed activity
                detailed = self.strava.get_activity(activity_id)
                activity = Activity.from_strava_activity(detailed)
                logger.debug("Activity: %s (%s)", activity.name, activity.start_date)

                # Track latest activity
                if latest_activity_date is None or activity.start_date > latest_activity_date:
                    latest_activity_date = activity.start_date

                # Check if activity already exists
                is_new = not activity_exists(self.data_dir, username, activity.start_date)

                if dry_run:
                    status = "NEW" if is_new else "UPDATE"
                    log(
                        f"  [{i}/{total}] {status}: {activity.name} ({format_session_datetime(activity.start_date)})"
                    )
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
                            logger.debug(
                                "Saved tracking data (%d points, GPS=%s)",
                                manifest.row_count,
                                manifest.has_gps,
                            )
                            log(f"    Saved tracking data ({manifest.row_count} points)", 2)
                    except Exception as e:
                        logger.warning(
                            "Failed to get streams for activity %d: %s",
                            activity.id,
                            e,
                            exc_info=True,
                        )
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
                            downloaded = self._download_photos(session_dir, photos, log)
                            photos_downloaded += downloaded
                            logger.debug("Downloaded %d photos", downloaded)
                    except Exception as e:
                        logger.warning("Failed to get photos for activity %d: %s", activity.id, e)
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

                # Remove from retry queue if this was a retry
                if is_retry:
                    retry_queue.remove(activity_id)
                    retries_succeeded += 1
                    logger.info("Retry succeeded for activity %d", activity_id)

                distance_km = activity.distance / 1000 if activity.distance else 0
                retry_marker = " [RETRY OK]" if is_retry else ""
                log(
                    f"  [{i}/{total}] {activity.name} ({format_session_datetime(activity.start_date)}) - {distance_km:.1f} km{retry_marker}"
                )

            except Exception as e:
                error_msg = str(e)
                logger.error(
                    "Error processing activity %d: %s", activity_id, error_msg, exc_info=True
                )

                # Add to retry queue (or update existing entry)
                failure_entry = retry_queue.add_failure(activity_id, e)
                failure_type = FailureType.from_error(e)

                if is_retry:
                    retries_failed += 1

                errors.append(
                    {
                        "activity_id": str(activity_id),
                        "error": error_msg,
                        "failure_type": failure_type.value,
                        "retry_count": failure_entry.retry_count,
                        "next_retry": failure_entry.next_retry_after.isoformat()
                        if failure_entry.next_retry_after
                        else None,
                    }
                )

                retry_info = ""
                if failure_entry.next_retry_after:
                    retry_info = (
                        f" (will retry after {failure_entry.next_retry_after.strftime('%H:%M:%S')})"
                    )
                elif failure_entry.is_permanently_failed():
                    retry_info = " (no more retries)"

                log(f"  [{i}/{total}] Error: {error_msg}{retry_info}")

        # Process retry-only activities (not in the regular activity list)
        if retry_ids_to_add and not dry_run:
            log(f"Processing {len(retry_ids_to_add)} retry-only activities...")
            for retry_activity_id in retry_ids_to_add:
                try:
                    logger.debug("Processing retry activity %d", retry_activity_id)

                    # Get detailed activity
                    detailed = self.strava.get_activity(retry_activity_id)
                    activity = Activity.from_strava_activity(detailed)

                    # Track latest activity
                    if latest_activity_date is None or activity.start_date > latest_activity_date:
                        latest_activity_date = activity.start_date

                    # Create session directory
                    session_dir = ensure_session_dir(self.data_dir, username, activity.start_date)

                    # Fetch and save streams
                    if include_streams:
                        try:
                            streams = self.strava.get_activity_streams(activity.id)
                            if streams:
                                _, manifest = save_tracking_data(session_dir, streams)
                                activity.has_gps = manifest.has_gps
                        except Exception as e:
                            logger.warning(
                                "Failed to get streams for activity %d: %s", activity.id, e
                            )

                    # Fetch photos
                    if include_photos:
                        try:
                            photos = self.strava.get_activity_photos(activity.id)
                            if photos:
                                activity.photos = photos
                                activity.has_photos = True
                                activity.photo_count = len(photos)
                                photos_downloaded += self._download_photos(session_dir, photos, log)
                        except Exception as e:
                            logger.warning(
                                "Failed to get photos for activity %d: %s", activity.id, e
                            )

                    # Fetch comments and kudos
                    if include_comments:
                        try:
                            activity.comments = self.strava.get_activity_comments(activity.id)
                            activity.comment_count = len(activity.comments)
                        except Exception:
                            pass
                        try:
                            activity.kudos = self.strava.get_activity_kudos(activity.id)
                            activity.kudos_count = len(activity.kudos)
                        except Exception:
                            pass

                    # Save activity
                    save_activity(self.data_dir, username, activity)
                    activities_synced += 1
                    activities_new += 1

                    # Remove from retry queue
                    retry_queue.remove(retry_activity_id)
                    retries_succeeded += 1
                    logger.info("Retry succeeded for activity %d", retry_activity_id)

                    distance_km = activity.distance / 1000 if activity.distance else 0
                    log(
                        f"  [RETRY] {activity.name} ({format_session_datetime(activity.start_date)}) - {distance_km:.1f} km [OK]"
                    )

                except Exception as e:
                    error_msg = str(e)
                    logger.error(
                        "Error processing retry activity %d: %s",
                        retry_activity_id,
                        error_msg,
                        exc_info=True,
                    )

                    # Update retry queue entry
                    failure_entry = retry_queue.add_failure(retry_activity_id, e)
                    retries_failed += 1

                    errors.append(
                        {
                            "activity_id": str(retry_activity_id),
                            "error": error_msg,
                            "failure_type": FailureType.from_error(e).value,
                            "retry_count": failure_entry.retry_count,
                            "next_retry": failure_entry.next_retry_after.isoformat()
                            if failure_entry.next_retry_after
                            else None,
                        }
                    )

                    retry_info = ""
                    if failure_entry.next_retry_after:
                        retry_info = f" (will retry after {failure_entry.next_retry_after.strftime('%H:%M:%S')})"
                    elif failure_entry.is_permanently_failed():
                        retry_info = " (no more retries)"

                    log(f"  [RETRY] Error: {error_msg}{retry_info}")

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

            # Save retry queue
            save_retry_queue(self.data_dir, username, retry_queue)

            # Report retry queue status
            pending_retries = retry_queue.get_pending_count()
            if pending_retries > 0:
                log(f"Retry queue: {pending_retries} activities pending retry", 1)
                # Show next retry time
                due = retry_queue.get_due_retries()
                if not due and retry_queue.failed_activities:
                    next_retry = min(
                        (
                            f.next_retry_after
                            for f in retry_queue.failed_activities
                            if f.next_retry_after
                        ),
                        default=None,
                    )
                    if next_retry:
                        log(
                            f"  Next retry scheduled for: {next_retry.strftime('%Y-%m-%d %H:%M:%S')}",
                            1,
                        )

        logger.info(
            "Sync complete: %d activities (%d new, %d updated), %d photos, %d errors, "
            "%d retries succeeded, %d retries failed, %d pending",
            activities_synced,
            activities_new,
            activities_updated,
            photos_downloaded,
            len(errors),
            retries_succeeded,
            retries_failed,
            retry_queue.get_pending_count(),
        )

        return {
            "athlete": username,
            "activities_synced": activities_synced,
            "activities_new": activities_new,
            "activities_updated": activities_updated,
            "photos_downloaded": photos_downloaded,
            "errors": errors,
            "retries_succeeded": retries_succeeded,
            "retries_failed": retries_failed,
            "pending_retries": retry_queue.get_pending_count(),
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

    def refresh_social(
        self,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int | None = None,
        dry_run: bool = False,
        log_callback: Callable[[str, int], None] | None = None,
    ) -> dict[str, Any]:
        """Refresh comments and kudos for existing activities.

        This method only updates social metadata (kudos, comments) for activities
        that already exist locally. It does not fetch new activities, GPS streams,
        or photos. Useful for fixing missing athlete_id values or updating
        social data after a bug fix.

        Args:
            after: Only refresh activities after this date.
            before: Only refresh activities before this date.
            limit: Maximum number of activities to refresh.
            dry_run: If True, only report what would be done.
            log_callback: Optional callback for logging.

        Returns:
            Dictionary with refresh results.
        """
        log = log_callback or (lambda _msg, _lvl: None)

        logger.info("Refreshing social data")
        log("Refreshing social data for existing activities", 0)

        # Get athlete info
        logger.debug("Fetching athlete info")
        log("Fetching athlete info", 1)
        athlete = Athlete.from_strava_athlete(self.strava.get_athlete())
        username = athlete.username

        # Iterate over existing sessions
        from strava_backup.lib.paths import (
            get_athlete_dir,
            iter_session_dirs,
            parse_session_datetime,
        )
        from strava_backup.models.activity import load_activity

        athlete_dir = get_athlete_dir(self.data_dir, username)
        activities_updated = 0
        errors: list[dict[str, Any]] = []

        log(f"Scanning activities for {username}", 1)

        processed = 0
        for session_key, session_dir in iter_session_dirs(athlete_dir):
            # Apply date filters
            try:
                session_dt = parse_session_datetime(session_key)
                if after and session_dt < after:
                    continue
                if before and session_dt > before:
                    continue
            except ValueError:
                continue

            # Apply limit
            if limit and processed >= limit:
                break

            # Load existing activity
            activity = load_activity(session_dir)
            if activity is None:
                continue

            processed += 1
            log(f"  [{processed}] {activity.name} ({session_key})", 1)

            if dry_run:
                continue

            # Fetch fresh comments and kudos
            try:
                from strava_backup.services.strava import StravaRateLimitError

                new_comments = self.strava.get_activity_comments(activity.id)
                new_kudos = self.strava.get_activity_kudos(activity.id)

                # Update activity
                activity.comments = new_comments
                activity.comment_count = len(new_comments)
                activity.kudos = new_kudos
                activity.kudos_count = len(new_kudos)

                # Save updated activity
                save_activity(self.data_dir, username, activity)
                activities_updated += 1

                # Small delay to be nice to API
                time.sleep(0.2)

            except StravaRateLimitError as e:
                # Rate limit hit - stop processing to avoid data loss
                logger.warning("Rate limit exceeded, stopping refresh: %s", e)
                log("Rate limit exceeded - stopping to preserve data", 0)
                errors.append(
                    {
                        "session": session_key,
                        "activity_id": activity.id,
                        "error": f"Rate limit: {e}",
                    }
                )
                break  # Stop processing more activities

            except Exception as e:
                logger.warning("Failed to refresh social data for %s: %s", session_key, e)
                errors.append(
                    {
                        "session": session_key,
                        "activity_id": activity.id,
                        "error": str(e),
                    }
                )

        # Update sessions.tsv
        if activities_updated > 0 and not dry_run:
            update_sessions_tsv(self.data_dir, username)
            log("Updated sessions.tsv", 1)

        return {
            "activities_updated": activities_updated,
            "activities_scanned": processed,
            "errors": errors,
        }

    def refresh_athlete_profiles(
        self,
        dry_run: bool = False,
        log_callback: Callable[[str, int], None] | None = None,
    ) -> dict[str, Any]:
        """Refresh athlete profile information and avatars.

        Downloads profile data (name, location) and avatar photos for all
        athletes in the backup. Currently only supports the authenticated athlete.

        Args:
            dry_run: If True, only report what would be done.
            log_callback: Optional callback for logging.

        Returns:
            Dictionary with refresh results.
        """
        from strava_backup.lib.paths import get_athlete_dir, get_avatar_path
        from strava_backup.models.athlete import (
            get_existing_avatar_path,
            save_athlete_profile,
        )
        from strava_backup.services.migrate import generate_athletes_tsv

        log = log_callback or (lambda _msg, _lvl: None)

        logger.info("Refreshing athlete profiles")
        log("Refreshing athlete profiles", 0)

        # Get authenticated athlete info
        logger.debug("Fetching athlete info from Strava")
        strava_athlete = self.strava.get_athlete()
        athlete = Athlete.from_strava_athlete(strava_athlete)

        log(f"  {athlete.username}: {athlete.firstname} {athlete.lastname}", 1)
        if athlete.city or athlete.country:
            location = ", ".join(filter(None, [athlete.city, athlete.country]))
            log(f"    Location: {location}", 1)

        profiles_updated = 0
        avatars_downloaded = 0
        errors: list[dict[str, Any]] = []

        if dry_run:
            log("Dry run - no changes made", 1)
            return {
                "profiles_updated": 0,
                "avatars_downloaded": 0,
                "errors": [],
            }

        # Save athlete profile
        try:
            save_athlete_profile(self.data_dir, athlete)
            profiles_updated += 1
            log("    Saved profile to athlete.json", 1)
        except Exception as e:
            logger.warning("Failed to save athlete profile: %s", e)
            errors.append(
                {
                    "username": athlete.username,
                    "error": str(e),
                    "type": "profile",
                }
            )

        # Download avatar if profile_url is available
        if athlete.profile_url:
            athlete_dir = get_athlete_dir(self.data_dir, athlete.username)

            # Determine extension from URL
            ext = "jpg"
            url_lower = athlete.profile_url.lower()
            if ".png" in url_lower:
                ext = "png"
            elif ".gif" in url_lower:
                ext = "gif"
            elif ".webp" in url_lower:
                ext = "webp"

            avatar_path = get_avatar_path(athlete_dir, ext)

            # Remove old avatar with different extension if exists
            existing_avatar = get_existing_avatar_path(athlete_dir)
            if existing_avatar and existing_avatar != avatar_path:
                try:
                    existing_avatar.unlink()
                    log(f"    Removed old avatar: {existing_avatar.name}", 1)
                except OSError:
                    pass

            try:
                response = requests.get(athlete.profile_url, timeout=30)
                response.raise_for_status()

                with open(avatar_path, "wb") as f:
                    f.write(response.content)

                avatars_downloaded += 1
                log(f"    Downloaded avatar: {avatar_path.name}", 1)

            except Exception as e:
                logger.warning("Failed to download avatar: %s", e)
                errors.append(
                    {
                        "username": athlete.username,
                        "error": str(e),
                        "type": "avatar",
                    }
                )

        # Regenerate athletes.tsv with updated profile info
        try:
            generate_athletes_tsv(self.data_dir)
            log("Updated athletes.tsv", 1)
        except Exception as e:
            logger.warning("Failed to update athletes.tsv: %s", e)
            errors.append(
                {
                    "error": str(e),
                    "type": "athletes_tsv",
                }
            )

        return {
            "profiles_updated": profiles_updated,
            "avatars_downloaded": avatars_downloaded,
            "errors": errors,
        }

    def check_and_fix(
        self,
        dry_run: bool = False,
        log_callback: Callable[[str, int], None] | None = None,
    ) -> dict[str, Any]:
        """Check data integrity and fix missing items.

        Iterates through all local sessions and verifies:
        - Photos exist if has_photos=True and photo_count > 0
        - Tracking data exists if has_gps=True
        - Parquet files are readable

        Missing data is re-fetched from Strava API.

        Args:
            dry_run: If True, only report what would be fixed.
            log_callback: Optional callback for logging.

        Returns:
            Dictionary with check/fix results.
        """
        import pyarrow.parquet as pq

        from strava_backup.lib.paths import (
            get_athlete_dir,
            iter_session_dirs,
        )
        from strava_backup.models.activity import load_activity

        log = log_callback or (lambda _msg, _lvl: None)

        logger.info("Running data integrity check")
        log("Checking data integrity for all sessions", 0)

        # Get athlete info
        logger.debug("Fetching athlete info")
        athlete = Athlete.from_strava_athlete(self.strava.get_athlete())
        username = athlete.username

        athlete_dir = get_athlete_dir(self.data_dir, username)
        if not athlete_dir.exists():
            log(f"No data found for athlete {username}", 1)
            return {
                "sessions_checked": 0,
                "issues_found": 0,
                "issues_fixed": 0,
                "errors": [],
            }

        sessions_checked = 0
        issues_found = 0
        issues_fixed = 0
        errors: list[dict[str, Any]] = []

        issues_detail: list[dict[str, Any]] = []

        log(f"Scanning sessions for {username}", 1)

        for session_key, session_dir in iter_session_dirs(athlete_dir):
            sessions_checked += 1

            # Load activity metadata
            activity = load_activity(session_dir)
            if activity is None:
                issues_found += 1
                issues_detail.append(
                    {
                        "session": session_key,
                        "issue": "missing_info_json",
                        "fixed": False,
                    }
                )
                log(f"  [{session_key}] Missing info.json", 1)
                continue

            session_issues: list[str] = []

            # Check photos
            if activity.has_photos and activity.photo_count and activity.photo_count > 0:
                photos_dir = session_dir / "photos"
                if not photos_dir.exists():
                    session_issues.append("missing_photos_dir")
                else:
                    photo_files = list(photos_dir.glob("*.jpg")) + list(photos_dir.glob("*.png"))
                    if len(photo_files) < activity.photo_count:
                        session_issues.append(
                            f"missing_photos({len(photo_files)}/{activity.photo_count})"
                        )

            # Check tracking data
            if activity.has_gps:
                tracking_file = session_dir / "tracking.parquet"
                if not tracking_file.exists():
                    session_issues.append("missing_tracking")
                else:
                    # Verify parquet is readable
                    try:
                        pq.read_table(tracking_file)
                    except Exception:
                        session_issues.append("corrupted_tracking")

            if not session_issues:
                continue

            issues_found += len(session_issues)
            log(f"  [{session_key}] Issues: {', '.join(session_issues)}", 1)

            for issue in session_issues:
                issues_detail.append(
                    {
                        "session": session_key,
                        "activity_id": activity.id,
                        "issue": issue,
                        "fixed": False,
                    }
                )

            if dry_run:
                continue

            # Attempt to fix issues
            try:
                fixed_issues: list[str] = []

                # Re-fetch photos if missing
                if any("photos" in i for i in session_issues):
                    try:
                        photos = self.strava.get_activity_photos(activity.id)
                        if photos:
                            activity.photos = photos
                            downloaded = self._download_photos(
                                session_dir, photos, lambda _m, _l: None
                            )
                            if downloaded > 0:
                                fixed_issues.append(f"photos({downloaded})")
                                log(f"    Fixed: Downloaded {downloaded} photos", 2)
                    except Exception as e:
                        logger.warning("Failed to re-fetch photos: %s", e)
                        errors.append(
                            {
                                "session": session_key,
                                "issue": "photos",
                                "error": str(e),
                            }
                        )

                # Re-fetch tracking data if missing/corrupted
                if any("tracking" in i for i in session_issues):
                    try:
                        streams = self.strava.get_activity_streams(activity.id)
                        if streams:
                            _, manifest = save_tracking_data(session_dir, streams)
                            activity.has_gps = manifest.has_gps
                            fixed_issues.append("tracking")
                            log(f"    Fixed: Saved tracking data ({manifest.row_count} points)", 2)
                    except Exception as e:
                        logger.warning("Failed to re-fetch tracking: %s", e)
                        errors.append(
                            {
                                "session": session_key,
                                "issue": "tracking",
                                "error": str(e),
                            }
                        )

                if fixed_issues:
                    issues_fixed += len(fixed_issues)
                    # Update activity info.json
                    save_activity(self.data_dir, username, activity)

                # Mark issues as fixed in detail
                for detail in issues_detail:
                    if detail["session"] == session_key and any(
                        detail["issue"].startswith(f) for f in fixed_issues
                    ):
                        detail["fixed"] = True

                # Rate limiting
                time.sleep(0.2)

            except Exception as e:
                logger.error("Error fixing session %s: %s", session_key, e)
                errors.append(
                    {
                        "session": session_key,
                        "error": str(e),
                    }
                )

        # Update sessions.tsv if fixes were made
        if issues_fixed > 0 and not dry_run:
            update_sessions_tsv(self.data_dir, username)
            log("Updated sessions.tsv", 1)

        log(
            f"Check complete: {sessions_checked} sessions, "
            f"{issues_found} issues found, {issues_fixed} fixed",
            0,
        )

        return {
            "sessions_checked": sessions_checked,
            "issues_found": issues_found,
            "issues_fixed": issues_fixed,
            "issues": issues_detail,
            "errors": errors,
        }
