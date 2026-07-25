#!/usr/bin/env python3
"""
Housecall Pro Job Invoices MCP Server
Job-specific invoice operations (separate from the standalone invoices server).
"""

from typing import Optional, List, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Job Invoices")


@mcp.tool()
async def get_job_invoices(
    job_id: str,
    include_line_items: Optional[bool] = None,
    include_attachments: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Get all invoices for a specific job.

    Args:
        job_id: Job UUID (required)
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
async def get_job_invoice(job_id: str, invoice_id: str) -> Dict[str, Any]:
    """
    Get a specific invoice for a job.

    Args:
        job_id: Job UUID
        invoice_id: Invoice UUID
    """
    return await api_request("GET", f"/jobs/{job_id}/invoices/{invoice_id}")


@mcp.tool()
async def create_job_invoice(
    job_id: str,
    line_items: Optional[List[Dict[str, Any]]] = None,
    notes: Optional[str] = None,
    due_concept: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new invoice for a job.

    Args:
        job_id: Job UUID (required)
        line_items: List of line item objects
        notes: Invoice notes
        due_concept: Due date concept (e.g. upon_receipt, net_30)
    """
    payload: dict = {}
    if line_items:
        payload["line_items"] = line_items
    if notes:
        payload["notes"] = notes
    if due_concept:
        payload["due_concept"] = due_concept
    return await api_request("POST", f"/jobs/{job_id}/invoices", json=payload)


@mcp.tool()
async def update_job_invoice(
    job_id: str,
    invoice_id: str,
    notes: Optional[str] = None,
    due_concept: Optional[str] = None,
    line_items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Update an existing job invoice.

    Args:
        job_id: Job UUID
        invoice_id: Invoice UUID
        notes: Updated notes
        due_concept: Updated due date concept
        line_items: Updated line items list
    """
    payload: dict = {}
    if notes is not None:
        payload["notes"] = notes
    if due_concept is not None:
        payload["due_concept"] = due_concept
    if line_items is not None:
        payload["line_items"] = line_items
    return await api_request("PUT", f"/jobs/{job_id}/invoices/{invoice_id}", json=payload)


if __name__ == "__main__":
    mcp.run()
