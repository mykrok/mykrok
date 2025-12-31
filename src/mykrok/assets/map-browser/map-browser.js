import { parquetReadObjects } from '../hyparquet/index.js';
import { getExpansionDays } from './date-utils.js';
import { parseTSV } from './tsv-utils.js';
import {
    canGoPrev as canGoPrevUtil,
    canGoNext as canGoNextUtil,
    getPrevIndex,
    getNextIndex,
    formatPhotoCounter,
    getClickDirection
} from './photo-viewer-utils.js';

// ===== Photo Viewer Modal =====
const PhotoViewer = {
    photos: [],
    currentIndex: 0,
    modal: null,

    init() {
        // Create modal container
        this.modal = document.createElement('div');
        this.modal.className = 'photo-viewer-modal';
        this.modal.innerHTML = `
            <div class="photo-viewer-overlay"></div>
            <div class="photo-viewer-content">
                <button class="photo-viewer-close" title="Close (Esc)">&times;</button>
                <button class="photo-viewer-prev" title="Previous (←)">&#8249;</button>
                <div class="photo-viewer-image-container">
                    <img class="photo-viewer-image" src="" alt="Photo">
                </div>
                <button class="photo-viewer-next" title="Next (→)">&#8250;</button>
                <div class="photo-viewer-footer">
                    <span class="photo-viewer-counter">1 of 1</span>
                    <button class="photo-viewer-open" title="Open in new tab">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;
        this.modal.style.display = 'none';
        document.body.appendChild(this.modal);

        // Event listeners
        this.modal.querySelector('.photo-viewer-overlay').addEventListener('click', () => this.close());
        this.modal.querySelector('.photo-viewer-close').addEventListener('click', () => this.close());
        this.modal.querySelector('.photo-viewer-prev').addEventListener('click', () => this.prev());
        this.modal.querySelector('.photo-viewer-next').addEventListener('click', () => this.next());
        this.modal.querySelector('.photo-viewer-open').addEventListener('click', () => this.openInNewTab());

        // Click on image: left half = prev, right half = next
        this.modal.querySelector('.photo-viewer-image-container').addEventListener('click', (e) => {
            if (this.photos.length <= 1) return;
            const rect = e.currentTarget.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const direction = getClickDirection(clickX, rect.width);
            if (direction === 'prev') {
                this.prev();
            } else {
                this.next();
            }
        });

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (this.modal.style.display === 'none') return;
            if (e.key === 'Escape') this.close();
            else if (e.key === 'ArrowLeft') this.prev();
            else if (e.key === 'ArrowRight') this.next();
        });
    },

    // Context for URL tracking
    context: null,  // { athlete, datetime, source: 'session'|'map' }

    open(photos, startIndex = 0, context = null) {
        if (!photos || photos.length === 0) return;
        this.photos = photos;
        this.currentIndex = startIndex;
        this.context = context;
        this.updateDisplay();
        this.modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        this.updateURL();
    },

    close() {
        this.modal.style.display = 'none';
        document.body.style.overflow = '';
        this.clearURL();
        this.context = null;
    },

    prev() {
        if (!this.canGoPrev()) return;
        this.currentIndex = getPrevIndex(this.currentIndex, this.photos.length);
        this.updateDisplay();
        this.updateURL();
    },

    next() {
        if (!this.canGoNext()) return;
        this.currentIndex = getNextIndex(this.currentIndex, this.photos.length);
        this.updateDisplay();
        this.updateURL();
    },

    updateURL() {
        if (!this.context) return;
        const { athlete, datetime, source } = this.context;
        if (source === 'session') {
            // Session view: #/session/athlete/datetime?photo=index
            URLState.updateSessionPhoto(athlete, datetime, this.currentIndex);
        } else if (source === 'map') {
            // Map view: update popup parameter
            URLState.update({ popup: `${athlete}/${datetime}/${this.currentIndex}` });
        }
    },

    clearURL() {
        if (!this.context) return;
        const { athlete, datetime, source } = this.context;
        if (source === 'session') {
            // Remove photo param from session URL
            URLState.updateSessionPhoto(athlete, datetime, null);
        } else if (source === 'map') {
            // Remove popup param from map URL
            URLState.update({ popup: '' });
        }
    },

    canGoPrev() {
        return canGoPrevUtil(this.currentIndex, this.photos.length);
    },

    canGoNext() {
        return canGoNextUtil(this.currentIndex, this.photos.length);
    },

    updateDisplay() {
        const photo = this.photos[this.currentIndex];
        const img = this.modal.querySelector('.photo-viewer-image');
        const counter = this.modal.querySelector('.photo-viewer-counter');
        const prevBtn = this.modal.querySelector('.photo-viewer-prev');
        const nextBtn = this.modal.querySelector('.photo-viewer-next');

        img.src = photo.src;
        counter.textContent = formatPhotoCounter(this.currentIndex, this.photos.length);

        // Show/hide and enable/disable nav buttons
        const hasMultiple = this.photos.length > 1;
        prevBtn.style.display = hasMultiple ? 'flex' : 'none';
        nextBtn.style.display = hasMultiple ? 'flex' : 'none';
        prevBtn.disabled = !this.canGoPrev();
        nextBtn.disabled = !this.canGoNext();
    },

    openInNewTab() {
        const photo = this.photos[this.currentIndex];
        if (photo && photo.fullUrl) {
            window.open(photo.fullUrl, '_blank');
        }
    }
};

// ===== URL State Manager =====
const URLState = {
    // Encode state to URL hash with query params
    encode(state) {
        const params = new URLSearchParams();
        if (state.athlete) params.set('a', state.athlete);
        if (state.zoom) params.set('z', state.zoom);
        if (state.lat) params.set('lat', state.lat.toFixed(4));
        if (state.lng) params.set('lng', state.lng.toFixed(4));
        if (state.session) params.set('s', state.session);
        if (state.search) params.set('q', state.search);
        if (state.type) params.set('t', state.type);
        if (state.dateFrom) params.set('from', state.dateFrom);
        if (state.dateTo) params.set('to', state.dateTo);
        // Track selection on map: track=athlete/datetime
        if (state.track) params.set('track', state.track);
        // Photo popup on map: popup=athlete/datetime/photoIndex
        if (state.popup) params.set('popup', state.popup);
        // Viewport filter: vp=1 when enabled
        if (state.viewportFilter) params.set('vp', '1');
        const queryStr = params.toString();
        return '#/' + state.view + (queryStr ? '?' + queryStr : '');
    },

    // Decode state from URL hash
    decode() {
        const hash = location.hash.slice(2) || 'map';
        const [path, queryStr] = hash.split('?');
        const params = new URLSearchParams(queryStr || '');
        return {
            view: path.split('/')[0] || 'map',
            athlete: params.get('a') || '',
            zoom: params.get('z') ? parseInt(params.get('z')) : null,
            lat: params.get('lat') ? parseFloat(params.get('lat')) : null,
            lng: params.get('lng') ? parseFloat(params.get('lng')) : null,
            session: params.get('s') || '',
            search: params.get('q') || '',
            type: params.get('t') || '',
            dateFrom: params.get('from') || '',
            dateTo: params.get('to') || '',
            // Track selection on map: track=athlete/datetime
            track: params.get('track') || '',
            // Photo popup on map: popup=athlete/datetime/photoIndex
            popup: params.get('popup') || '',
            // Viewport filter: true if vp=1
            viewportFilter: params.get('vp') === '1'
        };
    },

    // Decode session URL with photo parameter: #/session/athlete/datetime?photo=index
    decodeSession(hash) {
        const parts = hash.split('/');
        if (parts.length < 3) return null;
        const athlete = parts[1];
        const datetimePart = parts[2];
        const [datetime, queryStr] = datetimePart.split('?');
        const params = new URLSearchParams(queryStr || '');
        return {
            athlete,
            datetime,
            photo: params.get('photo') ? parseInt(params.get('photo')) : null
        };
    },

    // Update session URL with photo index
    updateSessionPhoto(athlete, datetime, photoIndex) {
        const base = `#/session/${athlete}/${datetime}`;
        const newHash = photoIndex !== null ? `${base}?photo=${photoIndex}` : base;
        history.replaceState(null, '', newHash);
    },

    // Update URL without triggering navigation
    update(partialState) {
        // Don't update URL if we're on a full-screen session route
        // Session routes use a different format: #/session/athlete/datetime
        const hash = location.hash;
        if (hash.startsWith('#/session/') && hash.split('/').length >= 3) {
            return; // Preserve session permalink
        }

        const current = this.decode();
        const newState = { ...current, ...partialState };
        const newHash = this.encode(newState);
        // Use replaceState to avoid cluttering browser history
        history.replaceState(null, '', newHash);
    }
};

// ===== Shared Filter State =====
const FilterState = {
    state: {
        search: '',
        type: '',
        dateFrom: '',
        dateTo: ''
    },
    listeners: [],

    get() {
        return { ...this.state };
    },

    set(newState, skipNotify = false) {
        const changed = Object.keys(newState).some(k => this.state[k] !== newState[k]);
        if (changed) {
            this.state = { ...this.state, ...newState };
            if (!skipNotify) this.notify();
        }
    },

    clear() {
        this.set({ search: '', type: '', dateFrom: '', dateTo: '' });
    },

    onChange(callback) {
        this.listeners.push(callback);
        return () => { this.listeners = this.listeners.filter(l => l !== callback); };
    },

    notify() {
        for (const listener of this.listeners) {
            try { listener(this.state); } catch (e) { console.error('FilterState listener error:', e); }
        }
    },

    // Sync with URL
    syncToURL() {
        URLState.update({
            search: this.state.search,
            type: this.state.type,
            dateFrom: this.state.dateFrom,
            dateTo: this.state.dateTo
        });
    },

    syncFromURL() {
        const urlState = URLState.decode();
        this.set({
            search: urlState.search || '',
            type: urlState.type || '',
            dateFrom: urlState.dateFrom || '',
            dateTo: urlState.dateTo || ''
        }, true);  // Skip notify - caller will handle
    },

    hasActiveFilters() {
        return this.state.search || this.state.type || this.state.dateFrom || this.state.dateTo;
    }
};

// ===== Shared Filter Function =====
function applyFilters(sessions, filters, athlete = '') {
    return sessions.filter(s => {
        // Athlete filter (global, from header selector)
        if (athlete && s.athlete !== athlete) return false;
        // Search filter
        if (filters.search && !s.name.toLowerCase().includes(filters.search.toLowerCase())) return false;
        // Type filter
        if (filters.type && s.type !== filters.type) return false;
        // Date filters
        if (filters.dateFrom) {
            const fromDate = filters.dateFrom.replace(/-/g, '');
            if (s.datetime < fromDate) return false;
        }
        if (filters.dateTo) {
            const toDate = filters.dateTo.replace(/-/g, '');
            if (s.datetime.substring(0, 8) > toDate) return false;
        }
        return true;
    });
}

// ===== Shared FilterBar Component =====
const FilterBar = {
    containerId: null,
    types: [],

    render(containerId, options = {}) {
        this.containerId = containerId;
        const container = document.getElementById(containerId);
        if (!container) return;

        const showSearch = options.showSearch !== false;
        const showType = options.showType !== false;
        const showDates = options.showDates !== false;
        const showDatePresets = options.showDatePresets !== false;

        const state = FilterState.get();

        let html = '';
        if (showSearch) {
            html += `<input type="search" class="filter-input filter-search" placeholder="Search activities..." value="${state.search}">`;
        }
        if (showType) {
            html += '<select class="filter-select filter-type"><option value="">All Types</option></select>';
        }
        if (showDatePresets) {
            html += `<select class="filter-select filter-date-preset">
                <option value="">Date Range</option>
                <option value="thisYear">This Year</option>
                <option value="last12m">Last 12 Months</option>
                <option value="last30d">Last 30 Days</option>
                <option value="thisMonth">This Month</option>
            </select>`;
        }
        if (showDates) {
            const navDisabled = !state.dateFrom || !state.dateTo ? 'disabled' : '';
            html += '<div class="date-nav-group">';
            html += `<button type="button" class="date-nav-btn date-nav-btn--expand-prev" title="Expand range backward" aria-label="Expand date range backward" ${navDisabled}>
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 12L6 8l4-4"/><path d="M3 4v8"/></svg>
            </button>`;
            html += `<button type="button" class="date-nav-btn date-nav-btn--prev" title="Previous period" aria-label="Move date range backward" ${navDisabled}>
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 12L6 8l4-4"/></svg>
            </button>`;
            html += `<input type="date" class="filter-input filter-date filter-date-from" title="From date" value="${state.dateFrom}">`;
            html += `<input type="date" class="filter-input filter-date filter-date-to" title="To date" value="${state.dateTo}">`;
            html += `<button type="button" class="date-nav-btn date-nav-btn--next" title="Next period" aria-label="Move date range forward" ${navDisabled}>
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 12l4-4-4-4"/></svg>
            </button>`;
            html += `<button type="button" class="date-nav-btn date-nav-btn--expand-next" title="Expand range forward" aria-label="Expand date range forward" ${navDisabled}>
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 12l4-4-4-4"/><path d="M13 4v8"/></svg>
            </button>`;
            html += '</div>';
        }
        html += '<button class="filter-btn filter-clear">Clear</button>';
        html += '<span class="filter-count"></span>';

        container.innerHTML = html;
    },

    init(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        // Search input
        const searchInput = container.querySelector('.filter-search');
        if (searchInput) {
            let debounceTimer;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    FilterState.set({ search: e.target.value });
                    FilterState.syncToURL();
                }, 300);
            });
        }

        // Type filter
        const typeSelect = container.querySelector('.filter-type');
        if (typeSelect) {
            typeSelect.addEventListener('change', (e) => {
                FilterState.set({ type: e.target.value });
                FilterState.syncToURL();
            });
        }

        // Date preset
        const presetSelect = container.querySelector('.filter-date-preset');
        if (presetSelect) {
            presetSelect.addEventListener('change', (e) => {
                const today = new Date();
                let dateFrom = '', dateTo = '';
                switch (e.target.value) {
                    case 'thisYear':
                        dateFrom = `${today.getFullYear()}-01-01`;
                        dateTo = today.toISOString().split('T')[0];
                        break;
                    case 'last12m':
                        const last12m = new Date(today);
                        last12m.setMonth(last12m.getMonth() - 12);
                        dateFrom = last12m.toISOString().split('T')[0];
                        dateTo = today.toISOString().split('T')[0];
                        break;
                    case 'last30d':
                        const last30d = new Date(today);
                        last30d.setDate(last30d.getDate() - 30);
                        dateFrom = last30d.toISOString().split('T')[0];
                        dateTo = today.toISOString().split('T')[0];
                        break;
                    case 'thisMonth':
                        dateFrom = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01`;
                        dateTo = today.toISOString().split('T')[0];
                        break;
                }
                FilterState.set({ dateFrom, dateTo });
                FilterState.syncToURL();
                // Update date inputs
                const fromInput = container.querySelector('.filter-date-from');
                const toInput = container.querySelector('.filter-date-to');
                if (fromInput) fromInput.value = dateFrom;
                if (toInput) toInput.value = dateTo;
                // Update nav button states
                this.updateDateNavButtons(container);
            });
        }

        // Date from
        const dateFromInput = container.querySelector('.filter-date-from');
        if (dateFromInput) {
            dateFromInput.addEventListener('change', (e) => {
                FilterState.set({ dateFrom: e.target.value });
                FilterState.syncToURL();
                // Reset preset
                const preset = container.querySelector('.filter-date-preset');
                if (preset) preset.value = '';
                // Update nav button states
                this.updateDateNavButtons(container);
            });
        }

        // Date to
        const dateToInput = container.querySelector('.filter-date-to');
        if (dateToInput) {
            dateToInput.addEventListener('change', (e) => {
                FilterState.set({ dateTo: e.target.value });
                FilterState.syncToURL();
                // Reset preset
                const preset = container.querySelector('.filter-date-preset');
                if (preset) preset.value = '';
                // Update nav button states
                this.updateDateNavButtons(container);
            });
        }

        // Date navigation buttons
        const prevBtn = container.querySelector('.date-nav-btn--prev');
        const nextBtn = container.querySelector('.date-nav-btn--next');

        const navigateDates = (direction) => {
            const state = FilterState.get();
            if (!state.dateFrom || !state.dateTo) return;

            const fromDate = new Date(state.dateFrom);
            const toDate = new Date(state.dateTo);
            const intervalMs = toDate - fromDate;
            // If same date, use 1 day interval
            const dayMs = 24 * 60 * 60 * 1000;
            const shiftMs = intervalMs > 0 ? intervalMs : dayMs;

            if (direction === 'prev') {
                fromDate.setTime(fromDate.getTime() - shiftMs);
                toDate.setTime(toDate.getTime() - shiftMs);
            } else {
                fromDate.setTime(fromDate.getTime() + shiftMs);
                toDate.setTime(toDate.getTime() + shiftMs);
            }

            const newFrom = fromDate.toISOString().split('T')[0];
            const newTo = toDate.toISOString().split('T')[0];

            FilterState.set({ dateFrom: newFrom, dateTo: newTo });
            FilterState.syncToURL();

            // Update inputs
            if (dateFromInput) dateFromInput.value = newFrom;
            if (dateToInput) dateToInput.value = newTo;

            // Reset preset dropdown
            const preset = container.querySelector('.filter-date-preset');
            if (preset) preset.value = '';
        };

        if (prevBtn) {
            prevBtn.addEventListener('click', () => navigateDates('prev'));
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', () => navigateDates('next'));
        }

        // Date expansion buttons
        const expandPrevBtn = container.querySelector('.date-nav-btn--expand-prev');
        const expandNextBtn = container.querySelector('.date-nav-btn--expand-next');

        const expandDateRange = (direction) => {
            const state = FilterState.get();
            if (!state.dateFrom || !state.dateTo) return;

            const fromDate = new Date(state.dateFrom);
            const toDate = new Date(state.dateTo);
            const dayMs = 24 * 60 * 60 * 1000;
            const intervalMs = toDate - fromDate;
            const intervalDays = Math.round(intervalMs / dayMs);

            // Use imported utility function for expansion logic
            const expandDays = getExpansionDays(intervalDays);

            if (direction === 'prev') {
                fromDate.setTime(fromDate.getTime() - expandDays * dayMs);
            } else {
                toDate.setTime(toDate.getTime() + expandDays * dayMs);
            }

            const newFrom = fromDate.toISOString().split('T')[0];
            const newTo = toDate.toISOString().split('T')[0];

            FilterState.set({ dateFrom: newFrom, dateTo: newTo });
            FilterState.syncToURL();

            // Update inputs
            if (dateFromInput) dateFromInput.value = newFrom;
            if (dateToInput) dateToInput.value = newTo;

            // Reset preset dropdown
            const preset = container.querySelector('.filter-date-preset');
            if (preset) preset.value = '';
        };

        if (expandPrevBtn) {
            expandPrevBtn.addEventListener('click', () => expandDateRange('prev'));
        }
        if (expandNextBtn) {
            expandNextBtn.addEventListener('click', () => expandDateRange('next'));
        }

        // Clear button
        const clearBtn = container.querySelector('.filter-clear');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                FilterState.clear();
                FilterState.syncToURL();
                this.syncFromState(containerId);
            });
        }
    },

    populateTypes(containerId, sessions) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const typeSelect = container.querySelector('.filter-type');
        if (!typeSelect) return;

        const types = [...new Set(sessions.map(s => s.type).filter(Boolean))].sort();
        const currentValue = typeSelect.value;
        typeSelect.innerHTML = '<option value="">All Types</option>';
        for (const type of types) {
            const option = document.createElement('option');
            option.value = type;
            option.textContent = type;
            typeSelect.appendChild(option);
        }
        typeSelect.value = currentValue;
    },

    syncFromState(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const state = FilterState.get();

        const searchInput = container.querySelector('.filter-search');
        if (searchInput) searchInput.value = state.search;

        const typeSelect = container.querySelector('.filter-type');
        if (typeSelect) typeSelect.value = state.type;

        const dateFromInput = container.querySelector('.filter-date-from');
        if (dateFromInput) dateFromInput.value = state.dateFrom;

        const dateToInput = container.querySelector('.filter-date-to');
        if (dateToInput) dateToInput.value = state.dateTo;

        // Update nav button states
        this.updateDateNavButtons(container);
    },

    updateDateNavButtons(container) {
        const state = FilterState.get();
        const hasBothDates = state.dateFrom && state.dateTo;
        const prevBtn = container.querySelector('.date-nav-btn--prev');
        const nextBtn = container.querySelector('.date-nav-btn--next');
        const expandPrevBtn = container.querySelector('.date-nav-btn--expand-prev');
        const expandNextBtn = container.querySelector('.date-nav-btn--expand-next');
        if (prevBtn) prevBtn.disabled = !hasBothDates;
        if (nextBtn) nextBtn.disabled = !hasBothDates;
        // Expand buttons should be active only when nav buttons are active
        if (expandPrevBtn) expandPrevBtn.disabled = !hasBothDates;
        if (expandNextBtn) expandNextBtn.disabled = !hasBothDates;
    },

    updateCount(containerId, filteredCount, totalCount) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const countEl = container.querySelector('.filter-count');
        if (countEl) {
            if (FilterState.hasActiveFilters()) {
                countEl.textContent = `${filteredCount} of ${totalCount}`;
                countEl.style.display = 'inline';
            } else {
                countEl.textContent = '';
                countEl.style.display = 'none';
            }
        }
    }
};

// ===== Session List Panel Component =====
const SessionListPanel = {
    containerId: null,
    sessions: [],
    onSessionClick: null,
    displayLimit: 50,

    render(containerId, options = {}) {
        this.containerId = containerId;
        this.onSessionClick = options.onSessionClick || null;
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = `
            <div class="session-list-header">
                <span class="session-list-title">Sessions</span>
                <span class="session-list-count">0</span>
                <button class="session-list-toggle" title="Toggle panel">▼</button>
            </div>
            <div class="session-list-content">
                <div class="session-list-items"></div>
                <button class="session-list-more" style="display: none;">Load more...</button>
            </div>
        `;

        // Toggle button
        const toggle = container.querySelector('.session-list-toggle');
        toggle.addEventListener('click', () => {
            container.classList.toggle('collapsed');
            toggle.textContent = container.classList.contains('collapsed') ? '▲' : '▼';
        });

        // Load more button
        const moreBtn = container.querySelector('.session-list-more');
        moreBtn.addEventListener('click', () => {
            this.displayLimit += 50;
            this.updateList();
        });
    },

    setSessions(sessions) {
        this.sessions = sessions;
        this.displayLimit = 50;
        this.updateList();
    },

    updateList() {
        const container = document.getElementById(this.containerId);
        if (!container) return;

        const countEl = container.querySelector('.session-list-count');
        if (countEl) countEl.textContent = this.sessions.length;

        const itemsEl = container.querySelector('.session-list-items');
        if (!itemsEl) return;

        const toShow = this.sessions.slice(0, this.displayLimit);
        itemsEl.innerHTML = toShow.map(s => {
            const dateStr = s.datetime ? `${s.datetime.substring(0,4)}-${s.datetime.substring(4,6)}-${s.datetime.substring(6,8)}` : '';
            const distance = s.distance_m > 0 ? `${(parseFloat(s.distance_m) / 1000).toFixed(1)} km` : '';
            return `
                <div class="session-list-item" data-athlete="${s.athlete}" data-datetime="${s.datetime}">
                    <div class="session-list-item-header">
                        <span class="session-list-item-date">${dateStr}</span>
                        <span class="session-list-item-type">${s.type || ''}</span>
                    </div>
                    <div class="session-list-item-name">${s.name || 'Untitled'}</div>
                    <div class="session-list-item-stats">${distance}</div>
                </div>
            `;
        }).join('');

        // Show/hide load more button
        const moreBtn = container.querySelector('.session-list-more');
        if (moreBtn) {
            moreBtn.style.display = this.sessions.length > this.displayLimit ? 'block' : 'none';
        }

        // Add click handlers
        itemsEl.querySelectorAll('.session-list-item').forEach(item => {
            item.addEventListener('click', () => {
                const athlete = item.dataset.athlete;
                const datetime = item.dataset.datetime;
                if (this.onSessionClick) {
                    this.onSessionClick(athlete, datetime);
                } else {
                    location.hash = `#/session/${athlete}/${datetime}`;
                }
            });
        });
    }
};

