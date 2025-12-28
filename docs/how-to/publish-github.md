# Publish to GitHub Pages

Share your activity map as a public website using GitHub Pages.

!!! warning "Privacy"
    Publishing to GitHub Pages makes your activities publicly visible. Consider using demo data or filtering out private activities.

## Quick Start

Generate and push a demo site:

```bash
mykrok gh-pages --push
```

Your site will be available at `https://username.github.io/mykrok/`.

## How It Works

The `gh-pages` command:

1. Creates a `gh-pages` branch (or uses existing)
2. Generates synthetic demo data (for privacy)
3. Creates the map browser
4. Optionally pushes to GitHub

## Using Your Real Data

To publish your actual activities:

```bash
# First sync your data
mykrok sync

# Generate browser with real data
mykrok create-browser

# Manually copy to gh-pages branch
git checkout gh-pages
cp data/mykrok.html .
git add mykrok.html
git commit -m "Update activity browser"
git push origin gh-pages
```

!!! tip
    Consider filtering out private activities before publishing.

## Custom Domain

To use a custom domain:

1. Add a `CNAME` file to the gh-pages branch:
   ```
   activities.example.com
   ```

2. Configure DNS to point to GitHub Pages

3. Enable HTTPS in repository settings

## Automating Updates

Use GitHub Actions to update automatically:

```yaml
# .github/workflows/update-pages.yml
name: Update GitHub Pages

on:
  schedule:
    - cron: '0 4 * * *'  # Daily at 4 AM
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install mykrok
      - run: mykrok gh-pages --push
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Demo Mode Options

Control demo data generation:

```bash
# Use specific random seed (reproducible)
mykrok gh-pages --seed 42

# Skip datalad even if available
mykrok gh-pages --no-datalad

# Custom worktree path
mykrok gh-pages --worktree /tmp/gh-pages
```

## Repository Setup

Ensure GitHub Pages is enabled:

1. Go to repository Settings > Pages
2. Set Source to "Deploy from a branch"
3. Select "gh-pages" branch
4. Save

The site deploys automatically after push.
