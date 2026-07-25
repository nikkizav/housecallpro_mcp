#!/usr/bin/env python3
"""
Housecall Pro Invoices Query MCP Server
Advanced invoice querying and reporting tools.
"""

from typing import Optional, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Invoices Query")


@mcp.tool()
async def query_invoices(
    status: Optional[str] = None,
    customer_uuid: Optional[str] = None,
    created_at_min: Optional[str] = None,
    created_at_max: Optional[str] = None,
    paid_at_min: Optional[str] = None,
    paid_at_max: Optional[str] = None,
    due_at_min: Optional[str] = None,
    due_at_max: Optional[str] = None,
    payment_method: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_direction: Optional[str] = "desc",
    page: Optional[int] = 1,
    page_size: Optional[int] = 100,
) -> Dict[str, Any]:
    """
    Advanced invoice querying with comprehensive filter support.
    Designed for post-week financial analysis and reporting.

    Args:
        status: Comma-separated: open, pending_payment, paid, voided, uncollectible, canceled
        customer_uuid: Comma-separated customer UUIDs
        created_at_min: Invoices created on or after (ISO 8601 e.g. 2026-04-21T00:00:00Z)
        created_at_max: Invoices created on or before (ISO 8601)
        paid_at_min: Invoices paid on or after (ISO 8601)
        paid_at_max: Invoices paid on or before (ISO 8601)
        due_at_min: Invoices due on or after (ISO 8601)
        due_at_max: Invoices due on or before (ISO 8601)
        payment_method: Comma-separated: consumer_financing, credit_card, ach, external, mobile_check_deposit
        sort_by: amount | created_at | due_amount | due_at | invoice_number | paid_at | status | updated_at
        sort_direction: asc or desc (default: desc)
        page: Page number (default 1)
        page_size: Results per page (default 100, max 100)
    """
    params: dict = {
        "page": page,
        "page_size": min(page_size, 100),
        "sort_by": sort_by,
        "sort_direction": sort_direction,
        "created_at_min": created_at_min,
        "created_at_max": created_at_max,
        "paid_at_min": paid_at_min,
        "paid_at_max": paid_at_max,
        "due_at_min": due_at_min,
        "due_at_max": due_at_max,
    }
    if status:
        params["status"] = [s.strip() for s in status.split(",") if s.strip()]
    if customer_uuid:
        params["customer_uuid"] = [s.strip() for s in customer_uuid.split(",") if s.strip()]
    if payment_method:
        params["payment_method"] = [s.strip() for s in payment_method.split(",") if s.strip()]
    return await api_request("GET", "/invoices", params=params)


@mcp.tool()
async def get_outstanding_invoices(
    page: Optional[int] = 1,
    page_size: Optional[int] = 100,
    sort_by: Optional[str] = "due_at",
    sort_direction: Optional[str] = "asc",
) -> Dict[str, Any]:
    """
    Get all open / pending-payment invoices sorted by due date (oldest first by default).
    Useful for collections review and follow-up prioritization.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 100, max 100)
        sort_by: Field to sort by (default: due_at)
        sort_direction: asc or desc (default: asc — oldest due date first)
    """
    params: dict = {
        "page": page,
        "page_size": min(page_size, 100),
        "status": ["open", "pending_payment"],
        "sort_by": sort_by,
        "sort_direction": sort_direction,
    }
    return await api_request("GET", "/invoices", params=params)


@mcp.tool()
async def get_paid_invoices_for_period(
    paid_at_min: str,
    paid_at_max: str,
    payment_method: Optional[str] = None,
    page: Optional[int] = 1,
    page_size: Optional[int] = 100,
) -> Dict[str, Any]:
    """
    Get all paid invoices within a specific date range.
    Core tool for weekly and monthly revenue reporting.

    Args:
        paid_at_min: Start of paid date range (ISO 8601 e.g. 2026-04-21T00:00:00Z) (required)
        paid_at_max: End of paid date range (ISO 8601) (required)
        payment_method: Comma-separated: consumer_financing, credit_card, ach, external, mobile_check_deposit
        page: Page number (default 1)
        page_size: Results per page (default 100, max 100)
    """
    params: dict = {
        "page": page,
        "page_size": min(page_size, 100),
        "status": ["paid"],
        "paid_at_min": paid_at_min,
        "paid_at_max": paid_at_max,
        "sort_by": "paid_at",
        "sort_direction": "asc",
    }
    if payment_method:
        params["payment_method"] = [s.strip() for s in payment_method.split(",") if s.strip()]
    return await api_request("GET", "/invoices", params=params)


if __name__ == "__main__":
    mcp.run()
