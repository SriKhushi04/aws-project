# 01 - AWS Setup & Security Guide

> **Status:** Architecture Design Document (Planned Implementation)

---

## 1. Security First Principles
This project strictly observes the **Principle of Least Privilege (PoLP)** and credential isolation:
* **No Hardcoded Credentials:** Never include AWS access keys, secret keys, or session tokens in source code.
* **Role-Based Execution:** In AWS, Lambda functions assume IAM execution roles with scoped permissions.
* **Local Offline Isolation:** Local testing and simulation run without active AWS credentials by utilizing environment variables, local mocks, and `moto`.

---

## 2. Planned IAM Roles and Execution Policies

### A. Role: `WasteIngestLambdaRole`
Assumed by: `waste-ingest`

**Required Permissions:**
1. **AWSLambdaBasicExecutionRole:** CloudWatch Logs creation and streaming (`logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`).
2. **DynamoDB Access:**
   * `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:GetItem` on `arn:aws:dynamodb:<region>:<account-id>:table/WasteBins`
   * `dynamodb:PutItem`, `dynamodb:BatchWriteItem` on `arn:aws:dynamodb:<region>:<account-id>:table/BinReadings`
3. **S3 Archival Access:**
   * `s3:PutObject` on `arn:aws:s3:::<s3-bucket-name>/raw-readings/*`
4. **SNS Publishing Access:**
   * `sns:Publish` on `arn:aws:sns:<region>:<account-id>:waste-threshold-alerts`

### B. Role: `WasteAnalyticsLambdaRole`
Assumed by: `waste-analytics`

**Required Permissions:**
1. **AWSLambdaBasicExecutionRole:** CloudWatch Logs.
2. **DynamoDB Access:**
   * `dynamodb:Query`, `dynamodb:Scan` on `arn:aws:dynamodb:<region>:<account-id>:table/BinReadings`
   * `dynamodb:Scan`, `dynamodb:UpdateItem`, `dynamodb:PutItem` on `arn:aws:dynamodb:<region>:<account-id>:table/WasteBins`

### C. Role: `WasteApiLambdaRole`
Assumed by: `waste-api`

**Required Permissions:**
1. **AWSLambdaBasicExecutionRole:** CloudWatch Logs.
2. **DynamoDB Read-Only Access:**
   * `dynamodb:Scan`, `dynamodb:GetItem`, `dynamodb:Query` on `arn:aws:dynamodb:<region>:<account-id>:table/WasteBins`

---

## 3. Environment Variable Configuration

Lambda functions read their resource references exclusively from environment variables:

| Variable Name | Description | Example (Planned) |
| :--- | :--- | :--- |
| `WASTE_BINS_TABLE` | DynamoDB table storing current bin state | `WasteBins` |
| `BIN_READINGS_TABLE` | DynamoDB table storing time-series readings | `BinReadings` |
| `S3_ARCHIVE_BUCKET` | S3 bucket storing raw batch archives | `smart-waste-archive-<id>` |
| `SNS_ALERT_TOPIC_ARN` | Topic ARN for email notifications | `arn:aws:sns:...:waste-threshold-alerts` |
| `ALERT_THRESHOLD` | Percentage threshold to trigger SNS alert | `85.0` |
| `RESET_THRESHOLD` | Percentage threshold to reset alert state | `50.0` |

---

## 4. Local Development Security Protocol
* Use `.env.example` as a template for local variables.
* The `.gitignore` file enforces exclusion of `.env`, `credentials`, `.aws/`, and SSH keys.
* When running local unit tests, test fixtures configure dummy environment variables:
  ```python
  os.environ["AWS_DEFAULT_REGION"] = "ap-southeast-2"
  os.environ["AWS_ACCESS_KEY_ID"] = "testing-mock-key"
  os.environ["AWS_SECRET_ACCESS_KEY"] = "testing-mock-secret"
  ```

