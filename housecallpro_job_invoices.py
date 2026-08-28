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


# Removed get_job_invoice, create_job_invoice, update_job_invoice: the underlying endpoint(s) do not exist.
# A request to them returns Housecall Pro's HTML 404 page, meaning the route
# itself is absent (a missing *record* returns a JSON error instead).
# Verified against a live account 2026-08-28.

if __name__ == "__main__":
    mcp.run()
