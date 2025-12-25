/**
 * Tests for date utility functions.
 *
 * These tests verify the date expansion algorithm used in the map view's
 * date navigation buttons.
 */

import { getExpansionDays, expandDateRange, formatDate } from '../../src/mykrok/assets/map-browser/date-utils.js';

describe('getExpansionDays', () => {
    test('single day range (0 days) expands by 3 days', () => {
        expect(getExpansionDays(0)).toBe(3);
    });

    test('1-day range expands by 3 days', () => {
        expect(getExpansionDays(1)).toBe(3);
    });

    test('2-day range expands by 3 days', () => {
        expect(getExpansionDays(2)).toBe(3);
    });

    test('3-day range (week range) expands by 14 days', () => {
        expect(getExpansionDays(3)).toBe(14);
    });

    test('7-day range expands by 14 days', () => {
        expect(getExpansionDays(7)).toBe(14);
    });

    test('10-day range (upper bound of week) expands by 14 days', () => {
        expect(getExpansionDays(10)).toBe(14);
    });

    test('11-day range (month range) expands by 150 days', () => {
        expect(getExpansionDays(11)).toBe(150);
    });

    test('30-day range expands by 150 days', () => {
        expect(getExpansionDays(30)).toBe(150);
    });

    test('45-day range (upper bound of month) expands by 150 days', () => {
        expect(getExpansionDays(45)).toBe(150);
    });

    test('46-day range (half-year range) expands by 180 days', () => {
        expect(getExpansionDays(46)).toBe(180);
    });

    test('180-day range expands by 180 days', () => {
        expect(getExpansionDays(180)).toBe(180);
    });

    test('200-day range (upper bound of half-year) expands by 180 days', () => {
        expect(getExpansionDays(200)).toBe(180);
    });

    test('201-day range (year range) expands by 365 days', () => {
        expect(getExpansionDays(201)).toBe(365);
    });

    test('365-day range expands by 365 days', () => {
        expect(getExpansionDays(365)).toBe(365);
    });

    test('1000-day range expands by 365 days', () => {
        expect(getExpansionDays(1000)).toBe(365);
    });
});

describe('expandDateRange', () => {
    test('single day expand prev extends start by 3 days', () => {
        const result = expandDateRange('2024-06-15', '2024-06-15', 'prev');
        expect(result.dateFrom).toBe('2024-06-12');
        expect(result.dateTo).toBe('2024-06-15');
    });

    test('single day expand next extends end by 3 days', () => {
        const result = expandDateRange('2024-06-15', '2024-06-15', 'next');
        expect(result.dateFrom).toBe('2024-06-15');
        expect(result.dateTo).toBe('2024-06-18');
    });

    test('week expand prev extends start by 14 days', () => {
        const result = expandDateRange('2024-06-10', '2024-06-17', 'prev');
        expect(result.dateFrom).toBe('2024-05-27');
        expect(result.dateTo).toBe('2024-06-17');
    });

    test('week expand next extends end by 14 days', () => {
        const result = expandDateRange('2024-06-10', '2024-06-17', 'next');
        expect(result.dateFrom).toBe('2024-06-10');
        expect(result.dateTo).toBe('2024-07-01');
    });

    test('month expand prev extends start by 150 days', () => {
        const result = expandDateRange('2024-06-01', '2024-06-30', 'prev');
        expect(result.dateFrom).toBe('2024-01-03');
        expect(result.dateTo).toBe('2024-06-30');
    });

    test('month expand next extends end by 150 days', () => {
        const result = expandDateRange('2024-06-01', '2024-06-30', 'next');
        expect(result.dateFrom).toBe('2024-06-01');
        expect(result.dateTo).toBe('2024-11-27');
    });
});

describe('expandDateRange progression', () => {
    test('repeated prev expansion grows range progressively', () => {
        let dateFrom = '2024-06-15';
        let dateTo = '2024-06-15';

        // First expansion: 0 days -> +3 days = 3 day range
        let result = expandDateRange(dateFrom, dateTo, 'prev');
        let intervalDays = Math.round((new Date(result.dateTo) - new Date(result.dateFrom)) / (24 * 60 * 60 * 1000));
        expect(intervalDays).toBe(3);

        // Second expansion: 3 days -> +14 days = 17 day range
        result = expandDateRange(result.dateFrom, result.dateTo, 'prev');
        intervalDays = Math.round((new Date(result.dateTo) - new Date(result.dateFrom)) / (24 * 60 * 60 * 1000));
        expect(intervalDays).toBe(17);

        // Third expansion: 17 days -> +150 days = 167 day range
        result = expandDateRange(result.dateFrom, result.dateTo, 'prev');
        intervalDays = Math.round((new Date(result.dateTo) - new Date(result.dateFrom)) / (24 * 60 * 60 * 1000));
        expect(intervalDays).toBe(167);

        // Fourth expansion: 167 days -> +180 days = 347 day range
        result = expandDateRange(result.dateFrom, result.dateTo, 'prev');
        intervalDays = Math.round((new Date(result.dateTo) - new Date(result.dateFrom)) / (24 * 60 * 60 * 1000));
        expect(intervalDays).toBe(347);

        // Fifth expansion: 347 days -> +365 days = 712 day range (~2 years)
        result = expandDateRange(result.dateFrom, result.dateTo, 'prev');
        intervalDays = Math.round((new Date(result.dateTo) - new Date(result.dateFrom)) / (24 * 60 * 60 * 1000));
        expect(intervalDays).toBe(712);
    });

    test('repeated next expansion grows range progressively', () => {
        let dateFrom = '2024-06-15';
        let dateTo = '2024-06-15';

        // First expansion: 0 days -> +3 days = 3 day range
        let result = expandDateRange(dateFrom, dateTo, 'next');
        let intervalDays = Math.round((new Date(result.dateTo) - new Date(result.dateFrom)) / (24 * 60 * 60 * 1000));
        expect(intervalDays).toBe(3);

        // Second expansion: 3 days -> +14 days = 17 day range
        result = expandDateRange(result.dateFrom, result.dateTo, 'next');
        intervalDays = Math.round((new Date(result.dateTo) - new Date(result.dateFrom)) / (24 * 60 * 60 * 1000));
        expect(intervalDays).toBe(17);

        // Third expansion: 17 days -> +150 days = 167 day range
        result = expandDateRange(result.dateFrom, result.dateTo, 'next');
        intervalDays = Math.round((new Date(result.dateTo) - new Date(result.dateFrom)) / (24 * 60 * 60 * 1000));
        expect(intervalDays).toBe(167);
    });
});

describe('formatDate', () => {
    test('formats YYYYMMDD to YYYY-MM-DD', () => {
        expect(formatDate('20240615')).toBe('2024-06-15');
    });

    test('formats datetime with time component', () => {
        expect(formatDate('20240615_123456')).toBe('2024-06-15');
    });

    test('returns dash for empty input', () => {
        expect(formatDate('')).toBe('-');
    });

    test('returns dash for null input', () => {
        expect(formatDate(null)).toBe('-');
    });

    test('returns dash for short input', () => {
        expect(formatDate('2024')).toBe('-');
    });
});
