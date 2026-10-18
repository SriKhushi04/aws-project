/**
 * AWS Smart Waste Monitoring System - Dashboard Application Controller
 */

// Application State
const AppState = {
  bins: [],
  route: null,
  isFetching: false,
  pollTimer: null,
  lastUpdated: null,
  activeTab: "route"
};

// Realistic VIT Vellore Demonstration Fallback Dataset
const DEMO_FALLBACK = {
  bins: [
    { bin_id: "BIN-001", location_name: "Periyar Central Library Plaza", latitude: 12.9698, longitude: 79.1559, fill_level: 38.5, alerted: false, predicted_hours_to_90: 10.3, priority_score: 27.0 },
    { bin_id: "BIN-002", location_name: "Technology Tower (TT) Food Court", latitude: 12.9705, longitude: 79.1595, fill_level: 87.2, alerted: true, predicted_hours_to_90: 0.3, priority_score: 95.4 },
    { bin_id: "BIN-003", location_name: "Silver Jubilee Tower (SJT) Entrance", latitude: 12.9718, longitude: 79.1645, fill_level: 76.0, alerted: false, predicted_hours_to_90: 2.0, priority_score: 65.5 },
    { bin_id: "BIN-004", location_name: "Main Building (MB) Quadrangle", latitude: 12.9692, longitude: 79.1560, fill_level: 28.0, alerted: false, predicted_hours_to_90: null, priority_score: 28.0 },
    { bin_id: "BIN-005", location_name: "Anna Auditorium North Gate", latitude: 12.9710, longitude: 79.1637, fill_level: 89.4, alerted: true, predicted_hours_to_90: 0.1, priority_score: 98.2 },
    { bin_id: "BIN-006", location_name: "Gazebo Canteen Hub", latitude: 12.9708, longitude: 79.1578, fill_level: 54.0, alerted: false, predicted_hours_to_90: 5.5, priority_score: 39.0 },
    { bin_id: "BIN-007", location_name: "SMV Academic Block Courtyard", latitude: 12.9700, longitude: 79.1600, fill_level: 42.0, alerted: false, predicted_hours_to_90: 10.6, priority_score: 28.9 },
    { bin_id: "BIN-008", location_name: "Outdoor Stadium Pavilion", latitude: 12.9725, longitude: 79.1580, fill_level: 31.0, alerted: false, predicted_hours_to_90: null, priority_score: 31.0 },
    { bin_id: "BIN-009", location_name: "Men's Hostel Block D Quad", latitude: 12.9730, longitude: 79.1620, fill_level: 86.5, alerted: true, predicted_hours_to_90: 0.4, priority_score: 94.1 },
    { bin_id: "BIN-010", location_name: "Ladies Hostel (LH) Gate 1", latitude: 12.9680, longitude: 79.1570, fill_level: 58.0, alerted: false, predicted_hours_to_90: 5.8, priority_score: 41.6 },
    { bin_id: "BIN-011", location_name: "Campus Health Center & Pharmacy", latitude: 12.9695, longitude: 79.1585, fill_level: 19.0, alerted: false, predicted_hours_to_90: null, priority_score: 19.0 },
    { bin_id: "BIN-012", location_name: "Swimming Pool & Sports Complex", latitude: 12.9722, longitude: 79.1592, fill_level: 47.0, alerted: false, predicted_hours_to_90: null, priority_score: 47.0 }
  ],
  route: {
    route_id: "__ROUTE__",
    generated_at: new Date().toISOString(),
    total_distance_km: 2.84,
    num_bins_serviced: 3,
    depot: {
      name: "VIT Estates & Maintenance Depot",
      latitude: 12.9685,
      longitude: 79.1550
    },
    stops: [
      { stop_number: 1, bin_id: "BIN-002", location_name: "Technology Tower (TT) Food Court", latitude: 12.9705, longitude: 79.1595, fill_level: 87.2, priority_score: 95.4 },
      { stop_number: 2, bin_id: "BIN-009", location_name: "Men's Hostel Block D Quad", latitude: 12.9730, longitude: 79.1620, fill_level: 86.5, priority_score: 94.1 },
      { stop_number: 3, bin_id: "BIN-005", location_name: "Anna Auditorium North Gate", latitude: 12.9710, longitude: 79.1637, fill_level: 89.4, priority_score: 98.2 }
    ]
  }
};

/**
 * Get base URL with query-string override support (?api=http...)
 */
function getApiBaseUrl() {
  const urlParams = new URLSearchParams(window.location.search);
  const queryApi = urlParams.get("api");
  if (queryApi) {
    return queryApi.replace(/\/$/, "");
  }
  const config = window.API_CONFIG || {};
  return (config.apiBaseUrl || "").replace(/\/$/, "");
}

