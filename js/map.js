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
    '?where=1%3D1&outFields=*&f=geojson&returnGeometry=true&orderByFields=CASE_%20ASC&resultRecordCount=500';

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
    UNKNOWN:    '#64748b',
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

  /* ── Location lookup for UNKNOWN/None cases ── */
  var LOCATION_COORDS = {
    'ITALY':          [41.9, 12.5],
    'FINLAND':        [61.9, 25.7],
    'DENMARK':        [56.0, 10.0],
    'SWEDEN':         [59.3, 18.1],
    'SPAIN':          [40.4, -3.7],
    'FRANCE':         [46.2, 2.2],
    'GERMANY':        [51.2, 10.5],
    'NETHERLANDS':    [52.1, 5.3],
    'BELGIUM':        [50.5, 4.5],
    'SWITZERLAND':    [47.4, 8.5],
    'UNITED KINGDOM': [51.5, -0.1],
    'UK':             [51.5, -0.1],
    'IRELAND':        [53.4, -8.2],
    'GREECE':         [39.1, 21.8],
    'TURKEY':         [39.9, 32.9],
    'PORTUGAL':       [39.4, -8.2],
    'POLAND':         [52.2, 21.0],
    'RUSSIA':         [55.8, 37.6],
    'UKRAINE':        [50.4, 30.5],
    'SOUTH AFRICA':   [-26.2, 28.0],
    'JOHANNESBURG':   [-26.2, 28.0],
    'SINGAPORE':      [1.35, 103.8],
    'AUSTRALIA':      [-25.3, 133.8],
    'NEW ZEALAND':    [-40.9, 174.9],
    'CANADA':         [56.1, -106.3],
    'UNITED STATES':  [37.1, -95.7],
    'USA':            [37.1, -95.7],
    'NEBRASKA, USA':  [41.5, -99.9],
    'GEORGIA, USA':   [32.2, -83.4],
    'TEXAS':          [31.0, -100.0],
    'CALIFORNIA':     [36.8, -119.4],
    'ARIZONA, USA':   [34.0, -111.1],
    'VIRGINIA':       [37.4, -78.7],
    'NEW JERSEY':     [40.1, -74.7],
    'ARGENTINA':      [-34.6, -58.4],
    'USHUAIA':        [-54.8, -68.3],
    'JAPAN':          [36.2, 138.3],
    'INDIA':          [20.6, 78.9],
    'PHILIPPINES':    [12.9, 121.8],
    'GUATEMALA':      [15.8, -90.2],
    'MONTENEGRO':     [42.7, 19.4],
    'SAINT KITTS AND NEVIS': [17.3, -62.7],
    'TRISTAN DA CUNHA': [-37.1, -12.3],
    'ST HELENA':      [-15.9, -5.7],
    'PRAIA, CAPE VERDE': [14.9, -23.5],
    'ALICANTE, SPAIN': [38.3, -0.5],
    'ZURICH':         [47.4, 8.5],
    'MV HONDIUS':     [28.1, -15.4],
    'MV HONDUS':      [28.1, -15.4],
  };

  function resolveCoords(props, geomCoords) {
    /* If geometry coords are valid WGS84, use them */
    if (geomCoords && geomCoords.length >= 2) {
      var lon = geomCoords[0], lat = geomCoords[1];
      if (lon >= -180 && lon <= 180 && lat >= -90 && lat <= 90 && (lon !== 0 || lat !== 0)) {
        return geomCoords;
      }
    }
    /* Try to resolve from LASTLOCATION */
    var loc = (props.LASTLOCATION || props.location_name || '').toUpperCase().trim();
    if (loc && LOCATION_COORDS[loc]) {
      var c = LOCATION_COORDS[loc];
      return [c[1], c[0]]; // [lon, lat]
    }
    /* Try partial match */
    var keys = Object.keys(LOCATION_COORDS);
    for (var i = 0; i < keys.length; i++) {
      if (loc.indexOf(keys[i]) !== -1 || keys[i].indexOf(loc) !== -1) {
        var c2 = LOCATION_COORDS[keys[i]];
        return [c2[1], c2[0]];
      }
    }
    /* Try from DETAILS text */
    var details = (props.DETAILS || '').toUpperCase();
    for (var j = 0; j < keys.length; j++) {
      if (details.indexOf(keys[j]) !== -1) {
        var c3 = LOCATION_COORDS[keys[j]];
        return [c3[1], c3[0]];
      }
    }
    return null; // truly unknown, skip
  }

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
    var shown = 0;
    features.forEach(function (f) {
      if (!f.geometry) return;
      var coords = resolveCoords(f.properties, f.geometry.coordinates);
      if (!coords) return; // truly no location data
      /* Patch the geometry so createMarker uses resolved coords */
      f.geometry.coordinates = coords;
      cg.addLayer(createMarker(f));
      shown++;
    });
    updateVisibleCount(shown);
  };

  /* ── Initialise Leaflet map ── */
  function initMap() {
    var map = L.map('map', {
      center:     [20, 0],
      zoom:       2,
      minZoom:    2,
      maxZoom:    18,
      zoomControl: false,
      worldCopyJump: false,
    });

    /* Set bounds after init — more reliable across Leaflet versions */
    map.setMaxBounds([[-85, -180], [85, 180]]);
    map.options.maxBoundsViscosity = 1.0;

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
        '&copy; <a href="https://carto.com/">CARTO</a> · ' +
        'Data: <a href="https://www.arcgis.com/apps/dashboards/5c68442d2afc42d7ba2696e4cd393729" target="_blank">ANDV Dashboard</a> · ' +
        'K. Panozzo, University of Toledo',
      subdomains: 'abcd',
      maxZoom:    19,
      noWrap:     false,
    }).addTo(map);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    /* Cluster group — disable clustering at low zoom so all dots visible */
    var clusterGroup = L.markerClusterGroup({
      maxClusterRadius:        40,
      showCoverageOnHover:     false,
      spiderfyOnMaxZoom:       true,
      disableClusteringAtZoom: 5,
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
    p.status        = titleCase(p.STATUS || p.status || 'Unknown');
    /* For UNKNOWN location, try to infer from DETAILS */
    var loc = p.LASTLOCATION || p.location_name || '';
    if (!loc || loc === 'None' || loc.toUpperCase() === 'UNKNOWN') {
      var details = (p.DETAILS || '').toUpperCase();
      var keys = Object.keys(LOCATION_COORDS);
      for (var i = 0; i < keys.length; i++) {
        if (details.indexOf(keys[i]) !== -1) {
          loc = keys[i].charAt(0) + keys[i].slice(1).toLowerCase();
          break;
        }
      }
    }
    p.location_name = loc || 'Unknown location';
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
