"""Unit tests for waste-api Lambda function (GET /bins and GET /route)."""
import json
import pytest
from unittest.mock import MagicMock
from lambdas.waste_api.lambda_function import lambda_handler
from lambdas.common.utils import to_decimal

def test_get_bins_with_data(mocked_aws):
    """Verify GET /bins returns active bins sorted alphabetically, excluding __ROUTE__."""
    waste_bins = mocked_aws["waste_bins_table"]

    # Seed bins and a route record
    waste_bins.put_item(Item=to_decimal({
        "bin_id": "BIN-002",
        "fill_level": 45.0,
        "latitude": 40.7130,
        "longitude": -74.0050,
        "alerted": False
    }))
    waste_bins.put_item(Item=to_decimal({
        "bin_id": "BIN-001",
        "fill_level": 88.0,
        "latitude": 40.7128,
        "longitude": -74.0060,
        "alerted": True
    }))
    waste_bins.put_item(Item=to_decimal({
        "bin_id": "__ROUTE__",
        "total_distance_km": 10.5,
        "stops": []
    }))

    # API Gateway HTTP API v2.0 event
    event = {
        "rawPath": "/bins",
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/bins"
            }
        }
    }

    response = lambda_handler(event)
    assert response["statusCode"] == 200
    assert "Access-Control-Allow-Origin" in response["headers"]

    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["total_bins"] == 2
    # Verify __ROUTE__ was excluded
    bin_ids = [b["bin_id"] for b in body["bins"]]
    assert bin_ids == ["BIN-001", "BIN-002"]  # Alphabetical order
    assert "__ROUTE__" not in bin_ids

def test_get_bins_empty_table(mocked_aws):
    """Verify GET /bins returns empty list when no bins are registered."""
    event = {
        "rawPath": "/bins",
        "requestContext": {
            "http": {
                "method": "GET"
            }
        }
    }
    response = lambda_handler(event)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["total_bins"] == 0
    assert body["bins"] == []

def test_get_route_with_active_route(mocked_aws):
    """Verify GET /route returns the active cached collection tour."""
    waste_bins = mocked_aws["waste_bins_table"]

    route_data = {
        "bin_id": "__ROUTE__",
        "generated_at": "2026-10-17T18:00:00Z",
        "total_distance_km": 14.5,
        "initial_distance_km": 18.2,
        "num_bins_serviced": 2,
        "depot": {"name": "Central Depot", "latitude": 40.7100, "longitude": -74.0100},
        "stops": [
            {"stop_number": 1, "bin_id": "BIN-001", "latitude": 40.7128, "longitude": -74.0060},
            {"stop_number": 2, "bin_id": "BIN-002", "latitude": 40.7130, "longitude": -74.0050}
        ]
    }
    waste_bins.put_item(Item=to_decimal(route_data))

    event = {
        "rawPath": "/route",
        "requestContext": {
            "http": {
                "method": "GET"
            }
        }
    }

    response = lambda_handler(event)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["route_id"] == "__ROUTE__"
    assert body["total_distance_km"] == 14.5
    assert len(body["stops"]) == 2
    assert body["stops"][0]["bin_id"] == "BIN-001"

def test_get_route_empty(mocked_aws):
    """Verify GET /route returns default structure when analytics hasn't run yet."""
    event = {
        "rawPath": "/route",
        "requestContext": {
            "http": {
                "method": "GET"
            }
        }
    }
    response = lambda_handler(event)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["route_id"] == "__ROUTE__"
    assert body["total_distance_km"] == 0.0
    assert body["stops"] == []
    assert "depot" in body

def test_cors_options_preflight(mocked_aws):
    """Verify OPTIONS request returns 200 with CORS headers."""
    event = {
        "rawPath": "/bins",
        "requestContext": {
            "http": {
                "method": "OPTIONS"
            }
        }
    }
    response = lambda_handler(event)
    assert response["statusCode"] == 200
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"

def test_method_not_allowed(mocked_aws):
    """Verify non-GET requests (e.g. POST, DELETE) return 405 Method Not Allowed."""
    event = {
        "rawPath": "/bins",
        "requestContext": {
            "http": {
                "method": "POST"
            }
        }
    }
    response = lambda_handler(event)
    assert response["statusCode"] == 405
    body = json.loads(response["body"])
    assert "not allowed" in body["message"]

def test_not_found_endpoint(mocked_aws):
    """Verify unmapped routes return 404 Not Found."""
    event = {
        "rawPath": "/unknown-endpoint",
        "requestContext": {
            "http": {
                "method": "GET"
            }
        }
    }
    response = lambda_handler(event)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "Resource not found" in body["message"]

def test_api_v1_payload_format(mocked_aws):
    """Verify backwards compatibility with API Gateway v1.0 payload format."""
    event = {
        "path": "/bins",
        "httpMethod": "GET"
    }
    response = lambda_handler(event)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"

def test_database_error_handling(mocked_aws):
    """Verify database exceptions return a clean 500 Internal Server Error."""
    mock_db = MagicMock()
    mock_db.scan_all_bins.side_effect = Exception("Simulated DynamoDB connection failure")

    event = {
        "rawPath": "/bins",
        "requestContext": {
            "http": {
                "method": "GET"
            }
        }
    }
    response = lambda_handler(event, dynamodb_svc=mock_db)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "Database error" in body["message"]

