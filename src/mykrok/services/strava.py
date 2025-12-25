"""Strava API client for MyKrok.

Wraps stravalib to provide OAuth2 handling, automatic token refresh,
and rate limiting for Strava API operations.
"""

from __future__ import annotations

import logging
import os
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

# Silence stravalib warnings about environment variables
# We read credentials from config file, not environment
os.environ.setdefault("SILENCE_TOKEN_WARNINGS", "true")

from stravalib import Client
from stravalib.util.limiter import DefaultRateLimiter

from mykrok.config import Config, save_tokens

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger("mykrok.strava")

# OAuth2 scopes we request
OAUTH_SCOPES = ["read", "activity:read_all", "profile:read_all"]


class StravaRateLimitError(Exception):
    """Raised when Strava API rate limit is exceeded."""

    pass


@dataclass
class TokenInfo:
    """OAuth2 token information."""

    access_token: str
    refresh_token: str
    expires_at: int

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired or about to expire."""
        return time.time() >= self.expires_at - 60  # 1 minute buffer


class StravaClient:
    """High-level Strava API client with automatic token refresh."""

    def __init__(self, config: Config) -> None:
        """Initialize the Strava client.

        Args:
            config: Application configuration.
        """
        self.config = config
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        """Get or create the stravalib client.

        Returns:
            Configured stravalib Client.

        Raises:
            ValueError: If not authenticated.
        """
        if self._client is not None:
            return self._client

        if not self.config.strava.access_token:
            raise ValueError("Not authenticated. Run 'mykrok auth' first.")

        # Check if token needs refresh
        if self._token_needs_refresh():
            self._refresh_token()

        self._client = Client(
            access_token=self.config.strava.access_token,
            rate_limiter=DefaultRateLimiter(priority="medium"),
        )
        return self._client

    def _token_needs_refresh(self) -> bool:
        """Check if the access token needs to be refreshed."""
        if not self.config.strava.token_expires_at:
            return True
        return time.time() >= self.config.strava.token_expires_at - 60

    def _refresh_token(self) -> None:
        """Refresh the OAuth access token."""
        if not self.config.strava.refresh_token:
            raise ValueError("No refresh token available. Re-authenticate.")

        temp_client = Client()
        token_response = temp_client.refresh_access_token(
            client_id=int(self.config.strava.client_id),
            client_secret=self.config.strava.client_secret,
            refresh_token=self.config.strava.refresh_token,
        )

        # Save new tokens
        save_tokens(
            self.config,
            access_token=token_response["access_token"],
            refresh_token=token_response["refresh_token"],
            expires_at=token_response["expires_at"],
        )

    def get_athlete(self) -> Any:
        """Get the authenticated athlete's profile.

        Returns:
            Athlete object from stravalib.
        """
        return self.client.get_athlete()

    def get_activities(
        self,
        after: float | None = None,
        before: float | None = None,
        limit: int | None = None,
    ) -> Iterator[Any]:
        """Get athlete's activities.

        Args:
            after: Return activities after this timestamp (Unix epoch).
            before: Return activities before this timestamp (Unix epoch).
            limit: Maximum number of activities to return.

        Yields:
            Activity objects from stravalib.
        """
        from datetime import datetime, timezone

        # Convert timestamps to datetime objects for stravalib
        after_dt = datetime.fromtimestamp(after, tz=timezone.utc) if after else None
        before_dt = datetime.fromtimestamp(before, tz=timezone.utc) if before else None

        activities = self.client.get_activities(after=after_dt, before=before_dt)

        for count, activity in enumerate(activities):
            if limit is not None and count >= limit:
                break
            yield activity

    def get_activity(self, activity_id: int) -> Any:
        """Get detailed activity data.

        Args:
            activity_id: Strava activity ID.

        Returns:
            Detailed activity object from stravalib.
        """
        return self.client.get_activity(activity_id)

    def get_activity_streams(
        self,
        activity_id: int,
        types: list[str] | None = None,
        resolution: str = "high",
    ) -> dict[str, list[Any]]:
        """Get activity stream data (GPS, heart rate, etc.).

        Args:
            activity_id: Strava activity ID.
            types: Stream types to request. Defaults to all available.
            resolution: Data resolution ('low', 'medium', 'high').

        Returns:
            Dictionary mapping stream type to list of values.
        """
        if types is None:
            types = [
                "time",
                "latlng",
                "distance",
                "altitude",
                "heartrate",
                "cadence",
                "watts",
                "temp",
                "velocity_smooth",
                "grade_smooth",
            ]

        try:
            streams = self.client.get_activity_streams(
                activity_id,
                types=types,
                resolution=resolution,  # type: ignore[arg-type]
            )
        except Exception:
            # Activity may not have stream data
            return {}

        result: dict[str, list[Any]] = {}
        for stream_type, stream in streams.items():
            result[stream_type] = list(stream.data) if stream.data else []

        return result

    def get_activity_photos(
        self,
        activity_id: int,
        size: int = 2048,
    ) -> list[dict[str, Any]]:
        """Get photos attached to an activity.

        Args:
            activity_id: Strava activity ID.
            size: Maximum photo size (pixels).

        Returns:
            List of photo metadata dictionaries.
        """
        try:
            logger.debug("Fetching photos for activity %d with size=%d", activity_id, size)
            photos = self.client.get_activity_photos(activity_id, size=size)
            result = []
            for p in photos:
                photo_dict = {
                    "unique_id": p.unique_id,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "location": list(p.location) if p.location else None,
                    "urls": p.urls,
                }
                logger.debug("  Photo %s: urls=%s", p.unique_id, p.urls)
                result.append(photo_dict)
            logger.debug("Fetched %d photos for activity %d", len(result), activity_id)
            return result
        except Exception as e:
            logger.debug("Failed to fetch photos for activity %d: %s", activity_id, e)
            return []

    def get_activity_comments(self, activity_id: int) -> list[dict[str, Any]]:
        """Get comments on an activity.

        Args:
            activity_id: Strava activity ID.

        Returns:
            List of comment dictionaries.

        Raises:
            StravaRateLimitError: If rate limit is exceeded.
        """
        from stravalib.exc import RateLimitExceeded, RateLimitTimeout

        try:
            comments = self.client.get_activity_comments(activity_id)
            result = []
            for c in comments:
                athlete = getattr(c, "athlete", None)
                athlete_id = None
                athlete_firstname = None
                athlete_lastname = None

                if athlete is not None:
                    # Try direct attribute access first
                    athlete_id = getattr(athlete, "id", None)

                    # If id is None, try pydantic v2 model_dump()
                    if athlete_id is None and hasattr(athlete, "model_dump"):
                        data = athlete.model_dump()
                        athlete_id = data.get("id")

                    athlete_firstname = getattr(athlete, "firstname", None)
                    athlete_lastname = getattr(athlete, "lastname", None)

                created_at = getattr(c, "created_at", None)
                result.append(
                    {
                        "id": getattr(c, "id", None),
                        "text": getattr(c, "text", None),
                        "created_at": created_at.isoformat() if created_at else None,
                        "athlete_id": athlete_id,
                        "athlete_firstname": athlete_firstname,
                        "athlete_lastname": athlete_lastname,
                    }
                )
            return result
        except (RateLimitExceeded, RateLimitTimeout) as e:
            raise StravaRateLimitError(str(e)) from e
        except Exception:
            return []

    def get_activity_kudos(self, activity_id: int) -> list[dict[str, Any]]:
        """Get kudos on an activity.

        Args:
            activity_id: Strava activity ID.

        Returns:
            List of kudo giver dictionaries.

        Raises:
            StravaRateLimitError: If rate limit is exceeded.

        Note:
            The Strava API does not return athlete IDs for kudos (privacy).
            The athlete_id field will always be None.
        """
        from stravalib.exc import RateLimitExceeded, RateLimitTimeout

        try:
            kudos = self.client.get_activity_kudos(activity_id)
            result = []
            for k in kudos:
                # Note: Strava API intentionally does not return athlete IDs
                # for kudos (privacy). The id will always be None.
                result.append(
                    {
                        "athlete_id": None,  # API limitation - not available
                        "firstname": getattr(k, "firstname", None),
                        "lastname": getattr(k, "lastname", None),
                    }
                )
            return result
        except (RateLimitExceeded, RateLimitTimeout) as e:
            raise StravaRateLimitError(str(e)) from e
        except Exception:
            return []

    def get_athlete_gear(self) -> list[dict[str, Any]]:
        """Get all gear for the authenticated athlete.

        Returns:
            List of gear dictionaries.
        """
        athlete = self.get_athlete()
        gear_list: list[dict[str, Any]] = []

        # Get bikes
        if hasattr(athlete, "bikes") and athlete.bikes:
            for bike in athlete.bikes:
                gear_info = self._get_gear_details(bike.id, "bike")
                if gear_info:
                    gear_list.append(gear_info)

        # Get shoes
        if hasattr(athlete, "shoes") and athlete.shoes:
            for shoe in athlete.shoes:
                gear_info = self._get_gear_details(shoe.id, "shoes")
                if gear_info:
                    gear_list.append(gear_info)

        return gear_list

    def _get_gear_details(self, gear_id: str, gear_type: str) -> dict[str, Any] | None:
        """Get detailed gear information.

        Args:
            gear_id: Gear ID.
            gear_type: Type of gear ('bike' or 'shoes').

        Returns:
            Gear details dictionary or None.
        """
        try:
            gear = self.client.get_gear(gear_id)
            return {
                "id": gear.id,
                "name": gear.name,
                "type": gear_type,
                "brand": getattr(gear, "brand_name", None),
                "model": getattr(gear, "model_name", None),
                "distance_m": float(gear.distance) if gear.distance else 0.0,
                "primary": getattr(gear, "primary", False),
                "retired": getattr(gear, "retired", False),
            }
        except Exception:
            return None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth2 callback."""

    authorization_code: str | None = None

    def do_GET(self) -> None:
        """Handle GET request with OAuth callback."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            OAuthCallbackHandler.authorization_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Authorization successful!</h1>"
                b"<p>You can close this window.</p></body></html>"
            )
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            error = params.get("error", ["Unknown error"])[0]
            self.wfile.write(
                f"<html><body><h1>Authorization failed</h1><p>{error}</p></body></html>".encode()
            )

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default logging."""
        pass


