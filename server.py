#!/usr/bin/env python3
"""
Housecall Pro MCP Server
Connects Claude Desktop to the Housecall Pro API.
"""

import os
import re
import json
import asyncio
from typing import Any
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ── Configuration ──────────────────────────────────────────────────────────────

API_KEY = os.environ.get("HCP_API_KEY", "")
BASE_URL = "https://api.housecallpro.com"

if not API_KEY:
    raise RuntimeError(
        "HCP_API_KEY environment variable is not set. "
        "Add it to your Claude Desktop MCP config (see README)."
    )

# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Token {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE_URL, headers=_headers(), timeout=30.0)


def _fmt(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def _dollars(cents: int | None) -> str:
    if cents is None:
        return "$0.00"
    return f"${cents / 100:,.2f}"


def _as_int(val: Any, default: int) -> int:
    """Coerce a value to int — handles both numeric and string inputs."""
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _as_list(val: Any) -> list[str] | None:
    """Coerce a value to list — handles arrays, comma-separated strings, or None."""
    if val is None:
        return None
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    s = str(val).strip()
    if not s:
        return None
    return [x.strip() for x in s.split(",") if x.strip()]


def _parse_tags(tags: list[str]) -> dict[str, list[str]]:
    """Group job tags by prefix category."""
    categories: dict[str, list[str]] = {
        "crew": [], "job": [], "scheduling": [], "materials": [], "tools": [], "other": []
    }
    for tag in tags:
        t = tag.upper()
        if t.startswith("CREW-"):
            categories["crew"].append(tag)
        elif t.startswith("JOB-"):
            categories["job"].append(tag)
        elif t.startswith("SCH-"):
            categories["scheduling"].append(tag)
        elif t.startswith("MAT-"):
            categories["materials"].append(tag)
        elif t.startswith("TOOL-"):
            categories["tools"].append(tag)
        else:
            categories["other"].append(tag)
    return categories


def _crew_summary(crew_tags: list[str]) -> str:
    """Parse a CREW-* tag into a human-readable label."""
    if not crew_tags:
        return "No crew tag"
    tag = crew_tags[0].upper()
    if tag == "CREW-TBD":
        return "TBD"
    m = re.match(r"CREW-(\d+)L(?:(\d+)A)?", tag)
    if m:
        leads = int(m.group(1))
        apprentices = int(m.group(2)) if m.group(2) else 0
        parts = [f"{leads} lead{'s' if leads > 1 else ''}"]
        if apprentices:
            parts.append(f"{apprentices} apprentice{'s' if apprentices > 1 else ''}")
        return " + ".join(parts)
    return crew_tags[0]


async def _get(client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> Any:
    clean = {k: v for k, v in params.items() if v is not None}
    resp = await client.get(path, params=clean)
    resp.raise_for_status()
    return resp.json()


def _error(msg: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=f"Error: {msg}")]


# ── MCP Server ─────────────────────────────────────────────────────────────────

app = Server("housecallpro")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [

        # ── Customers ────────────────────────────────────────────────────────

        types.Tool(
            name="hcp_list_customers",
            description=(
                "Search or list customers. Supports searching by name, email, phone, or address. "
                "Returns customer details including lead source."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "Search query (name, email, phone, address)"},
                    "page": {"description": "Page number (default 1)"},
                    "page_size": {"description": "Results per page, max 100 (default 25)"},
                    "sort_by": {"type": "string", "default": "created_at"},
                    "sort_direction": {"type": "string", "enum": ["asc", "desc"], "default": "desc"},
                },
                "required": [],
            },
        ),

        types.Tool(
            name="hcp_get_customer",
            description="Get full details for a single customer including lead source and all addresses.",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Customer ID"},
                },
                "required": ["customer_id"],
            },
        ),

        types.Tool(
            name="hcp_create_customer",
            description="Create a new customer in Housecall Pro.",
            inputSchema={
                "type": "object",
                "properties": {
                    "first_name": {"type": "string"},
                    "last_name": {"type": "string"},
                    "email": {"type": "string"},
                    "mobile_number": {"type": "string", "description": "Digits only, e.g. 5551234567"},
                    "home_number": {"type": "string"},
                    "work_number": {"type": "string"},
                    "company": {"type": "string"},
                    "notifications_enabled": {"type": "boolean", "default": True},
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string", "description": "2-letter state code"},
                    "zip": {"type": "string"},
                },
                "required": ["first_name", "last_name"],
            },
        ),

        # ── Jobs ─────────────────────────────────────────────────────────────

        types.Tool(
            name="hcp_list_jobs",
            description=(
                "List jobs with optional filters. Use for pre-week scheduling review and post-week analysis. "
                "Dates are ISO 8601 datetimes (e.g. 2025-04-21T00:00:00). "
                "work_status: comma-separated from unscheduled, scheduled, in_progress, completed, canceled. "
                "Returns financials (total_amount, outstanding_balance) and full tag breakdown "
                "(CREW, SCH, MAT, TOOL tags parsed automatically). "
                "Use expand=appointments to include appointment windows."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "scheduled_start_min": {
                        "type": "string",
                        "description": "Jobs starting on or after this datetime (ISO 8601)",
                    },
                    "scheduled_start_max": {
                        "type": "string",
                        "description": "Jobs starting on or before this datetime (ISO 8601)",
                    },
                    "scheduled_end_min": {"type": "string"},
                    "scheduled_end_max": {"type": "string"},
                    "work_status": {
                        "description": "Comma-separated statuses: unscheduled, scheduled, in_progress, completed, canceled",
                    },
                    "employee_ids": {
                        "description": "Comma-separated employee IDs",
                    },
                    "customer_id": {"type": "string"},
                    "sort_by": {
                        "type": "string",
                        "enum": ["created_at", "updated_at", "invoice_number", "id", "description", "work_status"],
                        "default": "created_at",
                    },
                    "sort_direction": {"type": "string", "enum": ["asc", "desc"], "default": "asc"},
                    "page": {"description": "Page number (default 1)"},
                    "page_size": {"description": "Results per page, max 100 (default 50)"},
                    "expand": {
                        "description": "Comma-separated expansions: appointments, attachments",
                    },
                },
                "required": [],
            },
        ),

        types.Tool(
            name="hcp_get_job",
            description=(
                "Get full details for a single job: schedule, assigned employees, financial totals "
                "(total_amount, outstanding_balance, subtotal), tags parsed by category, "
                "work timestamps (started_at, completed_at), lead source, and notes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "expand": {
                        "description": "Comma-separated expansions: appointments, attachments",
                    },
                },
                "required": ["job_id"],
            },
        ),

        types.Tool(
            name="hcp_get_job_line_items",
            description=(
                "Get all line items for a job — services (labor) and materials with quantity, "
                "unit_price, unit_cost, and total. Quantity on labor items = projected hours. "
                "Also returns discounts and gratuity line items. "
                "kind values: labor, materials, fixed gratuity, fixed discount, percent discount."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                },
                "required": ["job_id"],
            },
        ),

        types.Tool(
            name="hcp_get_job_invoice",
            description=(
                "Get the invoice for a job. Shows what was billed (line items, taxes, discounts) "
                "and payment status (what was paid, method, when, what is still outstanding)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                },
                "required": ["job_id"],
            },
        ),

        types.Tool(
            name="hcp_get_job_input_materials",
            description=(
                "Get materials logged as job inputs (separate from invoice line items). "
                "Returns name, quantity, unit cost, part number."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                },
                "required": ["job_id"],
            },
        ),

        types.Tool(
            name="hcp_get_job_appointments",
            description="Get all scheduled appointment windows for a specific job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                },
                "required": ["job_id"],
            },
        ),

        types.Tool(
            name="hcp_add_job_note",
            description=(
                "Add a note to a job. Notes are visible to both office and field techs. "
                "Use for follow-up details, job updates, or anything relevant to execution."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "content": {"type": "string", "description": "Note content"},
                },
                "required": ["job_id", "content"],
            },
        ),

        # ── Employees ─────────────────────────────────────────────────────────

        types.Tool(
            name="hcp_list_employees",
            description="List all active employees/technicians with their IDs, roles, and contact info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {"description": "Page number (default 1)"},
                    "page_size": {"description": "Results per page (default 50)"},
                },
                "required": [],
            },
        ),

        # ── Invoices ──────────────────────────────────────────────────────────

        types.Tool(
            name="hcp_list_invoices",
            description=(
                "List invoices with rich filtering. Core tool for post-week financial analysis. "
                "Filter by status, date ranges (created, paid, due), payment method, or customer. "
                "status: comma-separated from open, pending_payment, paid, voided, uncollectible, canceled. "
                "All amounts in dollars."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "description": "Comma-separated: open, pending_payment, paid, voided, uncollectible, canceled",
                    },
                    "created_at_min": {"type": "string", "description": "ISO datetime e.g. 2025-04-21T00:00:00Z"},
                    "created_at_max": {"type": "string"},
                    "paid_at_min": {"type": "string"},
                    "paid_at_max": {"type": "string"},
                    "due_at_min": {"type": "string"},
                    "due_at_max": {"type": "string"},
                    "payment_method": {
                        "description": "Comma-separated: consumer_financing, credit_card, ach, external, mobile_check_deposit",
                    },
                    "customer_uuid": {
                        "description": "Comma-separated customer UUIDs",
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": [
                            "amount", "created_at", "due_amount", "due_at",
                            "invoice_number", "paid_at", "sent_at", "status", "updated_at",
                        ],
                        "default": "created_at",
                    },
                    "sort_direction": {"type": "string", "enum": ["asc", "desc"], "default": "desc"},
                    "page": {"description": "Page number (default 1)"},
                    "page_size": {"description": "Results per page, max 100 (default 50)"},
                },
                "required": [],
            },
        ),

        types.Tool(
            name="hcp_get_invoice",
            description=(
                "Get full invoice detail by UUID. Includes line items, taxes, discounts, "
                "and a full payment breakdown (method, amount, date, status)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "invoice_uuid": {"type": "string"},
                },
                "required": ["invoice_uuid"],
            },
        ),

        # ── Estimates ─────────────────────────────────────────────────────────

        types.Tool(
            name="hcp_list_estimates",
            description=(
                "List estimates. Use for pipeline review and estimate-to-job conversion tracking. "
                "Filter by date range, status, or customer. "
                "work_status: comma-separated from unscheduled, scheduled, in_progress, completed, canceled."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "scheduled_start_min": {"type": "string"},
                    "scheduled_start_max": {"type": "string"},
                    "scheduled_end_min": {"type": "string"},
                    "scheduled_end_max": {"type": "string"},
                    "work_status": {
                        "description": "Comma-separated statuses",
                    },
                    "employee_ids": {"description": "Comma-separated employee IDs"},
                    "customer_id": {"type": "string"},
                    "page": {"description": "Page number (default 1)"},
                    "page_size": {"description": "Results per page (default 50)"},
                    "sort_direction": {"type": "string", "enum": ["asc", "desc"], "default": "desc"},
                },
                "required": [],
            },
        ),

        types.Tool(
            name="hcp_get_estimate",
            description="Get full details for a single estimate including options, line items, and customer info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "estimate_id": {"type": "string"},
                },
                "required": ["estimate_id"],
            },
        ),

        # ── Lead Sources ──────────────────────────────────────────────────────

        types.Tool(
            name="hcp_list_lead_sources",
            description=(
                "List all configured lead sources. Use this to see valid lead source names "
                "before doing lead source attribution analysis or reconciliation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {"description": "Page number (default 1)"},
                    "page_size": {"description": "Results per page (default 100)"},
                },
                "required": [],
            },
        ),

        # ── Tags ──────────────────────────────────────────────────────────────

        types.Tool(
            name="hcp_list_tags",
            description=(
                "List all tags configured in Housecall Pro with their IDs, grouped by prefix. "
                "Use to verify tag names and get IDs needed for add/remove operations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {"description": "Page number (default 1)"},
                    "page_size": {"description": "Results per page (default 100)"},
                },
                "required": [],
            },
        ),

        types.Tool(
            name="hcp_create_tag",
            description=(
                "Create a new tag in Housecall Pro. Use to add tags to your tag library "
                "(e.g. SCH-FOLLOWUP, CREW-2L1A, TOOL-SCAFF). Returns the new tag's ID."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Tag name, e.g. SCH-FOLLOWUP"},
                },
                "required": ["name"],
            },
        ),

        types.Tool(
            name="hcp_update_tag",
            description="Rename an existing tag. Provide the tag ID and the new name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tag_id": {"type": "string", "description": "Tag ID (from hcp_list_tags)"},
                    "name": {"type": "string", "description": "New tag name"},
                },
                "required": ["tag_id", "name"],
            },
        ),

        types.Tool(
            name="hcp_add_job_tag",
            description=(
                "Add a tag to a specific job. Use hcp_list_tags first to get the tag_id. "
                "Common use: apply SCH-FOLLOWUP, CREW-*, SCH-*, TOOL-* tags after reviewing a job."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job ID"},
                    "tag_id": {"type": "string", "description": "Tag ID (from hcp_list_tags)"},
                },
                "required": ["job_id", "tag_id"],
            },
        ),

        types.Tool(
            name="hcp_remove_job_tag",
            description="Remove a tag from a specific job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job ID"},
                    "tag_id": {"type": "string", "description": "Tag ID to remove"},
                },
                "required": ["job_id", "tag_id"],
            },
        ),

        # ── Week Schedule ─────────────────────────────────────────────────────

        types.Tool(
            name="hcp_get_week_schedule",
            description=(
                "Build the full schedule for a work week by pulling appointments across all active "
                "jobs and grouping them by day and technician. Shows scheduled hours vs available "
                "capacity with open gaps highlighted. Use week_start=YYYY-MM-DD (a Monday). "
                "Returns per-day and per-tech breakdowns in a single call. "
                "half_time_employee_ids: comma-separated IDs of apprentices who count at 0.5x capacity."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "week_start": {
                        "type": "string",
                        "description": "Monday of the week to build, YYYY-MM-DD. Defaults to current week.",
                    },
                    "full_time_count": {
                        "description": "Number of full-time techs (default 5)",
                    },
                    "hours_per_day": {
                        "description": "Working hours per full-time tech per day (default 8)",
                    },
                    "half_time_employee_ids": {
                        "description": "Comma-separated employee IDs who count at 0.5x capacity (e.g. apprentices)",
                    },
                },
                "required": [],
            },
        ),

        types.Tool(
            name="hcp_get_routes",
            description=(
                "NOTE: Requires HCP Routes feature to be configured in the dispatch board. "
                "Returns empty if your team does not use HCP named routes. "
                "Use hcp_get_week_schedule instead for schedule analysis."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                    "page": {"description": "Page number (default 1)"},
                    "page_size": {"description": "Routes per page (default 50)"},
                },
                "required": [],
            },
        ),

        types.Tool(
            name="hcp_create_appointment",
            description=(
                "Add a new appointment (scheduled day/visit) to an existing job. "
                "Use for multi-day jobs to schedule the next day of work. "
                "Specify start_time, end_time (ISO 8601), and which techs to dispatch."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "start_time": {
                        "type": "string",
                        "description": "ISO 8601 datetime, e.g. 2026-04-28T07:30:00",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "ISO 8601 datetime, e.g. 2026-04-28T16:00:00",
                    },
                    "arrival_window_minutes": {
                        "description": "Arrival window in minutes (default 0)",
                    },
                    "dispatched_employee_ids": {
                        "description": "Comma-separated employee IDs to dispatch to this appointment",
                    },
                },
                "required": ["job_id", "start_time", "end_time"],
            },
        ),

        types.Tool(
            name="hcp_update_appointment",
            description=(
                "Update an existing appointment — change the date, time window, or dispatched techs. "
                "Use hcp_get_job_appointments to get appointment IDs first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "appointment_id": {"type": "string", "description": "Appointment ID from hcp_get_job_appointments"},
                    "start_time": {"type": "string", "description": "ISO 8601 datetime"},
                    "end_time": {"type": "string", "description": "ISO 8601 datetime"},
                    "arrival_window_minutes": {"description": "Arrival window in minutes"},
                    "dispatched_employee_ids": {
                        "description": "Comma-separated employee IDs — replaces the current dispatched list",
                    },
                },
                "required": ["job_id", "appointment_id"],
            },
        ),

        types.Tool(
            name="hcp_delete_appointment",
            description=(
                "Delete a specific appointment from a job. "
                "Use hcp_get_job_appointments to get the appointment ID first. "
                "Cannot be undone — confirm before calling."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "appointment_id": {"type": "string", "description": "Appointment ID to delete"},
                },
                "required": ["job_id", "appointment_id"],
            },
        ),

        # ── Events ────────────────────────────────────────────────────────────

        types.Tool(
            name="hcp_list_events",
            description=(
                "List non-job calendar events (time off, meetings, internal schedule blocks). "
                "Important for full schedule visibility during pre-week planning."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {"default": 1, "type": "number"},
                    "page_size": {"default": 50, "type": "number"},
                    "sort_direction": {"default": "asc", "enum": ["asc", "desc"], "type": "string"},
                },
                "required": [],
            },
        ),

    ]


