#!/usr/bin/env python3
"""
Housecall Pro Company MCP Server
Company / account info retrieval.
"""

from typing import Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Company")


@mcp.tool()
async def get_company() -> Dict[str, Any]:
    """
    Get company/account information including name, address, phone, and settings.
    """
    return await api_request("GET", "/company")


if __name__ == "__main__":
    mcp.run()
