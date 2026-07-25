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


@mcp.tool()
async def create_event(
    name: str,
    start_time: str,
    end_time: str,
    employee_ids: Optional[List[str]] = None,
    all_day: Optional[bool] = False,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a calendar event.

    Args:
        name: Event name / title (required)
        start_time: Event start (ISO 8601)
        end_time: Event end (ISO 8601)
        employee_ids: List of employee UUIDs to assign
        all_day: True for an all-day event (default False)
        notes: Event notes
    """
    payload: dict = {
        "name": name,
        "start_time": start_time,
        "end_time": end_time,
        "all_day": all_day,
    }
    if employee_ids:
        payload["employee_ids"] = employee_ids
    if notes:
        payload["notes"] = notes
    return await api_request("POST", "/events", json=payload)


@mcp.tool()
async def update_event(
    event_id: str,
    name: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    employee_ids: Optional[List[str]] = None,
    all_day: Optional[bool] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update a calendar event.

    Args:
        event_id: Event UUID (required)
        name: New event name
        start_time: New start time (ISO 8601)
        end_time: New end time (ISO 8601)
        employee_ids: Updated assigned employee list
        all_day: All-day flag
        notes: Updated notes
    """
    payload: dict = {}
    for field in ("name", "start_time", "end_time", "employee_ids", "notes"):
        val = locals()[field]
        if val is not None:
            payload[field] = val
    if all_day is not None:
        payload["all_day"] = all_day
    return await api_request("PUT", f"/events/{event_id}", json=payload)


@mcp.tool()
async def delete_event(event_id: str) -> Dict[str, Any]:
    """
    Delete a calendar event.

    Args:
        event_id: Event UUID
    """
    return await api_request("DELETE", f"/events/{event_id}")


if __name__ == "__main__":
    mcp.run()
