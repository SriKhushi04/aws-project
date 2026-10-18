"""Amazon S3 service for archiving raw ingestion batches."""
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any
import boto3
from lambdas.common.config import get_config

class S3Service:
    def __init__(self, client=None):
        self.config = get_config()
        self.client = client or boto3.client("s3", region_name=self.config["AWS_REGION"])
        self.bucket_name = self.config["S3_ARCHIVE_BUCKET"]

    def archive_batch(self, batch_payload: Dict[str, Any], prefix: str = "raw-readings") -> str:
        """
        Archive a batch of sensor readings to S3.
        Key structure: raw-readings/YYYY/MM/DD/batch-<timestamp>-<uuid>.json
        Returns the created S3 object key.
        """
        now = datetime.now(timezone.utc)
        date_prefix = now.strftime("%Y/%m/%d")
        timestamp_str = now.strftime("%Y%m%dT%H%M%SZ")
        unique_id = str(uuid.uuid4())[:8]

        s3_key = f"{prefix}/{date_prefix}/batch-{timestamp_str}-{unique_id}.json"

        archive_content = {
            "archived_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "batch_data": batch_payload
        }

        self.client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=json.dumps(archive_content, default=str),
            ContentType="application/json"
        )
        return s3_key

