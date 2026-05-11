/**
 * map.js v3.0 — Hantavirus Tracker
 * Live data from ArcGIS ANDV Hantavirus 2026 Feature Service
 * All cases shown at every zoom level, UNKNOWN locations resolved
 */
(function () {
  'use strict';

  window.mapState = { allFeatures: [], clusterGroup: null, map: null };

  var ARCGIS_URL =
    'https://services1.arcgis.com/wb4Og4gH5mvzQAIV/arcgis/rest/services/' +
    'Tracking_Hantavirus_2026/FeatureServer/1/query' +
    '?where=1%3D1&outFields=*&f=geojson&returnGeometry=true' +
    '&orderByFields=CASE_%20ASC&resultRecordCount=500';

  var MV_HONDIUS_ROUTE = [
    [-54.8,-68.3],[-51.7,-59.0],[-54.2,-36.5],[-37.1,-12.3],
    [-15.9,-5.7],[-7.9,-14.4],[14.9,-23.5],[28.1,-15.4]
  ];

  var STATUS_COLORS = {
    CONFIRMED:  '#ef4444',
    SUSPECTED:  '#f97316',
    DECEASED:   '#8b5cf6',
    MONITORING: '#0ea5e9',
    UNKNOWN:    '#64748b'
  };

  // LOC lookup table — [lat, lon] — 50+ locations
  var LOC = {
    'ITALY':              [41.9,  12.5],
    'FINLAND':            [61.9,  25.7],
    'DENMARK':            [56.0,  10.0],
    'SWEDEN':             [59.3,  18.1],
    'SPAIN':              [40.4,  -3.7],
    'FRANCE':             [46.2,   2.2],
    'GERMANY':            [51.2,  10.5],
    'NETHERLANDS':        [52.1,   5.3],
    'BELGIUM':            [50.5,   4.5],
    'SWITZERLAND':        [47.4,   8.5],
    'UNITED KINGDOM':     [51.5,  -0.1],
    'UK':                 [51.5,  -0.1],
    'IRELAND':            [53.4,  -8.2],
    'GREECE':             [39.1,  21.8],
    'TURKEY':             [39.9,  32.9],
    'PORTUGAL':           [39.4,  -8.2],
    'POLAND':             [52.2,  21.0],
    'RUSSIA':             [55.8,  37.6],
    'UKRAINE':            [50.4,  30.5],
    'SOUTH AFRICA':       [-26.2, 28.0],
    'JOHANNESBURG':       [-26.2, 28.0],
    'CAPE TOWN':          [-33.9, 18.4],
    'SINGAPORE':          [1.35, 103.8],
    'AUSTRALIA':          [-25.3, 133.8],
    'NEW ZEALAND':        [-40.9, 174.9],
    'CANADA':             [56.1, -106.3],
    'UNITED STATES':      [37.1,  -95.7],
    'USA':                [37.1,  -95.7],
    'NEBRASKA, USA':      [41.5,  -99.9],
    'NEBRASKA':           [41.5,  -99.9],
    'GEORGIA, USA':       [32.2,  -83.4],
    'GEORGIA':            [32.2,  -83.4],
    'TEXAS':              [31.0, -100.0],
    'CALIFORNIA':         [36.8, -119.4],
    'ARIZONA, USA':       [34.0, -111.1],
    'ARIZONA':            [34.0, -111.1],
    'VIRGINIA':           [37.4,  -78.7],
    'NEW JERSEY':         [40.1,  -74.7],
    'FLORIDA':            [27.7,  -81.5],
    'NEW YORK':           [40.7,  -74.0],
    'ARGENTINA':          [-34.6, -58.4],
    'USHUAIA':            [-54.8, -68.3],
    'JAPAN':              [36.2,  138.3],
    'INDIA':              [20.6,   78.9],
    'PHILIPPINES':        [12.9,  121.8],
    'GUATEMALA':          [15.8,  -90.2],
    'MONTENEGRO':         [42.7,   19.4],
    'NORWAY':             [60.5,    8.5],
    'AUSTRIA':            [47.5,   14.6],
    'CZECH REPUBLIC':     [49.8,   15.5],
    'HUNGARY':            [47.2,   19.5],
    'ROMANIA':            [45.9,   24.9],
    'TRISTAN DA CUNHA':   [-37.1, -12.3],
    'TRISTAN':            [-37.1, -12.3],
    'ST HELENA':          [-15.9,  -5.7],
    'SAINT HELENA':       [-15.9,  -5.7],
    'ASCENSION ISLAND':   [-7.9,  -14.4],
    'PRAIA, CAPE VERDE':  [14.9,  -23.5],
    'CAPE VERDE':         [14.9,  -23.5],
    'ALICANTE, SPAIN':    [38.3,   -0.5],
    'ALICANTE':           [38.3,   -0.5],
    'ZURICH':             [47.4,    8.5],
    'PARIS':              [48.9,    2.3],
    'AMSTERDAM':          [52.4,    4.9],
    'LONDON':             [51.5,   -0.1],
    'BERLIN':             [52.5,   13.4],
    'MADRID':             [40.4,   -3.7],
    'ROME':               [41.9,   12.5],
    'MV HONDIUS':         [28.1,  -15.4],
    'MV HONDUS':          [28.1,  -15.4],
    'TENERIFE':           [28.1,  -15.4],
    'CANARY ISLANDS':     [28.1,  -15.4],
    'SOUTH GEORGIA':      [-54.2, -36.5],
    'FALKLAND ISLANDS':   [-51.7, -59.0],
    'FALKLANDS':          [-51.7, -59.0]
  };

  /**
   * resolveCoords(props, geomCoords)
   * Returns [lon, lat] from geometry if valid WGS84,
   * else looks up LASTLOCATION in LOC,
   * else scans DETAILS text,
   * else returns null.
   */
  function resolveCoords(props, geomCoords) {
    if (geomCoords && geomCoords.length >= 2) {
      var lon = geomCoords[0], lat = geomCoords[1];
      if (lon >= -180 && lon <= 180 && lat >= -90 && lat <= 90 &&
          Math.abs(lon) + Math.abs(lat) > 0.01) {
        return [lon, lat];
      }
    }
    var loc = ((props.LASTLOCATION || props.location_name || '')).toUpperCase().trim();
    var det = (props.DETAILS || '').toUpperCase();
    var keys = Object.keys(LOC);
    // Exact match on location
    if (loc && LOC[loc]) return [LOC[loc][1], LOC[loc][0]];
    // Partial match on location
    for (var i = 0; i < keys.length; i++) {
      if (loc && loc.indexOf(keys[i]) !== -1) return [LOC[keys[i]][1], LOC[keys[i]][0]];
    }
    // Scan DETAILS text
    for (var j = 0; j < keys.length; j++) {
      if (det.indexOf(keys[j]) !== -1) return [LOC[keys[j]][1], LOC[keys[j]][0]];
    }
    return null;
  }

  /**
   * resolveLocationName(props)
   * Returns a proper name, never "UNKNOWN" or "None".
   */
  function resolveLocationName(props) {
    var loc = (props.LASTLOCATION || props.location_name || '').trim();
    if (loc && loc.toUpperCase() !== 'UNKNOWN' && loc !== 'None' && loc !== 'null' && loc !== '') {
      return loc;
    }
    var det = (props.DETAILS || '').toUpperCase();
    var keys = Object.keys(LOC);
    for (var i = 0; i < keys.length; i++) {
      if (det.indexOf(keys[i]) !== -1) {
        var k = keys[i];
        return k.charAt(0) + k.slice(1).toLowerCase();
      }
    }
    return 'Unknown location';
  }

  function colorForStatus(s) {
    return STATUS_COLORS[(s || '').toUpperCase()] || '#94a3b8';
  }

  function titleCase(s) {
    if (!s) return 'Unknown';
    return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
  }

  function esc(s) {
    if (s == null) return '\u2014';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function fmtDate(raw) {
    if (!raw) return '\u2014';
    var d = typeof raw === 'number' ? new Date(raw) : new Date(raw);
    if (isNaN(d)) return String(raw);
    return d.toLocaleDateString('en-GB', { year: 'numeric', month: 'short', day: 'numeric' });
  }

  function updateVisibleCount(n) {
    var el = document.getElementById('visible-count');
    if (el) el.textContent = n;
  }

  /**
   * createMarker(feature)
   * Pulse DivIcon for CONFIRMED/DECEASED, circleMarker for others.
   * On click calls openCasePanel({...}).
   */
  function createMarker(feature) {
    var props  = feature.properties;
    var coords = feature.geometry.coordinates;
    var latlng = L.latLng(coords[1], coords[0]);
    var rawStatus = (props.STATUS || props.status || '').toUpperCase();
    // UNKNOWN treated as Monitoring for display
    var displayStatus = rawStatus === 'UNKNOWN' ? 'MONITORING' : rawStatus;
    var color = colorForStatus(displayStatus);
    var locName = resolveLocationName(props);

    var marker;
    if (rawStatus === 'CONFIRMED' || rawStatus === 'DECEASED') {
      marker = L.marker(latlng, {
        icon: L.divIcon({
          className: '',
          html: '<div class="pulse-marker" style="background:' + color + ';color:' + color + ';" ' +
                'role="img" aria-label="' + esc(locName) + '"></div>',
          iconSize:    [14, 14],
          iconAnchor:  [7, 7],
          popupAnchor: [0, -12]
        })
      });
    } else {
      marker = L.circleMarker(latlng, {
        radius:      rawStatus === 'SUSPECTED' ? 7 : 6,
        fillColor:   color,
        color:       'rgba(255,255,255,0.15)',
        weight:      1,
        opacity:     1,
        fillOpacity: (rawStatus === 'MONITORING' || rawStatus === 'UNKNOWN') ? 0.55 : 0.85,
        title:       locName + ' \u2014 ' + titleCase(rawStatus)
      });
    }

    marker.on('click', function () {
      var p = props;
      var ageSex = '';
      if (p.AGE) ageSex += p.AGE;
      if (p.SEX === 1) ageSex += (ageSex ? ' \u2642' : '\u2642');
      if (p.SEX === 2) ageSex += (ageSex ? ' \u2640' : '\u2640');
      var caseNum = p.CASE_ || p.case_id || p.OBJECTID;
      var statusDisplay = rawStatus === 'UNKNOWN' ? 'Monitoring (Unconfirmed)' : titleCase(rawStatus);
      openCasePanel({
        case_id:        caseNum,
        status:         statusDisplay,
        status_raw:     rawStatus,
        location_name:  locName,
        date_formatted: fmtDate(p.ONSET || p.date_reported),
        age_sex:        ageSex || '\u2014',
        exposure_group: p.Exposure_Group || p.exposure_group || '\u2014',
        notes:          p.DETAILS || p.notes || '',
        source:         p.SOURCE || p.source || '',
        lat:            coords[1].toFixed(4),
        lon:            coords[0].toFixed(4)
      });
    });

    return marker;
  }

  /**
   * window.renderMarkers(features)
   * Resolves coords for each feature, skips null, patches geometry, calls createMarker.
   */
  window.renderMarkers = function (features) {
    var cg = window.mapState.clusterGroup;
    if (!cg) return;
    cg.clearLayers();
    var shown = 0;
    features.forEach(function (f) {
      if (!f.geometry) f.geometry = { type: 'Point', coordinates: [0, 0] };
      var coords = resolveCoords(f.properties, f.geometry.coordinates);
      if (!coords) return;
      f.geometry.coordinates = coords;
      f.properties.location_name = resolveLocationName(f.properties);
      f.properties.status = titleCase(f.properties.STATUS || f.properties.status || 'Unknown');
      cg.addLayer(createMarker(f));
      shown++;
    });
    updateVisibleCount(shown);
  };

  /**
   * initMap()
   * CartoDB dark tiles, zoom control bottom-right,
   * maxBounds, maxBoundsViscosity:1.0,
   * markerClusterGroup with disableClusteringAtZoom:3 and maxClusterRadius:20.
   */
  function initMap() {
    var map = L.map('map', {
      center: [20, 0], zoom: 2, minZoom: 2, maxZoom: 18,
      zoomControl: false, worldCopyJump: false
    });
    map.setMaxBounds([[-85, -180], [85, 180]]);
    map.options.maxBoundsViscosity = 1.0;

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
                   '&copy; <a href="https://carto.com/">CARTO</a> &middot; ' +
                   'Data: <a href="https://www.arcgis.com/apps/dashboards/5c68442d2afc42d7ba2696e4cd393729" ' +
                   'target="_blank">ANDV Dashboard</a>',
      subdomains: 'abcd', maxZoom: 19, noWrap: false
    }).addTo(map);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    var cg = L.markerClusterGroup({
      maxClusterRadius:       20,
      disableClusteringAtZoom: 3,
      showCoverageOnHover:    false,
      spiderfyOnMaxZoom:      true,
      iconCreateFunction: function (cluster) {
        var n  = cluster.getChildCount();
        var sz = n >= 20 ? 40 : n >= 10 ? 34 : 28;
        return L.divIcon({
          html: '<div style="width:' + sz + 'px;height:' + sz + 'px;border-radius:50%;' +
                'background:rgba(59,130,246,0.2);border:2px solid rgba(59,130,246,0.6);' +
                'display:flex;align-items:center;justify-content:center;color:#93c5fd;' +
                'font-weight:700;font-size:' + (n >= 10 ? 11 : 12) + 'px;' +
                'box-shadow:0 0 10px rgba(59,130,246,0.3);">' + n + '</div>',
          className: '', iconSize: [sz, sz], iconAnchor: [sz / 2, sz / 2]
        });
      }
    });
    map.addLayer(cg);
    window.mapState.map = map;
    window.mapState.clusterGroup = cg;
    return map;
  }

  /**
   * addHondiusRoute(map)
   * Cyan dashed polyline with departure/arrival tooltips.
   */
  function addHondiusRoute(map) {
    L.polyline(MV_HONDIUS_ROUTE, {
      color: '#06b6d4', weight: 2, opacity: 0.7, dashArray: '10 8'
    }).addTo(map).bindTooltip('\uD83D\uDEA2 MV Hondius voyage route (Apr\u2013May 2026)', { sticky: true });

    [
      [0,                          '\uD83D\uDEF3 Departure: Ushuaia, Argentina (Apr 1)',       'right'],
      [MV_HONDIUS_ROUTE.length - 1, '\uD83C\uDFC1 Arrival: Tenerife, Canary Islands (May 10)', 'left']
    ].forEach(function (item) {
      L.circleMarker(MV_HONDIUS_ROUTE[item[0]], {
        radius: 5, fillColor: '#06b6d4', color: '#0ea5e9',
        weight: 1.5, fillOpacity: 0.9
      }).addTo(map).bindTooltip(item[1], { direction: item[2] });
    });
  }

  /**
   * normaliseFeature(f)
   * Sets p.status, p.location_name, p.date_reported, p.source, p.virus_strain, p.notes.
   */
  function normaliseFeature(f) {
    var p = f.properties;
    p.status        = titleCase(p.STATUS || p.status || 'Unknown');
    p.location_name = resolveLocationName(p);
    p.date_reported = p.ONSET || p.date_reported || null;
    p.source        = p.SOURCE || p.source || 'ArcGIS';
    p.virus_strain  = 'Andes';
    p.notes         = p.DETAILS || p.notes || '';
    return f;
  }

  /**
   * onDataLoaded(geojson, source)
   * Normalises features, dispatches 'geojsonloaded' event.
   */
  function onDataLoaded(geojson, source) {
    var features = (geojson.features || []).map(normaliseFeature);
    var now = new Date().toISOString();
    var metadata = geojson.metadata || {
      generated_at:       now,
      source_timestamps:  { 'ANDV Dashboard (ArcGIS)': now },
      total_cases:        features.length
    };
    console.log('[map.js] Loaded ' + features.length + ' cases from ' + source);
    window.mapState.allFeatures = features;
    window.renderMarkers(features);
    document.dispatchEvent(new CustomEvent('geojsonloaded', {
      detail: { metadata: metadata, features: features }
    }));
  }

  function showError(msg) {
    var el = document.getElementById('map');
    if (!el) return;
    var d = document.createElement('div');
    d.setAttribute('role', 'alert');
    d.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);' +
      'background:#0f1623;border:1px solid #ef4444;padding:20px 24px;border-radius:10px;' +
      'text-align:center;z-index:1000;color:#fca5a5;max-width:300px;';
    d.innerHTML = '<p style="font-weight:700;margin-bottom:6px;">\u26A0 Could not load case data</p>' +
                  '<p style="font-size:12px;color:#94a3b8;">' + msg + '</p>';
    el.appendChild(d);
  }

  /**
   * loadData()
   * Fetches ArcGIS, falls back to data/cases.geojson.
   */
  function loadData() {
    fetch(ARCGIS_URL)
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (g) {
        if (!g.features || !g.features.length) throw new Error('Empty dataset');
        onDataLoaded(g, 'ArcGIS live');
      })
      .catch(function (err) {
        console.warn('[map.js] ArcGIS failed:', err.message, '\u2014 trying local fallback');
        fetch('data/cases.geojson')
          .then(function (r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
          })
          .then(function (g) { onDataLoaded(g, 'local fallback'); })
          .catch(function () { showError('Check your connection and refresh.'); });
      });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var map = initMap();
    addHondiusRoute(map);
    loadData();
  });

})();
