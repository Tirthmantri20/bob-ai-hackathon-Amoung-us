"""
SupplyGuard MCP — Disruption Tools (tools 7–8)
================================================

Two tools that expose disruption data and proximity-based impact assessment
to IBM Bob.  All computation is delegated to the FastAPI backend via HTTP.

Imports allowed: src.mcp.client only.
Forbidden imports: src.backend.*, SQLAlchemy, ORM models, engine classes.
"""

from __future__ import annotations

from typing import Any, Dict

from src.mcp.client import api_get


def get_active_disruptions() -> Dict[str, Any]:
    """
    List all infrastructure disruption events tracked in the SupplyGuard system.

    Each disruption includes its ID, type (PORT_CONTAINER_HOLD, SEVERE_WEATHER,
    ROADWORK_CONGESTION), severity, title, affected corridor, geolocation
    (geometry_lat, geometry_lon), and active time window. Use this tool to
    discover which disruption IDs exist before calling get_disruption_impact.
    """
    return api_get("/api/disruptions/")


def get_disruption_impact(disruption_id: str) -> Dict[str, Any]:
    """
    Compute which active in-transit shipments are geographically affected by a
    specific disruption event (e.g. 'DIS-501').

    Uses a type-calibrated proximity radius:
      - SEVERE_WEATHER       → 200 km radius
      - PORT_CONTAINER_HOLD  → 50 km radius
      - ROADWORK_CONGESTION  → 30 km radius
      - default              → 100 km radius
    Returns each affected shipment ID, its current status, and its distance in
    km from the disruption epicentre. Returns an empty affected_shipments list
    (HTTP 200, not an error) if no active shipments fall within the radius.
    Use this to understand the blast radius of a port strike or weather event
    before dispatching mitigation actions.
    """
    return api_get(f"/api/disruptions/{disruption_id}/affected-shipments")
