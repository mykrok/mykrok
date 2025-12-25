# Unified Web Frontend Implementation Plan

## Overview

Transform the existing lightweight map into a full single-page application with tab navigation, athlete selection, sessions browser, and statistics dashboard. All functionality runs client-side with no backend required.

## Architecture

The implementation extends `generate_lightweight_map()` in `src/mykrok/views/map.py` to produce a more comprehensive HTML file. The key architectural decisions:

1. **Single HTML file**: All CSS and JavaScript embedded inline
2. **Module structure**: JavaScript organized into logical modules within the same file
3. **State management**: Simple global state object with event-based updates
4. **Routing**: Hash-based routing (`#/map`, `#/sessions`, `#/stats`)
5. **Data layer**: Shared data loading with caching

---

## Phase 1: App Shell and Navigation (Complexity: Medium)

**Goal**: Create the basic application structure with navigation that preserves the existing map functionality.

### 1.1 HTML Structure
Add app shell markup around existing map:
```html
<div id="app">
  <header id="app-header">
    <div class="logo">MyKrok</div>
    <nav id="main-nav">
      <a href="#/map" class="nav-tab active">Map</a>
      <a href="#/sessions" class="nav-tab">Sessions</a>
      <a href="#/stats" class="nav-tab">Stats</a>
    </nav>
    <div id="athlete-selector">...</div>
  </header>
  <main id="app-content">
    <div id="view-map" class="view active"><!-- existing map --></div>
    <div id="view-sessions" class="view"></div>
    <div id="view-stats" class="view"></div>
  </main>
</div>
```

### 1.2 CSS for Layout
- Fixed header (56px)
- Full-height main content
- View containers with `display: none` except active
- Mobile responsive with bottom nav at < 768px

### 1.3 JavaScript Router
```javascript
const Router = {
  routes: { map: showMapView, sessions: showSessionsView, stats: showStatsView },
  init() {
    window.addEventListener('hashchange', () => this.navigate());
    this.navigate();
  },
  navigate() {
    const hash = location.hash.slice(2) || 'map';
    const [view, ...params] = hash.split('/');
    this.routes[view]?.(params);
  }
};
```

### 1.4 Code Changes
- Modify `generate_lightweight_map()` to return extended HTML
- Wrap existing map initialization in `showMapView()` function
- Add CSS for header, navigation, views

### Estimated Lines of Code: ~300 (CSS) + ~150 (JS router/navigation)

---

## Phase 2: Athlete Selector (Complexity: Low-Medium)

**Goal**: Add dropdown to switch between athletes; support "All Athletes" mode for map.

### 2.1 Athlete Selector Component
```javascript
const AthleteSelector = {
  current: null,
  athletes: [],
  init(athletes) {
    this.athletes = athletes;
    this.current = athletes[0]?.username;
    this.render();
  },
  render() {
    // Render dropdown with athlete list + "All Athletes" option
  },
  select(username) {
    this.current = username;
    EventBus.emit('athlete-changed', username);
  }
};
```

### 2.2 Data Flow Updates
- Refactor session loading to support athlete filtering
- Add athlete color palette for multi-athlete map mode
- Update map markers to indicate athlete when "All Athletes" selected

### 2.3 UI Elements
- Avatar with initials (deterministic color from username)
- Dropdown showing username, session count, distance totals
- Selected state indicator

### Estimated Lines of Code: ~200 (JS) + ~100 (CSS)

---

## Phase 3: Sessions List View (Complexity: Medium-High)

**Goal**: Create a filterable, sortable sessions table with detail panel.

### 3.1 Sessions Table Structure
```html
<div id="view-sessions">
  <div class="filter-bar">
    <input type="search" id="session-search" placeholder="Search...">
    <select id="type-filter">...</select>
    <input type="date" id="date-from">
    <input type="date" id="date-to">
    <button id="clear-filters">Clear</button>
  </div>
  <div class="sessions-table-container">
    <table id="sessions-table">...</table>
  </div>
  <div class="pagination">...</div>
</div>
```