// ===== Router =====
const Router = {
    views: ['map', 'sessions', 'stats', 'session'],
    currentView: 'map',
    initialState: null,

    init() {
        // Decode initial state from URL
        this.initialState = URLState.decode();

        // Handle hash changes
        window.addEventListener('hashchange', () => this.handleRoute());

        // Handle initial route
        this.handleRoute();

        // Set up tab click handlers
        document.querySelectorAll('[data-view]').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const view = e.currentTarget.dataset.view;
                this.navigate(view);
            });
        });
    },

    handleRoute() {
        const hash = location.hash.slice(2) || 'map';
        const parts = hash.split('/');
        const view = parts[0].split('?')[0];

        // Handle full-screen session route: #/session/athlete/datetime?photo=index
        if (view === 'session' && parts.length >= 3) {
            const athlete = parts[1];
            const datetimePart = parts[2];
            const [datetime, queryStr] = datetimePart.split('?');
            const params = new URLSearchParams(queryStr || '');
            const photoIndex = params.get('photo') ? parseInt(params.get('photo')) : null;
            this.showView('session');
            FullSessionView.show(athlete, datetime, photoIndex);
            return;
        }

        if (this.views.includes(view) && view !== 'session') {
            const state = URLState.decode();
            this.showView(view);
            // Apply state after view switch
            this.applyState(state);
        } else if (!this.views.includes(view)) {
            this.navigate('map');
        }
    },

    applyState(state) {
        // Apply athlete filter if specified
        if (state.athlete) {
            const selector = document.getElementById('athlete-selector');
            if (selector) {
                selector.value = state.athlete;
                // Don't dispatch change event - we'll handle filtering below
            }
        }

        // Apply map position if on map view
        if (state.view === 'map' && state.zoom && state.lat && state.lng) {
            if (MapView.map) {
                MapView.map.setView([state.lat, state.lng], state.zoom);
            }
        }

        // Sync shared FilterState from URL (applies to all views)
        FilterState.syncFromURL();

        // Sync all filter bars from shared state
        FilterBar.syncFromState('map-filter-bar');
        FilterBar.syncFromState('sessions-filter-bar');
        FilterBar.syncFromState('stats-filter-bar');

        // Trigger re-render for current view
        if (state.view === 'map') {
            MapView.applyFiltersAndUpdateUI();
        } else if (state.view === 'sessions') {
            SessionsView.applyFiltersAndRender();
        } else if (state.view === 'stats') {
            StatsView.calculate();
        }

        // Open session detail if specified
        if (state.session && state.athlete && state.view === 'sessions') {
            setTimeout(() => {
                SessionsView.showDetail(state.athlete, state.session);
            }, 500);
        }

        // Restore viewport filter state on map view
        if (state.view === 'map' && state.viewportFilter !== undefined) {
            MapView.viewportFilterEnabled = state.viewportFilter;
            // Update button state if control exists
            if (MapView.viewportFilterControl) {
                const btn = MapView.viewportFilterControl.getContainer().querySelector('button');
                if (btn) {
                    btn.classList.toggle('active', state.viewportFilter);
                    btn.setAttribute('aria-checked', state.viewportFilter);
                }
            }
        }

        // Restore track selection on map view
        if (state.track && state.view === 'map') {
            const [trackAthlete, trackDatetime] = state.track.split('/');
            if (trackAthlete && trackDatetime) {
                // Store pending restore and start retry loop
                this.pendingTrackRestore = { athlete: trackAthlete, datetime: trackDatetime };
                this.restoreTrackFromURL(trackAthlete, trackDatetime);
            }
        }

        // Restore photo popup on map view
        if (state.popup && state.view === 'map') {
            const popupParts = state.popup.split('/');
            if (popupParts.length >= 3) {
                const [popupAthlete, popupDatetime, popupPhotoIndex] = popupParts;
                // Store pending restore and start retry loop
                this.pendingPopupRestore = { athlete: popupAthlete, datetime: popupDatetime, photoIndex: parseInt(popupPhotoIndex) };
                this.restorePhotoPopupFromURL(popupAthlete, popupDatetime, parseInt(popupPhotoIndex));
            }
        }
    },

    // Pending track/popup to restore after data loads
    pendingTrackRestore: null,
    pendingPopupRestore: null,

    async restoreTrackFromURL(athlete, datetime, retryCount = 0) {
        // Find the marker for this session
        const markerData = MapView.allMarkers.find(
            m => m.athlete === athlete && m.session === datetime
        );
        if (markerData) {
            // Load track and photos - await to ensure track is loaded before zooming
            await MapView.loadTrack(athlete, datetime, markerData.color);
            if (markerData.hasPhotos) {
                MapView.loadPhotos(athlete, datetime, markerData.sessionName);
            }
            MapView.focusSessionInList(athlete, datetime);
            // Zoom to the track bounds if available, otherwise marker
            const trackKey = `${athlete}/${datetime}`;
            const polyline = MapView.tracksBySession[trackKey];
            if (polyline) {
                MapView.map.fitBounds(polyline.getBounds(), { padding: [50, 50], maxZoom: 14 });
            } else {
                MapView.map.setView(markerData.marker.getLatLng(), 14);
            }
            this.pendingTrackRestore = null;
        } else if (retryCount < 10) {
            // Data might not be loaded yet, retry
            console.log(`Track restore: waiting for data (attempt ${retryCount + 1}/10)...`);
            setTimeout(() => this.restoreTrackFromURL(athlete, datetime, retryCount + 1), 500);
        } else {
            console.warn('Could not find session for track restore:', athlete, datetime);
            this.pendingTrackRestore = null;
        }
    },

    restorePhotoPopupFromURL(athlete, datetime, photoIndex, retryCount = 0) {
        const sessionKey = `${athlete}/${datetime}`;
        const photos = MapView.photosBySession[sessionKey];
        if (photos && photos.length > photoIndex) {
            // Open PhotoViewer with the specified photo
            MapView.openPhotoViewer(sessionKey, photoIndex);
            this.pendingPopupRestore = null;
        } else if (retryCount < 15) {
            // Photos might not be loaded yet, retry
            console.log(`Photo restore: waiting for photos (attempt ${retryCount + 1}/15)...`);
            setTimeout(() => this.restorePhotoPopupFromURL(athlete, datetime, photoIndex, retryCount + 1), 500);
        } else {
            console.warn('Could not find photos for popup restore:', sessionKey, photoIndex);
            this.pendingPopupRestore = null;
        }
    },

    navigate(view) {
        // Preserve athlete and filter state when navigating between views
        const currentAthlete = document.getElementById('athlete-selector')?.value || '';
        const filters = FilterState.get();

        // Build new hash with preserved filter state
        const params = new URLSearchParams();
        if (currentAthlete) params.set('a', currentAthlete);
        if (filters.search) params.set('q', filters.search);
        if (filters.type) params.set('t', filters.type);
        if (filters.dateFrom) params.set('from', filters.dateFrom);
        if (filters.dateTo) params.set('to', filters.dateTo);
        const queryStr = params.toString();
        const newHash = '#/' + view + (queryStr ? '?' + queryStr : '');

        // Set location.hash directly to trigger hashchange event
        // Don't use URLState.update() as it uses replaceState which doesn't trigger hashchange
        location.hash = newHash;
    },

    showView(view) {
        this.currentView = view;

        // Update view visibility
        document.querySelectorAll('.view').forEach(v => {
            v.classList.remove('active');
        });
        const viewEl = document.getElementById('view-' + view);
        if (viewEl) {
            viewEl.classList.add('active');
        }

        // Update desktop nav tabs
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.view === view);
        });

        // Update mobile nav tabs
        document.querySelectorAll('.mobile-nav-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.view === view);
        });

        // Trigger resize for map when switching to map view
        if (view === 'map' && window.mapInstance) {
            setTimeout(() => window.mapInstance.invalidateSize(), 100);
        }
    }
};

