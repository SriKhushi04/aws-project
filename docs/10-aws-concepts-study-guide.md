# 10 - AWS Concepts Study Guide

> **Purpose:** Academic and conceptual preparation for viva, technical examinations, and project defense.

---

## 1. Serverless Computing: AWS Lambda
* **What is it?** Event-driven, serverless computing service that executes code without provisioning or managing servers.
* **Execution Model:** Automatically runs code in response to events (e.g. HTTP requests via API Gateway, EventBridge cron triggers).
* **Cold Start vs. Warm Start:**
  * *Cold Start:* Occurs when a function is invoked after inactivity. AWS must provision an execution container, download runtime/code, and initialize dependencies.
  * *Warm Start:* Subsequent invocations reuse the established container, executing with minimal latency.
* **Why Python 3.12?** Offers modern syntax, enhanced interpreter performance, and native AWS SDK compatibility.

---

## 2. API Gateway: HTTP API vs. REST API
* **Why HTTP API for this project?**
  * Up to 70% cheaper than REST API.
  * Lower overhead and p99 latency (optimized for serverless proxying).
  * Built-in native CORS configuration and OIDC/JWT support without complex mapping templates.

---

## 3. NoSQL Database: Amazon DynamoDB
* **Architecture:** Fully managed, serverless key-value and document NoSQL database offering single-digit millisecond latency at any scale.
* **Primary Key Types:**
  * *Simple Primary Key (Partition Key only):* Used in `WasteBins` (`bin_id`). DynamoDB hashes the partition key to distribute data across physical storage partitions.
  * *Composite Primary Key (Partition Key + Sort Key):* Used in `BinReadings` (`bin_id` + `timestamp`). Enables fast time-series range queries (`BETWEEN`, `>`, `<`).
* **Time-to-Live (TTL):**
  * A background process that scans items and automatically removes expired entries without consuming read/write capacity units or incurring costs.
  * In this system, 7-day TTL ensures historical telemetry remains fresh and storage costs stay near zero.

---

## 4. Object Storage: Amazon S3
* **Concept:** Highly durable (99.999999999% - 11 9's), scalable object storage.
* **Storage Classes:** Standard, Intelligent-Tiering, Glacier, Deep Archive.
* **Role in Project:** Serves as immutable raw data lake storage for batch readings before any aggregation, useful for audit trails and long-term re-training.

---

## 5. Messaging & Scheduling: Amazon SNS & EventBridge
* **Amazon Simple Notification Service (SNS):**
  * Fully managed Pub/Sub messaging service.
  * Decouples the producer (`waste-ingest`) from consumers (email notification, SMS, operations webhook).
* **Amazon EventBridge:**
  * Serverless event bus and scheduler.
  * Emits automated `rate(15 minutes)` trigger events to drive periodic regression forecasting and route re-calculation in `waste-analytics`.

