# 09 - Deployment & Cleanup Procedure

> **Status:** Pre-Deployment Verification Complete | Deployment Plan & Guide Ready (Offline Verified)
> **Target Region:** AWS `ap-southeast-2` (Sydney) | AWS Lambda Python 3.12 | AWS CLI v2 / AWS Console

---

## 1. Pre-Deployment Verification Checklist

Before running any AWS CLI commands or creating resources in the AWS Console, complete the following local verification checks:

- [x] **Local Test Suite:** Run `.venv\Scripts\python.exe -m pytest -v` (Windows) or `pytest -v` (Linux/macOS). All 40 unit and integration tests must pass.
- [x] **Target Region Set to `ap-southeast-2` (Sydney):** Configured for AWS accounts restricted to the Asia Pacific (Sydney) region.
- [x] **Preserve Campus Geospatial Data:** VIT Vellore bin GPS coordinates and the Estates & Maintenance Depot coordinates (`12.9685, 79.1550`) are strictly preserved.
- [x] **Handler Paths & Structure:**
  - `lambdas.waste_ingest.lambda_function.lambda_handler`
  - `lambdas.waste_analytics.lambda_function.lambda_handler`
  - `lambdas.waste_api.lambda_function.lambda_handler`
- [x] **Packaging Script:** Run `python scripts/package_lambdas.py` to create zip packages in `dist/`.
- [x] **Zero External Lambda Dependencies:** All three Lambda functions rely exclusively on the Python 3.12 standard library (`math`, `heapq`, `json`, `datetime`, `urllib`) and the AWS-provided `boto3`/`botocore` SDK. No vendor layers or external pip packages are needed in the Lambda zips.
- [x] **Safe Secrets Management:** Confirm `.env` is listed in `.gitignore` and `.env.example` contains only non-sensitive placeholders.
- [ ] **AWS CLI Authentication:** Ensure local AWS credentials have appropriate provisioning permissions in `ap-southeast-2`:
  ```bash
  aws sts get-caller-identity
  ```

---

## 2. Automated Lambda Packaging

