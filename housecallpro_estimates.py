#!/usr/bin/env python3
"""
Housecall Pro Estimates MCP Server
Estimate CRUD operations.
"""

from typing import Optional, List, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Estimates")


@mcp.tool()
async def get_estimates(
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
    customer_id: Optional[str] = None,
    work_status: Optional[str] = None,
    employee_ids: Optional[str] = None,
    scheduled_start_min: Optional[str] = None,
    scheduled_start_max: Optional[str] = None,
    scheduled_end_min: Optional[str] = None,
    scheduled_end_max: Optional[str] = None,
    sort_direction: Optional[str] = "desc",
) -> Dict[str, Any]:
    """
    List estimates with optional filters.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 50, max 200)
        customer_id: Filter by customer UUID
        work_status: Comma-separated: unscheduled, scheduled, in_progress, completed, canceled
        employee_ids: Comma-separated employee UUIDs
        scheduled_start_min: Estimates starting on or after (ISO 8601)
        scheduled_start_max: Estimates starting on or before (ISO 8601)
        scheduled_end_min: Estimates ending on or after (ISO 8601)
        scheduled_end_max: Estimates ending on or before (ISO 8601)
        sort_direction: asc or desc (default: desc)
    """
    params: dict = {
        "page": page,
        "page_size": min(page_size, 200),
        "sort_direction": sort_direction,
        "customer_id": customer_id,
        "scheduled_start_min": scheduled_start_min,
        "scheduled_start_max": scheduled_start_max,
        "scheduled_end_min": scheduled_end_min,
        "scheduled_end_max": scheduled_end_max,
    }
    if work_status:
        params["work_status"] = [s.strip() for s in work_status.split(",") if s.strip()]
    if employee_ids:
        params["employee_ids"] = [s.strip() for s in employee_ids.split(",") if s.strip()]
    return await api_request("GET", "/estimates", params=params)


@mcp.tool()
async def get_estimate(estimate_id: str) -> Dict[str, Any]:
    """
    Get full details for a single estimate including options, line items, and customer info.

    Args:
        estimate_id: Estimate UUID
    """
    return await api_request("GET", f"/estimates/{estimate_id}")


@mcp.tool()
async def create_estimate(
    customer_id: str,
    employee_id: Optional[str] = None,
    line_items: Optional[List[Dict[str, Any]]] = None,
    notes: Optional[str] = None,
    work_status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new estimate.

    Args:
        customer_id: Customer UUID (required)
        employee_id: Assigned employee UUID
        line_items: List of line item objects (name, quantity, unit_price, kind)
        notes: Notes for the estimate
        work_status: unscheduled | scheduled | in_progress | completed | canceled
    """
    payload: dict = {"customer_id": customer_id}
    if employee_id:
        payload["employee_id"] = employee_id
    if line_items:
        payload["line_items"] = line_items
    if notes:
        payload["notes"] = notes
    if work_status:
        payload["work_status"] = work_status
    return await api_request("POST", "/estimates", json=payload)


@mcp.tool()
async def update_estimate(
    estimate_id: str,
    notes: Optional[str] = None,
    work_status: Optional[str] = None,
    line_items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Update an existing estimate.

    Args:
        estimate_id: Estimate UUID (required)
        notes: Updated notes
        work_status: Updated status
        line_items: Updated line items list
    """
    payload: dict = {}
    if notes is not None:
        payload["notes"] = notes
    if work_status is not None:
        payload["work_status"] = work_status
    if line_items is not None:
        payload["line_items"] = line_items
    return await api_request("PUT", f"/estimates/{estimate_id}", json=payload)


@mcp.tool()
async def delete_estimate(estimate_id: str) -> Dict[str, Any]:
    """
    Delete an estimate. Cannot be undone.

    Args:
        estimate_id: Estimate UUID
    """
    return await api_request("DELETE", f"/estimates/{estimate_id}")


if __name__ == "__main__":
    mcp.run()
