#!/usr/bin/env python3
"""
Housecall Pro Schedule MCP Server
Schedule / dispatch board access — routes and routing.
"""

from typing import Optional, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Schedule")


@mcp.tool()
async def get_routes(
    date: Optional[str] = None,
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
) -> Dict[str, Any]:
    """
    Get dispatch routes for a specific date.

    NOTE: Requires the HCP Routes feature to be configured in the dispatch board.
    Returns empty if your team does not use named routes.
    Use hcp_get_week_schedule (in housecallpro_LHSTL) for schedule analysis.

    Args:
        date: Date to fetch routes for (YYYY-MM-DD, defaults to today)
        page: Page number (default 1)
        page_size: Routes per page (default 50)
    """
    params: dict = {"page": page, "per_page": page_size}
    if date:
        params["date"] = date
    return await api_request("GET", "/routes", params=params)


@mcp.tool()
async def get_schedule(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    employee_id: Optional[str] = None,
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
) -> Dict[str, Any]:
    """
    Get schedule entries for a date range.

    Args:
        start_date: Start of date range (YYYY-MM-DD)
        end_date: End of date range (YYYY-MM-DD)
        employee_id: Filter by employee UUID
        page: Page number (default 1)
        page_size: Results per page (default 50)
    """
    params: dict = {
        "page": page,
        "page_size": page_size,
        "start_date": start_date,
        "end_date": end_date,
        "employee_id": employee_id,
    }
    return await api_request("GET", "/schedule", params=params)


if __name__ == "__main__":
    mcp.run()
