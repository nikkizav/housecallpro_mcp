#!/usr/bin/env python3
"""
Housecall Pro Application MCP Server
Application / OAuth info for the current API key.
"""

from typing import Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Application")


@mcp.tool()
async def get_application() -> Dict[str, Any]:
    """
    Get information about the current API application / OAuth credentials.
    Returns app name, scopes, and associated company info.
    """
    return await api_request("GET", "/application")


if __name__ == "__main__":
    mcp.run()
