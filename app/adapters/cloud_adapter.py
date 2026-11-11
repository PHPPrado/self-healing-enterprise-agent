"""Pluggable cloud adapter.

This is one of the two files a developer edits to wire up their cloud backend.
By default a fully working MockCloudAdapter is provided so the repo runs
out-of-the-box. Commented snippets for AWS (Boto3) and OCI are included.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from app.adapters.base import BaseCloudAdapter
from app.config import settings
from app.tools.enterprise_tools import run_tool

logger = logging.getLogger(__name__)


class MockCloudAdapter(BaseCloudAdapter):
    """In-memory mock adapter that simulates enterprise operations."""

    provider_name = "MOCK"

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def execute(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0)  # keep async contract
        logger.info("mock_adapter.execute", extra={"tool_name": tool_name})
        if tool_name == "create_purchase_order":
            record_id = str(uuid.uuid4())
            self._store[record_id] = payload
            business = run_tool(tool_name, payload)
            return {
                "status": "success",
                "provider": "MOCK",
                "record_id": record_id,
                "message": f"Purchase order {payload.get('order_id')} dispatched to mock ERP",
                "stored_count": len(self._store),
                "business_result": business,
            }
        if tool_name == "update_inventory":
            business = run_tool(tool_name, payload)
            return {
                "status": "success",
                "provider": "MOCK",
                "warehouse_id": payload.get("warehouse_id"),
                "sku": payload.get("sku"),
                "new_quantity_delta": payload.get("delta"),
                "message": "Inventory adjustment recorded in mock warehouse",
                "business_result": business,
            }
        raise ValueError(f"Unsupported tool for MockCloudAdapter: {tool_name}")

    async def health_check(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# AWS (Boto3) template — uncomment and implement to use AWS.
# ---------------------------------------------------------------------------
# import boto3
#
# class AWSCloudAdapter(BaseCloudAdapter):
#     provider_name = "AWS"
#
#     def __init__(self) -> None:
#         self.sqs = boto3.client("sqs")
#         self.s3 = boto3.client("s3")
#         self.queue_url = "https://sqs.<region>.amazonaws.com/<acct>/<queue>"
#
#     async def execute(self, tool_name, payload):
#         if tool_name == "create_purchase_order":
#             # Example: publish to SQS for downstream ERP
#             self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=json.dumps(payload))
#             return {"status": "success", "provider": "AWS", "message": "Published to SQS"}
#         raise ValueError(f"Unsupported tool: {tool_name}")
#
#     async def health_check(self):
#         try:
#             self.sqs.get_queue_attributes(QueueUrl=self.queue_url, AttributeNames=["ApproximateNumberOfMessages"])
#             return True
#         except Exception:
#             return False


# ---------------------------------------------------------------------------
# OCI (Oracle Cloud) template — uncomment and implement to use OCI.
# ---------------------------------------------------------------------------
# import oci
#
# class OCICloudAdapter(BaseCloudAdapter):
#     provider_name = "OCI"
#
#     def __init__(self):
#         config = oci.config.from_file()
#         self.client = oci.queue.QueueClient(config)
#
#     async def execute(self, tool_name, payload):
#         ...
#
#     async def health_check(self):
#         ...


# ---------------------------------------------------------------------------
# GCP / AZURE templates follow the same pattern.
# ---------------------------------------------------------------------------


def get_cloud_adapter() -> BaseCloudAdapter:
    """Factory returning the adapter selected by configuration."""
    provider = settings.cloud_provider.value.upper()
    if provider == "MOCK":
        return MockCloudAdapter()
    if provider == "AWS":
        # from app.adapters.cloud_adapter import AWSCloudAdapter
        # return AWSCloudAdapter()
        raise NotImplementedError("AWS adapter not implemented. See template above.")
    if provider == "OCI":
        raise NotImplementedError("OCI adapter not implemented. See template above.")
    if provider == "GCP":
        raise NotImplementedError("GCP adapter not implemented. See template above.")
    if provider == "AZURE":
        raise NotImplementedError("Azure adapter not implemented. See template above.")
    raise ValueError(f"Unknown cloud provider: {provider}")
