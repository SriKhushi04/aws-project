"""End-to-end integration test simulating the entire system pipeline without AWS credentials.

Flow:
1. Simulator generates realistic telemetry for 12 bins across VIT Vellore campus.
2. waste-ingest Lambda validates and ingests telemetry, updates WasteBins, writes BinReadings (with 7d TTL),
   archives batch to S3, and triggers SNS alert for critical bins.
3. Multiple simulated ticks populate time-series readings in DynamoDB.
4. waste-analytics Lambda runs regression forecasting, computes priority scores, and solves collection route.
5. waste-api Lambda serves GET /bins and GET /route.
6. Asserts that the entire data pipeline is consistent end-to-end.
"""
import json
import pytest
from simulator.simulate_bins import WasteBinSimulator
from lambdas.waste_ingest.lambda_function import lambda_handler as ingest_handler
from lambdas.waste_analytics.lambda_function import lambda_handler as analytics_handler
from lambdas.waste_api.lambda_function import lambda_handler as api_handler

def test_full_system_integration_pipeline(mocked_aws):
    """Verify complete data flow from Simulator -> Ingest -> Analytics -> API."""
    waste_bins_table = mocked_aws["waste_bins_table"]
    bin_readings_table = mocked_aws["bin_readings_table"]
    s3_client = mocked_aws["s3"]
    sns_client = mocked_aws["sns"]

    # 1. Initialize Simulator
    sim = WasteBinSimulator()
    assert len(sim.bins) == 12

    # Force BIN-005 to start near alert threshold to verify alert trigger
    for b in sim.bins:
        if b["bin_id"] == "BIN-005":
            b["initial_fill"] = 88.0
            b["fill_rate_per_hour"] = 12.0

    # 2. Simulate Tick 1 and Ingest
    readings_tick1 = sim.tick(delta_seconds=300.0)  # 5 minutes
    ingest_event1 = {
        "body": json.dumps({"readings": readings_tick1})
    }
    ingest_res1 = ingest_handler(ingest_event1)
    assert ingest_res1["statusCode"] == 200
    body1 = json.loads(ingest_res1["body"])
    assert body1["ingested_count"] == 12

    # Verify S3 archive object was created
    s3_key = body1.get("s3_archive_key")
    assert s3_key is not None
    s3_obj = s3_client.get_object(Bucket="test-smart-waste-archive", Key=s3_key)
    assert s3_obj is not None

    # Verify WasteBins updated
    b5_state = waste_bins_table.get_item(Key={"bin_id": "BIN-005"}).get("Item")
    assert b5_state is not None
    assert float(b5_state["fill_level"]) >= 85.0
    assert b5_state["alerted"] is True

    # 3. Simulate Tick 2 and Tick 3 to build time-series history
    readings_tick2 = sim.tick(delta_seconds=300.0)
    ingest_handler({"body": json.dumps({"readings": readings_tick2})})

    readings_tick3 = sim.tick(delta_seconds=300.0)
    ingest_handler({"body": json.dumps({"readings": readings_tick3})})

    # Verify BinReadings has multiple timestamp records per bin with 7-day TTL
    b5_readings = bin_readings_table.query(
        KeyConditionExpression="bin_id = :bid",
        ExpressionAttributeValues={":bid": "BIN-005"}
    ).get("Items", [])
    assert len(b5_readings) >= 3
    for r in b5_readings:
        assert "ttl" in r
        assert int(r["ttl"]) > int(r["timestamp"]) / 1000

    # 4. Trigger Scheduled waste-analytics Lambda
    analytics_res = analytics_handler()
    assert analytics_res["statusCode"] == 200
    analytics_body = json.loads(analytics_res["body"])
    assert analytics_body["status"] == "success"
    assert analytics_body["bins_analyzed"] == 12
    assert analytics_body["bins_selected_for_route"] >= 1

    # Verify route stored in DynamoDB under bin_id="__ROUTE__"
    route_item = waste_bins_table.get_item(Key={"bin_id": "__ROUTE__"}).get("Item")
    assert route_item is not None
    assert route_item["bin_id"] == "__ROUTE__"
    assert float(route_item["total_distance_km"]) > 0
    assert route_item["depot"]["name"] == "VIT Estates & Maintenance Depot"
    assert len(route_item["stops"]) >= 1

    # 5. Invoke waste-api Lambda: GET /bins
    get_bins_event = {
        "rawPath": "/bins",
        "requestContext": {"http": {"method": "GET"}}
    }
    bins_api_res = api_handler(get_bins_event)
    assert bins_api_res["statusCode"] == 200
    bins_data = json.loads(bins_api_res["body"])
    assert bins_data["status"] == "success"
    assert bins_data["total_bins"] == 12

    # Verify all bins have predictions and priority scores
    for b in bins_data["bins"]:
        assert b["bin_id"].startswith("BIN-")
        assert "fill_level" in b
        assert "priority_score" in b
        assert "alerted" in b

    # 6. Invoke waste-api Lambda: GET /route
    get_route_event = {
        "rawPath": "/route",
        "requestContext": {"http": {"method": "GET"}}
    }
    route_api_res = api_handler(get_route_event)
    assert route_api_res["statusCode"] == 200
    route_data = json.loads(route_api_res["body"])
    assert route_data["status"] == "success"
    assert route_data["route_id"] == "__ROUTE__"
    assert route_data["depot"]["name"] == "VIT Estates & Maintenance Depot"
    assert len(route_data["stops"]) >= 1
    assert route_data["stops"][0]["stop_number"] == 1

