"""AWS Lambda function: waste-api
Handles HTTP GET /bins and GET /route for the Leaflet dashboard.
"""
import logging
from typing import Dict, Any, Optional

from lambdas.common.config import get_config
from lambdas.common.dynamodb_service import DynamoDBService
from lambdas.common.utils import build_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handle_get_bins(db: DynamoDBService) -> Dict[str, Any]:
    """Retrieve all monitored physical bins from DynamoDB."""
    try:
        bins = db.scan_all_bins()
        # Sort bins alphabetically by bin_id for consistent presentation
        bins.sort(key=lambda b: b.get("bin_id", ""))
        return build_response(200, {
            "status": "success",
            "total_bins": len(bins),
            "bins": bins
        })
    except Exception as e:
        logger.error(f"Error querying bins: {str(e)}")
        return build_response(500, {
            "status": "error",
            "message": f"Database error querying bins: {str(e)}"
        })

def handle_get_route(db: DynamoDBService, config: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve the cached active collection route from DynamoDB."""
    try:
        route = db.get_route_record()
        if not route:
            # Return an empty route structure if analytics hasn't run yet
            return build_response(200, {
                "status": "success",
                "route_id": "__ROUTE__",
                "bin_id": "__ROUTE__",
                "generated_at": None,
                "total_distance_km": 0.0,
                "initial_distance_km": 0.0,
                "num_bins_serviced": 0,
                "depot": {
                    "name": config["DEPOT_NAME"],
                    "latitude": config["DEPOT_LATITUDE"],
                    "longitude": config["DEPOT_LONGITUDE"]
                },
                "stops": [],
                "message": "No optimized collection route has been generated yet."
            })

        response_payload = {
            "status": "success",
            "route_id": "__ROUTE__",
            **route
        }
        return build_response(200, response_payload)
    except Exception as e:
        logger.error(f"Error querying collection route: {str(e)}")
        return build_response(500, {
            "status": "error",
            "message": f"Database error querying route: {str(e)}"
        })

def lambda_handler(
    event: Dict[str, Any],
    context: Any = None,
    dynamodb_svc: Optional[DynamoDBService] = None
) -> Dict[str, Any]:
    """
    Main Lambda entrypoint for the REST API.
    Supports API Gateway HTTP API v2.0 and REST API v1.0 payload formats.
    """
    config = get_config()
    db = dynamodb_svc or DynamoDBService()

    # 1. Extract HTTP method
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "GET"
    ).upper()

    # 2. Extract path
    path = (
        event.get("rawPath")
        or event.get("requestContext", {}).get("http", {}).get("path")
        or event.get("path")
        or ""
    ).rstrip("/").lower()

    logger.info(f"Received API request: {method} {path}")

    # 3. Handle CORS preflight OPTIONS requests
    if method == "OPTIONS":
        return build_response(200, {"status": "ok"})

    # 4. Enforce GET-only for this service
    if method != "GET":
        return build_response(405, {
            "status": "error",
            "message": f"HTTP method '{method}' is not allowed on this resource. Only GET is supported."
        })

    # 5. Dispatch based on route path
    if path.endswith("/bins") or path == "bins":
        return handle_get_bins(db)

    elif path.endswith("/route") or path == "route":
        return handle_get_route(db, config)

    # 6. Unmatched endpoint
    return build_response(404, {
        "status": "error",
        "message": f"Resource not found at path '{path}'. Available endpoints: GET /bins, GET /route"
    })

