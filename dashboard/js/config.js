/**
 * AWS Smart Waste Monitoring System - Dashboard Configuration
 * Configure the API Gateway HTTP API endpoint and polling intervals.
 */
window.API_CONFIG = {
  // API Gateway base URL (set via environment or replace placeholder when deployed)
  // Can also be overridden at runtime via URL query param: ?api=https://...
  apiBaseUrl: "https://pr8f2gf36a.execute-api.ap-southeast-2.amazonaws.com",

  // Polling interval in seconds (default: 15s)
  refreshIntervalSeconds: 15,

  // Campus Default Map View (VIT Vellore, Tamil Nadu)
  mapCenter: [12.9702, 79.1595],
  mapZoom: 16,

  // Thresholds for visual styling
  thresholds: {
    warning: 50.0,
    critical: 85.0,
    capacityPredictionTarget: 90.0
  },

  // Enable demo fallback dataset when API Gateway is not deployed or unreachable
  // This allows full offline demonstration and review of all UI features.
  enableDemoFallback: true
};
