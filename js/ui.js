/**
 * ui.js — UI updates: timestamps, staleness, source panel.
 */
(function () {
  'use strict';

  window.isStale = function (ts) {
    if (!ts) return false;
    var d = new Date(ts);
    return !isNaN(d) && (Date.now() - d.getTime()) > 86400000;
  };

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
    if (isNaN(d)) return ts;
    return d.toLocaleString('en-GB', { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' });
  }

  function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function updateLastUpdated(ts) {
    var el = document.getElementById('last-updated');
    if (!el) return;
    if (!ts) { el.textContent = 'Unknown'; return; }
    el.textContent = fmtDate(ts) + ' (' + (relTime(ts) || '—') + ')';
    el.title = ts;
  }

  function updateSources(sourceTimestamps) {
    var el = document.getElementById('source-timestamps');
    if (!el) return;
    if (!sourceTimestamps || !Object.keys(sourceTimestamps).length) {
      el.innerHTML = '<div class="source-row"><span class="source-name" style="color:#64748b;">No data</span></div>';
      return;
    }
    el.innerHTML = Object.entries(sourceTimestamps).map(function (e) {
      var id = e[0], ts = e[1];
      var rel = relTime(ts);
      return '<div class="source-row">' +
        '<div style="display:flex;align-items:center;gap:6px;">' +
        '<div class="source-dot"></div>' +
        '<span class="source-name">' + esc(id) + '</span></div>' +
        '<span class="source-time" title="' + esc(ts) + '">' + esc(rel || fmtDate(ts)) + '</span>' +
        '</div>';
    }).join('');
  }

  function updateStaleness(ts) {
    var banner = document.getElementById('staleness-warning');
    if (!banner) return;
    if (window.isStale(ts)) {
      banner.classList.add('visible');
      var app = document.getElementById('app');
      if (app) app.style.paddingTop = banner.offsetHeight + 'px';
    } else {
      banner.classList.remove('visible');
      var app2 = document.getElementById('app');
      if (app2) app2.style.paddingTop = '';
    }
  }

  document.addEventListener('geojsonloaded', function (e) {
    var meta = ((e && e.detail) || {}).metadata || {};
    updateLastUpdated(meta.generated_at);
    updateSources(meta.source_timestamps);
    updateStaleness(meta.generated_at);
  });
})();
