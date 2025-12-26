/**
 * Photo viewer utility functions.
 * Pure functions for photo navigation logic.
 */

/**
 * Check if can navigate to previous photo.
 * @param {number} currentIndex - Current photo index (0-based)
 * @param {number} totalLength - Total number of photos
 * @returns {boolean} True if previous photo exists
 */
export function canGoPrev(currentIndex, totalLength) {
    return totalLength > 1 && currentIndex > 0;
}

/**
 * Check if can navigate to next photo.
 * @param {number} currentIndex - Current photo index (0-based)
 * @param {number} totalLength - Total number of photos
 * @returns {boolean} True if next photo exists
 */
export function canGoNext(currentIndex, totalLength) {
    return totalLength > 1 && currentIndex < totalLength - 1;
}

/**
 * Get previous photo index.
 * @param {number} currentIndex - Current photo index (0-based)
 * @param {number} totalLength - Total number of photos
 * @returns {number} Previous index (clamped to 0)
 */
export function getPrevIndex(currentIndex, totalLength) {
    if (!canGoPrev(currentIndex, totalLength)) return currentIndex;
    return currentIndex - 1;
}

/**
 * Get next photo index.
 * @param {number} currentIndex - Current photo index (0-based)
 * @param {number} totalLength - Total number of photos
 * @returns {number} Next index (clamped to length - 1)
 */
export function getNextIndex(currentIndex, totalLength) {
    if (!canGoNext(currentIndex, totalLength)) return currentIndex;
    return currentIndex + 1;
}

/**
 * Format photo counter text.
 * @param {number} currentIndex - Current photo index (0-based)
 * @param {number} totalLength - Total number of photos
 * @returns {string} Formatted counter like "3 of 10"
 */
export function formatPhotoCounter(currentIndex, totalLength) {
    return `${currentIndex + 1} of ${totalLength}`;
}

/**
 * Determine click direction based on X position.
 * @param {number} clickX - Click X coordinate relative to element
 * @param {number} width - Element width
 * @returns {'prev' | 'next'} Direction based on which half was clicked
 */
export function getClickDirection(clickX, width) {
    return clickX < width / 2 ? 'prev' : 'next';
}
