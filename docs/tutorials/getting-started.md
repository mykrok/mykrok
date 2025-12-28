# Getting Started

This tutorial walks you through setting up MyKrok and syncing your first activities.

## Prerequisites

- Python 3.10 or later
- A Strava account with activities
- A Strava API application (free, we'll set it up below)

## Step 1: Install MyKrok

=== "pip"

    ```bash
    pip install mykrok
    ```

=== "uv (recommended)"

    ```bash
    uv pip install mykrok
    ```

=== "From source"

    ```bash
    git clone https://github.com/mykrok/mykrok
    cd mykrok
    pip install -e .
    ```

Verify the installation:

```bash
mykrok --version
```

## Step 2: Create a Strava API Application

1. Go to [Strava API Settings](https://www.strava.com/settings/api)

2. Create a new application with these settings:
    - **Application Name**: "My Backup Tool" (or any name)
    - **Category**: Personal
    - **Website**: `http://localhost`
    - **Authorization Callback Domain**: `localhost`

3. Note your **Client ID** and **Client Secret**

!!! tip
    The Client ID is a number like `12345`. The Client Secret is a long alphanumeric string.

## Step 3: Authenticate with Strava

Run the auth command with your credentials:

```bash
mykrok auth --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET
```

This will:

1. Open your browser to Strava's authorization page
2. Ask you to grant access to your activities
3. Save the OAuth token locally

!!! note
    Tokens are stored in `.mykrok/oauth-tokens.toml` and automatically refresh when expired.

## Step 4: Sync Your Activities

Now sync your activities:

```bash
mykrok sync
```

For your first sync, this downloads all your activities. You'll see progress like:

```
Syncing activities for your_username...
  [1/150] Morning Run (20251218T063000) - 5.2 km
  [2/150] Evening Walk (20251217T180000) - 2.1 km
  ...
Synced 150 activities (150 new, 0 updated)
```

!!! tip "Large History?"
    If you have many years of activities, the first sync may take a while. Consider running it overnight. Strava rate limits apply automatically.

## Step 5: View Your Data

Generate and view the interactive browser:

```bash
mykrok create-browser --serve
```

This opens `http://127.0.0.1:8080` in your browser with:

- **Map View**: All activities on an interactive map
- **Sessions**: Filterable list of all activities
- **Stats**: Charts and statistics

## What's Next?

Now that you have your data:

- Learn to [explore your data](exploring-your-data.md) in the map browser
- [Automate daily syncs](../how-to/automate-sync.md) with cron
- [Export to FitTrackee](../how-to/export-fittrackee.md)
- [Query your data](../reference/data-model.md) with DuckDB

## Directory Structure

After syncing, your data directory looks like:

```
data/
├── athletes.tsv              # Summary of all athletes
└── athl=your_username/
    ├── athlete.json          # Your profile
    ├── sessions.tsv          # Activity summary
    └── ses=20251218T063000/  # Individual activity
        ├── info.json         # Metadata
        ├── tracking.parquet  # GPS + sensors
        └── photos/
            └── 20251218T063500.jpg
```

## Troubleshooting

### Token Expired

```bash
mykrok auth --force
```

### Rate Limit Hit

The tool automatically pauses and resumes. For large initial syncs, run overnight.

### Missing GPS Data

Some activities (treadmill, manual entries) have no GPS. They appear in sessions.tsv but not on maps.
