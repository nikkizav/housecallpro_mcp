#!/usr/bin/env python3
"""
Housecall Pro Customers MCP Server
Provides customer management: list, get, create, update, addresses.
"""

import json
from typing import Optional, List

from mcp.server.fastmcp import FastMCP
from shared import api_request

mcp = FastMCP("Housecall Pro Customers")


@mcp.tool()
async def get_customers(
    page: Optional[int] = 1,
    page_size: Optional[int] = 25,
    q: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company_name: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_direction: Optional[str] = "desc",
) -> dict:
    """
    List / search customers.

    Args:
        page: Page number (default 1)
        page_size: Results per page (default 25, max 200)
        q: Free-text search — name, email, phone, or address
        email: Filter by email
        phone: Filter by phone number
        company_name: Filter by company name
        first_name: Filter by first name
        last_name: Filter by last name
        sort_by: Field to sort by (default: created_at)
        sort_direction: asc or desc (default: desc)
    """
    params = {
        "page": page,
        "page_size": page_size,
        "q": q,
        "email": email,
        "phone": phone,
        "company_name": company_name,
        "first_name": first_name,
        "last_name": last_name,
        "sort_by": sort_by,
        "sort_direction": sort_direction,
    }
    return await api_request("GET", "/customers", params=params)


@mcp.tool()
async def get_customer(customer_id: str) -> dict:
    """
    Get full details for a single customer including addresses and lead source.

    Args:
        customer_id: Customer UUID
    """
    return await api_request("GET", f"/customers/{customer_id}")


@mcp.tool()
async def create_customer(
    first_name: str,
    last_name: str,
    email: Optional[str] = None,
    mobile_number: Optional[str] = None,
    home_number: Optional[str] = None,
    work_number: Optional[str] = None,
    company: Optional[str] = None,
    is_commercial: Optional[bool] = False,
    notifications_enabled: Optional[bool] = True,
    lead_source: Optional[str] = None,
    notes: Optional[str] = None,
    street: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip: Optional[str] = None,
) -> dict:
    """
    Create a new customer.

    Args:
        first_name: First name (required)
        last_name: Last name (required)
        email: Email address
        mobile_number: Mobile phone (digits only, e.g. 3145551234)
        home_number: Home phone
        work_number: Work phone
        company: Company name (for commercial accounts)
        is_commercial: True for commercial customers (default False)
        notifications_enabled: Enable customer notifications (default True)
        lead_source: How this customer was acquired
        notes: Internal notes about this customer
        street: Service address street
        city: Service address city
        state: Service address state (2-letter code)
        zip: Service address ZIP
    """
    payload: dict = {
        "first_name": first_name,
        "last_name": last_name,
        "notifications_enabled": notifications_enabled,
    }
    for field in ("email", "mobile_number", "home_number", "work_number", "company", "lead_source", "notes"):
        val = locals()[field]
        if val:
            payload[field] = val
    if is_commercial is not None:
        payload["is_commercial"] = is_commercial
    address = {k: locals()[k] for k in ("street", "city", "state", "zip") if locals()[k]}
    if address:
        payload["addresses"] = [address]
    return await api_request("POST", "/customers", json=payload)


@mcp.tool()
async def update_customer(
    customer_id: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    mobile_number: Optional[str] = None,
    home_number: Optional[str] = None,
    work_number: Optional[str] = None,
    company: Optional[str] = None,
    is_commercial: Optional[bool] = None,
    notifications_enabled: Optional[bool] = None,
    lead_source: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """
    Update an existing customer. Only provided fields are changed.

    Args:
        customer_id: Customer UUID (required)
        first_name: New first name
        last_name: New last name
        email: New email
        mobile_number: New mobile number
        home_number: New home number
        work_number: New work number
        company: New company name
        is_commercial: Commercial status
        notifications_enabled: Notification preference
        lead_source: Lead source
        notes: Internal notes
    """
    payload: dict = {}
    for field in ("first_name", "last_name", "email", "mobile_number", "home_number",
                  "work_number", "company", "lead_source", "notes"):
        val = locals()[field]
        if val is not None:
            payload[field] = val
    for bool_field in ("is_commercial", "notifications_enabled"):
        val = locals()[bool_field]
        if val is not None:
            payload[bool_field] = val
    return await api_request("PUT", f"/customers/{customer_id}", json=payload)


@mcp.tool()
async def get_customer_addresses(customer_id: str) -> dict:
    """
    Get all addresses for a customer.

    Args:
        customer_id: Customer UUID
    """
    return await api_request("GET", f"/customers/{customer_id}/addresses")


@mcp.tool()
async def create_customer_address(
    customer_id: str,
    street: str,
    city: str,
    state: str,
    zip: str,
    country: Optional[str] = "US",
    type: Optional[str] = "service",
    notes: Optional[str] = None,
    contact_name: Optional[str] = None,
    contact_phone: Optional[str] = None,
    is_primary: Optional[bool] = False,
) -> dict:
    """
    Add a new address to a customer.

    Args:
        customer_id: Customer UUID (required)
        street: Street address (required)
        city: City (required)
        state: State (required)
        zip: ZIP code (required)
        country: Country code (default: US)
        type: Address type — service or billing (default: service)
        notes: Notes about this address
        contact_name: On-site contact name
        contact_phone: On-site contact phone
        is_primary: Set as primary address (default False)
    """
    payload: dict = {
        "street": street,
        "city": city,
        "state": state,
        "zip": zip,
        "country": country,
        "type": type,
        "is_primary": is_primary,
    }
    for field in ("notes", "contact_name", "contact_phone"):
        val = locals()[field]
        if val:
            payload[field] = val
    return await api_request("POST", f"/customers/{customer_id}/addresses", json=payload)


if __name__ == "__main__":
    mcp.run()