// ===== Map Module =====
const MapView = {
    map: null,
    typeColors: {
        'Run': '#FF5722',
        'Ride': '#2196F3',
        'Hike': '#4CAF50',
        'Walk': '#9C27B0',
        'Swim': '#00BCD4',
        'Other': '#607D8B'
    },
    athleteColors: {},
    bounds: null,
    sessionsLayer: null,
    tracksLayer: null,
    photosLayer: null,
    loadedTracks: new Set(),
    loadingTracks: new Set(),
    loadedPhotos: new Set(),
    tracksBySession: {},  // Map of "athlete/session" -> polyline layer
    photosBySession: {},  // Map of "athlete/session" -> array of photo markers
    allMarkers: [],
    allSessions: [],
    filteredSessions: [],  // Sessions after applying filters
    sessionsByAthlete: {},
    athleteStats: {},
    currentAthlete: '',
    totalSessions: 0,
    loadedTrackCount: 0,
    totalPhotos: 0,
    infoControl: null,
    sessionListExpanded: false,
    sessionListHeight: 300,  // Default height, updated when user resizes
    AUTO_LOAD_ZOOM: 11,
    restoringFromURL: false,
    selectedTrackKey: null,  // Currently selected track key for bold styling
    viewportFilterEnabled: false,  // Filter activities list to current map viewport
    viewportFilterControl: null,  // Reference to the control for updating button state

    // Color palette for athletes
    ATHLETE_PALETTE: ['#2196F3', '#4CAF50', '#9C27B0', '#FF9800', '#00BCD4', '#E91E63', '#795548', '#607D8B'],

    getAthleteColor(username) {
        if (!this.athleteColors[username]) {
            const idx = Object.keys(this.athleteColors).length % this.ATHLETE_PALETTE.length;
            this.athleteColors[username] = this.ATHLETE_PALETTE[idx];
        }
        return this.athleteColors[username];
    },

    init() {
        // Check if we should restore map position from URL
        const urlState = Router.initialState;
        let initialLat = 20, initialLng = 0, initialZoom = 3;
        if (urlState && urlState.zoom && urlState.lat && urlState.lng) {
            initialLat = urlState.lat;
            initialLng = urlState.lng;
            initialZoom = urlState.zoom;
            this.restoringFromURL = true;
        }

        // Initialize map with URL position or world view default
        this.map = L.map('map', { preferCanvas: true }).setView([initialLat, initialLng], initialZoom);
        window.mapInstance = this.map;

        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            // Reduce tile requests to avoid rate limiting
            keepBuffer: 4,           // Keep more tiles cached around viewport
            updateWhenZooming: false, // Don't fetch during zoom animation
            updateWhenIdle: true      // Only fetch when map stops moving
        }).addTo(this.map);

        this.bounds = L.latLngBounds();
        this.sessionsLayer = L.layerGroup().addTo(this.map);
        this.tracksLayer = L.layerGroup().addTo(this.map);
        this.photosLayer = L.layerGroup().addTo(this.map);
        this.heatmapLayer = null;  // Created lazily when needed
        this.heatmapPoints = [];   // Collected from track data
        this.displayMode = 'tracks';  // 'tracks' or 'heatmap'

        // Set up legend
        this.setupLegend();

        // Set up custom layers control
        this.setupLayersControl();

        // Set up zoom-to-fit control
        const fitBoundsControl = L.control({ position: 'topright' });
        const self = this;
        fitBoundsControl.onAdd = function() {
            const div = L.DomUtil.create('div', 'leaflet-control-fitbounds leaflet-bar');
            div.innerHTML = `
                <button type="button" title="Fit all activities" aria-label="Zoom map to show all filtered activities">
                    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M2 5V2h3M11 2h3v3M14 11v3h-3M5 14H2v-3"/>
                        <path d="M5 5h6v6H5z"/>
                    </svg>
                </button>
            `;
            L.DomEvent.disableClickPropagation(div);
            div.querySelector('button').addEventListener('click', () => {
                self.fitToVisibleMarkers();
            });
            return div;
        };
        fitBoundsControl.addTo(this.map);

        // Viewport filter control - filter activities list to current map view
        const viewportFilterControl = L.control({ position: 'topright' });
        viewportFilterControl.onAdd = function() {
            const div = L.DomUtil.create('div', 'leaflet-control-viewport leaflet-bar');
            const isActive = self.viewportFilterEnabled;
            div.innerHTML = `
                <button type="button"
                    role="switch"
                    aria-checked="${isActive}"
                    aria-label="Filter activities list to current map view"
                    title="Filter to map view"
                    class="${isActive ? 'active' : ''}">
                    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M2 5V2h3M11 2h3v3M14 11v3h-3M5 14H2v-3"/>
                        <circle cx="8" cy="8" r="1.5" fill="currentColor"/>
                    </svg>
                </button>
            `;
            L.DomEvent.disableClickPropagation(div);
            const btn = div.querySelector('button');
            btn.addEventListener('click', () => {
                self.viewportFilterEnabled = !self.viewportFilterEnabled;
                btn.classList.toggle('active', self.viewportFilterEnabled);
                btn.setAttribute('aria-checked', self.viewportFilterEnabled);
                // Update URL state
                URLState.update({ viewportFilter: self.viewportFilterEnabled });
                // Re-apply filters to update the activities list
                self.applyFiltersAndUpdateUI();
            });
            return div;
        };
        this.viewportFilterControl = viewportFilterControl;
        viewportFilterControl.addTo(this.map);

        // Set up auto-loading on zoom/pan
        this.map.on('moveend', () => this.loadVisibleTracks());
        this.map.on('zoomend', () => {
            this.loadVisibleTracks();
            this.updateInfo();
        });

        // Update URL when map position changes (debounced)
        let urlUpdateTimeout = null;
        this.map.on('moveend', () => {
            clearTimeout(urlUpdateTimeout);
            urlUpdateTimeout = setTimeout(() => {
                const center = this.map.getCenter();
                const zoom = this.map.getZoom();
                URLState.update({ zoom, lat: center.lat, lng: center.lng });
            }, 500);
        });

        // Update activities list when viewport filter is enabled (debounced)
        let viewportFilterTimeout = null;
        this.map.on('moveend', () => {
            if (this.viewportFilterEnabled) {
                clearTimeout(viewportFilterTimeout);
                viewportFilterTimeout = setTimeout(() => {
                    this.applyFiltersAndUpdateUI();
                }, 150);
            }
        });

        // Set up athlete selector
        document.getElementById('athlete-selector').addEventListener('change', (e) => {
            this.filterByAthlete(e.target.value);
            URLState.update({ athlete: e.target.value });
            this.applyFiltersAndUpdateUI();
        });

        // Initialize filter bar for map
        FilterBar.render('map-filter-bar', {
            showSearch: true,
            showType: true,
            showDatePresets: true,
            showDates: true
        });
        FilterBar.init('map-filter-bar');

        // Subscribe to filter changes
        FilterState.onChange(() => this.applyFiltersAndUpdateUI());

        // Start loading sessions
        this.loadSessions();
    },

    // Apply filters and update UI (markers, info panel)
    applyFiltersAndUpdateUI() {
        if (!this.allSessions.length) return;

        const athlete = this.currentAthlete;
        const filters = FilterState.get();
        let filtered = applyFilters(this.allSessions, filters, athlete);

        // Store count before viewport filter for "X in view of Y" display
        const filteredCountBeforeViewport = filtered.length;

        // Apply viewport filter if enabled
        if (this.viewportFilterEnabled && this.map) {
            const bounds = this.map.getBounds();
            filtered = filtered.filter(s => {
                const lat = parseFloat(s.start_lat);
                const lng = parseFloat(s.start_lng);
                return !isNaN(lat) && !isNaN(lng) && bounds.contains([lat, lng]);
            });
        }

        // Store viewport filter stats for display
        this.viewportFilteredCount = filtered.length;
        this.preViewportFilteredCount = filteredCountBeforeViewport;

        // Store filtered sessions sorted by date desc
        this.filteredSessions = [...filtered].sort((a, b) => (b.datetime || '').localeCompare(a.datetime || ''));

        // Build a set of visible session keys for quick lookup
        const visibleKeys = new Set(filtered.map(s => `${s.athlete}/${s.datetime}`));

        // Update marker visibility by adding/removing from layer
        // This is the proper Leaflet way to show/hide markers
        for (const data of this.allMarkers) {
            const key = `${data.athlete}/${data.session}`;
            const visible = visibleKeys.has(key);
            data.visible = visible;

            if (visible) {
                if (!this.sessionsLayer.hasLayer(data.marker)) {
                    data.marker.addTo(this.sessionsLayer);
                }
            } else {
                this.sessionsLayer.removeLayer(data.marker);
            }
        }

        // Update track visibility - show/hide loaded tracks based on filter
        for (const [sessionKey, polyline] of Object.entries(this.tracksBySession)) {
            if (visibleKeys.has(sessionKey)) {
                if (!this.tracksLayer.hasLayer(polyline)) {
                    polyline.addTo(this.tracksLayer);
                }
            } else {
                this.tracksLayer.removeLayer(polyline);
            }
        }

        // Update photo visibility - show/hide loaded photos based on filter
        // Note: photosBySession stores { marker, index } objects, not direct markers
        for (const [sessionKey, entries] of Object.entries(this.photosBySession)) {
            const visible = visibleKeys.has(sessionKey);
            for (const entry of entries) {
                if (visible) {
                    if (!this.photosLayer.hasLayer(entry.marker)) {
                        entry.marker.addTo(this.photosLayer);
                    }
                } else {
                    this.photosLayer.removeLayer(entry.marker);
                }
            }
        }

        // Update info panel (which now includes session count and list)
        FilterBar.updateCount('map-filter-bar', filtered.length, this.allSessions.length);
        this.updateInfo();

        // Update legend to reflect active filter
        this.updateLegendContent();
    },

    filterByAthlete(username) {
        this.currentAthlete = username;
        // Apply filters (includes athlete filter) and update markers
        this.applyFiltersAndUpdateUI();

        // Recalculate bounds for visible markers and fit
        this.fitToVisibleMarkers();
    },

    fitToVisibleMarkers() {
        this.bounds = L.latLngBounds();
        for (const data of this.allMarkers) {
            if (data.visible) {
                this.bounds.extend(data.marker.getLatLng());
            }
        }
        if (this.bounds.isValid()) {
            // Use flyToBounds for smooth animation
            this.map.flyToBounds(this.bounds, { padding: [20, 20], duration: 0.8 });
        }
    },

    zoomToSession(athlete, session) {
        const markerData = this.allMarkers.find(m => m.athlete === athlete && m.session === session);
        if (markerData && markerData.marker) {
            // Close any open popup before zooming to new session
            this.map.closePopup();

            // Get the track bounds if available, otherwise use marker location
            const sessionKey = `${athlete}/${session}`;
            const track = this.tracksBySession[sessionKey];

            // Reset previous selected track to normal weight
            if (this.selectedTrackKey && this.selectedTrackKey !== sessionKey) {
                const prevTrack = this.tracksBySession[this.selectedTrackKey];
                if (prevTrack) {
                    prevTrack.setStyle({ weight: 3 });
                }
            }

            // Bold the new selected track
            if (track) {
                track.setStyle({ weight: 6 });
                this.selectedTrackKey = sessionKey;
                // Smooth animated zoom to track bounds
                this.map.flyToBounds(track.getBounds(), { padding: [50, 50], maxZoom: 14, duration: 0.8 });
            } else {
                // Smooth animated zoom to marker
                this.map.flyTo(markerData.marker.getLatLng(), 13, { duration: 0.8 });
                // Load the track for better view (will be bolded when loaded)
                this.loadTrack(athlete, session, markerData.color);
                this.selectedTrackKey = sessionKey;
            }

            // Update URL with selected track, clear stale popup
            URLState.update({
                track: sessionKey,
                popup: ''  // Clear popup when zooming to different session
            });
        }
    },

    filterByDate(dateStr) {
        // Filter activities to a specific date (YYYY-MM-DD format)
        if (dateStr) {
            FilterState.set({ dateFrom: dateStr, dateTo: dateStr });
            FilterState.syncToURL();
            // Update filter bar inputs so date navigation works
            FilterBar.syncFromState('map-filter-bar');
        }
    },

    focusSessionInList(athlete, session) {
        // Ensure the list is expanded
        if (!this.sessionListExpanded) {
            this.sessionListExpanded = true;
            this.updateInfo();
        }

        // Find the session's position in filtered list
        const sessionIndex = this.filteredSessions.findIndex(
            s => s.athlete === athlete && s.datetime === session
        );

        // If session is beyond current visible limit, expand to show it
        if (sessionIndex >= 0 && sessionIndex >= (this.maxVisibleSessions || 50)) {
            this.maxVisibleSessions = sessionIndex + 10;  // Show some extra
            this.updateInfo();
        }

        // Now find and focus the item (use setTimeout to wait for DOM update)
        setTimeout(() => {
            const list = document.querySelector('.info-session-list');
            if (!list) return;

            const item = list.querySelector(`.info-session-item[data-athlete="${athlete}"][data-datetime="${session}"]`);
            if (!item) return;

            // Remove highlight from any previously highlighted item
            list.querySelectorAll('.info-session-item.focused').forEach(el => {
                el.classList.remove('focused');
            });

            // Add highlight to this item
            item.classList.add('focused');

            // Scroll the item into view
            item.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 50);
    },

    populateAthleteSelector() {
        const selector = document.getElementById('athlete-selector');
        // Clear existing options except "All Athletes"
        while (selector.options.length > 1) {
            selector.remove(1);
        }

        // Add options with stats
        const athletes = Object.keys(this.athleteStats).sort();
        for (const username of athletes) {
            const stats = this.athleteStats[username];
            const distanceKm = (stats.distance / 1000).toFixed(0);
            const option = document.createElement('option');
            option.value = username;
            option.textContent = `${username} (${stats.sessions} sessions, ${distanceKm} km)`;
            option.style.color = this.athleteColors[username] || '#333';
            selector.appendChild(option);
        }

        // Update "All Athletes" option with total
        const totalSessions = Object.values(this.athleteStats).reduce((sum, s) => sum + s.sessions, 0);
        const totalDistance = Object.values(this.athleteStats).reduce((sum, s) => sum + s.distance, 0);
        selector.options[0].textContent = `All Athletes (${totalSessions} sessions, ${(totalDistance / 1000).toFixed(0)} km)`;
    },

    async loadTrack(athlete, session, color) {
        const trackKey = `${athlete}/${session}`;
        if (this.loadedTracks.has(trackKey) || this.loadingTracks.has(trackKey)) return;
        this.loadingTracks.add(trackKey);

        try {
            const url = `athl=${athlete}/ses=${session}/tracking.parquet`;
            const response = await fetch(url);
            if (!response.ok) {
                this.loadingTracks.delete(trackKey);
                return;
            }

            const arrayBuffer = await response.arrayBuffer();
            const rows = await parquetReadObjects({
                file: arrayBuffer,
                columns: ['lat', 'lng']
            });

            if (rows && rows.length > 0) {
                const coords = [];
                for (const row of rows) {
                    if (row.lat != null && row.lng != null) {
                        coords.push([row.lat, row.lng]);
                    }
                }
                if (coords.length > 0) {
                    // Store reference for filtering
                    const sessionKey = `${athlete}/${session}`;

                    // Use bold weight if this is the selected track
                    const weight = this.selectedTrackKey === sessionKey ? 6 : 3;

                    const polyline = L.polyline(coords, {
                        color: color,
                        weight: weight,
                        opacity: 0.7
                    });

                    // Only add to layer if session passes current filter
                    const markerData = this.allMarkers.find(m => m.athlete === athlete && m.session === session);
                    if (!markerData || markerData.visible !== false) {
                        polyline.addTo(this.tracksLayer);
                    }

                    this.tracksBySession[sessionKey] = polyline;

                    // Add points to heatmap data
                    this.addPointsToHeatmap(coords);

                    this.loadedTracks.add(trackKey);
                    this.loadedTrackCount++;
                    this.updateInfo();
                }
            }
        } catch (e) {
            console.warn(`Failed to load track ${trackKey}:`, e);
        } finally {
            this.loadingTracks.delete(trackKey);
        }
    },

    sessionPhotoData: {},  // Store photo arrays for PhotoViewer: sessionKey -> [{src, fullUrl}, ...]

    async loadPhotos(athlete, session, sessionName) {
        const photoKey = `${athlete}/${session}`;
        if (this.loadedPhotos.has(photoKey)) return;
        this.loadedPhotos.add(photoKey);

        // Find and update the session marker to remove photo badge
        const markerData = this.allMarkers.find(m => m.athlete === athlete && m.session === session);
        if (markerData && markerData.hasPhotos) {
            const newMarker = L.circleMarker(markerData.marker.getLatLng(), {
                radius: 6,
                fillColor: markerData.color,
                color: 'white',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8,
                className: 'session-marker'
            });
            newMarker.bindPopup(markerData.marker.getPopup());
            newMarker.on('click', () => {
                this.loadTrack(athlete, session, markerData.color);
                this.loadPhotos(athlete, session, sessionName);
            });
            this.sessionsLayer.removeLayer(markerData.marker);
            newMarker.addTo(this.sessionsLayer);
            markerData.marker = newMarker;
        }

        try {
            const url = `athl=${athlete}/ses=${session}/info.json`;
            const response = await fetch(url);
            if (!response.ok) return;

            const info = await response.json();
            const photos = info.photos || [];

            // Initialize array for this session's photos
            const sessionKey = `${athlete}/${session}`;
            this.photosBySession[sessionKey] = [];
            this.sessionPhotoData[sessionKey] = [];

            // First pass: build photo data array for PhotoViewer
            const photoDataList = [];
            for (const photo of photos) {
                const urls = photo.urls || {};
                const previewUrl = urls['600'] || urls['256'] || urls['1024'] || urls['2048'] || Object.values(urls)[0] || '';
                const fullUrl = urls['2048'] || urls['1024'] || urls['600'] || Object.values(urls)[0] || '';

                const createdAt = photo.created_at || '';
                let localPath = '';
                if (createdAt) {
                    const dt = createdAt.replace(/[-:]/g, '').replace(/\+.*$/, '').substring(0, 15);
                    localPath = `athl=${athlete}/ses=${session}/photos/${dt}.jpg`;
                }

                const locationRaw = photo.location;
                const hasLocation = locationRaw && locationRaw[0] && locationRaw[0][1];
                const [lat, lng] = hasLocation ? locationRaw[0][1] : [null, null];

                photoDataList.push({
                    src: localPath || previewUrl,
                    fullUrl: localPath || fullUrl,
                    lat,
                    lng,
                    hasLocation: lat != null && lng != null
                });
            }

            this.sessionPhotoData[sessionKey] = photoDataList;
            const totalPhotos = photoDataList.length;

            // Second pass: create markers for photos with location
            let photoIndex = 0;
            for (const photoData of photoDataList) {
                const currentIndex = photoIndex++;
                if (!photoData.hasLocation) continue;

                const photoIcon = L.divIcon({
                    html: '<div class="photo-icon" style="width:24px;height:24px;display:flex;align-items:center;justify-content:center;">' +
                          '<svg width="14" height="14" viewBox="0 0 24 24" fill="white"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>' +
                          '</div>',
                    className: '',
                    iconSize: [28, 28],
                    iconAnchor: [14, 14]
                });

                const marker = L.marker([photoData.lat, photoData.lng], { icon: photoIcon });
                const photoDateForFilter = `${session.substring(0, 4)}-${session.substring(4, 6)}-${session.substring(6, 8)}`;

                // Build navigation buttons
                const navPrev = currentIndex > 0
                    ? `<button class="photo-nav-btn" onclick="MapView.showPhotoAtIndex('${sessionKey}', ${currentIndex - 1})" title="Previous photo">&#8249;</button>`
                    : '<button class="photo-nav-btn" disabled>&#8249;</button>';
                const navNext = currentIndex < totalPhotos - 1
                    ? `<button class="photo-nav-btn" onclick="MapView.showPhotoAtIndex('${sessionKey}', ${currentIndex + 1})" title="Next photo">&#8250;</button>`
                    : '<button class="photo-nav-btn" disabled>&#8250;</button>';

                marker.bindPopup(`
                    <div class="photo-popup">
                        ${photoData.src ? `<img src="${photoData.src}" alt="Photo" style="cursor:pointer" onclick="MapView.openPhotoViewer('${sessionKey}', ${currentIndex})">` : '<p>No image available</p>'}
                        <div class="photo-nav-row">
                            ${navPrev}
                            <span class="photo-counter">${currentIndex + 1} / ${totalPhotos}</span>
                            ${navNext}
                        </div>
                        <div class="photo-meta">
                            <strong>${sessionName}</strong><br>
                            <a href="javascript:void(0)" class="popup-date-link" onclick="MapView.filterByDate('${photoDateForFilter}')" title="Filter to this date">${session.substring(0, 8)}</a>
                            <div class="popup-links">
                                <a href="javascript:void(0)" class="popup-zoom-link" onclick="MapView.zoomToSession('${athlete}', '${session}')">Zoom in</a>
                                <a href="#/session/${athlete}/${session}" class="popup-activity-link">View Activity →</a>
                            </div>
                        </div>
                    </div>
                `, { maxWidth: 350 });

                // Focus this activity in the Activities list when photo is clicked
                marker.on('click', () => {
                    this.focusSessionInList(athlete, session);
                });

                marker.addTo(this.photosLayer);
                this.photosBySession[sessionKey].push({ marker, index: currentIndex });
                this.totalPhotos++;
            }

            this.updateInfo();
        } catch (e) {
            console.warn(`Failed to load photos for ${photoKey}:`, e);
        }
    },

    // Navigate to a specific photo in the map popup
    showPhotoAtIndex(sessionKey, index) {
        const photoMarkers = this.photosBySession[sessionKey];
        if (!photoMarkers) return;

        // Find the marker with this index
        const entry = photoMarkers.find(p => p.index === index);
        if (entry && entry.marker) {
            // Close current popup, open the new one
            this.map.closePopup();
            entry.marker.openPopup();
            // Optionally pan to the marker
            this.map.panTo(entry.marker.getLatLng());
        }
    },

    // Open PhotoViewer with all photos from a session
    openPhotoViewer(sessionKey, startIndex) {
        const photos = this.sessionPhotoData[sessionKey];
        if (photos && photos.length > 0) {
            // sessionKey format: "athlete/datetime"
            const [athlete, datetime] = sessionKey.split('/');
            PhotoViewer.open(photos, startIndex, {
                athlete,
                datetime,
                source: 'map'
            });
        }
    },

    loadVisibleTracks() {
        if (this.map.getZoom() < this.AUTO_LOAD_ZOOM) return;

        const mapBounds = this.map.getBounds();
        for (const data of this.allMarkers) {
            // Only load tracks for markers that pass the current filter
            // visible is undefined initially (before filters applied), treat as visible
            // visible is explicitly false when filtered out
            if (data.visible === false) continue;
            if (mapBounds.contains(data.marker.getLatLng())) {
                this.loadTrack(data.athlete, data.session, data.color);
                if (data.hasPhotos) {
                    this.loadPhotos(data.athlete, data.session, data.sessionName);
                }
            }
        }
    },

    async loadSessions() {
        const loading = document.getElementById('loading');

        try {
            let athletes = [];
            try {
                const athletesResp = await fetch('athletes.tsv');
                if (athletesResp.ok) {
                    const athletesText = await athletesResp.text();
                    athletes = parseTSV(athletesText);
                }
            } catch (e) {
                console.warn('Could not load athletes.tsv, scanning directories...');
            }

            if (athletes.length === 0) {
                loading.textContent = 'Looking for sessions...';
            }

            // Initialize athlete stats
            for (const athlete of athletes) {
                const username = athlete.username;
                if (username) {
                    this.athleteStats[username] = { sessions: 0, distance: 0 };
                    // Assign color for each athlete
                    this.getAthleteColor(username);
                }
            }

            for (const athlete of athletes) {
                const username = athlete.username;
                if (!username) continue;

                // Initialize sessionsByAthlete for this athlete
                this.sessionsByAthlete[username] = [];

                try {
                    const sessionsResp = await fetch(`athl=${username}/sessions.tsv`);
                    if (!sessionsResp.ok) continue;

                    const sessionsText = await sessionsResp.text();
                    const sessions = parseTSV(sessionsText);

                    for (const session of sessions) {
                        const lat = parseFloat(session.start_lat);
                        const lng = parseFloat(session.start_lng);
                        const distance = parseFloat(session.distance_m || 0);

                        // Track athlete stats
                        this.athleteStats[username].sessions++;
                        this.athleteStats[username].distance += distance;

                        // Store full session data for SessionsView
                        const type = session.sport || session.type || 'Other';
                        const sessionData = {
                            athlete: username,
                            datetime: session.datetime,
                            datetime_local: session.datetime_local,
                            name: session.name || 'Activity',
                            type: type,
                            distance_m: session.distance_m || '0',
                            moving_time_s: session.moving_time_s || '0',
                            elevation_gain_m: session.elevation_gain_m || '0',
                            photo_count: session.photo_count || '0',
                            has_gps: session.has_gps,
                            start_lat: session.start_lat,
                            start_lng: session.start_lng
                        };
                        this.allSessions.push(sessionData);
                        this.sessionsByAthlete[username].push(sessionData);

                        if (isNaN(lat) || isNaN(lng)) continue;

                        const color = this.typeColors[type] || this.typeColors.Other;
                        const hasPhotos = parseInt(session.photo_count || '0') > 0;
                        const photoCount = parseInt(session.photo_count || '0');

                        let marker;
                        if (hasPhotos) {
                            const icon = L.divIcon({
                                html: `<div style="position:relative;">
                                    <div style="width:12px;height:12px;background:${color};border:2px solid white;border-radius:50%;box-shadow:0 2px 5px rgba(0,0,0,0.3);"></div>
                                    <div style="position:absolute;top:-6px;right:-8px;width:14px;height:14px;background:#E91E63;border:1.5px solid white;border-radius:50%;display:flex;align-items:center;justify-content:center;">
                                        <svg width="8" height="8" viewBox="0 0 24 24" fill="white"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>
                                    </div>
                                </div>`,
                                className: '',
                                iconSize: [20, 20],
                                iconAnchor: [8, 8]
                            });
                            marker = L.marker([lat, lng], { icon: icon });
                        } else {
                            marker = L.circleMarker([lat, lng], {
                                radius: 6,
                                fillColor: color,
                                color: 'white',
                                weight: 2,
                                opacity: 1,
                                fillOpacity: 0.8,
                                className: 'session-marker'
                            });
                        }

                        const photoInfo = hasPhotos ? `<br>Photos: ${photoCount}` : '';
                        const dateForFilter = session.datetime ? `${session.datetime.substring(0, 4)}-${session.datetime.substring(4, 6)}-${session.datetime.substring(6, 8)}` : '';
                        const dateDisplay = session.datetime?.substring(0, 8) || '';
                        marker.bindPopup(`
                            <b>${session.name || 'Activity'}</b><br>
                            Type: ${type}<br>
                            Date: <a href="javascript:void(0)" class="popup-date-link" onclick="MapView.filterByDate('${dateForFilter}')" title="Filter to this date">${dateDisplay}</a>${photoInfo}<br>
                            Distance: ${(parseFloat(session.distance_m || 0) / 1000).toFixed(2)} km
                            <div class="popup-links">
                                <a href="javascript:void(0)" class="popup-zoom-link" onclick="MapView.zoomToSession('${username}', '${session.datetime}')">Zoom in</a>
                                <a href="#/session/${username}/${session.datetime}" class="popup-activity-link">View Activity →</a>
                            </div>
                        `);

                        this.allMarkers.push({
                            marker: marker,
                            athlete: username,
                            session: session.datetime,
                            color: color,
                            hasGps: session.has_gps === 'true',
                            hasPhotos: hasPhotos,
                            sessionName: session.name || 'Activity'
                        });

                        marker.on('click', () => {
                            // Close any open popup before loading new track
                            this.map.closePopup();
                            this.loadTrack(username, session.datetime, color);
                            if (hasPhotos) {
                                this.loadPhotos(username, session.datetime, session.name || 'Activity');
                            }
                            // Focus this activity in the Activities list
                            this.focusSessionInList(username, session.datetime);
                            // Update URL with selected track, clear stale popup
                            URLState.update({
                                track: `${username}/${session.datetime}`,
                                popup: ''  // Clear popup when selecting new track
                            });
                        });

                        marker.addTo(this.sessionsLayer);
                        this.bounds.extend([lat, lng]);
                        this.totalSessions++;
                    }
                } catch (e) {
                    console.warn(`Failed to load sessions for ${username}:`, e);
                }
            }

            // Only fit bounds if not restoring from URL
            if (this.bounds.isValid() && !this.restoringFromURL) {
                this.map.fitBounds(this.bounds, { padding: [20, 20] });
            }
            this.restoringFromURL = false;  // Reset flag after first load

            // Populate athlete selector with stats
            this.populateAthleteSelector();

            loading.classList.add('hidden');
            this.updateInfo();

        } catch (e) {
            loading.textContent = 'Error loading data: ' + e.message;
            console.error('Error loading sessions:', e);
        }
    },

    updateInfo() {
        // Save scroll position and list height before updating
        let savedScrollTop = 0;
        if (this.infoControl) {
            const existingList = document.querySelector('.info-session-list');
            if (existingList) {
                savedScrollTop = existingList.scrollTop;
                // Save user's resized height if different from default
                const height = existingList.offsetHeight;
                if (height > 0) {
                    this.sessionListHeight = height;
                }
            }
            this.infoControl.remove();
        }
        this.infoControl = L.control({ position: 'topright' });
        const self = this;
        this.infoControl.onAdd = function() {
            const div = L.DomUtil.create('div', 'info map-info-panel');

            // Use filtered sessions count
            const filteredCount = self.filteredSessions.length;
            const totalCount = self.allSessions.length;
            const hasFilter = FilterState.hasActiveFilters() || self.currentAthlete;

            let html = '<div class="info-header"><b>Activities</b>';
            if (self.currentAthlete) {
                const color = self.athleteColors[self.currentAthlete] || '#333';
                html += ` <span style="color:${color}">${self.currentAthlete}</span>`;
            }
            html += '</div>';

            // Session count with filter indicator
            let countText;
            if (self.viewportFilterEnabled) {
                // Show "X in view of Y" when viewport filter is active
                const inViewCount = self.viewportFilteredCount || filteredCount;
                const baseCount = self.preViewportFilteredCount || totalCount;
                countText = `${inViewCount} in view`;
                if (hasFilter || inViewCount !== baseCount) {
                    countText += ` of ${baseCount}`;
                }
            } else {
                countText = hasFilter ? `${filteredCount} of ${totalCount}` : `${filteredCount}`;
            }
            html += '<div class="info-stats">';
            html += `<span class="info-sessions-toggle" title="Click to ${self.sessionListExpanded ? 'collapse' : 'expand'} session list">${countText} sessions ${self.sessionListExpanded ? '▲' : '▼'}</span>`;
            if (self.loadedTrackCount > 0) {
                html += `<br>${self.loadedTrackCount} tracks`;
            }
            if (self.totalPhotos > 0) {
                html += ` · ${self.totalPhotos} photos`;
            }
            html += '</div>';

            // Collapsible session list
            if (self.sessionListExpanded && self.filteredSessions.length === 0 && self.viewportFilterEnabled) {
                // Empty state when viewport filter is ON but no activities in view
                html += '<div class="info-session-list" style="text-align:center;padding:16px;color:#666;">';
                html += '<svg width="24" height="24" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom:8px;opacity:0.5;">';
                html += '<path d="M2 5V2h3M11 2h3v3M14 11v3h-3M5 14H2v-3"/>';
                html += '<circle cx="8" cy="8" r="1.5" fill="currentColor"/>';
                html += '</svg>';
                html += '<div style="margin-bottom:8px;">No activities in this area</div>';
                html += '<div style="display:flex;gap:8px;justify-content:center;">';
                html += '<button class="viewport-empty-zoom" style="padding:4px 8px;border:1px solid #ccc;background:#fff;border-radius:4px;cursor:pointer;">Zoom out</button>';
                html += '<button class="viewport-empty-showall" style="padding:4px 8px;border:1px solid #ccc;background:#fff;border-radius:4px;cursor:pointer;">Show all</button>';
                html += '</div>';
                html += '</div>';
            } else if (self.sessionListExpanded && self.filteredSessions.length > 0) {
                html += '<div class="info-session-list">';
                const limit = self.maxVisibleSessions || 50;
                const toShow = self.filteredSessions.slice(0, limit);
                for (const s of toShow) {
                    const dateStr = s.datetime ? `${s.datetime.substring(0,4)}-${s.datetime.substring(4,6)}-${s.datetime.substring(6,8)}` : '';
                    const dist = s.distance_m > 0 ? ` · ${(parseFloat(s.distance_m) / 1000).toFixed(1)}km` : '';
                    const typeColor = self.typeColors[s.type] || self.typeColors.Other;
                    const photoCount = parseInt(s.photo_count) || 0;
                    const photoIcon = photoCount > 0 ? `<span class="info-session-photo" title="${photoCount} photo${photoCount > 1 ? 's' : ''}"><svg width="12" height="12" viewBox="0 0 24 24" fill="#E91E63"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg></span>` : '';
                    html += `<div class="info-session-item" data-athlete="${s.athlete}" data-datetime="${s.datetime}">`;
                    html += '<div class="info-session-main">';
                    html += `<span class="info-session-date" data-date="${dateStr}" title="Click to filter to this date">${dateStr}</span>`;
                    html += `<span class="info-session-type" style="color:${typeColor}">${s.type || ''}</span>${photoIcon}`;
                    html += `<div class="info-session-name">${s.name || 'Untitled'}${dist}</div>`;
                    html += '</div>';
                    html += `<a href="#/session/${s.athlete}/${s.datetime}" class="info-session-link" title="View Activity">→</a>`;
                    html += '</div>';
                }
                if (self.filteredSessions.length > limit) {
                    // Build sessions URL with current filters
                    const filters = FilterState.get();
                    const params = new URLSearchParams();
                    if (filters.type) params.set('t', filters.type);
                    if (filters.dateFrom) params.set('from', filters.dateFrom);
                    if (filters.dateTo) params.set('to', filters.dateTo);
                    if (filters.search) params.set('q', filters.search);
                    if (self.currentAthlete) params.set('a', self.currentAthlete);
                    const sessionsUrl = params.toString() ? `#/sessions?${params.toString()}` : '#/sessions';
                    html += `<div class="info-session-more"><a href="${sessionsUrl}">View all ${self.filteredSessions.length} sessions</a></div>`;
                }
                html += '</div>';
                html += '<div class="info-resize-handle" title="Drag to resize"></div>';
            }

            // Zoom hint
            const zoom = self.map.getZoom();
            if (zoom < self.AUTO_LOAD_ZOOM) {
                html += '<div class="info-hint">Zoom in to auto-load tracks</div>';
            }

            div.innerHTML = html;

            // Set up event listeners after DOM is ready
            setTimeout(() => {
                // Restore scroll position and height
                const newList = div.querySelector('.info-session-list');
                if (newList) {
                    // Apply saved height if user has resized
                    if (self.sessionListHeight && self.sessionListHeight > 0) {
                        newList.style.maxHeight = self.sessionListHeight + 'px';
                    }
                    // Restore scroll position - use requestAnimationFrame for reliability
                    if (savedScrollTop > 0) {
                        requestAnimationFrame(() => {
                            newList.scrollTop = savedScrollTop;
                        });
                    }
                    // Prevent scroll events from propagating to map (fixes touchpad scrolling)
                    newList.addEventListener('wheel', (e) => {
                        e.stopPropagation();
                    }, { passive: true });
                }

                // Prevent map interactions on the entire panel
                L.DomEvent.disableScrollPropagation(div);
                L.DomEvent.disableClickPropagation(div);

                // Resize handle drag functionality
                const resizeHandle = div.querySelector('.info-resize-handle');
                if (resizeHandle && newList) {
                    let startY, startHeight;
                    const onMouseMove = (e) => {
                        const delta = e.clientY - startY;
                        // Allow expanding up to 80% of viewport height
                        const maxHeight = Math.min(800, window.innerHeight * 0.8);
                        const newHeight = Math.max(100, Math.min(maxHeight, startHeight + delta));
                        newList.style.maxHeight = newHeight + 'px';
                        // Save height for persistence
                        self.sessionListHeight = newHeight;
                    };
                    const onMouseUp = () => {
                        document.removeEventListener('mousemove', onMouseMove);
                        document.removeEventListener('mouseup', onMouseUp);
                        document.body.style.cursor = '';
                        document.body.style.userSelect = '';
                    };
                    resizeHandle.addEventListener('mousedown', (e) => {
                        e.preventDefault();
                        startY = e.clientY;
                        startHeight = newList.offsetHeight;
                        document.body.style.cursor = 'ns-resize';
                        document.body.style.userSelect = 'none';
                        document.addEventListener('mousemove', onMouseMove);
                        document.addEventListener('mouseup', onMouseUp);
                    });
                }

                // Toggle session list
                const toggle = div.querySelector('.info-sessions-toggle');
                if (toggle) {
                    toggle.addEventListener('click', (e) => {
                        e.preventDefault();
                        self.sessionListExpanded = !self.sessionListExpanded;
                        self.updateInfo();
                    });
                }
                // Date clicks - filter to that specific date
                div.querySelectorAll('.info-session-date').forEach(dateEl => {
                    dateEl.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const date = dateEl.dataset.date;
                        if (date) {
                            FilterState.set({ dateFrom: date, dateTo: date });
                            FilterState.syncToURL();
                            // Update filter bar inputs so date navigation works
                            FilterBar.syncFromState('map-filter-bar');
                        }
                    });
                });

                // Session item clicks - zoom to session on map
                div.querySelectorAll('.info-session-item').forEach(item => {
                    // Click on main area (except date) zooms to session
                    const mainArea = item.querySelector('.info-session-main');
                    if (mainArea) {
                        mainArea.style.cursor = 'pointer';
                        mainArea.addEventListener('click', (e) => {
                            // Don't zoom if clicking on the date
                            if (e.target.classList.contains('info-session-date')) return;
                            e.preventDefault();
                            e.stopPropagation();
                            const athlete = item.dataset.athlete;
                            const datetime = item.dataset.datetime;
                            self.zoomToSession(athlete, datetime);
                        });
                    }
                    // Arrow link navigates to session (handled by href)
                });

                // Viewport filter empty state buttons
                const zoomOutBtn = div.querySelector('.viewport-empty-zoom');
                if (zoomOutBtn) {
                    zoomOutBtn.addEventListener('click', () => {
                        self.fitToVisibleMarkers();
                    });
                }
                const showAllBtn = div.querySelector('.viewport-empty-showall');
                if (showAllBtn) {
                    showAllBtn.addEventListener('click', () => {
                        // Turn off viewport filter
                        self.viewportFilterEnabled = false;
                        // Update button state
                        const vpBtn = self.viewportFilterControl?.getContainer()?.querySelector('button');
                        if (vpBtn) {
                            vpBtn.classList.remove('active');
                            vpBtn.setAttribute('aria-checked', 'false');
                        }
                        // Update URL
                        URLState.update({ viewportFilter: false });
                        // Refresh the list
                        self.applyFiltersAndUpdateUI();
                    });
                }
            }, 0);

            return div;
        };
        this.infoControl.addTo(this.map);
    },

    setupLegend() {
        this.legendControl = L.control({ position: 'bottomright' });
        const self = this;
        this.legendControl.onAdd = function() {
            const div = L.DomUtil.create('div', 'info legend');
            self.updateLegendContent(div);
            return div;
        };
        this.legendControl.addTo(this.map);
    },

    updateLegendContent(div) {
        if (!div) {
            div = document.querySelector('.info.legend');
        }
        if (!div) return;

        if (this.displayMode === 'heatmap') {
            div.innerHTML = '<b>Activity Density</b><br>';
            div.innerHTML += '<div class="heatmap-gradient"></div>';
            div.innerHTML += '<div class="heatmap-labels"><span>Low</span><span>High</span></div>';
            div.innerHTML += `<br>${this.heatmapPoints.length.toLocaleString()} GPS points`;
        } else {
            const currentType = FilterState.get().type || '';
            div.innerHTML = '<b>Activity Types</b><br>';
            for (const [type, color] of Object.entries(this.typeColors)) {
                const isActive = currentType === type;
                div.innerHTML += `<span class="legend-type-item${isActive ? ' active' : ''}" data-type="${type}" style="cursor:pointer;display:block;padding:2px 4px;margin:1px 0;border-radius:3px;${isActive ? 'background:rgba(0,0,0,0.1);font-weight:bold;' : ''}"><i style="background:${color}"></i> ${type}</span>`;
            }
            // Clear filter option when a filter is active
            if (currentType) {
                div.innerHTML += '<span class="legend-clear-filter" style="cursor:pointer;display:block;padding:2px 4px;margin-top:4px;color:#666;font-style:italic;">&times; Clear filter</span>';
            }
            div.innerHTML += '<br><i style="background:#E91E63;border-radius:50%;"></i> Photos';

            // Add click handlers
            div.querySelectorAll('.legend-type-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const clickedType = item.dataset.type;
                    const current = FilterState.get().type;
                    // Toggle: if clicking active type, clear it
                    const newType = current === clickedType ? '' : clickedType;
                    FilterState.set({ type: newType });
                    FilterState.syncToURL();
                    this.updateLegendContent(div);
                });
                item.addEventListener('mouseenter', () => {
                    if (!item.classList.contains('active')) {
                        item.style.background = 'rgba(0,0,0,0.05)';
                    }
                });
                item.addEventListener('mouseleave', () => {
                    if (!item.classList.contains('active')) {
                        item.style.background = 'transparent';
                    }
                });
            });
            const clearBtn = div.querySelector('.legend-clear-filter');
            if (clearBtn) {
                clearBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    FilterState.set({ type: '' });
                    FilterState.syncToURL();
                    this.updateLegendContent(div);
                });
                clearBtn.addEventListener('mouseenter', () => {
                    clearBtn.style.background = 'rgba(0,0,0,0.05)';
                });
                clearBtn.addEventListener('mouseleave', () => {
                    clearBtn.style.background = 'transparent';
                });
            }
        }
    },

    setupLayersControl() {
        const layersControl = L.control({ position: 'topleft' });
        const self = this;

        layersControl.onAdd = function() {
            const div = L.DomUtil.create('div', 'info layers-control');

            div.innerHTML = `
                <div class="layers-control-header">
                    <svg viewBox="0 0 24 24"><path d="M11.99 18.54l-7.37-5.73L3 14.07l9 7 9-7-1.63-1.27-7.38 5.74zM12 16l7.36-5.73L21 9l-9-7-9 7 1.63 1.27L12 16z"/></svg>
                    Layers
                </div>
                <div class="layers-section">
                    <div class="layers-section-label">Display Mode</div>
                    <label>
                        <input type="radio" name="displayMode" value="tracks" checked>
                        Tracks
                    </label>
                    <label>
                        <input type="radio" name="displayMode" value="heatmap">
                        Heatmap
                    </label>
                </div>
                <div class="layers-divider"></div>
                <div class="layers-section">
                    <div class="layers-section-label">Overlays</div>
                    <label>
                        <input type="checkbox" name="showMarkers" checked>
                        Markers
                    </label>
                    <label>
                        <input type="checkbox" name="showPhotos" checked>
                        Photos
                    </label>
                </div>
            `;

            // Prevent map interactions
            L.DomEvent.disableClickPropagation(div);
            L.DomEvent.disableScrollPropagation(div);

            // Display mode radio buttons
            div.querySelectorAll('input[name="displayMode"]').forEach(radio => {
                radio.addEventListener('change', (e) => {
                    self.setDisplayMode(e.target.value);
                });
            });

            // Overlay checkboxes
            div.querySelector('input[name="showMarkers"]').addEventListener('change', (e) => {
                if (e.target.checked) {
                    self.sessionsLayer.addTo(self.map);
                } else {
                    self.map.removeLayer(self.sessionsLayer);
                }
            });

            div.querySelector('input[name="showPhotos"]').addEventListener('change', (e) => {
                if (e.target.checked) {
                    self.photosLayer.addTo(self.map);
                } else {
                    self.map.removeLayer(self.photosLayer);
                }
            });

            return div;
        };

        layersControl.addTo(this.map);
    },

    setDisplayMode(mode) {
        this.displayMode = mode;

        if (mode === 'heatmap') {
            // Hide tracks, show heatmap
            this.map.removeLayer(this.tracksLayer);
            // Auto-load visible tracks for heatmap data
            this.loadVisibleTracksForHeatmap();
        } else {
            // Hide heatmap, show tracks
            if (this.heatmapLayer) {
                this.map.removeLayer(this.heatmapLayer);
                // Destroy the layer to avoid stale canvas issues
                this.heatmapLayer = null;
            }
            this.tracksLayer.addTo(this.map);
        }

        // Update legend
        this.updateLegendContent();
    },

    async loadVisibleTracksForHeatmap() {
        // Load all visible tracks to populate heatmap data
        const bounds = this.map.getBounds();
        // Use allMarkers and filter by both visibility (from filters) and map bounds
        const visibleMarkers = (this.allMarkers || []).filter(m => {
            if (!m.visible) return false;
            const pos = m.marker.getLatLng();
            return bounds.contains(pos);
        });

        // Load tracks for visible markers that aren't already loaded
        const loadPromises = [];
        for (const m of visibleMarkers) {
            const trackKey = `${m.athlete}/${m.session}`;
            if (!this.loadedTracks.has(trackKey) && !this.loadingTracks.has(trackKey)) {
                loadPromises.push(this.loadTrack(m.athlete, m.session, m.color));
            }
        }

        // Wait for some tracks to load before showing heatmap
        if (loadPromises.length > 0) {
            console.log(`Loading ${loadPromises.length} tracks for heatmap...`);
            await Promise.all(loadPromises);
        }

        // Now show the heatmap
        this.createOrShowHeatmap();
    },

    createOrShowHeatmap() {
        // Don't create heatmap with empty data - causes errors
        if (this.heatmapPoints.length === 0) {
            console.log('No heatmap points available yet.');
            return;
        }

        // Sample points if too many (for performance)
        let points = this.heatmapPoints;
        const maxPoints = 50000;
        if (points.length > maxPoints) {
            const step = Math.ceil(points.length / maxPoints);
            points = points.filter((_, i) => i % step === 0);
        }

        // Create or update heatmap layer
        const heatData = points.map(p => [p[0], p[1], 1.0]);

        // Always create a fresh layer to avoid stale canvas issues
        if (this.heatmapLayer) {
            try {
                this.map.removeLayer(this.heatmapLayer);
            } catch (e) {
                // Layer may already be removed
            }
            this.heatmapLayer = null;
        }

        this.heatmapLayer = L.heatLayer(heatData, {
            radius: 15,
            blur: 20,
            maxZoom: 17,
            gradient: {
                0.0: 'blue',
                0.25: 'cyan',
                0.5: 'lime',
                0.75: 'yellow',
                1.0: 'red'
            }
        }).addTo(this.map);

        // Update legend with point count
        this.updateLegendContent();
    },

    addPointsToHeatmap(points) {
        // Called when tracks are loaded to add points to heatmap data
        this.heatmapPoints = this.heatmapPoints.concat(points);

        // If heatmap is active, update it
        if (this.displayMode === 'heatmap' && this.heatmapLayer) {
            this.createOrShowHeatmap();
            this.updateLegendContent();
        }
    }
};
window.MapView = MapView;

