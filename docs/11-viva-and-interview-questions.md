# 11 - Viva & Technical Interview Questions

> **Purpose:** Comprehensive question-and-answer preparation for academic viva, external examiners, and technical project defense.

---

### Q1: What is the main objective of this project?
**Answer:** The project replaces static, inefficient municipal waste collection schedules with a smart, demand-driven serverless system. By ingesting IoT fill-level telemetry into AWS, applying linear regression to forecast overflow times, and running 2-Opt route optimization, collection trucks only visit bins that actually need emptying, minimizing fuel consumption and preventing overflows.

---

### Q2: Why did you choose exactly three Lambda functions instead of a microservice per task or a monolithic function?
**Answer:** The 3-function model strikes an optimal balance between **cohesion, isolation, and operational simplicity**:
1. `waste-ingest`: High write frequency, latency-sensitive, handles ingestion, persistence, S3 archival, and immediate alerts.
2. `waste-analytics`: Heavy computational workload (matrix math, regression, graph optimization) triggered periodically on a 15-minute schedule via EventBridge.
3. `waste-api`: Read-only, low-latency API serving user queries from the dashboard.
Separating compute-heavy analytics from high-throughput ingestion prevents analytics operations from blocking or throttling incoming sensor traffic.

---

### Q3: Why is alert hysteresis (85% alert, 50% reset) necessary?
**Answer:** In physical IoT deployments, ultrasonic sensor readings fluctuate due to air temperature, garbage settling, and sensor jitter. If a static threshold of 85% was used without hysteresis, a bin reading 85.1%, 84.9%, 85.2% would spam operators with dozens of duplicate email notifications (**alert fatigue**). Hysteresis tracks an `alerted` boolean flag: once alerted at $\ge 85\%$, no further alerts are issued until the bin is physically collected and drops below $50\%$.

---

### Q4: Why use DynamoDB instead of a traditional relational database (e.g., MySQL / PostgreSQL)?
**Answer:**
1. **Serverless & Scalability:** DynamoDB auto-scales seamlessly to thousands of concurrent sensor writes without connection pool limits.
2. **Predictable Low Latency:** Key-value reads on `bin_id` guarantee single-digit millisecond response times regardless of table size.
3. **Automated Cost Control via TTL:** The built-in Time-To-Live (TTL) feature purges readings older than 7 days from `BinReadings` automatically, without needing manual cron purge queries that consume CPU and database locks.

---

### Q5: Why use both DynamoDB and Amazon S3 for storing readings?
**Answer:** They serve distinct access patterns:
* **DynamoDB (`BinReadings`)** is optimized for low-latency operational queries over the most recent 7 days required for real-time regression.
* **Amazon S3** is an ultra-low-cost, durable data lake. Archiving raw JSON payloads in S3 enables long-term historical records, compliance, and large-scale analytics or model training (e.g. AWS Glue / Athena) without bloating DynamoDB storage costs.

---

### Q6: Why did you choose Nearest-Neighbour followed by 2-Opt rather than Dijkstra, A*, or brute force?
**Answer:**
* **Dijkstra and A\*** find the shortest path between *two specific points* in a road graph, not an entire tour visiting multiple stops.
* The collection route is an instance of the **Traveling Salesperson Problem (TSP)**, which is NP-hard. Brute force requires $O(n!)$ time, which is impossible to compute for even 15–20 bins within a Lambda execution timeout.
* **Nearest-Neighbour** constructs a reasonable initial tour in $O(n^2)$ time.
* **2-Opt** systematically removes tour-crossing edges by swapping edge pairs until a local optimum is achieved in $O(n^2)$ iterations, producing near-optimal real-world routes within milliseconds.

---

### Q7: How does the linear regression algorithm work in `waste-analytics`?
**Answer:** The system retrieves recent timestamp-fill data points for a bin and computes the Ordinary Least Squares (OLS) best-fit line:
$$y = m \cdot t + c$$
where $m$ represents the fill rate (% per second). The time when the bin reaches $90\%$ capacity ($t_{90}$) is calculated as:
$$t_{90} = \frac{90.0 - c}{m}$$
If the slope $m \le 0$ (meaning the bin is emptying or static), the model handles the edge case gracefully by returning `null`, preventing false overflow predictions.

---

### Q8: How is the system tested without active AWS credentials or deployment costs?
**Answer:** We employ **offline automated testing** via `pytest` and `moto`. `moto` intercepts `boto3` API calls and runs an in-memory mock of AWS DynamoDB, S3, and SNS services on the local machine. This guarantees that all business logic, validation rules, TTL calculations, hysteresis states, and route algorithms are thoroughly verified before any cloud resources are provisioned.