def authenticate(
    config: Config,
    client_id: str | None = None,
    client_secret: str | None = None,
    port: int = 8000,
) -> TokenInfo:
    """Perform OAuth2 authentication flow.

    Args:
        config: Application configuration.
        client_id: Strava API client ID (overrides config).
        client_secret: Strava API client secret (overrides config).
        port: Local port for OAuth callback server.

    Returns:
        TokenInfo with access and refresh tokens.

    Raises:
        ValueError: If client credentials are missing.
        RuntimeError: If authentication fails.
    """
    # Get credentials
    cid = client_id or config.strava.client_id
    secret = client_secret or config.strava.client_secret

    if not cid or not secret:
        raise ValueError(
            "Client ID and secret are required. "
            "Provide via --client-id/--client-secret or config file."
        )

    # Generate authorization URL
    client = Client()
    redirect_uri = f"http://localhost:{port}/callback"
    auth_url = client.authorization_url(
        client_id=int(cid),
        redirect_uri=redirect_uri,
        scope=OAUTH_SCOPES,  # type: ignore[arg-type]
    )

    # Start callback server
    OAuthCallbackHandler.authorization_code = None
    server = HTTPServer(("localhost", port), OAuthCallbackHandler)
    server.timeout = 120  # 2 minute timeout

    # Open browser
    print("Opening browser for authorization...")
    print(f"If browser doesn't open, visit: {auth_url}")
    webbrowser.open(auth_url)

    # Wait for callback
    print("Waiting for authorization...")
    try:
        while OAuthCallbackHandler.authorization_code is None:
            server.handle_request()
    finally:
        # Close the server socket to avoid ResourceWarning
        server.server_close()

    code = OAuthCallbackHandler.authorization_code
    if not code:
        raise RuntimeError("No authorization code received")

    # Exchange code for tokens
    token_response = client.exchange_code_for_token(
        client_id=cid,
        client_secret=secret,
        code=code,
    )

    token_info = TokenInfo(
        access_token=token_response["access_token"],
        refresh_token=token_response["refresh_token"],
        expires_at=token_response["expires_at"],
    )

    # Save tokens to config
    save_tokens(
        config,
        access_token=token_info.access_token,
        refresh_token=token_info.refresh_token,
        expires_at=token_info.expires_at,
    )

    return token_info
