"""Command-line interface for strava-backup.

Provides CLI commands for authentication, syncing, viewing, and exporting
Strava activity data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from strava_backup import __version__
from strava_backup.config import DEFAULT_CONFIG_PATH, load_config

if TYPE_CHECKING:
    from strava_backup.config import Config


class JSONOutput:
    """Helper for JSON output formatting."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self._data: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        """Set a value in the output."""
        self._data[key] = value

    def update(self, data: dict[str, Any]) -> None:
        """Update with multiple values."""
        self._data.update(data)

    def output(self) -> None:
        """Print JSON output if enabled."""
        if self.enabled:
            click.echo(json.dumps(self._data, indent=2, default=str))


# Custom context class to hold shared state
class Context:
    """CLI context holding shared configuration and state."""

    def __init__(self) -> None:
        self.config: Config | None = None
        self.verbose: int = 0
        self.quiet: bool = False
        self.json_output: bool = False
        self.output: JSONOutput = JSONOutput()

    def log(self, message: str, level: int = 0) -> None:
        """Log a message if verbosity allows.

        Args:
            message: Message to log.
            level: Required verbosity level (0=normal, 1=-v, 2=-vv).
        """
        if self.json_output:
            return
        if self.quiet and level == 0:
            return
        if level <= self.verbose or level == 0:
            click.echo(message)

    def error(self, message: str) -> None:
        """Log an error message."""
        if self.json_output:
            self.output.set("error", message)
            self.output.set("status", "error")
        else:
            click.echo(f"Error: {message}", err=True)


pass_context = click.make_pass_decorator(Context, ensure=True)


@click.group()
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=False, path_type=Path),
    default=None,
    help=f"Configuration file path (default: {DEFAULT_CONFIG_PATH})",
)
@click.option(
    "--data-dir",
    "-d",
    type=click.Path(exists=False, path_type=Path),
    default=None,
    help="Data directory path (default: ./data)",
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase verbosity (can be repeated: -v, -vv, -vvv)",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress non-error output",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output in JSON format",
)
@click.version_option(version=__version__, prog_name="strava-backup")
@pass_context
def main(
    ctx: Context,
    config_path: Path | None,
    data_dir: Path | None,
    verbose: int,
    quiet: bool,
    json_output: bool,
) -> None:
    """Strava Activity Backup and Visualization CLI.

    Back up your Strava activities, view statistics, generate maps,
    and export to FitTrackee.
    """
    ctx.verbose = verbose
    ctx.quiet = quiet
    ctx.json_output = json_output
    ctx.output = JSONOutput(json_output)

    # Load configuration
    ctx.config = load_config(config_path)

    # Override data directory if specified
    if data_dir is not None:
        ctx.config.data.directory = data_dir


@main.command()
@click.option(
    "--client-id",
    help="Strava API client ID",
)
@click.option(
    "--client-secret",
    help="Strava API client secret",
)
@click.option(
    "--port",
    default=8000,
    help="Local OAuth callback port (default: 8000)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force re-authentication even if token exists",
)
@pass_context
def auth(
    ctx: Context,
    client_id: str | None,
    client_secret: str | None,
    port: int,
    force: bool,
) -> None:
    """Authenticate with Strava OAuth2.

    Opens a browser window for Strava authorization. After approval,
    tokens are saved to the configuration file.
    """
    from strava_backup.services.strava import StravaClient, authenticate

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    # Check if already authenticated
    if not force and config.strava.access_token:
        # Try to verify existing token
        try:
            client = StravaClient(config)
            athlete = client.get_athlete()
            ctx.log(f"Already authenticated as {athlete.username}")
            if ctx.json_output:
                ctx.output.update({
                    "status": "success",
                    "message": "Already authenticated",
                    "athlete_id": athlete.id,
                    "username": athlete.username,
                })
                ctx.output.output()
            return
        except Exception:
            # Token invalid, proceed with re-auth
            pass

    try:
        token_info = authenticate(
            config,
            client_id=client_id,
            client_secret=client_secret,
            port=port,
        )

        # Get athlete info
        client = StravaClient(config)
        athlete = client.get_athlete()

        ctx.log(f"Successfully authenticated as {athlete.username}")
        ctx.log(f"Token expires at: {token_info.expires_at}")

        if ctx.json_output:
            ctx.output.update({
                "status": "success",
                "athlete_id": athlete.id,
                "username": athlete.username,
                "token_expires_at": token_info.expires_at,
            })
            ctx.output.output()

    except ValueError as e:
        ctx.error(str(e))
        if ctx.json_output:
            ctx.output.output()
        sys.exit(2)
    except Exception as e:
        ctx.error(f"Authentication failed: {e}")
        if ctx.json_output:
            ctx.output.output()
        sys.exit(1)


@main.command()
@click.option(
    "--full",
    is_flag=True,
    help="Force full sync (ignore last sync time)",
)
@click.option(
    "--after",
    type=click.DateTime(),
    help="Only sync activities after this date (ISO 8601)",
)
@click.option(
    "--before",
    type=click.DateTime(),
    help="Only sync activities before this date (ISO 8601)",
)
@click.option(
    "--limit",
    type=int,
    help="Maximum number of activities to sync",
)
@click.option(
    "--no-photos",
    is_flag=True,
    help="Skip photo download",
)
@click.option(
    "--no-streams",
    is_flag=True,
    help="Skip GPS/sensor stream download",
)
@click.option(
    "--no-comments",
    is_flag=True,
    help="Skip comments and kudos download",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be synced without downloading",
)
@pass_context
def sync(
    ctx: Context,
    full: bool,
    after: Any | None,
    before: Any | None,
    limit: int | None,
    no_photos: bool,
    no_streams: bool,
    no_comments: bool,
    dry_run: bool,
) -> None:
    """Synchronize activities from Strava.

    Downloads activity metadata, GPS tracks, photos, and social data
    to the local data directory.
    """
    from strava_backup.services.backup import BackupService

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    try:
        service = BackupService(config)
        result = service.sync(
            full=full,
            after=after,
            before=before,
            limit=limit,
            include_photos=not no_photos and config.sync.photos,
            include_streams=not no_streams and config.sync.streams,
            include_comments=not no_comments and config.sync.comments,
            dry_run=dry_run,
            log_callback=ctx.log if not ctx.json_output else None,
        )

        if ctx.json_output:
            ctx.output.update({
                "status": "success",
                **result,
            })
            ctx.output.output()
        else:
            ctx.log(f"\nSynced {result['activities_synced']} activities "
                   f"({result['activities_new']} new, {result['activities_updated']} updated)")
            if result.get("photos_downloaded", 0) > 0:
                ctx.log(f"Downloaded {result['photos_downloaded']} photos")
            if result.get("errors"):
                ctx.log(f"Errors: {len(result['errors'])}")

    except ValueError as e:
        ctx.error(str(e))
        if ctx.json_output:
            ctx.output.output()
        sys.exit(2)
    except Exception as e:
        ctx.error(f"Sync failed: {e}")
        if ctx.json_output:
            ctx.output.output()
        sys.exit(1)


@main.command()
@click.argument("sessions", nargs=-1)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("./gpx"),
    help="Output directory (default: ./gpx)",
)
@click.option(
    "--after",
    type=click.DateTime(),
    help="Export activities after this date",
)
@click.option(
    "--before",
    type=click.DateTime(),
    help="Export activities before this date",
)
@click.option(
    "--with-hr",
    is_flag=True,
    help="Include heart rate in GPX extensions",
)
@click.option(
    "--with-cadence",
    is_flag=True,
    help="Include cadence in GPX extensions",
)
@click.option(
    "--with-power",
    is_flag=True,
    help="Include power in GPX extensions",
)
@pass_context
def gpx(
    ctx: Context,
    sessions: tuple[str, ...],
    output_dir: Path,
    after: Any | None,
    before: Any | None,
    with_hr: bool,
    with_cadence: bool,
    with_power: bool,
) -> None:
    """Export activities as GPX files.

    Exports backed-up activities to GPX format with optional heart rate,
    cadence, and power data in Garmin extensions.
    """
    from strava_backup.lib.gpx import export_activities_to_gpx

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    try:
        result = export_activities_to_gpx(
            data_dir=config.data.directory,
            output_dir=output_dir,
            sessions=list(sessions) if sessions else None,
            after=after,
            before=before,
            include_hr=with_hr,
            include_cadence=with_cadence,
            include_power=with_power,
            log_callback=ctx.log if not ctx.json_output else None,
        )

        if ctx.json_output:
            ctx.output.update({
                "status": "success",
                **result,
            })
            ctx.output.output()
        else:
            ctx.log(f"\nExported {result['exported']} activities to {output_dir}")

    except Exception as e:
        ctx.error(f"GPX export failed: {e}")
        if ctx.json_output:
            ctx.output.output()
        sys.exit(1)


@main.group()
def view() -> None:
    """View backed-up activity data."""
    pass


@view.command(name="stats")
@click.option(
    "--year",
    type=int,
    help="Show stats for specific year",
)
@click.option(
    "--month",
    help="Show stats for specific month (YYYY-MM)",
)
@click.option(
    "--after",
    type=click.DateTime(),
    help="Stats for activities after this date",
)
@click.option(
    "--before",
    type=click.DateTime(),
    help="Stats for activities before this date",
)
@click.option(
    "--type",
    "activity_type",
    help="Filter by activity type",
)
@click.option(
    "--by-month",
    is_flag=True,
    help="Break down by month",
)
@click.option(
    "--by-type",
    is_flag=True,
    help="Break down by activity type",
)
@pass_context
def stats(
    ctx: Context,
    year: int | None,
    month: str | None,
    after: Any | None,
    before: Any | None,
    activity_type: str | None,
    by_month: bool,
    by_type: bool,
) -> None:
    """Display activity statistics."""
    from strava_backup.views.stats import calculate_stats, format_stats

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    try:
        result = calculate_stats(
            data_dir=config.data.directory,
            year=year,
            month=month,
            after=after,
            before=before,
            activity_type=activity_type,
            by_month=by_month,
            by_type=by_type,
        )

        if ctx.json_output:
            ctx.output.update(result)
            ctx.output.output()
        else:
            output = format_stats(result)
            ctx.log(output)

    except Exception as e:
        ctx.error(f"Stats calculation failed: {e}")
        if ctx.json_output:
            ctx.output.output()
        sys.exit(1)


@view.command(name="map")
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output HTML file (default: stdout or ./map.html)",
)
@click.option(
    "--after",
    type=click.DateTime(),
    help="Only include activities after this date",
)
@click.option(
    "--before",
    type=click.DateTime(),
    help="Only include activities before this date",
)
@click.option(
    "--type",
    "activity_type",
    help="Filter by activity type (Run, Ride, Hike, etc.)",
)
@click.option(
    "--heatmap",
    is_flag=True,
    help="Generate heatmap instead of individual routes",
)
@click.option(
    "--serve",
    is_flag=True,
    help="Start local HTTP server to view map",
)
@click.option(
    "--port",
    default=8080,
    help="Server port (default: 8080)",
)
@pass_context
def map_cmd(
    ctx: Context,
    output: Path | None,
    after: Any | None,
    before: Any | None,
    activity_type: str | None,
    heatmap: bool,
    serve: bool,
    port: int,
) -> None:
    """Generate interactive map visualization."""
    from strava_backup.views.map import generate_map, serve_map

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    try:
        html = generate_map(
            data_dir=config.data.directory,
            after=after,
            before=before,
            activity_type=activity_type,
            heatmap=heatmap,
        )

        if serve:
            output_path = output or Path("./map.html")
            output_path.write_text(html)
            ctx.log(f"Map saved to {output_path}")
            ctx.log(f"Starting server at http://127.0.0.1:{port}")
            serve_map(output_path, port=port)
        elif output:
            output.write_text(html)
            ctx.log(f"Map saved to {output}")
        else:
            click.echo(html)

    except Exception as e:
        ctx.error(f"Map generation failed: {e}")
        if ctx.json_output:
            ctx.output.output()
        sys.exit(1)


@main.command()
@click.option(
    "--port",
    default=8080,
    help="Server port (default: 8080)",
)
@click.option(
    "--host",
    default="127.0.0.1",
    help="Server host (default: 127.0.0.1)",
)
@click.option(
    "--no-open",
    is_flag=True,
    help="Don't automatically open browser",
)
@pass_context
def browse(ctx: Context, port: int, host: str, no_open: bool) -> None:
    """Start local web server to browse backed-up activities."""
    from strava_backup.views.browser import start_browser

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    try:
        ctx.log(f"Starting browser at http://{host}:{port}")
        start_browser(
            data_dir=config.data.directory,
            host=host,
            port=port,
            open_browser=not no_open,
        )
    except Exception as e:
        ctx.error(f"Browser failed: {e}")
        sys.exit(1)


@main.group()
def export() -> None:
    """Export activities to external services."""
    pass


@export.command(name="fittrackee")
@click.option(
    "--url",
    help="FitTrackee instance URL",
)
@click.option(
    "--email",
    help="FitTrackee account email",
)
@click.option(
    "--password",
    help="FitTrackee account password (or use env: FITTRACKEE_PASSWORD)",
)
@click.option(
    "--after",
    type=click.DateTime(),
    help="Only export activities after this date",
)
@click.option(
    "--before",
    type=click.DateTime(),
    help="Only export activities before this date",
)
@click.option(
    "--limit",
    type=int,
    help="Maximum number of activities to export",
)
@click.option(
    "--force",
    is_flag=True,
    help="Re-export already exported activities",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be exported without uploading",
)
@pass_context
def fittrackee(
    ctx: Context,
    url: str | None,
    email: str | None,
    password: str | None,
    after: Any | None,
    before: Any | None,
    limit: int | None,
    force: bool,
    dry_run: bool,
) -> None:
    """Export activities to FitTrackee."""
    from strava_backup.services.fittrackee import FitTrackeeExporter

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    # Get FitTrackee credentials
    ft_url = url or config.fittrackee.url
    ft_email = email or config.fittrackee.email
    ft_password = password or config.fittrackee.password

    if not ft_url:
        ctx.error("FitTrackee URL is required")
        if ctx.json_output:
            ctx.output.output()
        sys.exit(2)

    try:
        exporter = FitTrackeeExporter(
            data_dir=config.data.directory,
            url=ft_url,
            email=ft_email,
            password=ft_password,
        )

        result = exporter.export(
            after=after,
            before=before,
            limit=limit,
            force=force,
            dry_run=dry_run,
            log_callback=ctx.log if not ctx.json_output else None,
        )

        if ctx.json_output:
            ctx.output.update({
                "status": "success",
                **result,
            })
            ctx.output.output()
        else:
            ctx.log(f"\nExported {result['exported']} activities")
            ctx.log(f"Skipped {result['skipped']} activities")
            if result.get("failed", 0) > 0:
                ctx.log(f"Failed: {result['failed']}")

    except Exception as e:
        ctx.error(f"FitTrackee export failed: {e}")
        if ctx.json_output:
            ctx.output.output()
        sys.exit(1)


if __name__ == "__main__":
    main()
