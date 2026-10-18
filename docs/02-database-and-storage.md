# 02 - Database & Storage Design

> **Status:** Architecture Design Document (Planned Implementation)

---

## 1. Storage Architecture Overview
The system uses a multi-tier storage model balancing fast low-latency key-value lookups, time-series retention, and low-cost long-term batch archival:
1. **`WasteBins` (DynamoDB):** Current state, geo-coordinates, alert flags, and latest analytics results.
2. **`BinReadings` (DynamoDB):** Short-term historical telemetry (7-day rolling window) enabling linear regression calculations.
3. **`smart-waste-archive-*` (Amazon S3):** Immutable cold storage of raw JSON ingestion batches.

---

## 2. DynamoDB Table Design

### A. Table: `WasteBins`
Stores current state per physical bin, plus system-wide optimized route caching.

* **Primary Key:** `bin_id` (String - Partition Key)
* **Read/Write Capacity:** On-Demand (`PAY_PER_REQUEST`)
* **Item Schema:**
  ```json
  {
    "bin_id": "BIN-001",
    "location_name": "Campus Library Courtyard",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "fill_level": 86.4,
    "capacity_liters": 120,
    "last_updated": "2026-10-17T17:15:00Z",
    "alerted": true,
    "predicted_hours_to_90": 1.8,
    "priority_score": 92.5
  }
  ```

* **Route Cache Item:** To avoid cross-service dependencies, the active route is stored under the reserved key `bin_id = "__ROUTE__"`:
  ```json
  {
    "bin_id": "__ROUTE__",
    "generated_at": "2026-10-17T17:15:00Z",
    "total_distance_km": 14.8,
    "stops": [
      {
        "bin_id": "DEPOT",
        "latitude": 12.9685,
        "longitude": 79.1550,
        "location_name": "VIT Estates & Maintenance Depot"
      }
    ],
    "num_bins_serviced": 3
  }
  ```

### B. Table: `BinReadings`
Stores time-series readings used for regression analysis.

* **Partition Key (PK):** `bin_id` (String)
* **Sort Key (SK):** `timestamp` (Number - Epoch Milliseconds)
* **Time to Live (TTL):** Enabled on attribute `ttl` (Epoch Seconds)
  * Calculated as: $\text{ttl} = \text{current\_epoch\_seconds} + (7 \times 86400)$
  * Automatically purges readings older than 7 days without consuming write capacity.
* **Item Schema:**
  ```json
  {
    "bin_id": "BIN-001",
    "timestamp": 1760721300000,
    "fill_level": 86.4,
    "ttl": 1761326100
  }
  ```

---

## 3. Amazon S3 Raw Archive Architecture
Each payload received by `waste-ingest` is preserved in Amazon S3 for compliance, re-training, or auditing.

* **Bucket Name:** `smart-waste-readings-archive-<account-id>`
* **Key Partitioning Format:**
  `raw-readings/YYYY/MM/DD/batch-<timestamp>-<uuid>.json`
* **Object Structure:**
  ```json
  {
    "ingested_at": "2026-10-17T17:15:00Z",
    "batch_size": 10,
    "readings": [
      {
        "bin_id": "BIN-001",
        "timestamp": 1760721300000,
        "fill_level": 86.4
      }
    ]
  }
  ```

---

## 4. Key Design Considerations
* **Why On-Demand Capacity?** Telemetry and scheduled analytics occur in bursts; On-Demand scales instantly without manual capacity planning.
* **Why TTL?** Linear regression only requires the last several hours/days of readings. Automated TTL pruning keeps query latency low and costs minimal.