### 3.2 Sessions Controller
```javascript
const SessionsController = {
  sessions: [],
  filtered: [],
  sortBy: 'datetime',
  sortDir: 'desc',
  filters: { search: '', type: '', dateFrom: null, dateTo: null },

  init(sessions) {
    this.sessions = sessions;
    this.applyFilters();
    this.render();
  },

  applyFilters() {
    this.filtered = this.sessions.filter(s => {
      if (this.filters.search && !s.name.toLowerCase().includes(this.filters.search)) return false;
      if (this.filters.type && s.type !== this.filters.type) return false;
      // date filters...
      return true;
    });
    this.sort();
  },

  sort() {
    this.filtered.sort((a, b) => {
      const cmp = a[this.sortBy] > b[this.sortBy] ? 1 : -1;
      return this.sortDir === 'desc' ? -cmp : cmp;
    });
  },

  render() {
    // Render table rows with pagination
  }
};
```

### 3.3 Session Detail Panel
Slide-in panel (400px width) showing:
- Activity name, type, date
- Stats cards (distance, time, elevation)
- Mini-map thumbnail (click to navigate to map view)
- Photo grid (load from info.json)
- Kudos/comments list
- Cross-athlete links

### 3.4 Mobile Adaptation
- Card layout instead of table
- Filter panel as modal
- Detail panel as full-screen modal

### Estimated Lines of Code: ~500 (JS) + ~300 (CSS)

---

## Phase 4: Stats Dashboard (Complexity: Medium)

**Goal**: Display aggregate statistics with charts.

### 4.1 Stats View Structure
```html
<div id="view-stats">
  <div class="stats-filters">
    <select id="year-filter">...</select>
    <select id="stats-type-filter">...</select>
  </div>
  <div class="summary-cards">
    <div class="stat-card">...</div>
  </div>
  <div class="chart-container" id="monthly-chart"></div>
  <div class="chart-container" id="type-chart"></div>
</div>
```

### 4.2 Stats Calculator (Client-side)
```javascript
const StatsCalculator = {
  calculate(sessions, { year, type } = {}) {
    const filtered = sessions.filter(s => {
      if (year && s.datetime.slice(0, 4) !== String(year)) return false;
      if (type && s.type !== type) return false;
      return true;
    });

    return {
      totals: this.calculateTotals(filtered),
      byMonth: this.groupByMonth(filtered),
      byType: this.groupByType(filtered)
    };
  },

  calculateTotals(sessions) {
    return {
      count: sessions.length,
      distance: sessions.reduce((s, a) => s + parseFloat(a.distance_m || 0), 0),
      time: sessions.reduce((s, a) => s + parseInt(a.moving_time_s || 0), 0),
      elevation: sessions.reduce((s, a) => s + parseFloat(a.elevation_gain_m || 0), 0)
    };
  }
  // ...
};
```

### 4.3 Charts (Canvas-based, no dependencies)
Simple bar charts using Canvas API:
- Monthly activity chart (count or distance)
- By-type horizontal bar chart

### 4.4 Interactions
- Click month bar: Filter sessions view to that month
- Click type bar: Filter sessions view to that type
- Year selector: Recalculate all stats

### Estimated Lines of Code: ~400 (JS) + ~200 (CSS) + ~200 (Chart rendering)

---

## Phase 5: Cross-View Integration (Complexity: Medium)

**Goal**: Enable navigation and filtering across views.

### 5.1 URL State Management
```javascript
const URLState = {
  parse() {
    const hash = location.hash.slice(2);
    const [path, queryStr] = hash.split('?');
    const params = new URLSearchParams(queryStr || '');
    return { path: path.split('/'), params };
  },

  update(path, params) {
    const queryStr = new URLSearchParams(params).toString();
    location.hash = '#/' + path + (queryStr ? '?' + queryStr : '');
  }
};
```

### 5.2 Cross-View Navigation
- Map marker click: Show session in detail panel, optionally navigate to sessions view
- Sessions row click: Open detail panel with "View on Map" button
- Stats chart click: Navigate to filtered sessions view
- Kudos/comment athlete names: Link to that athlete's sessions (if local)

### 5.3 Shared Runs Detection
```javascript
function findSharedSessions(datetime, currentAthlete, allAthletesSessions) {
  return Object.entries(allAthletesSessions)
    .filter(([username, sessions]) =>
      username !== currentAthlete && sessions.some(s => s.datetime === datetime)
    )
    .map(([username]) => username);
}
```

### Estimated Lines of Code: ~200 (JS)

---

## Phase 6: Polish and Mobile (Complexity: Medium)

**Goal**: Responsive design, loading states, error handling.

### 6.1 Loading States
- Skeleton loaders for table rows
- Spinner overlay for view transitions
- Progress indicator for batch data loading

### 6.2 Empty States
- No athletes found
- No sessions match filter
- No GPS data for session

### 6.3 Error Handling
- Retry buttons for failed fetches
- Graceful degradation (skip invalid entries)
- Console logging for debugging

