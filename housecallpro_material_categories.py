#!/usr/bin/env python3
"""
Housecall Pro Material Categories MCP Server
Material category management.
"""

from typing import Optional, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Material Categories")


@mcp.tool()
async def get_material_categories(
    page: Optional[int] = 1,
    page_size: Optional[int] = 100,
) -> Dict[str, Any]:
    """
    List all material categories.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 100)
    """
    return await api_request("GET", "/api/price_book/material_categories", params={"page": page, "page_size": page_size})


@mcp.tool()
async def get_material_category(category_id: str) -> Dict[str, Any]:
    """
    Get a specific material category by ID.

    Args:
        category_id: Material category UUID
    """
    return await api_request("GET", f"/api/price_book/material_categories/{category_id}")


@mcp.tool()
async def create_material_category(
    name: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new material category.

    Args:
        name: Category name (required)
        description: Category description
    """
    payload: dict = {"name": name}
    if description:
        payload["description"] = description
    return await api_request("POST", "/api/price_book/material_categories", json=payload)


@mcp.tool()
async def update_material_category(
    category_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update a material category.

    Args:
        category_id: Category UUID (required)
        name: New name
        description: New description
    """
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    return await api_request("PUT", f"/api/price_book/material_categories/{category_id}", json=payload)


if __name__ == "__main__":
    mcp.run()
