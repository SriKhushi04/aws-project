# AWS Smart Waste Monitoring & Collection Optimization System

An IoT-driven, serverless cloud platform designed to monitor urban/campus waste levels in real-time, predict overflow using linear regression, trigger threshold-based email alerts with hysteresis, optimize collection routes via Nearest-Neighbour and 2-Opt algorithms, and visualize live bin telemetry on an interactive Leaflet web dashboard.

---

## 📌 Implementation Status Tracker

| Component / Feature | Architecture Status | Local Implementation | AWS Deployment Status |
| :--- | :--- | :--- | :--- |
| **Project Skeleton & Directory Layout** | Planned & Approved | **Verified** | N/A (Local) |
| **Documentation Suite (00 to 11)** | Planned & Approved | **Verified** | N/A (Local) |
| **`waste-ingest` Lambda** | Planned (Single Ingest + S3 + SNS) | **Integration-Verified (8/8 tests)** | Packaged in `dist/` (Ready) |
| **`waste-analytics` Lambda** | Planned (Regression + 2-Opt) | **Integration-Verified (7/7 tests)** | Packaged in `dist/` (Ready) |
| **`waste-api` Lambda** | Planned (GET /bins + GET /route) | **Integration-Verified (9/9 tests)** | Packaged in `dist/` (Ready) |
| **DynamoDB (`WasteBins` & `BinReadings`)** | Planned (7-day TTL schema) | **Integration-Verified (moto)** | CLI & Console Scripts Ready |
| **S3 Raw Readings Archive** | Planned (Batch JSON prefix) | **Integration-Verified (moto)** | CLI & Console Scripts Ready |
| **SNS Email Alerts (85% / 50% hysteresis)**| Planned (`alerted` state tracking)| **Integration-Verified (moto)** | CLI & Console Scripts Ready |
| **EventBridge 15-Min Scheduler** | Planned | **Scheduled Handler Tested** | CLI & Console Scripts Ready |
| **Python IoT Simulator** | 12 Bins (VIT Vellore) | **Integration-Verified (8/8 tests)** | N/A (Runs locally) |
| **Leaflet Web Dashboard** | VIT Vellore Map & Routing UI | **Integration-Verified (6/6 tests)** | N/A (Runs locally) |
| **Packaging & Deployment Scripts** | Automated & Documented | **Verified (`scripts/package_lambdas.py`)** | Ready for execution |
| **Full Pipeline Integration** | End-to-end data lifecycle test | **Verified (39/39 tests passed)** | N/A (Local / Mocked) |

> **Note on Verification**: In accordance with project safety rules, all cloud resources and application modules remain marked as **Planned** until their respective code and offline unit tests are implemented and verified. No AWS resources are touched without prior instruction.

---

## 🏛️ System Architecture

The initial implementation consolidates cloud processing into **exactly three AWS Lambda functions**:

1. **`waste-ingest`**:
   * Validates incoming sensor payloads from API Gateway.
   * Updates current state in the `WasteBins` DynamoDB table.
   * Writes timestamped readings with a 7-day Time-To-Live (`ttl`) to the `BinReadings` table.
   * Archives raw batch JSON objects directly to Amazon S3.
   * Checks fill level against the 85% threshold; sends SNS alerts when crossed and sets `alerted = true`. Silences further alerts until the bin drops below 50% (`alerted = false`).

2. **`waste-analytics`** (Scheduled via EventBridge every 15 minutes):
   * Retrieves recent reading history from `BinReadings`.
   * Computes fill rates and predicts hours until 90% capacity using Ordinary Least Squares (OLS) linear regression.
   * Calculates priority scores for bins requiring emptying.
   * Computes an optimized collection route starting from the central depot using Nearest-Neighbour heuristic followed by 2-Opt edge swaps.
   * Persists predictions and the active route into `WasteBins`.

3. **`waste-api`**:
   * Exposes HTTP endpoints `GET /bins` and `GET /route` for the frontend dashboard.
   * Returns sanitized, structured JSON data.

4. **Local Components**:
   * **IoT Simulator**: Generates synthetic telemetry (bin ID, coordinates, fill level, timestamp, sensor noise) and posts to the API Gateway endpoint.
   * **Leaflet Dashboard**: Lightweight browser client displaying real-time bin status markers and the active optimized route polyline.

---

## 📁 Repository Structure

