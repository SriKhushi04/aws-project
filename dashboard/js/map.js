/**
 * AWS Smart Waste Monitoring System - Leaflet Map Integration
 */

let mapInstance = null;
let binMarkersLayer = null;
let routePolylineLayer = null;
let depotMarkerLayer = null;

/**
 * Initialize Leaflet map and tile layers.
 */
function initMap(containerId = "map") {
  const config = window.API_CONFIG || {};
  const center = config.mapCenter || [12.9702, 79.1595]; // VIT Vellore
  const zoom = config.mapZoom || 16;

  if (mapInstance) {
    return mapInstance;
  }

  // Create Leaflet map
  mapInstance = L.map(containerId, {
    zoomControl: true,
    scrollWheelZoom: true
  }).setView(center, zoom);

  // Add OpenStreetMap tile layer
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(mapInstance);

  // Initialize feature layer groups
  binMarkersLayer = L.layerGroup().addTo(mapInstance);
  routePolylineLayer = L.layerGroup().addTo(mapInstance);
  depotMarkerLayer = L.layerGroup().addTo(mapInstance);

  return mapInstance;
}

/**
 * Get visual configuration for a bin based on fill level.
 */
function getBinStatus(fillLevel) {
  const thresholds = (window.API_CONFIG && window.API_CONFIG.thresholds) || { warning: 50.0, critical: 85.0 };
  const fill = Number(fillLevel) || 0.0;

  if (fill >= thresholds.critical) {
    return {
      category: "critical",
      label: "Critical",
      color: "#ef4444",
      fillColor: "#ef4444",
      className: ""
    };
  } else if (fill >= thresholds.warning) {
    return {
      category: "warning",
      label: "Warning",
      color: "#f59e0b",
      fillColor: "#f59e0b",
      className: ""
    };
  } else {
    return {
      category: "normal",
      label: "Normal",
      color: "#10b981",
      fillColor: "#10b981",
      className: ""
    };
  }
}

// Cache of markers indexed by stable bin_id: Map<string, L.CircleMarker>
const binMarkersMap = new Map();

/**
 * Render all monitored waste bins on the Leaflet map.
 * Updates existing markers in-place using their stable bin_id without recreating them.
 */
function renderBins(bins) {
  if (!mapInstance || !binMarkersLayer) return;

  if (!bins || !Array.isArray(bins)) {
    binMarkersLayer.clearLayers();
    binMarkersMap.clear();
    return;
  }

  const currentBinIds = new Set();

  bins.forEach((bin) => {
    const binId = bin.bin_id;
    if (!binId) return;

    const lat = Number(bin.latitude);
    const lon = Number(bin.longitude);
    if (isNaN(lat) || isNaN(lon)) return;

    currentBinIds.add(binId);

    const fill = Number(bin.fill_level) || 0.0;
    const status = getBinStatus(fill);

    // Format hours to 90%
    let predText = "Normal (No overflow)";
    if (bin.predicted_hours_to_90 !== null && bin.predicted_hours_to_90 !== undefined) {
      predText = `${Number(bin.predicted_hours_to_90).toFixed(1)} hrs`;
    }

    // Format last updated
    const updatedTime = bin.last_updated ? new Date(bin.last_updated).toLocaleTimeString() : "Just now";

    // Bind rich popup
    const popupHtml = `
      <div style="font-family: inherit; min-width: 180px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <strong style="font-size: 14px;">${bin.bin_id}</strong>
          <span style="font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 9999px; background: ${status.fillColor}; color: #fff;">
            ${status.label}
          </span>
        </div>
        <div style="font-size: 12px; color: #475569; margin-bottom: 6px;">
          ${bin.location_name || "Campus Location"}
        </div>
        <div style="margin-bottom: 6px;">
          <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 2px;">
            <span>Fill Level:</span>
            <strong>${fill.toFixed(1)}%</strong>
          </div>
          <div style="width: 100%; height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden;">
            <div style="width: ${fill}%; height: 100%; background: ${status.fillColor};"></div>
          </div>
        </div>
        <div style="font-size: 11px; color: #334155;">
          <div>Est. to 90%: <strong>${predText}</strong></div>
          <div>Alert Triggered: <strong>${bin.alerted ? "Yes (Active)" : "No"}</strong></div>
          <div style="color: #64748b; margin-top: 4px; font-size: 10px;">Updated: ${updatedTime}</div>
        </div>
      </div>
    `;

    if (binMarkersMap.has(binId)) {
      // Update existing marker in-place without recreating or shifting position
      const marker = binMarkersMap.get(binId);

      // Keep fixed physical location
      marker.setLatLng([lat, lon]);

      // Update marker appearance based on latest fill level & alert status
      marker.setStyle({
        radius: 9,
        fillColor: status.fillColor,
        color: "#ffffff",
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9,
        className: status.className
      });

      // Synchronize CSS animation class on the SVG path element
      const pathEl = marker.getElement ? marker.getElement() : marker._path;
      if (pathEl) {
        if (status.className) {
          pathEl.classList.add(status.className);
        } else {
          pathEl.classList.remove("pulse-marker");
        }
      }

      // Update popup content without closing open popups
      if (marker.getPopup()) {
        marker.setPopupContent(popupHtml);
      } else {
        marker.bindPopup(popupHtml);
      }
    } else {
      // Create new marker on initial discovery
      const marker = L.circleMarker([lat, lon], {
        radius: 9,
        fillColor: status.fillColor,
        color: "#ffffff",
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9,
        className: status.className
      });

      marker.bindPopup(popupHtml);
      binMarkersLayer.addLayer(marker);
      binMarkersMap.set(binId, marker);
    }
  });

  // Remove any markers for bins that are no longer returned by the API
  for (const [binId, marker] of binMarkersMap.entries()) {
    if (!currentBinIds.has(binId)) {
      binMarkersLayer.removeLayer(marker);
      binMarkersMap.delete(binId);
    }
  }
}

