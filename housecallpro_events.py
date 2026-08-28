#!/usr/bin/env python3
"""
Housecall Pro Events MCP Server
Calendar events (time off, meetings, internal schedule blocks) — not job appointments.
"""

from typing import Optional, List, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Events")


@mcp.tool()
async def get_events(
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    employee_id: Optional[str] = None,
    sort_direction: Optional[str] = "asc",
) -> Dict[str, Any]:
    """
    List non-job calendar events (time off, meetings, schedule blocks).

    Important for full schedule visibility during pre-week planning.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 50)
        start_date: Filter events starting after this date (YYYY-MM-DD)
        end_date: Filter events starting before this date (YYYY-MM-DD)
        employee_id: Filter by assigned employee UUID
        sort_direction: asc or desc (default: asc)
    """
    params: dict = {
        "page": page,
        "page_size": page_size,
        "start_date": start_date,
        "end_date": end_date,
        "employee_id": employee_id,
        "sort_direction": sort_direction,
    }
    return await api_request("GET", "/events", params=params)


@mcp.tool()
async def get_event(event_id: str) -> Dict[str, Any]:
    """
    Get a single calendar event by ID.

    Args:
        event_id: Event UUID
    """
    return await api_request("GET", f"/events/{event_id}")


# Removed create_event, update_event, delete_event: the underlying endpoint(s) do not exist.
# A request to them returns Housecall Pro's HTML 404 page, meaning the route
# itself is absent (a missing *record* returns a JSON error instead).
# Verified against a live account 2026-08-28.

if __name__ == "__main__":
    mcp.run()
