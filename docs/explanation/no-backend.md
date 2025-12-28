# Why No Backend

MyKrok generates a static HTML file that works without a server. This design is intentional.

## The Problem with Backends

Traditional activity trackers require:

- Running server process
- Database management
- Authentication system
- Hosting infrastructure
- Ongoing maintenance

For a personal backup tool, this is overkill.

## The Static File Solution

MyKrok's browser is a single HTML file that:

- Opens directly in any browser
- Loads data from local files
- Works offline
- Requires no server

```
mykrok.html + data/ = Complete application
```

## How It Works

### Data Loading

The browser reads data files directly:

```javascript
// Load TSV index
const response = await fetch('athl=username/sessions.tsv');
const sessions = parseTSV(await response.text());

// Load Parquet tracks (using hyparquet)
const track = await readParquet('athl=username/ses=.../tracking.parquet');
```

### File Protocol

Opening `mykrok.html` from the filesystem (file://) works because:

- Modern browsers allow local file access
- No CORS restrictions for local files
- All dependencies are embedded

### Server Optional

For development or sharing, use any static server:

```bash
# Python
python -m http.server 8080

# Node.js
npx serve

# MyKrok built-in
mykrok create-browser --serve
```

## Benefits

### Simplicity

- No installation beyond the HTML file
- No database to configure
- No processes to manage

### Portability

- Copy to USB drive
- Email to yourself
- Host anywhere (S3, GitHub Pages, any web server)

### Privacy

- Data never leaves your machine
- No accounts needed
- No tracking or analytics

### Durability

- Plain files on disk
- Standard formats (JSON, TSV, Parquet)
- Readable by any tool (DuckDB, pandas, grep)

### Offline Access

- Works without internet
- View activities anywhere
- No dependency on external services

## Trade-offs

### No Real-time Sync

- Must run `mykrok sync` manually
- No push notifications
- Data is point-in-time snapshot

### Limited Interactivity

- Read-only browsing
- No editing activities
- No social features

### File Size

- Large histories mean large data directories
- Photos consume most space
- Parquet helps with GPS data

## When to Use a Backend

Consider a full application if you need:

- Real-time sync with Strava
- Multi-user access
- Mobile app integration
- Activity editing
- Social features

For personal backup and offline browsing, static files are ideal.

## Technical Details

### Browser Compatibility

The generated HTML works in:

- Chrome/Chromium
- Firefox
- Safari
- Edge

Requires JavaScript enabled.

### Embedded Dependencies

The HTML embeds:

- Leaflet.js (maps)
- Chart.js (statistics)
- hyparquet (Parquet reading)
- Custom CSS

No external CDN dependencies.

### File Size

A typical `mykrok.html` is ~500KB:

- 200KB JavaScript (minified)
- 150KB CSS
- 100KB HTML template
- 50KB icons/assets

Data files are separate and loaded on demand.
