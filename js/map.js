/**
 * map.js — Leaflet map for the Live Hantavirus Global Tracker.
 * Dark tile layer, styled markers, MV Hondius route, cluster group.
 */
(function () {
  'use strict';

  window.mapState = { allFeatures: [], clusterGroup: null, map: null };

  const MV_HONDIUS_ROUTE = [
    [-54.8, -68.3], [-51.7, -59.0], [-54.2, -36.5],
    [-37.1, -12.3], [-15.9,  -5.7], [ -7.9, -14.4],
    [ 14.9, -23.5], [ 28.1, -15.4],
  ];

  const STATUS_COLORS = {
    Confirmed: '#ef4444',
    Probable:  '#f97316',
    Suspected: '#eab308',
  };

  function colorForStatus(s) { return STATUS_COLORS[s] || '#94a3b8'; }

  function esc(str) {
    if (typeof str !== 'string') return String(str);
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
              .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  function buildPopup(props) {
    const status = props.status || 'Unknown';
    const color  = colorForStatus(status);
    const date   = props.date_reported
      ? new Date(props.date_reported).toLocaleDateString('en-GB', { year:'numeric', month:'short', day:'numeric' })
      : '—';
    const isAndes = props.virus_strain === 'Andes';

    return `<div style="min-width:230px;font-family:system-ui,sans-serif;font-size:13px;line-height:1.6;color:#e2e8f0;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <span style="width:10px;height:10px;border-radius:50%;background:${color};display:inline-block;flex-shrink:0;${isAndes?'box-shadow:0 0 6px '+color+';':''}"></span>
        <strong style="font-size:14px;color:#f1f5f9;">${esc(props.location_name || 'Unknown')}</strong>
      </div>
      <table style="width:100%;border-collapse:collapse;font-size:12px;">
        <tr><td style="color:#64748b;padding:2px 0;width:90px;">Status</td>
            <td style="color:${color};font-weight:600;">${esc(status)}</td></tr>
        <tr><td style="color:#64748b;padding:2px 0;">Date</td>
            <td>${esc(date)}</td></tr>
        <tr><td style="color:#64748b;padding:2px 0;">Source</td>
            <td>${esc(props.source || '—')}</td></tr>
        <tr><td style="color:#64748b;padding:2px 0;">Strain</td>
            <td style="color:${isAndes?'#f87171':'#e2e8f0'};font-weight:${isAndes?'600':'400'};">${esc(props.virus_strain || '—')}</td></tr>
      </table>
      ${props.notes ? `<div style="margin-top:8px;padding-top:8px;border-top:1px solid #1e2d45;font-size:11px;color:#94a3b8;line-height:1.5;">${esc(props.notes)}</div>` : ''}
    </div>`;
  }

  function createMarker(feature) {
    const props  = feature.properties;
    const coords = feature.geometry.coordinates;
    const latlng = L.latLng(coords[1], coords[0]);
    const status = props.status || 'Unknown';
    const color  = colorForStatus(status);
    const isAndes = props.virus_strain === 'Andes';

    let marker;

    if (isAndes) {
      const icon = L.divIcon({
        className: '',
        html: `<div class="pulse-marker" style="background:${color};color:${color};"
                    role="img" aria-label="${esc(props.location_name||'')}, ${esc(status)}, Andes virus"></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7],
        popupAnchor: [0, -12],
      });
      marker = L.marker(latlng, { icon });
    } else {
      marker = L.circleMarker(latlng, {
        radius: 8,
        fillColor: color,
        color: 'rgba(255,255,255,0.2)',
        weight: 1,
        opacity: 1,
        fillOpacity: 0.85,
        title: `${props.location_name || ''} — ${status}`,
      });
    }

    marker.bindPopup(buildPopup(props), { maxWidth: 320 });
    return marker;
  }

  function updateVisibleCount(n) {
    const el = document.getElementById('visible-count');
    if (el) el.textContent = n;
  }

  window.renderMarkers = function (features) {
    const cg = window.mapState.clusterGroup;
    if (!cg) return;
    cg.clearLayers();
    features.forEach(function (f) {
      if (!f.geometry || !f.geometry.coordinates || f.geometry.coordinates.length < 2) return;
      cg.addLayer(createMarker(f));
    });
    updateVisibleCount(features.length);
  };

  function initMap() {
    const map = L.map('map', {
      center: [20, 0],
      zoom: 2,
      minZoom: 2,
      maxZoom: 18,
      zoomControl: false,
    });

    // Dark tile layer (CartoDB Dark Matter)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map);

    // Zoom control bottom-right
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    // Cluster group with dark styling
    const clusterGroup = L.markerClusterGroup({
      maxClusterRadius: 60,
      showCoverageOnHover: false,
      spiderfyOnMaxZoom: true,
      iconCreateFunction: function (cluster) {
        const n = cluster.getChildCount();
        const size = n >= 20 ? 44 : n >= 10 ? 38 : 32;
        return L.divIcon({
          html: `<div style="
            width:${size}px;height:${size}px;border-radius:50%;
            background:rgba(59,130,246,0.2);
            border:2px solid rgba(59,130,246,0.6);
            display:flex;align-items:center;justify-content:center;
            color:#93c5fd;font-weight:700;font-size:${n>=10?12:13}px;
            box-shadow:0 0 12px rgba(59,130,246,0.3);
          " aria-label="${n} cases">${n}</div>`,
          className: '',
          iconSize: [size, size],
          iconAnchor: [size/2, size/2],
        });
      },
    });
    map.addLayer(clusterGroup);

    window.mapState.map = map;
    window.mapState.clusterGroup = clusterGroup;
    return map;
  }

  function addHondiusRoute(map) {
    // Animated dashed route
    const line = L.polyline(MV_HONDIUS_ROUTE, {
      color: '#38bdf8',
      weight: 2,
      opacity: 0.7,
      dashArray: '10 8',
    }).addTo(map);

    line.bindTooltip('🚢 MV Hondius voyage route (Apr–May 2026)', {
      sticky: true,
      className: '',
    });

    // Waypoint dots
    MV_HONDIUS_ROUTE.forEach(function (coord, i) {
      const isFirst = i === 0;
      const isLast  = i === MV_HONDIUS_ROUTE.length - 1;
      if (isFirst || isLast) {
        L.circleMarker(coord, {
          radius: isFirst || isLast ? 5 : 3,
          fillColor: '#38bdf8',
          color: '#0ea5e9',
          weight: 1.5,
          fillOpacity: 0.9,
        }).addTo(map).bindTooltip(
          isFirst ? '🛳 Departure: Ushuaia, Argentina (Apr 1)' : '🏁 Arrival: Tenerife, Canary Islands (May 10)',
          { direction: isFirst ? 'right' : 'left' }
        );
      }
    });
  }

  function loadGeoJSON() {
    fetch('data/cases.geojson')
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (geojson) {
        const features = geojson.features || [];
        const metadata = geojson.metadata || {};
        window.mapState.allFeatures = features;
        window.renderMarkers(features);
        document.dispatchEvent(new CustomEvent('geojsonloaded', { detail: { metadata, features } }));
      })
      .catch(function (err) {
        console.error('[map.js] Failed to load GeoJSON:', err);
        const el = document.getElementById('map');
        if (el) {
          const d = document.createElement('div');
          d.setAttribute('role', 'alert');
          d.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:#111827;border:1px solid #ef4444;padding:20px;border-radius:10px;text-align:center;z-index:1000;color:#fca5a5;max-width:280px;';
          d.innerHTML = '<p style="font-weight:700;margin-bottom:6px;">⚠ Could not load case data</p><p style="font-size:12px;color:#94a3b8;">Check your connection and refresh the page.</p>';
          el.appendChild(d);
        }
      });
  }

  document.addEventListener('DOMContentLoaded', function () {
    const map = initMap();
    addHondiusRoute(map);
    loadGeoJSON();
  });
})();
