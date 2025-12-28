# MyKrok Documentation

**CLI tool for fitness activity backup with map visualization**

MyKrok backs up your Strava activities to local files, with incremental sync, GPS tracking, photos, and an interactive map browser that works offline.

**[Live Demo](https://mykrok.github.io/mykrok/)** - Try the web frontend with synthetic data.

![Map view with activity markers](screenshots/01-map-overview.jpg)

## Documentation

| Section | Description |
|---------|-------------|
| **[Tutorials](tutorials/index.md)** | New to MyKrok? Start here with step-by-step guides. |
| **[How-to Guides](how-to/index.md)** | Solve specific problems: automate syncs, export data, recover photos. |
| **[Reference](reference/index.md)** | Technical details: CLI commands, configuration, data format. |
| **[Explanation](explanation/index.md)** | Understand the design: architecture, storage model, why no backend. |

## Quick Start

```bash
# Install
pip install mykrok

# Authenticate with Strava
mykrok auth --client-id YOUR_ID --client-secret YOUR_SECRET

# Sync your activities
mykrok sync

# View interactive map
mykrok create-browser --serve
```

## Key Features

- **Incremental sync** - Only downloads new activities
- **GPS tracking** - Stored as efficient [Parquet files](reference/data-model.md#track-gpssensor-data)
- **Photos & social** - Comments, kudos, and activity photos
- **Interactive map** - Browse activities on an interactive map
- **Works offline** - Generated HTML works without a server
- **Export options** - [GPX files](reference/cli.md#mykrok-gpx), [FitTrackee migration](how-to/export-fittrackee.md)
- **DataLad integration** - [Version control](how-to/use-datalad.md) for your fitness data

## Why MyKrok?

- **Your data, your control** - Activities stored as [local files](reference/data-model.md)
- **No backend required** - [Static files](explanation/no-backend.md) work anywhere
- **Query-friendly** - Use [DuckDB, pandas](reference/data-model.md#querying-with-duckdb), or any data tool
- **Git-compatible** - [Version control](how-to/use-datalad.md) your fitness history

## Screenshots

### Map View

![Activities zoomed to fit](screenshots/02-map-zoomed.jpg)
*Activities zoomed to fit with GPS tracks*

![Activity popup with details](screenshots/03-map-popup.jpg)
*Activity popup with details and photos*

### Sessions & Statistics

![Sessions list with filters](screenshots/04-sessions-list.jpg)
*Sessions list with date and type filters*

![Statistics dashboard](screenshots/09-stats-dashboard.jpg)
*Statistics dashboard with charts*

See the [Exploring Your Data](tutorials/exploring-your-data.md) tutorial for a complete walkthrough.
