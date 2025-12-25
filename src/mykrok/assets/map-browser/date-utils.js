/**
 * Date utility functions for the map browser.
 * These are exported for testing.
 */

/**
 * Calculate expansion amount based on current date interval.
 *
 * Expansion rules:
 * - ~1 day (0-2 days) -> expand by 3 days (to ~1 week)
 * - ~1 week (3-10 days) -> expand by 14 days (to ~1 month)
 * - ~1 month (11-45 days) -> expand by 150 days (to ~6 months)
 * - ~6 months (46-200 days) -> expand by 180 days (to ~1 year)
 * - >200 days -> expand by 365 days
 *
 * @param {number} intervalDays - Number of days in the current interval
 * @returns {number} Number of days to expand by
 */
export function getExpansionDays(intervalDays) {
    if (intervalDays <= 2) {
        return 3;  // ~1 day -> ~1 week
    } else if (intervalDays <= 10) {
        return 14;  // ~1 week -> ~1 month
    } else if (intervalDays <= 45) {
        return 150;  // ~1 month -> ~6 months
    } else if (intervalDays <= 200) {
        return 180;  // ~6 months -> ~1 year
    } else {
        return 365;  // >200 days -> add 1 year
    }
}

/**
 * Expand a date range in the given direction.
 *
 * @param {string} dateFrom - Start date in YYYY-MM-DD format
 * @param {string} dateTo - End date in YYYY-MM-DD format
 * @param {string} direction - 'prev' to expand backward, 'next' to expand forward
 * @returns {{dateFrom: string, dateTo: string}} New date range
 */
export function expandDateRange(dateFrom, dateTo, direction) {
    const fromDate = new Date(dateFrom);
    const toDate = new Date(dateTo);
    const dayMs = 24 * 60 * 60 * 1000;
    const intervalMs = toDate - fromDate;
    const intervalDays = Math.round(intervalMs / dayMs);

    const expandDays = getExpansionDays(intervalDays);

    if (direction === 'prev') {
        fromDate.setTime(fromDate.getTime() - expandDays * dayMs);
    } else {
        toDate.setTime(toDate.getTime() + expandDays * dayMs);
    }

    return {
        dateFrom: fromDate.toISOString().split('T')[0],
        dateTo: toDate.toISOString().split('T')[0]
    };
}

/**
 * Format a datetime string (YYYYMMDD_HHMMSS) to display format (YYYY-MM-DD).
 *
 * @param {string} datetime - DateTime string in YYYYMMDD format
 * @returns {string} Formatted date string
 */
export function formatDate(datetime) {
    if (!datetime || datetime.length < 8) return '-';
    const y = datetime.substring(0, 4);
    const m = datetime.substring(4, 6);
    const d = datetime.substring(6, 8);
    return `${y}-${m}-${d}`;
}
