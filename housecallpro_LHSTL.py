#!/usr/bin/env python3
"""
housecallpro_LHSTL.py — Local Handyman St. Louis custom MCP tools.

Rich, formatted output tailored for pre-week scheduling review, post-week
financial analysis, and day-to-day job management.  Wraps the raw HCP API
with business-specific defaults, tag parsing, crew summaries, and the
week-schedule capacity model.

Business constants are loaded from lhstl_config.json (one level up from this
file).  To add a tech, change capacity, or update pipeline stage IDs, edit
that file — no code changes required here.
"""

import asyncio
import json
import re
from datetime import date, timedelta, datetime as dt
from pathlib import Path
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from shared import api_request, BASE_URL, get_headers

mcp = FastMCP("Housecall Pro LHSTL")

# ── Load company config ────────────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).parent.parent / "lhstl_config.json"

def _load_config() -> dict:
    """Load lhstl_config.json.  Falls back to safe hardcoded defaults if missing."""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

_CFG = _load_config()

# ── Derive constants from config ───────────────────────────────────────────────

def _build_tech_sets(cfg: dict) -> tuple[frozenset, set]:
    """Return (active_field_tech_ids, half_time_ids) from config team list."""
    field_ids: set[str] = set()
    half_time: set[str] = set()
    for member in cfg.get("team", []):
        hcp_id = member.get("hcp_id")
        if not hcp_id or not member.get("field_tech"):
            continue
        field_ids.add(hcp_id)
        if member.get("capacity_multiplier", 1.0) < 1.0:
            half_time.add(hcp_id)
    return frozenset(field_ids), half_time

_ACTIVE_TECH_IDS, _HALF_TIME_IDS = _build_tech_sets(_CFG)

# Apprentice / half-time ID (used in tools that need to identify Ryan specifically)
_RYAN_ID = next(
    (m["hcp_id"] for m in _CFG.get("team", [])
     if m.get("role") == "apprentice" and m.get("hcp_id")),
    "pro_3dc62cf7dcba426d9e5701704753da70",  # fallback
)

# Scheduling constants
_SCHED_CFG        = _CFG.get("scheduling", {})
_HRS_PER_DAY      = float(_SCHED_CFG.get("productive_hours_per_day", 8.0))
_CAPACITY_TARGET  = float(_SCHED_CFG.get("capacity_target_hours_per_day", 44.0))
_OT_THRESHOLD     = float(_SCHED_CFG.get("overtime_threshold_hours_per_day", 40.0))

# ── Helpers ────────────────────────────────────────────────────────────────────

def _dollars(cents: int | None) -> str:
    if cents is None:
        return "$0.00"
    return f"${cents / 100:,.2f}"


def _as_int(val: Any, default: int) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _as_list(val: Any) -> list[str] | None:
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
    cats: dict[str, list[str]] = {
        "crew": [], "job": [], "scheduling": [], "materials": [], "tools": [], "other": []
    }
    for tag in tags:
        t = tag.upper()
        if t.startswith("CREW-"):
            cats["crew"].append(tag)
        elif t.startswith("JOB-"):
            cats["job"].append(tag)
        elif t.startswith("SCH-"):
            cats["scheduling"].append(tag)
        elif t.startswith("MAT-"):
            cats["materials"].append(tag)
        elif t.startswith("TOOL-"):
            cats["tools"].append(tag)
        else:
            cats["other"].append(tag)
    return cats


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


def _norm_status(s: str) -> str:
    """Normalize HCP status strings.  API returns 'in progress' (space) but
    filter params use 'in_progress' (underscore).  Normalise to underscore form."""
    return (s or "").lower().replace(" ", "_").replace("-", "_")


async def _get(client: httpx.AsyncClient, path: str, params: dict) -> Any:
    clean = {k: v for k, v in params.items() if v is not None}
    resp = await client.get(path, params=clean)
    resp.raise_for_status()
    return resp.json()


def _hcp_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE_URL, headers=get_headers(), timeout=30.0)


def _parse_hours(s: str, e: str, fallback: float = 8.0) -> float:
    """Return decimal hours between two ISO datetime strings.
    Returns *fallback* if either string is missing or unparseable."""
    try:
        s_dt = dt.fromisoformat(s.replace("Z", "+00:00"))
        e_dt = dt.fromisoformat(e.replace("Z", "+00:00"))
        return max(0.0, (e_dt - s_dt).total_seconds() / 3600)
    except Exception:
        return fallback


# ── SCH-tag priority constants (used by backlog + scheduler tools) ──────────────

# Lower number = higher urgency.  Untagged jobs sort last (key = 9).
_SCH_PRIORITY: dict[str, int] = {
    "SCH-URGENT": 0,
    "SCH-1W":     1,
    "SCH-2W":     2,
    "SCH-3W":     3,
    "SCH-4W":     4,
    "SCH-FLEX":   5,
    "SCH-MAT":    6,
    "SCH-TENT":   7,
    "SCH-TBD":    8,
}

_SCH_LABELS: dict[str, str] = {
    "SCH-URGENT": "URGENT",
    "SCH-1W":     "Schedule within 1 week",
    "SCH-2W":     "Schedule within 2 weeks",
    "SCH-3W":     "Schedule within 3 weeks",
    "SCH-4W":     "Schedule within 4 weeks",
    "SCH-FLEX":   "Flexible timing",
    "SCH-MAT":    "Awaiting materials",
    "SCH-TENT":   "Tentative (hold slot)",
    "SCH-TBD":    "TBD",
}


def _crew_size_from_tags(tags: list[str]) -> int:
    """Return integer crew size from CREW-* tags.  Default 2 when tag is missing."""
    for tag in tags:
        t = tag.upper()
        if t == "CREW-TBD":
            return 2
        m = re.match(r"CREW-(\d+)L(?:(\d+)A)?", t)
        if m:
            leads = int(m.group(1))
            apprentices = int(m.group(2)) if m.group(2) else 0
            return leads + apprentices
    return 2


def _sch_priority(tags: list[str]) -> int:
    """Return SCH sort key for a job's tag list.  Untagged → 9."""
    for tag in tags:
        p = _SCH_PRIORITY.get(tag.upper())
        if p is not None:
            return p
    return 9


def _days_since(iso_str: str) -> int:
    """Days elapsed since an ISO date/datetime string (based on today's date)."""
    try:
        return (date.today() - date.fromisoformat(iso_str[:10])).days
    except Exception:
        return 0


# ── Customers ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def hcp_list_customers(
    q: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    sort_by: Optional[str] = "created_at",
    sort_direction: Optional[str] = "desc",
) -> str:
    """
    Search or list customers.

    Args:
        q: Free-text search — name, email, phone, or address
        page: Page number (default 1)
        page_size: Results per page, max 100 (default 25)
        sort_by: Field to sort by (default: created_at)
        sort_direction: asc or desc (default: desc)
    """
    params: dict = {
        "page": _as_int(page, 1),
        "page_size": _as_int(page_size, 25),
        "sort_by": sort_by,
        "sort_direction": sort_direction,
    }
    if q:
        params["q"] = q
    data = await api_request("GET", "/customers", params=params)
    customers = data.get("customers", [])
    total = data.get("total_items", len(customers))
    return f"Found {total} customer(s). Page {params['page']}.\n\n{json.dumps(customers, indent=2)}"


@mcp.tool()
async def hcp_get_customer(customer_id: str) -> str:
    """
    Get full details for a single customer including lead source and all addresses.

    Args:
        customer_id: Customer UUID
    """
    data = await api_request("GET", f"/customers/{customer_id}")
    return json.dumps(data, indent=2)


@mcp.tool()
async def hcp_create_customer(
    first_name: str,
    last_name: str,
    email: Optional[str] = None,
    mobile_number: Optional[str] = None,
    home_number: Optional[str] = None,
    work_number: Optional[str] = None,
    company: Optional[str] = None,
    notifications_enabled: Optional[bool] = True,
    street: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip: Optional[str] = None,
) -> str:
    """
    Create a new customer in Housecall Pro.

    Args:
        first_name: First name (required)
        last_name: Last name (required)
        email: Email address
        mobile_number: Mobile phone — digits only e.g. 3145551234
        home_number: Home phone
        work_number: Work phone
        company: Company name
        notifications_enabled: Enable customer notifications (default True)
        street: Service address street
        city: Service address city
        state: State (2-letter code)
        zip: ZIP code
    """
    payload: dict = {
        "first_name": first_name,
        "last_name": last_name,
        "notifications_enabled": notifications_enabled,
    }
    for field in ("email", "company", "mobile_number", "home_number", "work_number"):
        val = locals()[field]
        if val:
            payload[field] = val
    address = {k: locals()[k] for k in ("street", "city", "state", "zip") if locals()[k]}
    if address:
        payload["addresses"] = [address]

    async with _hcp_client() as client:
        resp = await client.post("/customers", json=payload)
        resp.raise_for_status()
        return f"Customer created successfully!\n\n{json.dumps(resp.json(), indent=2)}"


# ── Jobs ───────────────────────────────────────────────────────────────────────

