#!/usr/bin/env python3
"""
Housecall Pro Price Forms MCP Server
Price book / form management.
"""

from typing import Optional, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Price Forms")


@mcp.tool()
async def get_price_forms(
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
) -> Dict[str, Any]:
    """
    List all price forms / price books.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 50)
    """
    return await api_request("GET", "/api/price_book/price_forms", params={"page": page, "page_size": page_size})


@mcp.tool()
async def get_price_form(price_form_id: str) -> Dict[str, Any]:
    """
    Get a specific price form by ID, including all line items.

    Args:
        price_form_id: Price form UUID
    """
    return await api_request("GET", f"/api/price_book/price_forms/{price_form_id}")


@mcp.tool()
async def get_price_book_services(
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
    expand: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List price book services (the service catalog, with default pricing).

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 50)
        expand: Comma-separated: service_materials, service_labor_rates.
                Both are returned as empty data arrays unless requested here —
                ask for service_labor_rates to see standard hours/rates per service.
    """
    params: Dict[str, Any] = {"page": page, "page_size": page_size}
    if wanted := [v.strip() for v in (expand or "").split(",") if v.strip()]:
        params["expand[]"] = wanted
    return await api_request("GET", "/api/price_book/services", params=params)


if __name__ == "__main__":
    mcp.run()
