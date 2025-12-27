/**
 * Tests for viewport filter logic.
 *
 * These tests verify the viewport filtering behavior used in the map view's
 * "filter to map view" feature.
 */

describe('viewport filter logic', () => {
    // Mock bounds object that mimics Leaflet's LatLngBounds
    const createBounds = (south, west, north, east) => ({
        contains: ([lat, lng]) => {
            return lat >= south && lat <= north && lng >= west && lng <= east;
        }
    });

    // Filter function extracted from applyFiltersAndUpdateUI
    const filterByViewport = (sessions, bounds) => {
        return sessions.filter(s => {
            const lat = parseFloat(s.start_lat);
            const lng = parseFloat(s.start_lng);
            return !isNaN(lat) && !isNaN(lng) && bounds.contains([lat, lng]);
        });
    };

    test('filters sessions within bounds', () => {
        const bounds = createBounds(38, -78, 40, -76);
        const sessions = [
            { start_lat: '39.0', start_lng: '-77.0', name: 'Inside' },
            { start_lat: '41.0', start_lng: '-77.0', name: 'North of bounds' },
            { start_lat: '37.0', start_lng: '-77.0', name: 'South of bounds' }
        ];

        const result = filterByViewport(sessions, bounds);

        expect(result.length).toBe(1);
        expect(result[0].name).toBe('Inside');
    });

    test('handles sessions with missing lat/lng', () => {
        const bounds = createBounds(38, -78, 40, -76);
        const sessions = [
            { start_lat: '39.0', start_lng: '-77.0', name: 'Has coords' },
            { start_lat: '', start_lng: '', name: 'Empty coords' },
            { name: 'No coords' }
        ];

        const result = filterByViewport(sessions, bounds);

        expect(result.length).toBe(1);
        expect(result[0].name).toBe('Has coords');
    });

    test('handles sessions with invalid lat/lng values', () => {
        const bounds = createBounds(38, -78, 40, -76);
        const sessions = [
            { start_lat: '39.0', start_lng: '-77.0', name: 'Valid' },
            { start_lat: 'invalid', start_lng: '-77.0', name: 'Invalid lat' },
            { start_lat: '39.0', start_lng: 'invalid', name: 'Invalid lng' },
            { start_lat: 'NaN', start_lng: 'NaN', name: 'NaN values' }
        ];

        const result = filterByViewport(sessions, bounds);

        expect(result.length).toBe(1);
        expect(result[0].name).toBe('Valid');
    });

    test('includes sessions exactly on bounds edge', () => {
        const bounds = createBounds(38, -78, 40, -76);
        const sessions = [
            { start_lat: '38.0', start_lng: '-78.0', name: 'SW corner' },
            { start_lat: '40.0', start_lng: '-76.0', name: 'NE corner' },
            { start_lat: '39.0', start_lng: '-78.0', name: 'West edge' },
            { start_lat: '40.0', start_lng: '-77.0', name: 'North edge' }
        ];

        const result = filterByViewport(sessions, bounds);

        expect(result.length).toBe(4);
    });

    test('returns empty array when no sessions in bounds', () => {
        const bounds = createBounds(38, -78, 40, -76);
        const sessions = [
            { start_lat: '50.0', start_lng: '-77.0', name: 'Far north' },
            { start_lat: '30.0', start_lng: '-77.0', name: 'Far south' }
        ];

        const result = filterByViewport(sessions, bounds);

        expect(result.length).toBe(0);
    });

    test('returns all sessions when all are in bounds', () => {
        const bounds = createBounds(38, -78, 40, -76);
        const sessions = [
            { start_lat: '39.0', start_lng: '-77.0', name: 'Session 1' },
            { start_lat: '38.5', start_lng: '-77.5', name: 'Session 2' },
            { start_lat: '39.5', start_lng: '-76.5', name: 'Session 3' }
        ];

        const result = filterByViewport(sessions, bounds);

        expect(result.length).toBe(3);
    });

    test('handles empty sessions array', () => {
        const bounds = createBounds(38, -78, 40, -76);
        const sessions = [];

        const result = filterByViewport(sessions, bounds);

        expect(result.length).toBe(0);
    });

    test('handles string coordinates with whitespace', () => {
        const bounds = createBounds(38, -78, 40, -76);
        const sessions = [
            { start_lat: ' 39.0 ', start_lng: ' -77.0 ', name: 'Whitespace coords' }
        ];

        const result = filterByViewport(sessions, bounds);

        // parseFloat handles leading/trailing whitespace
        expect(result.length).toBe(1);
    });
});
