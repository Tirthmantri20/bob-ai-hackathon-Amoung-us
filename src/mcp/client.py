"""
SupplyGuard MCP — Shared HTTP Client
=====================================

Single point of truth for all HTTP communication between MCP tool modules
and the FastAPI backend.

Design rules
------------
- This is the ONLY module in src/mcp/ that imports httpx.
- Never imports from src/backend/ (no engine code, no ORM, no DB sessions).
- All MCP tool modules import api_get / api_post from here.
- All logging writes to sys.stderr — stdout is the MCP stdio protocol channel.
- On any failure (network, timeout, 4xx, 5xx) a structured error dict is
  returned rather than raising an exception.  Tools propagate this dict as-is
  so Bob sees a descriptive message rather than an unhandled traceback.

Error dict shape
----------------
{
    "error": True,
    "status_code": int,   # 0 = connection/transport failure
    "detail": str,
}
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict

import httpx

# ---------------------------------------------------------------------------
# Logging — stderr only; stdout is the MCP stdio protocol channel
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s  %(levelname)-8s  mcp.client — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default timeout: 10 s covers connect + read + write + pool.
# Adequate for local API calls including Granite inference latency.
# ---------------------------------------------------------------------------
_TIMEOUT = httpx.Timeout(10.0)

_START_HINT = (
    "FastAPI backend is not available. "
    "Start it with: uvicorn src.backend.main:app --host 0.0.0.0 --port 8000"
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def get_api_url() -> str:
    """Return the FastAPI base URL, stripping any trailing slash."""
    url = os.getenv("SUPPLYGUARD_API_URL", "http://localhost:8000")
    return url.rstrip("/")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def api_get(path: str) -> Dict[str, Any]:
    """
    Perform a GET request to ``get_api_url() + path``.

    Returns the parsed JSON body on HTTP 2xx.
    Returns a structured error dict on any failure — never raises.
    """
    url = get_api_url() + path
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.get(url)
        if response.is_success:
            return response.json()
        detail = response.text[:500]
        logger.warning("api_get %s → HTTP %d: %s", url, response.status_code, detail)
        return {"error": True, "status_code": response.status_code, "detail": detail}
    except (httpx.ConnectError, httpx.ConnectTimeout):
        logger.warning("api_get %s → connection refused / connect timeout", url)
        return {"error": True, "status_code": 0, "detail": _START_HINT}
    except httpx.TimeoutException:
        logger.warning("api_get %s → request timed out after 10 s", url)
        return {"error": True, "status_code": 0, "detail": "Request timed out after 10 seconds."}
    except Exception as exc:  # pragma: no cover
        logger.warning("api_get %s → unexpected error: %s", url, exc)
        return {"error": True, "status_code": 0, "detail": str(exc)}


def api_post(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform a POST request to ``get_api_url() + path`` with a JSON body.

    Returns the parsed JSON body on HTTP 2xx.
    Returns a structured error dict on any failure — never raises.
    """
    url = get_api_url() + path
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(url, json=body)
        if response.is_success:
            return response.json()
        detail = response.text[:500]
        logger.warning("api_post %s → HTTP %d: %s", url, response.status_code, detail)
        return {"error": True, "status_code": response.status_code, "detail": detail}
    except (httpx.ConnectError, httpx.ConnectTimeout):
        logger.warning("api_post %s → connection refused / connect timeout", url)
        return {"error": True, "status_code": 0, "detail": _START_HINT}
    except httpx.TimeoutException:
        logger.warning("api_post %s → request timed out after 10 s", url)
        return {"error": True, "status_code": 0, "detail": "Request timed out after 10 seconds."}
    except Exception as exc:  # pragma: no cover
        logger.warning("api_post %s → unexpected error: %s", url, exc)
        return {"error": True, "status_code": 0, "detail": str(exc)}
