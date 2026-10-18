"""Pytest configuration and shared fixtures for offline testing."""
import os
import sys
import pytest
import boto3
from moto import mock_aws

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Setup mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing-mock-key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing-mock-secret"
os.environ["AWS_SECURITY_TOKEN"] = "testing-mock-token"
os.environ["AWS_SESSION_TOKEN"] = "testing-mock-token"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"

# Setup test table names and ARNs
os.environ["WASTE_BINS_TABLE"] = "TestWasteBins"
os.environ["BIN_READINGS_TABLE"] = "TestBinReadings"
os.environ["S3_ARCHIVE_BUCKET"] = "test-smart-waste-archive"
os.environ["SNS_ALERT_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-alerts"
os.environ["ALERT_THRESHOLD"] = "85.0"
os.environ["RESET_THRESHOLD"] = "50.0"

@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing-mock-key"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing-mock-secret"
    os.environ["AWS_SECURITY_TOKEN"] = "testing-mock-token"
    os.environ["AWS_SESSION_TOKEN"] = "testing-mock-token"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture
def mocked_aws(aws_credentials):
    """Set up mocked DynamoDB, S3, and SNS resources."""
    with mock_aws():
        # 1. Setup DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        # WasteBins Table (PK: bin_id String)
        waste_bins_table = dynamodb.create_table(
            TableName="TestWasteBins",
            KeySchema=[{"AttributeName": "bin_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "bin_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST"
        )
        waste_bins_table.wait_until_exists()

        # BinReadings Table (PK: bin_id String, SK: timestamp Number)
        bin_readings_table = dynamodb.create_table(
            TableName="TestBinReadings",
            KeySchema=[
                {"AttributeName": "bin_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "bin_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "N"}
            ],
            BillingMode="PAY_PER_REQUEST"
        )
        bin_readings_table.wait_until_exists()

        # 2. Setup S3
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-smart-waste-archive")

        # 3. Setup SNS
        sns = boto3.client("sns", region_name="us-east-1")
        topic = sns.create_topic(Name="test-alerts")
        os.environ["SNS_ALERT_TOPIC_ARN"] = topic["TopicArn"]

        yield {
            "dynamodb": dynamodb,
            "waste_bins_table": waste_bins_table,
            "bin_readings_table": bin_readings_table,
            "s3": s3,
            "sns": sns,
            "topic_arn": topic["TopicArn"]
        }

