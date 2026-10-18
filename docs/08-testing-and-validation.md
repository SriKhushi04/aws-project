# 08 - Testing & Validation Strategy

> **Status:** Test Suites Implemented & Verified (14/14 Tests Passed)

---

## 1. Testing Philosophy
A core constraint of this project is that **no AWS resources are deployed or credentials required** during local development and algorithm verification. The entire system is validated through automated offline tests using:
* **`pytest`**: Python test runner and assertion framework.
* **`moto`**: In-memory mocking of AWS services (DynamoDB, S3, SNS) running entirely on the local machine with dummy credentials.

---

## 2. Test Suite Organization

```text
tests/
├── conftest.py               # Shared fixtures: Moto in-memory DynamoDB tables, S3 bucket, SNS topic
├── test_waste_ingest.py      # Validates waste-ingest Lambda (verified: 8/8)
├── test_waste_analytics.py   # Validates waste-analytics Lambda (verified: 7/7)
├── test_waste_api.py         # Validates waste-api Lambda (verified: 9/9)
├── test_simulator.py         # Validates IoT telemetry simulator (verified: 8/8)
├── test_dashboard.py         # Validates frontend DOM structure & contract (verified: 6/6)
├── test_end_to_end_integration.py # Full pipeline integration test (verified: 1/1)
└── mock_events/              # Static sample payloads
    └── sample_reading.json
```

---

## 3. Implemented Test Suites

### A. Ingestion Tests (`test_waste_ingest.py`)
1. **Schema Validation:**
   * Missing `bin_id` returns `400 Bad Request`.
   * Out-of-bounds `fill_level` ($< 0.0$ or $> 100.0$) returns `400 Bad Request`.
   * Out-of-bounds coordinates (latitude $\notin [-90, 90]$ or longitude $\notin [-180, 180]$) returns `400 Bad Request`.
   * Malformed timestamp string returns `400 Bad Request`.
2. **Storage Operations:**
   * Valid reading writes to `WasteBins` (updating fill level, coordinates, `alerted = False`, and last updated time).
   * Valid reading writes to `BinReadings`.
3. **7-Day TTL Calculation:**
   * Verifies that the `ttl` attribute on `BinReadings` items precisely equals $\text{timestamp\_seconds} + 604800$.
4. **S3 Archival:**
   * Verifies that each accepted batch is archived to `raw-readings/YYYY/MM/DD/batch-<timestamp>-<uuid>.json` in S3.
5. **Hysteresis State Machine:**
   * Step 1: Fill reaches $87.0\%$ ($\ge 85\%$) $\to$ SNS alert published, `alerted` becomes `True`.
   * Step 2: Fill reaches $89.0\%$ ($\ge 85\%$) $\to$ duplicate alert suppressed, `alerted` stays `True`.
   * Step 3: Fill drops to $70.0\%$ (between $50\%$ and $85\%$) $\to$ `alerted` stays `True`.
   * Step 4: Fill drops to $30.0\%$ ($< 50\%$) $\to$ `alerted` resets to `False`.

### B. Analytics & Route Optimization Tests (`test_waste_analytics.py`)
1. **Reset Filtering:**
   * `test_regression_filtering_after_reset`: Ensures readings prior to a drop $\ge 15\%$ are discarded.
2. **OLS Regression Calculation:**
   * `test_linear_regression_math_and_forecast`: Confirms fill rate (%/hr) and hours to 90% forecast accuracy.
3. **Edge Case Handling:**
   * `test_regression_edge_cases`: Verifies single reading, declining fill, flat fill, and fill $\ge 90\%$.
4. **Priority Scoring:**
   * `test_priority_scoring`: Asserts score ranges, urgency scaling, and eligibility threshold $\ge 60.0$.
5. **2-Opt Distance Improvement:**
   * `test_two_opt_distance_improvement`: Verifies that 2-Opt untangles crossing edges and guarantees $\text{distance}_{\text{2-opt}} \le \text{distance}_{\text{NN}}$.
   * `test_empty_route_when_no_bins`: Handles zero eligible bins gracefully.
6. **End-to-End Handler Integration:**
   * `test_waste_analytics_handler_integration`: End-to-end execution against mock DynamoDB verifying predictions written to `WasteBins` and the optimized route stored under `bin_id = "__ROUTE__"`.

---

### C. API Tests (`test_waste_api.py`)
1. **`GET /bins` with Data:** Asserts active bins returned, sorted alphabetically, and system records (`__ROUTE__`) strictly excluded.
2. **`GET /bins` Empty State:** Asserts empty list and total_bins = 0 returned gracefully.
3. **`GET /route` with Active Route:** Asserts route object returned with stops, depot, and total_distance_km.
4. **`GET /route` Empty State:** Asserts clean default structure returned if analytics hasn't run yet.
5. **CORS Preflight:** Asserts `OPTIONS` request returns 200 with `Access-Control-Allow-Origin: *`.
6. **Method Validation:** Asserts non-GET requests (e.g. `POST`, `DELETE`) return `405 Method Not Allowed`.
7. **Route Not Found:** Asserts unmapped paths return `404 Not Found`.
8. **Gateway Compatibility:** Asserts support for both API Gateway v2.0 and REST v1.0 payload formats.
9. **Database Error Handling:** Asserts database connection errors return clean `500 Internal Server Error`.

