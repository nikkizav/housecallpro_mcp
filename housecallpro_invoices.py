#!/usr/bin/env python3
"""
Housecall Pro Invoices MCP Server
Invoice CRUD and payment operations.
"""

from typing import Optional, List, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Invoices")


@mcp.tool()
async def get_invoices(
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
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
) -> Dict[str, Any]:
    """
    List invoices with rich filtering. Core tool for financial analysis.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 50, max 100)
        status: Comma-separated: open, pending_payment, paid, voided, uncollectible, canceled
        customer_uuid: Comma-separated customer UUIDs
        created_at_min: Invoices created on or after (ISO 8601 e.g. 2026-04-01T00:00:00Z)
        created_at_max: Invoices created on or before (ISO 8601)
        paid_at_min: Invoices paid on or after (ISO 8601)
        paid_at_max: Invoices paid on or before (ISO 8601)
        due_at_min: Invoices due on or after (ISO 8601)
        due_at_max: Invoices due on or before (ISO 8601)
        payment_method: Comma-separated: consumer_financing, credit_card, ach, external, mobile_check_deposit
        sort_by: amount | created_at | due_amount | due_at | invoice_number | paid_at | status | updated_at
        sort_direction: asc or desc (default: desc)
    """
    params: dict = {
        "page": page,
        "page_size": page_size,
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
async def get_invoice(invoice_uuid: str) -> Dict[str, Any]:
    """
    Get full invoice detail by UUID, including line items, taxes, discounts, and payments.

    Args:
        invoice_uuid: Invoice UUID
    """
    return await api_request("GET", f"/invoices/{invoice_uuid}")


@mcp.tool()
async def get_job_invoices(
    job_id: str,
    include_line_items: Optional[bool] = None,
    include_attachments: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Get all invoices for a specific job.

    Args:
        job_id: Job UUID
        include_line_items: Include line items in response
        include_attachments: Include attachments in response
    """
    params: dict = {}
    if include_line_items is not None:
        params["include_line_items"] = str(include_line_items).lower()
    if include_attachments is not None:
        params["include_attachments"] = str(include_attachments).lower()
    return await api_request("GET", f"/jobs/{job_id}/invoices", params=params)


@mcp.tool()
async def send_invoice(invoice_uuid: str) -> Dict[str, Any]:
    """
    Send an invoice to the customer.

    Args:
        invoice_uuid: Invoice UUID
    """
    return await api_request("POST", f"/invoices/{invoice_uuid}/send")


@mcp.tool()
async def record_payment(
    invoice_uuid: str,
    amount: int,
    payment_method: str,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Record a payment on an invoice.

    Args:
        invoice_uuid: Invoice UUID
        amount: Payment amount in cents (e.g. 15000 = $150.00)
        payment_method: credit_card | ach | external | consumer_financing | mobile_check_deposit
        note: Optional payment note
    """
    payload: dict = {"amount": amount, "payment_method": payment_method}
    if note:
        payload["note"] = note
    return await api_request("POST", f"/invoices/{invoice_uuid}/payments", json=payload)


if __name__ == "__main__":
    mcp.run()
