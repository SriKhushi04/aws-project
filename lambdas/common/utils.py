"""Utility functions for data validation, serialization, and API Gateway responses."""
import json
import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Tuple, Union

def to_decimal(value: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB storage."""
    if isinstance(value, float):
        return Decimal(str(value))
    elif isinstance(value, dict):
        return {k: to_decimal(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [to_decimal(v) for v in value]
    return value

def decimal_to_python(value: Any) -> Any:
    """Recursively convert Decimal objects back to float/int for JSON serialization."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    elif isinstance(value, dict):
        return {k: decimal_to_python(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [decimal_to_python(v) for v in value]
    return value

def build_response(status_code: int, body: dict) -> dict:
    """Construct a standard API Gateway proxy response with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(decimal_to_python(body))
    }

def parse_and_validate_timestamp(ts: Union[int, float, str]) -> Tuple[int, int, str]:
    """
    Parse a timestamp into:
    - timestamp_ms: epoch milliseconds (used as DynamoDB Sort Key)
    - timestamp_sec: epoch seconds (used for TTL calculation)
    - timestamp_iso: ISO 8601 formatted string (e.g. 2026-10-17T17:15:00Z)
    """
    if ts is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(ts, (int, float)):
        # If timestamp is likely in seconds (e.g. < 10000000000), convert to ms
        if ts < 10000000000:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
    elif isinstance(ts, str):
        try:
            # Handle ISO string with or without Z
            clean_ts = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            raise ValueError(f"Invalid timestamp format: '{ts}'. Expected epoch or ISO 8601 string.")
    else:
        raise ValueError(f"Unsupported timestamp type: {type(ts)}")

    timestamp_sec = int(dt.timestamp())
    timestamp_ms = int(timestamp_sec * 1000 + dt.microsecond // 1000)
    timestamp_iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return timestamp_ms, timestamp_sec, timestamp_iso

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance in kilometers between two GPS points."""
    r = 6371.0  # Earth radius in kilometers
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c

