"""Configuration provider for AWS Lambda functions and local testing."""
import os

def get_env_var(name: str, default: str = "") -> str:
    """Retrieve an environment variable with a default fallback."""
    return os.environ.get(name, default).strip()

def get_config() -> dict:
    """Load configuration values from environment variables."""
    return {
        "AWS_REGION": get_env_var("AWS_REGION", get_env_var("AWS_DEFAULT_REGION", "ap-southeast-2")),
        "WASTE_BINS_TABLE": get_env_var("WASTE_BINS_TABLE", get_env_var("DYNAMODB_TABLE_WASTE_BINS", "WasteBins")),
        "BIN_READINGS_TABLE": get_env_var("BIN_READINGS_TABLE", get_env_var("DYNAMODB_TABLE_BIN_READINGS", "BinReadings")),
        "S3_ARCHIVE_BUCKET": get_env_var("S3_ARCHIVE_BUCKET", get_env_var("S3_BUCKET_NAME", "smart-waste-readings-archive")),
        "SNS_ALERT_TOPIC_ARN": get_env_var("SNS_ALERT_TOPIC_ARN", get_env_var("SNS_TOPIC_ARN", "")),
        "ALERT_THRESHOLD": float(get_env_var("ALERT_THRESHOLD", get_env_var("ALERT_THRESHOLD_PERCENT", "85.0"))),
        "RESET_THRESHOLD": float(get_env_var("RESET_THRESHOLD", get_env_var("RESET_THRESHOLD_PERCENT", "50.0"))),
        "CAPACITY_PREDICTION_TARGET": float(get_env_var("CAPACITY_PREDICTION_TARGET_PERCENT", get_env_var("CAPACITY_TARGET_PERCENT", "90.0"))),
        "DEPOT_LATITUDE": float(get_env_var("DEPOT_LATITUDE", "12.9685")),
        "DEPOT_LONGITUDE": float(get_env_var("DEPOT_LONGITUDE", "79.1550")),
        "DEPOT_NAME": get_env_var("DEPOT_NAME", "VIT Estates & Maintenance Depot"),
        "PRIORITY_THRESHOLD": float(get_env_var("PRIORITY_THRESHOLD", "60.0")),
        "MAX_ROUTE_STOPS": int(get_env_var("MAX_ROUTE_STOPS", "8")),
        "EMPTYING_DROP_THRESHOLD": float(get_env_var("EMPTYING_DROP_THRESHOLD", "15.0")),
    }