### 6.4 Mobile Bottom Navigation
```html
<nav id="mobile-nav" class="bottom-nav">
  <a href="#/map" class="nav-item"><svg>...</svg><span>Map</span></a>
  <a href="#/sessions" class="nav-item"><svg>...</svg><span>Sessions</span></a>
  <a href="#/stats" class="nav-item"><svg>...</svg><span>Stats</span></a>
</nav>
```

### 6.5 Touch Interactions
- Swipe to close detail panel
- Pull-to-refresh indicator (visual only, triggers reload)

### Estimated Lines of Code: ~300 (CSS) + ~200 (JS)

---

## Testing Approach

### Unit Tests (pytest)
Add to `tests/unit/test_unified_frontend.py`:

1. **HTML Structure Tests**
   - Verify generated HTML contains required elements
   - Verify CSS variables are present
   - Verify JavaScript modules are included

2. **Data Embedding Tests**
   - Verify type colors are correctly embedded
   - Verify activity type lists are complete

3. **Integration with Existing Map**
   - Verify lightweight map features still work
   - Verify parquet loading still works

### Manual Testing Checklist
1. Load app in browser, verify all three views render
2. Switch athletes, verify data updates
3. Test session filtering and sorting
4. Verify stats calculations match `mykrok view stats` output
5. Test on mobile device (or DevTools responsive mode)
6. Test with no athletes (empty state)
7. Test with single athlete (no "All Athletes" option)

### E2E Tests with Sample Data

#### Sample Data Generation
Create `tests/e2e/fixtures/` with synthetic multi-athlete data:

```
tests/e2e/fixtures/
├── athletes.tsv              # Two athletes: alice, bob
├── athl=alice/
│   ├── sessions.tsv          # 10 sample sessions
│   └── ses=20241218T063000/
│       ├── tracking.parquet  # With GPS, heart rate, cadence
│       ├── info.json         # Photos, kudos from bob, comments
│       └── photos/           # 2 sample photos
├── athl=bob/
│   ├── sessions.tsv          # 5 sample sessions
│   └── ses=20241218T063000/  # Shared run with alice
│       ├── tracking.parquet
│       └── info.json
└── generate_fixtures.py      # Script to regenerate fixtures
```

#### E2E Test Scenarios (pytest-playwright or similar)

1. **App Launch**
   - Verify favicon loads without 404
   - Verify all three nav tabs are present
   - Verify athlete selector shows "All Athletes (15 sessions, X km)"

2. **Map View**
   - Verify markers appear on map
   - Click marker, verify popup shows session info
   - Zoom in, verify tracks auto-load
   - Switch athlete, verify markers filter

3. **Sessions View**
   - Verify table shows correct session count
   - Test search filter
   - Test type filter
   - Test date range filter
   - Test sorting by each column
   - Click session, verify detail panel opens
   - Verify detail shows: stats, map, photos, kudos, comments
   - Click "View on Map", verify navigation works
   - Switch athlete, verify filter applies

4. **Stats View**
   - Verify summary cards show totals
   - Verify monthly chart renders
   - Verify type chart renders
   - Test year filter
   - Test type filter
   - Switch athlete, verify stats recalculate

5. **Shared Run Detection**
   - Verify alice's 20241218T063000 shows "Also: bob"
   - Click cross-link, verify navigation to bob's sessions

6. **Error States**
   - Session without GPS: verify map section hidden (no error)
   - Session without photos: verify photos section hidden
   - Session without social: verify social section hidden

#### Demo Mode
Add CLI option to generate demo with fixtures:
```bash
mykrok demo --output ./demo-data/
# Generates sample data and opens browser to mykrok.html
```

---

## File Changes Summary

### Modified Files
| File | Changes |
|------|---------|
| `src/mykrok/views/map.py` | Extend `generate_lightweight_map()` to produce full SPA |

### New Files
| File | Purpose |
|------|---------|
| `tests/unit/test_unified_frontend.py` | Unit tests for frontend generation |

---

## Implementation Order and Dependencies

```
Phase 1: App Shell ─────────────────────────────────────┐
  │                                                     │
  ▼                                                     │
Phase 2: Athlete Selector ─────────────┐               │
  │                                     │               │
  ▼                                     ▼               ▼
Phase 3: Sessions View            Phase 4: Stats    (Map already works)
  │                                     │
  └──────────────┬──────────────────────┘
                 │
                 ▼
           Phase 5: Integration
                 │
                 ▼
           Phase 6: Polish
```