/**
 * Render the optimized collection route and depot marker.
 */
function renderRoute(routeData) {
  if (!mapInstance || !routePolylineLayer || !depotMarkerLayer) return;

  routePolylineLayer.clearLayers();
  depotMarkerLayer.clearLayers();

  if (!routeData) return;

  const depot = routeData.depot;
  const stops = routeData.stops || [];

  // 1. Render Depot Marker
  if (depot && depot.latitude && depot.longitude) {
    const depotIcon = L.divIcon({
      className: "depot-map-icon",
      html: `
        <div style="background-color: #1e293b; color: white; width: 28px; height: 28px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); border: 2px solid #ffffff;">
          🏢
        </div>
      `,
      iconSize: [28, 28],
      iconAnchor: [14, 14]
    });

    const depotMarker = L.marker([Number(depot.latitude), Number(depot.longitude)], { icon: depotIcon })
      .bindPopup(`
        <strong>${depot.name || "Central Maintenance Depot"}</strong><br/>
        <span style="font-size: 11px; color: #64748b;">Route Starting & Finishing Base</span>
      `);
    depotMarkerLayer.addLayer(depotMarker);
  }

  // 2. Render Collection Stops & Path Polyline
  if (stops.length > 0 && depot) {
    const pathCoordinates = [];

    // Start at depot
    pathCoordinates.push([Number(depot.latitude), Number(depot.longitude)]);

    // Sequence of stops
    stops.forEach((stop, index) => {
      const stopLat = Number(stop.latitude);
      const stopLon = Number(stop.longitude);
      pathCoordinates.push([stopLat, stopLon]);

      // Add numbered stop icon
      const stopIcon = L.divIcon({
        className: "stop-number-icon",
        html: `
          <div style="background-color: #2563eb; color: #ffffff; width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; border: 2px solid #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.4);">
            ${index + 1}
          </div>
        `,
        iconSize: [20, 20],
        iconAnchor: [10, 10]
      });

      const stopMarker = L.marker([stopLat, stopLon], { icon: stopIcon })
        .bindPopup(`
          <strong>Stop #${index + 1}: ${stop.bin_id}</strong><br/>
          <span>${stop.location_name || ""}</span><br/>
          <span>Fill: <strong>${Number(stop.fill_level || 0).toFixed(1)}%</strong></span>
        `);
      routePolylineLayer.addLayer(stopMarker);
    });

    // Return to depot
    pathCoordinates.push([Number(depot.latitude), Number(depot.longitude)]);

    // Draw route polyline
    const polyline = L.polyline(pathCoordinates, {
      color: "#2563eb",
      weight: 4,
      opacity: 0.8,
      dashArray: "6, 6"
    });
    routePolylineLayer.addLayer(polyline);
  }
}

