/**
 * Tests for TSV parsing utilities.
 */

import { parseTSV } from '../../src/mykrok/assets/map-browser/tsv-utils.js';

describe('parseTSV', () => {
    test('parses simple TSV with Unix line endings', () => {
        const tsv = 'name\tage\tcity\nAlice\t30\tNYC\nBob\t25\tLA';
        const result = parseTSV(tsv);
        expect(result).toHaveLength(2);
        expect(result[0]).toEqual({ name: 'Alice', age: '30', city: 'NYC' });
        expect(result[1]).toEqual({ name: 'Bob', age: '25', city: 'LA' });
    });

    test('parses TSV with Windows line endings (CRLF)', () => {
        const tsv = 'name\tage\r\nAlice\t30\r\nBob\t25';
        const result = parseTSV(tsv);
        expect(result).toHaveLength(2);
        expect(result[0]).toEqual({ name: 'Alice', age: '30' });
        expect(result[1]).toEqual({ name: 'Bob', age: '25' });
    });

    test('returns empty array for header-only TSV', () => {
        const tsv = 'name\tage\tcity';
        const result = parseTSV(tsv);
        expect(result).toEqual([]);
    });

    test('returns empty array for empty input', () => {
        expect(parseTSV('')).toEqual([]);
    });

    test('handles missing values with empty strings', () => {
        const tsv = 'a\tb\tc\n1\t\t3';
        const result = parseTSV(tsv);
        expect(result).toHaveLength(1);
        expect(result[0]).toEqual({ a: '1', b: '', c: '3' });
    });

    test('handles trailing empty values', () => {
        const tsv = 'a\tb\tc\n1\t2\t';
        const result = parseTSV(tsv);
        expect(result).toHaveLength(1);
        expect(result[0]).toEqual({ a: '1', b: '2', c: '' });
    });

    test('handles fewer values than headers', () => {
        const tsv = 'a\tb\tc\n1\t2';
        const result = parseTSV(tsv);
        expect(result).toHaveLength(1);
        expect(result[0]).toEqual({ a: '1', b: '2', c: '' });
    });

    test('parses real athletes.tsv format', () => {
        const tsv = 'username\tfirstname\tlastname\tcity\nyhalchenko\tYaroslav\tHalchenko\tNorwich';
        const result = parseTSV(tsv);
        expect(result).toHaveLength(1);
        expect(result[0].username).toBe('yhalchenko');
        expect(result[0].firstname).toBe('Yaroslav');
    });

    test('parses real sessions.tsv format', () => {
        const tsv = 'datetime\ttype\tsport\tname\tdistance_m\n20230613T113607\tRun\tRun\tMorning Run\t6998.0';
        const result = parseTSV(tsv);
        expect(result).toHaveLength(1);
        expect(result[0].datetime).toBe('20230613T113607');
        expect(result[0].type).toBe('Run');
        expect(result[0].distance_m).toBe('6998.0');
    });
});
