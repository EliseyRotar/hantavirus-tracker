/**
 * filters.js — Filter controls for the Hantavirus Tracker v2.0.
 * Builds controls in both the desktop sidebar (#filter-controls)
 * and the mobile bottom sheet (#m-filter-controls), keeping them in sync.
 */
(function () {
  'use strict';

  /* Shared filter state */
  var state = {
    statuses:  new Set(['Confirmed', 'Probable', 'Suspected', 'Deceased', 'Monitoring', 'Unknown']),
    dateStart: null,
    dateEnd:   null,
    timelineDay: null, // Current day index for the slider
  };

  var timelineDays = []; // Sorted unique dates

  var STATUS_DEFS = [
    { val: 'Confirmed',  color: '#ef4444' },
    { val: 'Probable',   color: '#facc15' },
    { val: 'Suspected',  color: '#f97316' },
    { val: 'Deceased',   color: '#8b5cf6' },
    { val: 'Monitoring', color: '#0ea5e9' },
    { val: 'Unknown',    color: '#64748b' },
  ];

  /* ── Apply filters and update map + stats ── */
  function applyFilters() {
    var all = (window.mapState && window.mapState.allFeatures) || [];

    var filtered = all.filter(function (f) {
      var p = f.properties || {};
      /* Normalised status is stored as titlecase in p.status by map.js */
      var status = p.status || 'Unknown';
      if (!state.statuses.has(status)) return false;

      var raw = p.date_reported || p.ONSET;
      var d = (typeof raw === 'number') ? new Date(raw) : new Date(raw);
      if (isNaN(d)) return false;

      /* Timeline slider filter */
      if (state.timelineDay !== null && timelineDays.length > 0) {
        var currentDayLimit = new Date(timelineDays[state.timelineDay]);
        currentDayLimit.setHours(23, 59, 59, 999);
        if (d > currentDayLimit) return false;
      }

      /* Date range filter */
      if (state.dateStart || state.dateEnd) {
        if (state.dateStart && d < state.dateStart) return false;
        if (state.dateEnd) {
          var end = new Date(state.dateEnd);
          end.setHours(23, 59, 59, 999);
          if (d > end) return false;
        }
      }
      return true;
    });

    /* Render markers */
    if (typeof window.renderMarkers === 'function') {
      window.renderMarkers(filtered);
    }

    /* Count by status */
    var counts = { Confirmed: 0, Probable: 0, Suspected: 0, Deceased: 0, Monitoring: 0, Unknown: 0 };
    filtered.forEach(function (f) {
      var s = (f.properties || {}).status;
      if (s && counts[s] !== undefined) counts[s]++;
    });

    /* Update desktop stats bar */
    ['confirmed', 'probable', 'suspected', 'deceased', 'monitoring'].forEach(function (key) {
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
    var statusWrap = mk('div', { style: 'display:flex;flex-direction:column;gap:2px;' });
    var statusLbl  = mk('div', { class: 'filter-label', textContent: 'Case Status' });
    statusWrap.appendChild(statusLbl);

    STATUS_DEFS.forEach(function (s) {
      var row = mk('label', { class: 'checkbox-row' });
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
      var dot = mk('span', { class: 'dot', style: 'background:' + s.color + ';' });
      var lbl = document.createTextNode(s.val);
      row.appendChild(cb);
      row.appendChild(dot);
      row.appendChild(lbl);
      statusWrap.appendChild(row);
    });
    container.appendChild(statusWrap);

    /* ── Date range ── */
    var dateWrap = mk('div', { class: 'filter-group' });
    var dateLbl  = mk('div', { class: 'filter-label', textContent: 'Date Range' });
    var dateRow  = mk('div', { class: 'date-row' });

    var startWrap = mk('div', { class: 'filter-group' });
    var startLbl  = mk('label', { class: 'filter-label', for: prefix + 'fs-date-start', textContent: 'From' });
    var startIn   = mk('input', { type: 'date', id: prefix + 'fs-date-start', 'aria-label': 'From date' });
    startIn.addEventListener('change', function () {
      state.dateStart = this.value ? new Date(this.value) : null;
      /* Sync other panel */
      var otherId = (prefix === 'd-') ? 'm-fs-date-start' : 'd-fs-date-start';
      var other = document.getElementById(otherId);
      if (other) other.value = this.value;
      applyFilters();
    });
    startWrap.appendChild(startLbl);
    startWrap.appendChild(startIn);

    var endWrap = mk('div', { class: 'filter-group' });
    var endLbl  = mk('label', { class: 'filter-label', for: prefix + 'fs-date-end', textContent: 'To' });
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
      type: 'button', class: 'btn-reset', 'aria-label': 'Reset all filters',
      textContent: '↺  Reset Filters',
    });
    resetBtn.addEventListener('click', function () {
      state.statuses  = new Set(['Confirmed', 'Probable', 'Suspected', 'Deceased', 'Monitoring', 'Unknown']);
      state.dateStart = null;
      state.dateEnd   = null;
      state.timelineDay = null;
      /* Reset all checkboxes and date inputs in both panels */
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
      ['d-', 'm-'].forEach(function(p) {
        var s = document.getElementById(p + 'timeline-slider');
        if (s) s.value = s.max;
        var d = document.getElementById(p + 'timeline-date');
        if (d) d.textContent = 'Show all dates';
      });
      applyFilters();
    });
    container.appendChild(resetBtn);
  }

  /* ── Build timeline slider ── */
  function buildTimeline(container, prefix) {
    if (!container) return;
    container.innerHTML = '';

    var all = (window.mapState && window.mapState.allFeatures) || [];
    var dates = all.map(function(f) {
      var raw = f.properties.date_reported || f.properties.ONSET;
      return (typeof raw === 'number') ? new Date(raw).toISOString().split('T')[0] : raw;
    }).filter(Boolean);
    
    timelineDays = Array.from(new Set(dates)).sort();
    
    if (timelineDays.length === 0) {
      container.innerHTML = '<div class="filter-label">No date data available</div>';
      return;
    }

    var sliderWrap = mk('div', { class: 'filter-group', style: 'gap:10px;' });
    var labelRow = mk('div', { style: 'display:flex;justify-content:between;align-items:center;' });
    var dateDisplay = mk('div', { id: prefix + 'timeline-date', style: 'font-size:13px;font-weight:700;color:var(--cyan);', textContent: 'Show all dates' });
    labelRow.appendChild(dateDisplay);
    
    var slider = mk('input', {
      type: 'range',
      id: prefix + 'timeline-slider',
      min: 0,
      max: timelineDays.length,
      value: timelineDays.length,
      style: 'width:100%;accent-color:var(--cyan);cursor:pointer;'
    });

    slider.addEventListener('input', function() {
      var val = parseInt(this.value, 10);
      state.timelineDay = (val === timelineDays.length) ? null : val;
      
      /* Update display */
      var displayText = (state.timelineDay === null) ? 'Show all dates' : 'Cases up to: ' + timelineDays[state.timelineDay];
      ['d-', 'm-'].forEach(function(p) {
        var el = document.getElementById(p + 'timeline-date');
        if (el) el.textContent = displayText;
        var s = document.getElementById(p + 'timeline-slider');
        if (s) s.value = val;
      });
      
      applyFilters();
    });

    sliderWrap.appendChild(labelRow);
    sliderWrap.appendChild(slider);
    container.appendChild(sliderWrap);
  }

  /* ── Initialise both panels ── */
  function init() {
    buildControls(document.getElementById('filter-controls'),   'd-');
    buildControls(document.getElementById('m-filter-controls'), 'm-');
  }

  document.addEventListener('DOMContentLoaded', init);
  document.addEventListener('geojsonloaded', function() {
    buildTimeline(document.getElementById('timeline-controls'), 'd-');
    buildTimeline(document.getElementById('m-timeline-controls'), 'm-');
    applyFilters();
  });
})();
