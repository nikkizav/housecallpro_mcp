#!/usr/bin/env python3
"""
Housecall Pro Employees MCP Server
Employee listing, searching, and detail retrieval.
"""

from typing import Optional, Dict, Any

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Employees")


@mcp.tool()
async def get_employees(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    mobile_user: Optional[bool] = None,
    sort_by: Optional[str] = None,
    sort_direction: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List employees with optional filtering.

    Args:
        page: Page number (default 1)
        page_size: Results per page (max 100, default 50)
        role: Filter by role (e.g. technician, admin, manager)
        is_active: Filter by active status
        mobile_user: Filter to mobile app users only
        sort_by: Field to sort by (first_name, last_name, email)
        sort_direction: asc or desc
    """
    params: dict = {}
    if page is not None:
        params["page"] = page
    if page_size is not None:
        params["page_size"] = min(page_size, 100)
    if role is not None:
        params["role"] = role
    if is_active is not None:
        params["is_active"] = str(is_active).lower()
    if mobile_user is not None:
        params["mobile_user"] = str(mobile_user).lower()
    if sort_by is not None:
        params["sort_by"] = sort_by
    if sort_direction is not None:
        params["sort_direction"] = sort_direction
    return await api_request("GET", "/employees", params=params)


@mcp.tool()
async def get_employee(employee_id: str) -> Dict[str, Any]:
    """
    Get a specific employee by ID.

    Args:
        employee_id: Employee UUID
    """
    return await api_request("GET", f"/employees/{employee_id}")


@mcp.tool()
async def get_active_employees(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    sort_by: Optional[str] = "first_name",
    sort_direction: Optional[str] = "asc",
) -> Dict[str, Any]:
    """
    Get all active employees, sorted by first name by default.

    Args:
        page: Page number
        page_size: Results per page (max 100)
        sort_by: Field to sort by (default: first_name)
        sort_direction: asc or desc (default: asc)
    """
    params: dict = {"is_active": "true", "sort_by": sort_by, "sort_direction": sort_direction}
    if page is not None:
        params["page"] = page
    if page_size is not None:
        params["page_size"] = min(page_size, 100)
    return await api_request("GET", "/employees", params=params)


@mcp.tool()
async def search_employees(
    search_term: str,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Search employees by name, email, or phone.

    Args:
        search_term: Text to search (name, email, phone)
        page: Page number
        page_size: Results per page (max 100)
        is_active: Filter by active status
    """
    params: dict = {"search": search_term}
    if page is not None:
        params["page"] = page
    if page_size is not None:
        params["page_size"] = min(page_size, 100)
    if is_active is not None:
        params["is_active"] = str(is_active).lower()
    return await api_request("GET", "/employees", params=params)


if __name__ == "__main__":
    mcp.run()
