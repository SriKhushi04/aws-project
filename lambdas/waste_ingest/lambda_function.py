"""AWS Lambda function: waste-ingest
Ingests, validates, persists sensor readings, archives batches to S3,
and enforces SNS threshold alerting with hysteresis.
"""
import json
import logging
from typing import Dict, Any, List, Tuple, Optional

from lambdas.common.config import get_config
from lambdas.common.dynamodb_service import DynamoDBService
from lambdas.common.s3_service import S3Service
from lambdas.common.sns_service import SNSService
from lambdas.common.utils import (
    build_response,
    parse_and_validate_timestamp
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SEVEN_DAYS_SECONDS = 7 * 24 * 3600  # 604,800 seconds

def validate_reading(reading: Dict[str, Any], index: int) -> Dict[str, Any]:
    """
    Validate a single reading payload.
    Expected fields: bin_id, fill (or fill_level), latitude, longitude, timestamp.
    Returns cleaned reading dict with normalized fields.
    Raises ValueError on validation failure.
    """
    if not isinstance(reading, dict):
        raise ValueError(f"Reading item at index {index} must be a JSON object.")

    # 1. Validate bin_id
    bin_id = reading.get("bin_id")
    if not bin_id or not isinstance(bin_id, str) or not bin_id.strip():
        raise ValueError(f"Reading at index {index} is missing a valid non-empty 'bin_id'.")
    bin_id = bin_id.strip()

    # 2. Validate fill / fill_level
    raw_fill = reading.get("fill") if "fill" in reading else reading.get("fill_level")
    if raw_fill is None:
        raise ValueError(f"Reading for bin '{bin_id}' at index {index} is missing 'fill' or 'fill_level'.")
    try:
        fill_level = float(raw_fill)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid fill level '{raw_fill}' for bin '{bin_id}'. Must be a number.")
    if fill_level < 0.0 or fill_level > 100.0:
        raise ValueError(f"Fill level {fill_level}% for bin '{bin_id}' out of valid range (0.0 - 100.0%).")

    # 3. Validate latitude
    raw_lat = reading.get("latitude")
    if raw_lat is None:
        raise ValueError(f"Reading for bin '{bin_id}' at index {index} is missing 'latitude'.")
    try:
        latitude = float(raw_lat)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid latitude '{raw_lat}' for bin '{bin_id}'. Must be a number.")
    if latitude < -90.0 or latitude > 90.0:
        raise ValueError(f"Latitude {latitude} for bin '{bin_id}' out of valid range (-90.0 to 90.0).")

    # 4. Validate longitude
    raw_lon = reading.get("longitude")
    if raw_lon is None:
        raise ValueError(f"Reading for bin '{bin_id}' at index {index} is missing 'longitude'.")
    try:
        longitude = float(raw_lon)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid longitude '{raw_lon}' for bin '{bin_id}'. Must be a number.")
    if longitude < -180.0 or longitude > 180.0:
        raise ValueError(f"Longitude {longitude} for bin '{bin_id}' out of valid range (-180.0 to 180.0).")

    # 5. Validate timestamp
    raw_ts = reading.get("timestamp")
    if raw_ts is None:
        raise ValueError(f"Reading for bin '{bin_id}' at index {index} is missing 'timestamp'.")
    try:
        timestamp_ms, timestamp_sec, timestamp_iso = parse_and_validate_timestamp(raw_ts)
    except Exception as e:
        raise ValueError(f"Invalid timestamp '{raw_ts}' for bin '{bin_id}': {str(e)}")

    return {
        "bin_id": bin_id,
        "fill_level": fill_level,
        "latitude": latitude,
        "longitude": longitude,
        "timestamp_ms": timestamp_ms,
        "timestamp_sec": timestamp_sec,
        "timestamp_iso": timestamp_iso,
        "location_name": reading.get("location_name")
    }

def lambda_handler(
    event: Dict[str, Any],
    context: Any = None,
    dynamodb_svc: Optional[DynamoDBService] = None,
    s3_svc: Optional[S3Service] = None,
    sns_svc: Optional[SNSService] = None
) -> Dict[str, Any]:
    """Main Lambda entrypoint for waste ingestion."""
    config = get_config()
    db = dynamodb_svc or DynamoDBService()
    s3 = s3_svc or S3Service()
    sns = sns_svc or SNSService()

    # 0. Handle CORS preflight OPTIONS requests
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or ""
    ).upper()
    if method == "OPTIONS":
        return build_response(200, {"status": "ok"})

    # 1. Parse body from API Gateway event
    body = event.get("body", event)
    if isinstance(body, str):
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            return build_response(400, {
                "status": "error",
                "message": f"Malformed JSON request body: {str(e)}"
            })
    elif isinstance(body, dict):
        payload = body
    elif isinstance(body, list):
        payload = {"readings": body}
    else:
        return build_response(400, {
            "status": "error",
            "message": "Invalid request body format."
        })

    # 2. Extract readings list
    if "readings" in payload and isinstance(payload["readings"], list):
        raw_readings = payload["readings"]
    elif "bin_id" in payload:
        raw_readings = [payload]
    else:
        return build_response(400, {
            "status": "error",
            "message": "Payload must contain a 'readings' array or a single bin reading object."
        })

    if not raw_readings:
        return build_response(400, {
            "status": "error",
            "message": "The 'readings' array cannot be empty."
        })

    # 3. Validate all readings
    validated_readings: List[Dict[str, Any]] = []
    try:
        for idx, item in enumerate(raw_readings):
            cleaned = validate_reading(item, idx)
            validated_readings.append(cleaned)
    except ValueError as val_err:
        logger.warning(f"Validation error: {str(val_err)}")
        return build_response(400, {
            "status": "error",
            "message": str(val_err)
        })

    # 4. Archive raw batch to S3
    try:
        s3_archive_key = s3.archive_batch(payload)
    except Exception as s3_err:
        logger.error(f"S3 archival failed: {str(s3_err)}")
        s3_archive_key = None

    # 5. Process each reading (DynamoDB + Hysteresis Alerting)
    alerts_triggered = 0
    alert_threshold = config["ALERT_THRESHOLD"]  # Default 85.0
    reset_threshold = config["RESET_THRESHOLD"]  # Default 50.0

    for reading in validated_readings:
        bin_id = reading["bin_id"]
        fill_level = reading["fill_level"]
        timestamp_ms = reading["timestamp_ms"]
        timestamp_sec = reading["timestamp_sec"]
        timestamp_iso = reading["timestamp_iso"]
        latitude = reading["latitude"]
        longitude = reading["longitude"]
        location_name = reading.get("location_name")

        # 5a. Calculate 7-day TTL (current reading timestamp + 7 days)
        ttl_sec = timestamp_sec + SEVEN_DAYS_SECONDS

        # 5b. Check current bin state for hysteresis
        existing_bin = db.get_bin(bin_id)
        current_alerted = existing_bin.get("alerted", False) if existing_bin else False

        # 5c. Apply Alert Hysteresis Logic
        new_alerted = current_alerted
        if fill_level >= alert_threshold:
            if not current_alerted:
                # Trigger alert on crossing threshold
                sns.publish_threshold_alert(
                    bin_id=bin_id,
                    fill_level=fill_level,
                    timestamp_iso=timestamp_iso,
                    latitude=latitude,
                    longitude=longitude
                )
                new_alerted = True
                alerts_triggered += 1
            else:
                # Already alerted; suppress duplicate
                new_alerted = True
        elif fill_level < reset_threshold:
            # Below reset threshold (50%), clear alert flag
            new_alerted = False

        # 5d. Update current state in WasteBins
        db.update_bin_state(
            bin_id=bin_id,
            fill_level=fill_level,
            alerted=new_alerted,
            last_updated=timestamp_iso,
            latitude=latitude,
            longitude=longitude,
            location_name=location_name
        )

        # 5e. Write time-series record to BinReadings with TTL
        db.put_reading(
            bin_id=bin_id,
            timestamp_ms=timestamp_ms,
            fill_level=fill_level,
            ttl_sec=ttl_sec,
            latitude=latitude,
            longitude=longitude
        )

    return build_response(200, {
        "status": "success",
        "ingested_count": len(validated_readings),
        "alerts_triggered": alerts_triggered,
        "s3_archive_key": s3_archive_key
    })

