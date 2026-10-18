"""Amazon SNS service for publishing threshold alert notifications."""
import json
from typing import Optional, Dict, Any
import boto3
from lambdas.common.config import get_config

class SNSService:
    def __init__(self, client=None):
        self.config = get_config()
        self.client = client or boto3.client("sns", region_name=self.config["AWS_REGION"])
        self.topic_arn = self.config["SNS_ALERT_TOPIC_ARN"]

    def publish_threshold_alert(
        self,
        bin_id: str,
        fill_level: float,
        timestamp_iso: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> Optional[str]:
        """
        Publish a high-fill threshold alert to the configured SNS topic.
        Returns the SNS MessageId if sent, or None if topic ARN is not set.
        """
        if not self.topic_arn:
            return None

        subject = f"🚨 URGENT: Waste Bin {bin_id} Exceeded 85% Capacity"
        message_lines = [
            f"Smart Waste Monitoring System Alert",
            f"----------------------------------------",
            f"Bin ID:          {bin_id}",
            f"Current Fill:    {fill_level:.1f}% (Threshold: 85.0%)",
            f"Recorded Time:   {timestamp_iso}",
        ]
        if latitude is not None and longitude is not None:
            message_lines.append(f"Coordinates:     {latitude:.5f}, {longitude:.5f}")
        message_lines.extend([
            f"Status:          Critical - Overflow Imminent",
            f"Action Required: Dispatch collection vehicle to service bin.",
            f"----------------------------------------",
            f"This is an automated alert from AWS Smart Waste Management System."
        ])

        message = "\n".join(message_lines)

        response = self.client.publish(
            TopicArn=self.topic_arn,
            Subject=subject,
            Message=message,
            MessageAttributes={
                "bin_id": {"DataType": "String", "StringValue": bin_id},
                "fill_level": {"DataType": "Number", "StringValue": str(round(fill_level, 2))},
                "alert_type": {"DataType": "String", "StringValue": "THRESHOLD_OVERFLOW"}
            }
        )
        return response.get("MessageId")