@mcp.tool()
async def hcp_list_jobs(
    scheduled_start_min: Optional[str] = None,
    scheduled_start_max: Optional[str] = None,
    scheduled_end_min: Optional[str] = None,
    scheduled_end_max: Optional[str] = None,
    work_status: Optional[str] = None,
    employee_ids: Optional[str] = None,
    customer_id: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_direction: Optional[str] = "asc",
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    expand: Optional[str] = None,
) -> str:
    """
    List jobs with tag parsing, financials, and crew summary.

    Args:
        scheduled_start_min: Jobs starting on or after (ISO 8601 e.g. 2026-04-21T00:00:00)
        scheduled_start_max: Jobs starting on or before (ISO 8601)
        scheduled_end_min: Jobs ending on or after (ISO 8601)
        scheduled_end_max: Jobs ending on or before (ISO 8601)
        work_status: Comma-separated: unscheduled, scheduled, in_progress, completed, canceled
        employee_ids: Comma-separated employee UUIDs
        customer_id: Filter by customer UUID
        sort_by: created_at | updated_at | invoice_number | work_status (default: created_at)
        sort_direction: asc or desc (default: asc)
        page: Page number (default 1)
        page_size: Results per page, max 100 (default 50)
        expand: Comma-separated: appointments, attachments
    """
    params: dict = {
        "page": _as_int(page, 1),
        "page_size": _as_int(page_size, 50),
        "sort_by": sort_by,
        "sort_direction": sort_direction,
    }
    for key in ("scheduled_start_min", "scheduled_start_max",
                "scheduled_end_min", "scheduled_end_max", "customer_id"):
        val = locals()[key]
        if val:
            params[key] = val
    if statuses := _as_list(work_status):
        params["work_status"] = statuses
    if emp_ids := _as_list(employee_ids):
        params["employee_ids"] = emp_ids
    if expand_list := _as_list(expand):
        params["expand"] = expand_list

    data = await api_request("GET", "/jobs", params=params)
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

        ps = job.get("pipeline_status")
        ps_part = f"  |  Pipeline: {ps}" if ps else ""
        lines.append(
            f"• [{job.get('invoice_number','?')}] {job.get('description','(no description)')}"
            + (" ⚑ FOLLOW-UP" if follow_up else "")
            + f"\n  Status: {job.get('work_status','?')}{ps_part}"
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
    return "\n".join(lines)


@mcp.tool()
async def hcp_get_job(job_id: str, expand: Optional[str] = None) -> str:
    """
    Get full details for a single job with timestamps, financials, and tag breakdown.

    Args:
        job_id: Job UUID
        expand: Comma-separated expansions: appointments, attachments
    """
    params: dict = {}
    if expand_list := _as_list(expand):
        params["expand"] = expand_list
    data = await api_request("GET", f"/jobs/{job_id}", params=params)

    tags = data.get("tags", [])
    tg = _parse_tags(tags)
    ts = data.get("work_timestamps") or {}
    schedule = data.get("schedule") or {}
    employees = data.get("assigned_employees", [])
    customer = data.get("customer") or {}
    address = data.get("address") or {}

    actual_note = ""
    if ts.get("started_at") and ts.get("completed_at"):
        try:
            start = dt.fromisoformat(ts["started_at"].replace("Z", "+00:00"))
            end = dt.fromisoformat(ts["completed_at"].replace("Z", "+00:00"))
            elapsed = (end - start).total_seconds() / 3600
            actual_note = f" (elapsed start→complete: {elapsed:.1f} hrs — includes any paused time)"
        except Exception:
            pass

    emp_line = ", ".join(
        (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
        for e in employees
    ) or "None"

    pipeline_status = data.get("pipeline_status")
    ps_line = f"  Pipeline stage: {pipeline_status}\n" if pipeline_status else ""

    summary = (
        f"Job: {data.get('description','(no description)')}\n"
        f"Invoice #: {data.get('invoice_number','?')}  |  ID: {data.get('id','')}\n"
        f"Status: {data.get('work_status','?')}\n"
        + ps_line
        +
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
    return summary


@mcp.tool()
async def hcp_get_job_line_items(job_id: str) -> str:
    """
    Get all line items for a job — services (labor) and materials with financials.
    Quantity on labor items = projected hours.

    Args:
        job_id: Job UUID
    """
    data = await api_request("GET", f"/jobs/{job_id}/line_items")
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

    return "\n".join(lines)


@mcp.tool()
async def hcp_get_job_invoice(job_id: str) -> str:
    """
    Get the invoice for a job — line items, taxes, discounts, and payment breakdown.

    Args:
        job_id: Job UUID
    """
    data = await api_request("GET", f"/jobs/{job_id}/invoices")
    if isinstance(data, list):
        invoices = data
    else:
        invoices = data.get("invoices", [data] if data.get("id") else [])
    if not invoices:
        return "No invoice found for this job."

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

    return "\n".join(lines)


@mcp.tool()
async def hcp_get_job_input_materials(job_id: str) -> str:
    """
    Get materials logged as job inputs (separate from invoice line items).

    Args:
        job_id: Job UUID
    """
    data = await api_request("GET", f"/jobs/{job_id}/job_input_materials")
    materials = data.get("job_input_materials", [])
    if not materials:
        return "No input materials logged for this job."
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
    return "\n".join(lines)


@mcp.tool()
async def hcp_get_job_appointments(job_id: str) -> str:
    """
    Get all scheduled appointment windows for a specific job, with tech names resolved.

    Args:
        job_id: Job UUID
    """
    async with _hcp_client() as client:
        emp_data, appt_data = await asyncio.gather(
            _get(client, "/employees", {"page_size": 100}),
            _get(client, f"/jobs/{job_id}/appointments", {}),
        )
    emp_map: dict[str, str] = {
        e["id"]: (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
        for e in emp_data.get("employees", [])
    }

    appts = appt_data.get("appointments", [])
    if not appts:
        return "No appointments found for this job."
    lines = [f"{len(appts)} appointment(s):\n"]
    for a in appts:
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
            f"  |  ID: {a.get('id','')}"
        )
    return "\n".join(lines)


@mcp.tool()
async def hcp_add_job_note(job_id: str, content: str) -> str:
    """
    Add a note to a job. Visible to office and field techs.

    Args:
        job_id: Job UUID
        content: Note text
    """
    async with _hcp_client() as client:
        resp = await client.post(f"/jobs/{job_id}/notes", json={"content": content})
        resp.raise_for_status()
    return f"Note added to job {job_id}."


# ── Employees ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def hcp_list_employees(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> str:
    """
    List all active employees/technicians with IDs, roles, and contact info.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 50)
    """
    params: dict = {
        "page": _as_int(page, 1),
        "page_size": _as_int(page_size, 50),
    }
    data = await api_request("GET", "/employees", params=params)
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
    return "\n".join(lines)


# ── Invoices ───────────────────────────────────────────────────────────────────

@mcp.tool()
async def hcp_list_invoices(
    status: Optional[str] = None,
    created_at_min: Optional[str] = None,
    created_at_max: Optional[str] = None,
    paid_at_min: Optional[str] = None,
    paid_at_max: Optional[str] = None,
    due_at_min: Optional[str] = None,
    due_at_max: Optional[str] = None,
    payment_method: Optional[str] = None,
    customer_uuid: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_direction: Optional[str] = "desc",
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> str:
    """
    List invoices with rich filtering. Core tool for post-week financial analysis.

    Args:
        status: Comma-separated: open, pending_payment, paid, voided, uncollectible, canceled
        created_at_min: ISO datetime e.g. 2026-04-21T00:00:00Z
        created_at_max: ISO datetime
        paid_at_min: ISO datetime
        paid_at_max: ISO datetime
        due_at_min: ISO datetime
        due_at_max: ISO datetime
        payment_method: Comma-separated: consumer_financing, credit_card, ach, external, mobile_check_deposit
        customer_uuid: Comma-separated customer UUIDs
        sort_by: amount | created_at | due_amount | due_at | invoice_number | paid_at | status | updated_at
        sort_direction: asc or desc (default: desc)
        page: Page number (default 1)
        page_size: Results per page, max 100 (default 50)
    """
    params: dict = {
        "page": _as_int(page, 1),
        "page_size": _as_int(page_size, 50),
        "sort_by": sort_by,
        "sort_direction": sort_direction,
    }
    for key in ("created_at_min", "created_at_max", "paid_at_min", "paid_at_max",
                "due_at_min", "due_at_max"):
        val = locals()[key]
        if val:
            params[key] = val
    if statuses := _as_list(status):
        params["status"] = statuses
    if methods := _as_list(payment_method):
        params["payment_method"] = methods
    if cuuids := _as_list(customer_uuid):
        params["customer_uuid"] = cuuids

    data = await api_request("GET", "/invoices", params=params)
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
    return "\n".join(lines)


@mcp.tool()
async def hcp_get_invoice(invoice_uuid: str) -> str:
    """
    Get full invoice detail by UUID — line items, taxes, discounts, and payment breakdown.

    Args:
        invoice_uuid: Invoice UUID
    """
    inv = await api_request("GET", f"/invoices/{invoice_uuid}")
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
    return "\n".join(lines)


# ── Estimates ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def hcp_list_estimates(
    scheduled_start_min: Optional[str] = None,
    scheduled_start_max: Optional[str] = None,
    scheduled_end_min: Optional[str] = None,
    scheduled_end_max: Optional[str] = None,
    work_status: Optional[str] = None,
    employee_ids: Optional[str] = None,
    customer_id: Optional[str] = None,
    sort_direction: Optional[str] = "desc",
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> str:
    """
    List estimates. Use for pipeline review and estimate-to-job conversion tracking.

    Args:
        scheduled_start_min: ISO 8601 datetime
        scheduled_start_max: ISO 8601 datetime
        scheduled_end_min: ISO 8601 datetime
        scheduled_end_max: ISO 8601 datetime
        work_status: Comma-separated statuses
        employee_ids: Comma-separated employee UUIDs
        customer_id: Customer UUID
        sort_direction: asc or desc (default: desc)
        page: Page number (default 1)
        page_size: Results per page (default 50)
    """
    params: dict = {
        "page": _as_int(page, 1),
        "page_size": _as_int(page_size, 50),
        "sort_direction": sort_direction,
    }
    for key in ("scheduled_start_min", "scheduled_start_max",
                "scheduled_end_min", "scheduled_end_max", "customer_id"):
        val = locals()[key]
        if val:
            params[key] = val
    if statuses := _as_list(work_status):
        params["work_status"] = statuses
    if emp_ids := _as_list(employee_ids):
        params["employee_ids"] = emp_ids

    data = await api_request("GET", "/estimates", params=params)
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
    return "\n".join(lines)


@mcp.tool()
async def hcp_get_estimate(estimate_id: str) -> str:
    """
    Get formatted details for a single estimate — options, status, customer, and notes.

    For the full estimating brief (customer notes, property details, all option notes,
    and existing line items formatted for Dan's workflow), use hcp_get_estimate_brief.

    Args:
        estimate_id: Estimate UUID
    """
    data = await api_request("GET", f"/estimates/{estimate_id}")
    customer  = data.get("customer") or {}
    address   = data.get("address") or {}
    schedule  = data.get("schedule") or {}
    employees = data.get("assigned_employees", [])
    options   = data.get("options", [])

    emp_line = ", ".join(
        (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
        for e in employees
    ) or "Unassigned"

    lines = [
        f"Estimate #{data.get('estimate_number','?')}  |  Status: {data.get('work_status','?')}",
        f"ID: {data.get('id','')}",
        f"Customer: {customer.get('first_name','')} {customer.get('last_name','')}",
        f"  Phone: {customer.get('mobile_number') or customer.get('home_number') or '—'}",
        f"  Email: {customer.get('email') or '—'}",
        f"  Lead source: {data.get('lead_source') or customer.get('lead_source') or '—'}",
        f"Address: {address.get('street','')} {address.get('city','')}, {address.get('state','')} {address.get('zip','')}",
        f"Assigned: {emp_line}",
        f"Scheduled: {schedule.get('start_time','—')} → {schedule.get('end_time','—')}",
        f"Created: {data.get('created_at','?')}",
        f"\n{len(options)} option(s):",
    ]
    for opt in options:
        tags_str  = ", ".join(opt.get("tags") or []) or "—"
        notes_str = f"  ({len(opt.get('notes') or [])} note(s))"
        lines.append(
            f"  • [{opt.get('option_number','?')}] {opt.get('name','?')}"
            f"  |  {_dollars(opt.get('total_amount'))}  |  {opt.get('approval_status','?')}"
            f"  |  Tags: {tags_str}{notes_str}"
            f"  |  id: {opt.get('id','')}"
        )
    return "\n".join(lines)


@mcp.tool()
async def hcp_get_estimate_brief(estimate_id: str) -> str:
    """
    Pull everything Dan needs before building an estimate — the full pre-estimating brief.

    Shows:
      • Estimate header (customer, property address, lead source, assigned tech)
      • Customer record (full contact info + customer-level notes)
      • All private/scope notes across all options, de-duplicated (shown once)

    Attachments are downloaded directly from HCP — not included here.

    Use this at the START of an estimating session. After Dan builds his numbers,
    use hcp_write_estimate to push everything back to HCP in one shot.

    Args:
        estimate_id: Estimate UUID (from hcp_list_estimates)
    """
    est_data = await api_request("GET", f"/estimates/{estimate_id}")

    customer_id = (est_data.get("customer") or {}).get("id")
    options     = est_data.get("options") or []

    # Fetch customer record in parallel (if available)
    async def _empty_dict():
        return {}

    cust_result = await asyncio.gather(
        api_request("GET", f"/customers/{customer_id}") if customer_id else _empty_dict(),
        return_exceptions=True,
    )
    cust_data = cust_result[0] if not isinstance(cust_result[0], Exception) else {}

    # ── Customer & property ────────────────────────────────────────────────────
    customer = est_data.get("customer") or {}
    address  = est_data.get("address") or {}
    schedule = est_data.get("schedule") or {}

    phone = (customer.get("mobile_number") or customer.get("home_number")
             or customer.get("work_number") or "—")
    email = customer.get("email") or "—"
    lead  = est_data.get("lead_source") or customer.get("lead_source") or "—"

    assigned = ", ".join(
        (e.get("first_name","") + " " + e.get("last_name","")).strip()
        for e in (est_data.get("assigned_employees") or [])
    ) or "Unassigned"

    lines = [
        f"╔══ ESTIMATE BRIEF ═══════════════════════════════════════",
        f"║  Estimate #:  {est_data.get('estimate_number','?')}",
        f"║  Status:      {est_data.get('work_status','?')}",
        f"║  ID:          {est_data.get('id','')}",
        f"║  Created:     {est_data.get('created_at','?')[:10]}",
        f"║  Assigned to: {assigned}",
        f"╠══ CUSTOMER ═════════════════════════════════════════════",
        f"║  Name:        {customer.get('first_name','')} {customer.get('last_name','')}",
        f"║  Phone:       {phone}",
        f"║  Email:       {email}",
        f"║  Lead source: {lead}",
        f"╠══ PROPERTY ═════════════════════════════════════════════",
        f"║  Address:     {address.get('street','')}",
        f"║               {address.get('city','')}, {address.get('state','')} {address.get('zip','')}",
    ]

    # Appointment window (if scheduled)
    if schedule.get("start_time"):
        lines.append(
            f"║  Appointment: {schedule['start_time'][:16].replace('T',' ')} "
            f"→ {(schedule.get('end_time') or '')[:16].replace('T',' ')}"
        )

    # Customer-level notes from the full customer record
    cust_notes_raw = (cust_data.get("notes") or []) if isinstance(cust_data, dict) else []
    if isinstance(cust_notes_raw, str):
        cust_notes_list = [cust_notes_raw] if cust_notes_raw.strip() else []
    else:
        cust_notes_list = [
            (n.get("content") or "").strip()
            for n in cust_notes_raw
            if (n.get("content") or "").strip()
        ]
    if cust_notes_list:
        lines.append(f"╠══ CUSTOMER RECORD NOTES ════════════════════════════════")
        for n in cust_notes_list:
            for ln in n.splitlines():
                lines.append(f"║  {ln}")

    # ── Deduplicated scope / private notes across all options ─────────────────
    # Collect all unique note contents — same note often appears on every option
    seen_note_ids:   set[str] = set()
    seen_note_text:  set[str] = set()
    unique_notes: list[str]   = []
    for opt in options:
        for n in (opt.get("notes") or []):
            nid      = n.get("id", "")
            content  = (n.get("content") or "").strip()
            key      = nid or content[:120]   # dedup by id first, then by content prefix
            if key and key not in seen_note_ids and content not in seen_note_text:
                seen_note_ids.add(key)
                seen_note_text.add(content)
                unique_notes.append(content)

    if unique_notes:
        lines.append(f"╠══ SITE NOTES ({len(unique_notes)} unique) ═══════════════════════════════")
        for idx, note_text in enumerate(unique_notes, 1):
            lines.append(f"║  [{idx}]")
            for ln in note_text.splitlines():
                lines.append(f"║  {ln}")
    else:
        lines.append(f"╠══ SITE NOTES ═══════════════════════════════════════════")
        lines.append(f"║  (no notes on this estimate)")

    # ── Options summary (names + IDs only, for reference when writing back) ───
    lines.append(f"╠══ OPTIONS (for hcp_write_estimate reference) ════════════")
    for opt in options:
        total = _dollars(opt.get("total_amount")) if opt.get("total_amount") else "no price yet"
        lines.append(f"║  [{opt.get('option_number','?')}] {opt.get('name','?')}  |  {total}")
        lines.append(f"║      id: {opt.get('id','')}")

    lines.append(f"╚{'═'*57}")
    lines.append(
        f"\nTo push numbers back: hcp_write_estimate(estimate_id, option_id, services=[...], materials=[...])"
    )
    return "\n".join(lines)


@mcp.tool()
async def hcp_write_estimate(
    estimate_id: str,
    services: list,
    option_id: Optional[str] = None,
    option_name: Optional[str] = None,
    materials: Optional[list] = None,
    note: Optional[str] = None,
    deposit_percent: Optional[float] = 25.0,
    tags: Optional[list] = None,
) -> str:
    """
    Write Dan's completed estimate back to HCP in one shot — replaces manual copy-paste.

    TWO MODES:
      • option_name provided  → CREATE a new option with that name + line items in one call
      • option_id provided    → UPDATE an existing option (replaces all its line items)

    Use option_name when starting fresh. Use option_id to revise an existing option.
    Get option IDs from hcp_get_estimate_brief.

    SERVICES — each item is a dict (prices in dollars, not cents):
      {
        "name":        "Open Stair and Landing Rail",
        "quantity":    26,          # labor hours
        "unit_price":  130.00,      # dollar rate per hour (customer price)
        "description": "Remove existing rail, install wood handrail with black metal spindles"
      }

    MATERIALS — each item is a dict (prices in dollars, not cents):
      {
        "name":        "Staircase hardware package",
        "quantity":    1,
        "unit_price":  1505.00,     # dollar amount customer is charged
        "unit_cost":   1105.00,     # dollar amount LHSTL pays (job costing)
        "description": "Newel post, balusters, handrail, hardware — Home Depot"
      }

    TAGS — list of tag name strings to add to the job when it converts:
      ["CREW-2L", "JOB-IN", "SCH-2W"]
      Note: Tags are recorded as a note since HCP has no estimate tag endpoint.

    DEPOSIT — auto-calculated from option total. Default is 25%. Written as a note
      since HCP does not expose a deposit field in the API. Set to 0 to skip.
      The actual deposit checkbox in HCP must still be set manually.

    Args:
        estimate_id:     Estimate UUID
        services:        List of service/labor dicts — prices in dollars
        option_id:       Option UUID — provide to UPDATE an existing option
        option_name:     Option name — provide to CREATE a new named option
        materials:       List of material dicts — prices in dollars, optional
        note:            Summary note to attach to the option, optional
        deposit_percent: Deposit percentage (default 25). Set to 0 to omit.
        tags:            Tag names to record in note (applied to job after conversion), optional
    """
    if not option_id and not option_name:
        return "❌ Provide either option_id (to update existing) or option_name (to create new)."

    services  = services or []
    materials = materials or []
    tags      = tags or []

    def _to_cents(val) -> int:
        """Convert dollar amount (float or int) to integer cents for HCP API."""
        return int(round(float(val or 0) * 100))

    # ── Build line items payload ───────────────────────────────────────────────
    line_items: list[dict] = []
    for s in services:
        item: dict = {
            "name":       s.get("name", ""),
            "kind":       "labor",
            "quantity":   s.get("quantity", 1),
            "unit_price": _to_cents(s.get("unit_price", 0)),
        }
        if s.get("description"):
            item["description"] = s["description"]
        line_items.append(item)

    for m in materials:
        item = {
            "name":       m.get("name", ""),
            "kind":       "materials",
            "quantity":   m.get("quantity", 1),
            "unit_price": _to_cents(m.get("unit_price", 0)),
        }
        if m.get("unit_cost"):
            item["unit_cost"] = _to_cents(m["unit_cost"])
        if m.get("description"):
            item["description"] = m["description"]
        line_items.append(item)

    if not line_items:
        return "❌ No services or materials provided. Nothing written."

    # ── CREATE new option or UPDATE existing ──────────────────────────────────
    if option_name:
        # Create option with name + line items in one API call
        result = await api_request(
            "POST",
            f"/estimates/{estimate_id}/options",
            json={"name": option_name, "line_items": line_items},
        )
        option_id    = result.get("id", "")
        total        = result.get("total_amount") or 0
        # Line items aren't echoed back on create — reconstruct from inputs for confirmation
        written      = line_items
        mode_str     = f"✓ New option created: \"{option_name}\""
    else:
        # Replace all line items on existing option
        li_result = await api_request(
            "PUT",
            f"/estimates/{estimate_id}/options/{option_id}/line_items/bulk_update",
            json={"line_items": line_items},
        )
        written  = li_result.get("data", li_result.get("line_items", []))
        total    = sum((i.get("amount") or 0) for i in written)
        mode_str = f"✓ Option updated  (id: {option_id})"

    # ── Compute option total in cents (works for both modes) ─────────────────
    calc_total = sum(
        int(i.get("unit_price", 0)) * float(i.get("quantity", 1))
        for i in line_items
    )

    # ── Calculate deposit from option total ───────────────────────────────────
    deposit_str = ""
    if deposit_percent and deposit_percent > 0:
        deposit_amt = calc_total * (deposit_percent / 100) / 100  # calc_total in cents → dollars
        deposit_str = f"{deposit_percent:.0f}% deposit due before work begins: ${deposit_amt:,.2f}"

    # ── Build and write combined note ─────────────────────────────────────────
    note_parts: list[str] = []
    if note:
        note_parts.append(note.strip())
    if deposit_str:
        note_parts.append(f"DEPOSIT: {deposit_str}")
    if tags:
        note_parts.append(f"TAGS FOR JOB: {', '.join(tags)}")

    note_result = ""
    if note_parts and option_id:
        full_note = "\n\n".join(note_parts)
        note_resp = await api_request(
            "POST",
            f"/estimates/{estimate_id}/options/{option_id}/notes",
            json={"content": full_note},
        )
        note_result = f"✓ Note written (id: {note_resp.get('id', '')})"

    # ── Format confirmation output ─────────────────────────────────────────────
    # For created options, written = raw input dicts (unit_price in cents already)
    # For updated options, written = API response dicts
    # Use line_items for display in both modes (consistent, no API echo needed)
    labor_items = [i for i in line_items if i.get("kind") == "labor"]
    mats_items  = [i for i in line_items if i.get("kind") == "materials"]
    proj_hrs    = sum((i.get("quantity") or 0) for i in labor_items)
    total_str   = _dollars(int(calc_total))

    out = [
        mode_str,
        f"  Option id:       {option_id}",
        f"  Line items:      {len(line_items)}",
        f"  Total:           {total_str}",
        f"  Deposit ({deposit_percent:.0f}%):    ${calc_total * (deposit_percent or 0) / 100 / 100:,.2f}" if deposit_percent else f"  Deposit:         none",
        f"  Projected hours: {proj_hrs:.1f}h",
        "",
    ]

    out.append("SERVICES:")
    for i in labor_items:
        price = i.get("unit_price", 0)
        qty   = float(i.get("quantity", 1))
        out.append(
            f"  • {i.get('name','')}  {qty:.0f} hrs @ {_dollars(price)} = {_dollars(int(price * qty))}"
        )
        if i.get("description"):
            out.append(f"    {i['description'][:100]}")

    if mats_items:
        out.append("\nMATERIALS:")
        for i in mats_items:
            price = i.get("unit_price", 0)
            qty   = float(i.get("quantity", 1))
            cost  = i.get("unit_cost")
            out.append(
                f"  • {i.get('name','')}  qty: {qty:.0f} @ {_dollars(price)}"
                + (f"  cost: {_dollars(cost)}" if cost else "")
                + f" = {_dollars(int(price * qty))}"
            )
            if i.get("description"):
                out.append(f"    {i['description'][:120]}")

    if note_result:
        out.append(f"\n{note_result}")
    if tags:
        out.append(
            f"\n⚠ Tags {tags} recorded in note — apply to the JOB in HCP after customer approval."
        )
    out.append(
        f"\nNext: review in HCP → hcp_approve_estimate_option('{option_id}')"
    )
    return "\n".join(out)


@mcp.tool()
async def hcp_upload_estimate_pdf(
    estimate_id: str,
    option_id: str,
    file_path: str,
) -> str:
    """
    Upload a PDF (or any file) to an estimate option as an attachment.

    The file appears in the estimate in HCP and is visible to the customer
    when the estimate is sent for approval.

    Common uses:
      • Attach Dan's detailed scope/measurement PDF
      • Attach a material spec sheet
      • Attach a reference photo or drawing

    Args:
        estimate_id: Estimate UUID
        option_id:   Estimate option UUID
        file_path:   Absolute path to the file on this machine
                     (e.g. /Users/nikki_zav/Documents/estimates/kokoski_scope.pdf)
    """
    from pathlib import Path as _Path
    import mimetypes

    p = _Path(file_path)
    if not p.exists():
        return f"❌ File not found: {file_path}"
    if not p.is_file():
        return f"❌ Path is not a file: {file_path}"

    mime_type, _ = mimetypes.guess_type(str(p))
    mime_type = mime_type or "application/octet-stream"

    url     = f"{BASE_URL}/estimates/{estimate_id}/options/{option_id}/attachments"
    headers = get_headers()
    # Remove Content-Type — httpx sets it automatically with the correct multipart boundary
    headers.pop("Content-Type", None)

    async with httpx.AsyncClient(timeout=60.0) as client:
        with open(p, "rb") as fh:
            resp = await client.post(
                url,
                headers=headers,
                files={"file": (p.name, fh, mime_type)},
            )
        resp.raise_for_status()
        result = resp.json()

    estimate_url = result.get("estimate_url", "")
    return (
        f"✓ '{p.name}' uploaded to estimate option.\n"
        + (f"  Estimate URL: {estimate_url}" if estimate_url else "")
    )


# ── Lead Sources ───────────────────────────────────────────────────────────────

@mcp.tool()
async def hcp_list_lead_sources(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> str:
    """
    List all configured lead sources with IDs.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 100)
    """
    params: dict = {
        "page": _as_int(page, 1),
        "page_size": _as_int(page_size, 100),
    }
    data = await api_request("GET", "/lead_sources", params=params)
    sources = data.get("lead_sources", data if isinstance(data, list) else [])
    lines = [f"{len(sources)} lead source(s):\n"]
    for s in sources:
        editable = "editable" if s.get("editable") else "read-only"
        lines.append(f"  • {s.get('name','')}  [{editable}]  id: {s.get('id','')}")
    return "\n".join(lines)


# ── Tags ───────────────────────────────────────────────────────────────────────

@mcp.tool()
async def hcp_list_tags(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> str:
    """
    List all tags configured in Housecall Pro, grouped by prefix.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 100)
    """
    params: dict = {
        "page": _as_int(page, 1),
        "page_size": _as_int(page_size, 100),
    }
    data = await api_request("GET", "/tags", params=params)
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
    return "\n".join(lines)


@mcp.tool()
async def hcp_create_tag(name: str) -> str:
    """
    Create a new tag in Housecall Pro.

    Args:
        name: Tag name e.g. SCH-FOLLOWUP, CREW-2L1A, TOOL-SCAFF
    """
    async with _hcp_client() as client:
        resp = await client.post("/tags", json={"name": name})
        resp.raise_for_status()
        tag = resp.json()
    return f"Tag created: {tag.get('name','')}  id: {tag.get('id','')}"


@mcp.tool()
async def hcp_update_tag(tag_id: str, name: str) -> str:
    """
    Rename an existing tag.

    Args:
        tag_id: Tag UUID (from hcp_list_tags)
        name: New tag name
    """
    async with _hcp_client() as client:
        resp = await client.put(f"/tags/{tag_id}", json={"name": name})
        resp.raise_for_status()
        tag = resp.json()
    return f"Tag updated: {tag.get('name','')}  id: {tag.get('id','')}"


@mcp.tool()
async def hcp_add_job_tag(job_id: str, tag_id: str) -> str:
    """
    Add a tag to a job. Use hcp_list_tags to get the tag_id.

    Args:
        job_id: Job UUID
        tag_id: Tag UUID
    """
    async with _hcp_client() as client:
        resp = await client.post(f"/jobs/{job_id}/tags", json={"tag_id": tag_id})
        resp.raise_for_status()
        result = resp.json()
    tags_now = [t.get("name", "") for t in result.get("tags", [])]
    return f"Tag added. Job now has tags: {', '.join(tags_now) or '(none)'}"


@mcp.tool()
async def hcp_remove_job_tag(job_id: str, tag_id: str) -> str:
    """
    Remove a tag from a job.

    Args:
        job_id: Job UUID
        tag_id: Tag UUID
    """
    async with _hcp_client() as client:
        resp = await client.delete(f"/jobs/{job_id}/tags/{tag_id}")
        resp.raise_for_status()
        result = resp.json()
    tags_now = [t.get("name", "") for t in result.get("tags", [])]
    return f"Tag removed. Job now has tags: {', '.join(tags_now) or '(none)'}"


# ── Appointments (job-level) ───────────────────────────────────────────────────

@mcp.tool()
async def hcp_create_appointment(
    job_id: str,
    start_time: str,
    end_time: str,
    arrival_window_minutes: Optional[int] = None,
    dispatched_employee_ids: Optional[str] = None,
) -> str:
    """
    Add a new appointment to an existing job.

    Args:
        job_id: Job UUID
        start_time: ISO 8601 datetime e.g. 2026-04-28T07:30:00
        end_time: ISO 8601 datetime e.g. 2026-04-28T16:00:00
        arrival_window_minutes: Arrival window in minutes (default 0)
        dispatched_employee_ids: Comma-separated employee UUIDs to dispatch
    """
    payload: dict = {
        "start_time": start_time,
        "end_time": end_time,
        "arrival_window_minutes": _as_int(arrival_window_minutes, 0),
    }
    if emp_ids := _as_list(dispatched_employee_ids):
        payload["dispatched_employees_ids"] = emp_ids

    async with _hcp_client() as client:
        resp = await client.post(f"/jobs/{job_id}/appointments", json=payload)
        resp.raise_for_status()
        appt = resp.json()
        emp_data = await _get(client, "/employees", {"page_size": 100})

    emp_map = {
        e["id"]: (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
        for e in emp_data.get("employees", [])
    }
    dispatched_ids = appt.get("dispatched_employees_ids", [])
    dispatched = ", ".join(emp_map.get(i, i) for i in dispatched_ids) or "—"
    return (
        f"Appointment created  id: {appt.get('id','?')}\n"
        f"  {appt.get('start_time','?')} → {appt.get('end_time','?')}\n"
        f"  Dispatched: {dispatched}"
    )


@mcp.tool()
async def hcp_update_appointment(
    job_id: str,
    appointment_id: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    arrival_window_minutes: Optional[int] = None,
    dispatched_employee_ids: Optional[str] = None,
) -> str:
    """
    Update an existing appointment.

    Args:
        job_id: Job UUID
        appointment_id: Appointment UUID (from hcp_get_job_appointments)
        start_time: New start time (ISO 8601)
        end_time: New end time (ISO 8601)
        arrival_window_minutes: New arrival window in minutes
        dispatched_employee_ids: Comma-separated employee UUIDs — replaces current list
    """
    payload: dict = {}
    if start_time:
        payload["start_time"] = start_time
    if end_time:
        payload["end_time"] = end_time
    if arrival_window_minutes is not None:
        payload["arrival_window_minutes"] = _as_int(arrival_window_minutes, 0)
    if emp_ids := _as_list(dispatched_employee_ids):
        payload["dispatched_employees_ids"] = emp_ids

    async with _hcp_client() as client:
        resp = await client.put(
            f"/jobs/{job_id}/appointments/{appointment_id}", json=payload
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
    return (
        f"Appointment updated  id: {appt.get('id','?')}\n"
        f"  {appt.get('start_time','?')} → {appt.get('end_time','?')}\n"
        f"  Dispatched: {dispatched}"
    )


@mcp.tool()
async def hcp_delete_appointment(job_id: str, appointment_id: str) -> str:
    """
    Delete an appointment from a job. Cannot be undone — confirm before calling.

    Args:
        job_id: Job UUID
        appointment_id: Appointment UUID
    """
    async with _hcp_client() as client:
        resp = await client.delete(f"/jobs/{job_id}/appointments/{appointment_id}")
        resp.raise_for_status()
    return f"Appointment {appointment_id} deleted from job {job_id}."


# ── Events ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def hcp_list_events(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    sort_direction: Optional[str] = "asc",
) -> str:
    """
    List non-job calendar events (time off, meetings, internal schedule blocks).
    Important for full schedule visibility during pre-week planning.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 50)
        sort_direction: asc or desc (default: asc)
    """
    params: dict = {
        "page": _as_int(page, 1),
        "page_size": _as_int(page_size, 50),
        "sort_direction": sort_direction,
    }
    data = await api_request("GET", "/events", params=params)
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
    return "\n".join(lines)


# ── Routes ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def hcp_get_routes(
    date: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> str:
    """
    Get dispatch routes for a specific date.

    NOTE: Requires HCP Routes feature to be configured in the dispatch board.
    Returns empty if your team does not use named routes.
    Use hcp_get_week_schedule for schedule analysis instead.

    Args:
        date: Date to query (YYYY-MM-DD, defaults to today)
        page: Page number (default 1)
        page_size: Routes per page (default 50)
    """
    params: dict = {
        "page": _as_int(page, 1),
        "per_page": _as_int(page_size, 50),
    }
    if date:
        params["date"] = date

    async with _hcp_client() as client:
        emp_data = await _get(client, "/employees", {"page_size": 100})
        emp_map: dict[str, str] = {
            e["id"]: (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
            for e in emp_data.get("employees", [])
        }
        route_data = await _get(client, "/routes", params)

    routes = route_data.get("routes", [])
    total = route_data.get("total_items", len(routes))
    query_date = date or "today"

    if not routes:
        return f"No routes found for {query_date}."

    lines = [f"Routes for {query_date} — {total} route(s):\n"]
    for route in routes:
        emp_ids = route.get("employee_ids", [])
        emp_names = ", ".join(emp_map.get(i, i) for i in emp_ids) or "Unassigned"
        lines.append(f"\n▸ {route.get('name', '?')}  ({emp_names})")

        appts = route.get("job_appointments", [])
        if appts:
            for a in appts:
                job = a.get("job") or {}
                dispatched_ids = a.get("dispatched_employees_ids", [])
                dispatched = ", ".join(emp_map.get(i, i) for i in dispatched_ids) or "—"
                lines.append(
                    f"   • [{job.get('invoice_number','?')}] {job.get('description','?')}"
                    f"  {a.get('start_time','?')} → {a.get('end_time','?')}"
                    f"  |  {job.get('work_status','?')}"
                    f"  |  Dispatched: {dispatched}"
                )
        else:
            lines.append("   (no job appointments)")

        if event_ids := route.get("event_ids", []):
            lines.append(f"   Events: {len(event_ids)} calendar event(s)")

    return "\n".join(lines)


# ── Week Schedule ──────────────────────────────────────────────────────────────

@mcp.tool()
async def hcp_get_week_schedule(
    week_start: Optional[str] = None,
    full_time_count: Optional[int] = None,
    hours_per_day: Optional[int] = None,
    half_time_employee_ids: Optional[str] = None,
) -> str:
    """
    Build the full schedule for a work week.

    Pulls appointments across all active (scheduled + in_progress) jobs,
    groups by day and technician, shows hours vs capacity with open gaps and
    conflict flags.

    Team defaults come from lhstl_config.json:
      • Full-time techs each contribute _HRS_PER_DAY to capacity.
      • Half-time employees (Ryan) count 0.5× toward team capacity math only —
        they still work full days and can be booked without an overbook flag.
      • Total daily capacity = sum(multiplier × hrs_per_day) across all field techs.

    Args:
        week_start: Monday of the week (YYYY-MM-DD). Any weekday input is snapped
                    to that week's Monday. Defaults to current week.
        full_time_count: Number of full-time techs (default: from config)
        hours_per_day: Productive hrs/day per full-time tech (default: from config)
        half_time_employee_ids: Comma-separated employee IDs who count at 0.5×
                                capacity (default: from config — Ryan Bianucci)
    """
    # ── Parse week_start → always Monday ────────────────────────────────────────
    if week_start:
        anchor = date.fromisoformat(week_start)
    else:
        anchor = date.today()
    week_monday = anchor - timedelta(days=anchor.weekday())
    weekdays = [week_monday + timedelta(days=i) for i in range(5)]
    week_end = weekdays[-1]

    # ── Capacity config — defaults from lhstl_config.json ───────────────────────
    ft_count = _as_int(full_time_count, sum(
        1 for m in _CFG.get("team", [])
        if m.get("field_tech") and m.get("capacity_multiplier", 1.0) >= 1.0
    ) or 5)
    hrs_per_day = float(hours_per_day) if hours_per_day else _HRS_PER_DAY
    ht_ids = set(_as_list(half_time_employee_ids) or []) or set(_HALF_TIME_IDS) or {_RYAN_ID}

    # ── Parallel API fetches ─────────────────────────────────────────────────────
    # Two job queries are needed:
    #   A) Date-filtered: catches scheduled jobs with a primary schedule date set.
    #   B) Recently-updated: catches in_progress jobs whose schedule.start_time
    #      is null (scheduled via appointments only).
    # We do NOT pass work_status to the API — it causes 400 errors in some
    # configurations.  Filter client-side with _norm_status() instead.
    look_back = week_monday - timedelta(days=60)
    date_params: dict = {
        "page_size": 100,
        "scheduled_start_min": f"{look_back.isoformat()}T00:00:00",
        "scheduled_start_max": f"{week_end.isoformat()}T23:59:59",
        "sort_by": "updated_at",
        "sort_direction": "desc",
    }
    recent_params: dict = {
        "page_size": 100,
        "sort_by": "updated_at",
        "sort_direction": "desc",
    }

    async with _hcp_client() as client:
        emp_data, d1, d2, r1, r2 = await asyncio.gather(
            _get(client, "/employees", {"page_size": 100}),
            _get(client, "/jobs", {**date_params, "page": 1}),
            _get(client, "/jobs", {**date_params, "page": 2}),
            _get(client, "/jobs", {**recent_params, "page": 1}),
            _get(client, "/jobs", {**recent_params, "page": 2}),
        )

        # Only include active field techs — excludes admin/office accounts
        emp_map: dict[str, str] = {
            e["id"]: (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
            for e in emp_data.get("employees", [])
            if e["id"] in _ACTIVE_TECH_IDS
        }

        # Merge + dedup, keep only scheduled / in_progress
        seen_ids: set[str] = set()
        active: list[dict] = []
        for j in (
            r1.get("jobs", []) + r2.get("jobs", [])    # recent first (catches in_progress)
            + d1.get("jobs", []) + d2.get("jobs", [])   # then date-filtered
        ):
            if _norm_status(j.get("work_status", "")) not in ("scheduled", "in_progress"):
                continue
            jid = j.get("id")
            if jid and jid not in seen_ids:
                seen_ids.add(jid)
                active.append(j)

        # Parallel fetch appointments for every active job
        appt_lists = await asyncio.gather(*[
            _get(client, f"/jobs/{j['id']}/appointments", {})
            for j in active
        ])

    # ── Aggregate: day → tech → [(hours, label)] ─────────────────────────────────
    day_map: dict[str, dict] = {d.isoformat(): {} for d in weekdays}

    for job, resp in zip(active, appt_lists):
        customer = job.get("customer") or {}
        cust_name = (
            f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
            or (job.get("description") or "")[:22]
        )
        label = f"#{job.get('invoice_number','?')} {cust_name}"
        job_assigned_ids = [e["id"] for e in (job.get("assigned_employees") or []) if e.get("id")]

        for appt in resp.get("appointments", []):
            appt_start_str = appt.get("start_time") or ""
            appt_end_str = appt.get("end_time") or ""
            if not appt_start_str:
                continue

            try:
                appt_s = date.fromisoformat(appt_start_str[:10])
                appt_e = date.fromisoformat(appt_end_str[:10]) if appt_end_str else appt_s
            except ValueError:
                continue

            covered = [d for d in weekdays if appt_s <= d <= appt_e]
            if not covered:
                continue

            total_span_days = max(1, (appt_e - appt_s).days + 1)
            daily_hrs = (
                _parse_hours(appt_start_str, appt_end_str, fallback=float(hrs_per_day))
                if total_span_days == 1
                else float(hrs_per_day)
            )

            dispatched = appt.get("dispatched_employees_ids") or []
            if not dispatched:
                dispatched = job_assigned_ids  # job-level fallback

            for target_day in covered:
                d_str = target_day.isoformat()
                if not dispatched:
                    day_map[d_str].setdefault(None, []).append((daily_hrs, label))
                else:
                    for tid in dispatched:
                        day_map[d_str].setdefault(tid, []).append((daily_hrs, label))

    # ── Build output ──────────────────────────────────────────────────────────────
    _DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_names = [_DAY_ABBR[d.weekday()] for d in weekdays]

    lines: list[str] = [
        f"Week of {week_monday.strftime('%b %d, %Y')} — schedule vs capacity\n"
    ]

    week_sched = 0.0
    week_cap = 0.0
    day_summaries: list[str] = []
    conflicts: list[str] = []

    for day_date, day_name in zip(weekdays, day_names):
        d_str = day_date.isoformat()
        tech_data = day_map[d_str]

        tech_hours: dict[str, float] = {}
        unassigned_hrs = 0.0
        for tid, entries in tech_data.items():
            hrs_sum = sum(h for h, _ in entries)
            if tid is None:
                unassigned_hrs += hrs_sum
            else:
                tech_hours[tid] = tech_hours.get(tid, 0.0) + hrs_sum

        # Capacity = FT portion + half-time portion at 0.5×
        cap = ft_count * hrs_per_day + len(ht_ids) * hrs_per_day * 0.5
        sched = sum(tech_hours.values()) + unassigned_hrs
        week_sched += sched
        week_cap += cap
        open_hrs = max(0.0, cap - sched)

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
            for tid, hrs in sorted(tech_hours.items(), key=lambda x: emp_map.get(x[0], x[0])):
                name = emp_map.get(tid, tid)
                ht_marker = " (0.5×)" if tid in ht_ids else ""
                jobs_today = [lbl for _, lbl in tech_data.get(tid, [])]
                job_str = " · ".join(dict.fromkeys(jobs_today))  # dedupe, preserve order
                # Overbook check: everyone gets the same threshold — Ryan works full days;
                # the 0.5× only affects team capacity contribution, not his personal limit.
                tech_cap_hrs = float(hrs_per_day)
                tolerance = 1.0
                if hrs > tech_cap_hrs + tolerance:
                    flag = " ⚠ OVERBOOKED"
                    conflicts.append(
                        f"  {day_name} {day_date.strftime('%b %d')}: "
                        f"{name} has {hrs:.1f} hrs scheduled "
                        f"(>{tech_cap_hrs:.0f} hr day) — {job_str}"
                    )
                else:
                    flag = ""
                day_lines.append(f"  {name}{ht_marker}: {hrs:.1f} hrs  — {job_str}{flag}")

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

    return "\n".join(lines)


# ── Job backlog (unscheduled jobs) ────────────────────────────────────────────

@mcp.tool()
async def hcp_job_backlog(
    max_jobs: Optional[int] = 100,
) -> str:
    """
    View all unscheduled jobs as a prioritized backlog.

    For each job shows: customer name, job number, description, projected
    manhours (from labor line items), predicted crew size (from CREW tag or
    default 2), estimated days-to-complete, SCH urgency tag, MAT and TOOL
    tags, and how long ago the job was created.

    Jobs tagged SCH-FOLLOWUP are shown in a separate section at the bottom
    (needs a return call before scheduling).

    Sort order: URGENT → 1W → 2W → 3W → 4W → FLEX → MAT → TENT → TBD → untagged

    Args:
        max_jobs: Max jobs to scan (default 100).  Fetches up to 2 pages of 100.
    """
    page_size = 100
    pages_needed = 2 if (max_jobs or 100) > 100 else 1

    async with _hcp_client() as client:
        page_results = await asyncio.gather(*[
            _get(client, "/jobs", {
                "page": p + 1,
                "page_size": page_size,
                "sort_by": "invoice_number",
                "sort_direction": "desc",
            })
            for p in range(pages_needed)
        ])

    # Flatten + dedup
    seen_ids: set[str] = set()
    all_jobs: list[dict] = []
    for r in page_results:
        for j in r.get("jobs", []):
            jid = j.get("id")
            if jid and jid not in seen_ids:
                seen_ids.add(jid)
                all_jobs.append(j)

    # Filter to jobs not yet on the calendar.
    # HCP returns work_status "needs scheduling" (normalized: "needs_scheduling")
    # for pipeline jobs with no appointment.  Also catch legacy "unscheduled".
    #
    # Planning-phase exception: some jobs (e.g. "schedule a measurement visit")
    # have a preliminary appointment which promotes them to work_status="scheduled",
    # but the actual construction work hasn't started.  We include those here if
    # they carry a SCH-TENT tag — that tag signals "holding a slot pending
    # permit / customer approval / detailed scoping."
    _NEEDS_SCHED = {"unscheduled", "needs_scheduling"}

    def _is_planning_phase(j: dict) -> bool:
        """True if the job is 'scheduled' but only has a planning/measurement appointment."""
        if _norm_status(j.get("work_status", "")) != "scheduled":
            return False
        tags_raw = [
            t.get("name", "") if isinstance(t, dict) else str(t)
            for t in (j.get("tags") or [])
        ]
        return "SCH-TENT" in [t.upper() for t in tags_raw]

    unscheduled = [
        j for j in all_jobs
        if _norm_status(j.get("work_status", "")) in _NEEDS_SCHED
        or _is_planning_phase(j)
    ]

    if not unscheduled:
        return (
            "No unscheduled jobs found in the current page of results.\n"
            "Try increasing max_jobs or check HCP for jobs in 'unscheduled' status."
        )

    # Parallel fetch line items. API returns {"object":"list","data":[...],"url":"..."}.
    li_results = await asyncio.gather(*[
        api_request("GET", f"/jobs/{j['id']}/line_items")
        for j in unscheduled
    ])

    # Build enriched entries
    followup_jobs: list[dict] = []
    backlog_jobs: list[dict] = []

    for job, li_data in zip(unscheduled, li_results):
        tags_raw = [
            t.get("name", "") if isinstance(t, dict) else str(t)
            for t in (job.get("tags") or [])
        ]
        tags_upper = [t.upper() for t in tags_raw]

        tag_cats   = _parse_tags(tags_raw)
        crew_tags  = tag_cats["crew"]
        sch_tags   = tag_cats["scheduling"]
        mat_tags   = tag_cats["materials"]
        tool_tags  = tag_cats["tools"]

        is_followup = "SCH-FOLLOWUP" in tags_upper

        # Manhours = sum of labor line item quantities.
        # API returns {"object":"list","data":[...],"url":"..."} — items under "data".
        line_items   = li_data.get("data", [])
        labor_items  = [i for i in line_items if i.get("kind") == "labor"]
        manhours     = sum((i.get("quantity") or 0) for i in labor_items)

        # Crew prediction — 8.0 productive hrs/day
        crew_size = _crew_size_from_tags(tags_raw)
        days_est  = (manhours / (crew_size * _HRS_PER_DAY)) if manhours > 0 else 0.0

        # Job title: use first line of labor item description when name is generic
        job_title = (job.get("description") or "").strip()
        if labor_items:
            svc_name = (labor_items[0].get("name") or "").strip()
            svc_desc = (labor_items[0].get("description") or "").strip()
            first_desc_line = svc_desc.split("\n")[0].strip() if svc_desc else ""
            # Use the description's first line if the service name is a placeholder
            generic = {"scope of work", "scope of work.", "services", "labor"}
            if svc_name.lower() in generic and first_desc_line:
                job_title = first_desc_line
            elif svc_name and svc_name.lower() not in generic:
                job_title = svc_name

        customer  = job.get("customer") or {}
        cust_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
        if not cust_name:
            cust_name = customer.get("company", "Unknown")

        job_total = _as_int(job.get("total_amount"), 0)

        entry = {
            "job":             job,
            "cust_name":       cust_name,
            "job_title":       job_title,
            "job_total":       job_total,
            "sch_tags":        sch_tags,
            "crew_tags":       crew_tags,
            "mat_tags":        mat_tags,
            "tool_tags":       tool_tags,
            "manhours":        manhours,
            "crew_size":       crew_size,
            "days_est":        days_est,
            "is_followup":     is_followup,
            "is_planning":     _is_planning_phase(job),
            "pipeline_status": job.get("pipeline_status") or "",
            "priority":        _sch_priority(tags_raw),
            "created_at":      job.get("created_at", ""),
        }

        if is_followup:
            followup_jobs.append(entry)
        else:
            backlog_jobs.append(entry)

    backlog_jobs.sort(key=lambda x: x["priority"])

    # ── Output ────────────────────────────────────────────────────────────────
    total_mh        = sum(e["manhours"] for e in backlog_jobs)
    weeks_of_backlog = total_mh / 220.0  # 44 effective hrs/day × 5 days/wk

    lines: list[str] = [
        f"JOB BACKLOG — {len(backlog_jobs)} unscheduled job(s)",
        f"Total manhours: {total_mh:.1f} hrs  |  Estimated backlog: ~{weeks_of_backlog:.1f} weeks at full capacity",
        f"{'═'*60}",
    ]

    current_priority = -1
    for e in backlog_jobs:
        p = e["priority"]
        if p != current_priority:
            current_priority = p
            # Find the SCH tag responsible for this priority bucket
            sch_tag_key = next(
                (t.upper() for t in e["sch_tags"] if t.upper() in _SCH_PRIORITY),
                None,
            )
            section_label = _SCH_LABELS.get(sch_tag_key, "No SCH tag") if sch_tag_key else "No SCH tag"
            lines.append(f"\n── {section_label.upper()} ──")

        job          = e["job"]
        inv_num      = job.get("invoice_number", "?")
        created_days = _days_since(e["created_at"])
        city         = (job.get("address") or {}).get("city", "")
        total_str    = _dollars(e["job_total"]) if e["job_total"] else ""

        if e["manhours"] > 0:
            crew_label  = _crew_summary(e["crew_tags"]) if e["crew_tags"] else f"~{e['crew_size']} crew (default)"
            no_crew_tag = " ⚠ no CREW tag" if not e["crew_tags"] else ""
            hrs_line    = (
                f"{e['manhours']:.0f} manhrs → {crew_label}{no_crew_tag}"
                f"  ~{e['days_est']:.1f} day(s)"
            )
        else:
            hrs_line = "⚠ No line items on record — add scope to job in HCP"

        # Tags line — SCH | CREW | MAT | TOOL
        tag_parts: list[str] = []
        sch_display  = ", ".join(e["sch_tags"]) if e["sch_tags"] else "⚠ no SCH tag"
        crew_display = ", ".join(e["crew_tags"]) if e["crew_tags"] else "⚠ no CREW tag"
        tag_parts.append("SCH: "  + sch_display)
        tag_parts.append("CREW: " + crew_display)
        if e["mat_tags"]:
            tag_parts.append("MAT: " + ", ".join(e["mat_tags"]))
        if e["tool_tags"]:
            tag_parts.append("TOOL: " + ", ".join(e["tool_tags"]))
        tags_line = "  |  ".join(tag_parts)

        planning_note = "  📐 PLANNING PHASE (measurement/permitting appt scheduled)" if e["is_planning"] else ""
        header = f"\n#{inv_num}  {e['cust_name']}"
        if city:
            header += f"  [{city}]"
        if total_str:
            header += f"  |  {total_str}"
        header += f"  (created {created_days}d ago)"
        if planning_note:
            header += planning_note
        lines.append(header)
        if e["job_title"]:
            lines.append(f"  {e['job_title'][:80]}")
        if e["pipeline_status"]:
            lines.append(f"  📋 Pipeline: {e['pipeline_status']}")
        lines.append(f"  {hrs_line}")
        lines.append(f"  {tags_line}")

    # ── Follow-up section ────────────────────────────────────────────────────
    if followup_jobs:
        lines.append(f"\n{'═'*60}")
        lines.append(
            f"SCH-FOLLOWUP — {len(followup_jobs)} job(s) needing a return call before scheduling:"
        )
        for e in sorted(followup_jobs, key=lambda x: x["priority"]):
            job     = e["job"]
            inv_num = job.get("invoice_number", "?")
            desc    = (job.get("description") or "")[:65]
            created_days = _days_since(e["created_at"])
            lines.append(f"\n  #{inv_num}  {e['cust_name']}  (created {created_days}d ago)")
            if desc:
                lines.append(f"    {desc}")
            lines.append(
                f"    Manhours: {e['manhours']:.0f}  |  SCH: {', '.join(e['sch_tags']) or 'none'}"
            )

    return "\n".join(lines)


# ── Multi-week rolling capacity view ──────────────────────────────────────────

@mcp.tool()
async def hcp_multi_week_view(
    start_date: Optional[str] = None,
    weeks: Optional[int] = 4,
) -> str:
    """
    View a rolling multi-week schedule — capacity bars, per-tech breakdown,
    and weekly/grand totals.

    Fetches the entire date range in one round of API calls so it's efficient.
    Use this for planning which jobs fit where and spotting capacity gaps.

    Args:
        start_date: ISO date (YYYY-MM-DD) for the first Monday.
                    Defaults to the current week's Monday — but if today is
                    Wednesday or later, automatically jumps to NEXT Monday so
                    the view leads with actionable future weeks.
        weeks: Number of weeks to show (default 4, max 6).
    """
    today = date.today()
    if start_date:
        try:
            anchor = date.fromisoformat(start_date)
        except ValueError:
            return f"Invalid start_date '{start_date}'. Use YYYY-MM-DD format."
        week_monday = anchor - timedelta(days=anchor.weekday())
    else:
        # Default: current week's Monday.
        # If today is Wednesday (weekday 2) or later the week is already more
        # than half done — jump ahead to NEXT Monday so the view leads with
        # actionable future weeks rather than days already lived.
        week_monday = today - timedelta(days=today.weekday())
        if today.weekday() >= 2:  # Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
            week_monday += timedelta(weeks=1)
    n_weeks     = min(6, max(1, weeks or 4))
    range_start = week_monday
    range_end   = week_monday + timedelta(weeks=n_weeks) - timedelta(days=1)
    hrs_per_day = _HRS_PER_DAY  # loaded from lhstl_config.json

    async with _hcp_client() as client:
        # Employees + date-ranged job pages + recent in-progress jobs — all parallel
        results = await asyncio.gather(
            _get(client, "/employees", {"page": 1, "page_size": 100}),
            *[
                _get(client, "/jobs", {
                    "page": p + 1,
                    "page_size": 100,
                    "scheduled_start_min": range_start.isoformat() + "T00:00:00",
                    "scheduled_start_max": range_end.isoformat() + "T23:59:59",
                })
                for p in range(3)
            ],
            _get(client, "/jobs", {"page": 1, "page_size": 50,
                                   "sort_field": "scheduled_start",
                                   "sort_direction": "desc"}),
        )

    emp_data    = results[0]
    page_results = results[1:4]
    recent_data  = results[4]

    employees = emp_data.get("employees", [])
    # Filter to active field techs only — excludes admin/office accounts
    emp_map   = {
        e["id"]: (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
        for e in employees
        if e["id"] in _ACTIVE_TECH_IDS
    }
    ht_ids   = set(_HALF_TIME_IDS) or {_RYAN_ID}
    ft_count = sum(1 for eid in _ACTIVE_TECH_IDS if eid not in ht_ids)

    # Flatten + dedup; keep scheduled + in_progress
    seen_ids: set[str] = set()
    active: list[dict] = []
    raw_jobs: list[dict] = recent_data.get("jobs", [])
    for r in page_results:
        raw_jobs += r.get("jobs", [])
    for j in raw_jobs:
        status = _norm_status(j.get("work_status", ""))
        if status not in ("scheduled", "in_progress"):
            continue
        jid = j.get("id")
        if jid and jid not in seen_ids:
            seen_ids.add(jid)
            active.append(j)

    # Parallel fetch appointments for all active jobs
    async with _hcp_client() as client:
        appt_lists = await asyncio.gather(*[
            _get(client, f"/jobs/{j['id']}/appointments", {})
            for j in active
        ])

    # Build full date range — Mon-Fri only (no weekends)
    all_weekdays: list[date] = []
    week_ranges: list[list[date]] = []
    for w in range(n_weeks):
        mon  = week_monday + timedelta(weeks=w)
        week = [mon + timedelta(days=d) for d in range(5)]  # Mon=0 … Fri=4
        all_weekdays.extend(week)
        week_ranges.append(week)

    # day_map: date_str → tech_id → [(hours, label)]
    day_map: dict[str, dict] = {d.isoformat(): {} for d in all_weekdays}

    for job, resp in zip(active, appt_lists):
        customer  = job.get("customer") or {}
        cust_name = (
            f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
            or (job.get("description") or "")[:22]
        )
        label = f"#{job.get('invoice_number', '?')} {cust_name}"
        job_assigned_ids = [
            e["id"] for e in (job.get("assigned_employees") or []) if e.get("id")
        ]

        for appt in resp.get("appointments", []):
            appt_start_str = appt.get("start_time") or ""
            appt_end_str   = appt.get("end_time") or ""
            if not appt_start_str:
                continue
            try:
                appt_s = date.fromisoformat(appt_start_str[:10])
                appt_e = date.fromisoformat(appt_end_str[:10]) if appt_end_str else appt_s
            except ValueError:
                continue

            covered = [d for d in all_weekdays if appt_s <= d <= appt_e]
            if not covered:
                continue

            span_days = max(1, (appt_e - appt_s).days + 1)
            daily_hrs = (
                _parse_hours(appt_start_str, appt_end_str, fallback=hrs_per_day)
                if span_days == 1
                else hrs_per_day
            )

            dispatched = appt.get("dispatched_employees_ids") or []
            if not dispatched:
                dispatched = job_assigned_ids

            for target_day in covered:
                d_str = target_day.isoformat()
                if d_str not in day_map:
                    continue
                if not dispatched:
                    day_map[d_str].setdefault(None, []).append((daily_hrs, label))
                else:
                    for tid in dispatched:
                        day_map[d_str].setdefault(tid, []).append((daily_hrs, label))

    # ── Build output ─────────────────────────────────────────────────────────────
    _DAY_ABBR  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    cap_per_day = ft_count * hrs_per_day + len(ht_ids) * hrs_per_day * 0.5

    grand_sched = 0.0
    grand_cap   = 0.0
    out_lines: list[str] = [
        f"MULTI-WEEK SCHEDULE — {n_weeks} weeks  "
        f"({week_monday.strftime('%b %d')} → {(week_monday + timedelta(weeks=n_weeks) - timedelta(days=1)).strftime('%b %d, %Y')})\n"
    ]

    for week_idx, week_days in enumerate(week_ranges):
        week_mon   = week_days[0]
        week_lines = [
            f"{'═'*60}",
            f"WEEK {week_idx + 1}  —  {week_mon.strftime('%b %d')} to {week_days[-1].strftime('%b %d, %Y')}",
        ]
        week_sched = 0.0
        week_cap   = 0.0

        for day_date in week_days:
            d_str     = day_date.isoformat()
            day_name  = _DAY_ABBR[day_date.weekday()]
            tech_data = day_map.get(d_str, {})

            tech_hours: dict[str, float] = {}
            unassigned_hrs = 0.0
            for tid, entries in tech_data.items():
                hrs_sum = sum(h for h, _ in entries)
                if tid is None:
                    unassigned_hrs += hrs_sum
                else:
                    tech_hours[tid] = tech_hours.get(tid, 0.0) + hrs_sum

            sched    = sum(tech_hours.values()) + unassigned_hrs
            week_sched += sched
            week_cap   += cap_per_day

            open_hrs   = max(0.0, cap_per_day - sched)
            bar_filled = min(20, int(round((sched / cap_per_day * 20) if cap_per_day else 0)))
            bar        = "█" * bar_filled + "░" * (20 - bar_filled)
            pct        = sched / cap_per_day * 100 if cap_per_day else 0

            week_lines.append(
                f"  {day_name} {day_date.strftime('%b %d')}  "
                f"[{bar}] {pct:.0f}%  "
                f"{sched:.1f}/{cap_per_day:.0f}h  "
                f"({'%.1f open' % open_hrs if open_hrs > 0.5 else 'FULL'})"
            )

            for tid, hrs in sorted(tech_hours.items(), key=lambda x: emp_map.get(x[0], x[0])):
                name      = emp_map.get(tid, tid[:8])
                ht_marker = " (½)" if tid in ht_ids else ""
                jobs_str  = " · ".join(dict.fromkeys(lbl for _, lbl in tech_data.get(tid, [])))
                overbook  = "⚠ " if hrs > hrs_per_day + 1.0 else ""
                week_lines.append(f"      {overbook}{name}{ht_marker}: {hrs:.1f}h — {jobs_str}")

            if unassigned_hrs > 0:
                week_lines.append(
                    f"      ⚠ UNASSIGNED: {unassigned_hrs:.1f} hrs "
                    f"(no dispatch assignments in HCP)"
                )

        grand_sched += week_sched
        grand_cap   += week_cap
        open_wk      = max(0.0, week_cap - week_sched)
        week_pct     = week_sched / week_cap * 100 if week_cap else 0
        week_lines.append(
            f"  ── Week {week_idx + 1} total: {week_sched:.1f} / {week_cap:.0f} hrs  "
            f"({week_pct:.0f}%)  |  {open_wk:.1f} hrs open"
        )
        out_lines.append("\n".join(week_lines))

    grand_pct = grand_sched / grand_cap * 100 if grand_cap else 0
    out_lines.append(f"\n{'═'*60}")
    out_lines.append(
        f"GRAND TOTAL ({n_weeks} weeks): {grand_sched:.1f} / {grand_cap:.0f} hrs  "
        f"({grand_pct:.0f}%)  |  {max(0.0, grand_cap - grand_sched):.1f} hrs open"
    )

    return "\n".join(out_lines)


# ── Estimate write tools ───────────────────────────────────────────────────────

@mcp.tool()
async def hcp_get_estimate_line_items(
    estimate_id: str,
    option_id: str,
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
) -> str:
    """
    Get all line items for a specific estimate option.

    Args:
        estimate_id: Estimate UUID (from hcp_list_estimates or hcp_get_estimate)
        option_id: Option UUID — found inside estimate['options'][0]['id']
        page: Page number (default 1)
        page_size: Results per page (default 50)
    """
    params: dict = {"page": page, "page_size": page_size}
    data = await api_request(
        "GET", f"/estimates/{estimate_id}/options/{option_id}/line_items", params=params
    )
    items = data.get("line_items", [])
    if not items:
        return "No line items on this estimate option yet."

    labor = [i for i in items if i.get("kind") == "labor"]
    materials = [i for i in items if i.get("kind") == "materials"]
    other = [i for i in items if i.get("kind") not in ("labor", "materials")]

    projected_hours = sum(i.get("quantity", 0) or 0 for i in labor)
    lines = [f"Estimate line items — {len(items)} total  |  Projected hours: {projected_hours:.2f}\n"]

    if labor:
        lines.append("LABOR / SERVICES:")
        for i in labor:
            lines.append(
                f"  • {i.get('name','')} — qty: {i.get('quantity', 0)}"
                f"  @ {_dollars(i.get('unit_price'))} = {_dollars(i.get('amount'))}"
                + (f"  (id: {i['id']})" if i.get("id") else "")
            )
            if i.get("description"):
                lines.append(f"    {i['description']}")

    if materials:
        lines.append("\nMATERIALS:")
        for i in materials:
            lines.append(
                f"  • {i.get('name','')} — qty: {i.get('quantity', 0)}"
                f"  @ {_dollars(i.get('unit_price'))} = {_dollars(i.get('amount'))}"
                + (f"  (id: {i['id']})" if i.get("id") else "")
            )

    if other:
        lines.append("\nDISCOUNTS / GRATUITY:")
        for i in other:
            lines.append(
                f"  • [{i.get('kind','')}] {i.get('name','')} — {_dollars(i.get('amount'))}"
            )

    return "\n".join(lines)


@mcp.tool()
async def hcp_update_estimate_line_items(
    estimate_id: str,
    option_id: str,
    line_items: list,
) -> str:
    """
    Bulk write line items to an estimate option. This is the core write tool for
    the estimating workflow — call this once Dan approves the built-out estimate.

    Existing line items are replaced/updated. Omit 'id' on a line item to create
    it as new; include 'id' to update an existing one.

    Each line_item dict supports:
      name (str, required), quantity (float), unit_price (int, cents),
      unit_cost (int, cents), kind (labor|materials|fixed discount|percent discount|fixed gratuity),
      description (str)

    Example:
      [
        {"name": "Framing — 18×12 basement room", "kind": "labor", "quantity": 16, "unit_price": 9500},
        {"name": "Drywall & finishing (2 walls)", "kind": "labor", "quantity": 12, "unit_price": 9500},
        {"name": "Door installation", "kind": "labor", "quantity": 4, "unit_price": 9500},
        {"name": "Lumber & hardware", "kind": "materials", "quantity": 1, "unit_price": 45000},
        {"name": "Drywall sheets & screws", "kind": "materials", "quantity": 1, "unit_price": 22000}
      ]

    Args:
        estimate_id: Estimate UUID
        option_id: Option UUID
        line_items: List of line item dicts (see above)
    """
    data = await api_request(
        "PUT",
        f"/estimates/{estimate_id}/options/{option_id}/line_items/bulk_update",
        json={"line_items": line_items},
    )
    items = data.get("line_items", [])
    total = sum(i.get("amount", 0) or 0 for i in items)
    lines = [f"✓ {len(items)} line item(s) written to estimate option.  Total: {_dollars(total)}\n"]
    for i in items:
        lines.append(
            f"  • [{i.get('kind','')}] {i.get('name','')} — qty: {i.get('quantity', 0)}"
            f"  @ {_dollars(i.get('unit_price'))} = {_dollars(i.get('amount'))}"
        )
    return "\n".join(lines)


@mcp.tool()
async def hcp_add_estimate_note(
    estimate_id: str,
    option_id: str,
    content: str,
) -> str:
    """
    Add a note to a specific estimate option.

    Use this to record Dan's estimate assumptions, scope clarifications, or
    a summary of what was built into the estimate so there's a paper trail.

    Args:
        estimate_id: Estimate UUID
        option_id: Option UUID
        content: Note text
    """
    data = await api_request(
        "POST",
        f"/estimates/{estimate_id}/options/{option_id}/notes",
        json={"content": content},
    )
    note_id = data.get("id", "?")
    return f"Note added to estimate option (id: {note_id})."


@mcp.tool()
async def hcp_finalize_estimate(
    estimate_id: str,
    option_id: str,
    line_items: list,
    summary_note: Optional[str] = None,
) -> str:
    """
    Write all line items to an estimate option, add an optional summary note,
    then mark it Pro-approved — all in the correct order.

    This is the single "Dan approved it" tool. Call this once Dan has reviewed
    the built-out estimate. It will:
      1. Write every line item to the estimate option (bulk)
      2. Add a summary note if provided (scope assumptions, exclusions, etc.)
      3. Mark the option as Pro-approved → moves to "Ready 4 Review" pipeline
         so the customer can review and approve

    Args:
        estimate_id: Estimate UUID
        option_id: Option UUID (from estimate['options'][0]['id'])
        line_items: List of line item dicts — same format as hcp_update_estimate_line_items
                    Each item: {name, kind, quantity, unit_price (cents), unit_cost (cents, optional), description (optional)}
        summary_note: Optional note summarising what's included / excluded / assumed.
                      Logged to the estimate so there's a paper trail before it goes to the customer.
    """
    # Step 1 — Write line items
    li_data = await api_request(
        "PUT",
        f"/estimates/{estimate_id}/options/{option_id}/line_items/bulk_update",
        json={"line_items": line_items},
    )
    written_items = li_data.get("line_items", [])
    total = sum(i.get("amount", 0) or 0 for i in written_items)

    # Step 2 — Add summary note (optional)
    note_result = ""
    if summary_note:
        await api_request(
            "POST",
            f"/estimates/{estimate_id}/options/{option_id}/notes",
            json={"content": summary_note},
        )
        note_result = "\n  ✓ Summary note added"

    # Step 3 — Approve
    approval_data = await api_request(
        "POST", "/estimates/options/approve", json={"option_ids": [option_id]}
    )
    status = approval_data.get("status", "approved")

    lines = [
        f"✓ Estimate finalized and sent to Ready 4 Review\n",
        f"  Line items written: {len(written_items)}  |  Total: {_dollars(total)}",
    ]
    for i in written_items:
        lines.append(
            f"    • [{i.get('kind','')}] {i.get('name','')} — "
            f"qty: {i.get('quantity',0)}  @ {_dollars(i.get('unit_price'))} = {_dollars(i.get('amount'))}"
        )
    lines.append(note_result)
    lines.append(f"\n  Approval status: {status}")
    lines.append("  → Customer will receive the estimate for review and approval.")
    return "\n".join(lines)


@mcp.tool()
async def hcp_approve_estimate_option(option_ids: str) -> str:
    """
    Mark estimate option(s) as Pro-approved — moves the estimate to
    "Ready 4 Review" in the pipeline so the customer can review and approve it.

    The customer approves through their portal, which then converts it to a job.
    This tool only sets the pro-side approval; it does NOT create a job.

    Args:
        option_ids: Comma-separated option UUIDs to approve
                    (from estimate['options'][N]['id'])
    """
    ids = [s.strip() for s in option_ids.split(",") if s.strip()]
    if not ids:
        return "Error: no option IDs provided."
    data = await api_request(
        "POST", "/estimates/options/approve", json={"option_ids": ids}
    )
    job_id = data.get("copied_on_approval_to_job_id")
    status = data.get("status", "approved")
    result = f"✓ Estimate option(s) marked Pro-approved — status: {status}"
    result += "\n  → Estimate is now in 'Ready 4 Review'. Customer must approve to convert to a job."
    if job_id:
        result += f"\n  → (Job also created: {job_id})"
    return result


# ── Pipeline / Kanban tools ────────────────────────────────────────────────────

@mcp.tool()
async def hcp_get_pipeline_statuses(
    resource_type: Optional[str] = "job",
) -> str:
    """
    List all pipeline stages configured in HCP for jobs, estimates, or leads.

    Returns each stage name and its UUID (needed for hcp_set_pipeline_status).
    Run this once to learn your stage names and IDs.

    Args:
        resource_type: 'job' (default), 'estimate', or 'lead'
    """
    rt = (resource_type or "job").strip().lower()
    data = await api_request(
        "GET", "/pipeline/statuses",
        params={"resource_type": rt, "page_size": 50, "page": 1},
    )
    statuses = data.get("statuses", [])
    if not statuses:
        return (
            f"No pipeline stages found for resource_type='{rt}'.\n"
            "Pipeline may not be enabled, or no stages are configured."
        )
    lines = [f"Pipeline stages for '{rt}'  ({len(statuses)} stages):"]
    for i, s in enumerate(statuses, 1):
        lines.append(
            f"  {i:2d}. {s.get('name', '?'):<35}  "
            f"type: {s.get('status_type', '?'):<15}  "
            f"id: {s.get('id', '?')}"
        )
    return "\n".join(lines)


@mcp.tool()
async def hcp_pipeline_board(
    include_completed: Optional[bool] = False,
    include_canceled: Optional[bool] = False,
) -> str:
    """
    View all active jobs as a kanban-style board grouped by work status.

    NOTE: The HCP public API does not return a job's current pipeline stage
    on job objects — only the stage *definitions* can be read, not which
    stage each job is in.  This board therefore groups by work_status, which
    is the closest reliable proxy.  Use hcp_set_pipeline_status to move a
    specific job to a named stage; use hcp_get_pipeline_statuses for stage IDs.

    Groups shown (in order):
      needs scheduling  →  in progress  →  scheduled  →  completed  →  (in_progress sub-stages)

    Args:
        include_completed: Show completed jobs (default False — clutter reduction).
        include_canceled:  Show pro/user-canceled jobs (default False).
    """
    # Fetch all jobs across pages in parallel
    page_results = await asyncio.gather(
        api_request("GET", "/jobs",
                    params={"page": 1, "page_size": 100,
                            "sort_by": "updated_at", "sort_direction": "desc"}),
        api_request("GET", "/jobs",
                    params={"page": 2, "page_size": 100,
                            "sort_by": "updated_at", "sort_direction": "desc"}),
        api_request("GET", "/jobs",
                    params={"page": 3, "page_size": 100,
                            "sort_by": "updated_at", "sort_direction": "desc"}),
        return_exceptions=True,
    )

    _canceled_set = {"user_canceled", "pro_canceled"}
    _complete_set = {"complete_rated", "complete_unrated"}

    seen_ids: set[str] = set()
    all_jobs: list[dict] = []
    for r in page_results:
        if isinstance(r, Exception):
            continue
        for j in r.get("jobs", []):
            jid = j.get("id")
            if not jid or jid in seen_ids:
                continue
            seen_ids.add(jid)
            sn = _norm_status(j.get("work_status", ""))
            if not include_canceled and sn in _canceled_set:
                continue
            if not include_completed and sn in _complete_set:
                continue
            all_jobs.append(j)

    if not all_jobs:
        return "No jobs found."

    # ── Bucket by work_status ─────────────────────────────────────────────────
    # Display order matches the natural job lifecycle
    BUCKET_ORDER = [
        "needs_scheduling",
        "in_progress",
        "scheduled",
    ]
    if include_completed:
        BUCKET_ORDER += ["complete_rated", "complete_unrated"]
    if include_canceled:
        BUCKET_ORDER += ["user_canceled", "pro_canceled"]

    BUCKET_LABELS = {
        "needs_scheduling":  "NEEDS SCHEDULING  (backlog — not yet on calendar)",
        "in_progress":       "IN PROGRESS  (actively being worked)",
        "scheduled":         "SCHEDULED  (on the calendar — not yet started)",
        "complete_rated":    "COMPLETED (rated)",
        "complete_unrated":  "COMPLETED (not yet rated)",
        "user_canceled":     "CANCELED (customer)",
        "pro_canceled":      "CANCELED (pro)",
    }

    buckets: dict[str, list[dict]] = {k: [] for k in BUCKET_ORDER}
    other_bucket: list[dict] = []

    for job in all_jobs:
        sn = _norm_status(job.get("work_status", ""))
        if sn in buckets:
            buckets[sn].append(job)
        else:
            other_bucket.append(job)

    # ── Render ────────────────────────────────────────────────────────────────
    total_val = sum((j.get("total_amount") or 0) for j in all_jobs)
    lines = [
        f"PIPELINE BOARD — {len(all_jobs)} active job(s)  |  "
        f"Total value: {_dollars(total_val)}\n"
        f"{'═'*60}",
    ]

    def _render_job(job: dict) -> str:
        inv   = job.get("invoice_number", "?")
        cust  = job.get("customer") or {}
        cname = (
            f"{cust.get('first_name','')} {cust.get('last_name','')}".strip()
            or cust.get("company", "?")
        )
        city  = (job.get("address") or {}).get("city", "")
        total = _dollars(job.get("total_amount"))
        tags_raw = [
            t.get("name", "") if isinstance(t, dict) else str(t)
            for t in (job.get("tags") or [])
        ]
        tag_cats  = _parse_tags(tags_raw)
        sch_disp  = ", ".join(tag_cats["scheduling"]) or "—"
        crew_disp = ", ".join(tag_cats["crew"]) or "—"
        emps      = job.get("assigned_employees", [])
        emp_names = ", ".join(
            (e.get("first_name", "") + " " + e.get("last_name", "")).strip()
            for e in emps
            if e.get("id") in _ACTIVE_TECH_IDS
        ) or "Unassigned"
        loc = f"  [{city}]" if city else ""
        sched = job.get("schedule") or {}
        appt_str = ""
        if sched.get("start_time"):
            try:
                appt_dt = dt.fromisoformat(sched["start_time"].replace("Z", "+00:00"))
                appt_str = f"  📅 {appt_dt.strftime('%b %d')}"
            except Exception:
                pass
        return (
            f"  #{inv}  {cname}{loc}  |  {total}{appt_str}\n"
            f"      CREW: {crew_disp}  |  SCH: {sch_disp}  |  👷 {emp_names}"
        )

    for bucket_key in BUCKET_ORDER:
        jobs_here = buckets[bucket_key]
        label = BUCKET_LABELS.get(bucket_key, bucket_key.upper())
        lines.append(f"\n▶ {label}  ({len(jobs_here)})")
        if not jobs_here:
            lines.append("    (empty)")
        else:
            # Sort needs_scheduling by value desc (biggest jobs first)
            if bucket_key == "needs_scheduling":
                jobs_here = sorted(jobs_here,
                                   key=lambda j: j.get("total_amount") or 0,
                                   reverse=True)
            # Sort in_progress and scheduled by appointment date asc
            elif bucket_key in ("in_progress", "scheduled"):
                def _appt_sort(j: dict) -> str:
                    s = (j.get("schedule") or {}).get("start_time") or "9999"
                    return s
                jobs_here = sorted(jobs_here, key=_appt_sort)
            for job in jobs_here:
                lines.append(_render_job(job))

    if other_bucket:
        lines.append(f"\n▶ OTHER STATUS  ({len(other_bucket)})")
        for job in other_bucket:
            lines.append(_render_job(job))

    lines.append(
        f"\n{'─'*60}\n"
        f"ℹ️  To see HCP pipeline stage names/IDs: hcp_get_pipeline_statuses\n"
        f"ℹ️  To move a job to a stage: hcp_set_pipeline_status(job_id, status_id)\n"
        f"    Note: HCP API does not return each job's current pipeline stage on\n"
        f"    job objects — grouping above uses work_status as the closest proxy."
    )

    return "\n".join(lines)


@mcp.tool()
async def hcp_set_pipeline_status(
    job_id: str,
    status_id: str,
) -> str:
    """
    Move a job to a different pipeline stage.

    HCP only allows forward movement — you can't move a job backward
    to a stage with a lower order value than the current stage.

    Use hcp_get_pipeline_statuses to find stage IDs (kcs_... format).

    Args:
        job_id: Job UUID (job_... format)
        status_id: Pipeline stage UUID (kcs_... format)
    """
    data = await api_request(
        "PUT", "/pipeline/statuses",
        json={
            "resource_type": "job",
            "resource_id": job_id,
            "status_id": status_id,
        },
    )
    if isinstance(data, dict) and "error" in data:
        return f"❌ Error: {data['error']}"
    name        = data.get("name", status_id)
    returned_id = data.get("resource_id", job_id)
    return (
        f"✓ Job {returned_id} moved to pipeline stage: {name}\n"
        f"  (status_id: {data.get('status_id', status_id)})"
    )


@mcp.tool()
async def hcp_post_job_analysis(job_id: str) -> str:
    """
    Full post-job profitability and performance analysis for a completed job.

    Pulls in parallel: job detail, line items, invoice, appointments, input materials.

    Calculates:
      • Quoted hours vs scheduled tech-hours (best available proxy for actual)
      • Labor cost using blended rate from lhstl_config.json
      • Materials cost from line item unit_costs (what LHSTL paid)
      • Gross profit and margin %
      • Add-on revenue (line items with 'add on' / 'addon' in name)
      • Discounts applied
      • Warranty flag (JOB-WARRANTY tag)
      • Payment speed and method
      • Notes for issues / context

    Args:
        job_id: Job UUID (job_... format)
    """
    # ── Load config for blended rate ──────────────────────────────────────────
    cfg         = _load_config()
    sched_cfg   = cfg.get("scheduling", {})
    cost_rate   = float(sched_cfg.get("blended_cost_per_tech_hour", 95.0))

    # ── Parallel fetch job data, line items, invoice, materials ──────────────
    job_data, li_data, inv_data, mat_data = await asyncio.gather(
        api_request("GET", f"/jobs/{job_id}"),
        api_request("GET", f"/jobs/{job_id}/line_items"),
        api_request("GET", f"/jobs/{job_id}/invoices"),
        api_request("GET", f"/jobs/{job_id}/job_input_materials"),
        return_exceptions=True,
    )

    def _safe(result, default):
        return default if isinstance(result, Exception) else result

    job_data = _safe(job_data, {})
    li_data  = _safe(li_data,  {})
    inv_data = _safe(inv_data, {})
    mat_data = _safe(mat_data, {})

    # Fetch appointments via _hcp_client — embeds assigned_employees objects
    # (api_request does not embed them; same pattern as hcp_get_job_appointments)
    try:
        async with _hcp_client() as client:
            appt_data = await _get(client, f"/jobs/{job_id}/appointments", {})
    except Exception:
        appt_data = {}

    # ── Job header ────────────────────────────────────────────────────────────
    customer   = job_data.get("customer") or {}
    address    = job_data.get("address") or {}
    tags_raw   = [t.get("name","") if isinstance(t, dict) else str(t)
                  for t in (job_data.get("tags") or [])]
    tags_upper = [t.upper() for t in tags_raw]

    assigned = ", ".join(
        (e.get("first_name","") + " " + e.get("last_name","")).strip()
        for e in (job_data.get("assigned_employees") or [])
    ) or "Unassigned"

    timestamps  = job_data.get("work_timestamps") or {}
    started_at  = timestamps.get("started_at") or ""
    completed_at = timestamps.get("completed_at") or ""

    # ── Line items ────────────────────────────────────────────────────────────
    items      = (li_data.get("data") or li_data.get("line_items") or [])
    labor      = [i for i in items if i.get("kind") == "labor"]
    materials  = [i for i in items if i.get("kind") == "materials"]

    quoted_hrs = sum(float(i.get("quantity") or 0) for i in labor)
    labor_rev  = sum(int(i.get("amount") or 0) for i in labor)
    mat_rev    = sum(int(i.get("amount") or 0) for i in materials)
    mat_cost_li = sum(
        int(i.get("unit_cost") or 0) * float(i.get("quantity") or 1)
        for i in materials
    )

    # Add-on detection — line items with "add on" or "addon" in name
    addons     = [i for i in labor if "add on" in (i.get("name") or "").lower()
                  or "addon" in (i.get("name") or "").lower()]
    addon_rev  = sum(int(i.get("amount") or 0) for i in addons)
    addon_hrs  = sum(float(i.get("quantity") or 0) for i in addons)
    base_labor = [i for i in labor if i not in addons]
    base_rev   = sum(int(i.get("amount") or 0) for i in base_labor)
    base_hrs   = sum(float(i.get("quantity") or 0) for i in base_labor)

    # ── Invoice ───────────────────────────────────────────────────────────────
    # invoice endpoint returns list or object depending on version
    if isinstance(inv_data, list):
        inv = inv_data[0] if inv_data else {}
    else:
        inv = inv_data.get("invoice") or inv_data.get("invoices", [{}])[0] if "invoices" in inv_data else inv_data

    # HCP invoice keys: subtotal → "subtotal", total → "amount", balance → "due_amount"
    inv_subtotal  = int(inv.get("subtotal") or 0)
    inv_total     = int(inv.get("amount")   or 0)
    inv_discount  = inv_subtotal - inv_total if inv_subtotal > inv_total else 0
    inv_balance   = int(inv.get("due_amount") or 0)
    inv_status    = inv.get("status") or "unknown"

    payments      = inv.get("payments") or []
    if not isinstance(payments, list):
        payments = []
    pay_method    = payments[0].get("payment_method", "—") if payments else "—"
    pay_date      = (payments[0].get("paid_at") or payments[0].get("created_at") or "")[:10] if payments else ""
    completed_date = (completed_at or "")[:10]
    days_to_pay   = ""
    if completed_date and pay_date:
        from datetime import date
        try:
            d1 = date.fromisoformat(completed_date)
            d2 = date.fromisoformat(pay_date)
            days_to_pay = str((d2 - d1).days)
        except Exception:
            pass

    # Use invoice total as authoritative revenue (reflects discounts)
    revenue = inv_total if inv_total > 0 else (labor_rev + mat_rev)

    # ── Appointments → scheduled tech-hours ───────────────────────────────────
    appts = appt_data.get("appointments") or []
    if not isinstance(appts, list):
        appts = []

    total_tech_hours = 0.0
    appt_lines       = []
    for appt in appts:
        start_str = appt.get("start_time") or appt.get("scheduled_start") or ""
        end_str   = appt.get("end_time")   or appt.get("scheduled_end")   or ""

        # assigned_employees — list of employee objects (available when fetched via _hcp_client)
        emp_objs = appt.get("assigned_employees") or []
        if isinstance(emp_objs, list) and emp_objs and isinstance(emp_objs[0], dict):
            n_techs    = len(emp_objs)
            tech_names = ", ".join(
                (e.get("first_name","") + " " + e.get("last_name","")).strip()
                for e in emp_objs
            ) or f"{n_techs} tech(s)"
        else:
            # Fallback: count dispatched employee IDs if objects aren't embedded
            emp_ids    = appt.get("dispatched_employees_ids") or []
            n_techs    = len(emp_ids)
            tech_names = f"{n_techs} tech(s)" if n_techs > 0 else "—"

        # Use existing _parse_hours helper — handles Z suffix correctly
        appt_hrs = _parse_hours(start_str, end_str, fallback=0.0)

        tech_hrs = appt_hrs * n_techs
        total_tech_hours += tech_hrs
        date_str = start_str[:10] if start_str else "?"
        appt_lines.append(
            f"    {date_str}  {n_techs} tech(s) × {appt_hrs:.1f}h = {tech_hrs:.1f} tech-hrs  [{tech_names}]"
        )

    # ── Input materials (if logged) ───────────────────────────────────────────
    input_mats = mat_data.get("job_input_materials") or mat_data.get("data") or []
    if not isinstance(input_mats, list):
        input_mats = []

    # ── Cost & margin ─────────────────────────────────────────────────────────
    labor_cost   = total_tech_hours * cost_rate
    # Use input material costs if logged, otherwise fall back to line item unit_costs
    if input_mats:
        mat_cost = sum(
            float(m.get("unit_cost") or 0) * float(m.get("quantity") or 1)
            for m in input_mats
        )
    else:
        mat_cost = mat_cost_li / 100  # convert cents → dollars

    total_cost   = labor_cost + mat_cost
    gross_profit = (revenue / 100) - total_cost
    margin_pct   = (gross_profit / (revenue / 100) * 100) if revenue > 0 else 0.0

    # ── Flags ─────────────────────────────────────────────────────────────────
    is_warranty  = "JOB-WARRANTY" in tags_upper
    has_addons   = len(addons) > 0
    has_discount = inv_discount > 0
    hour_variance = total_tech_hours - quoted_hrs  # + = over, - = under

    # ── Format output ─────────────────────────────────────────────────────────
    lines = [
        f"╔══ POST-JOB ANALYSIS ════════════════════════════════════════",
        f"║  Job:        #{job_data.get('invoice_number','?')} — {job_data.get('description','?')}",
        f"║  Customer:   {customer.get('first_name','')} {customer.get('last_name','')}",
        f"║  Address:    {address.get('street','')} {address.get('city','')}",
        f"║  Techs:      {assigned}",
        f"║  Status:     {job_data.get('work_status','?')}",
        f"║  Completed:  {completed_date or '?'}",
    ]
    if is_warranty:
        lines.append(f"║  ⚠ WARRANTY JOB — JOB-WARRANTY tag present")

    # ── Time ──────────────────────────────────────────────────────────────────
    lines += [
        f"╠══ TIME ══════════════════════════════════════════════════════",
        f"║  Quoted hours:          {quoted_hrs:.1f} hrs",
        f"║    Base scope:          {base_hrs:.1f} hrs",
        f"║    Add-ons:             {addon_hrs:.1f} hrs",
        f"║  Scheduled tech-hours:  {total_tech_hours:.1f} hrs  (across {len(appts)} appointment(s))",
        f"║  Hour variance:         {hour_variance:+.1f} hrs  ({'over' if hour_variance > 0 else 'under'} quoted)",
    ]
    if appt_lines:
        lines.append(f"║")
        lines.append(f"║  Appointment breakdown:")
        lines += appt_lines

    # ── Revenue ───────────────────────────────────────────────────────────────
    lines += [
        f"╠══ REVENUE ═══════════════════════════════════════════════════",
        f"║  Base scope labor:      {_dollars(labor_rev - addon_rev)}",
        f"║  Add-on labor:          {_dollars(addon_rev)}" + ("  ← add-on revenue" if has_addons else ""),
        f"║  Materials (charged):   {_dollars(mat_rev)}",
        f"║  Subtotal:              {_dollars(inv_subtotal)}",
    ]
    if has_discount:
        lines.append(f"║  Discount applied:      -{_dollars(inv_discount)}")
    lines += [
        f"║  Final invoice:         {_dollars(inv_total)}",
        f"║  Balance outstanding:   {_dollars(inv_balance)}",
        f"║  Payment:               {pay_method}  |  Paid: {pay_date or '—'}"
        + (f"  ({days_to_pay} day(s) after completion)" if days_to_pay else ""),
    ]

    # Add-on detail
    if has_addons:
        lines.append(f"║")
        lines.append(f"║  ADD-ONS ({len(addons)}):")
        for a in addons:
            lines.append(f"║    • {a.get('name','')}  {float(a.get('quantity',0)):.0f} hrs  {_dollars(a.get('amount'))}")

    # ── Cost & margin ─────────────────────────────────────────────────────────
    lines += [
        f"╠══ COST & MARGIN ═════════════════════════════════════════════",
        f"║  Labor cost:            ${labor_cost:,.2f}  ({total_tech_hours:.1f} tech-hrs × ${cost_rate:.0f}/hr)",
        f"║  Materials cost:        ${mat_cost:,.2f}" + ("  (from input materials log)" if input_mats else "  (from line item unit costs)"),
        f"║  Total cost:            ${total_cost:,.2f}",
        f"║  ─────────────────────────────────────────────────────────",
        f"║  Gross profit:          ${gross_profit:,.2f}",
        f"║  Gross margin:          {margin_pct:.1f}%",
    ]
    if margin_pct < 20:
        lines.append(f"║  ⚠ LOW MARGIN — below 20%")
    elif margin_pct >= 50:
        lines.append(f"║  ✓ Strong margin")

    # ── Tags ──────────────────────────────────────────────────────────────────
    lines.append(f"╠══ TAGS & FLAGS ══════════════════════════════════════════════")
    lines.append(f"║  Tags present:  {', '.join(tags_raw) if tags_raw else 'none'}")
    if is_warranty:
        lines.append(f"║  ⚠ WARRANTY — this visit should be tracked against original job")
    if not any(t.startswith("CREW-") for t in tags_upper):
        lines.append(f"║  ⚠ No CREW tag on this job")
    if not any(t.startswith("JOB-IN") or t.startswith("JOB-OUT") for t in tags_upper):
        lines.append(f"║  ⚠ No JOB location tag (JOB-IN / JOB-OUT / JOB-INOUT)")

    # ── Notes ─────────────────────────────────────────────────────────────────
    notes = job_data.get("notes") or []
    if not isinstance(notes, list):
        notes = []
    note_contents = [(n.get("content") or "").strip() for n in notes if (n.get("content") or "").strip()]
    if note_contents:
        lines.append(f"╠══ JOB NOTES ({len(note_contents)}) ════════════════════════════════════")
        for idx, nc in enumerate(note_contents, 1):
            lines.append(f"║  [{idx}]")
            for ln in nc.splitlines():
                lines.append(f"║  {ln}")
    else:
        lines.append(f"╠══ JOB NOTES ══════════════════════════════════════════════")
        lines.append(f"║  (no notes on this job)")

    # ── Input materials (if logged) ───────────────────────────────────────────
    if input_mats:
        lines.append(f"╠══ INPUT MATERIALS LOGGED ({len(input_mats)}) ═══════════════════════════")
        for m in input_mats:
            lines.append(
                f"║  • {m.get('name','')}  qty: {m.get('quantity','')}  "
                f"cost: ${float(m.get('unit_cost') or 0):.2f}"
            )
    else:
        lines.append(f"╠══ INPUT MATERIALS ════════════════════════════════════════")
        lines.append(f"║  (none logged — materials cost from line item unit costs)")

    lines.append(f"╚{'═'*61}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
