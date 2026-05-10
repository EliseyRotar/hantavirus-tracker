/**
 * map.js — Leaflet map for the Hantavirus Tracker v2.0.
 *
 * Data source: ArcGIS Feature Service (ANDV Hantavirus 2026 dashboard)
 * Fallback:    data/cases.geojson (static snapshot)
 */
(function () {
  'use strict';

  /* ── ArcGIS endpoint ── */
  var ARCGIS_URL =
    'https://services1.arcgis.com/wb4Og4gH5mvzQAIV/arcgis/rest/services/' +
    'Tracking_Hantavirus_2026/FeatureServer/1/query' +
    '?where=1%3D1&outFields=*&f=geojson&returnGeometry=true&orderByFields=CASE_%20ASC';

  /* ── MV Hondius route waypoints ── */
  var MV_HONDIUS_ROUTE = [
    [-54.8, -68.3],  // Ushuaia, Argentina (departure)
    [-51.7, -59.0],  // Falkland Islands area
    [-54.2, -36.5],  // South Georgia
    [-37.1, -12.3],  // Atlantic Ocean (mid)
    [-15.9,  -5.7],  // Saint Helena
    [ -7.9, -14.4],  // Ascension Island area
    [ 14.9, -23.5],  // Cape Verde area
    [ 28.1, -15.4],  // Tenerife, Canary Islands (arrival)
  ];

  /* ── Status colour map ── */
  var STATUS_COLORS = {
    CONFIRMED:  '#ef4444',
    SUSPECTED:  '#f97316',
    DECEASED:   '#8b5cf6',
    MONITORING: '#0ea5e9',
  };

  function colorForStatus(s) {
    return STATUS_COLORS[(s || '').toUpperCase()] || '#94a3b8';
  }

  function titleCase(s) {
    if (!s) return 'Unknown';
    return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
  }

  function fmtDate(raw) {
    if (!raw) return '—';
    var d = (typeof raw === 'number') ? new Date(raw) : new Date(raw);
    if (isNaN(d)) return String(raw);
    return d.toLocaleDateString('en-GB', { year: 'numeric', month: 'short', day: 'numeric' });
  }

  /* ── Shared state ── */
  window.mapState = { allFeatures: [], clusterGroup: null, map: null };

  /* ── Update visible-count badge ── */
  function updateVisibleCount(n) {
    var el = document.getElementById('visible-count');
    if (el) el.textContent = n;
  }

  /* ── Create a single marker ── */
  function createMarker(feature) {
    var props  = feature.properties;
    var coords = feature.geometry.coordinates;
    var latlng = L.latLng(coords[1], coords[0]);
    var status = (props.STATUS || props.status || '').toUpperCase();
    var color  = colorForStatus(status);
    var label  = (props.LASTLOCATION || props.location_name || '') + ' — ' + titleCase(props.STATUS || props.status || '');

    var marker;

    if (status === 'CONFIRMED' || status === 'DECEASED') {
      /* Pulsing div icon */
      var icon = L.divIcon({
        className: '',
        html: '<div class="pulse-marker" style="background:' + color + ';color:' + color + ';" ' +
              'role="img" aria-label="' + label.replace(/"/g, '&quot;') + '"></div>',
        iconSize:    [14, 14],
        iconAnchor:  [7, 7],
        popupAnchor: [0, -12],
      });
      marker = L.marker(latlng, { icon: icon });
    } else {
      /* Circle marker for Suspected / Monitoring */
      marker = L.circleMarker(latlng, {
        radius:      8,
        fillColor:   color,
        color:       'rgba(255,255,255,0.12)',
        weight:      1,
        opacity:     1,
        fillOpacity: status === 'MONITORING' ? 0.5 : 0.85,
        title:       label,
      });
    }

    /* Click → case detail panel instead of popup */
    marker.on('click', function () {
      var p = props;
      var ageSex = '';
      if (p.AGE)       ageSex += p.AGE;
      if (p.SEX === 1) ageSex += (ageSex ? ' ♂' : '♂');
      if (p.SEX === 2) ageSex += (ageSex ? ' ♀' : '♀');

      openCasePanel({
        case_id:        String(p.CASE_ || p.case_id || p.OBJECTID || '—'),
        status:         titleCase(p.STATUS || p.status || 'Unknown'),
        location_name:  p.LASTLOCATION || p.location_name || '—',
        date_formatted: fmtDate(p.ONSET || p.date_reported),
        age_sex:        ageSex || '—',
        exposure_group: p.Exposure_Group || p.exposure_group || '—',
        notes:          p.DETAILS || p.notes || '',
        source:         p.SOURCE || p.source || '—',
      });
    });

    return marker;
  }

  /* ── Render markers (called by filters.js) ── */
  window.renderMarkers = function (features) {
    var cg = window.mapState.clusterGroup;
    if (!cg) return;
    cg.clearLayers();
    features.forEach(function (f) {
      if (!f.geometry || !f.geometry.coordinates || f.geometry.coordinates.length < 2) return;
      cg.addLayer(createMarker(f));
    });
    updateVisibleCount(features.length);
  };

  /* ── Initialise Leaflet map ── */
  function initMap() {
    var map = L.map('map', {
      center:     [20, 0],
      zoom:       2,
      minZoom:    2,
      maxZoom:    18,
      zoomControl: false,
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
        '&copy; <a href="https://carto.com/">CARTO</a> · ' +
        'Data: <a href="https://www.arcgis.com/apps/dashboards/5c68442d2afc42d7ba2696e4cd393729" target="_blank">ANDV Dashboard</a> · ' +
        'K. Panozzo, University of Toledo',
      subdomains: 'abcd',
      maxZoom:    19,
    }).addTo(map);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    /* Cluster group */
    var clusterGroup = L.markerClusterGroup({
      maxClusterRadius:    60,
      showCoverageOnHover: false,
      spiderfyOnMaxZoom:   true,
      iconCreateFunction: function (cluster) {
        var n    = cluster.getChildCount();
        var size = n >= 20 ? 44 : n >= 10 ? 38 : 32;
        var fs   = n >= 10 ? 12 : 13;
        return L.divIcon({
          html: '<div style="' +
            'width:' + size + 'px;height:' + size + 'px;border-radius:50%;' +
            'background:rgba(59,130,246,0.18);border:2px solid rgba(59,130,246,0.55);' +
            'display:flex;align-items:center;justify-content:center;' +
            'color:#93c5fd;font-weight:700;font-size:' + fs + 'px;' +
            'box-shadow:0 0 14px rgba(59,130,246,0.35);" aria-label="' + n + ' cases">' + n + '</div>',
          className: '',
          iconSize:   [size, size],
          iconAnchor: [size / 2, size / 2],
        });
      },
    });
    map.addLayer(clusterGroup);

    window.mapState.map          = map;
    window.mapState.clusterGroup = clusterGroup;
    return map;
  }

  /* ── MV Hondius route ── */
  function addHondiusRoute(map) {
    L.polyline(MV_HONDIUS_ROUTE, {
      color:     '#06b6d4',
      weight:    2,
      opacity:   0.7,
      dashArray: '10 8',
    }).addTo(map).bindTooltip('🚢 MV Hondius voyage route (Apr–May 2026)', { sticky: true });

    var endpoints = [
      [0,                          '🛳 Departure: Ushuaia, Argentina (Apr 1)',        'right'],
      [MV_HONDIUS_ROUTE.length - 1,'🏁 Arrival: Tenerife, Canary Islands (May 10)',  'left'],
    ];
    endpoints.forEach(function (item) {
      L.circleMarker(MV_HONDIUS_ROUTE[item[0]], {
        radius:      5,
        fillColor:   '#06b6d4',
        color:       '#0ea5e9',
        weight:      1.5,
        fillOpacity: 0.9,
      }).addTo(map).bindTooltip(item[1], { direction: item[2] });
    });
  }

  /* ── Error overlay ── */
  function showError(msg) {
    var el = document.getElementById('map');
    if (!el) return;
    var d = document.createElement('div');
    d.setAttribute('role', 'alert');
    d.style.cssText =
      'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);' +
      'background:#0f1623;border:1px solid #ef4444;padding:20px 24px;border-radius:10px;' +
      'text-align:center;z-index:1000;color:#fca5a5;max-width:300px;';
    d.innerHTML =
      '<p style="font-weight:700;margin-bottom:6px;">⚠ Could not load case data</p>' +
      '<p style="font-size:12px;color:#94a3b8;">' + msg + '</p>';
    el.appendChild(d);
  }

  /* ── Normalise feature properties ── */
  function normaliseFeature(f) {
    var p = f.properties;
    /* Add lowercase/normalised aliases so filters.js works with both sources */
    p.status        = titleCase(p.STATUS || p.status || 'Unknown');
    p.location_name = p.LASTLOCATION || p.location_name || 'Unknown';
    p.date_reported = p.ONSET        || p.date_reported || null;
    p.source        = p.SOURCE       || p.source        || 'ArcGIS';
    p.virus_strain  = 'Andes';
    p.notes         = p.DETAILS      || p.notes         || '';
    return f;
  }

  /* ── Data loaded callback ── */
  function onDataLoaded(geojson, source) {
    var features = (geojson.features || []).map(normaliseFeature);
    var now      = new Date().toISOString();

    var metadata = geojson.metadata || {
      generated_at:      now,
      source_timestamps: { 'ANDV Dashboard (ArcGIS)': now },
      data_source:       'ArcGIS Feature Service — ANDV Hantavirus 2026',
      data_source_url:   'https://www.arcgis.com/apps/dashboards/5c68442d2afc42d7ba2696e4cd393729',
      total_cases:       features.length,
    };

    console.log('[map.js] Loaded ' + features.length + ' cases from ' + source);
    window.mapState.allFeatures = features;
    window.renderMarkers(features);
    document.dispatchEvent(new CustomEvent('geojsonloaded', {
      detail: { metadata: metadata, features: features },
    }));
  }

  /* ── Fetch data: ArcGIS first, local fallback ── */
  function loadData() {
    fetch(ARCGIS_URL)
      .then(function (r) {
        if (!r.ok) throw new Error('ArcGIS HTTP ' + r.status);
        return r.json();
      })
      .then(function (geojson) {
        if (!geojson.features || geojson.features.length === 0) {
          throw new Error('ArcGIS returned empty dataset');
        }
        onDataLoaded(geojson, 'ArcGIS Feature Service (live)');
      })
      .catch(function (err) {
        console.warn('[map.js] ArcGIS fetch failed (' + err.message + '), falling back to local GeoJSON');
        fetch('data/cases.geojson')
          .then(function (r) {
            if (!r.ok) throw new Error('Local GeoJSON HTTP ' + r.status);
            return r.json();
          })
          .then(function (geojson) {
            onDataLoaded(geojson, 'local snapshot (fallback)');
          })
          .catch(function (err2) {
            console.error('[map.js] Both data sources failed:', err2);
            showError('Check your connection and refresh the page.');
          });
      });
  }

  /* ── Bootstrap ── */
  document.addEventListener('DOMContentLoaded', function () {
    var map = initMap();
    addHondiusRoute(map);
    loadData();
  });
})();
