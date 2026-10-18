"""Unit tests for waste-analytics Lambda function and predictive routing algorithms."""
import json
import pytest
from lambdas.waste_analytics.predictor import (
    filter_readings_after_latest_reset,
    fit_linear_regression,
    predict_hours_to_capacity,
    calculate_priority_score
)
from lambdas.waste_analytics.optimizer import (
    nearest_neighbour_tour,
    two_opt_optimize,
    compute_total_tour_distance,
    solve_collection_route
)
from lambdas.waste_analytics.lambda_function import lambda_handler
from lambdas.common.utils import to_decimal

# ==============================================================================
# 1. Predictive Regression & Filtering Tests
# ==============================================================================

def test_regression_filtering_after_reset():
    """Verify that readings prior to an emptying event (drop >= 15%) are excluded."""
    readings = [
        {"timestamp": 1000000, "fill_level": 75.0},
        {"timestamp": 2000000, "fill_level": 92.0},
        {"timestamp": 3000000, "fill_level": 12.0},  # Emptied! Drop of 80%
        {"timestamp": 4000000, "fill_level": 25.0},
        {"timestamp": 5000000, "fill_level": 38.0}
    ]
    filtered = filter_readings_after_latest_reset(readings, drop_threshold=15.0)
    assert len(filtered) == 3
    assert filtered[0]["fill_level"] == 12.0
    assert filtered[-1]["fill_level"] == 38.0

def test_linear_regression_math_and_forecast():
    """Verify OLS regression calculates exact slope and hours to 90%."""
    # 20% fill increase every hour (3600 seconds = 3,600,000 ms)
    readings = [
        {"timestamp": 1000000000000, "fill_level": 20.0},
        {"timestamp": 1000003600000, "fill_level": 40.0},
        {"timestamp": 1000007200000, "fill_level": 60.0}
    ]
    slope, intercept, rate_hr = fit_linear_regression(readings)
    assert slope is not None
    assert round(rate_hr, 1) == 20.0

    # Current fill 60%, rate 20%/hr -> exactly 1.5 hours to 90%
    hours = predict_hours_to_capacity(current_fill=60.0, slope_per_sec=slope, target_capacity=90.0)
    assert hours == 1.5

def test_regression_edge_cases():
    """Verify edge cases: negative slope, flat fill, single reading, fill >= 90%."""
    # 1. Single reading
    single = [{"timestamp": 1000000000000, "fill_level": 50.0}]
    slope, _, _ = fit_linear_regression(single)
    assert slope is None
    assert predict_hours_to_capacity(50.0, slope) is None

    # 2. Declining fill (negative slope)
    declining = [
        {"timestamp": 1000000000000, "fill_level": 70.0},
        {"timestamp": 1000003600000, "fill_level": 50.0}
    ]
    neg_slope, _, _ = fit_linear_regression(declining)
    assert neg_slope < 0
    assert predict_hours_to_capacity(50.0, neg_slope) is None

    # 3. Already >= 90%
    assert predict_hours_to_capacity(92.5, slope_per_sec=0.01) == 0.0

# ==============================================================================
# 2. Priority Scoring Tests
# ==============================================================================

def test_priority_scoring():
    """Verify priority score assigns highest urgency to overflowing bins."""
    score_full = calculate_priority_score(current_fill=92.0, hours_to_90=0.0)
    assert score_full == 100.0

    score_urgent = calculate_priority_score(current_fill=85.0, hours_to_90=0.5)
    score_moderate = calculate_priority_score(current_fill=60.0, hours_to_90=5.0)
    score_safe = calculate_priority_score(current_fill=20.0, hours_to_90=None)

    assert score_urgent > score_moderate > score_safe
    assert score_urgent >= 60.0  # Eligible for collection

# ==============================================================================
# 3. Route Optimization Tests (2-Opt & Nearest-Neighbour)
# ==============================================================================