/**
 * Fetch latest telemetry and route data from API Gateway.
 */
async function fetchDashboardData() {
  if (AppState.isFetching) return;
  AppState.isFetching = true;

  const baseUrl = getApiBaseUrl();
  const banner = document.getElementById("system-banner");
  const connDot = document.getElementById("conn-dot");
  const connText = document.getElementById("conn-text");

  // Check if API endpoint is still using placeholder
  const isPlaceholderUrl = !baseUrl || baseUrl.includes("<api-id>");

  if (isPlaceholderUrl && window.API_CONFIG.enableDemoFallback) {
    // Render demo dataset with informative demo banner
    setDemoMode(banner, connDot, connText);
    AppState.bins = DEMO_FALLBACK.bins;
    AppState.route = DEMO_FALLBACK.route;
    updateUI();
    AppState.isFetching = false;
    return;
  }

  try {
    connDot.className = "status-dot online";
    connText.innerText = "Syncing...";

    const [binsRes, routeRes] = await Promise.all([
      fetch(`${baseUrl}/bins`, { cache: "no-store" }),
      fetch(`${baseUrl}/route`, { cache: "no-store" })
    ]);

    if (!binsRes.ok) throw new Error(`HTTP ${binsRes.status} querying /bins`);
    if (!routeRes.ok) throw new Error(`HTTP ${routeRes.status} querying /route`);

    const binsData = await binsRes.json();
    const routeData = await routeRes.json();

    AppState.bins = binsData.bins || [];
    AppState.route = routeData;

    // Clear any previous error banner
    banner.style.display = "none";
    connDot.className = "status-dot online";
    connText.innerText = "Live";

    updateUI();
  } catch (err) {
    console.warn("API fetch failed:", err);

    if (window.API_CONFIG.enableDemoFallback) {
      setDemoMode(banner, connDot, connText, err.message);
      AppState.bins = DEMO_FALLBACK.bins;
      AppState.route = DEMO_FALLBACK.route;
      updateUI();
    } else {
      banner.className = "system-banner error";
      banner.innerHTML = `<strong>API Connection Error:</strong> Unable to reach <code>${baseUrl}</code>. (${err.message})`;
      banner.style.display = "block";
      connDot.className = "status-dot error";
      connText.innerText = "Offline";
    }
  } finally {
    AppState.isFetching = false;
  }
}

function setDemoMode(banner, connDot, connText, errorMsg = "") {
  banner.className = "system-banner warning";
  banner.innerHTML = `
    <strong>Demo Mode:</strong> Displaying simulated VIT Vellore telemetry.
    ${errorMsg ? `(API: ${errorMsg})` : `Configure <code>apiBaseUrl</code> in <code>dashboard/js/config.js</code> to connect live.`}
  `;
  banner.style.display = "block";
  connDot.className = "status-dot online";
  connText.innerText = "Demo";
}

/**
 * Update UI summary metrics, lists, and map visualizations.
 */
function updateUI() {
  const bins = AppState.bins;
  const route = AppState.route;

  // 1. Calculate Metrics
  const totalBins = bins.length;
  const criticalCount = bins.filter((b) => Number(b.fill_level || 0) >= 85.0).length;

  const totalFill = bins.reduce((sum, b) => sum + Number(b.fill_level || 0), 0);
  const avgFill = totalBins > 0 ? (totalFill / totalBins).toFixed(1) : "0.0";

  const routeDistance = route && route.total_distance_km ? `${Number(route.total_distance_km).toFixed(2)} km` : "0.0 km";
  const numServiced = route && route.num_bins_serviced !== undefined ? route.num_bins_serviced : 0;

  // 2. Render Metric Cards
  document.getElementById("stat-total-bins").innerText = totalBins;

  const critEl = document.getElementById("stat-critical-bins");
  critEl.innerText = criticalCount;
  critEl.style.color = criticalCount > 0 ? "var(--status-critical)" : "inherit";

  document.getElementById("stat-avg-fill").innerText = `${avgFill}%`;
  document.getElementById("stat-route-distance").innerText = routeDistance;
  document.getElementById("stat-route-sub").innerText = `${numServiced} stops scheduled`;

  // 3. Render Leaflet Map
  renderBins(bins);
  renderRoute(route);

  // 4. Render Active Tab Content
  renderRouteStopsTab();
  renderBinsInventoryTab();

  // 5. Update timestamp
  AppState.lastUpdated = new Date();
  document.getElementById("last-updated-text").innerText = `Last updated: ${AppState.lastUpdated.toLocaleTimeString()}`;
}

