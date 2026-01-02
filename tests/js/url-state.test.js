/**
 * Tests for URL state management.
 *
 * These tests verify that map-specific URL parameters (zoom, lat, lng, track, popup, viewportFilter)
 * are only included in URLs when the view is 'map', preventing parameter leakage to other views.
 */

// URLState.encode logic extracted from map-browser.js
const URLStateEncode = (state) => {
    const params = new URLSearchParams();
    // Common params for all views
    if (state.athlete) params.set('a', state.athlete);
    if (state.session) params.set('s', state.session);
    if (state.search) params.set('q', state.search);
    if (state.type) params.set('t', state.type);
    if (state.dateFrom) params.set('from', state.dateFrom);
    if (state.dateTo) params.set('to', state.dateTo);

    // Map-specific params - only include for map view
    if (state.view === 'map') {
        if (state.zoom) params.set('z', state.zoom);
        if (state.lat) params.set('lat', state.lat.toFixed(4));
        if (state.lng) params.set('lng', state.lng.toFixed(4));
        if (state.track) params.set('track', state.track);
        if (state.popup) params.set('popup', state.popup);
        if (state.viewportFilter) params.set('vp', '1');
    }

    const queryStr = params.toString();
    return '#/' + state.view + (queryStr ? '?' + queryStr : '');
};

describe('URLState.encode', () => {
    describe('map view includes map-specific params', () => {
        test('includes zoom, lat, lng when view is map', () => {
            const state = {
                view: 'map',
                zoom: 14,
                lat: 39.1234,
                lng: -77.5678
            };

            const result = URLStateEncode(state);

            expect(result).toContain('z=14');
            expect(result).toContain('lat=39.1234');
            expect(result).toContain('lng=-77.5678');
        });

        test('includes track param when view is map', () => {
            const state = {
                view: 'map',
                track: 'athlete1/20251230T120000'
            };

            const result = URLStateEncode(state);

            expect(result).toContain('track=athlete1%2F20251230T120000');
        });

        test('includes popup param when view is map', () => {
            const state = {
                view: 'map',
                popup: 'athlete1/20251230T120000/2'
            };

            const result = URLStateEncode(state);

            expect(result).toContain('popup=athlete1%2F20251230T120000%2F2');
        });

        test('includes viewportFilter (vp=1) when view is map', () => {
            const state = {
                view: 'map',
                viewportFilter: true
            };

            const result = URLStateEncode(state);

            expect(result).toContain('vp=1');
        });
    });

    describe('non-map views exclude map-specific params', () => {
        test('sessions view excludes zoom, lat, lng', () => {
            const state = {
                view: 'sessions',
                zoom: 19,
                lat: 18.6043,
                lng: -2.2845
            };

            const result = URLStateEncode(state);

            expect(result).toBe('#/sessions');
            expect(result).not.toContain('z=');
            expect(result).not.toContain('lat=');
            expect(result).not.toContain('lng=');
        });

        test('stats view excludes zoom, lat, lng', () => {
            const state = {
                view: 'stats',
                zoom: 19,
                lat: 18.6043,
                lng: -2.2845
            };

            const result = URLStateEncode(state);

            expect(result).toBe('#/stats');
            expect(result).not.toContain('z=');
            expect(result).not.toContain('lat=');
            expect(result).not.toContain('lng=');
        });

        test('sessions view excludes track param', () => {
            const state = {
                view: 'sessions',
                track: 'athlete1/20251230T120000'
            };

            const result = URLStateEncode(state);

            expect(result).not.toContain('track=');
        });

        test('sessions view excludes popup param', () => {
            const state = {
                view: 'sessions',
                popup: 'athlete1/20251230T120000/2'
            };

            const result = URLStateEncode(state);

            expect(result).not.toContain('popup=');
        });

        test('sessions view excludes viewportFilter', () => {
            const state = {
                view: 'sessions',
                viewportFilter: true
            };

            const result = URLStateEncode(state);

            expect(result).not.toContain('vp=');
        });
    });

    describe('common params are preserved across all views', () => {
        test('preserves athlete filter in sessions view', () => {
            const state = {
                view: 'sessions',
                athlete: 'john_doe'
            };

            const result = URLStateEncode(state);

            expect(result).toContain('a=john_doe');
        });

        test('preserves search filter in sessions view', () => {
            const state = {
                view: 'sessions',
                search: 'morning run'
            };

            const result = URLStateEncode(state);

            expect(result).toContain('q=morning+run');
        });

        test('preserves type filter in stats view', () => {
            const state = {
                view: 'stats',
                type: 'Run'
            };

            const result = URLStateEncode(state);

            expect(result).toContain('t=Run');
        });

        test('preserves date range in map view', () => {
            const state = {
                view: 'map',
                dateFrom: '2025-01-01',
                dateTo: '2025-12-31'
            };

            const result = URLStateEncode(state);

            expect(result).toContain('from=2025-01-01');
            expect(result).toContain('to=2025-12-31');
        });

        test('preserves all filters when switching from map to sessions', () => {
            // Simulate state when on map view
            const mapState = {
                view: 'map',
                athlete: 'john_doe',
                search: 'park',
                type: 'Run',
                dateFrom: '2025-01-01',
                dateTo: '2025-12-31',
                zoom: 14,
                lat: 39.1234,
                lng: -77.5678
            };

            // Same state but view changed to sessions
            const sessionsState = { ...mapState, view: 'sessions' };

            const mapResult = URLStateEncode(mapState);
            const sessionsResult = URLStateEncode(sessionsState);

            // Map view should have all params
            expect(mapResult).toContain('z=14');
            expect(mapResult).toContain('lat=');
            expect(mapResult).toContain('a=john_doe');
            expect(mapResult).toContain('q=park');

            // Sessions view should have common params but not map params
            expect(sessionsResult).toContain('a=john_doe');
            expect(sessionsResult).toContain('q=park');
            expect(sessionsResult).toContain('t=Run');
            expect(sessionsResult).not.toContain('z=14');
            expect(sessionsResult).not.toContain('lat=');
        });
    });

    describe('edge cases', () => {
        test('handles empty state', () => {
            const state = { view: 'map' };

            const result = URLStateEncode(state);

            expect(result).toBe('#/map');
        });

        test('handles null/undefined values', () => {
            const state = {
                view: 'map',
                zoom: null,
                lat: undefined,
                lng: null
            };

            const result = URLStateEncode(state);

            expect(result).toBe('#/map');
            expect(result).not.toContain('z=');
            expect(result).not.toContain('lat=');
        });

        test('handles zoom level 0', () => {
            const state = {
                view: 'map',
                zoom: 0,
                lat: 0.0,
                lng: 0.0
            };

            const result = URLStateEncode(state);

            // zoom 0 is falsy, so not included (world view)
            expect(result).not.toContain('z=0');
        });

        test('viewportFilter false is not included', () => {
            const state = {
                view: 'map',
                viewportFilter: false
            };

            const result = URLStateEncode(state);

            expect(result).not.toContain('vp=');
        });
    });
});