---

## Complexity Estimates

| Phase | Complexity | Estimated LOC |
|-------|------------|---------------|
| 1. App Shell | Medium | 450 |
| 2. Athlete Selector | Low-Medium | 300 |
| 3. Sessions View | Medium-High | 800 |
| 4. Stats Dashboard | Medium | 800 |
| 5. Integration | Medium | 200 |
| 6. Polish | Medium | 500 |
| **Total** | | **~3050** |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Large HTML file size | Slow initial load | Minify CSS/JS, lazy-load non-critical |
| Browser compatibility | Features may not work | Test in Chrome, Firefox, Safari; use ES2020 baseline |
| Chart library complexity | Scope creep | Keep charts simple, Canvas-based |
| Mobile performance | Slow on phones | Virtual scrolling for sessions list, limit initial data |

---

## Critical Files for Implementation

- `src/mykrok/views/map.py` - Core file to extend with SPA generation
- `src/mykrok/views/stats.py` - Reference for stats calculation logic to port to JS
- `src/mykrok/models/activity.py` - Data model for sessions.tsv columns
- `features/unified-frontend/spec.md` - UX specification for design reference

---

## Future Enhancement: Permalinks/Deep Linking

**Goal**: Preserve UI state in the URL so page refresh maintains the current view.

### URL State to Preserve
- Map zoom level and center position
- Currently selected session (open popup)
- Layer visibility (sessions, tracks, photos)
- Active view (map, sessions, stats)
- Current athlete filter
- Sessions view: current page, sort order, filters

### Implementation Approach
```javascript
const URLState = {
  // Encode state to URL hash
  encode(state) {
    const params = new URLSearchParams();
    if (state.view) params.set('v', state.view);
    if (state.zoom) params.set('z', state.zoom);
    if (state.lat) params.set('lat', state.lat.toFixed(5));
    if (state.lng) params.set('lng', state.lng.toFixed(5));
    if (state.session) params.set('s', state.session);
    if (state.athlete) params.set('a', state.athlete);
    return '#/' + state.view + (params.toString() ? '?' + params.toString() : '');
  },

  // Decode state from URL hash
  decode() {
    const hash = location.hash.slice(2);
    const [path, queryStr] = hash.split('?');
    const params = new URLSearchParams(queryStr || '');
    return {
      view: path || 'map',
      zoom: params.get('z') ? parseInt(params.get('z')) : null,
      lat: params.get('lat') ? parseFloat(params.get('lat')) : null,
      lng: params.get('lng') ? parseFloat(params.get('lng')) : null,
      session: params.get('s'),
      athlete: params.get('a')
    };
  }
};
```

### Priority: Low (Phase 7+)
This enhancement can be implemented after core features are complete.

---

## Future Enhancement: Full-Screen Session View

**Goal**: Allow viewing session details in full-screen mode with permalinks for sharing.

### Current Behavior
- Session details appear in a 400px side panel
- Clicking a session in sessions list opens the panel
- Clicking a map marker shows a popup, then can open panel

### Proposed Enhancement

#### New Route: `#/session/{athlete}/{datetime}`
Add a dedicated full-page session view accessible via:
- `#/session/alice/20241218T063000` - Direct permalink
- Click "Expand" button in side panel
- Click "View Details" in map popup (optional)

#### Full-Screen Layout
```html
<div id="view-session" class="view">
  <header class="session-header">
    <button class="back-btn" onclick="history.back()">← Back</button>
    <h1 class="session-title">{activity name}</h1>
    <div class="session-meta">{date} • {type} • {athlete}</div>
  </header>

  <div class="session-content">
    <!-- Stats cards - larger, more prominent -->
    <section class="session-stats">
      <div class="stat-card large">...</div>
    </section>

    <!-- Full-width map with track -->
    <section class="session-map-full">
      <div id="session-map" style="height: 400px;"></div>
    </section>

    <!-- Data streams charts (if available) -->
    <section class="session-charts">
      <canvas id="hr-chart"></canvas>
      <canvas id="elevation-chart"></canvas>
    </section>

    <!-- Photo gallery - grid layout -->
    <section class="session-photos">
      <div class="photo-grid">...</div>
    </section>

    <!-- Social section -->
    <section class="session-social">
      <div class="kudos-list">...</div>
      <div class="comments-list">...</div>
    </section>

    <!-- Cross-athlete links -->
    <section class="session-shared" id="shared-athletes">
      Also ran with: <a href="#/session/bob/20241218T063000">Bob</a>
    </section>
  </div>
</div>
```

