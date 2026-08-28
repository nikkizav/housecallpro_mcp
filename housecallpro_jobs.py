#!/usr/bin/env python3
"""
Housecall Pro Jobs MCP Server
Comprehensive job management: CRUD, line items, notes, tags, attachments, scheduling.
"""

import json
from typing import Optional, List, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Jobs")


@mcp.tool()
async def get_jobs(
    customer_id: Optional[str] = None,
    work_status: Optional[str] = None,
    employee_ids: Optional[str] = None,
    scheduled_start_min: Optional[str] = None,
    scheduled_start_max: Optional[str] = None,
    scheduled_end_min: Optional[str] = None,
    scheduled_end_max: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    updated_after: Optional[str] = None,
    updated_before: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_direction: Optional[str] = "desc",
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
    expand: Optional[str] = None,
) -> dict:
    """
    List jobs with optional filters.

    Args:
        customer_id: Filter by customer UUID
        work_status: Comma-separated statuses: unscheduled, scheduled, in_progress, completed, canceled
        employee_ids: Comma-separated employee UUIDs
        scheduled_start_min: Jobs starting on or after (ISO 8601 e.g. 2026-04-21T00:00:00)
        scheduled_start_max: Jobs starting on or before (ISO 8601)
        scheduled_end_min: Jobs ending on or after (ISO 8601)
        scheduled_end_max: Jobs ending on or before (ISO 8601)
        created_after: Return jobs created after this datetime (ISO 8601)
        created_before: Return jobs created before this datetime (ISO 8601)
        updated_after: Return jobs updated after this datetime (ISO 8601)
        updated_before: Return jobs updated before this datetime (ISO 8601)
        sort_by: created_at | updated_at | invoice_number | work_status (default: created_at)
        sort_direction: asc or desc (default: desc)
        page: Page number (default 1)
        page_size: Results per page (default 50, max 100)
        expand: Comma-separated expansions: appointments, attachments
    """
    params: dict = {
        "page": page,
        "page_size": page_size,
        "sort_by": sort_by,
        "sort_direction": sort_direction,
        "customer_id": customer_id,
        "scheduled_start_min": scheduled_start_min,
        "scheduled_start_max": scheduled_start_max,
        "scheduled_end_min": scheduled_end_min,
        "scheduled_end_max": scheduled_end_max,
        "created_after": created_after,
        "created_before": created_before,
        "updated_after": updated_after,
        "updated_before": updated_before,
    }
    if work_status:
        params["work_status"] = [s.strip() for s in work_status.split(",") if s.strip()]
    if employee_ids:
        params["employee_ids"] = [s.strip() for s in employee_ids.split(",") if s.strip()]
    if expand:
        params["expand"] = [s.strip() for s in expand.split(",") if s.strip()]
    return await api_request("GET", "/jobs", params=params)


@mcp.tool()
async def get_job(job_id: str, expand: Optional[str] = None) -> dict:
    """
    Get full details for a single job.

    Args:
        job_id: Job UUID
        expand: Comma-separated expansions: appointments, attachments
    """
    params: dict = {}
    if expand:
        params["expand"] = [s.strip() for s in expand.split(",") if s.strip()]
    return await api_request("GET", f"/jobs/{job_id}", params=params)


