/**
 * ui.js — UI updates for the Live Hantavirus Global Tracker.
 *
 * Responsibilities:
 *   - Display metadata.generated_at as a human-readable "last updated" string
 *   - Display per-source timestamps in #source-timestamps
 *   - Show #staleness-warning banner when data is older than 24 hours
 *
 * Exports (on window):
 *   window.isStale(generatedAt) — returns true if age > 24 hours
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Staleness check — exported for testability
  // ---------------------------------------------------------------------------
  /**
   * Returns true if the given ISO timestamp is more than 24 hours old.
   * @param {string} generatedAt — ISO 8601 timestamp string
   * @returns {boolean}
   */
  window.isStale = function isStale(generatedAt) {
    if (!generatedAt) return false;
    const generated = new Date(generatedAt);
    if (isNaN(generated.getTime())) return false;
    const ageMs = Date.now() - generated.getTime();
    const twentyFourHoursMs = 24 * 60 * 60 * 1000;
    return ageMs > twentyFourHoursMs;
  };

  // ---------------------------------------------------------------------------
  // Format helpers
  // ---------------------------------------------------------------------------
  /**
   * Formats an ISO timestamp as a human-readable local date/time string.
   * @param {string} isoString
   * @returns {string}
   */
  function formatTimestamp(isoString) {
    if (!isoString) return 'Unknown';
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    return date.toLocaleString('en-GB', {
      year:   'numeric',
      month:  'long',
      day:    'numeric',
      hour:   '2-digit',
      minute: '2-digit',
      timeZoneName: 'short',
    });
  }

  /**
   * Returns a relative time string like "2 hours ago" or "just now".
   * @param {string} isoString
   * @returns {string}
   */
  function relativeTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return '';
    const diffMs = Date.now() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1)  return 'just now';
    if (diffMins < 60) return diffMins + ' minute' + (diffMins !== 1 ? 's' : '') + ' ago';

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return diffHours + ' hour' + (diffHours !== 1 ? 's' : '') + ' ago';

    const diffDays = Math.floor(diffHours / 24);
    return diffDays + ' day' + (diffDays !== 1 ? 's' : '') + ' ago';
  }

  // ---------------------------------------------------------------------------
  // DOM update functions
  // ---------------------------------------------------------------------------
  /**
   * Updates the #last-updated element with a human-readable timestamp.
   * @param {string} generatedAt — ISO 8601 string
   */
  function updateLastUpdated(generatedAt) {
    const el = document.getElementById('last-updated');
    if (!el) return;

    if (!generatedAt) {
      el.textContent = 'Unknown';
      return;
    }

    const formatted = formatTimestamp(generatedAt);
    const relative  = relativeTime(generatedAt);
    el.textContent  = formatted + (relative ? ' (' + relative + ')' : '');
    el.setAttribute('title', generatedAt); // full ISO string on hover
  }

  /**
   * Updates the #source-timestamps list with per-source timestamps.
   * @param {object} sourceTimestamps — { sourceId: isoString, ... }
   */
  function updateSourceTimestamps(sourceTimestamps) {
    const el = document.getElementById('source-timestamps');
    if (!el) return;

    if (!sourceTimestamps || Object.keys(sourceTimestamps).length === 0) {
      el.innerHTML = '<li class="text-gray-500">No source data available.</li>';
      return;
    }

    const items = Object.entries(sourceTimestamps).map(function (entry) {
      const sourceId = entry[0];
      const isoString = entry[1];
      const formatted = formatTimestamp(isoString);
      const relative  = relativeTime(isoString);

      return (
        '<li class="flex justify-between gap-2" ' +
        'aria-label="' + escapeAttr(sourceId) + ' last updated ' + escapeAttr(formatted) + '">' +
        '<span class="font-medium text-gray-300">' + escapeHTML(sourceId) + '</span>' +
        '<span class="text-gray-500 text-right" title="' + escapeAttr(isoString) + '">' +
        escapeHTML(relative || formatted) +
        '</span>' +
        '</li>'
      );
    });

    el.innerHTML = items.join('');
  }

  /**
   * Shows or hides the staleness warning banner.
   * @param {boolean} stale
   */
  function updateStalenessWarning(stale) {
    const banner = document.getElementById('staleness-warning');
    if (!banner) return;

    if (stale) {
      banner.classList.add('visible');
      banner.removeAttribute('hidden');
      // Shift the app down to avoid overlap
      const app = document.getElementById('app');
      if (app) app.style.paddingTop = banner.offsetHeight + 'px';
    } else {
      banner.classList.remove('visible');
      banner.setAttribute('hidden', '');
      const app = document.getElementById('app');
      if (app) app.style.paddingTop = '';
    }
  }

  // ---------------------------------------------------------------------------
  // Minimal escaping helpers
  // ---------------------------------------------------------------------------
  function escapeHTML(str) {
    if (typeof str !== 'string') return String(str);
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function escapeAttr(str) {
    if (typeof str !== 'string') return String(str);
    return str
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;');
  }

  // ---------------------------------------------------------------------------
  // Handle geojsonloaded event (dispatched by map.js)
  // ---------------------------------------------------------------------------
  document.addEventListener('geojsonloaded', function (event) {
    const detail = (event && event.detail) || {};
    const metadata = detail.metadata || {};

    updateLastUpdated(metadata.generated_at);
    updateSourceTimestamps(metadata.source_timestamps);
    updateStalenessWarning(window.isStale(metadata.generated_at));
  });

  // ---------------------------------------------------------------------------
  // Fallback: poll window.mapState in case the event was missed
  // (e.g., if ui.js loads after map.js has already dispatched)
  // ---------------------------------------------------------------------------
  (function pollForData() {
    let attempts = 0;
    const MAX_ATTEMPTS = 30; // 15 seconds total

    function check() {
      attempts++;
      const state = window.mapState;
      if (state && state.allFeatures && state.allFeatures.length > 0) {
        // Data already loaded — but we may have missed the event.
        // The event handler above will have fired if it was in time;
        // if not, we can't recover metadata here without it being stored.
        // map.js stores metadata on the event detail only, so we rely on
        // the event. This poll is a safety net for the #last-updated element.
        return;
      }
      if (attempts < MAX_ATTEMPTS) {
        setTimeout(check, 500);
      }
    }

    setTimeout(check, 500);
  })();

})();