```text
aws-smart-waste-system/
│
├── .gitignore
├── .env.example
├── README.md
├── requirements.txt
│
├── lambdas/
│   ├── common/                       # Shared utilities across Lambda functions
│   │   ├── config.py                 # Environment variables and defaults
│   │   ├── dynamodb_service.py       # DynamoDB table accessors
│   │   ├── s3_service.py             # S3 archival helper
│   │   ├── sns_service.py            # SNS email publisher with hysteresis check
│   │   └── utils.py                  # Haversine distance, serializers, response helpers
│   ├── waste_ingest/                 # Lambda 1: Ingestion, archival, and alerts
│   ├── waste_analytics/              # Lambda 2: Regression, prioritization, and 2-opt route
│   └── waste_api/                    # Lambda 3: REST API serving GET /bins & GET /route
│
├── simulator/                        # Local Python sensor simulator
│   ├── config.py
│   ├── bins_seed.json
│   └── simulate_bins.py
│
├── dashboard/                        # Leaflet-based web UI
│   ├── index.html
│   ├── css/styles.css
│   └── js/ (config.js, map.js, app.js)
│
├── tests/                            # Offline test suite (pytest + moto)
│   ├── test_waste_ingest.py
│   ├── test_waste_analytics.py
│   ├── test_waste_api.py
│   ├── test_simulator.py
│   ├── test_dashboard.py
│   └── test_end_to_end_integration.py
│
├── scripts/                          # Build & packaging utilities
│   └── package_lambdas.py            # Generates Lambda deployment ZIPs in dist/
│
└── docs/                             # Complete project documentation suite
    ├── 00-project-overview.md
    ├── 01-aws-setup-and-security.md
    ├── 02-database-and-storage.md
    ├── 03-ingestion-lambda-and-api.md
    ├── 04-simulator-and-data-flow.md
    ├── 05-analytics-and-route-optimization.md
    ├── 06-dashboard-and-api.md
    ├── 07-monitoring-and-security.md
    ├── 08-testing-and-validation.md
    ├── 09-deployment-and-cleanup.md
    ├── 10-aws-concepts-study-guide.md
    └── 11-viva-and-interview-questions.md
```

---

## 📚 Documentation Index

For in-depth explanations and design specifications, refer to the guides in [`docs/`](file:///c:/Users/asus/Desktop/aws%20project/docs):

1. [00-project-overview.md](file:///c:/Users/asus/Desktop/aws%20project/docs/00-project-overview.md): High-level objectives, problem statement, and solution architecture.
2. [01-aws-setup-and-security.md](file:///c:/Users/asus/Desktop/aws%20project/docs/01-aws-setup-and-security.md): IAM policies, role separation, and credentials safety.
3. [02-database-and-storage.md](file:///c:/Users/asus/Desktop/aws%20project/docs/02-database-and-storage.md): DynamoDB key schemas, 7-day TTL, and S3 batch partitioning.
4. [03-ingestion-lambda-and-api.md](file:///c:/Users/asus/Desktop/aws%20project/docs/03-ingestion-lambda-and-api.md): Ingestion mechanics, payload validation, and hysteresis alerting.
5. [04-simulator-and-data-flow.md](file:///c:/Users/asus/Desktop/aws%20project/docs/04-simulator-and-data-flow.md): Minimal sensor telemetry generation, noise model, and simulation loop.
6. [05-analytics-and-route-optimization.md](file:///c:/Users/asus/Desktop/aws%20project/docs/05-analytics-and-route-optimization.md): Linear regression mathematics, prioritization formula, and 2-Opt TSP solver.
7. [06-dashboard-and-api.md](file:///c:/Users/asus/Desktop/aws%20project/docs/06-dashboard-and-api.md): Web UI structure, Leaflet map integration, and API consumption.
8. [07-monitoring-and-security.md](file:///c:/Users/asus/Desktop/aws%20project/docs/07-monitoring-and-security.md): CloudWatch metrics, alarms, CORS configuration, and threat model.
9. [08-testing-and-validation.md](file:///c:/Users/asus/Desktop/aws%20project/docs/08-testing-and-validation.md): Unit testing guide with pytest and moto mocking.
10. [09-deployment-and-cleanup.md](file:///c:/Users/asus/Desktop/aws%20project/docs/09-deployment-and-cleanup.md): Manual deployment steps and complete resource teardown procedures.
11. [10-aws-concepts-study-guide.md](file:///c:/Users/asus/Desktop/aws%20project/docs/10-aws-concepts-study-guide.md): Core concepts, terminology, and AWS architectural principles.
12. [11-viva-and-interview-questions.md](file:///c:/Users/asus/Desktop/aws%20project/docs/11-viva-and-interview-questions.md): Comprehensive Q&A preparation for project viva and technical interviews.

