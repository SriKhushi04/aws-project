# 07 - Monitoring & Security

> **Status:** Architecture Design Document (Planned Implementation)

---

## 1. CloudWatch Observability Strategy
The system utilizes native Amazon CloudWatch components for logging, operational metrics, and error tracking across all serverless resources.

### A. Structured Logging
Each of the three Lambda functions writes JSON-structured logs to CloudWatch Log Groups:
* `/aws/lambda/waste-ingest`
* `/aws/lambda/waste-analytics`
* `/aws/lambda/waste-api`

Log events include standardized correlation fields:
```json
{
  "timestamp": "2026-10-17T17:15:02Z",
  "level": "INFO",
  "function": "waste-ingest",
  "action": "PROCESS_BATCH",
  "batch_size": 10,
  "alerts_triggered": 1
}
```

### B. CloudWatch Alarms (Planned)
1. **`IngestErrorsAlarm`:** Triggers when `Errors >= 1` in a 5-minute evaluation period for `waste-ingest`.
2. **`AnalyticsDurationAlarm`:** Triggers when `Duration > 10000ms` for `waste-analytics` (indicating algorithmic performance degradation on large bin sets).

---

## 2. API Security & CORS Policy
* **CORS Headers:** The `waste-api` and `waste-ingest` endpoints return appropriate Cross-Origin Resource Sharing (CORS) headers to allow the dashboard to communicate from local browser origins:
  * `Access-Control-Allow-Origin: *` (for local demo)
  * `Access-Control-Allow-Methods: GET, POST, OPTIONS`
  * `Access-Control-Allow-Headers: Content-Type, Authorization`
* **Throttling & Rate Limiting:** API Gateway enforces throttling (e.g. 100 requests/second burst, 50 requests/second steady) to safeguard against denial-of-service traffic.

---

## 3. Storage Security
* **Amazon S3:**
  * **Block Public Access:** All 4 S3 block public access settings enabled.
  * **Server-Side Encryption:** Enabled by default using Amazon S3-managed keys (`SSE-S3` / AES-256).
* **Amazon DynamoDB:**
  * Encrypted at rest using default AWS-managed KMS keys.
  * Access restricted strictly via IAM resource policies.

---

## 4. Security Risk Audit: Wildcard CORS & Public Ingestion

### A. Wildcard CORS Risk (`Access-Control-Allow-Origin: *`)
* **Current State:** Both API Gateway CORS configuration and Lambda response headers use `Access-Control-Allow-Origin: *` to facilitate testing across localhost ports and file previewers.
* **Risk:** Permits any third-party web domain to issue cross-origin requests to the API Gateway. In production, this exposes the API to unauthorized web clients, scraping, and potential cross-origin exploitation.
* **Production Recommendation:** Restrict allowed origins to the explicit production domain hosting the Leaflet web dashboard (e.g. `https://waste-dashboard.example.com` or CloudFront distribution origin).

### B. Public Unauthenticated Telemetry Ingestion (`POST /readings`)
* **Current State:** The `POST /readings` route is public with no authorizer, API key, or HMAC signature validation.
* **Risk:** Anyone possessing the public API Gateway URL can post arbitrary JSON batches, which could:
  1. Inject fraudulent sensor readings, skewing fill rates and route optimization.
  2. Cause excessive writes to DynamoDB and S3, incurring unexpected billing ("Denial-of-Wallet").
  3. Trigger continuous false-alarm SNS threshold emails to the operator.
* **Production Recommendation:**
  1. **Option 1 (API Gateway Lambda Authorizer / Token Header):** Require an `x-sensor-token` or `Authorization: Bearer <token>` header verified either at API Gateway or inside `waste-ingest`.
  2. **Option 2 (AWS IoT Core with X.509 Device Certificates):** Transition physical hardware sensors to publish MQTT telemetry via AWS IoT Core with per-device mutual TLS certificates.


