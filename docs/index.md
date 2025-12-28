# MyKrok Documentation

**CLI tool for fitness activity backup with map visualization**

MyKrok backs up your Strava activities to local files, with incremental sync, GPS tracking, photos, and an interactive map browser that works offline.

<div class="grid cards" markdown>

-   :material-school:{ .lg .middle } __Tutorials__

    ---

    New to MyKrok? Start here with step-by-step guides.

    [:octicons-arrow-right-24: Getting Started](tutorials/getting-started.md)

-   :material-book-open-variant:{ .lg .middle } __How-to Guides__

    ---

    Solve specific problems: automate syncs, export data, recover photos.

    [:octicons-arrow-right-24: How-to Guides](how-to/index.md)

-   :material-file-document:{ .lg .middle } __Reference__

    ---

    Technical details: CLI commands, configuration, data format.

    [:octicons-arrow-right-24: Reference](reference/index.md)

-   :material-lightbulb:{ .lg .middle } __Explanation__

    ---

    Understand the design: architecture, storage model, why no backend.

    [:octicons-arrow-right-24: Explanation](explanation/index.md)

</div>

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
