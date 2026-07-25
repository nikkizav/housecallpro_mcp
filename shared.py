#!/usr/bin/env python3
"""
shared.py — Common helpers for all Housecall Pro MCP servers.

Every domain module imports from here:
    from shared import api_request, BASE_URL

This keeps auth, headers, and the HTTP client in one place.
"""

import os
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.housecallpro.com"

_API_KEY = os.getenv("HOUSECALL_PRO_API_KEY")
if not _API_KEY:
    raise RuntimeError(
        "HOUSECALL_PRO_API_KEY environment variable is required. "
        "Add it to a .env file in this directory or set it in the MCP server config."
    )


def get_headers() -> Dict[str, str]:
    """Return the authentication and content headers for every API request."""
    return {
        "Authorization": f"Token {_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def api_request(
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
) -> Any:
    """
    Make an authenticated async HTTP request to the Housecall Pro API.

    Args:
        method:   HTTP verb — GET, POST, PUT, PATCH, DELETE
        endpoint: Path starting with /  e.g. /jobs  or  /jobs/{id}/notes
        params:   Query-string parameters (None values are filtered out automatically)
        json:     Request body as a dict (serialised to JSON)
        timeout:  Request timeout in seconds (default 30)

    Returns:
        Parsed JSON response (dict or list).  Empty-body responses return {}.

    Raises:
        httpx.HTTPStatusError on 4xx / 5xx responses.
    """
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers=get_headers(),
        timeout=timeout,
    ) as client:
        resp = await client.request(method, endpoint, params=clean_params, json=json)
        resp.raise_for_status()
        return resp.json() if resp.content else {}
