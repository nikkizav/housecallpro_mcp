#!/usr/bin/env python3
"""
Housecall Pro Leads MCP Server
Lead management: list, get, create, update, convert.
"""

from typing import Optional, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Leads")


@mcp.tool()
async def get_leads(
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
    status: Optional[str] = None,
    source: Optional[str] = None,
    assigned_employee_id: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    sort_direction: Optional[str] = "desc",
) -> Dict[str, Any]:
    """
    List leads with optional filters.

    Each lead includes:
        total_amount: Lead value in CENTS (divide by 100 to display as dollars)
        conversions:  List of {type, id} for jobs/estimates this lead became.
                      Empty until the lead is converted. type is "Job" or "Estimate".
        job_fields:   {job_type_uuid, business_unit_uuid} assigned to the lead
        pipeline_status: Current pipeline stage name (e.g. "New Lead")

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 50, max 200)
        status: Filter by lead status
        source: Filter by lead source
        assigned_employee_id: Filter by assigned employee UUID
        created_after: Return leads created after this datetime (ISO 8601)
        created_before: Return leads created before this datetime (ISO 8601)
        sort_direction: asc or desc (default: desc)
    """
    params: dict = {
        "page": page,
        "page_size": min(page_size, 200),
        "sort_direction": sort_direction,
        "status": status,
        "source": source,
        "assigned_employee_id": assigned_employee_id,
        "created_after": created_after,
        "created_before": created_before,
    }
    return await api_request("GET", "/leads", params=params)


@mcp.tool()
async def get_lead(lead_id: str) -> Dict[str, Any]:
    """
    Get a specific lead by ID.

    Includes total_amount (in CENTS), conversions (list of {type, id} for the
    jobs/estimates this lead became — empty until converted), and job_fields
    ({job_type_uuid, business_unit_uuid}).

    Args:
        lead_id: Lead UUID
    """
    return await api_request("GET", f"/leads/{lead_id}")


@mcp.tool()
async def create_lead(
    first_name: str,
    last_name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    source: Optional[str] = None,
    notes: Optional[str] = None,
    assigned_employee_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new lead.

    Args:
        first_name: Lead first name (required)
        last_name: Lead last name (required)
        email: Lead email
        phone: Lead phone number
        source: How this lead was acquired
        notes: Notes about the lead
        assigned_employee_id: Employee UUID to assign this lead to
    """
    payload: dict = {"first_name": first_name, "last_name": last_name}
    for field in ("email", "phone", "source", "notes", "assigned_employee_id"):
        val = locals()[field]
        if val:
            payload[field] = val
    return await api_request("POST", "/leads", json=payload)


@mcp.tool()
async def update_lead(
    lead_id: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    source: Optional[str] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    assigned_employee_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update an existing lead.

    Args:
        lead_id: Lead UUID (required)
        first_name: New first name
        last_name: New last name
        email: New email
        phone: New phone
        source: New source
        status: New status
        notes: Updated notes
        assigned_employee_id: New assigned employee UUID
    """
    payload: dict = {}
    for field in ("first_name", "last_name", "email", "phone", "source", "status",
                  "notes", "assigned_employee_id"):
        val = locals()[field]
        if val is not None:
            payload[field] = val
    return await api_request("PUT", f"/leads/{lead_id}", json=payload)


@mcp.tool()
async def convert_lead_to_customer(lead_id: str) -> Dict[str, Any]:
    """
    Convert a lead to a customer.

    Args:
        lead_id: Lead UUID
    """
    return await api_request("POST", f"/leads/{lead_id}/convert")


if __name__ == "__main__":
    mcp.run()