#### Fragment IDs for Deep Linking
Support scrolling to specific sections:
- `#/session/alice/20241218T063000#map` - Scroll to map
- `#/session/alice/20241218T063000#photos` - Scroll to photos
- `#/session/alice/20241218T063000#social` - Scroll to kudos/comments

#### Router Updates
```javascript
const Router = {
  routes: {
    map: showMapView,
    sessions: showSessionsView,
    stats: showStatsView,
    session: showFullSessionView  // New route
  },

  navigate() {
    const hash = location.hash.slice(2) || 'map';
    const [view, ...params] = hash.split('/');
    const fragment = params[params.length - 1]?.split('#')[1];

    if (view === 'session' && params.length >= 2) {
      const [athlete, datetime] = params;
      this.routes.session(athlete, datetime.split('#')[0], fragment);
    } else {
      this.routes[view]?.(params);
    }
  }
};
```

#### UI Integration
- Add "Expand" icon button to side panel header
- Side panel close button navigates back (not just hides)
- Sessions list row click: opens side panel
- Sessions list row double-click: opens full view
- Mobile: always use full view (no side panel)

### Estimated LOC: ~400 (JS) + ~200 (CSS)

### Priority: Medium (Phase 7)
Should be implemented after permalinks/deep linking (shares URL infrastructure).

---

## ✅ DONE: Data Streams Visualization (Phase 8)

**Status**: Basic implementation complete

**Goal**: Rich visualization of activity data streams (heart rate, cadence, power, elevation, speed) with time-series charts.

### What Was Implemented
- **Elevation profile chart**: Grey area fill showing terrain
- **Activity data chart**: Multi-axis chart with HR (red), cadence (blue), power (yellow)
- **Interactive tooltips**: Hover to see values at cursor position
- **Responsive design**: Charts resize with container
- **Performance**: Downsampling for large datasets (max 500 points)
- **X-axis**: Uses distance (km) when available, otherwise time (min)

### TODO: UX Design Required

**Action**: Engage UX designer to create comprehensive design for data streams visualization, including:

1. **Time-Series Charts**
   - Primary X-axis: time (or distance)
   - Elevation profile as grey background fill (standard cycling/running convention)
   - Heart rate, cadence, power as colored line overlays
   - Synchronized hover/crosshair showing values at cursor position
   - Zoom/pan capabilities for detailed inspection

2. **Multi-Stream Overlay Options**
   - Toggle individual streams on/off
   - Dual Y-axis support (e.g., HR on left, power on right)
   - Color coding consistent with activity type colors

3. **Analytical Scatter Plots**
   - Heart rate vs. power (cycling power zones)
   - Heart rate vs. speed/pace
   - Cadence vs. speed
   - Elevation vs. heart rate
   - User-selectable X/Y axes

4. **Basic Analytics**
   - Zone distribution (HR zones, power zones)
   - Time-in-zone pie/bar charts
   - Moving averages (30s, 60s rolling)
   - Lap/split markers on timeline

5. **Integration Points**
   - Session detail panel (compact view)
   - Full-screen session view (expanded charts)
   - Map synchronization (click on chart → highlight position on map)

6. **Mobile Considerations**
   - Touch-friendly zoom/pan
   - Swipe between different chart views
   - Landscape orientation for better chart viewing

### Technical Considerations
- Canvas-based rendering for performance (large datasets)
- Lazy loading of stream data (only when chart visible)
- Downsampling for overview, full resolution on zoom
- Consider lightweight charting library (Chart.js, uPlot) vs. custom Canvas

### Priority: Low (Phase 8)
Depends on full-screen session view (Phase 7) for optimal presentation.

---

## ✅ DONE: Unified Charting Framework (Phase 8 Prerequisite)

**Status**: Implemented

### Implementation
- **Library**: Chart.js 4.4.1 via CDN (cdnjs)
- **Stats View**: Interactive bar charts with hover tooltips and click handlers
- **Data Streams**: Elevation profile and HR/cadence/power overlays

### What Was Done
1. Replaced Canvas-based stats charts with Chart.js
2. Added Chart.js CDN to HTML template
3. Implemented interactive tooltips and click-to-filter functionality
4. Created data streams visualization for full-screen session view

---

## ✅ DONE: Automated Walkthrough and README Screenshots

**Status**: Implemented

### Implementation

