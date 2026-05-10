/**
 * map.js — Leaflet map initialization, marker rendering, and overlays
 * for the Live Hantavirus Global Tracker.
 *
 * Exports (on window):
 *   window.mapState  — { allFeatures, clusterGroup, map }
 *   window.renderMarkers(features) — clears and re-renders markers
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Shared state — consumed by filters.js and ui.js
  // ---------------------------------------------------------------------------
  window.mapState = {
    allFeatures: [],
    clusterGroup: null,
    map: null,
  };

  // ---------------------------------------------------------------------------
  // MV Hondius voyage route coordinates [lat, lon]
  // Ushuaia → Falklands → South Georgia → Ascension → Saint Helena →
  // São Tomé → Cape Verde → Canary Islands
  // ---------------------------------------------------------------------------
  const MV_HONDIUS_ROUTE = [
    [-54.8, -68.3],
    [-51.7, -59.0],
    [-54.2, -36.5],
    [-37.1, -12.3],
    [-15.9,  -5.7],
    [ -7.9, -14.4],
    [ 14.9, -23.5],
    [ 28.1, -15.4],
  ];

  // ---------------------------------------------------------------------------
  // Marker color helpers
  // ---------------------------------------------------------------------------
  const STATUS_COLORS = {
    Confirmed: '#dc2626',  // red-600
    Probable:  '#ea580c',  // orange-600
    Suspected: '#ca8a04',  // yellow-600
  };

  /**
   * Returns the fill color for a given case status.
   * @param {string} status
   * @returns {string} hex color
   */
  function colorForStatus(status) {
    return STATUS_COLORS[status] || '#6b7280'; // gray fallback
  }

  /**
   * Scales marker radius based on case count.
   * Individual cases default to radius 8; clusters handled by markercluster.
   * @param {number|null} count
   * @returns {number} radius in pixels
   */
  function radiusForCount(count) {
    if (!count || count <= 1) return 8;
    const MIN_R = 8;
    const MAX_R = 30;
    // Logarithmic scale: count 1→8, count 100→30
    const scaled = MIN_R + (MAX_R - MIN_R) * (Math.log(count) / Math.log(100));
    return Math.min(MAX_R, Math.max(MIN_R, scaled));
  }

  // ---------------------------------------------------------------------------
  // Popup content builder
  // ---------------------------------------------------------------------------
  /**
   * Builds accessible HTML popup content for a GeoJSON feature.
   * @param {object} props — feature.properties
   * @returns {string} HTML string
   */
  function buildPopupHTML(props) {
    const status = props.status || 'Unknown';
    const statusColor = colorForStatus(status);
    const dateStr = props.date_reported
      ? new Date(props.date_reported).toLocaleDateString('en-GB', {
          year: 'numeric', month: 'long', day: 'numeric',
        })
      : 'Unknown date';

    return `
      <div style="min-width:220px;font-family:system-ui,sans-serif;font-size:13px;line-height:1.5;">
        <h3 style="margin:0 0 6px;font-size:14px;font-weight:700;color:#111;">
          ${escapeHTML(props.location_name || 'Unknown location')}
        </h3>
        <p style="margin:2px 0;">
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;
                       background:${statusColor};margin-right:5px;vertical-align:middle;"
                aria-hidden="true"></span>
          <strong>Status:</strong> ${escapeHTML(status)}
        </p>
        <p style="margin:2px 0;"><strong>Date reported:</strong> ${escapeHTML(dateStr)}</p>
        <p style="margin:2px 0;"><strong>Source:</strong> ${escapeHTML(props.source || 'Unknown')}</p>
        <p style="margin:2px 0;"><strong>Virus strain:</strong> ${escapeHTML(props.virus_strain || 'Unknown')}</p>
        ${props.notes ? `<p style="margin:6px 0 0;font-size:12px;color:#555;border-top:1px solid #e5e7eb;padding-top:5px;">${escapeHTML(props.notes)}</p>` : ''}
      </div>
    `;
  }

  /**
   * Minimal HTML escaping to prevent XSS in popup content.
   * @param {string} str
   * @returns {string}
   */
  function escapeHTML(str) {
    if (typeof str !== 'string') return String(str);
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // ---------------------------------------------------------------------------
  // Marker factory
  // ---------------------------------------------------------------------------
  /**
   * Creates a Leaflet marker for a GeoJSON feature.
   * Andes virus cases get a pulsing DivIcon ring; others get a circleMarker.
   * @param {object} feature — GeoJSON Feature
   * @returns {L.CircleMarker|L.Marker}
   */
  function createMarker(feature) {
    const props = feature.properties;
    const coords = feature.geometry.coordinates; // [lon, lat]
    const latlng = L.latLng(coords[1], coords[0]);
    const status = props.status || 'Unknown';
    const color = colorForStatus(status);
    const radius = radiusForCount(props.case_count || 1);
    const isAndes = props.virus_strain === 'Andes';

    let marker;

    if (isAndes) {
      // Pulsing DivIcon for Andes virus cases
      const icon = L.divIcon({
        className: '',
        html: `<div class="pulse-ring" role="img"
                    aria-label="Andes virus case at ${escapeHTML(props.location_name || 'unknown location')}, status: ${escapeHTML(status)}">
               </div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8],
        popupAnchor: [0, -10],
      });
      marker = L.marker(latlng, { icon });
    } else {
      marker = L.circleMarker(latlng, {
        radius,
        fillColor: color,
        color: '#fff',
        weight: 1.5,
        opacity: 0.9,
        fillOpacity: 0.85,
        // Accessible title for screen readers
        title: `${props.location_name || 'Case'} — ${status}`,
      });
    }

    // Bind popup
    marker.bindPopup(buildPopupHTML(props), {
      maxWidth: 300,
      className: 'hanta-popup',
    });

    // Keyboard accessibility: open popup on Enter/Space
    marker.on('keydown', function (e) {
      if (e.originalEvent.key === 'Enter' || e.originalEvent.key === ' ') {
        this.openPopup();
      }
    });

    return marker;
  }

  // ---------------------------------------------------------------------------
  // renderMarkers — exported on window, called by filters.js
  // ---------------------------------------------------------------------------
  /**
   * Clears the cluster group and re-renders markers from the given feature array.
   * @param {Array} features — array of GeoJSON Feature objects
   */
  window.renderMarkers = function renderMarkers(features) {
    const { clusterGroup } = window.mapState;
    if (!clusterGroup) return;

    clusterGroup.clearLayers();

    features.forEach(function (feature) {
      if (
        !feature.geometry ||
        !feature.geometry.coordinates ||
        feature.geometry.coordinates.length < 2
      ) return;

      const marker = createMarker(feature);
      clusterGroup.addLayer(marker);
    });
  };

  // ---------------------------------------------------------------------------
  // Map initialization
  // ---------------------------------------------------------------------------
  function initMap() {
    const map = L.map('map', {
      center: [20, 0],
      zoom: 2,
      minZoom: 2,
      maxZoom: 18,
      zoomControl: true,
    });

    // OpenStreetMap tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    // Marker cluster group
    const clusterGroup = L.markerClusterGroup({
      maxClusterRadius: 80,
      showCoverageOnHover: false,
      iconCreateFunction: function (cluster) {
        const count = cluster.getChildCount();
        let size = 'small';
        if (count >= 10) size = 'medium';
        if (count >= 50) size = 'large';
        return L.divIcon({
          html: `<div aria-label="${count} cases in this area"><span>${count}</span></div>`,
          className: `marker-cluster marker-cluster-${size}`,
          iconSize: L.point(40, 40),
        });
      },
    });
    map.addLayer(clusterGroup);

    // Store references
    window.mapState.map = map;
    window.mapState.clusterGroup = clusterGroup;

    return map;
  }

  // ---------------------------------------------------------------------------
  // MV Hondius route overlay
  // ---------------------------------------------------------------------------
  function addHondiusRoute(map) {
    const polyline = L.polyline(MV_HONDIUS_ROUTE, {
      color: '#3b82f6',       // blue-500
      weight: 2,
      opacity: 0.7,
      dashArray: '8, 6',
    });

    polyline.bindTooltip('MV Hondius voyage route (Apr–May 2026)', {
      permanent: false,
      direction: 'top',
      className: 'hondius-tooltip',
    });

    polyline.addTo(map);
    return polyline;
  }

  // ---------------------------------------------------------------------------
  // Data loading
  // ---------------------------------------------------------------------------
  function loadGeoJSON() {
    fetch('data/cases.geojson')
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Failed to fetch cases.geojson: ' + response.status);
        }
        return response.json();
      })
      .then(function (geojson) {
        const features = geojson.features || [];
        const metadata = geojson.metadata || {};

        // Store all features for filtering
        window.mapState.allFeatures = features;

        // Initial render — all features
        window.renderMarkers(features);

        // Notify ui.js and filters.js that data is ready
        const event = new CustomEvent('geojsonloaded', {
          detail: { metadata, features },
        });
        document.dispatchEvent(event);
      })
      .catch(function (err) {
        console.error('[map.js] Error loading GeoJSON:', err);
        // Show a user-visible error in the map container
        const mapEl = document.getElementById('map');
        if (mapEl) {
          const errDiv = document.createElement('div');
          errDiv.setAttribute('role', 'alert');
          errDiv.style.cssText =
            'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);' +
            'background:#fff;padding:16px;border-radius:8px;text-align:center;z-index:1000;' +
            'box-shadow:0 4px 12px rgba(0,0,0,0.3);max-width:300px;';
          errDiv.innerHTML =
            '<p style="color:#dc2626;font-weight:bold;">⚠ Could not load case data</p>' +
            '<p style="color:#374151;font-size:13px;margin-top:4px;">Please check your connection and refresh.</p>';
          mapEl.appendChild(errDiv);
        }
      });
  }

  // ---------------------------------------------------------------------------
  // Bootstrap
  // ---------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    const map = initMap();
    addHondiusRoute(map);
    loadGeoJSON();
  });

})();