// ===== Sessions View Module =====
const SessionsView = {
    sessions: [],
    filtered: [],
    sortBy: 'datetime',
    sortDir: 'desc',
    filters: { search: '', type: '', dateFrom: '', dateTo: '' },
    page: 1,
    perPage: 50,
    typeColors: {
        'Run': '#FF5722',
        'Ride': '#2196F3',
        'Hike': '#4CAF50',
        'Walk': '#9C27B0',
        'Swim': '#00BCD4',
        'Other': '#607D8B'
    },
    selectedSession: null,

    init() {
        // Initialize filter bar using shared FilterBar component
        FilterBar.render('sessions-filter-bar', {
            showSearch: true,
            showType: true,
            showDatePresets: true,
            showDates: true
        });
        FilterBar.init('sessions-filter-bar');

        // Subscribe to FilterState changes
        FilterState.onChange(() => {
            this.page = 1;
            this.applyFiltersAndRender();
        });

        // Set up sortable headers
        document.querySelectorAll('#sessions-table th.sortable').forEach(th => {
            th.addEventListener('click', () => this.handleSort(th.dataset.sort));
        });

        // Set up detail panel close
        document.getElementById('close-detail').addEventListener('click', () => {
            this.closeDetail();
        });

        // Set up expand button to open full-screen view
        document.getElementById('expand-detail').addEventListener('click', () => {
            if (this.selectedSession) {
                const athlete = this.selectedSession.athlete;
                const datetime = this.selectedSession.datetime;
                location.hash = '#/session/' + athlete + '/' + datetime;
            }
        });

        // Set up swipe-to-close on detail panel (mobile touch gesture)
        const detailPanel = document.getElementById('session-detail');
        let touchStartX = 0;
        let touchStartY = 0;
        detailPanel.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        }, { passive: true });
        detailPanel.addEventListener('touchend', (e) => {
            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;
            const deltaX = touchEndX - touchStartX;
            const deltaY = Math.abs(touchEndY - touchStartY);
            // Close if swiped right by at least 80px and mostly horizontal
            if (deltaX > 80 && deltaY < 50) {
                this.closeDetail();
            }
        }, { passive: true });

        // Listen for athlete changes
        document.getElementById('athlete-selector').addEventListener('change', () => {
            this.page = 1;
            this.applyFiltersAndRender();
        });
    },

    setSessions(sessions) {
        this.sessions = sessions;
        // Use shared FilterBar component for type population and state sync
        FilterBar.populateTypes('sessions-filter-bar', sessions);
        FilterBar.syncFromState('sessions-filter-bar');
        this.applyFiltersAndRender();
    },

    applyFiltersAndRender() {
        const currentAthlete = document.getElementById('athlete-selector').value;
        const filters = FilterState.get();

        // Use shared applyFilters function
        this.filtered = applyFilters(this.sessions, filters, currentAthlete);

        // Update filter count display
        FilterBar.updateCount('sessions-filter-bar', this.filtered.length, this.sessions.length);

        this.sort();
        this.render();
    },

    // Alias for external calls (e.g., from stats chart clicks)
    applyFilters() {
        this.applyFiltersAndRender();
    },

    handleSort(field) {
        if (this.sortBy === field) {
            this.sortDir = this.sortDir === 'desc' ? 'asc' : 'desc';
        } else {
            this.sortBy = field;
            this.sortDir = 'desc';
        }

        // Update header styles
        document.querySelectorAll('#sessions-table th.sortable').forEach(th => {
            th.classList.remove('sorted-asc', 'sorted-desc');
            if (th.dataset.sort === field) {
                th.classList.add(this.sortDir === 'asc' ? 'sorted-asc' : 'sorted-desc');
            }
        });

        this.sort();
        this.render();
    },

    sort() {
        this.filtered.sort((a, b) => {
            let valA, valB;
            switch (this.sortBy) {
                case 'datetime':
                    valA = a.datetime || '';
                    valB = b.datetime || '';
                    break;
                case 'name':
                    valA = (a.name || '').toLowerCase();
                    valB = (b.name || '').toLowerCase();
                    break;
                case 'type':
                    valA = a.type || '';
                    valB = b.type || '';
                    break;
                case 'distance':
                    valA = parseFloat(a.distance_m) || 0;
                    valB = parseFloat(b.distance_m) || 0;
                    break;
                case 'duration':
                    valA = parseInt(a.moving_time_s) || 0;
                    valB = parseInt(b.moving_time_s) || 0;
                    break;
                case 'photos':
                    valA = parseInt(a.photo_count) || 0;
                    valB = parseInt(b.photo_count) || 0;
                    break;
                default:
                    valA = a[this.sortBy] || '';
                    valB = b[this.sortBy] || '';
            }
            const cmp = valA > valB ? 1 : valA < valB ? -1 : 0;
            return this.sortDir === 'desc' ? -cmp : cmp;
        });
    },

    formatDuration(seconds) {
        if (!seconds) return '-';
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        if (h > 0) return `${h}h ${m}m`;
        return `${m}m`;
    },

    formatDate(datetime) {
        if (!datetime || datetime.length < 8) return '-';
        const y = datetime.substring(0, 4);
        const m = datetime.substring(4, 6);
        const d = datetime.substring(6, 8);
        return `${y}-${m}-${d}`;
    },

    render() {
        const tbody = document.getElementById('sessions-tbody');
        const start = (this.page - 1) * this.perPage;
        const end = start + this.perPage;
        const pageData = this.filtered.slice(start, end);

        if (pageData.length === 0) {
            const hasFilters = this.filters.search || this.filters.type || this.filters.dateFrom || this.filters.dateTo;
            tbody.innerHTML = `<tr><td colspan="6">
                <div class="empty-state">
                    <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 14c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H9V5h6v2z"/></svg>
                    <h3>No sessions found</h3>
                    <p>${hasFilters ? 'Try adjusting your filters or search terms' : 'No activity data available yet'}</p>
                    ${hasFilters ? '<button class="clear-filters-btn" onclick="FilterState.clear(); FilterState.syncToURL();">Clear Filters</button>' : ''}
                </div>
            </td></tr>`;
        } else {
            tbody.innerHTML = pageData.map(s => {
                const color = this.typeColors[s.type] || this.typeColors.Other || '#607D8B';
                const distance = parseFloat(s.distance_m) || 0;
                const duration = parseInt(s.moving_time_s) || 0;
                const photos = parseInt(s.photo_count) || 0;
                return `
                    <tr data-athlete="${s.athlete}" data-session="${s.datetime}">
                        <td>${this.formatDate(s.datetime)}</td>
                        <td>${s.name || 'Activity'}</td>
                        <td><span class="session-type" style="background:${color}20;color:${color}">${s.type || 'Other'}</span></td>
                        <td>${(distance / 1000).toFixed(2)} km</td>
                        <td>${this.formatDuration(duration)}</td>
                        <td>${photos > 0 ? photos : '-'}</td>
                    </tr>
                `;
            }).join('');

            // Add click handlers
            tbody.querySelectorAll('tr').forEach(tr => {
                tr.addEventListener('click', () => {
                    const athlete = tr.dataset.athlete;
                    const session = tr.dataset.session;
                    this.showDetail(athlete, session);

                    // Update selection style
                    tbody.querySelectorAll('tr').forEach(r => r.classList.remove('selected'));
                    tr.classList.add('selected');
                });
            });
        }

        this.renderPagination();
    },

    renderPagination() {
        const totalPages = Math.ceil(this.filtered.length / this.perPage);
        const pagination = document.getElementById('pagination');

        if (totalPages <= 1) {
            pagination.innerHTML = `<span class="page-info">${this.filtered.length} sessions</span>`;
            return;
        }

        pagination.innerHTML = `
            <button ${this.page <= 1 ? 'disabled' : ''} id="prev-page">Previous</button>
            <span class="page-info">Page ${this.page} of ${totalPages} (${this.filtered.length} sessions)</span>
            <button ${this.page >= totalPages ? 'disabled' : ''} id="next-page">Next</button>
        `;

        document.getElementById('prev-page')?.addEventListener('click', () => {
            if (this.page > 1) {
                this.page--;
                this.render();
            }
        });

        document.getElementById('next-page')?.addEventListener('click', () => {
            if (this.page < totalPages) {
                this.page++;
                this.render();
            }
        });
    },

    showDetail(athlete, sessionId) {
        const session = this.sessions.find(s => s.athlete === athlete && s.datetime === sessionId);
        if (!session) return;

        this.selectedSession = session;
        const panel = document.getElementById('session-detail');
        panel.classList.remove('hidden');

        // Update URL with session permalink
        URLState.update({ session: sessionId, athlete: athlete });

        document.getElementById('detail-name').textContent = session.name || 'Activity';

        const distance = parseFloat(session.distance_m) || 0;
        const duration = parseInt(session.moving_time_s) || 0;
        const elevation = parseFloat(session.elevation_gain_m) || 0;

        document.getElementById('detail-meta').innerHTML = `
            <div>${session.type || 'Activity'} · ${this.formatDate(session.datetime)}</div>
            <div style="font-size:12px;color:#999;margin-top:4px;">Athlete: ${athlete}</div>
        `;

        document.getElementById('detail-stats').innerHTML = `
            <div class="stat-card">
                <div class="stat-value">${(distance / 1000).toFixed(2)}</div>
                <div class="stat-label">km</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${this.formatDuration(duration)}</div>
                <div class="stat-label">Duration</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${elevation.toFixed(0)}</div>
                <div class="stat-label">m elevation</div>
            </div>
        `;

        // Load track for mini-map
        this.loadDetailMap(athlete, sessionId);

        // Load description from info.json
        this.loadDetailDescription(athlete, sessionId);

        // Load photos if available
        const photoCount = parseInt(session.photo_count) || 0;
        if (photoCount > 0) {
            this.loadDetailPhotos(athlete, sessionId);
        } else {
            document.getElementById('detail-photos').innerHTML = '';
        }

        // Load social data (kudos, comments)
        this.loadDetailSocial(athlete, sessionId);

        // Load data streams (heart rate, cadence, etc.)
        this.loadDetailStreams(athlete, sessionId);

        // Check for shared runs (same datetime, different athlete)
        this.loadSharedRuns(athlete, sessionId);
    },

    async loadSharedRuns(currentAthlete, sessionId) {
        const container = document.getElementById('detail-shared');
        if (!container) return;
        container.innerHTML = '';

        // Find sessions from other athletes with the same datetime
        const sharedWith = [];
        for (const [athleteUsername, sessions] of Object.entries(MapView.sessionsByAthlete || {})) {
            if (athleteUsername === currentAthlete) continue;

            const match = sessions.find(s => s.datetime === sessionId);
            if (match) {
                sharedWith.push({
                    username: athleteUsername,
                    session: match
                });
            }
        }

        if (sharedWith.length === 0) return;

        container.innerHTML = `
            <div class="shared-runs">
                <strong>Also with:</strong>
                ${sharedWith.map(s => `
                    <a href="#" class="shared-athlete-link" data-athlete="${s.username}" data-session="${s.session.datetime}">
                        ${s.username}
                    </a>
                `).join(', ')}
            </div>
        `;

        // Add click handlers for cross-athlete navigation
        container.querySelectorAll('.shared-athlete-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const athlete = e.target.dataset.athlete;
                const sessionDt = e.target.dataset.session;

                // Switch athlete and show their version of the session
                const athleteSelect = document.getElementById('athlete-select');
                athleteSelect.value = athlete;
                athleteSelect.dispatchEvent(new Event('change'));

                // After a short delay to allow filter update, show the session
                setTimeout(() => {
                    const session = MapView.sessionsByAthlete[athlete]?.find(s => s.datetime === sessionDt);
                    if (session) {
                        this.showDetail(session, athlete);
                    }
                }, 200);
            });
        });
    },

    detailMapInstance: null,

    async loadDetailMap(athlete, sessionId) {
        const mapContainer = document.getElementById('detail-map');

        // Destroy previous map instance if exists
        if (this.detailMapInstance) {
            this.detailMapInstance.remove();
            this.detailMapInstance = null;
        }

        // Remove any existing "View on Map" button
        document.querySelectorAll('.view-on-map-btn').forEach(btn => btn.remove());

        mapContainer.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#666;">Loading track...</div>';

        try {
            const url = `athl=${athlete}/ses=${sessionId}/tracking.parquet`;
            const response = await fetch(url);
            if (!response.ok) {
                // Hide container if no track data
                mapContainer.style.display = 'none';
                return;
            }

            const arrayBuffer = await response.arrayBuffer();
            const { parquetReadObjects } = await import('../hyparquet/index.js');
            const rows = await parquetReadObjects({ file: arrayBuffer, columns: ['lat', 'lng'] });

            const coords = rows ? rows.filter(r => r.lat && r.lng).map(r => [r.lat, r.lng]) : [];

            if (coords.length > 0) {
                mapContainer.style.display = 'block';
                mapContainer.innerHTML = '';
                this.detailMapInstance = L.map(mapContainer, { zoomControl: false, attributionControl: false });
                L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(this.detailMapInstance);

                const session = this.selectedSession;
                const color = this.typeColors[session?.type] || '#fc4c02';
                const polyline = L.polyline(coords, { color, weight: 3 }).addTo(this.detailMapInstance);
                this.detailMapInstance.fitBounds(polyline.getBounds(), { padding: [10, 10] });

                // Add "View on Map" button with proper navigation
                const lat = coords[0][0];
                const lng = coords[0][1];
                const btn = document.createElement('button');
                btn.className = 'view-on-map-btn';
                btn.textContent = 'View on Map';
                btn.onclick = () => {
                    const session = this.selectedSession;
                    if (session) {
                        // Include track parameter to load the track on the map
                        const trackKey = `${session.athlete}/${session.datetime}`;
                        location.hash = `#/map?z=14&lat=${lat}&lng=${lng}&track=${encodeURIComponent(trackKey)}`;
                    } else {
                        location.hash = `#/map?z=14&lat=${lat}&lng=${lng}`;
                    }
                };
                mapContainer.insertAdjacentElement('afterend', btn);
            } else {
                // Hide container if no GPS coords
                mapContainer.style.display = 'none';
            }
        } catch (e) {
            console.warn('Failed to load detail map:', e);
            mapContainer.style.display = 'none';
        }
    },

    // Convert URLs in text to clickable links (with HTML escaping for safety)
    linkifyText(text) {
        // First escape HTML entities to prevent XSS
        const escapeHtml = (str) => str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');

        const escaped = escapeHtml(text);

        // Then convert URLs to links
        // Match http:// or https:// URLs
        const urlPattern = /(https?:\/\/[^\s<>&"]+)/g;
        return escaped.replace(urlPattern, '<a href="$1" target="_blank" rel="noopener">$1</a>');
    },

    async loadDetailDescription(athlete, sessionId) {
        const container = document.getElementById('detail-description');
        container.innerHTML = '';

        try {
            const response = await fetch(`athl=${athlete}/ses=${sessionId}/info.json`);
            if (!response.ok) return;

            const info = await response.json();
            const description = info.description;

            if (description && description.trim()) {
                container.innerHTML = this.linkifyText(description);
            }
        } catch (e) {
            console.warn('Failed to load description:', e);
        }
    },

    async loadDetailPhotos(athlete, sessionId) {
        const container = document.getElementById('detail-photos');
        container.innerHTML = '<div style="color:#666;">Loading photos...</div>';

        try {
            const response = await fetch(`athl=${athlete}/ses=${sessionId}/info.json`);
            if (!response.ok) {
                container.innerHTML = '';
                return;
            }

            const info = await response.json();
            const photos = info.photos || [];

            if (photos.length === 0) {
                container.innerHTML = '';
                return;
            }

            container.innerHTML = photos.map(photo => {
                const urls = photo.urls || {};
                const thumbUrl = urls['256'] || urls['600'] || Object.values(urls)[0] || '';
                const fullUrl = urls['2048'] || urls['1024'] || urls['600'] || thumbUrl;

                // Try local path
                const createdAt = photo.created_at || '';
                let localPath = '';
                if (createdAt) {
                    const dt = createdAt.replace(/[-:]/g, '').replace(/\+.*$/, '').substring(0, 15);
                    localPath = `athl=${athlete}/ses=${sessionId}/photos/${dt}.jpg`;
                }

                const src = localPath || thumbUrl;
                const href = localPath || fullUrl;

                return src ? `<a href="${href}" target="_blank"><img src="${src}" alt="Photo"></a>` : '';
            }).join('');
        } catch (e) {
            console.warn('Failed to load detail photos:', e);
            container.innerHTML = '';
        }
    },

    async loadDetailSocial(athlete, sessionId) {
        const container = document.getElementById('detail-social');
        container.innerHTML = '';

        try {
            const response = await fetch(`athl=${athlete}/ses=${sessionId}/info.json`);
            if (!response.ok) return;

            const info = await response.json();
            const kudos = info.kudos || [];
            const comments = info.comments || [];

            if (kudos.length === 0 && comments.length === 0) return;

            let html = '';

            if (kudos.length > 0) {
                html += '<h4>Kudos (' + kudos.length + ')</h4>';
                html += '<div class="kudos-list">';
                html += kudos.map(k => `<span class="kudos-item">${k.firstname || ''} ${k.lastname || ''}</span>`).join('');
                html += '</div>';
            }

            if (comments.length > 0) {
                html += '<h4>Comments (' + comments.length + ')</h4>';
                html += '<div class="comments-list">';
                html += comments.map(c => `
                    <div class="comment-item">
                        <div class="comment-author">${c.firstname || ''} ${c.lastname || ''}</div>
                        <div class="comment-text">${c.text || ''}</div>
                    </div>
                `).join('');
                html += '</div>';
            }

            container.innerHTML = html;
        } catch (e) {
            console.warn('Failed to load social data:', e);
        }
    },

    async loadDetailStreams(athlete, sessionId) {
        const container = document.getElementById('detail-streams');
        container.innerHTML = '';

        try {
            const url = `athl=${athlete}/ses=${sessionId}/tracking.parquet`;
            const response = await fetch(url);
            if (!response.ok) return;

            const arrayBuffer = await response.arrayBuffer();
            const { parquetReadObjects } = await import('../hyparquet/index.js');

            // Try to get all available columns
            const rows = await parquetReadObjects({ file: arrayBuffer });
            if (!rows || rows.length === 0) return;

            // Detect available streams from first row
            const sampleRow = rows[0];
            const streamConfigs = [
                { key: 'hr', label: 'Heart Rate', unit: 'bpm' },
                { key: 'heartrate', label: 'Heart Rate', unit: 'bpm' },
                { key: 'cadence', label: 'Cadence', unit: 'rpm' },
                { key: 'watts', label: 'Power', unit: 'W' },
                { key: 'power', label: 'Power', unit: 'W' },
                { key: 'temp', label: 'Temperature', unit: '°C' },
                { key: 'temperature', label: 'Temperature', unit: '°C' },
                { key: 'altitude', label: 'Elevation', unit: 'm' },
                { key: 'ele', label: 'Elevation', unit: 'm' }
            ];

            const availableStreams = [];
            for (const config of streamConfigs) {
                if (sampleRow[config.key] !== undefined && sampleRow[config.key] !== null) {
                    // Check if we already have this type of stream
                    const existingType = availableStreams.find(s => s.label === config.label);
                    if (!existingType) {
                        availableStreams.push(config);
                    }
                }
            }

            if (availableStreams.length === 0) return;

            // Calculate stats for each stream
            const streamStats = [];
            for (const config of availableStreams) {
                const values = rows.map(r => parseFloat(r[config.key])).filter(v => !isNaN(v) && v > 0);
                if (values.length === 0) continue;

                const avg = values.reduce((a, b) => a + b, 0) / values.length;
                const max = Math.max(...values);
                const min = Math.min(...values);

                streamStats.push({
                    label: config.label,
                    unit: config.unit,
                    avg: avg.toFixed(config.key === 'altitude' || config.key === 'ele' ? 0 : 0),
                    max: max.toFixed(0),
                    min: min.toFixed(0)
                });
            }

            if (streamStats.length === 0) return;

            // Render streams
            let html = '<h4>Data Streams</h4><div class="streams-grid">';
            for (const stream of streamStats) {
                html += `
                    <div class="stream-card">
                        <div class="stream-label">${stream.label}</div>
                        <div class="stream-values">
                            <div class="stream-stat">
                                <span class="stream-stat-label">Avg</span>
                                <span class="stream-stat-value">${stream.avg} ${stream.unit}</span>
                            </div>
                            <div class="stream-stat">
                                <span class="stream-stat-label">Max</span>
                                <span class="stream-stat-value">${stream.max} ${stream.unit}</span>
                            </div>
                        </div>
                    </div>
                `;
            }
            html += '</div>';
            container.innerHTML = html;
        } catch (e) {
            console.warn('Failed to load data streams:', e);
        }
    },

    closeDetail() {
        document.getElementById('session-detail').classList.add('hidden');
        document.querySelectorAll('#sessions-tbody tr').forEach(r => r.classList.remove('selected'));
        this.selectedSession = null;

        // Clear session from URL
        URLState.update({ session: '' });

        // Clean up detail map instance
        if (this.detailMapInstance) {
            this.detailMapInstance.remove();
            this.detailMapInstance = null;
        }

        // Remove any "View on Map" button that was added
        document.querySelectorAll('.view-on-map-btn').forEach(btn => btn.remove());

        // Reset map container visibility for next session
        document.getElementById('detail-map').style.display = 'block';
    }
};

// ===== Full Session View Module =====
const FullSessionView = {
    map: null,
    currentAthlete: null,
    currentSession: null,
    pendingPhotoIndex: null,  // Photo index to open after photos load
    retryCount: 0,
    maxRetries: 10,

    show(athlete, datetime, photoIndex = null) {
        this.currentAthlete = athlete;
        this.currentSession = datetime;
        this.pendingPhotoIndex = photoIndex;

        // Find session data
        const sessions = MapView.sessionsByAthlete?.[athlete] || [];
        const session = sessions.find(s => s.datetime === datetime);

        if (!session) {
            // Data might not be loaded yet, retry with limit
            this.retryCount++;
            if (this.retryCount <= this.maxRetries) {
                console.log('Session data not loaded yet, retrying... (' + this.retryCount + '/' + this.maxRetries + ')');
                document.getElementById('full-session-name').textContent = 'Loading...';
                document.getElementById('full-session-meta').textContent = 'Please wait while data loads';
                setTimeout(() => this.show(athlete, datetime, this.pendingPhotoIndex), 500);
                return;
            } else {
                console.warn('Session not found after retries:', athlete, datetime);
                document.getElementById('full-session-name').textContent = 'Session Not Found';
                document.getElementById('full-session-meta').textContent = `Could not find session ${datetime} for ${athlete}`;
                this.retryCount = 0;
                return;
            }
        }

        // Reset retry count on success
        this.retryCount = 0;

        // Update header
        document.getElementById('full-session-name').textContent = session.name || 'Activity';
        const dateStr = this.formatDate(datetime);
        document.getElementById('full-session-meta').innerHTML =
            `${dateStr} &bull; ${session.type || 'Activity'} &bull; ${athlete}`;

        // Update share button with error handling and visual feedback
        const shareBtn = document.getElementById('full-session-share');
        shareBtn.onclick = async () => {
            const url = location.origin + location.pathname + '#/session/' + athlete + '/' + datetime;
            try {
                await navigator.clipboard.writeText(url);
                // Visual feedback - green checkmark
                shareBtn.classList.add('copied');
                shareBtn.title = 'Link copied!';
                setTimeout(() => {
                    shareBtn.classList.remove('copied');
                    shareBtn.title = 'Copy permalink';
                }, 2000);
            } catch (err) {
                // Fallback for browsers without clipboard API or insecure contexts
                console.warn('Clipboard API failed, using fallback:', err);
                // Create temporary input for copying
                const input = document.createElement('input');
                input.value = url;
                document.body.appendChild(input);
                input.select();
                try {
                    document.execCommand('copy');
                    shareBtn.classList.add('copied');
                    shareBtn.title = 'Link copied!';
                    setTimeout(() => {
                        shareBtn.classList.remove('copied');
                        shareBtn.title = 'Copy permalink';
                    }, 2000);
                } catch (e) {
                    // Show URL in alert as last resort
                    alert('Copy this link:\n' + url);
                }
                document.body.removeChild(input);
            }
        };

        // Update "View on Map" button
        const mapBtn = document.getElementById('full-session-map-btn');
        mapBtn.onclick = () => {
            // Navigate to map view centered on this session
            const lat = parseFloat(session.start_lat);
            const lng = parseFloat(session.start_lng);
            if (!isNaN(lat) && !isNaN(lng)) {
                location.hash = `#/map?z=14&lat=${lat}&lng=${lng}`;
            } else {
                location.hash = '#/map';
            }
        };

        // Load description from info.json
        this.loadDescription(athlete, datetime);

        // Render stats
        this.renderStats(session);

        // Load map
        this.loadMap(athlete, datetime);

        // Load streams (placeholder for Phase 8)
        this.loadStreams(athlete, datetime);

        // Load photos
        this.loadPhotos(athlete, datetime, session);

        // Load social
        this.loadSocial(athlete, datetime);

        // Load shared runs
        this.loadSharedRuns(athlete, datetime);
    },

    formatDate(datetime) {
        if (!datetime || datetime.length < 8) return '';
        const y = datetime.substring(0, 4);
        const m = datetime.substring(4, 6);
        const d = datetime.substring(6, 8);
        return `${y}-${m}-${d}`;
    },

    formatDuration(seconds) {
        if (!seconds) return '-';
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        if (h > 0) return `${h}h ${m}m`;
        return `${m}m`;
    },

    async loadDescription(athlete, datetime) {
        const container = document.getElementById('full-session-description');
        container.innerHTML = '';

        try {
            const response = await fetch(`athl=${athlete}/ses=${datetime}/info.json`);
            if (!response.ok) return;

            const info = await response.json();
            const description = info.description;

            if (description && description.trim()) {
                // Use SessionsView's linkifyText helper
                container.innerHTML = SessionsView.linkifyText(description);
            }
        } catch (e) {
            console.warn('Failed to load description:', e);
        }
    },

    renderStats(session) {
        const distance = parseFloat(session.distance_m) || 0;
        const duration = parseInt(session.moving_time_s) || 0;
        const elevation = parseFloat(session.elevation_gain_m) || 0;
        const avgHr = parseFloat(session.average_heartrate) || 0;
        const avgCadence = parseFloat(session.average_cadence) || 0;

        let html = `
            <div class="stat-card">
                <div class="stat-value">${(distance / 1000).toFixed(2)}</div>
                <div class="stat-label">km</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${this.formatDuration(duration)}</div>
                <div class="stat-label">Duration</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${elevation.toFixed(0)}</div>
                <div class="stat-label">m elevation</div>
            </div>
        `;

        if (avgHr > 0) {
            html += `
                <div class="stat-card">
                    <div class="stat-value">${avgHr.toFixed(0)}</div>
                    <div class="stat-label">avg HR</div>
                </div>
            `;
        }

        if (avgCadence > 0) {
            html += `
                <div class="stat-card">
                    <div class="stat-value">${avgCadence.toFixed(0)}</div>
                    <div class="stat-label">avg cadence</div>
                </div>
            `;
        }

        document.getElementById('full-session-stats').innerHTML = html;
    },

    async loadMap(athlete, datetime) {
        const container = document.getElementById('full-session-map-container');
        container.innerHTML = '';

        // Clean up previous map
        if (this.map) {
            this.map.remove();
            this.map = null;
        }

        // Create map
        this.map = L.map(container).setView([40, 0], 3);
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap'
        }).addTo(this.map);

        // Load track
        try {
            const response = await fetch(`athl=${athlete}/ses=${datetime}/tracking.parquet`);
            if (!response.ok) return;
            const buffer = await response.arrayBuffer();
            const data = await parquetReadObjects({ file: buffer });

            const coords = data
                .filter(row => row.lat && row.lng)
                .map(row => [row.lat, row.lng]);

            if (coords.length > 0) {
                const polyline = L.polyline(coords, {
                    color: MapView.typeColors[this.currentSession?.type] || '#fc4c02',
                    weight: 3
                }).addTo(this.map);
                this.map.fitBounds(polyline.getBounds(), { padding: [20, 20] });
            }
        } catch (e) {
            console.warn('Could not load track:', e);
        }
    },

    streamCharts: [],  // Track Chart.js instances for cleanup

    // Downsample data for performance (max 500 points for display)
    downsampleData(data, maxPoints = 500) {
        if (data.length <= maxPoints) return data;
        const step = Math.ceil(data.length / maxPoints);
        return data.filter((_, i) => i % step === 0);
    },

    async loadStreams(athlete, datetime) {
        const container = document.getElementById('full-session-streams');

        // Destroy existing charts
        this.streamCharts.forEach(chart => chart.destroy());
        this.streamCharts = [];

        try {
            const response = await fetch(`athl=${athlete}/ses=${datetime}/tracking.parquet`);
            if (!response.ok) {
                container.innerHTML = '';
                return;
            }
            const buffer = await response.arrayBuffer();
            const data = await parquetReadObjects({ file: buffer });

            if (!data || data.length === 0) {
                container.innerHTML = '';
                return;
            }

            // Check what streams are available
            const hasHr = data.some(r => r.heartrate);
            const hasCadence = data.some(r => r.cadence);
            const hasWatts = data.some(r => r.watts);
            const hasElevation = data.some(r => r.altitude);
            // hasSpeed available but not currently used in UI
            // const hasSpeed = data.some(r => r.velocity_smooth);

            if (!hasHr && !hasCadence && !hasWatts && !hasElevation) {
                container.innerHTML = '';
                return;
            }

            // Downsample for performance
            const sampled = this.downsampleData(data);

            // Check what X-axis options are available
            const hasDistance = sampled.some(r => r.distance);
            const hasTime = sampled.some(r => r.time !== undefined);

            // Store data for re-rendering when X-axis changes
            this.streamData = { sampled, hasElevation, hasHr, hasCadence, hasWatts, hasDistance, hasTime };

            // Build HTML with X-axis selector
            let html = '<div class="stream-header">';
            html += '<h3 class="full-session-section-title">Data Streams</h3>';
            if (hasDistance && hasTime) {
                html += `<select id="xaxis-selector" class="xaxis-select">
                    <option value="distance">Distance (km)</option>
                    <option value="time">Time (min)</option>
                </select>`;
            }
            html += '</div>';
            html += '<div class="stream-charts">';

            // Elevation chart (area fill, always first if available)
            if (hasElevation) {
                html += `
                    <div class="stream-chart-container elevation-chart">
                        <span class="stream-chart-label">Elevation</span>
                        <canvas id="elevation-chart" class="stream-chart-canvas"></canvas>
                    </div>
                `;
            }

            // Combined HR/Cadence/Power chart
            if (hasHr || hasCadence || hasWatts) {
                html += `
                    <div class="stream-chart-container">
                        <span class="stream-chart-label">Activity Data</span>
                        <canvas id="activity-chart" class="stream-chart-canvas"></canvas>
                    </div>
                `;
            }

            html += '</div>';
            container.innerHTML = html;

            // Set up X-axis selector change handler
            const xaxisSelector = document.getElementById('xaxis-selector');
            if (xaxisSelector) {
                xaxisSelector.addEventListener('change', () => this.renderStreamCharts());
            }

            // Render charts
            this.renderStreamCharts();

        } catch (e) {
            console.warn('Could not load streams:', e);
            container.innerHTML = '';
        }
    },

    xAxisMode: 'distance',  // Default mode

    renderStreamCharts() {
        if (!this.streamData) return;
        const { sampled, hasElevation, hasHr, hasCadence, hasWatts, hasDistance } = this.streamData;

        // Destroy existing charts
        this.streamCharts.forEach(chart => chart.destroy());
        this.streamCharts = [];

        // Determine X-axis mode
        const selector = document.getElementById('xaxis-selector');
        const useDistance = selector ? selector.value === 'distance' : hasDistance;

        // Calculate X-axis data
        const xData = sampled.map(r => {
            if (useDistance && r.distance) return Math.round(r.distance / 100) / 10;  // km, 1 decimal
            return Math.round((r.time || 0) / 60);  // minutes, whole numbers
        });
        const xLabel = useDistance ? 'Distance (km)' : 'Time (min)';

        // Create elevation chart
        if (hasElevation) {
            const elevData = sampled.map(r => r.altitude);
            const minElev = Math.min(...elevData.filter(e => e != null));
            const maxElev = Math.max(...elevData.filter(e => e != null));

            const elevChart = new Chart(document.getElementById('elevation-chart'), {
                type: 'line',
                data: {
                    labels: xData,
                    datasets: [{
                        label: 'Elevation',
                        data: elevData,
                        borderColor: '#888',
                        backgroundColor: 'rgba(100, 100, 100, 0.2)',
                        fill: true,
                        tension: 0.3,
                        borderWidth: 1,
                        pointRadius: 0,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: (items) => `${items[0].parsed.x.toFixed(1)} ${useDistance ? 'km' : 'min'}`,
                                label: (item) => `${item.parsed.y.toFixed(0)} m`
                            }
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            title: { display: false },
                            ticks: { font: { size: 10 }, maxTicksLimit: 8 }
                        },
                        y: {
                            display: true,
                            min: Math.floor(minElev * 0.95),
                            max: Math.ceil(maxElev * 1.05),
                            ticks: { font: { size: 10 } },
                            title: { display: true, text: 'm', font: { size: 10 } }
                        }
                    }
                }
            });
            this.streamCharts.push(elevChart);
        }

        // Create combined activity data chart
        if (hasHr || hasCadence || hasWatts) {
            const datasets = [];

            if (hasHr) {
                // Filter out initial 0 HR readings (common sensor artifact)
                const hrData = sampled.map((r, i) => {
                    // Skip first point if HR is 0 or very low (sensor warming up)
                    if (i === 0 && (!r.heartrate || r.heartrate < 30)) return null;
                    return r.heartrate || null;
                });
                datasets.push({
                    label: 'Heart Rate',
                    data: hrData,
                    borderColor: '#e63946',
                    backgroundColor: 'rgba(230, 57, 70, 0.1)',
                    fill: false,
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    yAxisID: 'yHr',
                    spanGaps: true  // Connect line across null gaps
                });
            }

            if (hasCadence) {
                datasets.push({
                    label: 'Cadence',
                    data: sampled.map(r => r.cadence),
                    borderColor: '#457b9d',
                    backgroundColor: 'rgba(69, 123, 157, 0.1)',
                    fill: false,
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    yAxisID: 'yCadence'
                });
            }

            if (hasWatts) {
                datasets.push({
                    label: 'Power',
                    data: sampled.map(r => r.watts),
                    borderColor: '#f4a261',
                    backgroundColor: 'rgba(244, 162, 97, 0.1)',
                    fill: false,
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    yAxisID: 'yPower'
                });
            }

            // Configure scales based on available data
            const scales = {
                x: {
                    display: true,
                    title: { display: true, text: xLabel, font: { size: 10 } },
                    ticks: { font: { size: 10 }, maxTicksLimit: 8 }
                }
            };

            if (hasHr) {
                scales.yHr = {
                    type: 'linear',
                    position: 'left',
                    display: true,
                    title: { display: true, text: 'BPM', font: { size: 10 }, color: '#e63946' },
                    ticks: { font: { size: 10 }, color: '#e63946' },
                    grid: { display: hasHr && !hasCadence && !hasWatts }
                };
            }

            if (hasCadence) {
                scales.yCadence = {
                    type: 'linear',
                    position: hasHr ? 'right' : 'left',
                    display: true,
                    title: { display: true, text: 'RPM', font: { size: 10 }, color: '#457b9d' },
                    ticks: { font: { size: 10 }, color: '#457b9d' },
                    grid: { display: !hasHr }
                };
            }

            if (hasWatts) {
                scales.yPower = {
                    type: 'linear',
                    position: 'right',
                    display: true,
                    title: { display: true, text: 'W', font: { size: 10 }, color: '#f4a261' },
                    ticks: { font: { size: 10 }, color: '#f4a261' },
                    grid: { display: false }
                };
            }

            const activityChart = new Chart(document.getElementById('activity-chart'), {
                type: 'line',
                data: {
                    labels: xData,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top',
                            labels: { font: { size: 11 }, usePointStyle: true, boxWidth: 6 }
                        },
                        tooltip: {
                            callbacks: {
                                title: (items) => `${items[0].parsed.x.toFixed(1)} ${useDistance ? 'km' : 'min'}`
                            }
                        }
                    },
                    scales: scales
                }
            });
            this.streamCharts.push(activityChart);
        }
    },

    sessionPhotos: [],  // Store photos for PhotoViewer

    async loadPhotos(athlete, datetime, session) {
        const container = document.getElementById('full-session-photos');
        const photoCount = parseInt(session?.photo_count) || 0;
        this.sessionPhotos = [];

        if (photoCount === 0) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = `
            <h3 class="full-session-section-title">Photos (${photoCount})</h3>
            <div class="photo-grid" id="full-session-photo-grid">Loading...</div>
        `;

        try {
            // Load photos from info.json (works without directory listing)
            const response = await fetch(`athl=${athlete}/ses=${datetime}/info.json`);
            if (!response.ok) {
                container.innerHTML = '';
                return;
            }

            const info = await response.json();
            const photos = info.photos || [];

            if (photos.length === 0) {
                container.innerHTML = '';
                return;
            }

            // Build photo data array for PhotoViewer
            this.sessionPhotos = photos.map(photo => {
                const urls = photo.urls || {};
                const thumbUrl = urls['600'] || urls['256'] || Object.values(urls)[0] || '';
                const fullUrl = urls['2048'] || urls['1024'] || urls['600'] || thumbUrl;

                // Build local path from created_at timestamp
                const createdAt = photo.created_at || '';
                let localPath = '';
                if (createdAt) {
                    const dt = createdAt.replace(/[-:]/g, '').replace(/\+.*$/, '').substring(0, 15);
                    localPath = `athl=${athlete}/ses=${datetime}/photos/${dt}.jpg`;
                }

                return {
                    src: localPath || thumbUrl,
                    fullUrl: localPath || fullUrl
                };
            }).filter(p => p.src);

            const grid = document.getElementById('full-session-photo-grid');
            grid.innerHTML = this.sessionPhotos.map((photo, index) => `
                <div class="photo-item">
                    <img src="${photo.src}"
                         data-index="${index}"
                         alt="Activity photo">
                </div>
            `).join('');

            // Add click handlers for PhotoViewer
            const self = this;
            grid.querySelectorAll('img').forEach(img => {
                img.style.cursor = 'pointer';
                img.addEventListener('click', () => {
                    const index = parseInt(img.dataset.index);
                    PhotoViewer.open(self.sessionPhotos, index, {
                        athlete: self.currentAthlete,
                        datetime: self.currentSession,
                        source: 'session'
                    });
                });
            });

            // Open PhotoViewer if URL had photo index parameter
            if (this.pendingPhotoIndex !== null && this.pendingPhotoIndex < this.sessionPhotos.length) {
                PhotoViewer.open(this.sessionPhotos, this.pendingPhotoIndex, {
                    athlete: this.currentAthlete,
                    datetime: this.currentSession,
                    source: 'session'
                });
                this.pendingPhotoIndex = null;
            }
        } catch (e) {
            console.warn('Failed to load photos:', e);
            container.innerHTML = '';
        }
    },

    loadSocial(athlete, datetime) {
        const container = document.getElementById('full-session-social');

        fetch(`athl=${athlete}/ses=${datetime}/info.json`)
            .then(response => response.json())
            .then(info => {
                const kudos = info.kudos || [];
                const comments = info.comments || [];

                if (kudos.length === 0 && comments.length === 0) {
                    container.innerHTML = '';
                    return;
                }

                let html = '<h3 class="full-session-section-title">Social</h3>';

                if (kudos.length > 0) {
                    html += `<div style="margin-bottom:16px;">
                        <strong>👍 ${kudos.length} kudos</strong>
                        <span style="color:#666;font-size:13px;margin-left:8px;">
                            ${kudos.slice(0, 5).map(k => k.firstname || 'Someone').join(', ')}
                            ${kudos.length > 5 ? ` and ${kudos.length - 5} more` : ''}
                        </span>
                    </div>`;
                }

                if (comments.length > 0) {
                    html += `<div>
                        <strong>💬 ${comments.length} comments</strong>
                        ${comments.map(c => `
                            <div style="margin-top:8px;padding:8px;background:#f5f5f5;border-radius:6px;">
                                <strong style="font-size:13px;">${c.athlete_firstname || 'Someone'}</strong>
                                <p style="margin:4px 0 0 0;font-size:14px;">${c.text || ''}</p>
                            </div>
                        `).join('')}
                    </div>`;
                }

                container.innerHTML = html;
            })
            .catch(() => { container.innerHTML = ''; });
    },

    loadSharedRuns(athlete, datetime) {
        const container = document.getElementById('full-session-shared');
        container.innerHTML = '';

        const sharedWith = [];
        for (const [athleteUsername, sessions] of Object.entries(MapView.sessionsByAthlete || {})) {
            if (athleteUsername === athlete) continue;
            const match = sessions.find(s => s.datetime === datetime);
            if (match) {
                sharedWith.push({ username: athleteUsername, session: match });
            }
        }

        if (sharedWith.length === 0) return;

        container.innerHTML = `
            <h3 class="full-session-section-title">Shared Activity</h3>
            <p style="color:#666;">
                Also recorded by:
                ${sharedWith.map(s => `
                    <a href="#/session/${s.username}/${datetime}"
                       style="color:#fc4c02;font-weight:600;">${s.username}</a>
                `).join(', ')}
            </p>
        `;
    }
};

