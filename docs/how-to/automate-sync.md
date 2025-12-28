# Automate Syncs

Set up automatic daily backups of your Strava activities.

## Using cron

The simplest way to automate syncs is with cron.

### Step 1: Find Your Installation

```bash
which mykrok
# Example: /home/user/.local/bin/mykrok
```

### Step 2: Edit Crontab

```bash
crontab -e
```

### Step 3: Add Sync Job

Add a line to sync daily at 2 AM:

```cron
0 2 * * * cd /path/to/your/data && /home/user/.local/bin/mykrok sync --quiet
```

!!! tip "Using uv"
    If you installed with uv:
    ```cron
    0 2 * * * cd /path/to/data && /home/user/.local/bin/uv run mykrok sync --quiet
    ```

### Options for Cron

- `--quiet` - Only output errors
- `--lean-update` - Skip sync if already up to date

```cron
# Lean sync - skip if no new activities
0 2 * * * cd /path/to/data && mykrok sync --quiet --lean-update
```

## Using systemd

For more control, use a systemd timer.

### Step 1: Create Service File

Create `/etc/systemd/user/mykrok-sync.service`:

```ini
[Unit]
Description=MyKrok Strava Sync
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/your/data
ExecStart=/home/user/.local/bin/mykrok sync --quiet
```

### Step 2: Create Timer File

Create `/etc/systemd/user/mykrok-sync.timer`:

```ini
[Unit]
Description=Daily MyKrok sync

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

### Step 3: Enable Timer

```bash
systemctl --user daemon-reload
systemctl --user enable mykrok-sync.timer
systemctl --user start mykrok-sync.timer
```

### Step 4: Check Status

```bash
systemctl --user status mykrok-sync.timer
systemctl --user list-timers
```

## Handling Errors

### Logging

Redirect output to a log file:

```cron
0 2 * * * cd /path/to/data && mykrok sync >> /var/log/mykrok.log 2>&1
```

### Email Notifications

Cron sends email on errors by default. Configure with:

```cron
MAILTO=your@email.com
0 2 * * * cd /path/to/data && mykrok sync --quiet
```

### Rate Limits

If you hit Strava's rate limit:

- The sync pauses automatically
- It resumes when the limit resets
- No action needed

## Regenerating the Browser

To keep your map browser up to date, add a second job:

```cron
# Sync at 2 AM
0 2 * * * cd /path/to/data && mykrok sync --quiet

# Regenerate browser at 3 AM
0 3 * * * cd /path/to/data && mykrok create-browser
```

## Git/DataLad Integration

If using DataLad, commit changes after sync:

```cron
0 2 * * * cd /path/to/data && mykrok sync --quiet && datalad save -m "Daily sync"
```
