/**
 * filters.js — Filter controls for the Live Hantavirus Global Tracker.
 *
 * Injects filter UI into #filter-controls and wires changes to
 * window.renderMarkers() using window.mapState.allFeatures.
 *
 * Filters:
 *   1. Status checkboxes: Confirmed, Probable, Suspected
 *   2. Virus strain select: All | Andes | Sin Nombre | Unknown
 *   3. Date range: start date + end date
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Filter state
  // ---------------------------------------------------------------------------
  const filterState = {
    statuses: new Set(['Confirmed', 'Probable', 'Suspected']),
    strain: 'all',
    dateStart: null,  // Date object or null
    dateEnd: null,    // Date object or null
  };

  // ---------------------------------------------------------------------------
  // Apply filters and re-render
  // ---------------------------------------------------------------------------
  function applyFilters() {
    const allFeatures = (window.mapState && window.mapState.allFeatures) || [];

    const filtered = allFeatures.filter(function (feature) {
      const props = feature.properties || {};

      // 1. Status filter
      if (!filterState.statuses.has(props.status)) return false;

      // 2. Virus strain filter
      if (filterState.strain !== 'all') {
        const strain = (props.virus_strain || 'Unknown').toLowerCase();
        const target = filterState.strain.toLowerCase();
        if (strain !== target) return false;
      }

      // 3. Date range filter
      if (filterState.dateStart || filterState.dateEnd) {
        const caseDate = props.date_reported ? new Date(props.date_reported) : null;
        if (!caseDate || isNaN(caseDate.getTime())) return false;

        if (filterState.dateStart && caseDate < filterState.dateStart) return false;
        if (filterState.dateEnd) {
          // Include the full end day
          const endOfDay = new Date(filterState.dateEnd);
          endOfDay.setHours(23, 59, 59, 999);
          if (caseDate > endOfDay) return false;
        }
      }

      return true;
    });

    if (typeof window.renderMarkers === 'function') {
      window.renderMarkers(filtered);
    }
  }

  // ---------------------------------------------------------------------------
  // Build filter UI
  // ---------------------------------------------------------------------------
  function buildFilterControls() {
    const container = document.getElementById('filter-controls');
    if (!container) return;

    container.innerHTML = '';

    // ---- 1. Status checkboxes ----
    const statusGroup = document.createElement('fieldset');
    statusGroup.className = 'border border-gray-600 rounded p-2';

    const statusLegend = document.createElement('legend');
    statusLegend.className = 'text-xs font-semibold text-gray-300 px-1';
    statusLegend.textContent = 'Case Status';
    statusGroup.appendChild(statusLegend);

    const statuses = ['Confirmed', 'Probable', 'Suspected'];
    const statusColors = {
      Confirmed: 'text-red-400',
      Probable:  'text-orange-400',
      Suspected: 'text-yellow-400',
    };

    statuses.forEach(function (status) {
      const label = document.createElement('label');
      label.className = 'flex items-center gap-2 cursor-pointer py-0.5 text-sm';

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = true;
      checkbox.value = status;
      checkbox.id = 'filter-status-' + status.toLowerCase();
      checkbox.setAttribute('aria-label', 'Show ' + status + ' cases');
      checkbox.className =
        'w-4 h-4 rounded border-gray-500 bg-gray-700 text-red-500 cursor-pointer ' +
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500';

      checkbox.addEventListener('change', function () {
        if (this.checked) {
          filterState.statuses.add(status);
        } else {
          filterState.statuses.delete(status);
        }
        applyFilters();
      });

      const span = document.createElement('span');
      span.className = statusColors[status] || 'text-gray-300';
      span.textContent = status;

      label.appendChild(checkbox);
      label.appendChild(span);
      statusGroup.appendChild(label);
    });

    container.appendChild(statusGroup);

    // ---- 2. Virus strain select ----
    const strainWrapper = document.createElement('div');
    strainWrapper.className = 'flex flex-col gap-1';

    const strainLabel = document.createElement('label');
    strainLabel.htmlFor = 'filter-strain';
    strainLabel.className = 'text-xs font-semibold text-gray-300';
    strainLabel.textContent = 'Virus Strain';

    const strainSelect = document.createElement('select');
    strainSelect.id = 'filter-strain';
    strainSelect.setAttribute('aria-label', 'Filter by virus strain');
    strainSelect.className =
      'bg-gray-700 border border-gray-600 text-gray-100 text-sm rounded px-2 py-1 ' +
      'focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500 cursor-pointer';

    const strainOptions = [
      { value: 'all',        label: 'All strains' },
      { value: 'Andes',      label: 'Andes' },
      { value: 'Sin Nombre', label: 'Sin Nombre' },
      { value: 'Unknown',    label: 'Unknown' },
    ];

    strainOptions.forEach(function (opt) {
      const option = document.createElement('option');
      option.value = opt.value;
      option.textContent = opt.label;
      strainSelect.appendChild(option);
    });

    strainSelect.addEventListener('change', function () {
      filterState.strain = this.value;
      applyFilters();
    });

    strainWrapper.appendChild(strainLabel);
    strainWrapper.appendChild(strainSelect);
    container.appendChild(strainWrapper);

    // ---- 3. Date range ----
    const dateWrapper = document.createElement('div');
    dateWrapper.className = 'flex flex-col gap-1';

    const dateHeading = document.createElement('p');
    dateHeading.className = 'text-xs font-semibold text-gray-300';
    dateHeading.textContent = 'Date Range';
    dateWrapper.appendChild(dateHeading);

    const dateRow = document.createElement('div');
    dateRow.className = 'flex flex-col gap-1';

    // Start date
    const startLabel = document.createElement('label');
    startLabel.htmlFor = 'filter-date-start';
    startLabel.className = 'text-xs text-gray-400';
    startLabel.textContent = 'From';

    const startInput = document.createElement('input');
    startInput.type = 'date';
    startInput.id = 'filter-date-start';
    startInput.setAttribute('aria-label', 'Filter cases from this date');
    startInput.className =
      'bg-gray-700 border border-gray-600 text-gray-100 text-sm rounded px-2 py-1 ' +
      'focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500 cursor-pointer';

    startInput.addEventListener('change', function () {
      filterState.dateStart = this.value ? new Date(this.value) : null;
      applyFilters();
    });

    // End date
    const endLabel = document.createElement('label');
    endLabel.htmlFor = 'filter-date-end';
    endLabel.className = 'text-xs text-gray-400';
    endLabel.textContent = 'To';

    const endInput = document.createElement('input');
    endInput.type = 'date';
    endInput.id = 'filter-date-end';
    endInput.setAttribute('aria-label', 'Filter cases up to this date');
    endInput.className =
      'bg-gray-700 border border-gray-600 text-gray-100 text-sm rounded px-2 py-1 ' +
      'focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500 cursor-pointer';

    endInput.addEventListener('change', function () {
      filterState.dateEnd = this.value ? new Date(this.value) : null;
      applyFilters();
    });

    dateRow.appendChild(startLabel);
    dateRow.appendChild(startInput);
    dateRow.appendChild(endLabel);
    dateRow.appendChild(endInput);
    dateWrapper.appendChild(dateRow);
    container.appendChild(dateWrapper);

    // ---- Reset button ----
    const resetBtn = document.createElement('button');
    resetBtn.type = 'button';
    resetBtn.textContent = 'Reset Filters';
    resetBtn.setAttribute('aria-label', 'Reset all filters to default values');
    resetBtn.className =
      'mt-1 w-full text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 ' +
      'border border-gray-600 rounded px-3 py-1.5 cursor-pointer transition-colors ' +
      'focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500';

    resetBtn.addEventListener('click', function () {
      // Reset state
      filterState.statuses = new Set(['Confirmed', 'Probable', 'Suspected']);
      filterState.strain = 'all';
      filterState.dateStart = null;
      filterState.dateEnd = null;

      // Reset UI
      statuses.forEach(function (s) {
        const cb = document.getElementById('filter-status-' + s.toLowerCase());
        if (cb) cb.checked = true;
      });
      strainSelect.value = 'all';
      startInput.value = '';
      endInput.value = '';

      applyFilters();
    });

    container.appendChild(resetBtn);
  }

  // ---------------------------------------------------------------------------
  // Bootstrap — build controls once DOM is ready, re-apply when data loads
  // ---------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    buildFilterControls();
  });

  // Re-apply filters when new GeoJSON data arrives (dispatched by map.js)
  document.addEventListener('geojsonloaded', function () {
    applyFilters();
  });

})();
