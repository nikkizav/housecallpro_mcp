#!/usr/bin/env python3
"""
Housecall Pro Lead Sources MCP Server
Read-only access to configured lead sources.
"""

from typing import Optional, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Lead Sources")


@mcp.tool()
async def get_lead_sources(
    page: Optional[int] = 1,
    page_size: Optional[int] = 100,
) -> Dict[str, Any]:
    """
    List all configured lead sources.

    Use this to see valid lead source names before doing attribution analysis
    or reconciliation. Returns name, ID, and whether the source is user-editable.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 100)
    """
    return await api_request("GET", "/lead_sources", params={"page": page, "page_size": page_size})


if __name__ == "__main__":
    mcp.run()
