#!/usr/bin/env python3
"""
⚠ NOT WORKING — every endpoint in this file returns HTTP 404.

Verified against a live account on 2026-08-28. These paths are not in the
Housecall Pro public API (v1-4). Do not register this server in your Claude
Desktop config; nothing in it can succeed.

The spec has POST and DELETE /webhooks/subscription only - there is no way to
list or update webhooks, and the /webhooks paths used here do not exist.

Original description:
Housecall Pro Webhooks MCP Server
Webhook subscription management.
"""

from typing import Optional, List, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Webhooks")


@mcp.tool()
async def get_webhooks(
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
) -> Dict[str, Any]:
    """
    List all configured webhook subscriptions.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 50)
    """
    return await api_request("GET", "/webhooks", params={"page": page, "page_size": page_size})


@mcp.tool()
async def get_webhook(webhook_id: str) -> Dict[str, Any]:
    """
    Get a specific webhook subscription by ID.

    Args:
        webhook_id: Webhook UUID
    """
    return await api_request("GET", f"/webhooks/{webhook_id}")


@mcp.tool()
async def create_webhook(
    url: str,
    events: List[str],
    is_active: Optional[bool] = True,
) -> Dict[str, Any]:
    """
    Create a new webhook subscription.

    Args:
        url: The endpoint URL to receive webhook payloads (required)
        events: List of event types to subscribe to, e.g.
                ["job.created", "job.completed", "invoice.paid"] (required)
        is_active: Whether this webhook is active (default True)
    """
    payload: dict = {"url": url, "events": events, "is_active": is_active}
    return await api_request("POST", "/webhooks", json=payload)


@mcp.tool()
async def update_webhook(
    webhook_id: str,
    url: Optional[str] = None,
    events: Optional[List[str]] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Update an existing webhook subscription.

    Args:
        webhook_id: Webhook UUID (required)
        url: New endpoint URL
        events: New list of event types
        is_active: New active status
    """
    payload: dict = {}
    if url is not None:
        payload["url"] = url
    if events is not None:
        payload["events"] = events
    if is_active is not None:
        payload["is_active"] = is_active
    return await api_request("PUT", f"/webhooks/{webhook_id}", json=payload)


@mcp.tool()
async def delete_webhook(webhook_id: str) -> Dict[str, Any]:
    """
    Delete a webhook subscription.

    Args:
        webhook_id: Webhook UUID
    """
    return await api_request("DELETE", f"/webhooks/{webhook_id}")


if __name__ == "__main__":
    mcp.run()
