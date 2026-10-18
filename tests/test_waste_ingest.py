"""Unit tests for waste-ingest Lambda function."""
import json
import pytest
from lambdas.waste_ingest.lambda_function import lambda_handler

def test_validation_missing_bin_id(mocked_aws):
    """Verify that a reading without a valid bin_id returns 400."""
    event = {
        "body": json.dumps({
            "readings": [
                {
                    "fill_level": 50.0,
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                    "timestamp": 1760721300000
                }
            ]
        })
    }
    response = lambda_handler(event)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "missing a valid non-empty 'bin_id'" in body["message"]

def test_validation_out_of_range_fill_level(mocked_aws):
    """Verify that fill levels < 0 or > 100 return 400."""
    # Test negative fill
    event_neg = {
        "body": json.dumps({
            "readings": [{
                "bin_id": "BIN-001",
                "fill_level": -5.0,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timestamp": 1760721300000
            }]
        })
    }
    resp_neg = lambda_handler(event_neg)
    assert resp_neg["statusCode"] == 400
    assert "out of valid range" in json.loads(resp_neg["body"])["message"]

    # Test overflow > 100%
    event_high = {
        "body": json.dumps({
            "readings": [{
                "bin_id": "BIN-001",
                "fill_level": 105.0,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timestamp": 1760721300000
            }]
        })
    }
    resp_high = lambda_handler(event_high)
    assert resp_high["statusCode"] == 400
    assert "out of valid range" in json.loads(resp_high["body"])["message"]

def test_validation_coordinates_and_timestamp(mocked_aws):
    """Verify that out-of-range coordinates or bad timestamps return 400."""
    # Bad latitude (> 90)
    event_bad_lat = {
        "body": json.dumps({
            "readings": [{
                "bin_id": "BIN-001",
                "fill_level": 50.0,
                "latitude": 95.0,
                "longitude": -74.0060,
                "timestamp": 1760721300000
            }]
        })
    }
    assert lambda_handler(event_bad_lat)["statusCode"] == 400

    # Bad longitude (> 180)
    event_bad_lon = {
        "body": json.dumps({
            "readings": [{
                "bin_id": "BIN-001",
                "fill_level": 50.0,
                "latitude": 40.7128,
                "longitude": 185.0,
                "timestamp": 1760721300000
            }]
        })
    }
    assert lambda_handler(event_bad_lon)["statusCode"] == 400

    # Bad timestamp
    event_bad_ts = {
        "body": json.dumps({
            "readings": [{
                "bin_id": "BIN-001",
                "fill_level": 50.0,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timestamp": "not-a-timestamp"
            }]
        })
    }
    assert lambda_handler(event_bad_ts)["statusCode"] == 400

def test_successful_ingestion_and_storage(mocked_aws):
    """Verify successful ingestion updates WasteBins and writes BinReadings."""
    event = {
        "body": json.dumps({
            "readings": [{
                "bin_id": "BIN-001",
                "location_name": "Main Quad",
                "fill": 65.5,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timestamp": 1760721300000
            }]
        })
    }
    response = lambda_handler(event)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["ingested_count"] == 1

    # Verify WasteBins item
    waste_bins = mocked_aws["waste_bins_table"]
    bin_item = waste_bins.get_item(Key={"bin_id": "BIN-001"}).get("Item")
    assert bin_item is not None
    assert float(bin_item["fill_level"]) == 65.5
    assert float(bin_item["latitude"]) == 40.7128
    assert float(bin_item["longitude"]) == -74.0060
    assert bin_item["alerted"] is False

    # Verify BinReadings item
    bin_readings = mocked_aws["bin_readings_table"]
    reading_item = bin_readings.get_item(Key={"bin_id": "BIN-001", "timestamp": 1760721300000}).get("Item")
    assert reading_item is not None
    assert float(reading_item["fill_level"]) == 65.5

def test_seven_day_ttl_calculation(mocked_aws):
    """Verify that BinReadings items receive an epoch TTL equal to timestamp + 7 days (604,800s)."""
    timestamp_sec = 1760721300
    timestamp_ms = timestamp_sec * 1000
    expected_ttl = timestamp_sec + (7 * 24 * 3600)

    event = {
        "body": json.dumps({
            "readings": [{
                "bin_id": "BIN-TTL-TEST",
                "fill_level": 40.0,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timestamp": timestamp_ms
            }]
        })
    }
    response = lambda_handler(event)
    assert response["statusCode"] == 200

    bin_readings = mocked_aws["bin_readings_table"]
    item = bin_readings.get_item(Key={"bin_id": "BIN-TTL-TEST", "timestamp": timestamp_ms}).get("Item")
    assert item is not None
    assert int(item["ttl"]) == expected_ttl

