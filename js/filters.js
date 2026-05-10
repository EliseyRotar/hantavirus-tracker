/**
 * filters.js — Filter controls for the Hantavirus Tracker.
 */
(function () {
  'use strict';

  const state = {
    statuses: new Set(['Confirmed', 'Suspected', 'Deceased', 'Monitoring']),
    strain: 'all',
    dateStart: null,
    dateEnd: null,
  };

  function applyFilters() {
    const all = (window.mapState && window.mapState.allFeatures) || [];
    const filtered = all.filter(function (f) {
      const p = f.properties || {};
      if (!state.statuses.has(p.status)) return false;
      if (state.strain !== 'all' && (p.virus_strain || 'Unknown').toLowerCase() !== state.strain.toLowerCase()) return false;
      if (state.dateStart || state.dateEnd) {
        const d = p.date_reported ? new Date(p.date_reported) : null;
        if (!d || isNaN(d)) return false;
        if (state.dateStart && d < state.dateStart) return false;
        if (state.dateEnd) {
          const end = new Date(state.dateEnd);
          end.setHours(23,59,59,999);
          if (d > end) return false;
        }
      }
      return true;
    });
    if (typeof window.renderMarkers === 'function') window.renderMarkers(filtered);

    // Update stats (desktop + mobile)
    const counts = { Confirmed: 0, Suspected: 0, Deceased: 0, Monitoring: 0 };
    filtered.forEach(function (f) {
      const s = (f.properties || {}).status;
      if (counts[s] !== undefined) counts[s]++;
    });
    const idMap = { Confirmed: 'confirmed', Suspected: 'suspected', Deceased: 'deceased', Monitoring: 'monitoring' };
    Object.entries(idMap).forEach(function (e) {
      const el = document.getElementById('count-' + e[1]);
      if (el) el.textContent = counts[e[0]];
    });
    if (typeof window.updateMobileStats === 'function') window.updateMobileStats(counts);
  }

  function mk(tag, attrs, text) {
    const el = document.createElement(tag);
    Object.entries(attrs || {}).forEach(function (e) { el.setAttribute(e[0], e[1]); });
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function buildControls() {
    const container = document.getElementById('filter-controls');
    if (!container) return;
    container.innerHTML = '';

    // ── Status checkboxes ──
    const statuses = [
      { val: 'Confirmed',  color: '#ef4444' },
      { val: 'Suspected',  color: '#f97316' },
      { val: 'Deceased',   color: '#7c3aed' },
      { val: 'Monitoring', color: '#0ea5e9' },
    ];

    const statusWrap = mk('div', { style: 'display:flex;flex-direction:column;gap:2px;' });
    const statusLbl = mk('div', { class: 'filter-label' }, 'Case Status');
    statusWrap.appendChild(statusLbl);

    statuses.forEach(function (s) {
      const row = mk('label', { class: 'checkbox-row', style: 'user-select:none;' });
      const cb  = mk('input', { type: 'checkbox', id: 'fs-' + s.val.toLowerCase(), 'aria-label': 'Show ' + s.val + ' cases' });
      cb.checked = true;
      cb.addEventListener('change', function () {
        if (this.checked) state.statuses.add(s.val); else state.statuses.delete(s.val);
        applyFilters();
      });
      const dot = mk('span', { class: 'dot', style: 'background:' + s.color + ';' });
      const lbl = mk('span', {}, s.val);
      row.appendChild(cb); row.appendChild(dot); row.appendChild(lbl);
      statusWrap.appendChild(row);
    });
    container.appendChild(statusWrap);

    // ── Strain select ──
    const strainWrap = mk('div', { class: 'filter-group' });
    const strainLbl  = mk('label', { class: 'filter-label', for: 'fs-strain' }, 'Virus Strain');
    const strainSel  = mk('select', { id: 'fs-strain', 'aria-label': 'Filter by virus strain' });
    [['all','All strains'],['Andes','Andes'],['Sin Nombre','Sin Nombre'],['Unknown','Unknown']].forEach(function (o) {
      const opt = mk('option', { value: o[0] }, o[1]);
      strainSel.appendChild(opt);
    });
    strainSel.addEventListener('change', function () { state.strain = this.value; applyFilters(); });
    strainWrap.appendChild(strainLbl); strainWrap.appendChild(strainSel);
    container.appendChild(strainWrap);

    // ── Date range ──
    const dateWrap = mk('div', { class: 'filter-group' });
    const dateLbl  = mk('div', { class: 'filter-label' }, 'Date Range');
    const dateRow  = mk('div', { class: 'date-row' });

    const startWrap = mk('div', { class: 'filter-group' });
    const startLbl  = mk('label', { class: 'filter-label', for: 'fs-date-start' }, 'From');
    const startIn   = mk('input', { type: 'date', id: 'fs-date-start', 'aria-label': 'From date' });
    startIn.addEventListener('change', function () { state.dateStart = this.value ? new Date(this.value) : null; applyFilters(); });
    startWrap.appendChild(startLbl); startWrap.appendChild(startIn);

    const endWrap = mk('div', { class: 'filter-group' });
    const endLbl  = mk('label', { class: 'filter-label', for: 'fs-date-end' }, 'To');
    const endIn   = mk('input', { type: 'date', id: 'fs-date-end', 'aria-label': 'To date' });
    endIn.addEventListener('change', function () { state.dateEnd = this.value ? new Date(this.value) : null; applyFilters(); });
    endWrap.appendChild(endLbl); endWrap.appendChild(endIn);

    dateRow.appendChild(startWrap); dateRow.appendChild(endWrap);
    dateWrap.appendChild(dateLbl); dateWrap.appendChild(dateRow);
    container.appendChild(dateWrap);

    // ── Reset ──
    const resetBtn = mk('button', { type: 'button', class: 'btn-reset', 'aria-label': 'Reset all filters' }, '↺ Reset Filters');
    resetBtn.addEventListener('click', function () {
      state.statuses = new Set(['Confirmed','Suspected','Deceased','Monitoring']);
      state.strain = 'all';
      state.dateStart = null; state.dateEnd = null;
      statuses.forEach(function (s) {
        const cb = document.getElementById('fs-' + s.val.toLowerCase());
        if (cb) cb.checked = true;
      });
      strainSel.value = 'all';
      startIn.value = ''; endIn.value = '';
      applyFilters();
    });
    container.appendChild(resetBtn);
  }

  document.addEventListener('DOMContentLoaded', buildControls);
  document.addEventListener('geojsonloaded', applyFilters);
})();
