"""
SupplyGuard MCP — Shipment and Engine Tools (tools 1–6)
=========================================================

These six tools give IBM Bob visibility into shipments and the four
deterministic Step 2 engines.  No scoring, ranking, or database logic
lives here — all computation is delegated to the FastAPI backend via HTTP.

Imports allowed: src.mcp.client only.
Forbidden imports: src.backend.*, SQLAlchemy, ORM models, engine classes.
"""

from __future__ import annotations

from typing import Any, Dict

from src.mcp.client import api_get


def get_active_shipments() -> Dict[str, Any]:
    """
    Retrieve all shipments currently tracked in the SupplyGuard system.

    Returns the full shipment collection including IDs, origin, destination,
    cargo type, cargo category, assigned carrier, current GPS coordinates,
    ETA, and operational status (e.g. IN_TRANSIT, ALERT_DISRUPTION, PENDING,
    DELIVERED). Use this tool first to discover which shipment IDs are
    available before calling other shipment or engine tools.
    """
    return api_get("/api/shipments/")


def get_shipment_detail(shipment_id: str) -> Dict[str, Any]:
    """
    Get complete details for a single shipment by its ID (e.g. 'SHP-1001').

    Returns origin, destination, cargo type, cargo category, cargo value,
    required temperature bounds, current GPS position, ETA, assigned carrier,
    and current operational status. Returns an error dict if the shipment ID
    does not exist in the system.
    """
    return api_get(f"/api/shipments/{shipment_id}")


def evaluate_shipment_risk(shipment_id: str) -> Dict[str, Any]:
    """
    Run the deterministic Risk Engine for a shipment and return a composite
    risk score from 0 to 100 with severity classification.

    Severity levels: LOW (0–25), MEDIUM (26–50), HIGH (51–75),
    CRITICAL (76–100). Includes five sub-scores:
      - r_disruption (weight 0.30): proximity to active disruption zones
      - r_weather (weight 0.25): current and forecast weather along the route
      - r_route (weight 0.20): corridor hazard and congestion
      - r_cold_chain (weight 0.15): cold-chain excursion exposure
      - r_business (weight 0.10): cargo value and SLA criticality
    Also lists contributing_disruption_ids. Use this to assess whether a
    shipment needs immediate intervention or rerouting.
    """
    return api_get(f"/api/shipments/{shipment_id}/risk")


def evaluate_cold_chain(shipment_id: str) -> Dict[str, Any]:
    """
    Evaluate cold-chain integrity for a temperature-sensitive shipment.

    Checks the most recent telemetry reading against the cargo's regulatory
    temperature profile (e.g. WHO Grade A Pharma, Ultra-Cold Cryo, FDA HACCP).
    Returns: current cargo temperature (cargo_temp_c), allowed min/max bounds,
    deviation from the allowed range (deviation_c), excursion severity
    (OK, WARNING, HIGH, CRITICAL), is_in_excursion flag, is_destructive flag,
    and compliance_standard. Use this tool when a shipment carries
    pharmaceutical, biological, or perishable frozen cargo.
    """
    return api_get(f"/api/shipments/{shipment_id}/cold-chain")


def get_route_recommendations(shipment_id: str) -> Dict[str, Any]:
    """
    Run the multi-criteria Route Optimizer for a shipment and return ranked
    alternative routes.

    Each route is scored across five factors:
      - ETA (weight 0.30), Cost (0.20), Disruption avoidance (0.25),
        Weather risk (0.15), Cold-chain exposure (0.10).
    The highest-scoring route is flagged recommended=true. Returns
    no_route_found=true (HTTP 200, not an error) if no route corridor in
    the database matches this shipment's exact origin-destination pair.
    Use this when a shipment's primary route is blocked or degraded.
    """
    return api_get(f"/api/shipments/{shipment_id}/routes")


def match_fleet_asset(shipment_id: str) -> Dict[str, Any]:
    """
    Run the Fleet Matcher to find the best idle fleet asset to rescue a
    distressed shipment.

    Scores available assets by: Proximity (0.30), Cargo compatibility (0.25),
    Refrigeration match (0.20), Capacity fit (0.15), Availability (0.10).
    Returns the top-ranked asset flagged recommended=true with proximity_km.
    Returns no_asset_found=true (HTTP 200, not an error) when no suitable idle
    vehicle exists. Use this when a shipment needs emergency cargo transfer
    or vehicle substitution.
    """
    return api_get(f"/api/shipments/{shipment_id}/fleet-match")