# ── Tool handlers ──────────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    try:
        async with _client() as client:

            # ── hcp_list_customers ────────────────────────────────────────────
            if name == "hcp_list_customers":
                params: dict[str, Any] = {
                    "page": _as_int(arguments.get("page"), 1),
                    "page_size": _as_int(arguments.get("page_size"), 25),
                    "sort_by": arguments.get("sort_by", "created_at"),
                    "sort_direction": arguments.get("sort_direction", "desc"),
                }
                if q := arguments.get("q"):
                    params["q"] = q
                data = await _get(client, "/customers", params)
                customers = data.get("customers", [])
                total = data.get("total_items", len(customers))
                return [types.TextContent(
                    type="text",
                    text=f"Found {total} customer(s). Page {params['page']}.\n\n{_fmt(customers)}",
                )]

            # ── hcp_get_customer ──────────────────────────────────────────────
            elif name == "hcp_get_customer":
                data = await _get(client, f"/customers/{arguments['customer_id']}", {})
                return [types.TextContent(type="text", text=_fmt(data))]

            # ── hcp_create_customer ───────────────────────────────────────────
            elif name == "hcp_create_customer":
                payload: dict[str, Any] = {
                    "first_name": arguments["first_name"],
                    "last_name": arguments["last_name"],
                    "notifications_enabled": arguments.get("notifications_enabled", True),
                }
                for field in ("email", "company", "mobile_number", "home_number", "work_number"):
                    if arguments.get(field):
                        payload[field] = arguments[field]
                address_fields = {k: arguments.get(k) for k in ("street", "city", "state", "zip")}
                if any(address_fields.values()):
                    payload["addresses"] = [{k: v for k, v in address_fields.items() if v}]
                resp = await client.post("/customers", json=payload)
                resp.raise_for_status()
                return [types.TextContent(
                    type="text",
                    text=f"Customer created successfully!\n\n{_fmt(resp.json())}",
                )]

            # ── hcp_list_jobs ─────────────────────────────────────────────────
            elif name == "hcp_list_jobs":
                params = {
                    "page": _as_int(arguments.get("page"), 1),
                    "page_size": _as_int(arguments.get("page_size"), 50),
                    "sort_by": arguments.get("sort_by", "created_at"),
                    "sort_direction": arguments.get("sort_direction", "asc"),
                }
                for key in (
                    "scheduled_start_min", "scheduled_start_max",
                    "scheduled_end_min", "scheduled_end_max", "customer_id",
                ):
                    if val := arguments.get(key):
                        params[key] = val
                if statuses := _as_list(arguments.get("work_status")):
                    params["work_status"] = statuses
                if emp_ids := _as_list(arguments.get("employee_ids")):
                    params["employee_ids"] = emp_ids
                if expand := _as_list(arguments.get("expand")):
                    params["expand"] = expand

                data = await _get(client, "/jobs", params)
                jobs = data.get("jobs", [])
                total = data.get("total_items", len(jobs))

                lines = [f"Found {total} job(s). Page {params['page']}.\n"]
                for job in jobs:
                    tags = job.get("tags", [])
                    tg = _parse_tags(tags)
                    schedule = job.get("schedule") or {}
                    employees = job.get("assigned_employees", [])
                    emp_names = (
                        ", ".join(
                            (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
                            for e in employees
                        )
                        or "Unassigned"
                    )
                    customer = job.get("customer") or {}
                    follow_up = "SCH-FOLLOWUP" in [t.upper() for t in tags]

                    lines.append(
                        f"• [{job.get('invoice_number','?')}] {job.get('description','(no description)')}"
                        + (" ⚑ FOLLOW-UP" if follow_up else "")
                        + f"\n  Status: {job.get('work_status','?')}"
                        f"  |  Total: {_dollars(job.get('total_amount'))}"
                        f"  |  Outstanding: {_dollars(job.get('outstanding_balance'))}"
                        f"\n  Schedule: {schedule.get('start_time','?')} → {schedule.get('end_time','?')}"
                        f"\n  Assigned: {emp_names}"
                        f"  |  Crew: {_crew_summary(tg['crew'])}"
                        f"\n  SCH: {', '.join(tg['scheduling']) or '—'}"
                        f"  |  MAT: {', '.join(tg['materials']) or '—'}"
                        f"  |  TOOL: {', '.join(tg['tools']) or '—'}"
                        f"\n  Customer: {customer.get('first_name','')} {customer.get('last_name','')}"
                        f"  |  Lead source: {job.get('lead_source') or customer.get('lead_source') or '—'}"
                        f"  |  Job ID: {job.get('id','')}\n"
                    )
                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── hcp_get_job ───────────────────────────────────────────────────
            elif name == "hcp_get_job":
                params = {}
                if expand := _as_list(arguments.get("expand")):
                    params["expand"] = expand
                data = await _get(client, f"/jobs/{arguments['job_id']}", params)

                tags = data.get("tags", [])
                tg = _parse_tags(tags)
                ts = data.get("work_timestamps") or {}
                schedule = data.get("schedule") or {}
                employees = data.get("assigned_employees", [])
                customer = data.get("customer") or {}
                address = data.get("address") or {}

                actual_note = ""
                if ts.get("started_at") and ts.get("completed_at"):
                    from datetime import datetime
                    try:
                        start = datetime.fromisoformat(ts["started_at"].replace("Z", "+00:00"))
                        end = datetime.fromisoformat(ts["completed_at"].replace("Z", "+00:00"))
                        elapsed = (end - start).total_seconds() / 3600
                        actual_note = f" (elapsed start→complete: {elapsed:.1f} hrs — includes any paused time)"
                    except Exception:
                        pass

                emp_line = ", ".join(
                    (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
                    for e in employees
                ) or "None"

                summary = (
                    f"Job: {data.get('description','(no description)')}\n"
                    f"Invoice #: {data.get('invoice_number','?')}  |  ID: {data.get('id','')}\n"
                    f"Status: {data.get('work_status','?')}\n"
                    f"Customer: {customer.get('first_name','')} {customer.get('last_name','')}"
                    f"  |  Lead source: {data.get('lead_source') or customer.get('lead_source') or '—'}\n"
                    f"Address: {address.get('street','')} {address.get('city','')}, {address.get('state','')}\n\n"
                    f"Schedule: {schedule.get('start_time','?')} → {schedule.get('end_time','?')}"
                    f"  |  Window: {schedule.get('arrival_window_minutes','?')} min\n\n"
                    f"Financials:\n"
                    f"  Subtotal:    {_dollars(data.get('subtotal'))}\n"
                    f"  Total:       {_dollars(data.get('total_amount'))}\n"
                    f"  Outstanding: {_dollars(data.get('outstanding_balance'))}\n\n"
                    f"Assigned: {emp_line}\n\n"
                    f"Tags:\n"
                    f"  Crew:      {_crew_summary(tg['crew'])}\n"
                    f"  Location:  {', '.join(tg['job']) or '—'}\n"
                    f"  Scheduling:{', '.join(tg['scheduling']) or '—'}\n"
                    f"  Materials: {', '.join(tg['materials']) or '—'}\n"
                    f"  Tools:     {', '.join(tg['tools']) or '—'}\n"
                    f"  Other:     {', '.join(tg['other']) or '—'}\n\n"
                    f"Work Timestamps:\n"
                    f"  On My Way: {ts.get('on_my_way_at','—')}\n"
                    f"  Started:   {ts.get('started_at','—')}\n"
                    f"  Completed: {ts.get('completed_at','—')}{actual_note}\n\n"
                    f"Created: {data.get('created_at','?')}  |  Updated: {data.get('updated_at','?')}\n"
                )
                if data.get("original_estimate_id"):
                    summary += f"From estimate: {data['original_estimate_id']}\n"
                if data.get("recurrence_rule"):
                    summary += f"Recurrence: {data['recurrence_rule']}\n"
                return [types.TextContent(type="text", text=summary)]

            # ── hcp_get_job_line_items ────────────────────────────────────────
            elif name == "hcp_get_job_line_items":
                data = await _get(client, f"/jobs/{arguments['job_id']}/line_items", {})
                items = data.get("data", [])

                labor = [i for i in items if i.get("kind") == "labor"]
                materials = [i for i in items if i.get("kind") == "materials"]
                other = [i for i in items if i.get("kind") not in ("labor", "materials")]

                projected_hours = sum(i.get("quantity", 0) or 0 for i in labor)
                lines = [f"Line Items — {len(items)} total  |  Projected hours: {projected_hours:.2f}\n"]

                if labor:
                    lines.append("SERVICES / LABOR:")
                    for i in labor:
                        cost_str = f"  (cost/unit: {_dollars(i.get('unit_cost'))})" if i.get("unit_cost") else ""
                        lines.append(
                            f"  • {i.get('name','')} — qty: {i.get('quantity', 0)}"
                            f"  @ {_dollars(i.get('unit_price'))} = {_dollars(i.get('amount'))}{cost_str}"
                        )
                        if i.get("description"):
                            lines.append(f"    {i['description']}")

                if materials:
                    lines.append("\nMATERIALS:")
                    for i in materials:
                        cost_str = f"  (cost/unit: {_dollars(i.get('unit_cost'))})" if i.get("unit_cost") else ""
                        lines.append(
                            f"  • {i.get('name','')} — qty: {i.get('quantity', 0)}"
                            f"  @ {_dollars(i.get('unit_price'))} = {_dollars(i.get('amount'))}{cost_str}"
                        )
                        if i.get("description"):
                            lines.append(f"    {i['description']}")

                if other:
                    lines.append("\nDISCOUNTS / GRATUITY:")
                    for i in other:
                        lines.append(
                            f"  • [{i.get('kind','')}] {i.get('name','')} — {_dollars(i.get('amount'))}"
                        )

                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── hcp_get_job_invoice ───────────────────────────────────────────
            elif name == "hcp_get_job_invoice":
                data = await _get(client, f"/jobs/{arguments['job_id']}/invoices", {})
                if isinstance(data, list):
                    invoices = data
                else:
                    invoices = data.get("invoices", [data] if data.get("id") else [])
                if not invoices:
                    return [types.TextContent(type="text", text="No invoice found for this job.")]

                inv = invoices[0]
                lines = [
                    f"Invoice #{inv.get('invoice_number','?')}  |  Status: {inv.get('status','?')}\n",
                    f"Service date: {inv.get('service_date','—')}  |  Invoice date: {inv.get('invoice_date','—')}",
                    f"Sent: {inv.get('sent_at','—')}  |  Paid: {inv.get('paid_at','—')}",
                    f"Due concept: {inv.get('display_due_concept','—')}  |  Due: {inv.get('due_at','—')}\n",
                    f"Subtotal:   {_dollars(inv.get('subtotal'))}",
                    f"Total:      {_dollars(inv.get('amount'))}",
                    f"Due:        {_dollars(inv.get('due_amount'))}\n",
                ]

                if items := inv.get("items", []):
                    lines.append("Line Items:")
                    for i in items:
                        qty = (i.get("qty_in_hundredths") or 0) / 100
                        lines.append(
                            f"  • {i.get('name','')} [{i.get('type','')}]"
                            f"  qty: {qty}  @ {_dollars(i.get('unit_price'))} = {_dollars(i.get('amount'))}"
                        )

                if taxes := inv.get("taxes", []):
                    lines.append("\nTaxes:")
                    for t in taxes:
                        lines.append(f"  • {t.get('name','')} — {_dollars(t.get('amount'))}")

                if discounts := inv.get("discounts", []):
                    lines.append("\nDiscounts:")
                    for d in discounts:
                        lines.append(f"  • {d.get('name','')} — {_dollars(d.get('amount'))}")

                if payments := inv.get("payments", []):
                    lines.append("\nPayments:")
                    for p in payments:
                        lines.append(
                            f"  • {_dollars(p.get('amount'))} via {p.get('payment_method','?')}"
                            f"  on {p.get('paid_at','?')}  [{p.get('status','?')}]"
                            + (f"  note: {p['note']}" if p.get("note") else "")
                        )

                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── hcp_get_job_input_materials ───────────────────────────────────
            elif name == "hcp_get_job_input_materials":
                data = await _get(client, f"/jobs/{arguments['job_id']}/job_input_materials", {})
                materials = data.get("job_input_materials", [])
                if not materials:
                    return [types.TextContent(type="text", text="No input materials logged for this job.")]
                lines = [f"{len(materials)} material(s):\n"]
                for m in materials:
                    cost = _dollars(m.get("unit_cost")) if m.get("unit_cost") else "—"
                    lines.append(
                        f"  • {m.get('name','')}  qty: {m.get('quantity', '?')}  unit cost: {cost}"
                    )
                    if m.get("description"):
                        lines.append(f"    {m['description']}")
                    if m.get("part_number"):
                        lines.append(f"    Part #: {m['part_number']}")
                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── hcp_get_job_appointments ──────────────────────────────────────
            elif name == "hcp_get_job_appointments":
                # Fetch employee list to resolve IDs → names
                emp_data = await _get(client, "/employees", {"page_size": 100})
                emp_map: dict[str, str] = {
                    e["id"]: (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
                    for e in emp_data.get("employees", [])
                }

                data = await _get(client, f"/jobs/{arguments['job_id']}/appointments", {})
                appts = data.get("appointments", [])
                if not appts:
                    return [types.TextContent(type="text", text="No appointments found for this job.")]
                lines = [f"{len(appts)} appointment(s):\n"]
                for a in appts:
                    # Try full objects first, fall back to ID list
                    emp_objs = a.get("assigned_employees") or []
                    if emp_objs:
                        dispatched = ", ".join(
                            (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
                            for e in emp_objs
                        )
                    else:
                        ids = a.get("dispatched_employees_ids") or []
                        dispatched = ", ".join(emp_map.get(i, i) for i in ids) if ids else "—"
                    lines.append(
                        f"  • {a.get('start_time','?')} → {a.get('end_time','?')}"
                        f"  [{a.get('status','?')}]"
                        f"  window: {a.get('arrival_window_minutes','?')} min"
                        f"  |  Dispatched: {dispatched}"
                    )
                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── hcp_add_job_note ──────────────────────────────────────────────
            elif name == "hcp_add_job_note":
                payload = {"content": arguments["content"]}
                resp = await client.post(f"/jobs/{arguments['job_id']}/notes", json=payload)
                resp.raise_for_status()
                return [types.TextContent(
                    type="text",
                    text=f"Note added to job {arguments['job_id']}.",
                )]

            # ── hcp_list_employees ────────────────────────────────────────────
            elif name == "hcp_list_employees":
                params = {
                    "page": _as_int(arguments.get("page"), 1),
                    "page_size": _as_int(arguments.get("page_size"), 50),
                }
                data = await _get(client, "/employees", params)
                employees = data.get("employees", [])
                total = data.get("total_items", len(employees))
                lines = [f"{total} employee(s):\n"]
                for e in employees:
                    lines.append(
                        f"  • {e.get('first_name','')} {e.get('last_name','')}"
                        f"  [{e.get('role','?')}]"
                        f"  id: {e.get('id','')}"
                        f"  |  {e.get('email','—')}"
                    )
                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── hcp_list_invoices ─────────────────────────────────────────────
            elif name == "hcp_list_invoices":
                params: dict[str, Any] = {
                    "page": _as_int(arguments.get("page"), 1),
                    "page_size": _as_int(arguments.get("page_size"), 50),
                    "sort_by": arguments.get("sort_by", "created_at"),
                    "sort_direction": arguments.get("sort_direction", "desc"),
                }
                for key in (
                    "created_at_min", "created_at_max",
                    "paid_at_min", "paid_at_max",
                    "due_at_min", "due_at_max",
                ):
                    if val := arguments.get(key):
                        params[key] = val
                if statuses := _as_list(arguments.get("status")):
                    params["status"] = statuses
                if methods := _as_list(arguments.get("payment_method")):
                    params["payment_method"] = methods
                if cuuids := _as_list(arguments.get("customer_uuid")):
                    params["customer_uuid"] = cuuids

                data = await _get(client, "/invoices", params)
                invoices = data.get("invoices", [])
                total = data.get("total_items", len(invoices))

                page_billed = sum(i.get("amount", 0) or 0 for i in invoices)
                page_due = sum(i.get("due_amount", 0) or 0 for i in invoices)

                lines = [
                    f"Found {total} invoice(s). Page {params['page']}.",
                    f"This page — Billed: {_dollars(page_billed)}  |  Still due: {_dollars(page_due)}\n",
                ]
                for inv in invoices:
                    lines.append(
                        f"• #{inv.get('invoice_number','?')} [{inv.get('status','?')}]"
                        f"  {_dollars(inv.get('amount'))}"
                        f"  |  due: {_dollars(inv.get('due_amount'))}"
                        f"  |  paid: {inv.get('paid_at','—')}"
                        f"  |  job: {inv.get('job_id','?')}"
                    )
                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── hcp_get_invoice ───────────────────────────────────────────────
            elif name == "hcp_get_invoice":
                data = await _get(client, f"/api/invoices/{arguments['invoice_uuid']}", {})
                inv = data
                lines = [
                    f"Invoice #{inv.get('invoice_number','?')}  |  Status: {inv.get('status','?')}",
                    f"Job ID: {inv.get('job_id','—')}",
                    f"Service date: {inv.get('service_date','—')}  |  Paid: {inv.get('paid_at','—')}\n",
                    f"Subtotal:   {_dollars(inv.get('subtotal'))}",
                    f"Total:      {_dollars(inv.get('amount'))}",
                    f"Due:        {_dollars(inv.get('due_amount'))}\n",
                ]
                if items := inv.get("items", []):
                    lines.append("Items:")
                    for i in items:
                        qty = (i.get("qty_in_hundredths") or 0) / 100
                        lines.append(
                            f"  • {i.get('name','')}  qty: {qty}"
                            f"  @ {_dollars(i.get('unit_price'))} = {_dollars(i.get('amount'))}"
                        )
                if taxes := inv.get("taxes", []):
                    lines.append("\nTaxes:")
                    for t in taxes:
                        lines.append(f"  • {t.get('name','')} — {_dollars(t.get('amount'))}")
                if discounts := inv.get("discounts", []):
                    lines.append("\nDiscounts:")
                    for d in discounts:
                        lines.append(f"  • {d.get('name','')} — {_dollars(d.get('amount'))}")
                if payments := inv.get("payments", []):
                    lines.append("\nPayments:")
                    for p in payments:
                        lines.append(
                            f"  • {_dollars(p.get('amount'))} via {p.get('payment_method','?')}"
                            f"  [{p.get('status','?')}]  {p.get('paid_at','—')}"
                        )
                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── hcp_list_estimates ────────────────────────────────────────────
            elif name == "hcp_list_estimates":
                params = {
                    "page": _as_int(arguments.get("page"), 1),
                    "page_size": _as_int(arguments.get("page_size"), 50),
                    "sort_direction": arguments.get("sort_direction", "desc"),
                }
                for key in (
                    "scheduled_start_min", "scheduled_start_max",
                    "scheduled_end_min", "scheduled_end_max", "customer_id",
                ):
                    if val := arguments.get(key):
                        params[key] = val
                if statuses := _as_list(arguments.get("work_status")):
                    params["work_status"] = statuses
                if emp_ids := _as_list(arguments.get("employee_ids")):
                    params["employee_ids"] = emp_ids

                data = await _get(client, "/estimates", params)
                estimates = data.get("estimates", [])
                total = data.get("total_items", len(estimates))
                lines = [f"Found {total} estimate(s). Page {params['page']}.\n"]
                for e in estimates:
                    customer = e.get("customer") or {}
                    lines.append(
                        f"• [{e.get('estimate_number','?')}] {e.get('work_status','?')}"
                        f"  |  Customer: {customer.get('first_name','')} {customer.get('last_name','')}"
                        f"  |  Lead source: {e.get('lead_source') or customer.get('lead_source') or '—'}"
                        f"  |  ID: {e.get('id','')}"
                    )
                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── hcp_get_estimate ──────────────────────────────────────────────
            elif name == "hcp_get_estimate":
                data = await _get(client, f"/estimates/{arguments['estimate_id']}", {})
                return [types.TextContent(type="text", text=_fmt(data))]

            # ── hcp_list_lead_sources ─────────────────────────────────────────
            elif name == "hcp_list_lead_sources":
                params = {
                    "page": _as_int(arguments.get("page"), 1),
                    "page_size": _as_int(arguments.get("page_size"), 100),
                }
                data = await _get(client, "/lead_sources", params)
                sources = data.get("lead_sources", data if isinstance(data, list) else [])
                lines = [f"{len(sources)} lead source(s):\n"]
                for s in sources:
                    editable = "editable" if s.get("editable") else "read-only"
                    lines.append(f"  • {s.get('name','')}  [{editable}]  id: {s.get('id','')}")
                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── hcp_list_tags ─────────────────────────────────────────────────
            elif name == "hcp_list_tags":
                params = {
                    "page": _as_int(arguments.get("page"), 1),
                    "page_size": _as_int(arguments.get("page_size"), 100),
                }
                data = await _get(client, "/tags", params)
                tags = data.get("tags", data if isinstance(data, list) else [])
                grouped: dict[str, list[str]] = {}
                for t in tags:
                    tag_name = t.get("name", "")
                    prefix = tag_name.split("-")[0].upper() if "-" in tag_name else "OTHER"
                    grouped.setdefault(prefix, []).append(f"{tag_name}  (id: {t.get('id','')})")
                lines = [f"{len(tags)} tag(s) configured:\n"]
                for prefix in sorted(grouped):
                    lines.append(f"{prefix}:")
                    for entry in grouped[prefix]:
                        lines.append(f"  • {entry}")
                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── hcp_create_tag ────────────────────────────────────────────────
            elif name == "hcp_create_tag":
                resp = await client.post("/tags", json={"name": arguments["name"]})
                resp.raise_for_status()
                tag = resp.json()
                return [types.TextContent(
                    type="text",
                    text=f"Tag created: {tag.get('name','')}  id: {tag.get('id','')}",
                )]

            # ── hcp_update_tag ────────────────────────────────────────────────
            elif name == "hcp_update_tag":
                resp = await client.put(f"/tags/{arguments['tag_id']}", json={"name": arguments["name"]})
                resp.raise_for_status()
                tag = resp.json()
                return [types.TextContent(
                    type="text",
                    text=f"Tag updated: {tag.get('name','')}  id: {tag.get('id','')}",
                )]

            # ── hcp_add_job_tag ───────────────────────────────────────────────
            elif name == "hcp_add_job_tag":
                resp = await client.post(
                    f"/jobs/{arguments['job_id']}/tags",
                    json={"tag_id": arguments["tag_id"]},
                )
                resp.raise_for_status()
                result = resp.json()
                tags_now = [t.get("name", "") for t in result.get("tags", [])]
                return [types.TextContent(
                    type="text",
                    text=f"Tag added. Job now has tags: {', '.join(tags_now) or '(none)'}",
                )]

            # ── hcp_remove_job_tag ────────────────────────────────────────────
            elif name == "hcp_remove_job_tag":
                resp = await client.delete(
                    f"/jobs/{arguments['job_id']}/tags/{arguments['tag_id']}"
                )
                resp.raise_for_status()
                result = resp.json()
                tags_now = [t.get("name", "") for t in result.get("tags", [])]
                return [types.TextContent(
                    type="text",
                    text=f"Tag removed. Job now has tags: {', '.join(tags_now) or '(none)'}",
                )]

            # ── hcp_get_week_schedule ─────────────────────────────────────────
            elif name == "hcp_get_week_schedule":
                from datetime import date, timedelta, datetime as dt

                # Parse week_start → always snap to Monday of that week
                ws_str = arguments.get("week_start")
                if ws_str:
                    anchor = date.fromisoformat(ws_str)
                else:
                    anchor = date.today()
                week_start = anchor - timedelta(days=anchor.weekday())  # always Monday
                weekdays = [week_start + timedelta(days=i) for i in range(5)]
                week_end  = weekdays[-1]

                # Capacity config
                # Default half-time employee: Ryan Bianucci (apprentice, 0.5× capacity)
                _DEFAULT_HALF_TIME = {"pro_3dc62cf7dcba426d9e5701704753da70"}
                ft_count    = _as_int(arguments.get("full_time_count"), 5)
                hrs_per_day = _as_int(arguments.get("hours_per_day"), 8)
                ht_ids      = set(_as_list(arguments.get("half_time_employee_ids")) or []) or _DEFAULT_HALF_TIME

                # ── Parallel fetch: employees + scheduled jobs + in_progress jobs ─
                #
                # TWO separate job queries are needed because the API's
                # scheduled_start_min/max filter is applied to the job's PRIMARY
                # schedule object (schedule.start_time).  Jobs that were scheduled
                # via individual appointments but never had a primary schedule date
                # set will have schedule.start_time = null and are completely
                # invisible to date-filtered queries.
                #
                # Fix: fetch in_progress jobs WITHOUT a date filter (they're
                # actively running by definition), and fetch scheduled jobs WITH a
                # date window.  Then merge + deduplicate by job ID.
                look_back = week_start - timedelta(days=60)
                # Query A: date-filtered window — catches scheduled jobs that have a
                #   primary schedule date set.  No work_status filter (API rejects
                #   scalar strings; list form conflicts with httpx encoding for
                #   single-value arrays on this endpoint).  Filter client-side.
                date_params = {
                    "page_size": 100,
                    "scheduled_start_min": f"{look_back.isoformat()}T00:00:00",
                    "scheduled_start_max": f"{week_end.isoformat()}T23:59:59",
                    "sort_by": "updated_at",
                    "sort_direction": "desc",
                }
                # Query B: recently-updated jobs with NO date filter — catches
                #   in_progress jobs whose schedule.start_time is null (they were
                #   scheduled via appointments only).  Sorted by updated_at desc so
                #   active jobs always appear on page 1-2.
                recent_params = {
                    "page_size": 100,
                    "sort_by": "updated_at",
                    "sort_direction": "desc",
                }

                emp_data, d1, d2, r1, r2 = await asyncio.gather(
                    _get(client, "/employees", {"page_size": 100}),
                    _get(client, "/jobs", {**date_params, "page": 1}),
                    _get(client, "/jobs", {**date_params, "page": 2}),
                    _get(client, "/jobs", {**recent_params, "page": 1}),
                    _get(client, "/jobs", {**recent_params, "page": 2}),
                )

                emp_map: dict[str, str] = {
                    e["id"]: (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
                    for e in emp_data.get("employees", [])
                }

                # Merge, deduplicate, and keep only scheduled + in_progress.
                # NOTE: HCP API returns status as "in progress" (space) in job data
                # but filter params use "in_progress" (underscore). Normalize both
                # so we don't silently drop actively-running jobs.
                def _norm_status(s: str) -> str:
                    return (s or "").lower().replace(" ", "_").replace("-", "_")

                seen_ids: set[str] = set()
                active: list[dict] = []
                for j in (
                    r1.get("jobs", []) + r2.get("jobs", [])   # recent first
                    + d1.get("jobs", []) + d2.get("jobs", [])  # then date-filtered
                ):
                    if _norm_status(j.get("work_status", "")) not in ("scheduled", "in_progress"):
                        continue
                    jid = j.get("id")
                    if jid and jid not in seen_ids:
                        seen_ids.add(jid)
                        active.append(j)

                # ── Parallel fetch: appointments for every active job ─────────
                appt_lists = await asyncio.gather(*[
                    _get(client, f"/jobs/{j['id']}/appointments", {})
                    for j in active
                ])

                # ── Aggregate: day → tech → [(hours, job_label)] ─────────────
                week_day_strs = {d.isoformat() for d in weekdays}
                DayData = dict  # {tech_id|None: [(hours, label)]}
                day_map: dict[str, DayData] = {d.isoformat(): {} for d in weekdays}

                def _parse_hours(s: str, e: str) -> float:
                    try:
                        s_dt = dt.fromisoformat(s.replace("Z", "+00:00"))
                        e_dt = dt.fromisoformat(e.replace("Z", "+00:00"))
                        return max(0.0, (e_dt - s_dt).total_seconds() / 3600)
                    except Exception:
                        return 8.0

                for job, resp in zip(active, appt_lists):
                    customer = job.get("customer") or {}
                    cust_name = (
                        f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                        or (job.get("description") or "")[:22]
                    )
                    label = f"#{job.get('invoice_number','?')} {cust_name}"
                    # Job-level assigned employees — fallback when the appointment's
                    # dispatched_employees_ids field is empty.
                    job_assigned_ids = [
                        e["id"] for e in (job.get("assigned_employees") or [])
                        if e.get("id")
                    ]
                    for appt in resp.get("appointments", []):
                        appt_start_str = appt.get("start_time") or ""
                        appt_end_str   = appt.get("end_time")   or ""
                        if not appt_start_str:
                            continue

                        # Resolve which days in THIS week the appointment covers.
                        # Multi-week/multi-day jobs often have a single appointment
                        # whose start_time predates this week — we must check date
                        # range overlap, not just start_time[:10].
                        try:
                            appt_s = date.fromisoformat(appt_start_str[:10])
                            appt_e = date.fromisoformat(appt_end_str[:10]) if appt_end_str else appt_s
                        except ValueError:
                            continue

                        covered = [d for d in weekdays if appt_s <= d <= appt_e]
                        if not covered:
                            continue

                        # Hours per covered day:
                        # - Single-day appointment → use actual start/end duration.
                        # - Multi-day span → use hrs_per_day (can't split a
                        #   multi-week appointment duration into per-day hours
                        #   reliably from start/end alone).
                        total_span_days = max(1, (appt_e - appt_s).days + 1)
                        if total_span_days == 1:
                            daily_hrs = _parse_hours(appt_start_str, appt_end_str)
                        else:
                            daily_hrs = float(hrs_per_day)

                        dispatched = appt.get("dispatched_employees_ids") or []
                        if not dispatched:
                            dispatched = job_assigned_ids  # job-level fallback

                        for target_day in covered:
                            d_str = target_day.isoformat()
                            if not dispatched:
                                bucket = day_map[d_str].setdefault(None, [])
                                bucket.append((daily_hrs, label))
                            else:
                                for tid in dispatched:
                                    bucket = day_map[d_str].setdefault(tid, [])
                                    bucket.append((daily_hrs, label))

                # ── Build output ──────────────────────────────────────────────
                _DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                day_names = [_DAY_ABBR[d.weekday()] for d in weekdays]
                lines: list[str] = [
                    f"Week of {week_start.strftime('%b %d, %Y')} — schedule vs capacity\n"
                ]

                # Capacity per day: full-time techs + 0.5× half-time
                # Use actual dispatched employee set to know half-timers each day
                total_ft_cap = ft_count * hrs_per_day  # full-time portion
                # We'll compute half-time contribution dynamically per day below

                week_sched = 0.0
                week_cap   = 0.0
                day_summaries: list[str] = []
                conflicts: list[str] = []  # scheduling issues to surface at bottom

                for day_date, day_name in zip(weekdays, day_names):
                    d_str = day_date.isoformat()
                    tech_data = day_map[d_str]

                    # Scheduled hours per tech
                    tech_hours: dict[str, float] = {}
                    unassigned_hrs = 0.0
                    for tid, entries in tech_data.items():
                        hrs_sum = sum(h for h, _ in entries)
                        if tid is None:
                            unassigned_hrs += hrs_sum
                        else:
                            tech_hours[tid] = tech_hours.get(tid, 0.0) + hrs_sum

                    # Capacity = full-time techs + half-timers at 0.5×
                    cap = ft_count * hrs_per_day + len(ht_ids) * hrs_per_day * 0.5
                    sched = sum(tech_hours.values()) + unassigned_hrs

                    week_sched += sched
                    week_cap   += cap
                    open_hrs    = max(0.0, cap - sched)

                    bar_filled = min(20, int(round((sched / cap * 20) if cap else 0)))
                    bar = "█" * bar_filled + "░" * (20 - bar_filled)
                    pct = sched / cap * 100 if cap else 0

                    day_lines = [
                        f"{'─'*56}",
                        f"{day_name} {day_date.strftime('%b %d')}  "
                        f"[{bar}] {pct:.0f}%  "
                        f"{sched:.1f} / {cap:.1f} hrs  "
                        f"({'%.1f open' % open_hrs if open_hrs > 0.5 else 'FULL'})",
                    ]
                    if tech_hours:
                        for tid, hrs in sorted(tech_hours.items(),
                                               key=lambda x: emp_map.get(x[0], x[0])):
                            name = emp_map.get(tid, tid)
                            ht_marker = " (0.5×)" if tid in ht_ids else ""
                            jobs_today = [lbl for _, lbl in tech_data.get(tid, [])]
                            job_str = " · ".join(dict.fromkeys(jobs_today))  # dedupe
                            # Flag tech overbook: hours exceed a full day's work.
                            # Half-time employees (apprentices) still work full days —
                            # their 0.5× factor only reduces team capacity contribution,
                            # NOT their personal daily hours. So everyone gets the same
                            # 1.0 hr tolerance over hrs_per_day.
                            tech_cap  = float(hrs_per_day)
                            tolerance = 1.0
                            if hrs > tech_cap + tolerance:
                                flag = " ⚠ OVERBOOKED"
                                conflicts.append(
                                    f"  {day_name} {day_date.strftime('%b %d')}: "
                                    f"{name} has {hrs:.1f} hrs scheduled "
                                    f"(>{tech_cap:.0f} hr day) — {job_str}"
                                )
                            else:
                                flag = ""
                            day_lines.append(
                                f"  {name}{ht_marker}: {hrs:.1f} hrs  — {job_str}{flag}"
                            )
                    if unassigned_hrs > 0:
                        day_lines.append(
                            f"  ⚠ UNASSIGNED: {unassigned_hrs:.1f} hrs  "
                            f"(appointments missing dispatch assignments in HCP)"
                        )
                    if open_hrs > 0.5:
                        day_lines.append(f"  ◌ {open_hrs:.1f} hrs open / available to schedule")
                    day_summaries.append("\n".join(day_lines))

                lines.append("\n".join(day_summaries))
                lines.append(f"\n{'═'*56}")
                lines.append(
                    f"WEEK TOTAL: {week_sched:.1f} scheduled / {week_cap:.1f} available "
                    f"({week_sched/week_cap*100:.0f}% capacity)"
                )
                lines.append(f"Open capacity: {max(0.0, week_cap - week_sched):.1f} hrs")
                if conflicts:
                    lines.append(f"\n⚠ SCHEDULING CONFLICTS ({len(conflicts)}):")
                    lines.extend(conflicts)

                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── hcp_get_routes ────────────────────────────────────────────────
            elif name == "hcp_get_routes":
                params: dict[str, Any] = {
                    "page": _as_int(arguments.get("page"), 1),
                    "per_page": _as_int(arguments.get("page_size"), 50),
                }
                if date := arguments.get("date"):
                    params["date"] = date

                # Fetch employee map and routes in parallel
                emp_data = await _get(client, "/employees", {"page_size": 100})
                emp_map: dict[str, str] = {
                    e["id"]: (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
                    for e in emp_data.get("employees", [])
                }

                data = await _get(client, "/routes", params)
                routes = data.get("routes", [])
                total = data.get("total_items", len(routes))
                query_date = arguments.get("date", "today")

                if not routes:
                    return [types.TextContent(type="text", text=f"No routes found for {query_date}.")]

                lines = [f"Routes for {query_date} — {total} route(s):\n"]
                for route in routes:
                    emp_ids = route.get("employee_ids", [])
                    emp_names = ", ".join(emp_map.get(i, i) for i in emp_ids) or "Unassigned"
                    lines.append(f"\n▸ {route.get('name', '?')}  ({emp_names})")

                    appts = route.get("job_appointments", [])
                    if appts:
                        for a in appts:
                            job = a.get("job") or {}
                            start = a.get("start_time", "?")
                            end = a.get("end_time", "?")
                            dispatched_ids = a.get("dispatched_employees_ids", [])
                            dispatched = ", ".join(emp_map.get(i, i) for i in dispatched_ids) or "—"
                            lines.append(
                                f"   • [{job.get('invoice_number','?')}] {job.get('description','?')}"
                                f"  {start} → {end}"
                                f"  |  {job.get('work_status','?')}"
                                f"  |  Dispatched: {dispatched}"
                            )
                    else:
                        lines.append("   (no job appointments)")

                    event_ids = route.get("event_ids", [])
                    if event_ids:
                        lines.append(f"   Events: {len(event_ids)} calendar event(s)")

                return [types.TextContent(type="text", text="\n".join(lines))]

            # ── hcp_create_appointment ────────────────────────────────────────
            elif name == "hcp_create_appointment":
                payload: dict[str, Any] = {
                    "start_time": arguments["start_time"],
                    "end_time": arguments["end_time"],
                    "arrival_window_minutes": _as_int(arguments.get("arrival_window_minutes"), 0),
                }
                if emp_ids := _as_list(arguments.get("dispatched_employee_ids")):
                    payload["dispatched_employees_ids"] = emp_ids
                resp = await client.post(
                    f"/jobs/{arguments['job_id']}/appointments", json=payload
                )
                resp.raise_for_status()
                appt = resp.json()
                # Resolve names for confirmation
                emp_data = await _get(client, "/employees", {"page_size": 100})
                emp_map = {
                    e["id"]: (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
                    for e in emp_data.get("employees", [])
                }
                dispatched_ids = appt.get("dispatched_employees_ids", [])
                dispatched = ", ".join(emp_map.get(i, i) for i in dispatched_ids) or "—"
                return [types.TextContent(
                    type="text",
                    text=(
                        f"Appointment created  id: {appt.get('id','?')}\n"
                        f"  {appt.get('start_time','?')} → {appt.get('end_time','?')}\n"
                        f"  Dispatched: {dispatched}"
                    ),
                )]

            # ── hcp_update_appointment ────────────────────────────────────────
            elif name == "hcp_update_appointment":
                payload = {}
                if st := arguments.get("start_time"):
                    payload["start_time"] = st
                if et := arguments.get("end_time"):
                    payload["end_time"] = et
                if aw := arguments.get("arrival_window_minutes"):
                    payload["arrival_window_minutes"] = _as_int(aw, 0)
                if emp_ids := _as_list(arguments.get("dispatched_employee_ids")):
                    payload["dispatched_employees_ids"] = emp_ids
                resp = await client.put(
                    f"/jobs/{arguments['job_id']}/appointments/{arguments['appointment_id']}",
                    json=payload,
                )
                resp.raise_for_status()
                appt = resp.json()
                emp_data = await _get(client, "/employees", {"page_size": 100})
                emp_map = {
                    e["id"]: (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
                    for e in emp_data.get("employees", [])
                }
                dispatched_ids = appt.get("dispatched_employees_ids", [])
                dispatched = ", ".join(emp_map.get(i, i) for i in dispatched_ids) or "—"
                return [types.TextContent(
                    type="text",
                    text=(
                        f"Appointment updated  id: {appt.get('id','?')}\n"
                        f"  {appt.get('start_time','?')} → {appt.get('end_time','?')}\n"
                        f"  Dispatched: {dispatched}"
                    ),
                )]

            # ── hcp_delete_appointment ────────────────────────────────────────
            elif name == "hcp_delete_appointment":
                resp = await client.delete(
                    f"/jobs/{arguments['job_id']}/appointments/{arguments['appointment_id']}"
                )
                resp.raise_for_status()
                return [types.TextContent(
                    type="text",
                    text=f"Appointment {arguments['appointment_id']} deleted from job {arguments['job_id']}.",
                )]

            # ── hcp_list_events ───────────────────────────────────────────────
            elif name == "hcp_list_events":
                params = {
                    "page": _as_int(arguments.get("page"), 1),
                    "page_size": _as_int(arguments.get("page_size"), 50),
                    "sort_direction": arguments.get("sort_direction", "asc"),
                }
                data = await _get(client, "/events", params)
                events = data.get("events", [])
                total = data.get("total_items", len(events))
                lines = [f"Found {total} event(s).\n"]
                for ev in events:
                    schedule = ev.get("schedule") or {}
                    employees = ev.get("assigned_employees") or []
                    if isinstance(employees, dict):
                        employees = [employees]
                    emp_names = (
                        ", ".join(
                            (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
                            for e in employees
                        )
                        or "—"
                    )
                    lines.append(
                        f"• {ev.get('name','?')}"
                        f"  {schedule.get('start_time','?')} → {schedule.get('end_time','?')}"
                        f"  |  {emp_names}"
                        + ("  (all day)" if ev.get("all_day") else "")
                    )
                return [types.TextContent(type="text", text="\n".join(lines))]

            else:
                return _error(f"Unknown tool: {name}")

    except httpx.HTTPStatusError as e:
        return _error(f"HCP API {e.response.status_code}: {e.response.text[:500]}")
    except httpx.RequestError as e:
        return _error(f"Request failed: {e}")
    except Exception as e:
        return _error(f"Unexpected error: {e}")


# ── Entry point ────────────────────────────────────────────────────────────────

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
