# Unified Web Frontend Implementation Plan

## Overview

Transform the existing lightweight map into a full single-page application with tab navigation, athlete selection, sessions browser, and statistics dashboard. All functionality runs client-side with no backend required.

## Architecture

The implementation extends `generate_lightweight_map()` in `src/strava_backup/views/map.py` to produce a more comprehensive HTML file. The key architectural decisions:

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
    <div class="logo">Strava Backup</div>
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
4. Verify stats calculations match `strava-backup view stats` output
5. Test on mobile device (or DevTools responsive mode)
6. Test with no athletes (empty state)
7. Test with single athlete (no "All Athletes" option)

---

## File Changes Summary

### Modified Files
| File | Changes |
|------|---------|
| `src/strava_backup/views/map.py` | Extend `generate_lightweight_map()` to produce full SPA |

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

- `src/strava_backup/views/map.py` - Core file to extend with SPA generation
- `src/strava_backup/views/stats.py` - Reference for stats calculation logic to port to JS
- `src/strava_backup/models/activity.py` - Data model for sessions.tsv columns
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
