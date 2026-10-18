# 06 - Dashboard & API Specification

> **Status:** Implementation Complete / Unit Tests Verified (9/9 API Tests + 6/6 Frontend Tests Passed)

---

## 1. REST API Contract (`waste-api`)
The `waste-api` Lambda function responds to GET requests forwarded by API Gateway HTTP API (or REST API v1.0).

### Endpoint 1: `GET /bins`
Returns current statuses, locations, and predictions for all monitored bins.

* **Response Status:** `200 OK`
* **Response Payload:**
  ```json
  {
    "status": "success",
    "total_bins": 12,
    "bins": [
      {
        "bin_id": "BIN-001",
        "location_name": "Periyar Central Library Plaza",
        "latitude": 12.9698,
        "longitude": 79.1559,
        "fill_level": 86.4,
        "alerted": true,
        "predicted_hours_to_90": 1.8,
        "priority_score": 92.5,
        "last_updated": "2026-10-17T17:15:00Z"
      }
    ]
  }
  ```

### Endpoint 2: `GET /route`
Returns the active optimized collection path and stop sequence.

* **Response Status:** `200 OK`
* **Response Payload:**
  ```json
  {
    "status": "success",
    "route_id": "__ROUTE__",
    "generated_at": "2026-10-17T17:15:00Z",
    "total_distance_km": 2.84,
    "initial_distance_km": 3.42,
    "num_bins_serviced": 3,
    "depot": {
      "name": "VIT Estates & Maintenance Depot",
      "latitude": 12.9685,
      "longitude": 79.1550
    },
    "stops": [
      {
        "stop_number": 1,
        "bin_id": "BIN-002",
        "location_name": "Technology Tower (TT) Food Court",
        "latitude": 12.9705,
        "longitude": 79.1595,
        "fill_level": 87.2,
        "priority_score": 95.4
      }
    ]
  }
  ```

---

## 2. Frontend Architecture (Leaflet Web Dashboard)
The dashboard is designed as a clean, zero-build, responsive web interface located in [`dashboard/`](file:///c:/Users/asus/Desktop/aws%20project/dashboard/):
* **`index.html`:** Semantic HTML5 layout featuring header metrics (Total Bins, Critical Count, Average Fill Level, Active Route Distance), full-screen interactive Leaflet map, and tabbed sidebar panel.
* **`css/styles.css`:** Modern UI styles with color-coded status badges, pulsing red beacon animation for overflowing bins, custom scrollbars, and mobile `@media` responsive breakpoints.
* **`js/config.js`:** API Gateway base URL configuration, polling frequency (default: 15s), VIT Vellore default map center (`12.9702, 79.1595`), and demo fallback toggle.
* **`js/map.js`:** Leaflet initialization, OpenStreetMap tile layer, custom colored circle pin markers with rich info popups, Central Depot warehouse marker, and polyline route renderer with numbered stop badges.
* **`js/app.js`:** Telemetry polling controller, overlap prevention (`isFetching` guard), metrics calculation, tab switching (Route Stops vs. All Bins), error banner, and built-in offline demonstration fallback.

---

## 3. Visual Indicators & Pin Color Coding
| Fill Level Range | Status Category | Marker Color | Visual Style |
| :--- | :--- | :--- | :--- |
| $\text{fill} < 50.0\%$ | **Normal** | 🟢 Green | Solid green marker, standard popup |
| $50.0\% \le \text{fill} < 85.0\%$ | **Warning** | 🟡 Amber | Solid amber marker, warning badge |
| $\text{fill} \ge 85.0\%$ | **Critical / Overflow** | 🔴 Red | Pulsing red marker, alert badge (`alerted=true`) |

---

## 4. Verification Status
* **REST API Handler:** [`lambdas/waste_api/lambda_function.py`](file:///c:/Users/asus/Desktop/aws%20project/lambdas/waste_api/lambda_function.py)
* **Frontend Web App:** [`dashboard/index.html`](file:///c:/Users/asus/Desktop/aws%20project/dashboard/index.html)
* **Unit Tests:** [`tests/test_waste_api.py`](file:///c:/Users/asus/Desktop/aws%20project/tests/test_waste_api.py) & [`tests/test_dashboard.py`](file:///c:/Users/asus/Desktop/aws%20project/tests/test_dashboard.py)
* **Status:** **VERIFIED** (15/15 tests passing across API and frontend validation).
