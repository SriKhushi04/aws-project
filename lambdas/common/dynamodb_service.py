"""DynamoDB service for managing WasteBins and BinReadings tables."""
from typing import Optional, Dict, Any, List
import boto3
from boto3.dynamodb.conditions import Key, Attr
from lambdas.common.config import get_config
from lambdas.common.utils import to_decimal, decimal_to_python

class DynamoDBService:
    def __init__(self, resource=None):
        self.config = get_config()
        self.resource = resource or boto3.resource("dynamodb", region_name=self.config["AWS_REGION"])
        self.waste_bins_table = self.resource.Table(self.config["WASTE_BINS_TABLE"])
        self.bin_readings_table = self.resource.Table(self.config["BIN_READINGS_TABLE"])

    def get_bin(self, bin_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the current state of a bin from WasteBins."""
        response = self.waste_bins_table.get_item(Key={"bin_id": bin_id})
        item = response.get("Item")
        return decimal_to_python(item) if item else None

    def scan_all_bins(self) -> List[Dict[str, Any]]:
        """Retrieve all active physical bins, excluding system records like __ROUTE__."""
        response = self.waste_bins_table.scan(
            FilterExpression=Attr("bin_id").ne("__ROUTE__")
        )
        items = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = self.waste_bins_table.scan(
                FilterExpression=Attr("bin_id").ne("__ROUTE__"),
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response.get("Items", []))
        return [decimal_to_python(item) for item in items]

    def update_bin_state(
        self,
        bin_id: str,
        fill_level: float,
        alerted: bool,
        last_updated: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        location_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update or insert a bin record in the WasteBins table."""
        update_expr_parts = [
            "#fl = :fl",
            "#al = :al",
            "#lu = :lu"
        ]
        expr_attr_names = {
            "#fl": "fill_level",
            "#al": "alerted",
            "#lu": "last_updated"
        }
        expr_attr_values = {
            ":fl": to_decimal(round(float(fill_level), 2)),
            ":al": alerted,
            ":lu": last_updated
        }

        if latitude is not None and longitude is not None:
            update_expr_parts.extend(["#lat = :lat", "#lon = :lon"])
            expr_attr_names["#lat"] = "latitude"
            expr_attr_names["#lon"] = "longitude"
            expr_attr_values[":lat"] = to_decimal(latitude)
            expr_attr_values[":lon"] = to_decimal(longitude)

        if location_name:
            update_expr_parts.append("#loc = :loc")
            expr_attr_names["#loc"] = "location_name"
            expr_attr_values[":loc"] = location_name

        update_expression = "SET " + ", ".join(update_expr_parts)

        response = self.waste_bins_table.update_item(
            Key={"bin_id": bin_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
            ReturnValues="ALL_NEW"
        )
        return decimal_to_python(response.get("Attributes", {}))

    def update_bin_predictions(
        self,
        bin_id: str,
        predicted_hours_to_90: Optional[float],
        priority_score: float,
        fill_rate_per_hour: Optional[float] = None,
        analyzed_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update the predicted overflow and priority score for a bin."""
        update_expr_parts = [
            "#ps = :ps"
        ]
        expr_attr_names = {
            "#ps": "priority_score"
        }
        expr_attr_values = {
            ":ps": to_decimal(round(float(priority_score), 2))
        }

        if predicted_hours_to_90 is not None:
            update_expr_parts.append("#pred = :pred")
            expr_attr_names["#pred"] = "predicted_hours_to_90"
            expr_attr_values[":pred"] = to_decimal(round(float(predicted_hours_to_90), 2))
        else:
            update_expr_parts.append("#pred = :pred")
            expr_attr_names["#pred"] = "predicted_hours_to_90"
            expr_attr_values[":pred"] = None

        if fill_rate_per_hour is not None:
            update_expr_parts.append("#fr = :fr")
            expr_attr_names["#fr"] = "fill_rate_per_hour"
            expr_attr_values[":fr"] = to_decimal(round(float(fill_rate_per_hour), 2))

        if analyzed_at:
            update_expr_parts.append("#aat = :aat")
            expr_attr_names["#aat"] = "analyzed_at"
            expr_attr_values[":aat"] = analyzed_at

        update_expression = "SET " + ", ".join(update_expr_parts)

        response = self.waste_bins_table.update_item(
            Key={"bin_id": bin_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
            ReturnValues="ALL_NEW"
        )
        return decimal_to_python(response.get("Attributes", {}))

    def save_route_record(self, route_data: Dict[str, Any]) -> Dict[str, Any]:
        """Persist the optimized collection route under bin_id='__ROUTE__'."""
        item = {
            "bin_id": "__ROUTE__",
            **route_data
        }
        self.waste_bins_table.put_item(Item=to_decimal(item))
        return route_data

    def get_route_record(self) -> Optional[Dict[str, Any]]:
        """Retrieve the cached active collection route."""
        response = self.waste_bins_table.get_item(Key={"bin_id": "__ROUTE__"})
        item = response.get("Item")
        return decimal_to_python(item) if item else None

    def put_reading(
        self,
        bin_id: str,
        timestamp_ms: int,
        fill_level: float,
        ttl_sec: int,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> Dict[str, Any]:
        """Write a single time-series reading to BinReadings with a 7-day TTL."""
        item = {
            "bin_id": bin_id,
            "timestamp": timestamp_ms,
            "fill_level": to_decimal(round(float(fill_level), 2)),
            "ttl": int(ttl_sec)
        }
        if latitude is not None and longitude is not None:
            item["latitude"] = to_decimal(latitude)
            item["longitude"] = to_decimal(longitude)

        self.bin_readings_table.put_item(Item=item)
        return decimal_to_python(item)

    def get_recent_readings(self, bin_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Query recent time-series readings for a bin, ordered chronologically."""
        response = self.bin_readings_table.query(
            KeyConditionExpression=Key("bin_id").eq(bin_id),
            ScanIndexForward=True,  # Chronological order
            Limit=limit
        )
        items = response.get("Items", [])
        return [decimal_to_python(item) for item in items]

    def batch_put_readings(self, readings: List[Dict[str, Any]]) -> None:
        """Batch write multiple readings to BinReadings."""
        with self.bin_readings_table.batch_writer() as batch:
            for reading in readings:
                item = {
                    "bin_id": reading["bin_id"],
                    "timestamp": reading["timestamp_ms"],
                    "fill_level": to_decimal(round(float(reading["fill_level"]), 2)),
                    "ttl": int(reading["ttl_sec"])
                }
                if "latitude" in reading and "longitude" in reading:
                    item["latitude"] = to_decimal(reading["latitude"])
                    item["longitude"] = to_decimal(reading["longitude"])
                batch.put_item(Item=item)