A cross-platform packaging utility is provided at [`scripts/package_lambdas.py`](file:///c:/Users/asus/Desktop/aws%20project/scripts/package_lambdas.py).

To generate deployment archives:
```bash
# From the project root:
python scripts/package_lambdas.py
```

This generates three archives in the `dist/` directory:
1. `dist/waste_ingest.zip` (~9 KB) — contains `lambdas/__init__.py`, `lambdas/common/`, and `lambdas/waste_ingest/`.
2. `dist/waste_analytics.zip` (~12 KB) — contains `lambdas/__init__.py`, `lambdas/common/`, and `lambdas/waste_analytics/`.
3. `dist/waste_api.zip` (~8 KB) — contains `lambdas/__init__.py`, `lambdas/common/`, and `lambdas/waste_api/`.

*(Alternative manual PowerShell command)*:
```powershell
Compress-Archive -Path lambdas -DestinationPath dist/waste_ingest.zip -Force
```

---

## 3. Step-by-Step AWS CLI Deployment Roadmap

Run the following parameterized commands in a Bash or POSIX shell (e.g., Git Bash, WSL, or macOS terminal). Replace placeholders where noted.

### Step 0: Shell Variables & Context Setup
```bash
# Configure deployment variables for Sydney region
export AWS_REGION="ap-southeast-2"
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export S3_BUCKET="smart-waste-readings-archive-${ACCOUNT_ID}"
export SNS_TOPIC="waste-threshold-alerts"
export OPERATOR_EMAIL="operator@example.com"    # <-- Replace with actual notification email
export WASTE_BINS_TABLE="WasteBins"
export BIN_READINGS_TABLE="BinReadings"

echo "Deploying to Account: ${ACCOUNT_ID} in Region: ${AWS_REGION}"
```

#### Pre-Flight Conflict & Error Diagnosis (Safe to Run)
```bash
# 1. S3 Pre-flight check (diagnoses accessible bucket, 403, 404, or inconclusive errors)
# NOTE: head-bucket cannot authoritatively confirm global bucket name availability.
# HTTP 404 indicates the bucket was not found or is inaccessible; the actual create-bucket
# call determines authoritatively whether the name is taken (BucketAlreadyExists) or created.
echo -n "Checking S3 bucket name '${S3_BUCKET}'... "
S3_CHECK=$(aws s3api head-bucket --bucket "${S3_BUCKET}" 2>&1)
S3_STATUS=$?
if [ $S3_STATUS -eq 0 ]; then
  echo "[EXISTS] Bucket '${S3_BUCKET}' already exists and is accessible."
elif echo "${S3_CHECK}" | grep -q "404"; then
  echo "[NOT FOUND LOCALLY] Bucket was not found in account/region. Authoritative availability is determined by create-bucket."
elif echo "${S3_CHECK}" | grep -q "403"; then
  echo "[COLLISION / FORBIDDEN] Bucket exists and is owned by another account, or access is denied by policy."
else
  echo "[INCONCLUSIVE / ERROR] Pre-flight check could not determine status (network/credentials): ${S3_CHECK}"
fi

# 2. DynamoDB WasteBins Pre-flight check
echo -n "Checking DynamoDB table '${WASTE_BINS_TABLE}' in ${AWS_REGION}... "
DDB1_CHECK=$(aws dynamodb describe-table --table-name "${WASTE_BINS_TABLE}" --region "${AWS_REGION}" 2>&1)
DDB1_STATUS=$?
if [ $DDB1_STATUS -eq 0 ]; then
  echo "[EXISTS] Table '${WASTE_BINS_TABLE}' already exists."
elif echo "${DDB1_CHECK}" | grep -q "ResourceNotFoundException"; then
  echo "[AVAILABLE] Table '${WASTE_BINS_TABLE}' does not exist (ready to create)."
else
  echo "[ERROR] Pre-flight check failed: ${DDB1_CHECK}"
fi

# 3. DynamoDB BinReadings Pre-flight check
echo -n "Checking DynamoDB table '${BIN_READINGS_TABLE}' in ${AWS_REGION}... "
DDB2_CHECK=$(aws dynamodb describe-table --table-name "${BIN_READINGS_TABLE}" --region "${AWS_REGION}" 2>&1)
DDB2_STATUS=$?
if [ $DDB2_STATUS -eq 0 ]; then
  echo "[EXISTS] Table '${BIN_READINGS_TABLE}' already exists."
elif echo "${DDB2_CHECK}" | grep -q "ResourceNotFoundException"; then
  echo "[AVAILABLE] Table '${BIN_READINGS_TABLE}' does not exist (ready to create)."
else
  echo "[ERROR] Pre-flight check failed: ${DDB2_CHECK}"
fi
```

---

### Step 1: Storage Provisioning (S3 & DynamoDB)

#### A. Amazon S3 Raw Telemetry Bucket (`ap-southeast-2`)
```bash
# 1. Create S3 archival bucket in ap-southeast-2 (LocationConstraint is REQUIRED for ap-southeast-2)
aws s3api create-bucket \
  --bucket "${S3_BUCKET}" \
  --region "${AWS_REGION}" \
  --create-bucket-configuration LocationConstraint="${AWS_REGION}"

# 2. Block all public access
aws s3api put-public-access-block \
  --bucket "${S3_BUCKET}" \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# 3. Enable default server-side encryption (SSE-S3)
aws s3api put-bucket-encryption \
  --bucket "${S3_BUCKET}" \
  --server-side-encryption-configuration '{"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}'
```

#### B. Amazon DynamoDB Tables (`ap-southeast-2`)
```bash
# 1. Create WasteBins table (Partition Key: bin_id [S], On-Demand)
aws dynamodb create-table \
  --table-name "${WASTE_BINS_TABLE}" \
  --attribute-definitions AttributeName=bin_id,AttributeType=S \
  --key-schema AttributeName=bin_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${AWS_REGION}"

# 2. Create BinReadings table (Partition Key: bin_id [S], Sort Key: timestamp [N], On-Demand)
aws dynamodb create-table \
  --table-name "${BIN_READINGS_TABLE}" \
  --attribute-definitions AttributeName=bin_id,AttributeType=S AttributeName=timestamp,AttributeType=N \
  --key-schema AttributeName=bin_id,KeyType=HASH AttributeName=timestamp,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region "${AWS_REGION}"

# 3. Wait for tables to become ACTIVE
aws dynamodb wait table-exists --table-name "${WASTE_BINS_TABLE}" --region "${AWS_REGION}"
aws dynamodb wait table-exists --table-name "${BIN_READINGS_TABLE}" --region "${AWS_REGION}"

# 4. Enable Time to Live (TTL) on BinReadings attribute 'ttl'
aws dynamodb update-time-to-live \
  --table-name "${BIN_READINGS_TABLE}" \
  --time-to-live-specification "Enabled=true, AttributeName=ttl" \
  --region "${AWS_REGION}"
```

---

### Step 2: Amazon SNS Alert Topic Setup

```bash
# 1. Create standard SNS topic in ap-southeast-2
aws sns create-topic \
  --name "${SNS_TOPIC}" \
  --region "${AWS_REGION}"

export SNS_TOPIC_ARN="arn:aws:sns:${AWS_REGION}:${ACCOUNT_ID}:${SNS_TOPIC}"

# 2. Subscribe operator email address
aws sns subscribe \
  --topic-arn "${SNS_TOPIC_ARN}" \
  --protocol email \
  --notification-endpoint "${OPERATOR_EMAIL}" \
  --region "${AWS_REGION}"

echo "Subscription requested. Operator must click 'Confirm subscription' in the confirmation email."
```

---

### Step 3: IAM Execution Roles & Least-Privilege Policies

```bash
# 1. Base Lambda Trust Policy
cat << 'EOF' > /tmp/lambda-trust-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# 2. Create Roles
aws iam create-role --role-name WasteIngestRole --assume-role-policy-document file:///tmp/lambda-trust-policy.json
aws iam create-role --role-name WasteAnalyticsRole --assume-role-policy-document file:///tmp/lambda-trust-policy.json
aws iam create-role --role-name WasteApiRole --assume-role-policy-document file:///tmp/lambda-trust-policy.json

# 3. Attach AWSLambdaBasicExecutionRole to all roles for CloudWatch Logs
aws iam attach-role-policy --role-name WasteIngestRole --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam attach-role-policy --role-name WasteAnalyticsRole --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam attach-role-policy --role-name WasteApiRole --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# 4. Attach scoped policy to WasteIngestRole
cat << EOF > /tmp/waste-ingest-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:GetItem"
      ],
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${WASTE_BINS_TABLE}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:BatchWriteItem"
      ],
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${BIN_READINGS_TABLE}"
    },
    {
      "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::${S3_BUCKET}/*"
    },
    {
      "Effect": "Allow",
      "Action": "sns:Publish",
      "Resource": "${SNS_TOPIC_ARN}"
    }
  ]
}
EOF
aws iam put-role-policy --role-name WasteIngestRole --policy-name WasteIngestLeastPrivilege --policy-document file:///tmp/waste-ingest-policy.json

# 5. Attach scoped policy to WasteAnalyticsRole
cat << EOF > /tmp/waste-analytics-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${BIN_READINGS_TABLE}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Scan",
        "dynamodb:UpdateItem",
        "dynamodb:PutItem",
        "dynamodb:GetItem"
      ],
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${WASTE_BINS_TABLE}"
    }
  ]
}
EOF
aws iam put-role-policy --role-name WasteAnalyticsRole --policy-name WasteAnalyticsLeastPrivilege --policy-document file:///tmp/waste-analytics-policy.json

# 6. Attach scoped policy to WasteApiRole
cat << EOF > /tmp/waste-api-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Scan",
        "dynamodb:GetItem"
      ],
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${WASTE_BINS_TABLE}"
    }
  ]
}
EOF
aws iam put-role-policy --role-name WasteApiRole --policy-name WasteApiLeastPrivilege --policy-document file:///tmp/waste-api-policy.json

# Wait 10 seconds for IAM roles to propagate
sleep 10
```

---

### Step 4: AWS Lambda Functions Creation

Deploy the three functions using Python 3.12:

```bash
# 1. Deploy waste-ingest
aws lambda create-function \
  --function-name waste-ingest \
  --runtime python3.12 \
  --handler lambdas.waste_ingest.lambda_function.lambda_handler \
  --zip-file fileb://dist/waste_ingest.zip \
  --role "arn:aws:iam::${ACCOUNT_ID}:role/WasteIngestRole" \
  --timeout 15 \
  --memory-size 256 \
  --environment "Variables={WASTE_BINS_TABLE=${WASTE_BINS_TABLE},BIN_READINGS_TABLE=${BIN_READINGS_TABLE},S3_ARCHIVE_BUCKET=${S3_BUCKET},SNS_ALERT_TOPIC_ARN=${SNS_TOPIC_ARN},ALERT_THRESHOLD=85.0,RESET_THRESHOLD=50.0}" \
  --region "${AWS_REGION}"

# 2. Deploy waste-analytics
aws lambda create-function \
  --function-name waste-analytics \
  --runtime python3.12 \
  --handler lambdas.waste_analytics.lambda_function.lambda_handler \
  --zip-file fileb://dist/waste_analytics.zip \
  --role "arn:aws:iam::${ACCOUNT_ID}:role/WasteAnalyticsRole" \
  --timeout 30 \
  --memory-size 256 \
  --environment "Variables={WASTE_BINS_TABLE=${WASTE_BINS_TABLE},BIN_READINGS_TABLE=${BIN_READINGS_TABLE},DEPOT_LATITUDE=12.9685,DEPOT_LONGITUDE=79.1550,DEPOT_NAME='VIT Estates & Maintenance Depot',CAPACITY_PREDICTION_TARGET_PERCENT=90.0,CAPACITY_TARGET_PERCENT=90.0}" \
  --region "${AWS_REGION}"

# 3. Deploy waste-api
aws lambda create-function \
  --function-name waste-api \
  --runtime python3.12 \
  --handler lambdas.waste_api.lambda_function.lambda_handler \
  --zip-file fileb://dist/waste_api.zip \
  --role "arn:aws:iam::${ACCOUNT_ID}:role/WasteApiRole" \
  --timeout 15 \
  --memory-size 256 \
  --environment "Variables={WASTE_BINS_TABLE=${WASTE_BINS_TABLE},DEPOT_LATITUDE=12.9685,DEPOT_LONGITUDE=79.1550,DEPOT_NAME='VIT Estates & Maintenance Depot'}" \
  --region "${AWS_REGION}"
```

---

### Step 5: EventBridge 15-Minute Analytics Schedule

```bash
# 1. Create 15-minute scheduled rule in ap-southeast-2
aws events put-rule \
  --name waste-analytics-15m-schedule \
  --schedule-expression "rate(15 minutes)" \
  --state ENABLED \
  --description "Triggers fill rate regression and route optimization every 15 minutes" \
  --region "${AWS_REGION}"

# 2. Grant EventBridge permission to invoke waste-analytics Lambda
aws lambda add-permission \
  --function-name waste-analytics \
  --statement-id EventBridgeInvokeAnalytics \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:${AWS_REGION}:${ACCOUNT_ID}:rule/waste-analytics-15m-schedule" \
  --region "${AWS_REGION}"

# 3. Add waste-analytics function as the rule target
aws events put-targets \
  --rule waste-analytics-15m-schedule \
  --targets "Id=1,Arn=arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:waste-analytics" \
  --region "${AWS_REGION}"
```

---

### Step 6: Amazon API Gateway HTTP API Provisioning

```bash
# 1. Create HTTP API with global CORS configuration in ap-southeast-2
API_ID=$(aws apigatewayv2 create-api \
  --name SmartWasteApi \
  --protocol-type HTTP \
  --cors-configuration "AllowOrigins=*,AllowMethods=GET,POST,OPTIONS,AllowHeaders=Content-Type,Authorization" \
  --query ApiId \
  --output text \
  --region "${AWS_REGION}")

export API_ID
echo "Created HTTP API with ID: ${API_ID}"

# 2. Create Lambda integrations
INGEST_INT_ID=$(aws apigatewayv2 create-integration \
  --api-id "${API_ID}" \
  --integration-type AWS_PROXY \
  --integration-uri "arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:waste-ingest" \
  --payload-format-version "2.0" \
  --query IntegrationId \
  --output text \
  --region "${AWS_REGION}")

API_INT_ID=$(aws apigatewayv2 create-integration \
  --api-id "${API_ID}" \
  --integration-type AWS_PROXY \
  --integration-uri "arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:waste-api" \
  --payload-format-version "2.0" \
  --query IntegrationId \
  --output text \
  --region "${AWS_REGION}")

# 3. Create Routes
aws apigatewayv2 create-route --api-id "${API_ID}" --route-key "POST /readings" --target "integrations/${INGEST_INT_ID}" --region "${AWS_REGION}"
aws apigatewayv2 create-route --api-id "${API_ID}" --route-key "GET /bins" --target "integrations/${API_INT_ID}" --region "${AWS_REGION}"
aws apigatewayv2 create-route --api-id "${API_ID}" --route-key "GET /route" --target "integrations/${API_INT_ID}" --region "${AWS_REGION}"

# 4. Grant API Gateway permission to invoke Lambda functions
aws lambda add-permission \
  --function-name waste-ingest \
  --statement-id ApiGatewayInvokeIngest \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${AWS_REGION}:${ACCOUNT_ID}:${API_ID}/*" \
  --region "${AWS_REGION}"

aws lambda add-permission \
  --function-name waste-api \
  --statement-id ApiGatewayInvokeApi \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${AWS_REGION}:${ACCOUNT_ID}:${API_ID}/*" \
  --region "${AWS_REGION}"

# 5. Retrieve base invoke URL
API_URL=$(aws apigatewayv2 get-api --api-id "${API_ID}" --query ApiEndpoint --output text --region "${AWS_REGION}")
echo "=========================================================="
echo "DEPLOYMENT COMPLETE!"
echo "API Base URL: ${API_URL}"
echo "Endpoints:"
echo "  - Ingestion: ${API_URL}/readings"
echo "  - Bins:      ${API_URL}/bins"
echo "  - Route:     ${API_URL}/route"
echo "=========================================================="
```

---

### Step 7: Client Wiring (Simulator & Dashboard)

Once deployed, wire the live cloud endpoint into client configurations:

1. **Simulator Configuration:**
   In `.env`:
   ```bash
   API_GATEWAY_URL=https://<api-id>.execute-api.ap-southeast-2.amazonaws.com
   SIMULATOR_API_ENDPOINT=https://<api-id>.execute-api.ap-southeast-2.amazonaws.com/readings
   ```
   Start the simulator:
   ```bash
   .venv/Scripts/python.exe simulator/simulate_bins.py
   ```

2. **Web Dashboard Configuration:**
   In [`dashboard/js/config.js`](file:///c:/Users/asus/Desktop/aws%20project/dashboard/js/config.js):
   ```javascript
   API_BASE_URL: 'https://<api-id>.execute-api.ap-southeast-2.amazonaws.com'
   ```
   Open [`dashboard/index.html`](file:///c:/Users/asus/Desktop/aws%20project/dashboard/index.html) in any modern browser to view live data.

---

## 4. Manual AWS Management Console Walkthrough (Region: `ap-southeast-2`)

For developers or evaluators deploying via the AWS Web Console:

| Component | AWS Console Service | Key Configuration Details |
| :--- | :--- | :--- |
| **Console Region** | Global Header Bar | Select **Asia Pacific (Sydney) ap-southeast-2** |
| **S3 Bucket** | Amazon S3 | Create bucket `smart-waste-readings-archive-<account-id>`. Region: `ap-southeast-2`. Block public access = ON. Bucket encryption = SSE-S3. |
| **DynamoDB Tables** | Amazon DynamoDB | In `ap-southeast-2`, create `WasteBins` (PK: `bin_id` [String]). Create `BinReadings` (PK: `bin_id` [String], SK: `timestamp` [Number]). Under `BinReadings` Additional Settings, enable TTL on attribute `ttl`. |
| **SNS Topic** | Amazon SNS | In `ap-southeast-2`, create Standard topic `waste-threshold-alerts`. Create Email subscription and confirm the verification email. |
| **IAM Roles** | IAM -> Roles | Create role with Lambda trusted entity. Attach `AWSLambdaBasicExecutionRole` and custom inline policy for DynamoDB/S3/SNS as documented in Step 3. |
| **Lambda Functions** | AWS Lambda | In `ap-southeast-2`, create `waste-ingest`, `waste-analytics`, and `waste-api` using Python 3.12. Set Handler to `lambdas.waste_<name>.lambda_function.lambda_handler`. Upload corresponding ZIP from `dist/`. Add Environment Variables. |
| **EventBridge Rule** | Amazon EventBridge | In `ap-southeast-2`, create Rule `waste-analytics-15m-schedule`. Schedule pattern: `rate(15 minutes)`. Target: Lambda function `waste-analytics`. |
| **API Gateway** | API Gateway | In `ap-southeast-2`, create HTTP API `SmartWasteApi`. Add routes `POST /readings`, `GET /bins`, `GET /route`. Set CORS Allow-Origin to `*`. Integrate routes to Lambda functions. |

---

## 5. Teardown & Resource Decommissioning Guide

> [!CAUTION]
> **[DESTRUCTIVE ACTION: PERMANENT DATA LOSS]**
> Deleting DynamoDB tables permanently destroys all stored telemetry and route calculations. Deleting the S3 bucket removes raw JSON archives. Confirm that all target resource identifiers belong strictly to this project before executing the commands below.

```bash
# Verify environment variables point strictly to project resources
echo "Target Region: ${AWS_REGION}"
echo "Target S3 Bucket: ${S3_BUCKET}"
echo "Target Tables: ${WASTE_BINS_TABLE}, ${BIN_READINGS_TABLE}"

# 1. Delete API Gateway HTTP API
aws apigatewayv2 delete-api --api-id "${API_ID}" --region "${AWS_REGION}"

# 2. Delete EventBridge Schedule Target & Rule
aws events remove-targets --rule waste-analytics-15m-schedule --ids "1" --region "${AWS_REGION}"
aws events delete-rule --name waste-analytics-15m-schedule --region "${AWS_REGION}"

# 3. Delete Lambda Functions
aws lambda delete-function --function-name waste-ingest --region "${AWS_REGION}"
aws lambda delete-function --function-name waste-analytics --region "${AWS_REGION}"
aws lambda delete-function --function-name waste-api --region "${AWS_REGION}"

# 4. Delete Amazon SNS Topic and Subscriptions
aws sns delete-topic --topic-arn "${SNS_TOPIC_ARN}" --region "${AWS_REGION}"

# 5. [DESTRUCTIVE] Empty and Delete S3 Bucket
aws s3 rm "s3://${S3_BUCKET}" --recursive --region "${AWS_REGION}"
aws s3api delete-bucket --bucket "${S3_BUCKET}" --region "${AWS_REGION}"

# 6. [DESTRUCTIVE] Delete DynamoDB Tables
aws dynamodb delete-table --table-name "${WASTE_BINS_TABLE}" --region "${AWS_REGION}"
aws dynamodb delete-table --table-name "${BIN_READINGS_TABLE}" --region "${AWS_REGION}"

# 7. Delete IAM Execution Policies and Roles
aws iam delete-role-policy --role-name WasteIngestRole --policy-name WasteIngestLeastPrivilege
aws iam detach-role-policy --role-name WasteIngestRole --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name WasteIngestRole

aws iam delete-role-policy --role-name WasteAnalyticsRole --policy-name WasteAnalyticsLeastPrivilege
aws iam detach-role-policy --role-name WasteAnalyticsRole --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name WasteAnalyticsRole

aws iam delete-role-policy --role-name WasteApiRole --policy-name WasteApiLeastPrivilege
aws iam detach-role-policy --role-name WasteApiRole --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name WasteApiRole

echo "[OK] Complete AWS environment teardown executed successfully."
```

---

## 6. Actions That Incur Charges or Delete Data

> [!WARNING]
> **AWS Pricing & Free Tier Notice:**
> - **Verify Current Pricing:** Always consult the official [AWS Pricing Calculator](https://calculator.aws/) and check your specific account's Free Tier eligibility. Never assume costs will be zero.
> - **S3 Storage Costs:** S3 charges for stored data (GB-months) and PUT/GET requests once Free Tier allowances are exceeded or if the account is older than 12 months. Empty the bucket upon project completion.
> - **DynamoDB On-Demand:** Charged per million read and write request units. While the 12-bin prototype consumes modest request volume, excessive polling or unbounded table scans will incur charges.
> - **EventBridge Invocations:** The 15-minute schedule invokes `waste-analytics` 96 times/day (~2,880 invocations/month). Disable or delete the rule when evaluation is complete to avoid continuous Lambda invocations.
> - **Permanent Data Loss:** `aws s3 rm --recursive` and `aws dynamodb delete-table` are irreversible.

---

## 7. Cloud-Only Behaviors Unverifiable Without Live AWS Account

The following platform-specific cloud behaviors have been mocked or unit-tested locally, but **cannot be verified without an active AWS account**:

1. **IAM Policy Boundary Evaluation:** Offline tests use `moto` mock clients which bypass AWS IAM evaluation. Real AWS IAM evaluation validates exact ARN patterns, permissions boundaries, and service principal trust relationships.
2. **SNS Email Dispatch & Inbox Delivery:** While `moto` confirms the `sns:Publish` API call returns a valid MessageId, real SMTP email dispatch, DKIM/SPF verification, spam filtering, and operator subscription confirmation links require live AWS SNS.
3. **API Gateway DNS Resolution & SSL/TLS:** Local integration tests simulate API Gateway request/response payloads directly. Real HTTPS handshakes, certificate management, route matching, and latency can only be verified on `execute-api.<region>.amazonaws.com`.
4. **DynamoDB Background TTL Sweeper:** DynamoDB guarantees eventual deletion of expired items typically within 48 hours via a background process that consumes no read/write units. In local `moto` tests, TTL attributes are stored and checked mathematically, but the background deletion worker is AWS-managed.
5. **EventBridge Real-World Cron Dispatch:** The timer trigger is verified offline by directly invoking the handler. The AWS EventBridge scheduler engine's precision and CloudWatch trigger metrics require cloud deployment.
6. **CloudWatch Logs Streaming & Log Retention:** The creation of `/aws/lambda/<function-name>` log groups, subscription filters, and log expiration policies can only be validated against live Amazon CloudWatch.
