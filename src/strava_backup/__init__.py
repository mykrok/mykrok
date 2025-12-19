"""Strava Activity Backup and Visualization CLI Tool.

A command-line tool to backup Strava activities (metadata, GPS tracks, photos,
comments, kudos) with incremental sync, store in Hive-partitioned layout for
DuckDB queries, generate interactive map visualizations, and export to FitTrackee.
"""

__version__ = "0.1.0"
__author__ = "strava-backup contributors"
__license__ = "MIT"

__all__ = ["__version__"]