def test_s3_raw_batch_archival(mocked_aws):
    """Verify that the raw ingestion batch is archived to S3."""
    event = {
        "body": json.dumps({
            "readings": [{
                "bin_id": "BIN-001",
                "fill_level": 55.0,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timestamp": 1760721300000
            }]
        })
    }
    response = lambda_handler(event)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    s3_key = body.get("s3_archive_key")
    assert s3_key is not None
    assert s3_key.startswith("raw-readings/")

    # Verify S3 object content
    s3_client = mocked_aws["s3"]
    obj = s3_client.get_object(Bucket="test-smart-waste-archive", Key=s3_key)
    stored_data = json.loads(obj["Body"].read().decode("utf-8"))
    assert "batch_data" in stored_data
    assert stored_data["batch_data"]["readings"][0]["bin_id"] == "BIN-001"

def test_alert_hysteresis_state_machine(mocked_aws):
    """
    Verify complete alert hysteresis cycle:
    1. Fill >= 85%: Triggers SNS alert, alerted set to True.
    2. Fill >= 85% again: Alert suppressed, alerted stays True.
    3. Fill between 50% and 85%: Alert suppressed, alerted stays True.
    4. Fill < 50%: Alert reset, alerted set to False.
    5. Fill < 50% again: No alert, alerted stays False.
    """
    waste_bins = mocked_aws["waste_bins_table"]

    # Step 1: Fill reaches 87% (Crosses threshold >= 85%)
    ev1 = {
        "body": json.dumps({
            "bin_id": "BIN-HYST",
            "fill_level": 87.0,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1760721300000
        })
    }
    r1 = lambda_handler(ev1)
    assert r1["statusCode"] == 200
    assert json.loads(r1["body"])["alerts_triggered"] == 1
    bin_state1 = waste_bins.get_item(Key={"bin_id": "BIN-HYST"}).get("Item")
    assert bin_state1["alerted"] is True

    # Step 2: Fill increases to 89% (Already alerted; duplicate suppressed)
    ev2 = {
        "body": json.dumps({
            "bin_id": "BIN-HYST",
            "fill_level": 89.0,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1760721360000
        })
    }
    r2 = lambda_handler(ev2)
    assert r2["statusCode"] == 200
    assert json.loads(r2["body"])["alerts_triggered"] == 0
    bin_state2 = waste_bins.get_item(Key={"bin_id": "BIN-HYST"}).get("Item")
    assert bin_state2["alerted"] is True

    # Step 3: Fill drops slightly to 70% (Still above 50% reset threshold)
    ev3 = {
        "body": json.dumps({
            "bin_id": "BIN-HYST",
            "fill_level": 70.0,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1760721420000
        })
    }
    r3 = lambda_handler(ev3)
    assert r3["statusCode"] == 200
    assert json.loads(r3["body"])["alerts_triggered"] == 0
    bin_state3 = waste_bins.get_item(Key={"bin_id": "BIN-HYST"}).get("Item")
    assert bin_state3["alerted"] is True

    # Step 4: Bin is emptied; fill drops to 30% (< 50% reset threshold)
    ev4 = {
        "body": json.dumps({
            "bin_id": "BIN-HYST",
            "fill_level": 30.0,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": 1760721480000
        })
    }
    r4 = lambda_handler(ev4)
    assert r4["statusCode"] == 200
    assert json.loads(r4["body"])["alerts_triggered"] == 0
    bin_state4 = waste_bins.get_item(Key={"bin_id": "BIN-HYST"}).get("Item")
    assert bin_state4["alerted"] is False  # Successfully reset!

def test_ingest_cors_options_preflight(mocked_aws):
    """Verify OPTIONS preflight request to waste-ingest returns 200 with CORS headers."""
    event = {
        "requestContext": {
            "http": {
                "method": "OPTIONS"
            }
        }
    }
    response = lambda_handler(event)
    assert response["statusCode"] == 200
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"