@mcp.tool()
async def create_job(
    customer_id: str,
    work_status: str = "needs_scheduling",
    description: Optional[str] = None,
    lead_source: Optional[str] = None,
    note_to_customer: Optional[str] = None,
    scheduled_start: Optional[str] = None,
    scheduled_end: Optional[str] = None,
    employee_ids: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> dict:
    """
    Create a new job.

    Args:
        customer_id: Customer UUID (required)
        work_status: needs_scheduling | scheduled | in_progress | completed | canceled
        description: Job description / scope of work
        lead_source: Lead source name
        note_to_customer: Note visible on the customer portal
        scheduled_start: Primary scheduled start (ISO 8601)
        scheduled_end: Primary scheduled end (ISO 8601)
        employee_ids: List of employee UUIDs to assign
        tags: List of tag names to apply
    """
    payload: dict = {"customer_id": customer_id, "work_status": work_status}
    for field in ("description", "lead_source", "note_to_customer", "scheduled_start",
                  "scheduled_end", "employee_ids", "tags"):
        val = locals()[field]
        if val is not None:
            payload[field] = val
    return await api_request("POST", "/jobs", json=payload)


# ── Job Line Items ─────────────────────────────────────────────────────────────

@mcp.tool()
async def get_job_line_items(job_id: str) -> dict:
    """
    Get all line items for a job (services, materials, discounts, gratuity).

    Args:
        job_id: Job UUID
    """
    return await api_request("GET", f"/jobs/{job_id}/line_items")


@mcp.tool()
async def add_job_line_item(
    job_id: str,
    name: str,
    quantity: float,
    unit_price: int,
    kind: Optional[str] = "labor",
    unit_cost: Optional[int] = None,
    description: Optional[str] = None,
) -> dict:
    """
    Add a line item to a job.

    Args:
        job_id: Job UUID
        name: Line item name
        quantity: Quantity (for labor = projected hours)
        unit_price: Price per unit in cents (e.g. 10000 = $100.00)
        kind: labor | materials | fixed_discount | percent_discount | fixed_gratuity
        unit_cost: Cost per unit in cents (for margin tracking)
        description: Additional description
    """
    payload: dict = {"name": name, "quantity": quantity, "unit_price": unit_price, "kind": kind}
    if unit_cost is not None:
        payload["unit_cost"] = unit_cost
    if description:
        payload["description"] = description
    return await api_request("POST", f"/jobs/{job_id}/line_items", json=payload)


@mcp.tool()
async def update_job_line_item(
    job_id: str,
    line_item_id: str,
    name: Optional[str] = None,
    quantity: Optional[float] = None,
    unit_price: Optional[int] = None,
    unit_cost: Optional[int] = None,
    description: Optional[str] = None,
) -> dict:
    """
    Update a single line item on a job.

    Args:
        job_id: Job UUID
        line_item_id: Line item UUID
        name: New name
        quantity: New quantity
        unit_price: New unit price in cents
        unit_cost: New unit cost in cents
        description: New description
    """
    payload: dict = {}
    for field in ("name", "quantity", "unit_price", "unit_cost", "description"):
        val = locals()[field]
        if val is not None:
            payload[field] = val
    return await api_request("PUT", f"/jobs/{job_id}/line_items/{line_item_id}", json=payload)


@mcp.tool()
async def delete_job_line_item(job_id: str, line_item_id: str) -> dict:
    """
    Delete a line item from a job.

    Args:
        job_id: Job UUID
        line_item_id: Line item UUID
    """
    return await api_request("DELETE", f"/jobs/{job_id}/line_items/{line_item_id}")


# ── Job Notes ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def add_job_note(job_id: str, content: str) -> dict:
    """
    Add a note to a job. Visible to office and field techs.

    Args:
        job_id: Job UUID
        content: Note text
    """
    return await api_request("POST", f"/jobs/{job_id}/notes", json={"content": content})


@mcp.tool()
async def delete_job_note(job_id: str, note_id: str) -> dict:
    """
    Delete a note from a job.

    Args:
        job_id: Job UUID
        note_id: Note UUID
    """
    return await api_request("DELETE", f"/jobs/{job_id}/notes/{note_id}")


# ── Job Tags ───────────────────────────────────────────────────────────────────

@mcp.tool()
async def add_job_tag(job_id: str, tag_id: str) -> dict:
    """
    Add a tag to a job.

    Args:
        job_id: Job UUID
        tag_id: Tag UUID (use get_tags to find IDs)
    """
    return await api_request("POST", f"/jobs/{job_id}/tags", json={"tag_id": tag_id})


@mcp.tool()
async def remove_job_tag(job_id: str, tag_id: str) -> dict:
    """
    Remove a tag from a job.

    Args:
        job_id: Job UUID
        tag_id: Tag UUID
    """
    return await api_request("DELETE", f"/jobs/{job_id}/tags/{tag_id}")


# ── Job Input Materials ────────────────────────────────────────────────────────

@mcp.tool()
async def get_job_input_materials(job_id: str) -> dict:
    """
    Get materials logged as job inputs (separate from invoice line items).

    Args:
        job_id: Job UUID
    """
    return await api_request("GET", f"/jobs/{job_id}/job_input_materials")


@mcp.tool()
async def bulk_update_job_input_materials(
    job_id: str,
    input_materials: List[Dict[str, Any]],
) -> dict:
    """
    Bulk update input materials for a job.

    Args:
        job_id: Job UUID
        input_materials: List of material objects with name, quantity, unit_cost, etc.
    """
    return await api_request(
        # /bulk_update, not the bare path — the bare PUT route does not exist
        # (returns Housecall Pro's HTML 404 page). Verified 2026-08-28.
        "PUT", f"/jobs/{job_id}/job_input_materials/bulk_update",
        json={"job_input_materials": input_materials},
    )


# ── Job Appointments ───────────────────────────────────────────────────────────

@mcp.tool()
async def get_job_appointments(job_id: str) -> dict:
    """
    Get all appointments for a job.

    Args:
        job_id: Job UUID
    """
    return await api_request("GET", f"/jobs/{job_id}/appointments")


@mcp.tool()
async def create_job_appointment(
    job_id: str,
    start_time: str,
    end_time: str,
    arrival_window_minutes: Optional[int] = 0,
    dispatched_employees_ids: Optional[List[str]] = None,
) -> dict:
    """
    Add a new appointment to a job.

    Args:
        job_id: Job UUID
        start_time: Appointment start (ISO 8601 e.g. 2026-04-28T07:30:00)
        end_time: Appointment end (ISO 8601)
        arrival_window_minutes: Arrival window in minutes (default 0)
        dispatched_employees_ids: Employee UUIDs to dispatch
    """
    payload: dict = {
        "start_time": start_time,
        "end_time": end_time,
        "arrival_window_minutes": arrival_window_minutes,
    }
    if dispatched_employees_ids:
        payload["dispatched_employees_ids"] = dispatched_employees_ids
    return await api_request("POST", f"/jobs/{job_id}/appointments", json=payload)


@mcp.tool()
async def update_job_appointment(
    job_id: str,
    appointment_id: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    arrival_window_minutes: Optional[int] = None,
    dispatched_employees_ids: Optional[List[str]] = None,
) -> dict:
    """
    Update an existing appointment on a job.

    Args:
        job_id: Job UUID
        appointment_id: Appointment UUID
        start_time: New start time (ISO 8601)
        end_time: New end time (ISO 8601)
        arrival_window_minutes: New arrival window in minutes
        dispatched_employees_ids: New list of dispatched employee UUIDs (replaces existing)
    """
    payload: dict = {}
    for field in ("start_time", "end_time", "arrival_window_minutes", "dispatched_employees_ids"):
        val = locals()[field]
        if val is not None:
            payload[field] = val
    return await api_request("PUT", f"/jobs/{job_id}/appointments/{appointment_id}", json=payload)


@mcp.tool()
async def delete_job_appointment(job_id: str, appointment_id: str) -> dict:
    """
    Delete an appointment from a job. Cannot be undone.

    Args:
        job_id: Job UUID
        appointment_id: Appointment UUID
    """
    return await api_request("DELETE", f"/jobs/{job_id}/appointments/{appointment_id}")


# ── Job Links ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def create_job_link(
    job_id: str,
    url: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    """
    Create a link associated with a job.

    Args:
        job_id: Job UUID
        url: URL of the link
        name: Display name / title for the link
        description: Link description
    """
    payload: dict = {"url": url}
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description
    return await api_request("POST", f"/jobs/{job_id}/links", json=payload)


if __name__ == "__main__":
    mcp.run()
