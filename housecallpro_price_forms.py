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
    return await api_request("GET", "/price_forms", params={"page": page, "page_size": page_size})


@mcp.tool()
async def get_price_form(price_form_id: str) -> Dict[str, Any]:
    """
    Get a specific price form by ID, including all line items.

    Args:
        price_form_id: Price form UUID
    """
    return await api_request("GET", f"/price_forms/{price_form_id}")


if __name__ == "__main__":
    mcp.run()
