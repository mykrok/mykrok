"""Command-line interface for MyKrok.

Provides CLI commands for authentication, syncing, viewing, and exporting
Strava activity data.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from mykrok import __version__
from mykrok.config import DEFAULT_CONFIG_PATH, load_config

if TYPE_CHECKING:
    from mykrok.config import Config


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


@click.group(invoke_without_command=True)
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
@click.version_option(version=__version__, prog_name="mykrok")
@click.pass_context
def main(
    click_ctx: click.Context,
    config_path: Path | None,
    data_dir: Path | None,
    verbose: int,
    quiet: bool,
    json_output: bool,
) -> None:
    """Fitness Activity Backup and Visualization CLI.

    Back up your fitness activities, view statistics, generate maps,
    and export to other platforms. Currently supports Strava as the
    data source and FitTrackee as an export target.
    """
    # Create our context object
    ctx = Context()
    click_ctx.obj = ctx

    ctx.verbose = verbose
    ctx.quiet = quiet
    ctx.json_output = json_output
    ctx.output = JSONOutput(json_output)

    # Store options for deferred initialization
    ctx._config_path = config_path  # type: ignore[attr-defined]
    ctx._data_dir = data_dir  # type: ignore[attr-defined]

    # Only initialize config and logging when running an actual command
    # Skip for --help/--version to avoid creating log files
    help_requested = any(arg in sys.argv for arg in ("--help", "-h", "--version"))
    if click_ctx.invoked_subcommand is not None and not help_requested:
        import logging

        from mykrok.lib.logging import setup_logging

        # Load configuration
        ctx.config = load_config(config_path)

        # Override data directory if specified
        if data_dir is not None:
            ctx.config.data.directory = data_dir

        # Set up logging
        # Console level based on verbosity, file always at DEBUG
        console_level = (
            logging.WARNING
            if quiet
            else (logging.DEBUG if verbose >= 2 else logging.INFO if verbose >= 1 else logging.INFO)
        )
        setup_logging(
            config=ctx.config,
            console_level=console_level,
            quiet=quiet,
        )


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
    from mykrok.services.strava import StravaClient, authenticate

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
                ctx.output.update(
                    {
                        "status": "success",
                        "message": "Already authenticated",
                        "athlete_id": athlete.id,
                        "username": athlete.username,
                    }
                )
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
            ctx.output.update(
                {
                    "status": "success",
                    "athlete_id": athlete.id,
                    "username": athlete.username,
                    "token_expires_at": token_info.expires_at,
                }
            )
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
    "--what",
    type=click.Choice(
        ["recent", "full", "social", "athlete-profiles", "check-and-fix"], case_sensitive=False
    ),
    default="recent",
    help="What to sync: recent (default), full, social, athlete-profiles, or check-and-fix",
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
@click.option(
    "--activity-ids",
    help="Comma-separated list of activity IDs to sync",
)
@click.option(
    "--lean-update",
    is_flag=True,
    help="Only update sync_state.json if there are actual changes (new/updated activities)",
)
@click.option(
    "--refresh-social-days",
    type=int,
    default=7,
    show_default=True,
    help="After sync, refresh kudos/comments for activities from past N days (0 to disable)",
)
@pass_context
def sync(
    ctx: Context,
    what: str,
    after: Any | None,
    before: Any | None,
    limit: int | None,
    no_photos: bool,
    no_streams: bool,
    no_comments: bool,
    dry_run: bool,
    activity_ids: str | None,
    lean_update: bool,
    refresh_social_days: int,
) -> None:
    """Synchronize activities from Strava.

    Downloads activity metadata, GPS tracks, photos, and social data
    to the local data directory.

    \b
    Sync modes (--what):
      recent           Incremental sync of new activities since last sync (default)
      full             Sync all activities from Strava (ignores last sync time)
      social           Only refresh kudos/comments for existing local activities
      athlete-profiles Refresh athlete profile info (name, location) and avatar photos
      check-and-fix    Verify data integrity and re-fetch missing photos/tracking data
    """
    from mykrok.services.backup import BackupService

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    # Parse activity IDs if provided
    activity_id_list: list[int] | None = None
    if activity_ids:
        try:
            activity_id_list = [int(aid.strip()) for aid in activity_ids.split(",")]
        except ValueError:
            ctx.error("Invalid activity ID format. Use comma-separated integers.")
            sys.exit(2)

    try:
        service = BackupService(config)

        # Handle athlete-profiles mode
        if what == "athlete-profiles":
            result = service.refresh_athlete_profiles(
                dry_run=dry_run,
                log_callback=ctx.log if not ctx.json_output else None,
            )

            if ctx.json_output:
                ctx.output.update(
                    {
                        "status": "success",
                        **result,
                    }
                )
                ctx.output.output()
            else:
                ctx.log(
                    f"\nUpdated {result['profiles_updated']} profile(s), "
                    f"downloaded {result['avatars_downloaded']} avatar(s)"
                )
                if result.get("errors"):
                    ctx.log(f"Errors: {len(result['errors'])}")
            return

        # Handle social mode (only update kudos/comments for existing activities)
        if what == "social":
            result = service.refresh_social(
                after=after,
                before=before,
                limit=limit,
                dry_run=dry_run,
                log_callback=ctx.log if not ctx.json_output else None,
            )

            if ctx.json_output:
                ctx.output.update(
                    {
                        "status": "success",
                        **result,
                    }
                )
                ctx.output.output()
            else:
                ctx.log(f"\nRefreshed social data for {result['activities_updated']} activities")
                if result.get("errors"):
                    ctx.log(f"Errors: {len(result['errors'])}")
            return

        # Handle check-and-fix mode (verify and repair missing data)
        if what == "check-and-fix":
            result = service.check_and_fix(
                dry_run=dry_run,
                log_callback=ctx.log if not ctx.json_output else None,
            )

            if ctx.json_output:
                ctx.output.update(
                    {
                        "status": "success",
                        **result,
                    }
                )
                ctx.output.output()
            else:
                ctx.log(
                    f"\nChecked {result['sessions_checked']} sessions: "
                    f"{result['issues_found']} issues found, {result['issues_fixed']} fixed"
                )
                if result.get("errors"):
                    ctx.log(f"Errors: {len(result['errors'])}")
            return

        # Normal sync (recent or full mode)
        result = service.sync(
            full=(what == "full"),
            after=after,
            before=before,
            limit=limit,
            activity_id_filter=activity_id_list,
            include_photos=not no_photos and config.sync.photos,
            include_streams=not no_streams and config.sync.streams,
            include_comments=not no_comments and config.sync.comments,
            dry_run=dry_run,
            lean_update=lean_update,
            log_callback=ctx.log if not ctx.json_output else None,
        )

        if ctx.json_output:
            ctx.output.update(
                {
                    "status": "success",
                    **result,
                }
            )
            ctx.output.output()
        else:
            ctx.log(
                f"\nSynced {result['activities_synced']} activities "
                f"({result['activities_new']} new, {result['activities_updated']} updated)"
            )
            if result.get("photos_downloaded", 0) > 0:
                ctx.log(f"Downloaded {result['photos_downloaded']} photos")
            if result.get("errors"):
                ctx.log(f"Errors: {len(result['errors'])}")

        # Refresh social data for recent activities (after main sync)
        if refresh_social_days > 0 and not dry_run and what in ("recent", "full"):
            social_after = datetime.now() - timedelta(days=refresh_social_days)
            ctx.log(f"\nRefreshing social data for activities from past {refresh_social_days} days...")
            social_result = service.refresh_social(
                after=social_after,
                dry_run=False,
                log_callback=ctx.log if not ctx.json_output else None,
            )
            if not ctx.json_output:
                ctx.log(
                    f"Social refresh: {social_result['activities_updated']} activities updated"
                )

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
    from mykrok.lib.gpx import export_activities_to_gpx

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
            ctx.output.update(
                {
                    "status": "success",
                    **result,
                }
            )
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
    from mykrok.views.stats import calculate_stats, format_stats

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


@main.command("create-browser")
@click.option(
    "-o",
    "--output",
    default="mykrok.html",
    help="Output filename (default: mykrok.html)",
)
@click.option(
    "--serve",
    is_flag=True,
    help="Start local HTTP server after generation",
)
@click.option(
    "--port",
    default=8080,
    help="Server port (default: 8080)",
)
@pass_context
def create_browser_cmd(ctx: Context, output: str, serve: bool, port: int) -> None:
    """Generate interactive activity browser.

    Creates a single-page application (SPA) with:
    - Map view with activity markers and tracks
    - Sessions list with filtering and search
    - Statistics view with charts

    The browser loads data on demand from the data directory (athletes.tsv,
    sessions.tsv, tracking.parquet files).
    """
    from mykrok.views.map import copy_assets_to_output, generate_browser, serve_map

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    # Validate that data directory looks like a mykrok dataset
    athletes_tsv = config.data.directory / "athletes.tsv"
    if not athletes_tsv.exists():
        ctx.error(
            f"Data directory {config.data.directory} does not appear to be a "
            "mykrok dataset (missing athletes.tsv). "
            "Run 'mykrok sync' first to populate data, or check your configuration."
        )
        sys.exit(1)

    try:
        # Generate the SPA HTML
        html = generate_browser(config.data.directory)

        # Output to data directory
        output_path = config.data.directory / output
        output_path.write_text(html, encoding="utf-8")

        # Copy JS/CSS assets
        assets_dst = copy_assets_to_output(config.data.directory)
        ctx.log(f"Browser saved to {output_path}")
        ctx.log(f"Assets copied to {assets_dst}")

        if serve:
            ctx.log(f"Starting server at http://127.0.0.1:{port}")
            serve_map(output_path, port=port)
        else:
            ctx.log(
                f"To view: python -m http.server --directory {config.data.directory} {port}"
            )

    except Exception as e:
        ctx.error(f"Browser generation failed: {e}")
        if ctx.json_output:
            ctx.output.output()
        sys.exit(1)




@main.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for demo data (default: ./demo-data)",
)
@click.option(
    "--port",
    default=8080,
    help="Server port (default: 8080)",
)
@click.option(
    "--no-serve",
    is_flag=True,
    help="Generate demo data without starting server",
)
@click.option(
    "--seed",
    type=int,
    default=42,
    help="Random seed for reproducible data (default: 42)",
)
def demo(output: Path | None, port: int, no_serve: bool, seed: int) -> None:
    """Generate demo data and view in browser.

    Creates sample data for two athletes (alice and bob) with various
    activity types, GPS tracks, photos, kudos, and comments. Useful for
    testing and demonstrating the unified frontend.

    The demo includes:
    - 10 sessions for alice (runs, rides, swims, hikes)
    - 5 sessions for bob (mostly rides)
    - A shared run session (both athletes together)
    - GPS tracks with heart rate, cadence, and power data
    - Sample photos and social data (kudos/comments)

    Example:
        mykrok demo                    # Generate and serve
        mykrok demo --no-serve         # Generate only
        mykrok demo -o /tmp/demo       # Custom output directory
    """
    import random
    import shutil
    import webbrowser
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    from mykrok.views.map import copy_assets_to_output, generate_browser

    # Import fixture generator
    fixtures_path = Path(__file__).parent.parent.parent / "tests" / "e2e" / "fixtures"
    if fixtures_path.exists():
        import sys as _sys

        _sys.path.insert(0, str(fixtures_path))
        from generate_fixtures import generate_fixtures
    else:
        click.echo("Error: Fixture generator not found. Run from project root.", err=True)
        sys.exit(1)

    output_dir = output or Path("./demo-data")
    output_dir = output_dir.resolve()

    click.echo(f"Generating demo data in: {output_dir}")

    # Clean and create output directory
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Generate fixtures with specified seed
    random.seed(seed)
    generate_fixtures(output_dir)

    # Generate the SPA HTML
    html = generate_browser(output_dir)
    html_path = output_dir / "mykrok.html"
    html_path.write_text(html, encoding="utf-8")
    click.echo(f"Generated: {html_path}")

    # Copy assets
    assets_dst = copy_assets_to_output(output_dir)
    click.echo(f"Assets copied to: {assets_dst}")

    if no_serve:
        click.echo(f"\nTo view: python -m http.server --directory {output_dir} {port}")
        click.echo(f"Then open: http://127.0.0.1:{port}/mykrok.html")
    else:
        # Start server and open browser
        import os

        os.chdir(output_dir)

        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass  # Suppress request logs

        server = HTTPServer(("127.0.0.1", port), QuietHandler)
        url = f"http://127.0.0.1:{port}/mykrok.html"
        click.echo(f"\nStarting server at {url}")
        click.echo("Press Ctrl+C to stop")

        webbrowser.open(url)

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            click.echo("\nServer stopped")
            server.shutdown()


@main.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making changes",
)
@pass_context
def migrate(ctx: Context, dry_run: bool) -> None:
    """Migrate data directory to latest format.

    Performs the following migrations:
    - Renames .strava-backup/ config directory to .mykrok/
    - Updates git-annex annex.addunlocked config
    - Updates .gitattributes, README.md, Makefile, .gitignore references
    - Renames sub= directories to athl= prefix
    - Generates top-level athletes.tsv
    - Migrates center_lat/lng columns to start_lat/lng

    NOTE: If config file shows as pointer after reset, run 'git annex fsck'
    (not 'git annex unlock') to restore content before migrating.
    """
    from mykrok.services.migrate import run_full_migration

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    data_dir = config.data.directory

    if dry_run:
        ctx.log("Dry run - no changes will be made")

    try:
        results = run_full_migration(data_dir, dry_run=dry_run)

        # Report config directory migration
        if results["config_dir_migrated"]:
            old_path, new_path = results["config_dir_migrated"]
            action = "Would rename" if dry_run else "Renamed"
            ctx.log(f"{action} config directory: {old_path} -> {new_path}")

        if results["config_file_migrated"]:
            old_path, new_path = results["config_file_migrated"]
            action = "Would migrate" if dry_run else "Migrated"
            ctx.log(f"{action} config file: {old_path} -> {new_path}")

        # Report annex.addunlocked config update
        if results.get("annex_config_updated"):
            action = "Would update" if dry_run else "Updated"
            ctx.log(f"{action} git-annex addunlocked config (.strava-backup -> .mykrok)")

        # Report config.toml content update
        if results.get("config_content_updated"):
            action = "Would update" if dry_run else "Updated"
            ctx.log(f"{action} config.toml comments (.strava-backup -> .mykrok)")

        # Report gitattributes path updates
        if results["gitattributes_paths_updated"]:
            action = "Would update" if dry_run else "Updated"
            ctx.log(f"{action} .gitattributes paths (.strava-backup -> .mykrok)")

        # Report template file updates (README, Makefile, .gitignore)
        if results.get("template_files_updated"):
            ctx.log(f"Template files updated: {len(results['template_files_updated'])}")
            for filename in results["template_files_updated"]:
                action = "Would update" if dry_run else "Updated"
                ctx.log(f"  {action}: {filename}")

        # Report prefix renames
        if results["prefix_renames"]:
            ctx.log(f"Directory renames: {len(results['prefix_renames'])}")
            for old, new in results["prefix_renames"]:
                action = "Would rename" if dry_run else "Renamed"
                ctx.log(f"  {action}: {old} -> {new}")

        # Report dataset file updates (sub= -> athl=)
        if results["dataset_files_updated"]:
            ctx.log(f"Prefix updates in files: {len(results['dataset_files_updated'])}")
            for filepath in results["dataset_files_updated"]:
                action = "Would update" if dry_run else "Updated"
                ctx.log(f"  {action}: {filepath}")

        # Report gitattributes log rule
        if results["log_gitattributes_added"]:
            action = "Would add" if dry_run else "Added"
            ctx.log(f"{action} log file gitattributes rule")

        if not dry_run:
            # Report coordinate column migrations
            if results["coords_columns_migrated"]:
                ctx.log(
                    f"Migrated center_lat/lng -> start_lat/lng in "
                    f"{results['coords_columns_migrated']} file(s)"
                )

            # Report athletes.tsv
            if results["athletes_tsv"]:
                ctx.log(f"Generated: {results['athletes_tsv']}")

            ctx.log("Migration complete")
        else:
            # Check if anything would be done
            has_changes = any([
                results["config_dir_migrated"],
                results["config_file_migrated"],
                results.get("annex_config_updated"),
                results.get("config_content_updated"),
                results["gitattributes_paths_updated"],
                results.get("template_files_updated"),
                results["prefix_renames"],
                results["dataset_files_updated"],
                results["log_gitattributes_added"],
            ])
            if has_changes:
                ctx.log("Dry run complete - run without --dry-run to apply changes")
            else:
                ctx.log("No migrations needed")

    except Exception as e:
        ctx.error(f"Migration failed: {e}")
        sys.exit(1)


@main.command()
@pass_context
def rebuild_sessions(ctx: Context) -> None:
    """Rebuild sessions.tsv files from activity data.

    Scans all session directories and regenerates sessions.tsv for each athlete
    from their info.json files. Use this if sessions.tsv is missing entries
    or needs to be recreated.

    Includes start_lat/start_lng columns for map visualization.
    """
    from mykrok.lib.paths import iter_athlete_dirs
    from mykrok.models.activity import update_sessions_tsv

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    data_dir = config.data.directory

    try:
        # Find all athletes
        athletes = list(iter_athlete_dirs(data_dir))
        if not athletes:
            ctx.log("No athlete directories found")
            return

        ctx.log(f"Found {len(athletes)} athlete(s)")

        total_sessions = 0
        for username, _athlete_dir in athletes:
            sessions_path = update_sessions_tsv(data_dir, username)
            # Count sessions in the file
            with open(sessions_path, encoding="utf-8") as f:
                session_count = sum(1 for _ in f) - 1  # Subtract header
            ctx.log(f"  {username}: {session_count} sessions -> {sessions_path}")
            total_sessions += session_count

        ctx.log(f"Total: {total_sessions} sessions across {len(athletes)} athlete(s)")
        ctx.log("Done")

    except Exception as e:
        ctx.error(f"Failed to rebuild sessions: {e}")
        sys.exit(1)


@main.command("rebuild-timezones")
@click.option(
    "--default-timezone",
    default="America/New_York",
    help="Default timezone before first GPS-detected change",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force rebuild, ignoring rapid change warnings",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making changes",
)
@pass_context
def rebuild_timezones(
    ctx: Context,
    default_timezone: str,
    force: bool,
    dry_run: bool,
) -> None:
    """Rebuild timezone history from GPS coordinates in activities.

    Scans all activities with GPS data and builds a timezone change history
    for each athlete. This history is used to correct local times that may
    have been recorded with wrong timezone settings.

    Activities without GPS (indoor workouts) will use the timezone that was
    active at that time based on surrounding GPS-enabled activities.

    Example:
        mykrok rebuild-timezones --default-timezone America/New_York
    """
    from mykrok.lib.paths import iter_athlete_dirs
    from mykrok.models.activity import load_activities
    from mykrok.models.tracking import get_coordinates, load_tracking_manifest
    from mykrok.services.timezone import (
        TimezoneHistory,
        detect_timezone_from_coords,
        validate_timezone_history,
    )

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    data_dir = config.data.directory

    # Check if timezonefinder is available
    try:
        import timezonefinder  # noqa: F401
    except ImportError:
        ctx.error(
            "timezonefinder not installed. Install with: pip install mykrok[timezone]"
        )
        sys.exit(1)

    try:
        athletes = list(iter_athlete_dirs(data_dir))
        if not athletes:
            ctx.log("No athlete directories found")
            return

        ctx.log(f"Found {len(athletes)} athlete(s)")
        ctx.log(f"Default timezone: {default_timezone}")
        if dry_run:
            ctx.log("DRY RUN - no changes will be made")

        for username, athlete_dir in athletes:
            ctx.log(f"\nProcessing {username}...")

            # Load or create timezone history
            history = TimezoneHistory(athlete_dir, default_timezone=default_timezone)
            if not dry_run:
                history.clear()  # Start fresh

            # Get all activities sorted by date
            activities = load_activities(data_dir, username)
            activities.sort(key=lambda a: a.start_date)

            changes_added = 0
            activities_with_gps = 0

            for activity in activities:
                # Check for GPS coordinates - get from tracking data
                if not activity.has_gps:
                    continue

                session_key = activity.start_date.strftime("%Y%m%dT%H%M%S")
                session_dir = athlete_dir / f"ses={session_key}"

                manifest = load_tracking_manifest(session_dir)
                if not manifest or not manifest.has_gps:
                    continue

                coords = get_coordinates(session_dir)
                if not coords:
                    continue

                lat, lng = coords[0]  # Use first GPS point
                activities_with_gps += 1

                # Detect timezone from coordinates
                detected_tz = detect_timezone_from_coords(lat, lng)
                if detected_tz is None:
                    continue

                # Try to add timezone change
                if force:
                    success, msg = history.add_change_force(
                        activity.start_date,
                        detected_tz,
                        f"gps:ses={activity.start_date.strftime('%Y%m%dT%H%M%S')}",
                    )
                else:
                    success, msg = history.add_change(
                        activity.start_date,
                        detected_tz,
                        f"gps:ses={activity.start_date.strftime('%Y%m%dT%H%M%S')}",
                    )

                if success:
                    changes_added += 1
                    ctx.log(f"  {activity.start_date.date()}: -> {detected_tz}")

            # Validate and warn
            warnings = validate_timezone_history(history)
            for warning in warnings:
                ctx.log(f"  WARNING: {warning}")

            # Save
            if not dry_run:
                history.save()
                ctx.log(
                    f"  Saved: {changes_added} timezone changes "
                    f"(from {activities_with_gps} GPS activities)"
                )
            else:
                ctx.log(
                    f"  Would save: {changes_added} timezone changes "
                    f"(from {activities_with_gps} GPS activities)"
                )

        ctx.log("\nDone")

    except Exception as e:
        ctx.error(f"Failed to rebuild timezones: {e}")
        import traceback
        traceback.print_exc()
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
    from mykrok.services.fittrackee import FitTrackeeExporter

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
            ctx.output.update(
                {
                    "status": "success",
                    **result,
                }
            )
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


@main.command("create-datalad-dataset")
@click.argument("path", type=click.Path(path_type=Path))
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing files if present",
)
@pass_context
def create_datalad_dataset_cmd(ctx: Context, path: Path, force: bool) -> None:
    """Create a DataLad dataset for activity backups.

    Creates a new DataLad dataset at PATH with:

    \b
    - text2git configuration (text in git, binaries in git-annex)
    - Sample .mykrok/config.toml config with comments
    - README.md explaining the dataset
    - Makefile for reproducible syncs using `datalad run`

    Example:

    \b
        mykrok create-datalad-dataset ./my-mykrok-backup
        cd my-mykrok-backup
        # Edit .mykrok/config.toml with your credentials
        mykrok auth
        make sync
    """
    from mykrok.services.datalad import create_datalad_dataset

    try:
        result = create_datalad_dataset(path, force=force)

        if ctx.json_output:
            ctx.output.update(
                {
                    "status": "success",
                    **result,
                }
            )
            ctx.output.output()
        else:
            ctx.log(f"Created DataLad dataset at: {result['path']}")
            ctx.log("")
            ctx.log("Next steps:")
            ctx.log(f"  1. cd {result['path']}")
            ctx.log("  2. Edit .mykrok/config.toml with your Strava API credentials")
            ctx.log("  3. Run: mykrok auth")
            ctx.log("  4. Run: make sync")

    except FileExistsError as e:
        ctx.error(str(e))
        if ctx.json_output:
            ctx.output.output()
        sys.exit(1)
    except RuntimeError as e:
        ctx.error(str(e))
        if ctx.json_output:
            ctx.output.output()
        sys.exit(1)
    except ImportError:
        ctx.error("DataLad is not installed. Install with: pip install datalad")
        if ctx.json_output:
            ctx.output.output()
        sys.exit(1)


@main.command("gh-pages")
@click.option(
    "--push",
    is_flag=True,
    help="Push gh-pages branch to origin after generating",
)
@click.option(
    "--worktree",
    type=click.Path(path_type=Path),
    default=None,
    help="Path for gh-pages worktree (default: .gh-pages)",
)
@click.option(
    "--no-datalad",
    is_flag=True,
    help="Don't use datalad even if available",
)
@click.option(
    "--seed",
    type=int,
    default=42,
    help="Random seed for reproducible demo data (default: 42)",
)
@pass_context
def gh_pages_cmd(
    ctx: Context,
    push: bool,
    worktree: Path | None,
    no_datalad: bool,
    seed: int,
) -> None:
    """Generate GitHub Pages demo website.

    Creates or updates a gh-pages branch with a live demo of the
    MyKrok web frontend using reproducible synthetic data.

    The demo includes:

    \b
    - Interactive map with activity markers
    - Sessions list with filtering and search
    - Session detail view with GPS track
    - Statistics dashboard with charts

    Example:

    \b
        # Generate locally (review before pushing)
        strava-backup gh-pages

        # Generate and push to GitHub
        strava-backup gh-pages --push
    """
    from mykrok.services.gh_pages import generate_gh_pages

    # Find repo root (current directory or parent with .git)
    repo_root = Path.cwd()
    while repo_root != repo_root.parent:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent
    else:
        ctx.error("Not in a git repository")
        sys.exit(1)

    try:
        ctx.log("Generating GitHub Pages demo...")

        results = generate_gh_pages(
            repo_root=repo_root,
            worktree_path=worktree,
            push=push,
            use_datalad=not no_datalad,
            seed=seed,
        )

        if ctx.json_output:
            ctx.output.update(results)
            ctx.output.output()
        else:
            if results["is_new_branch"]:
                ctx.log("Created new gh-pages branch")
            else:
                ctx.log("Updated existing gh-pages branch")

            if results["had_changes"]:
                ctx.log("Committed changes to gh-pages")
                if results["pushed"]:
                    ctx.log("Pushed to origin")
                else:
                    ctx.log("Run with --push to deploy to GitHub Pages")
            elif results["reset_log_only"]:
                ctx.log("Only log files changed, no commit made")
            else:
                ctx.log("No changes to commit (demo is up to date)")

    except RuntimeError as e:
        ctx.error(str(e))
        if ctx.json_output:
            ctx.output.output()
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        ctx.error(f"Git command failed: {e}")
        if ctx.json_output:
            ctx.output.output()
        sys.exit(1)


@main.group()
def retry() -> None:
    """Manage the retry queue for failed activity syncs."""
    pass


@retry.command(name="list")
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    help="Show all entries including permanently failed",
)
@pass_context
def retry_list(ctx: Context, show_all: bool) -> None:
    """List activities in the retry queue.

    Shows activities that failed to sync and are scheduled for retry.
    """
    from mykrok.config import ensure_data_dir
    from mykrok.lib.paths import iter_athlete_dirs
    from mykrok.models.state import load_retry_queue

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    data_dir = ensure_data_dir(config)

    total_pending = 0
    total_permanent = 0

    for username, _athlete_dir in iter_athlete_dirs(data_dir):
        queue = load_retry_queue(data_dir, username)

        if queue.get_pending_count() == 0:
            continue

        ctx.log(f"\nAthlete: {username}")
        ctx.log("-" * 40)

        for entry in queue.failed_activities:
            if entry.is_permanently_failed():
                total_permanent += 1
                if show_all:
                    ctx.log(f"  [PERMANENT] Activity {entry.activity_id}")
                    ctx.log(f"    Error: {entry.error_message[:80]}...")
                    ctx.log(f"    Retries: {entry.retry_count}")
            else:
                total_pending += 1
                status = "DUE" if entry.is_due_for_retry() else "WAITING"
                next_retry = (
                    entry.next_retry_after.strftime("%Y-%m-%d %H:%M:%S")
                    if entry.next_retry_after
                    else "N/A"
                )
                ctx.log(f"  [{status}] Activity {entry.activity_id}")
                ctx.log(f"    Type: {entry.failure_type.value}")
                ctx.log(f"    Error: {entry.error_message[:80]}...")
                ctx.log(f"    Retries: {entry.retry_count}, Next: {next_retry}")

    if total_pending == 0 and total_permanent == 0:
        ctx.log("No activities in retry queue.")
    else:
        ctx.log(f"\nTotal: {total_pending} pending, {total_permanent} permanently failed")

    if ctx.json_output:
        ctx.output.update(
            {
                "status": "success",
                "pending_count": total_pending,
                "permanent_count": total_permanent,
            }
        )
        ctx.output.output()


@retry.command(name="clear")
@click.option(
    "--permanent-only",
    is_flag=True,
    help="Only clear permanently failed entries",
)
@click.option(
    "--activity-id",
    type=int,
    help="Clear specific activity by ID",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
@pass_context
def retry_clear(
    ctx: Context,
    permanent_only: bool,
    activity_id: int | None,
    yes: bool,
) -> None:
    """Clear entries from the retry queue.

    Without options, clears all entries. Use --permanent-only to only
    remove entries that have exhausted all retries.
    """
    from mykrok.config import ensure_data_dir
    from mykrok.lib.paths import iter_athlete_dirs
    from mykrok.models.state import load_retry_queue, save_retry_queue

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    data_dir = ensure_data_dir(config)
    cleared_total = 0

    for username, _athlete_dir in iter_athlete_dirs(data_dir):
        queue = load_retry_queue(data_dir, username)

        if queue.get_pending_count() == 0:
            continue

        cleared = 0
        if activity_id is not None:
            if queue.remove(activity_id):
                cleared = 1
        elif permanent_only:
            cleared = queue.cleanup_permanent_failures()
        else:
            if not yes:
                count = queue.get_pending_count()
                if not click.confirm(f"Clear all {count} entries for {username}?"):
                    continue
            cleared = queue.get_pending_count()
            queue.failed_activities = []

        if cleared > 0:
            save_retry_queue(data_dir, username, queue)
            ctx.log(f"Cleared {cleared} entries for {username}")
            cleared_total += cleared

    if cleared_total == 0:
        ctx.log("No entries cleared.")
    else:
        ctx.log(f"Total cleared: {cleared_total}")

    if ctx.json_output:
        ctx.output.update(
            {
                "status": "success",
                "cleared_count": cleared_total,
            }
        )
        ctx.output.output()


@retry.command(name="now")
@click.option(
    "--activity-id",
    type=int,
    help="Force retry of specific activity ID",
)
@pass_context
def retry_now(ctx: Context, activity_id: int | None) -> None:
    """Force immediate retry of pending activities.

    Resets the next_retry_after time to now, so activities will be
    retried on the next sync.
    """
    from datetime import datetime

    from mykrok.config import ensure_data_dir
    from mykrok.lib.paths import iter_athlete_dirs
    from mykrok.models.state import load_retry_queue, save_retry_queue

    config = ctx.config
    if config is None:
        ctx.error("Configuration not loaded")
        sys.exit(1)

    data_dir = ensure_data_dir(config)
    reset_total = 0
    now = datetime.now()

    for username, _athlete_dir in iter_athlete_dirs(data_dir):
        queue = load_retry_queue(data_dir, username)

        if queue.get_pending_count() == 0:
            continue

        reset = 0
        for entry in queue.failed_activities:
            if entry.is_permanently_failed():
                continue

            if activity_id is not None:
                if entry.activity_id == activity_id:
                    entry.next_retry_after = now
                    reset = 1
                    break
            else:
                entry.next_retry_after = now
                reset += 1

        if reset > 0:
            save_retry_queue(data_dir, username, queue)
            ctx.log(f"Reset {reset} entries for {username} - will retry on next sync")
            reset_total += reset

    if reset_total == 0:
        ctx.log("No entries to reset.")
    else:
        ctx.log(f"Total reset: {reset_total} - run 'strava-backup sync' to retry")

    if ctx.json_output:
        ctx.output.update(
            {
                "status": "success",
                "reset_count": reset_total,
            }
        )
        ctx.output.output()


if __name__ == "__main__":
    main()
