#!/usr/bin/env python3
"""
Housecall Pro Tags MCP Server
Tag library management: list, create, update.
"""

from typing import Optional, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Tags")


@mcp.tool()
async def get_tags(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    name: Optional[str] = None,
    tag_type: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    List tags with optional filtering.

    Args:
        page: Page number
        page_size: Results per page
        name: Filter by tag name
        tag_type: Filter by tag type (customer, job)
        is_active: Filter by active status
    """
    params: dict = {
        "page": page,
        "page_size": page_size,
        "name": name,
        "tag_type": tag_type,
    }
    if is_active is not None:
        params["is_active"] = is_active
    return await api_request("GET", "/tags", params=params)


@mcp.tool()
async def create_tag(
    name: str,
    tag_type: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Create a new tag in Housecall Pro.

    Args:
        name: Tag name (e.g. SCH-FOLLOWUP, CREW-2L1A, TOOL-SCAFF)
        tag_type: Tag type: customer or job
        is_active: Active status (default True)
    """
    payload: dict = {"name": name}
    if tag_type:
        payload["tag_type"] = tag_type
    if is_active is not None:
        payload["is_active"] = is_active
    return await api_request("POST", "/tags", json=payload)


@mcp.tool()
async def update_tag(
    tag_id: str,
    name: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Update an existing tag.

    Args:
        tag_id: Tag UUID (required)
        name: New tag name
        is_active: New active status
    """
    payload: dict = {}
    if name:
        payload["name"] = name
    if is_active is not None:
        payload["is_active"] = is_active
    return await api_request("PUT", f"/tags/{tag_id}", json=payload)


if __name__ == "__main__":
    mcp.run()