def test_two_opt_distance_improvement():
    """
    Verify that 2-Opt untangles crossing edges and reduces or matches tour distance.
    Create a polygon with crossed path.
    """
    depot = {"bin_id": "DEPOT", "latitude": 40.7100, "longitude": -74.0100}
    # Nodes arranged such that naive order crosses
    b1 = {"bin_id": "B1", "latitude": 40.7200, "longitude": -74.0200}
    b2 = {"bin_id": "B2", "latitude": 40.7300, "longitude": -74.0100}
    b3 = {"bin_id": "B3", "latitude": 40.7200, "longitude": -74.0000}
    b4 = {"bin_id": "B4", "latitude": 40.7300, "longitude": -74.0300}

    bins = [b1, b2, b3, b4]
    route_result = solve_collection_route(depot, bins)

    assert route_result["num_bins_serviced"] == 4
    # Optimized distance must be less than or equal to initial Nearest-Neighbour distance
    assert route_result["total_distance_km"] <= route_result["initial_distance_km"]

def test_empty_route_when_no_bins():
    """Verify route solver handles empty bin list safely."""
    depot = {"bin_id": "DEPOT", "latitude": 40.7100, "longitude": -74.0100}
    route_result = solve_collection_route(depot, [])
    assert route_result["num_bins_serviced"] == 0
    assert route_result["total_distance_km"] == 0.0
    assert route_result["stops"] == []

# ==============================================================================
# 4. End-to-End Scheduled Analytics Lambda Handler Test
# ==============================================================================

def test_waste_analytics_handler_integration(mocked_aws):
    """
    Test full waste-analytics pipeline:
    - Scans WasteBins
    - Fits OLS regression on readings in BinReadings
    - Persists predictions to WasteBins
    - Solves route for bins with priority >= 60.0
    - Persists route under bin_id="__ROUTE__" in WasteBins
    """
    dynamodb = mocked_aws["dynamodb"]
    waste_bins = mocked_aws["waste_bins_table"]
    bin_readings = mocked_aws["bin_readings_table"]

    # 1. Seed 3 bins in WasteBins
    bins_seed = [
        {"bin_id": "BIN-CRITICAL", "fill_level": 88.0, "latitude": 40.7128, "longitude": -74.0060, "alerted": True},
        {"bin_id": "BIN-GROWING",  "fill_level": 70.0, "latitude": 40.7150, "longitude": -74.0080, "alerted": False},
        {"bin_id": "BIN-EMPTY",    "fill_level": 15.0, "latitude": 40.7180, "longitude": -74.0020, "alerted": False}
    ]
    for b in bins_seed:
        waste_bins.put_item(Item=to_decimal(b))

    # 2. Seed time-series readings for BIN-GROWING to create positive slope
    # 10% increase every hour
    base_ts = 1760720000000
    for hour, fill in enumerate([50.0, 60.0, 70.0]):
        bin_readings.put_item(Item=to_decimal({
            "bin_id": "BIN-GROWING",
            "timestamp": base_ts + (hour * 3600 * 1000),
            "fill_level": fill,
            "ttl": 1761320000
        }))

    # 3. Execute analytics Lambda handler
    response = lambda_handler()
    assert response["statusCode"] == 200
    body = json.loads(response["body"])

    assert body["status"] == "success"
    assert body["bins_analyzed"] == 3
    assert body["bins_selected_for_route"] >= 1

    # 4. Verify predictions were written to WasteBins
    critical_item = waste_bins.get_item(Key={"bin_id": "BIN-CRITICAL"}).get("Item")
    assert critical_item is not None
    assert "priority_score" in critical_item
    assert float(critical_item["priority_score"]) >= 60.0

    growing_item = waste_bins.get_item(Key={"bin_id": "BIN-GROWING"}).get("Item")
    assert growing_item is not None
    assert "predicted_hours_to_90" in growing_item
    assert float(growing_item["predicted_hours_to_90"]) > 0

    # 5. Verify route was stored under bin_id="__ROUTE__"
    route_item = waste_bins.get_item(Key={"bin_id": "__ROUTE__"}).get("Item")
    assert route_item is not None
    assert route_item["bin_id"] == "__ROUTE__"
    assert "total_distance_km" in route_item
    assert "stops" in route_item
    assert len(route_item["stops"]) >= 1
    assert route_item["depot"]["name"] == "VIT Estates & Maintenance Depot"
    assert round(float(route_item["depot"]["latitude"]), 4) == 12.9685
    assert round(float(route_item["depot"]["longitude"]), 4) == 79.1550