/**
 * Render the collection route tab.
 */
function renderRouteStopsTab() {
  const container = document.getElementById("route-stops-list");
  const route = AppState.route;

  if (!route || !route.stops || route.stops.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <p>No critical bins require collection right now.</p>
        <span style="font-size: 11px;">(Route triggers automatically when priority score &ge; 60.0)</span>
      </div>
    `;
    return;
  }

  const depotName = (route.depot && route.depot.name) || "Central Maintenance Depot";

  let html = `
    <div class="route-summary">
      <div class="route-summary-item">
        <span>Route Depot:</span> <strong>${depotName}</strong>
      </div>
      <div class="route-summary-item">
        <span>Optimized Total Distance:</span> <strong>${Number(route.total_distance_km).toFixed(2)} km</strong>
      </div>
      <div class="route-summary-item">
        <span>Bins Serviced:</span> <strong>${route.num_bins_serviced}</strong>
      </div>
    </div>
    <div class="list-container">
  `;

  route.stops.forEach((stop) => {
    const fill = Number(stop.fill_level || 0);
    const badgeClass = fill >= 85 ? "critical" : fill >= 50 ? "warning" : "normal";

    html += `
      <div class="list-item">
        <div class="item-top">
          <span class="item-title">Stop #${stop.stop_number}: ${stop.bin_id}</span>
          <span class="item-badge ${badgeClass}">${fill.toFixed(1)}% Fill</span>
        </div>
        <div class="item-sub">${stop.location_name || "Campus Location"}</div>
        <div class="progress-track">
          <div class="progress-bar ${badgeClass}" style="width: ${fill}%;"></div>
        </div>
      </div>
    `;
  });

  html += `</div>`;
  container.innerHTML = html;
}

/**
 * Render the complete bin inventory tab.
 */
function renderBinsInventoryTab() {
  const container = document.getElementById("bins-inventory-list");
  const bins = AppState.bins;

  if (!bins || bins.length === 0) {
    container.innerHTML = `<div class="empty-state">No bins registered in database.</div>`;
    return;
  }

  let html = `<div class="list-container">`;
  bins.forEach((bin) => {
    const fill = Number(bin.fill_level || 0);
    const badgeClass = fill >= 85 ? "critical" : fill >= 50 ? "warning" : "normal";
    const pred = bin.predicted_hours_to_90 !== null && bin.predicted_hours_to_90 !== undefined
      ? `${Number(bin.predicted_hours_to_90).toFixed(1)}h to 90%`
      : "Steady / Safe";

    html += `
      <div class="list-item">
        <div class="item-top">
          <span class="item-title">${bin.bin_id}</span>
          <span class="item-badge ${badgeClass}">${fill.toFixed(1)}%</span>
        </div>
        <div class="item-sub">${bin.location_name || "Campus Ground"} &bull; ${pred}</div>
        <div class="progress-track">
          <div class="progress-bar ${badgeClass}" style="width: ${fill}%;"></div>
        </div>
      </div>
    `;
  });
  html += `</div>`;
  container.innerHTML = html;
}

/**
 * Setup event listeners, tabs, and start polling timer.
 */
function setupDashboard() {
  // Initialize Leaflet Map
  initMap("map");

  // Tab Switching
  const tabRouteBtn = document.getElementById("tab-route-btn");
  const tabBinsBtn = document.getElementById("tab-bins-btn");
  const routeTab = document.getElementById("tab-route-content");
  const binsTab = document.getElementById("tab-bins-content");

  tabRouteBtn.addEventListener("click", () => {
    tabRouteBtn.classList.add("active");
    tabBinsBtn.classList.remove("active");
    routeTab.style.display = "block";
    binsTab.style.display = "none";
  });

  tabBinsBtn.addEventListener("click", () => {
    tabBinsBtn.classList.add("active");
    tabRouteBtn.classList.remove("active");
    routeTab.style.display = "none";
    binsTab.style.display = "block";
  });

  // Manual Refresh Button
  document.getElementById("btn-refresh").addEventListener("click", () => {
    fetchDashboardData();
  });

  // Initial Data Fetch
  fetchDashboardData();

  // Setup Polling Interval
  const intervalSeconds = (window.API_CONFIG && window.API_CONFIG.refreshIntervalSeconds) || 15;
  AppState.pollTimer = setInterval(fetchDashboardData, intervalSeconds * 1000);
}

// Bootstrap on DOM ready
document.addEventListener("DOMContentLoaded", setupDashboard);