describe('URL state navigation scenarios', () => {
    // These tests simulate the bug scenario where z=19 appeared after view switching

    test('scenario: reload sessions page then navigate to map', () => {
        // Step 1: User is on sessions page (after reload, map has some position from fitBounds)
        // The map's moveend would try to update state
        const stateOnSessions = {
            view: 'sessions',
            zoom: 3,
            lat: 20.0,
            lng: 10.0  // Non-zero to be truthy
        };

        // Sessions URL should not include map params
        const sessionsUrl = URLStateEncode(stateOnSessions);
        expect(sessionsUrl).toBe('#/sessions');

        // Step 2: User clicks Map tab, view changes to map
        // Same state but view is now map
        const stateOnMap = { ...stateOnSessions, view: 'map' };

        // Map URL should now include map params
        const mapUrl = URLStateEncode(stateOnMap);
        expect(mapUrl).toContain('z=3');
        expect(mapUrl).toContain('lat=20.0000');
        expect(mapUrl).toContain('lng=10.0000');
    });

    test('scenario: high zoom (z=19) should not leak to sessions/stats', () => {
        // Simulate fitBounds zooming to max when single point
        const stateWithHighZoom = {
            view: 'sessions',
            zoom: 19,
            lat: 18.6043,
            lng: -2.2845
        };

        const url = URLStateEncode(stateWithHighZoom);

        // URL should not contain high zoom
        expect(url).toBe('#/sessions');
        expect(url).not.toContain('19');
    });
});
