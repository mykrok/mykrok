"""Strava Activity Backup and Visualization CLI Tool.

A command-line tool to backup Strava activities (metadata, GPS tracks, photos,
comments, kudos) with incremental sync, store in Hive-partitioned layout for
DuckDB queries, generate interactive map visualizations, and export to FitTrackee.
"""

try:
    from strava_backup._version import __version__
except ImportError:
    # Fallback for development without build
    __version__ = "0.0.0.dev0+unknown"

__author__ = "strava_backup contributors"
__license__ = "Apache-2.0"

__all__ = ["__version__"]
