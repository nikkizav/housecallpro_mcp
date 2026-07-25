#!/usr/bin/env python3
"""
Housecall Pro Materials MCP Server
Material catalog management.
"""

from typing import Optional, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Materials")


@mcp.tool()
async def get_materials(
    page: Optional[int] = 1,
    page_size: Optional[int] = 100,
    category_id: Optional[str] = None,
    name: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    List materials in the catalog.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 100)
        category_id: Filter by material category UUID
        name: Filter by material name
        is_active: Filter by active status
    """
    params: dict = {
        "page": page,
        "page_size": page_size,
        "category_id": category_id,
        "name": name,
    }
    if is_active is not None:
        params["is_active"] = is_active
    return await api_request("GET", "/materials", params=params)


@mcp.tool()
async def get_material(material_id: str) -> Dict[str, Any]:
    """
    Get a specific material by ID.

    Args:
        material_id: Material UUID
    """
    return await api_request("GET", f"/materials/{material_id}")


@mcp.tool()
async def create_material(
    name: str,
    unit_cost: Optional[int] = None,
    unit_price: Optional[int] = None,
    unit: Optional[str] = None,
    sku: Optional[str] = None,
    description: Optional[str] = None,
    category_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new material in the catalog.

    Args:
        name: Material name (required)
        unit_cost: Cost per unit in cents
        unit_price: Sell price per unit in cents
        unit: Unit of measure (e.g. each, ft, sq ft)
        sku: SKU / part number
        description: Material description
        category_id: Material category UUID
    """
    payload: dict = {"name": name}
    for field in ("unit_cost", "unit_price", "unit", "sku", "description", "category_id"):
        val = locals()[field]
        if val is not None:
            payload[field] = val
    return await api_request("POST", "/materials", json=payload)


@mcp.tool()
async def update_material(
    material_id: str,
    name: Optional[str] = None,
    unit_cost: Optional[int] = None,
    unit_price: Optional[int] = None,
    unit: Optional[str] = None,
    sku: Optional[str] = None,
    description: Optional[str] = None,
    category_id: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Update a material in the catalog.

    Args:
        material_id: Material UUID (required)
        name: New name
        unit_cost: New cost per unit in cents
        unit_price: New sell price per unit in cents
        unit: New unit of measure
        sku: New SKU
        description: New description
        category_id: New category UUID
        is_active: Active status
    """
    payload: dict = {}
    for field in ("name", "unit_cost", "unit_price", "unit", "sku", "description", "category_id"):
        val = locals()[field]
        if val is not None:
            payload[field] = val
    if is_active is not None:
        payload["is_active"] = is_active
    return await api_request("PUT", f"/materials/{material_id}", json=payload)


if __name__ == "__main__":
    mcp.run()
