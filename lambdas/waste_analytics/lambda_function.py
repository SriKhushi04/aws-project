"""AWS Lambda function: waste-analytics
Performs OLS regression fill-rate forecasting, priority scoring,
and 2-Opt route optimization. Scheduled every 15 minutes by EventBridge.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from lambdas.common.config import get_config
from lambdas.common.dynamodb_service import DynamoDBService
from lambdas.common.utils import build_response
from lambdas.waste_analytics.predictor import (
    filter_readings_after_latest_reset,
    fit_linear_regression,
    predict_hours_to_capacity,
    calculate_priority_score
)
from lambdas.waste_analytics.optimizer import solve_collection_route

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(
    event: Optional[Dict[str, Any]] = None,
    context: Any = None,
    dynamodb_svc: Optional[DynamoDBService] = None
) -> Dict[str, Any]:
    """Main Lambda entrypoint for scheduled waste analytics and routing."""
    config = get_config()
    db = dynamodb_svc or DynamoDBService()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    logger.info("Starting waste-analytics execution...")

    # 1. Fetch all physical bins
    bins = db.scan_all_bins()
    logger.info(f"Retrieved {len(bins)} bins for analysis.")

    analyzed_bins: List[Dict[str, Any]] = []

    # 2. Analyze each bin
    for bin_item in bins:
        bin_id = bin_item["bin_id"]
        current_fill = float(bin_item.get("fill_level", 0.0))

        # Query recent time-series readings
        recent_readings = db.get_recent_readings(bin_id, limit=50)

        # Filter readings after latest emptying/reset event
        active_readings = filter_readings_after_latest_reset(
            recent_readings,
            drop_threshold=config["EMPTYING_DROP_THRESHOLD"]
        )

        # Fit linear regression
        slope_per_sec, intercept, fill_rate_hr = fit_linear_regression(active_readings)

        # Forecast hours to 90%
        hours_to_90 = predict_hours_to_capacity(
            current_fill=current_fill,
            slope_per_sec=slope_per_sec,
            target_capacity=config["CAPACITY_PREDICTION_TARGET"]
        )

        # Calculate priority score
        priority_score = calculate_priority_score(
            current_fill=current_fill,
            hours_to_90=hours_to_90
        )

        # Update bin record in DynamoDB
        db.update_bin_predictions(
            bin_id=bin_id,
            predicted_hours_to_90=hours_to_90,
            priority_score=priority_score,
            fill_rate_per_hour=fill_rate_hr,
            analyzed_at=now_iso
        )

        bin_copy = dict(bin_item)
        bin_copy["predicted_hours_to_90"] = hours_to_90
        bin_copy["priority_score"] = priority_score
        bin_copy["fill_rate_per_hour"] = fill_rate_hr
        analyzed_bins.append(bin_copy)

    # 3. Select bins with priority_score >= 60.0 (up to MAX_ROUTE_STOPS, default 8)
    priority_threshold = config["PRIORITY_THRESHOLD"]  # 60.0
    max_stops = config["MAX_ROUTE_STOPS"]              # 8

    eligible_bins = [b for b in analyzed_bins if b.get("priority_score", 0.0) >= priority_threshold]
    # Sort descending by priority score
    eligible_bins.sort(key=lambda x: x.get("priority_score", 0.0), reverse=True)
    selected_bins = eligible_bins[:max_stops]

    logger.info(f"{len(eligible_bins)} bins met priority threshold >= {priority_threshold}; selecting top {len(selected_bins)} for routing.")

    # 4. Route Optimization
    depot = {
        "bin_id": "DEPOT",
        "name": config["DEPOT_NAME"],
        "latitude": config["DEPOT_LATITUDE"],
        "longitude": config["DEPOT_LONGITUDE"]
    }

    route_result = solve_collection_route(depot, selected_bins)
    route_record = {
        "generated_at": now_iso,
        "total_distance_km": route_result["total_distance_km"],
        "initial_distance_km": route_result.get("initial_distance_km", route_result["total_distance_km"]),
        "num_bins_serviced": route_result["num_bins_serviced"],
        "depot": route_result["depot"],
        "stops": route_result["stops"]
    }

    # 5. Persist route under bin_id="__ROUTE__" in WasteBins
    db.save_route_record(route_record)
    logger.info(f"Persisted optimized collection route: {route_result['total_distance_km']} km, {route_result['num_bins_serviced']} stops.")

    return build_response(200, {
        "status": "success",
        "bins_analyzed": len(bins),
        "bins_selected_for_route": len(selected_bins),
        "route": route_record,
        "timestamp": now_iso
    })

