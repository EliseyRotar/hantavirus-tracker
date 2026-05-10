/**
 * map.js — Leaflet map for the Live Hantavirus Global Tracker.
 *
 * Data source: ArcGIS Feature Service (ANDV Hantavirus 2026 dashboard)
 * https://services1.arcgis.com/wb4Og4gH5mvzQAIV/arcgis/rest/services/Tracking_Hantavirus_2026/FeatureServer/1
 * Fallback: data/cases.geojson (static snapshot)
 */
(function () {
  'use strict';

  // ── ArcGIS Feature Service endpoint ──────────────────────────────
  var ARCGIS_URL =
    'https://services1.arcgis.com/wb4Og4gH5mvzQAIV/arcgis/rest/services/' +
    'Tracking_Hantavirus_2026/FeatureServer/1/query' +
    '?where=1%3D1&outFields=*&f=geojson&returnGeometry=true&orderByFields=CASE_%20ASC';

  window.mapState = { allFeatures: [], clusterGroup: null, map: null };

  var MV_HONDIUS_ROUTE = [
    [-54.8, -68.3], [-51.7, -59.0], [-54.2, -36.5],
    [-37.1, -12.3], [-15.9,  -5.7], [ -7.9, -14.4],
    [ 14.9, -23.5], [ 28.1, -15.4],
  ];

  // ArcGIS uses uppercase STATUS values
  var STATUS_COLORS = {
    CONFIRMED:  '#ef4444',
    SUSPECTED:  '#f97316',
    DECEASED:   '#7c3aed',
    MONITORING: '#0ea5e9',
    // lowercase fallbacks (local GeoJSON)
    Confirmed:  '#ef4444',
    Suspected:  '#f97316',
    Deceased:   '#7c3aed',
    Monitoring: '#0ea5e9',
  };

  function colorForStatus(s) { return STATUS_COLORS[s] || '#94a3b8'; }

  function titleCase(s) {
    if (!s) return 'Unknown';
    return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
  }

  function esc(str) {
    if (str == null) return '—';
    return String(str)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  function fmtDate(ms) {
    if (!ms) return '—';
    // ArcGIS timestamps are epoch milliseconds
    var d = typeof ms === 'number' ? new Date(ms) : new Date(ms);
    if (isNaN(d)) return String(ms);
    return d.toLocaleDateString('en-GB', { year:'numeric', month:'short', day:'numeric' });
  }

  // Convert ArcGIS feature properties to our normalised format
  function normalise(props) {
    return {
      case_id:          String(props.CASE_ || props.case_id || props.OBJECTID || ''),
      status:           titleCase(props.STATUS || props.status || 'Unknown'),
      location_name:    props.LASTLOCATION || props.location_name || 'Unknown',
      date_reported:    props.ONSET        || props.date_reported || null,
      source:           props.SOURCE       || props.source        || 'ArcGIS',
      virus_strain:     'Andes',
      notes:            props.DETAILS      || props.notes         || '',
      age:              props.AGE          || null,
      sex:              props.SEX === 1 ? '♂' : props.SEX === 2 ? '♀' : null,
      exposure_group:   props.Exposure_Group || '',
      source_verified_at: new Date().toISOString(),
      // keep originals for reference
      latitude:  null,
      longitude: null,
    };
  }

  function buildPopup(rawProps, coords) {
    var p      = normalise(rawProps);
    var status = p.status;
    var color  = colorForStatus(status.toUpperCase());
    var date   = fmtDate(p.date_reported);
    var lat    = coords ? coords[1].toFixed(4) : '—';
    var lon    = coords ? coords[0].toFixed(4) : '—';

    var sourceLink = p.source && p.source.startsWith('http')
      ? '<a href="' + esc(p.source) + '" target="_blank" rel="noopener" style="color:#38bdf8;">Source ↗</a>'
      : esc(p.source);

    return '<div style="min-width:240px;font-family:system-ui,sans-serif;font-size:13px;line-height:1.6;color:#e2e8f0;">' +
      '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">' +
        '<span style="width:11px;height:11px;border-radius:50%;background:' + color + ';display:inline-block;flex-shrink:0;box-shadow:0 0 6px ' + color + ';"></span>' +
        '<strong style="font-size:14px;color:#f1f5f9;">' + esc(p.location_name) + '</strong>' +
      '</div>' +
      '<table style="width:100%;border-collapse:collapse;font-size:12px;">' +
        '<tr><td style="color:#64748b;padding:2px 0;width:100px;">Case #</td><td>' + esc(p.case_id) + '</td></tr>' +
        '<tr><td style="color:#64748b;padding:2px 0;">Status</td><td style="color:' + color + ';font-weight:600;">' + esc(status) + '</td></tr>' +
        (p.age  ? '<tr><td style="color:#64748b;padding:2px 0;">Age</td><td>' + esc(p.age) + (p.sex ? ' ' + p.sex : '') + '</td></tr>' : '') +
        '<tr><td style="color:#64748b;padding:2px 0;">Onset</td><td>' + date + '</td></tr>' +
        (p.exposure_group ? '<tr><td style="color:#64748b;padding:2px 0;">Group</td><td>' + esc(p.exposure_group) + '</td></tr>' : '') +
        '<tr><td style="color:#64748b;padding:2px 0;">Coords</td><td style="font-size:11px;color:#475569;">' + lat + ', ' + lon + '</td></tr>' +
        '<tr><td style="color:#64748b;padding:2px 0;">Source</td><td style="font-size:11px;">' + sourceLink + '</td></tr>' +
      '</table>' +
      (p.notes ? '<div style="margin-top:8px;padding-top:8px;border-top:1px solid #1e2d45;font-size:11px;color:#94a3b8;line-height:1.5;">' + esc(p.notes) + '</div>' : '') +
    '</div>';
  }

  function createMarker(feature) {
    var props  = feature.properties;
    var coords = feature.geometry.coordinates;
    var latlng = L.latLng(coords[1], coords[0]);
    var status = (props.STATUS || props.status || '').toUpperCase();
    var color  = colorForStatus(status);

    var marker = L.circleMarker(latlng, {
      radius:      status === 'DECEASED' ? 10 : 8,
      fillColor:   color,
      color:       status === 'DECEASED' ? '#c4b5fd' : 'rgba(255,255,255,0.15)',
      weight:      status === 'DECEASED' ? 2 : 1,
      opacity:     1,
      fillOpacity: status === 'MONITORING' ? 0.5 : 0.85,
      title:       (props.LASTLOCATION || props.location_name || '') + ' — ' + titleCase(props.STATUS || props.status || ''),
    });

    // Pulse effect for confirmed/deceased
    if (status === 'CONFIRMED' || status === 'DECEASED') {
      var icon = L.divIcon({
        className: '',
        html: '<div class="pulse-marker" style="background:' + color + ';color:' + color + ';" ' +
              'role="img" aria-label="' + esc(props.LASTLOCATION || '') + ', ' + titleCase(props.STATUS || '') + '"></div>',
        iconSize: [14, 14],
        iconAnchor: [7, 7],
        popupAnchor: [0, -12],
      });
      marker = L.marker(latlng, { icon: icon });
    }

    marker.bindPopup(buildPopup(props, coords), { maxWidth: 340 });
    return marker;
  }

  function updateVisibleCount(n) {
    var el = document.getElementById('visible-count');
    if (el) el.textContent = n;
  }

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

  function initMap() {
    var map = L.map('map', {
      center: [20, 0], zoom: 2, minZoom: 2, maxZoom: 18, zoomControl: false,
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a> · Data: <a href="https://www.arcgis.com/apps/dashboards/5c68442d2afc42d7ba2696e4cd393729" target="_blank">ANDV Dashboard</a>',
      subdomains: 'abcd', maxZoom: 19,
    }).addTo(map);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    var clusterGroup = L.markerClusterGroup({
      maxClusterRadius: 60,
      showCoverageOnHover: false,
      spiderfyOnMaxZoom: true,
      iconCreateFunction: function (cluster) {
        var n = cluster.getChildCount();
        var size = n >= 20 ? 44 : n >= 10 ? 38 : 32;
        return L.divIcon({
          html: '<div style="width:' + size + 'px;height:' + size + 'px;border-radius:50%;' +
                'background:rgba(59,130,246,0.2);border:2px solid rgba(59,130,246,0.6);' +
                'display:flex;align-items:center;justify-content:center;' +
                'color:#93c5fd;font-weight:700;font-size:' + (n >= 10 ? 12 : 13) + 'px;' +
                'box-shadow:0 0 12px rgba(59,130,246,0.3);" aria-label="' + n + ' cases">' + n + '</div>',
          className: '', iconSize: [size, size], iconAnchor: [size/2, size/2],
        });
      },
    });
    map.addLayer(clusterGroup);

    window.mapState.map = map;
    window.mapState.clusterGroup = clusterGroup;
    return map;
  }

  function addHondiusRoute(map) {
    L.polyline(MV_HONDIUS_ROUTE, {
      color: '#38bdf8', weight: 2, opacity: 0.7, dashArray: '10 8',
    }).addTo(map).bindTooltip('🚢 MV Hondius voyage route (Apr–May 2026)', { sticky: true });

    [[0, '🛳 Departure: Ushuaia, Argentina (Apr 1)', 'right'],
     [MV_HONDIUS_ROUTE.length - 1, '🏁 Arrival: Tenerife, Canary Islands (May 10)', 'left']
    ].forEach(function (item) {
      L.circleMarker(MV_HONDIUS_ROUTE[item[0]], {
        radius: 5, fillColor: '#38bdf8', color: '#0ea5e9', weight: 1.5, fillOpacity: 0.9,
      }).addTo(map).bindTooltip(item[1], { direction: item[2] });
    });
  }

  function showError(msg) {
    var el = document.getElementById('map');
    if (!el) return;
    var d = document.createElement('div');
    d.setAttribute('role', 'alert');
    d.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);' +
      'background:#111827;border:1px solid #ef4444;padding:20px;border-radius:10px;' +
      'text-align:center;z-index:1000;color:#fca5a5;max-width:300px;';
    d.innerHTML = '<p style="font-weight:700;margin-bottom:6px;">⚠ Could not load case data</p>' +
      '<p style="font-size:12px;color:#94a3b8;">' + msg + '</p>';
    el.appendChild(d);
  }

  function onDataLoaded(geojson, source) {
    var features = geojson.features || [];
    var now = new Date().toISOString();

    // Build metadata from ArcGIS data
    var metadata = geojson.metadata || {
      generated_at: now,
      source_timestamps: { 'ANDV Dashboard (ArcGIS)': now },
      data_source: 'ArcGIS Feature Service — ANDV Hantavirus 2026',
      data_source_url: 'https://www.arcgis.com/apps/dashboards/5c68442d2afc42d7ba2696e4cd393729',
      total_cases: features.length,
    };

    // Normalise properties so filters.js works with both ArcGIS and local data
    features = features.map(function (f) {
      var p = f.properties;
      // Add lowercase aliases so filters work
      p.status        = titleCase(p.STATUS || p.status || 'Unknown');
      p.location_name = p.LASTLOCATION || p.location_name || 'Unknown';
      p.date_reported = p.ONSET        || p.date_reported || null;
      p.source        = p.SOURCE       || p.source        || 'ArcGIS';
      p.virus_strain  = 'Andes';
      p.notes         = p.DETAILS      || p.notes         || '';
      return f;
    });

    console.log('[map.js] Loaded ' + features.length + ' cases from ' + source);
    window.mapState.allFeatures = features;
    window.renderMarkers(features);
    document.dispatchEvent(new CustomEvent('geojsonloaded', { detail: { metadata: metadata, features: features } }));
  }

  function loadData() {
    // Try ArcGIS live API first
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
        // Fallback to local snapshot
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

  document.addEventListener('DOMContentLoaded', function () {
    var map = initMap();
    addHondiusRoute(map);
    loadData();
  });
})();
