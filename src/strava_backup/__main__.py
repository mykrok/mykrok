"""Entry point for running strava-backup as a module.

Usage:
    python -m strava_backup [command] [options]
"""

from strava_backup.cli import main

if __name__ == "__main__":
    main()
