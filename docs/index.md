# MyKrok Documentation

**CLI tool for fitness activity backup with map visualization**

MyKrok backs up your Strava activities to local files, with incremental sync, GPS tracking, photos, and an interactive map browser that works offline.

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
- **GPS tracking** - Stored as efficient Parquet files
- **Photos & social** - Comments, kudos, and activity photos
- **Interactive map** - Browse activities on an interactive map
- **Works offline** - Generated HTML works without a server
- **Export options** - GPX files, FitTrackee migration
- **DataLad integration** - Version control for your fitness data

## Why MyKrok?

- **Your data, your control** - Activities stored as local files
- **No backend required** - Static files work anywhere
- **Query-friendly** - Use DuckDB, pandas, or any data tool
- **Git-compatible** - Version control your fitness history