- **Screenshot script**: `scripts/generate_screenshots.py` - Playwright-based walkthrough
- **Tox environment**: `tox -e screenshots` - Generates all screenshots
- **Demo data**: `tests/e2e/fixtures/generate_fixtures.py` - Creates synthetic multi-athlete data with "DEMO"-shaped GPS tracks
- **README.md**: Screenshots section with 9 images showing full user journey
- **File tree documentation**: "No Backend Required" section explaining direct file-based architecture

### Screenshots Generated

1. Map view (overview) - World map with activity markers
2. Map view (zoomed) - California region cluster
3. Map view (popup) - Activity details popup
4. Sessions view - Table with filters
5. Sessions view (filtered) - Filtered by type
6. Session detail panel - Side panel with stats, map, data streams
7. Full-screen session view - Expanded view with "DEMO" GPS track
8. Stats dashboard - Charts and summary cards
9. Stats view (filtered) - Filtered by athlete

### Usage

```bash
# Generate screenshots (saves to docs/screenshots/)
tox -e screenshots
```

---

## ✅ DONE: Additional UX Improvements (v0.5.0 - v0.8.0)

**Status**: Implemented across multiple releases

### Map View Enhancements

1. **Clickable Legend Filtering** (v0.5.0)
   - Click activity type in legend to filter map markers
   - Toggle visibility of specific activity types
   - Visual feedback on active/inactive filters

2. **Layers Control with Heatmap Toggle** (v0.5.0)
   - Leaflet layers control for sessions/tracks/heatmap
   - Toggle heatmap visualization on/off
   - Persist layer state across view changes

3. **Date Range Expand Buttons** (v0.6.0)
   - Quick buttons to expand date range by week/month/year
   - Integrated into FilterBar component

4. **Date Navigation Buttons** (v0.5.0)
   - Prev/next day buttons in filter bar
   - Quick navigation through activity timeline

5. **Clickable Dates in Popups** (v0.6.0)
   - Click date in activity popup to filter by that date
   - Quick filtering without using date pickers

6. **Bold Selected Track** (v0.7.0)
   - Highlight selected track with increased weight
   - Better visibility when multiple tracks overlap

7. **Version Display in Header** (v0.6.0)
   - Show mykrok version in map header
   - Links to project repository

### Sessions View Enhancements

1. **Photo Indicators** (v0.8.0)
   - Camera icon badge on sessions with photos
   - Visual indicator in both table and activities panel

2. **Color-coded Activity Type Labels** (v0.7.0)
   - Activity type badges use type-specific colors
   - Consistent with map marker colors

3. **Resizable Activities Panel** (v0.5.0)
   - Drag handle to resize panel width
   - Scroll preservation during resize
   - Touchpad compatibility for resize

### Filter System

1. **Unified FilterBar Component** (v0.5.0)
   - DRY refactor: same component across Map, Sessions, Stats views
   - Consistent filter behavior everywhere

2. **Filter State Preservation** (v0.6.0)
   - "View all sessions" link preserves current filters
   - URL state management for filter parameters

3. **Track Filter Visibility** (v0.8.0)
   - Tracks respect date/type/search filters
   - Only visible sessions load tracks on zoom

### Infrastructure

1. **JavaScript External Modules** (v0.7.0)
   - Extracted JS to map-browser.js
   - ESLint linting configuration
   - Jest unit tests for JS code

2. **REUSE 3.3 Licensing** (v0.7.0)
   - REUSE.toml configuration
   - License files in LICENSES/ directory
   - Proper attribution for vendored libraries

3. **Pre-commit Hooks** (v0.4.0)
   - ruff for Python linting/formatting
   - mypy for type checking
   - codespell for spell checking

---

## Phase Summary: Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | App Shell and Navigation | ✅ Complete |
| Phase 2 | Athlete Selector | ✅ Complete |
| Phase 3 | Sessions List View | ✅ Complete |
| Phase 4 | Stats Dashboard | ✅ Complete |
| Phase 5 | Cross-View Integration | ✅ Complete |
| Phase 6 | Polish and Mobile | ✅ Complete |
| Phase 7 | Permalinks/Deep Linking | ✅ Complete |
| Phase 7b | Full-Screen Session View | ✅ Complete |
| Phase 8 | Data Streams Visualization | ✅ Complete |
| Phase 8b | Unified Charting (Chart.js) | ✅ Complete |
| Phase 9 | Screenshots Automation | ✅ Complete |
| Post-release | UX Improvements (v0.5-v0.8) | ✅ Complete |
