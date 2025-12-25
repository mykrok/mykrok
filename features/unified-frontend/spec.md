# Unified Web Frontend for mykrok

## Overview

A single-page web application that combines map visualization, activity browsing, and statistics into one cohesive offline-capable interface. The frontend loads all data from static files (TSV, JSON, Parquet) without requiring a backend server.

## Design Goals

1. **No backend required** - All data loaded from static files via fetch
2. **Fast initial load** - Show navigation and athlete selector immediately, lazy-load details
3. **Offline capable** - All assets bundled locally (Leaflet, hyparquet)
4. **Multi-athlete support** - Switch between athletes, cross-link from kudos/comments
5. **Strava-inspired design** - Clean, modern UI with orange accent (#fc4c02)
6. **Mobile responsive** - Works on phone, tablet, and desktop

---

## 1. Information Architecture

### View Hierarchy

```
App Shell
├── Global Header (fixed)
│   ├── Logo/Title
│   ├── Primary Navigation (Map | Sessions | Stats)
│   └── Athlete Selector (dropdown)
│
├── Main Content Area
│   ├── [Map View]
│   │   ├── Interactive map (full viewport)
│   │   ├── Layer controls (tracks, photos, athletes)
│   │   ├── Activity type legend
│   │   └── Info overlay (counts, zoom hint)
│   │
│   ├── [Sessions View]
│   │   ├── Filter bar (search, type, date range)
│   │   ├── Sessions table/list
│   │   └── Session detail panel (slide-in or modal)
│   │
│   └── [Stats View]
│       ├── Summary cards (totals)
│       ├── Monthly breakdown chart
│       └── By-type breakdown chart
│
└── [Mobile] Bottom Navigation Bar
```

### Data Flow

```
athletes.tsv
    │
    ├── Load on app start
    │   └── Populate athlete selector
    │
    └── For each athlete:
        │
        athl={username}/sessions.tsv
            │
            ├── Map View: Show markers for all sessions
            ├── Sessions View: Populate table
            └── Stats View: Calculate aggregates
            │
            └── On demand (click/zoom):
                │
                ├── ses={datetime}/tracking.parquet → Draw track polyline
                └── ses={datetime}/info.json → Photos, kudos, comments
```

---

## 2. Navigation Structure

### Desktop (width >= 768px)

**Top Navigation Bar** - Fixed at top, 56px height

```
┌────────────────────────────────────────────────────────────────────┐
│  [Logo]  MyKrok     Map   Sessions   Stats     [Athlete ▾] │
└────────────────────────────────────────────────────────────────────┘
```

- Logo: Simple icon or "SB" monogram (links to Map view)
- Primary nav tabs: Map, Sessions, Stats
- Active tab: Orange underline (#fc4c02)
- Athlete selector: Dropdown at right with avatar/initial and username

### Mobile (width < 768px)

**Compact Header** - 48px height

```
┌────────────────────────────────────────────────────────────┐
│  [Athlete ▾]          MyKrok          [Filter ☰]   │
└────────────────────────────────────────────────────────────┘
```

**Bottom Tab Bar** - Fixed at bottom, 56px height

```
┌────────────────────────────────────────────────────────────┐
│       Map           Sessions           Stats               │
│       [icon]         [icon]           [icon]               │
└────────────────────────────────────────────────────────────┘
```

### URL Structure (Hash-based routing)

Since this is a static file app served without a backend, use hash routing:

**Basic Routes**:
- `#/map` - Map view (default)
- `#/map?a=alice` - Map filtered to specific athlete
- `#/sessions` - Sessions list
- `#/sessions?a=alice` - Sessions for specific athlete
- `#/session/{athlete}/{datetime}` - Full session detail view
- `#/stats` - Statistics dashboard
- `#/stats?year=2024` - Stats for specific year

**Permalink Parameters for Sharing**:

Map view supports additional parameters to share specific views:
- `#/map?track={athlete}/{datetime}` - Focus and load track for a specific session
- `#/map?popup={athlete}/{datetime}/{photoIndex}` - Open PhotoViewer on a specific photo
- `#/map?z=14&lat=40.7&lng=-74.0` - Specific map position and zoom

Session view supports photo permalinks:
- `#/session/{athlete}/{datetime}?photo={index}` - Open PhotoViewer at specific photo

All parameters can be combined for a complete shareable state:
- `#/map?a=alice&from=2024-01-01&to=2024-12-31&track=alice/20241218T063000`

---

## 3. Athlete Selection UX

### Athlete Selector Component

**Desktop**: Dropdown in top-right of header

```
┌─────────────────────────┐
│ [A] alice_runner    ▾   │  ← Current athlete
├─────────────────────────┤
│ ○ All Athletes (3)      │  ← For map view only
├─────────────────────────┤
│ ● [A] alice_runner      │  ← Selected
│   142 sessions | 2.3k km│
│   Jan 2020 - Dec 2024   │
├─────────────────────────┤
│ ○ [B] bob_cyclist       │
│   89 sessions | 5.1k km │
│   Mar 2021 - Nov 2024   │
├─────────────────────────┤
│ ○ [C] carol_hiker       │
│   45 sessions | 320 km  │
│   Jun 2022 - Dec 2024   │
└─────────────────────────┘
```

**Mobile**: Full-screen modal on tap

### Multi-Athlete Map Mode

When "All Athletes" is selected (map view only):
- Each athlete gets a distinct color or pattern
- Legend shows athlete color mapping
- Clicking a marker shows which athlete it belongs to
- Filter checkboxes to show/hide individual athletes

### Athlete Avatar

Generate avatar from username initial with deterministic color:
```javascript
function getAvatarColor(username) {
  const hash = username.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  const colors = ['#FF5722', '#2196F3', '#4CAF50', '#9C27B0', '#FF9800'];
  return colors[hash % colors.length];
}
```

---

## 4. Layout Specifications

### 4.1 Map View

**Purpose**: Visualize activity locations, discover areas, view photos

**Layout (Desktop)**:
```
┌─────────────────────────────────────────────────────────────────────┐
│ Header                                                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│    ┌────────┐                                              ┌─────┐ │
│    │Layers  │        INTERACTIVE MAP                       │Info │ │
│    │Control │        (full viewport)                        │Count│ │
│    └────────┘                                              └─────┘ │
│                                                                     │
│                          [session markers]                          │
│                          [photo markers]                            │
│                          [track polylines]                          │
│                                                                     │
│    ┌──────────────────────────────────────────────────────────────┐│
│    │ Legend: Run | Ride | Hike | Walk | Swim | Other | Photos     ││
│    └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

**Components**:

1. **Session Markers**
   - Small circle markers colored by activity type
   - Position: center_lat/center_lng from sessions.tsv
   - Click: Load track + photos, show popup with basic info
   - Photo badge overlay if session has photos

2. **Track Polylines** (loaded on demand)
   - Colored by activity type
   - Loaded when: zoom >= 11 OR marker clicked
   - Weight: 3px, opacity: 0.7

3. **Photo Markers** (loaded on demand)
   - Pink camera icons (#E91E63)
   - Clustered when zoomed out
   - Click: Show photo popup with thumbnail

4. **Layer Controls** (top-left)
   - Checkboxes: Sessions, Tracks, Photos
   - Athlete filter (when multi-athlete)

5. **Info Panel** (top-right)
   - Total sessions count
   - Loaded tracks count
   - Photos count
   - Zoom hint when < zoom 11

6. **Legend** (bottom-right)
   - Activity type colors
   - Photo marker indicator

**Interactions**:
- Pan/zoom: Standard map behavior
- Click session marker: Load track polyline + photos, open popup
- Click photo marker: Show photo popup with image
- Hover track: Highlight with thicker line
- Zoom >= 11: Auto-load visible tracks

**States**:
- Loading: Spinner overlay "Loading sessions..."
- Empty: "No sessions found" message
- Error: "Failed to load data" with retry button

---

### 4.2 Sessions View

**Purpose**: Browse activities chronologically, search, view details

**Layout (Desktop)**:
```
┌─────────────────────────────────────────────────────────────────────┐
│ Header                                                              │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ [Search...            ]  [Type ▾]  [Date: From ▾] [To ▾]  Clear │ │
│ └─────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ │ Date      │ Type    │ Name            │ Distance│ Time   │ +    ││
│ ├───────────┼─────────┼─────────────────┼─────────┼────────┼──────┤│
│ │ 2024-12-18│ Run     │ Morning Run     │ 5.2 km  │ 28:30  │ [P]  ││
│ │ 2024-12-17│ Ride    │ Commute         │ 12.4 km │ 35:00  │      ││
│ │ 2024-12-15│ Hike    │ Weekend Hike    │ 8.1 km  │ 2:15:00│ [P]  ││
│ │ ...                                                              ││
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│ Showing 1-50 of 142 sessions                         [Load More]   │
└─────────────────────────────────────────────────────────────────────┘
```

**Layout (Mobile)**:
```
┌────────────────────────────────────┐
│ Header                             │
├────────────────────────────────────┤
│ [Search...              ] [Filter] │
├────────────────────────────────────┤
│ ┌────────────────────────────────┐ │
│ │ Morning Run              5.2 km │ │
│ │ Run | Dec 18, 2024      28:30  │ │
│ │                          [GPS] │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ Commute                  12.4 km│ │
│ │ Ride | Dec 17, 2024     35:00  │ │
│ │                                │ │
│ └────────────────────────────────┘ │
│ ...                                │
├────────────────────────────────────┤
│ Bottom Nav                         │
└────────────────────────────────────┘
```

**Filter Bar Components**:
- Search input: Filter by activity name (client-side)
- Type dropdown: All, Run, Ride, Hike, Walk, Swim, Other
- Date range: From/To date pickers
- Clear button: Reset all filters

**Table Columns** (Desktop):
- Date: Formatted date (Dec 18, 2024)
- Type: Activity type with color indicator
- Name: Activity name (truncated if long)
- Distance: X.X km
- Time: H:MM:SS or MM:SS
- Indicators: [GPS] [P] (photos) badges

**List Cards** (Mobile):
- Activity name (primary)
- Type + Date (secondary)
- Distance + Time (tertiary)
- Badges for GPS/photos

**Interactions**:
- Click row/card: Open session detail panel
- Sort by column (click header)
- Infinite scroll or "Load More" pagination
- Pull-to-refresh (mobile)

**Session Detail Panel** (slide-in from right, 400px width on desktop):
```
┌──────────────────────────────────────┐
│ [←] Morning Run                      │
│ Run | December 18, 2024 6:30 AM      │
├──────────────────────────────────────┤
│ ┌────────┐ ┌────────┐ ┌────────┐    │
│ │ 5.23   │ │ 28:30  │ │ 45     │    │
│ │   km   │ │  time  │ │  elev  │    │
│ └────────┘ └────────┘ └────────┘    │
├──────────────────────────────────────┤
│ [MAP THUMBNAIL - click to go to map] │
├──────────────────────────────────────┤
│ Photos (3)                           │
│ [img1] [img2] [img3]                 │
├──────────────────────────────────────┤
│ Comments (2)                         │
│ Alice: Great run!                    │
│ Bob: Looking strong!                 │
├──────────────────────────────────────┤
│ Kudos (5)                            │
│ Alice, Bob, Carol, +2 more           │
├──────────────────────────────────────┤
│ Details                              │
│ Avg Pace: 5:27 /km                   │
│ Avg HR: 145 bpm                      │
│ Calories: 320                        │
│ Device: Garmin Forerunner 255        │
└──────────────────────────────────────┘
```

**Data Streams** (from tracking.parquet):
- Display available data streams when present (not all sessions have all streams):
  - Heart rate (hr): Line chart or summary stats
  - Cadence (cadence): Line chart or summary stats
  - Power (watts): Line chart or summary stats (cycling)
  - Temperature (temp): Line chart or summary stats
  - Altitude (altitude): Elevation profile
- Check which columns exist in the parquet file before rendering
- Show summary stats: avg, max, min for numeric streams
- Optional: Interactive chart with distance/time on x-axis

**Cross-linking**:
- Kudos/comment athlete names: If that athlete exists locally (in athletes.tsv), render as link to their sessions
- "View on Map" button: Navigate to map view, zoom to this session

**Shared Run Indicator**:
- If session has `athletes > 1`, show "Group Activity" badge
- Cross-reference: Check if other local athletes have sessions at same datetime
- If match found, show linked badges: "Also: alice, bob"

---

### 4.3 Stats View

**Purpose**: Aggregate statistics, trends over time

**Layout (Desktop)**:
```
┌─────────────────────────────────────────────────────────────────────┐
│ Header                                                              │
├─────────────────────────────────────────────────────────────────────┤
│ ┌───────────────────────────────────────────────────────────────┐   │
│ │ Year: [2024 ▾]   Type: [All ▾]                                │   │
│ └───────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐        │
│ │    142     │ │   1,234    │ │    156     │ │   45,230   │        │
│ │ Activities │ │    km      │ │   hours    │ │   meters   │        │
│ └────────────┘ └────────────┘ └────────────┘ └────────────┘        │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Monthly Activity                                                    │
│ ┌───────────────────────────────────────────────────────────────┐   │
│ │         █                                                     │   │
│ │    █    █    █                   █                            │   │
│ │    █    █    █    █         █    █    █                       │   │
│ │ █  █    █    █    █    █    █    █    █    █    █    █        │   │
│ │ Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec               │   │
│ └───────────────────────────────────────────────────────────────┘   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ By Activity Type                                                    │
│ ┌───────────────────────────────────────────────────────────────┐   │
│ │ Run   ████████████████████████████  68 (48%)    543 km        │   │
│ │ Ride  ██████████████                 35 (25%)    891 km        │   │
│ │ Hike  ████████                       22 (15%)    176 km        │   │
│ │ Walk  ████                           12 (8%)      45 km        │   │
│ │ Other ██                              5 (4%)      12 km        │   │
│ └───────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Summary Cards**:
- Activities count
- Total distance (km)
- Total time (hours)
- Total elevation (meters)
- Optional: Calories if data available

**Monthly Chart**:
- Bar chart showing activity count or distance per month
- Toggle: Count vs Distance vs Time
- Click bar: Filter sessions view to that month

**By-Type Chart**:
- Horizontal bar chart
- Shows count, percentage, and total distance
- Color-coded by activity type
- Click bar: Filter sessions view to that type

**Filters**:
- Year selector: All years, or specific year
- Type filter: All types, or specific type
- Stats recalculate client-side on filter change

---

## 5. Mobile Responsiveness

### Breakpoints

| Breakpoint | Width | Layout Changes |
|------------|-------|----------------|
| Mobile S   | < 375px | Single column, smaller fonts |
| Mobile     | 375-767px | Single column, bottom nav |
| Tablet     | 768-1023px | Two column where useful |
| Desktop    | >= 1024px | Full layout, sidebar details |

### View-Specific Adaptations

**Map View**:
- Mobile: Full screen map, floating buttons
- Controls collapse to icons
- Legend hidden, available via button
- Info panel minimized to single line

**Sessions View**:
- Mobile: Card list instead of table
- Filter bar collapses to search + filter button
- Detail panel: Full screen modal instead of slide-in

**Stats View**:
- Mobile: Single column stack
- Summary cards: 2x2 grid
- Charts: Full width, touch-scrollable
- Monthly chart: Horizontal scroll if needed

### Touch Interactions

- Swipe left on session card: Quick actions (if any future features)
- Swipe right on detail panel: Close
- Pull down on lists: Refresh
- Long press on map: Not used (avoid conflict with map interaction)

---

## 6. Key Interactions

### 6.1 Data Loading Sequence

1. **App Initialization**
   ```
   1. Load index.html (bundled CSS/JS)
   2. Fetch athletes.tsv → populate athlete selector
   3. Fetch sessions.tsv for selected athlete
   4. Initialize view based on URL hash
   ```

2. **View Switch**
   ```
   Map View: Show markers from sessions.tsv data
   Sessions View: Populate table from sessions.tsv data
   Stats View: Calculate aggregates from sessions.tsv data
   ```

3. **Lazy Loading Triggers**
   ```
   - Map: zoom >= 11 OR click marker → load tracking.parquet
   - Map: click photo marker → already have location from sessions
   - Sessions: click row → fetch info.json for full details
   - Sessions detail: photos from info.json, display from local files
   ```

### 6.2 Filtering & Search

**Client-side filtering** (no network requests):
- All filters operate on already-loaded sessions.tsv data
- Use JavaScript array filtering
- Debounce search input (300ms)

**Filter State Persistence**:
- Store in URL hash: `#/sessions?type=Run&after=2024-01-01`
- Restore on page load
- Optional: localStorage for cross-session persistence

### 6.3 Cross-Athlete Linking

**Kudos/Comment Authors**:
```javascript
// Check if author exists in local athletes
function renderAthleteLink(athleteId, firstName, lastName) {
  const localAthlete = athletes.find(a => a.id === athleteId);
  if (localAthlete) {
    return `<a href="#/sessions?athlete=${localAthlete.username}">
              ${firstName} ${lastName}
            </a>`;
  }
  return `${firstName} ${lastName}`;
}
```

**Shared Runs**:
```javascript
// Find sessions at same datetime across athletes
function findSharedSessions(datetime) {
  return athletes
    .filter(a => a.username !== currentAthlete)
    .filter(a => a.sessions.has(datetime))
    .map(a => a.username);
}
```

### 6.4 Photo Handling

**Photo Sources** (priority order):
1. Local files: `athl={username}/ses={datetime}/photos/{timestamp}.jpg`
2. Remote URLs: From `info.json` photos array

**Photo Display**:
- Map popup: Thumbnail (600px size) with navigation controls
- Session detail: Grid of thumbnails
- Click thumbnail: Opens PhotoViewer modal
- PhotoViewer: Full-screen modal with navigation between photos

### 6.5 PhotoViewer Component

**Purpose**: Unified photo viewing experience across all views (session detail, map popups)

**Layout (Modal)**:
```
┌─────────────────────────────────────────────────────────────────────┐
│                                                        [×] [↗]      │
│                                                                     │
│                                                                     │
│    [<]              [PHOTO IMAGE]                           [>]     │
│                                                                     │
│                                                                     │
│                         3 of 10                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Components**:

1. **Modal Container**
   - Full viewport overlay with semi-transparent backdrop
   - Centered photo display
   - Click backdrop to close

2. **Navigation Buttons**
   - Previous (`<`) and Next (`>`) buttons on sides
   - Disabled state at sequence ends (no looping)
   - Arrow key support (Left/Right)

3. **Photo Counter**
   - Format: "X of Y" (e.g., "3 of 10")
   - Updates on navigation

4. **Close Button**
   - Top-right corner
   - Escape key also closes

5. **Open in New Tab**
   - Icon button to open full resolution in new tab

**Click Zones**:
- Left half of image → Previous photo
- Right half of image → Next photo
- Enables single-handed navigation on mobile

**Map Popup Navigation**:
```
┌────────────────────────────────────────┐
│           [PHOTO THUMBNAIL]            │
├────────────────────────────────────────┤
│    [<]      2 of 5           [>]       │
├────────────────────────────────────────┤
│  Activity Name                         │
│  Date | Zoom in | View session         │
└────────────────────────────────────────┘
```

- Navigation row appears below photo in popups
- Counter shows position in sequence
- Prev/Next buttons disabled at ends
- Click photo to open in PhotoViewer modal

**Keyboard Support**:
- `←` (Left Arrow): Previous photo
- `→` (Right Arrow): Next photo
- `Escape`: Close modal

**Styling**:
```css
.photo-viewer-modal {
  z-index: 10000;
  background: rgba(0, 0, 0, 0.9);
}

.photo-viewer-prev:disabled,
.photo-viewer-next:disabled {
  opacity: 0.3;
  cursor: default;
}
```

**States**:
- At first photo: Previous button disabled
- At last photo: Next button disabled
- Single photo: Both buttons disabled, no navigation row

---

## 7. Visual Design

### Color Palette

```css
:root {
  /* Primary - Strava Orange */
  --color-primary: #fc4c02;
  --color-primary-dark: #e04100;
  --color-primary-light: #ff6d33;

  /* Activity Types */
  --color-run: #FF5722;
  --color-ride: #2196F3;
  --color-hike: #4CAF50;
  --color-walk: #9C27B0;
  --color-swim: #00BCD4;
  --color-other: #607D8B;

  /* Photos */
  --color-photo: #E91E63;

  /* Neutrals */
  --color-bg: #ffffff;
  --color-bg-secondary: #f5f5f5;
  --color-text: #333333;
  --color-text-secondary: #666666;
  --color-border: #e0e0e0;

  /* States */
  --color-success: #4CAF50;
  --color-warning: #FF9800;
  --color-error: #f44336;
}
```

### Typography

```css
:root {
  --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                 'Helvetica Neue', Arial, sans-serif;

  --font-size-xs: 11px;
  --font-size-sm: 13px;
  --font-size-base: 15px;
  --font-size-lg: 18px;
  --font-size-xl: 24px;
  --font-size-xxl: 32px;

  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-bold: 600;
}
```

### Spacing Scale

```css
:root {
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-xxl: 48px;
}
```

### Component Styles

**Buttons**:
- Primary: Orange background, white text
- Secondary: White background, orange border/text
- Border radius: 4px
- Padding: 8px 16px

**Cards**:
- Background: White
- Border: 1px solid #e0e0e0
- Border radius: 8px
- Shadow: 0 2px 4px rgba(0,0,0,0.1)

**Tables**:
- Header: Orange background (#fc4c02), white text
- Rows: Alternating white/gray (#f9f9f9)
- Hover: Light orange tint (#fff5f0)

**Badges**:
- GPS: Green (#4CAF50)
- Photos: Blue (#2196F3)
- Group: Purple (#9C27B0)

---

## 8. States & Edge Cases

### Loading States

```
Initial Load:
┌─────────────────────────────────┐
│                                 │
│        [Spinner]                │
│   Loading activities...         │
│                                 │
└─────────────────────────────────┘

Lazy Load (map track):
- Show dotted line placeholder
- Replace with solid line when loaded
```

### Empty States

```
No Athletes Found:
┌─────────────────────────────────┐
│                                 │
│   No athlete data found.        │
│                                 │
│   Run 'mykrok sync'      │
│   to download activities.       │
│                                 │
└─────────────────────────────────┘

No Sessions Match Filter:
┌─────────────────────────────────┐
│                                 │
│   No sessions match your        │
│   search criteria.              │
│                                 │
│   [Clear Filters]               │
│                                 │
└─────────────────────────────────┘

No GPS Data:
- Session marked without track
- Map shows "No GPS" in popup
- Session detail shows map thumbnail placeholder
```

### Error States

```
Network Error:
┌─────────────────────────────────┐
│                                 │
│   Failed to load data.          │
│   Check that files exist.       │
│                                 │
│   [Retry]                       │
│                                 │
└─────────────────────────────────┘

Invalid Data:
- Log to console
- Show graceful degradation
- Skip invalid entries, show rest
```

---

## 9. Accessibility

### Keyboard Navigation

- Tab order: Header -> Nav -> Main content
- Arrow keys: Navigate within tables/lists
- Enter: Activate buttons, open details
- Escape: Close modals/panels (including PhotoViewer)
- Focus indicators: Visible outline on interactive elements

**PhotoViewer Shortcuts**:
- Left Arrow (←): Previous photo
- Right Arrow (→): Next photo
- Escape: Close viewer

### Screen Reader Support

- Semantic HTML: nav, main, section, article
- ARIA labels on icons and buttons
- Alt text for all images
- Table headers with scope
- Live regions for dynamic updates

### Color Contrast

- All text: Minimum 4.5:1 ratio
- Large text: Minimum 3:1 ratio
- Interactive elements: Clear focus states
- Activity type colors: Pattern/shape redundancy

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 10. Technical Implementation Notes

### File Structure

```
data/
├── index.html              # Main SPA entry point
├── assets/
│   ├── app.css            # Application styles
│   ├── app.js             # Application code (vanilla JS or bundled)
│   ├── leaflet/           # Leaflet CSS/JS (local copy)
│   └── hyparquet/         # Parquet reader (local copy)
├── athletes.tsv
└── athl={username}/
    ├── sessions.tsv
    └── ses={datetime}/
        ├── info.json
        ├── tracking.parquet
        └── photos/
```

### Dependencies

- **Leaflet.js**: Map rendering (bundled locally)
- **hyparquet**: Parquet file reading (bundled locally)
- **No build step required**: Vanilla JavaScript with ES modules

### Browser Support

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+
- Mobile Chrome/Safari

---

## 11. Future Considerations

### Potential Enhancements

1. **Gear tracking**: Show gear usage stats, link activities to equipment
2. **Year-over-year comparison**: Compare stats across years
3. **Achievement badges**: Display PRs, achievements from Strava data
4. **Export functionality**: Export filtered data as CSV
5. **Offline PWA**: Service worker for full offline capability
6. **Dark mode**: Respect system preference

### Data Model Extensions

- Add `shared_session_ids` column to sessions.tsv for cross-athlete linking
- Add `gear_name` column for display without needing gear.json lookup
- Consider pre-computing monthly stats in a stats.json file

---

## Appendix: Sessions.tsv Extended Columns

Current columns from `sessions.tsv`:
```
datetime, type, sport, name, distance_m, moving_time_s, elapsed_time_s,
elevation_gain_m, calories, avg_hr, max_hr, avg_watts, gear_id, athletes,
kudos_count, comment_count, has_gps, photos_path, photo_count,
start_lat, start_lng
```

Note: `start_lat`/`start_lng` replaced `center_lat`/`center_lng` in v0.2.0
to use GPS start coordinates for more accurate map positioning.

All columns needed for frontend features are already available.
