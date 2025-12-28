# Architecture

How MyKrok is structured and how the components work together.

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         User                                │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│   CLI (click)   │     │  Map Browser    │
│                 │     │  (JavaScript)   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│    Services     │     │   Data Files    │◄───────┐
│  (Python)       │────▶│  (TSV/Parquet)  │        │
└────────┬────────┘     └─────────────────┘        │
         │                                          │
         ▼                                          │
┌─────────────────┐                                 │
│  External APIs  │                                 │
│  (Strava, etc.) │─────────────────────────────────┘
└─────────────────┘
```

## Components

### CLI Layer

The command-line interface built with Click provides:

- **Commands**: `auth`, `sync`, `view stats`, `create-browser`, etc.
- **Options**: Global flags for config, verbosity, output format
- **Help**: Auto-generated help text

```python
# Entry point: src/mykrok/cli.py
@click.group()
def main():
    """MyKrok - Fitness activity backup."""
    pass
```

### Service Layer

Business logic is organized into services:

| Service | Responsibility |
|---------|----------------|
| `backup.py` | Core sync logic, activity processing |
| `strava.py` | Strava API client, OAuth handling |
| `fittrackee.py` | FitTrackee export |
| `migrate.py` | Data schema migrations |
| `datalad.py` | DataLad integration |
| `gh_pages.py` | Demo site generation |

### Data Models

Python dataclasses model the domain:

```python
# src/mykrok/models/
activity.py   # Activity metadata
athlete.py    # Athlete profile
tracking.py   # GPS/sensor streams
state.py      # Sync state tracking
```

### Views

HTML generation for the browser:

```python
# src/mykrok/views/
map.py    # Interactive map HTML
stats.py  # Statistics charts
```

### Assets

JavaScript and CSS for the browser:

```
src/mykrok/assets/
├── map-browser/
│   ├── map-browser.js     # Main application
│   ├── date-utils.js      # Date formatting
│   ├── tsv-utils.js       # TSV parsing
│   └── photo-viewer.js    # Photo lightbox
└── hyparquet/             # Parquet reader
```

## Data Flow

### Sync Flow

```
Strava API ──▶ backup.py ──▶ Data Files
                   │
                   ├──▶ info.json (metadata)
                   ├──▶ tracking.parquet (GPS)
                   ├──▶ photos/*.jpg
                   └──▶ sessions.tsv (index)
```

### Browser Flow

```
Data Files ──▶ Browser ──▶ User
     │
     ├──▶ athletes.tsv (loaded first)
     ├──▶ sessions.tsv (per athlete)
     ├──▶ tracking.parquet (on demand)
     └──▶ info.json (on demand)
```

## Storage Architecture

### Hive Partitioning

Data is organized in Hive-style partitions:

```
data/
└── athl={username}/
    └── ses={datetime}/
```

This enables:

- **Efficient querying**: DuckDB reads partitions directly
- **Human navigation**: Easy to find specific activities
- **Git-friendly**: Clear directory structure

### File Format Choices

| Data | Format | Why |
|------|--------|-----|
| Metadata | JSON | Human readable, flexible schema |
| Indexes | TSV | Git-friendly, universal compatibility |
| GPS/sensors | Parquet | Efficient, columnar, browser-compatible |
| Photos | JPEG/PNG | Standard image formats |

## Browser Architecture

The map browser is a single-page application (SPA):

```
┌────────────────────────────────────────────┐
│              HTML Container                │
│  ┌──────────────────────────────────────┐  │
│  │           Map View (Leaflet)         │  │
│  │  ┌────────────┐  ┌────────────────┐  │  │
│  │  │   Legend   │  │ Activities     │  │  │
│  │  │            │  │ Panel          │  │  │
│  │  └────────────┘  └────────────────┘  │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │           Filter Bar                 │  │
│  └──────────────────────────────────────┘  │
└────────────────────────────────────────────┘
```

### Key Components

- **MapView**: Leaflet map with markers and tracks
- **FilterBar**: Date, type, and search filters
- **ActivityPanel**: List of activities
- **SessionDetail**: Activity detail view
- **PhotoViewer**: Lightbox for photos
- **StatsView**: Charts and statistics

### Data Loading

1. Load `athletes.tsv` (small, contains athlete list)
2. Load `sessions.tsv` for each athlete (index)
3. Lazy-load `tracking.parquet` when track requested
4. Lazy-load `info.json` for details

### URL State

State is encoded in the URL hash:

```
#view=map&from=2025-01-01&type=Run&track=username,20251218T063000
```

This enables:

- Shareable links
- Browser back/forward
- Bookmarking

## Extension Points

### Adding a New Sync Source

1. Create a new service in `src/mykrok/services/`
2. Implement activity fetching and storage
3. Add CLI command in `cli.py`

### Adding a New Export Format

1. Create export service
2. Map activity data to target format
3. Add CLI command

### Customizing the Browser

1. Modify JavaScript in `src/mykrok/assets/map-browser/`
2. Update HTML generation in `src/mykrok/views/map.py`
3. Run `npm test` to verify