// ===== Stats View Module =====
const StatsView = {
    sessions: [],
    filtered: [],
    typeColors: {
        'Run': '#FF5722',
        'Ride': '#2196F3',
        'Hike': '#4CAF50',
        'Walk': '#9C27B0',
        'Swim': '#00BCD4',
        'Other': '#607D8B'
    },
    monthlyChart: null,  // Chart.js instance
    typeChart: null,     // Chart.js instance

    init() {
        // Initialize filter bar for stats
        FilterBar.render('stats-filter-bar', {
            showSearch: true,
            showType: true,
            showDatePresets: true,
            showDates: true
        });
        FilterBar.init('stats-filter-bar');

        // Initialize session list panel for stats
        SessionListPanel.render('stats-session-list', {
            onSessionClick: (athlete, datetime) => {
                location.hash = `#/session/${athlete}/${datetime}`;
            }
        });

        // Subscribe to filter changes
        FilterState.onChange(() => this.calculate());

        // Listen for athlete changes
        document.getElementById('athlete-selector').addEventListener('change', () => {
            this.calculate();
        });
        // Chart click handlers are set up in renderMonthlyChart/renderTypeChart
    },

    handleMonthlyChartClick(month) {
        // Navigate to sessions view with month filter via URL
        const [year, monthNum] = [month.substring(0, 4), month.substring(4, 6)];
        const dateFrom = `${year}-${monthNum}-01`;
        const lastDay = new Date(parseInt(year), parseInt(monthNum), 0).getDate();
        const dateTo = `${year}-${monthNum}-${String(lastDay).padStart(2, '0')}`;

        // Build URL with date filter params
        const params = new URLSearchParams();
        params.set('from', dateFrom);
        params.set('to', dateTo);
        // Preserve current athlete
        const athlete = document.getElementById('athlete-selector')?.value;
        if (athlete) params.set('a', athlete);

        location.hash = `#/sessions?${params.toString()}`;
    },

    handleTypeChartClick(type) {
        // Navigate to sessions view with type filter via URL
        const params = new URLSearchParams();
        params.set('t', type);
        // Preserve current athlete
        const athlete = document.getElementById('athlete-selector')?.value;
        if (athlete) params.set('a', athlete);

        location.hash = `#/sessions?${params.toString()}`;
    },

    setSessions(sessions) {
        this.sessions = sessions;
        this.calculate();
    },

    calculate() {
        const currentAthlete = document.getElementById('athlete-selector').value;
        const filters = FilterState.get();

        // Use shared applyFilters function
        const filtered = applyFilters(this.sessions, filters, currentAthlete);
        this.filtered = filtered;

        // Update session list panel
        const sortedFiltered = [...filtered].sort((a, b) => (b.datetime || '').localeCompare(a.datetime || ''));
        SessionListPanel.setSessions(sortedFiltered);
        FilterBar.updateCount('stats-filter-bar', filtered.length, this.sessions.length);

        // Calculate totals
        const totals = {
            sessions: filtered.length,
            distance: filtered.reduce((sum, s) => sum + parseFloat(s.distance_m || 0), 0),
            time: filtered.reduce((sum, s) => sum + parseInt(s.moving_time_s || 0), 0),
            elevation: filtered.reduce((sum, s) => sum + parseFloat(s.elevation_gain_m || 0), 0)
        };

        // Group by month
        const byMonth = {};
        for (const s of filtered) {
            if (!s.datetime || s.datetime.length < 6) continue;
            const month = s.datetime.substring(0, 6);
            if (!byMonth[month]) byMonth[month] = { count: 0, distance: 0 };
            byMonth[month].count++;
            byMonth[month].distance += parseFloat(s.distance_m || 0);
        }

        // Group by type
        const byType = {};
        for (const s of filtered) {
            const type = s.type || 'Other';
            if (!byType[type]) byType[type] = { count: 0, distance: 0 };
            byType[type].count++;
            byType[type].distance += parseFloat(s.distance_m || 0);
        }

        this.renderSummary(totals);
        this.renderMonthlyChart(byMonth);
        this.renderTypeChart(byType);
        this.renderHeatmap();
        this.renderCalendarHeatmap();
    },

    formatDuration(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        if (h >= 24) {
            const d = Math.floor(h / 24);
            return `${d}d ${h % 24}h`;
        }
        return `${h}h ${m}m`;
    },

    renderSummary(totals) {
        document.getElementById('total-sessions').textContent = totals.sessions.toLocaleString();
        document.getElementById('total-distance').textContent = (totals.distance / 1000).toFixed(0) + ' km';
        document.getElementById('total-time').textContent = this.formatDuration(totals.time);
        document.getElementById('total-elevation').textContent = totals.elevation.toFixed(0) + ' m';
    },

    renderMonthlyChart(byMonth) {
        const canvas = document.getElementById('monthly-chart');
        const months = Object.keys(byMonth).sort();

        // Destroy existing chart if any
        if (this.monthlyChart) {
            this.monthlyChart.destroy();
            this.monthlyChart = null;
        }

        if (!canvas) return; // Canvas may have been removed

        // Remove any existing "no data" message
        const existingMsg = canvas.parentElement.querySelector('.no-data-message');
        if (existingMsg) existingMsg.remove();

        if (months.length === 0) {
            canvas.style.display = 'none';
            const msg = document.createElement('div');
            msg.className = 'no-data-message';
            msg.style.cssText = 'text-align:center;padding:100px 0;color:#999;';
            msg.textContent = 'No data available';
            canvas.parentElement.appendChild(msg);
            return;
        }

        canvas.style.display = 'block';

        const labels = months.map(m => m.substring(0, 4) + '-' + m.substring(4, 6));
        const data = months.map(m => byMonth[m].count);
        const monthKeys = months; // Store for click handler

        this.monthlyChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Sessions',
                    data: data,
                    backgroundColor: '#fc4c02',
                    borderRadius: 4,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        titleFont: { size: 13 },
                        bodyFont: { size: 12 },
                        padding: 10,
                        cornerRadius: 6,
                        callbacks: {
                            title: (items) => items[0].label,
                            label: (item) => `${item.raw} sessions`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                            font: { size: 10 }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: '#eee' },
                        ticks: { stepSize: 1 },
                        title: {
                            display: true,
                            text: 'Sessions',
                            font: { size: 12 }
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        this.handleMonthlyChartClick(monthKeys[index]);
                    }
                },
                onHover: (event, elements) => {
                    canvas.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                }
            }
        });
    },

    renderTypeChart(byType) {
        const canvas = document.getElementById('type-chart');
        const types = Object.keys(byType).sort((a, b) => byType[b].count - byType[a].count);

        // Destroy existing chart if any
        if (this.typeChart) {
            this.typeChart.destroy();
            this.typeChart = null;
        }

        if (!canvas) return; // Canvas may have been removed

        // Remove any existing "no data" message
        const existingMsg = canvas.parentElement.querySelector('.no-data-message');
        if (existingMsg) existingMsg.remove();

        if (types.length === 0) {
            canvas.style.display = 'none';
            const msg = document.createElement('div');
            msg.className = 'no-data-message';
            msg.style.cssText = 'text-align:center;padding:100px 0;color:#999;';
            msg.textContent = 'No data available';
            canvas.parentElement.appendChild(msg);
            return;
        }

        canvas.style.display = 'block';

        const data = types.map(t => byType[t].count);
        const colors = types.map(t => this.typeColors[t] || '#607D8B');
        const typeKeys = types; // Store for click handler

        this.typeChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: types,
                datasets: [{
                    label: 'Sessions',
                    data: data,
                    backgroundColor: colors,
                    borderRadius: 4,
                    borderSkipped: false
                }]
            },
            options: {
                indexAxis: 'y',  // Horizontal bar chart
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        titleFont: { size: 13 },
                        bodyFont: { size: 12 },
                        padding: 10,
                        cornerRadius: 6,
                        callbacks: {
                            title: (items) => items[0].label,
                            label: (item) => `${item.raw} sessions`
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: { color: '#eee' },
                        ticks: { stepSize: 1 }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { font: { size: 12 } }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        this.handleTypeChartClick(typeKeys[index]);
                    }
                },
                onHover: (event, elements) => {
                    canvas.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                }
            }
        });
    },

    calculateHeatmapData(sessions) {
        // Initialize 7x24 grid (days × hours)
        // Index 0 = Sunday, 6 = Saturday (JavaScript Date convention)
        const grid = Array(7).fill(null).map(() => Array(24).fill(0));

        for (const session of sessions) {
            // Use datetime_local for correct local time, fall back to datetime (UTC)
            const datetime = session.datetime_local || session.datetime;
            if (!datetime || datetime.length < 13) continue;

            const year = parseInt(datetime.substring(0, 4));
            const month = parseInt(datetime.substring(4, 6)) - 1;  // JS months are 0-indexed
            const day = parseInt(datetime.substring(6, 8));
            // Hour starts at position 9 (after separator)
            const hour = parseInt(datetime.substring(9, 11));

            if (isNaN(year) || isNaN(month) || isNaN(day) || isNaN(hour)) continue;
            if (hour < 0 || hour > 23) continue;

            const date = new Date(year, month, day);
            const dayOfWeek = date.getDay();  // 0=Sunday, 6=Saturday

            grid[dayOfWeek][hour]++;
        }

        return grid;
    },

    getHeatmapColor(intensity) {
        if (intensity === 0) return '#ebedf0';  // Light gray for empty
        // Interpolate from light orange to Strava orange (#fc4c02)
        // Light: rgb(254, 235, 200) -> Dark: rgb(252, 76, 2)
        const r = Math.round(254 - (254 - 252) * intensity);
        const g = Math.round(235 - (235 - 76) * intensity);
        const b = Math.round(200 - (200 - 2) * intensity);
        return `rgb(${r}, ${g}, ${b})`;
    },

    // Day labels used by both heatmaps (Monday first)
    dayLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    // Map display index to JS day index (0=Sun in JS)
    dayIndexMap: [1, 2, 3, 4, 5, 6, 0],

    /**
     * Render a heatmap grid table
     * @param {Object} config
     * @param {string} config.wrapperId - ID of wrapper element
     * @param {string} config.legendId - ID of legend element (for min/max values)
     * @param {Array} config.columns - Column definitions [{label, showLabel, colspan?, clickData?}]
     * @param {Function} config.getCellData - (dayIdx, colIdx) => {count, tooltip, clickData?, isEmpty?}
     * @param {number} config.maxCount - Maximum count for color scaling
     * @param {Function} config.onCellClick - Optional click handler (clickData) => void
     * @param {Function} config.onHeaderClick - Optional header click handler (clickData) => void
     * @param {Function} config.getFooterData - Optional (colIdx) => {count, tooltip, clickData?} for footer row
     * @param {string} config.footerLabel - Optional label for footer row (e.g., "Week")
     */
    renderHeatmapGrid(config) {
        const wrapper = document.getElementById(config.wrapperId);
        if (!wrapper) return;

        const { columns, getCellData, maxCount, onCellClick, onHeaderClick, getFooterData, footerLabel } = config;

        // Build table HTML
        let html = '<table class="heatmap-grid-table"><thead><tr><th></th>';

        // Column headers - skip columns spanned by previous colspan
        for (const col of columns) {
            // Skip columns that are covered by a previous colspan
            if (col.spannedBy !== undefined) continue;

            const colspanAttr = col.colspan ? ` colspan="${col.colspan}"` : '';
            const clickClass = col.clickData ? ' heatmap-header-clickable' : '';
            const clickAttr = col.clickData ? ` data-click='${JSON.stringify(col.clickData)}'` : '';
            const titleAttr = col.title ? ` title="${col.title}"` : '';

            if (col.showLabel) {
                html += `<th class="heatmap-col-label${clickClass}"${colspanAttr}${clickAttr}${titleAttr}>${col.label}</th>`;
            } else {
                html += `<th${colspanAttr}></th>`;
            }
        }
        html += '</tr></thead><tbody>';

        // Build rows (one per day of week) - render ALL columns
        for (let dayIdx = 0; dayIdx < 7; dayIdx++) {
            html += `<tr><td class="heatmap-day-label">${this.dayLabels[dayIdx]}</td>`;

            for (let colIdx = 0; colIdx < columns.length; colIdx++) {
                const cellData = getCellData(dayIdx, colIdx);
                const intensity = maxCount > 0 ? cellData.count / maxCount : 0;
                const color = cellData.isEmpty ? '#f6f8fa' : this.getHeatmapColor(intensity);
                const clickClass = cellData.clickData ? ' heatmap-cell-clickable' : '';
                const clickAttr = cellData.clickData ? ` data-click='${JSON.stringify(cellData.clickData)}'` : '';
                const emptyClass = cellData.isEmpty ? ' heatmap-cell-empty' : '';

                html += `<td class="heatmap-cell${clickClass}${emptyClass}" style="background:${color}" ` +
                        `title="${cellData.tooltip}"${clickAttr}></td>`;
            }
            html += '</tr>';
        }

        // Optional footer row (e.g., week totals)
        if (getFooterData) {
            html += `<tr class="heatmap-footer-row"><td class="heatmap-day-label">${footerLabel || ''}</td>`;
            for (let colIdx = 0; colIdx < columns.length; colIdx++) {
                const footerData = getFooterData(colIdx);
                const intensity = maxCount > 0 ? footerData.count / maxCount : 0;
                const color = footerData.isEmpty ? '#f6f8fa' : this.getHeatmapColor(intensity);
                const clickClass = footerData.clickData ? ' heatmap-cell-clickable' : '';
                const clickAttr = footerData.clickData ? ` data-click='${JSON.stringify(footerData.clickData)}'` : '';
                const emptyClass = footerData.isEmpty ? ' heatmap-cell-empty' : '';

                html += `<td class="heatmap-cell heatmap-footer-cell${clickClass}${emptyClass}" style="background:${color}" ` +
                        `title="${footerData.tooltip}"${clickAttr}></td>`;
            }
            html += '</tr>';
        }

        html += '</tbody></table>';

        wrapper.innerHTML = html;

        // Update legend with actual values
        if (config.legendId) {
            const legend = document.getElementById(config.legendId);
            if (legend) {
                const minSpan = legend.querySelector('.legend-min');
                const maxSpan = legend.querySelector('.legend-max');
                if (minSpan) minSpan.textContent = '0';
                if (maxSpan) maxSpan.textContent = String(maxCount);
            }
        }

        // Add click handlers
        if (onCellClick) {
            wrapper.querySelectorAll('.heatmap-cell-clickable').forEach(cell => {
                cell.addEventListener('click', () => {
                    const clickData = JSON.parse(cell.dataset.click);
                    onCellClick(clickData);
                });
            });
        }

        if (onHeaderClick) {
            wrapper.querySelectorAll('.heatmap-header-clickable').forEach(th => {
                th.addEventListener('click', () => {
                    const clickData = JSON.parse(th.dataset.click);
                    onHeaderClick(clickData);
                });
            });
        }
    },

    renderHeatmap() {
        const data = this.calculateHeatmapData(this.filtered);

        // Calculate hourly totals for footer row
        const hourlyTotals = [];
        for (let hour = 0; hour < 24; hour++) {
            let total = 0;
            for (let day = 0; day < 7; day++) {
                total += data[day][hour];
            }
            hourlyTotals.push(total);
        }

        // Max includes both individual cells and totals
        const cellMax = Math.max(...data.flat());
        const totalMax = Math.max(...hourlyTotals);
        const maxCount = Math.max(cellMax, totalMax);

        // Build column definitions for hours 0-23
        const columns = [];
        for (let hour = 0; hour < 24; hour++) {
            columns.push({
                label: String(hour),
                showLabel: hour % 3 === 0  // Show label every 3 hours
            });
        }

        this.renderHeatmapGrid({
            wrapperId: 'heatmap-wrapper',
            legendId: 'heatmap-legend',
            columns,
            maxCount,
            footerLabel: 'Total',
            getCellData: (dayIdx, colIdx) => {
                const jsDay = this.dayIndexMap[dayIdx];
                const count = data[jsDay][colIdx];
                return {
                    count,
                    tooltip: `${this.dayLabels[dayIdx]} ${colIdx}:00 - ${count} ${count === 1 ? 'activity' : 'activities'}`
                };
            },
            getFooterData: (colIdx) => {
                const total = hourlyTotals[colIdx];
                return {
                    count: total,
                    tooltip: `${colIdx}:00 total: ${total} ${total === 1 ? 'activity' : 'activities'}`
                };
            }
        });
    },

    calculateCalendarHeatmapData(sessions) {
        // Build a map of date strings to activity counts
        const dateMap = {};

        for (const session of sessions) {
            const datetime = session.datetime;
            if (!datetime || datetime.length < 8) continue;

            // Extract YYYY-MM-DD
            const dateKey = `${datetime.substring(0, 4)}-${datetime.substring(4, 6)}-${datetime.substring(6, 8)}`;
            dateMap[dateKey] = (dateMap[dateKey] || 0) + 1;
        }

        return dateMap;
    },

    getWeekStart(date) {
        // Get Monday of the week containing this date
        const d = new Date(date);
        const day = d.getDay();
        const diff = d.getDate() - day + (day === 0 ? -6 : 1);  // Adjust for Sunday
        return new Date(d.setDate(diff));
    },

    formatDateKey(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    },

    handleWeekClick(weekStart) {
        // Navigate to sessions view filtered to this week
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekEnd.getDate() + 6);

        const params = new URLSearchParams();
        params.set('from', this.formatDateKey(weekStart));
        params.set('to', this.formatDateKey(weekEnd));

        // Preserve current athlete
        const athlete = document.getElementById('athlete-selector')?.value;
        if (athlete) params.set('a', athlete);

        location.hash = `#/sessions?${params.toString()}`;
    },

    parseLocalDate(dateStr) {
        // Parse "YYYY-MM-DD" as local date (not UTC)
        const [year, month, day] = dateStr.split('-').map(Number);
        return new Date(year, month - 1, day);
    },

    renderCalendarHeatmap() {
        const wrapper = document.getElementById('calendar-heatmap-wrapper');
        if (!wrapper) return;

        const data = this.calculateCalendarHeatmapData(this.filtered);

        // Determine date range from filtered sessions
        const dates = Object.keys(data).sort();
        if (dates.length === 0) {
            wrapper.innerHTML = '<div style="text-align:center;padding:20px;color:#999;">No activities in selected period</div>';
            return;
        }

        // Find range: from first activity's week start to last activity's date
        const firstDate = this.parseLocalDate(dates[0]);
        const lastDate = this.parseLocalDate(dates[dates.length - 1]);
        const startWeek = this.getWeekStart(firstDate);

        // Calculate number of weeks
        const msPerWeek = 7 * 24 * 60 * 60 * 1000;
        const endWeek = this.getWeekStart(lastDate);
        const numWeeks = Math.ceil((endWeek - startWeek) / msPerWeek) + 1;

        // Calculate week totals for footer row (needed for maxCount calculation)
        const weekTotals = [];
        for (let week = 0; week < numWeeks; week++) {
            const weekStartDate = new Date(startWeek);
            weekStartDate.setDate(weekStartDate.getDate() + week * 7);
            let total = 0;
            let hasAnyInRange = false;

            for (let day = 0; day < 7; day++) {
                const cellDate = new Date(weekStartDate);
                cellDate.setDate(cellDate.getDate() + day);
                const dateKey = this.formatDateKey(cellDate);
                const inRange = cellDate >= firstDate && cellDate <= lastDate;
                if (inRange) {
                    hasAnyInRange = true;
                    total += data[dateKey] || 0;
                }
            }
            weekTotals.push({ total, hasAnyInRange, weekStartDate: this.formatDateKey(weekStartDate) });
        }

        // Calculate max for color scaling (includes week totals)
        const cellMax = Math.max(...Object.values(data));
        const weekMax = Math.max(...weekTotals.map(w => w.total));
        const maxCount = Math.max(cellMax, weekMax);

        // Month names for labels
        const monthNames = [
            'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
        ];

        // Build columns array (one per week, with month headers)
        const columns = [];
        let currentMonth = -1;

        for (let week = 0; week < numWeeks; week++) {
            const weekStartDate = new Date(startWeek);
            weekStartDate.setDate(weekStartDate.getDate() + week * 7);
            const weekMonth = weekStartDate.getMonth();
            const year = weekStartDate.getFullYear();

            // Check if this week starts a new month
            const isNewMonth = weekMonth !== currentMonth;
            if (isNewMonth) {
                currentMonth = weekMonth;
            }

            // Calculate colspan for month label (how many weeks in this month)
            let colspan = 1;
            const showLabel = isNewMonth;
            if (isNewMonth) {
                // Count how many weeks until next month change
                for (let w = week + 1; w < numWeeks; w++) {
                    const checkDate = new Date(startWeek);
                    checkDate.setDate(checkDate.getDate() + w * 7);
                    if (checkDate.getMonth() !== weekMonth) break;
                    colspan++;
                }
            }

            // Calculate month date range for click handler
            const monthStart = `${year}-${String(weekMonth + 1).padStart(2, '0')}-01`;
            const lastDay = new Date(year, weekMonth + 1, 0).getDate();
            const monthEnd = `${year}-${String(weekMonth + 1).padStart(2, '0')}-${lastDay}`;

            columns.push({
                label: monthNames[weekMonth],
                showLabel,
                colspan: showLabel ? colspan : undefined,
                spannedBy: !showLabel ? week - 1 : undefined,
                title: showLabel ? `Filter to ${monthNames[weekMonth]} ${year}` : undefined,
                clickData: showLabel ? { monthStart, monthEnd } : undefined,
                weekIndex: week,
                weekStartDate: this.formatDateKey(weekStartDate)
            });
        }

        // Store for getCellData access
        const calendarStartWeek = startWeek;

        this.renderHeatmapGrid({
            wrapperId: 'calendar-heatmap-wrapper',
            legendId: 'calendar-heatmap-legend',
            columns,
            maxCount,
            footerLabel: 'Week',
            getCellData: (dayIdx, colIdx) => {
                const col = columns[colIdx];
                const weekStartDate = new Date(calendarStartWeek);
                weekStartDate.setDate(weekStartDate.getDate() + col.weekIndex * 7);

                const cellDate = new Date(weekStartDate);
                cellDate.setDate(cellDate.getDate() + dayIdx);

                const dateKey = this.formatDateKey(cellDate);
                const count = data[dateKey] || 0;

                // Check if within data range
                const inRange = cellDate >= firstDate && cellDate <= lastDate;

                return {
                    count,
                    isEmpty: !inRange,
                    tooltip: inRange
                        ? `${this.dayLabels[dayIdx]}, ${dateKey}: ${count} ${count === 1 ? 'activity' : 'activities'}`
                        : '',
                    // Click on individual date, not week
                    clickData: inRange && count > 0 ? { date: dateKey } : undefined
                };
            },
            getFooterData: (colIdx) => {
                const weekData = weekTotals[colIdx];
                const weekEnd = new Date(this.parseLocalDate(weekData.weekStartDate));
                weekEnd.setDate(weekEnd.getDate() + 6);
                const weekEndStr = this.formatDateKey(weekEnd);

                return {
                    count: weekData.total,
                    isEmpty: !weekData.hasAnyInRange,
                    tooltip: weekData.hasAnyInRange
                        ? `Week ${weekData.weekStartDate} to ${weekEndStr}: ${weekData.total} ${weekData.total === 1 ? 'activity' : 'activities'}`
                        : '',
                    clickData: weekData.hasAnyInRange && weekData.total > 0
                        ? { weekStart: weekData.weekStartDate }
                        : undefined
                };
            },
            onCellClick: (clickData) => {
                if (clickData.date) {
                    // Single date click
                    this.handleDateClick(clickData.date);
                } else if (clickData.weekStart) {
                    // Week total click
                    const weekStart = this.parseLocalDate(clickData.weekStart);
                    this.handleWeekClick(weekStart);
                }
            },
            onHeaderClick: (clickData) => {
                this.handleMonthClick(clickData.monthStart, clickData.monthEnd);
            }
        });
    },

    handleDateClick(dateStr) {
        // Navigate to sessions view filtered to this specific date
        const params = new URLSearchParams();
        params.set('from', dateStr);
        params.set('to', dateStr);

        // Preserve current athlete
        const athlete = document.getElementById('athlete-selector')?.value;
        if (athlete) params.set('a', athlete);

        location.hash = `#/sessions?${params.toString()}`;
    },

    handleMonthClick(monthStart, monthEnd) {
        // Navigate to sessions view filtered to this month
        const params = new URLSearchParams();
        params.set('from', monthStart);
        params.set('to', monthEnd);

        // Preserve current athlete
        const athlete = document.getElementById('athlete-selector')?.value;
        if (athlete) params.set('a', athlete);

        location.hash = `#/sessions?${params.toString()}`;
    }
};

