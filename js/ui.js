/**
 * ui.js — UI updates: timestamps, staleness banner, source panel.
 * v2.0 — updates both desktop sidebar and mobile bottom sheet.
 */
(function () {
  'use strict';

  /* ── Helpers ── */
  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function relTime(ts) {
    if (!ts) return '';
    var d = new Date(ts);
    if (isNaN(d)) return '';
    var m = Math.floor((Date.now() - d.getTime()) / 60000);
    if (m < 1)  return 'just now';
    if (m < 60) return m + 'm ago';
    var h = Math.floor(m / 60);
    if (h < 24) return h + 'h ago';
    return Math.floor(h / 24) + 'd ago';
  }

  function fmtDate(ts) {
    if (!ts) return '—';
    var d = new Date(ts);
    if (isNaN(d)) return String(ts);
    return d.toLocaleString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  window.isStale = function (ts) {
    if (!ts) return false;
    var d = new Date(ts);
    return !isNaN(d) && (Date.now() - d.getTime()) > 86400000;
  };

  /* ── Last updated ── */
  function updateLastUpdated(ts) {
    var text = ts ? fmtDate(ts) + ' (' + (relTime(ts) || '—') + ')' : 'Unknown';
    ['last-updated', 'm-last-updated'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) { el.textContent = text; el.title = ts || ''; }
    });
  }

  /* ── Source status panel (desktop sidebar only) ── */
  function updateSources(sourceStats) {
    var el = document.getElementById('source-timestamps');
    if (!el) return;
    if (!sourceStats || !Object.keys(sourceStats).length) {
      el.innerHTML = '<div class="source-row"><span class="source-name" style="color:#64748b;">No data</span></div>';
      return;
    }
    el.innerHTML = Object.entries(sourceStats).map(function (e) {
      var id = e[0], stats = e[1];
      var status = stats.status || 'ok';
      var ts = stats.verified_at || '';
      var rel = relTime(ts);
      var dotColor = status === 'ok' ? '#22c55e' : '#ef4444';
      var statusText = status === 'ok' ? (rel || fmtDate(ts)) : 'Error';
      
      return '<div class="source-row">' +
        '<div style="display:flex;align-items:center;gap:6px;">' +
          '<div class="source-dot" style="background:' + dotColor + ';"></div>' +
          '<span class="source-name">' + esc(id) + '</span>' +
        '</div>' +
        '<span class="source-time" title="' + esc(ts + (stats.error ? '\nError: ' + stats.error : '')) + '">' + 
          esc(statusText) + 
        '</span>' +
        '</div>';
    }).join('');
  }

  /* ── Staleness banner ── */
  function updateStaleness(ts) {
    var banner = document.getElementById('staleness-warning');
    if (!banner) return;
    if (window.isStale(ts)) {
      banner.classList.add('visible');
    } else {
      banner.classList.remove('visible');
    }
  }

  /* ── Listen for data loaded event ── */
  document.addEventListener('geojsonloaded', function (e) {
    var meta = ((e && e.detail) || {}).metadata || {};
    updateLastUpdated(meta.generated_at);
    updateSources(meta.source_stats || meta.source_timestamps);
    updateStaleness(meta.generated_at);
  });
})();