### D. IoT Simulator Tests (`test_simulator.py`)
1. **Seed Initialization:** Asserts all 12 bins are loaded with coordinates within the VIT Vellore campus bounds.
2. **Tick Advancement & Bounds:** Asserts fill accumulation per delta seconds and clamping within $[0.0, 100.0\%]$.
3. **Emptying Simulation:** Asserts bins reaching $100\%$ reset to a baseline between $5.0\%$ and $10.0\%$.
4. **Schema Compliance:** Asserts that generated payload strictly passes `waste-ingest` schema validation.
5. **Successful Dispatch:** Asserts HTTP `POST` serialization and successful 200 response handling.
6. **API Error Handling:** Asserts graceful handling of HTTP 400 Bad Request responses.
7. **Network Resilience:** Asserts that connection errors and timeouts are caught without crashing the simulator loop.
8. **Finite Run Mode:** Asserts `run(max_ticks=3)` terminates cleanly after 3 ticks.

### E. Leaflet Frontend Dashboard Tests (`test_dashboard.py`)
1. **Asset Integrity:** Asserts that `index.html`, `styles.css`, `config.js`, `map.js`, and `app.js` are all present.
2. **DOM Container Verification:** Asserts that `#map`, `#stat-total-bins`, `#stat-critical-bins`, `#stat-avg-fill`, `#stat-route-distance`, `#route-stops-list`, `#bins-inventory-list`, and `#btn-refresh` exist in `index.html`.
3. **Leaflet CDN Integration:** Asserts Leaflet CSS and JS CDN tags are embedded.
4. **CSS Status & Animation Rules:** Asserts presence of status variables (`--status-normal`, `--status-warning`, `--status-critical`), pulsing beacon animation, and mobile responsive rules.
5. **Config & Map Coordinates:** Asserts VIT Vellore campus center (`[12.9702, 79.1595]`) and threshold definitions.
6. **API Schema Compatibility:** Asserts `app.js` consumes exact attributes (`fill_level`, `bin_id`, `total_distance_km`, `stops`, `predicted_hours_to_90`) served by `waste-api`.

### F. End-to-End Pipeline Integration Tests (`test_end_to_end_integration.py`)
1. **Full Lifecycle Verification:**
   * Advances the 12-bin VIT Vellore simulator across multiple ticks.
   * Feeds readings through `waste-ingest` $\to$ validates DynamoDB `WasteBins`, `BinReadings` (with 7d TTL), S3 batch archival, and SNS alert triggers.
   * Executes scheduled `waste-analytics` $\to$ fits OLS regressions, scores urgency, and solves 2-Opt collection route for depot `VIT Estates & Maintenance Depot`.
   * Queries `waste-api` via `GET /bins` and `GET /route` $\to$ verifies that output attributes strictly match the Leaflet frontend expectations.

### G. Lambda Packaging Integrity Tests (`test_packaging.py`)
1. **Archive Completeness & Cleanliness:**
   * Verifies that `package_lambdas.py` automatically generates valid ZIP archives for `waste-ingest`, `waste-analytics`, and `waste-api` in `dist/`.
   * Asserts inclusion of `lambdas/__init__.py`, `lambdas/common/` utilities, and respective lambda modules.
   * Asserts complete exclusion of `__pycache__`, `.pyc`, and `.pyo` files.

---

## 4. Execution & Verification Status
* **Test files:**
  * [`tests/test_waste_ingest.py`](file:///c:/Users/asus/Desktop/aws%20project/tests/test_waste_ingest.py) (8 tests)
  * [`tests/test_waste_analytics.py`](file:///c:/Users/asus/Desktop/aws%20project/tests/test_waste_analytics.py) (7 tests)
  * [`tests/test_waste_api.py`](file:///c:/Users/asus/Desktop/aws%20project/tests/test_waste_api.py) (9 tests)
  * [`tests/test_simulator.py`](file:///c:/Users/asus/Desktop/aws%20project/tests/test_simulator.py) (8 tests)
  * [`tests/test_dashboard.py`](file:///c:/Users/asus/Desktop/aws%20project/tests/test_dashboard.py) (6 tests)
  * [`tests/test_packaging.py`](file:///c:/Users/asus/Desktop/aws%20project/tests/test_packaging.py) (1 test)
  * [`tests/test_end_to_end_integration.py`](file:///c:/Users/asus/Desktop/aws%20project/tests/test_end_to_end_integration.py) (1 test)
* **Status:** **VERIFIED (40/40 tests passing)** in isolated `.venv` environment.
* **Execution Command:**
  ```powershell
  .venv\Scripts\python.exe -m pytest -v
  ```