// ===== Initialize App =====
// Set up wrapper BEFORE MapView.init() since init() calls loadSessions()
const originalLoadSessions = MapView.loadSessions.bind(MapView);
MapView.loadSessions = async function() {
    await originalLoadSessions();
    // Pass full session data to views
    SessionsView.setSessions(this.allSessions);
    StatsView.setSessions(this.allSessions);

    // Populate filter bar types for all views
    FilterBar.populateTypes('map-filter-bar', this.allSessions);
    FilterBar.populateTypes('sessions-filter-bar', this.allSessions);
    FilterBar.populateTypes('stats-filter-bar', this.allSessions);

    // Sync initial filter state from URL
    FilterState.syncFromURL();
    FilterBar.syncFromState('map-filter-bar');
    FilterBar.syncFromState('sessions-filter-bar');
    FilterBar.syncFromState('stats-filter-bar');

    // Apply initial filters
    MapView.applyFiltersAndUpdateUI();

    // Hide loading overlay
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.classList.add('hidden');
        // Remove from DOM after animation
        setTimeout(() => overlay.remove(), 300);
    }
};

Router.init();
PhotoViewer.init();
MapView.init();
SessionsView.init();
StatsView.init();
// Export to window for onclick handlers in popups
window.MapView = MapView;
window.PhotoViewer = PhotoViewer;
