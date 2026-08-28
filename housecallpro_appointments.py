#!/usr/bin/env python3
"""
⚠ NOT WORKING — every endpoint in this file returns HTTP 404.

Verified against a live account on 2026-08-28. These paths are not in the
Housecall Pro public API (v1-4). Do not register this server in your Claude
Desktop config; nothing in it can succeed.

Use the main server instead: hcp_get_job_appointments, hcp_create_appointment,
hcp_update_appointment and hcp_delete_appointment all work, because the real
endpoints are job-scoped (/jobs/{job_id}/appointments), not top-level.

Original description:
Housecall Pro Appointments MCP Server
Standalone appointment CRUD (job-specific appointments are also in housecallpro_jobs.py).
"""

from typing import Optional, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Appointments")


@mcp.tool()
async def get_appointments(
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
    customer_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List appointments with optional filters.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 50, max 200)
        customer_id: Filter by customer UUID
        employee_id: Filter by employee UUID
        start_date: Filter appointments after this date (YYYY-MM-DD)
        end_date: Filter appointments before this date (YYYY-MM-DD)
        status: Filter by appointment status
    """
    params: dict = {
        "page": page,
        "page_size": min(page_size, 200),
        "customer_id": customer_id,
        "employee_id": employee_id,
        "start_date": start_date,
        "end_date": end_date,
        "status": status,
    }
    return await api_request("GET", "/appointments", params=params)


@mcp.tool()
async def get_appointment(appointment_id: str) -> Dict[str, Any]:
    """
    Get a single appointment by ID.

    Args:
        appointment_id: Appointment UUID
    """
    return await api_request("GET", f"/appointments/{appointment_id}")


@mcp.tool()
async def create_appointment(
    customer_id: str,
    start_time: str,
    end_time: str,
    employee_id: Optional[str] = None,
    service_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a standalone appointment.

    Args:
        customer_id: Customer UUID (required)
        start_time: Start time (ISO 8601)
        end_time: End time (ISO 8601)
        employee_id: Assigned employee UUID
        service_id: Service UUID
        notes: Appointment notes
    """
    payload: dict = {
        "customer_id": customer_id,
        "start_time": start_time,
        "end_time": end_time,
    }
    for field in ("employee_id", "service_id", "notes"):
        val = locals()[field]
        if val:
            payload[field] = val
    return await api_request("POST", "/appointments", json=payload)


@mcp.tool()
async def update_appointment(
    appointment_id: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    employee_id: Optional[str] = None,
    notes: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update an existing appointment.

    Args:
        appointment_id: Appointment UUID (required)
        start_time: New start time (ISO 8601)
        end_time: New end time (ISO 8601)
        employee_id: New assigned employee UUID
        notes: Updated notes
        status: Updated status
    """
    payload: dict = {}
    for field in ("start_time", "end_time", "employee_id", "notes", "status"):
        val = locals()[field]
        if val is not None:
            payload[field] = val
    return await api_request("PUT", f"/appointments/{appointment_id}", json=payload)


@mcp.tool()
async def delete_appointment(appointment_id: str) -> Dict[str, Any]:
    """
    Delete an appointment. Cannot be undone.

    Args:
        appointment_id: Appointment UUID
    """
    return await api_request("DELETE", f"/appointments/{appointment_id}")


if __name__ == "__main__":
    mcp.run()
