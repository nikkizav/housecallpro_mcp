#!/usr/bin/env python3
"""
Housecall Pro Job Types MCP Server
Job type (service category) management.
"""

from typing import Optional, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Job Types")


@mcp.tool()
async def get_job_types(
    page: Optional[int] = 1,
    page_size: Optional[int] = 100,
) -> Dict[str, Any]:
    """
    List all configured job types / service categories.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 100)
    """
    return await api_request("GET", "/job_types", params={"page": page, "page_size": page_size})


@mcp.tool()
async def get_job_type(job_type_id: str) -> Dict[str, Any]:
    """
    Get a specific job type by ID.

    Args:
        job_type_id: Job type UUID
    """
    return await api_request("GET", f"/job_types/{job_type_id}")


@mcp.tool()
async def create_job_type(
    name: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new job type.

    Args:
        name: Job type name (required)
        description: Description of this job type
    """
    payload: dict = {"name": name}
    if description:
        payload["description"] = description
    return await api_request("POST", "/job_types", json=payload)


@mcp.tool()
async def update_job_type(
    job_type_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update a job type.

    Args:
        job_type_id: Job type UUID (required)
        name: New name
        description: New description
    """
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    return await api_request("PUT", f"/job_types/{job_type_id}", json=payload)


if __name__ == "__main__":
    mcp.run()
