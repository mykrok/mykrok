/**
 * TSV parsing utilities for the map browser.
 * Exported for testing.
 */

/**
 * Parse a TSV (tab-separated values) string into an array of objects.
 *
 * @param {string} text - TSV content with header row
 * @returns {Array<Object>} Array of objects with keys from header row
 */
export function parseTSV(text) {
    const lines = text.trim().replace(/\r/g, '').split('\n');
    if (lines.length < 2) return [];
    const headers = lines[0].split('\t');
    return lines.slice(1).map(line => {
        const values = line.split('\t');
        return Object.fromEntries(headers.map((h, i) => [h, values[i] || '']));
    });
}
