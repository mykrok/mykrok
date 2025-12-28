# Use with DataLad

Version control your fitness data with DataLad for full history tracking.

## What is DataLad?

[DataLad](https://www.datalad.org/) is a data management tool built on Git and git-annex. It lets you:

- Track changes to large files (photos, GPS data)
- Version your entire fitness history
- Sync data across machines
- Share datasets with others

## Setting Up DataLad

### Install DataLad

```bash
pip install datalad
```

### Create a DataLad Dataset

```bash
mykrok create-datalad-dataset
```

This initializes your data directory as a DataLad dataset with:

- Git for text files (JSON, TSV)
- git-annex for binary files (photos, Parquet)
- Appropriate `.gitattributes` rules

## Workflow

### After Each Sync

Save changes to the dataset:

```bash
mykrok sync
datalad save -m "Daily sync"
```

### View History

See all changes:

```bash
git log --oneline
datalad diff --from HEAD~5
```

### Restore Previous Version

```bash
# View a specific activity from the past
git show HEAD~10:data/athl=username/ses=20251218T063000/info.json

# Restore a file
git checkout HEAD~10 -- data/athl=username/ses=20251218T063000/info.json
```

## Remote Storage

### Push to GitHub

```bash
# Create sibling
datalad create-sibling-github mykrok-data

# Push
datalad push --to github
```

### Push to Another Machine

```bash
# On remote machine
datalad clone ssh://user@remote/path/to/data

# Sync data
datalad get .
```

## Automated Saves

Combine with cron for automatic version control:

```cron
0 2 * * * cd /path/to/data && mykrok sync --quiet && datalad save -m "Daily sync $(date +%Y-%m-%d)"
```

## Large File Handling

Photos and Parquet files are stored in git-annex:

```bash
# Check which files are annexed
git annex whereis data/athl=username/ses=20251218T063000/photos/

# Get specific files
datalad get data/athl=username/ses=20251218T063000/photos/

# Drop to save space (keeps in remote)
datalad drop data/athl=username/ses=20251218T063000/photos/
```

## Migration from Existing Data

If you already have MyKrok data:

```bash
cd /path/to/existing/data
datalad create --force .
datalad save -m "Initial import"
```

## Best Practices

1. **Save after each sync** - Keep a clean history
2. **Use meaningful messages** - Include date or activity count
3. **Push regularly** - Keep remote backup current
4. **Don't modify manually** - Let MyKrok manage files

## Troubleshooting

### "Not a datalad dataset"

Initialize the dataset:

```bash
datalad create --force .
```

### git-annex Lock Issues

```bash
git annex unlock data/athl=username/ses=20251218T063000/photos/
```

### Large Clone Size

Use partial clones:

```bash
datalad clone --reckless fast ssh://remote/path
datalad get -n .  # Get metadata only
datalad get data/athl=username/ses=20251218T063000/  # Get specific files
```
