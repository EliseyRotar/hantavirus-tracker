/**
 * filters.js — Filter controls for the Hantavirus Tracker v3.0.
 * Builds controls in both the desktop sidebar (#filter-controls)
 * and the mobile bottom sheet (#m-filter-controls), keeping them in sync.
 * Removed: Probable, Unknown, timeline slider.
 * Kept: Confirmed, Suspected, Deceased, Monitoring + date range + reset.
 */
(function () {
  'use strict';

  /* Shared filter state */
  var state = {
    statuses:  new Set(['Confirmed', 'Suspected', 'Deceased', 'Monitoring']),
    dateStart: null,
    dateEnd:   null,
  };

  var STATUS_DEFS = [
    { val: 'Confirmed',  color: '#e05252' },
    { val: 'Suspected',  color: '#e07b52' },
    { val: 'Deceased',   color: '#9b59b6' },
    { val: 'Monitoring', color: '#3498db' },
  ];

  /* ── Apply filters and update map + stats ── */
  function applyFilters() {
    var all = (window.mapState && window.mapState.allFeatures) || [];

    var filtered = all.filter(function (f) {
      var p = f.properties || {};
      var status = p.status || 'Unknown';
      /* Map Unknown/Probable to Monitoring for display */
      if (status === 'Unknown' || status === 'Probable') status = 'Monitoring';
      if (!state.statuses.has(status)) return false;

      var raw = p.date_reported || p.ONSET;
      if (raw) {
        var d = (typeof raw === 'number') ? new Date(raw) : new Date(raw);
        if (!isNaN(d)) {
          if (state.dateStart && d < state.dateStart) return false;
          if (state.dateEnd) {
            var end = new Date(state.dateEnd);
            end.setHours(23, 59, 59, 999);
            if (d > end) return false;
          }
        }
      }
      return true;
    });

    /* Render markers */
    if (typeof window.renderMarkers === 'function') {
      window.renderMarkers(filtered);
    }

    /* Count by status */
    var counts = { Confirmed: 0, Suspected: 0, Deceased: 0, Monitoring: 0 };
    filtered.forEach(function (f) {
      var s = (f.properties || {}).status;
      if (!s) return;
      if (s === 'Unknown' || s === 'Probable') s = 'Monitoring';
      if (counts[s] !== undefined) counts[s]++;
    });

    /* Update desktop stats bar */
    ['confirmed', 'suspected', 'deceased', 'monitoring'].forEach(function (key) {
      var el = document.getElementById('count-' + key);
      var cap = key.charAt(0).toUpperCase() + key.slice(1);
      if (el) el.textContent = counts[cap];
    });

    /* Update mobile topbar stats */
    if (typeof window.updateMobileStats === 'function') {
      window.updateMobileStats(counts);
    }
  }

  /* ── DOM helper ── */
  function mk(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'textContent') { el.textContent = attrs[k]; }
        else { el.setAttribute(k, attrs[k]); }
      });
    }
    return el;
  }

  /* ── Build filter controls into a container element ── */
  function buildControls(container, prefix) {
    if (!container) return;
    container.innerHTML = '';

    /* ── Status checkboxes ── */
    var statusWrap = mk('div', { style: 'display:flex;flex-direction:column;gap:1px;margin-bottom:12px;' });
    var statusLbl  = mk('div', { 'class': 'filter-label', textContent: 'Case Status' });
    statusWrap.appendChild(statusLbl);

    STATUS_DEFS.forEach(function (s) {
      var row = mk('label', { 'class': 'checkbox-row' });
      var cb  = mk('input', {
        type: 'checkbox',
        id: prefix + 'fs-' + s.val.toLowerCase(),
        'aria-label': 'Show ' + s.val + ' cases',
      });
      cb.checked = true;
      cb.addEventListener('change', function () {
        if (this.checked) state.statuses.add(s.val);
        else              state.statuses.delete(s.val);
        /* Sync the other panel's checkbox */
        var otherId = (prefix === 'd-') ? 'm-fs-' + s.val.toLowerCase()
                                        : 'd-fs-' + s.val.toLowerCase();
        var other = document.getElementById(otherId);
        if (other) other.checked = this.checked;
        applyFilters();
      });
      var swatch = mk('span', { 'class': 'status-swatch', style: 'background:' + s.color + ';' });
      var lbl = document.createTextNode(s.val);
      row.appendChild(cb);
      row.appendChild(swatch);
      row.appendChild(lbl);
      statusWrap.appendChild(row);
    });
    container.appendChild(statusWrap);

    /* ── Date range ── */
    var dateWrap = mk('div', { 'class': 'filter-group', style: 'margin-bottom:12px;' });
    var dateLbl  = mk('div', { 'class': 'filter-label', textContent: 'Date Range' });
    var dateRow  = mk('div', { 'class': 'date-row' });

    var startWrap = mk('div', { 'class': 'filter-group' });
    var startLbl  = mk('label', { 'class': 'filter-label', 'for': prefix + 'fs-date-start', textContent: 'From' });
    var startIn   = mk('input', { type: 'date', id: prefix + 'fs-date-start', 'aria-label': 'From date' });
    startIn.addEventListener('change', function () {
      state.dateStart = this.value ? new Date(this.value) : null;
      var otherId = (prefix === 'd-') ? 'm-fs-date-start' : 'd-fs-date-start';
      var other = document.getElementById(otherId);
      if (other) other.value = this.value;
      applyFilters();
    });
    startWrap.appendChild(startLbl);
    startWrap.appendChild(startIn);

    var endWrap = mk('div', { 'class': 'filter-group' });
    var endLbl  = mk('label', { 'class': 'filter-label', 'for': prefix + 'fs-date-end', textContent: 'To' });
    var endIn   = mk('input', { type: 'date', id: prefix + 'fs-date-end', 'aria-label': 'To date' });
    endIn.addEventListener('change', function () {
      state.dateEnd = this.value ? new Date(this.value) : null;
      var otherId = (prefix === 'd-') ? 'm-fs-date-end' : 'd-fs-date-end';
      var other = document.getElementById(otherId);
      if (other) other.value = this.value;
      applyFilters();
    });
    endWrap.appendChild(endLbl);
    endWrap.appendChild(endIn);

    dateRow.appendChild(startWrap);
    dateRow.appendChild(endWrap);
    dateWrap.appendChild(dateLbl);
    dateWrap.appendChild(dateRow);
    container.appendChild(dateWrap);

    /* ── Reset button ── */
    var resetBtn = mk('button', {
      type: 'button', 'class': 'btn-reset', 'aria-label': 'Reset all filters',
      textContent: 'Reset Filters',
    });
    resetBtn.addEventListener('click', function () {
      state.statuses  = new Set(['Confirmed', 'Suspected', 'Deceased', 'Monitoring']);
      state.dateStart = null;
      state.dateEnd   = null;
      STATUS_DEFS.forEach(function (s) {
        ['d-', 'm-'].forEach(function (p) {
          var cb = document.getElementById(p + 'fs-' + s.val.toLowerCase());
          if (cb) cb.checked = true;
        });
      });
      ['d-fs-date-start', 'd-fs-date-end', 'm-fs-date-start', 'm-fs-date-end'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.value = '';
      });
      applyFilters();
    });
    container.appendChild(resetBtn);
  }

  /* ── Initialise both panels ── */
  function init() {
    buildControls(document.getElementById('filter-controls'),   'd-');
    buildControls(document.getElementById('m-filter-controls'), 'm-');
  }

  document.addEventListener('DOMContentLoaded', init);
  document.addEventListener('geojsonloaded', function() {
    applyFilters();
  });
})();
