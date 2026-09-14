"""
Evidence Builder — Step 4 AI Explanation Layer

Converts Step 2 engine result dicts (produced via dataclasses.asdict()) and
minimal ORM-derived attribute dicts into tightly-scoped, JSON-serialisable
evidence dicts suitable for inclusion in a watsonx.ai prompt.

Design constraints
------------------
- Accepts only plain dicts — never ORM objects, never SQLAlchemy sessions.
- Never queries the database.
- Risk scores use the ENGINE output scale (0–100) from ShipmentRiskResult,
  NOT Shipment.current_risk_score (0–1 DB column).  See MD-09.
- If an optional sub-field is absent (e.g. top_route when no routes found),
  its key is set to None rather than omitted.
- All values must be JSON-serialisable (no datetime objects in evidence;
  convert to ISO string if needed).
- No imports from ibm_watsonx_ai, FastAPI, Pydantic, or engine modules.

Note on Enum serialisation
--------------------------
dataclasses.asdict() in Python 3.11+ does NOT convert str-Enum subclasses to
plain strings — it preserves the Enum instance.  _sev() extracts .value when
the field is an Enum, falling back to plain str() for everything else.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enum-safe severity extractor
# ---------------------------------------------------------------------------

def _sev(value: Any) -> str:
    """
    Return the plain string value of a severity field.

    dataclasses.asdict() preserves str-Enum instances rather than converting
    them to plain strings, so 'severity' fields from engine result dicts may
    arrive as RiskSeverity.MEDIUM / ColdChainSeverity.WARNING instead of
    'MEDIUM' / 'WARNING'.  This helper normalises either form.
    """
    if isinstance(value, Enum):
        return value.value
    return str(value) if value is not None else "UNKNOWN"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _top_route(scored_routes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the first recommended RouteScore dict, or the first overall."""
    if not scored_routes:
        return None
    for r in scored_routes:
        if r.get("recommended"):
            return {
                "route_id": r.get("route_id"),
                "route_name": r.get("route_name"),
                "total_score": r.get("total_score"),
                "eta_hours": r.get("eta_hours"),
                "disruption_factor": r.get("disruption_factor"),
                "weather_factor": r.get("weather_factor"),
                "cold_chain_factor": r.get("cold_chain_factor"),
                "warnings": r.get("warnings", []),
                "recommended": True,
            }
    return None


def _top_fleet_asset(scored_assets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the first recommended FleetMatchScore dict, or the first overall."""
    if not scored_assets:
        return None
    for a in scored_assets:
        if a.get("recommended"):
            return {
                "asset_id": a.get("asset_id"),
                "vehicle_type": a.get("vehicle_type"),
                "cooling_capability": a.get("cooling_capability"),
                "total_score": a.get("total_score"),
                "proximity_km": a.get("proximity_km"),
                "cargo_compat_score": a.get("cargo_compat_score"),
                "refrigeration_score": a.get("refrigeration_score"),
                "recommended": True,
            }
    return None


# ---------------------------------------------------------------------------
# Public builders — one per use case
# ---------------------------------------------------------------------------

def build_shipment_risk_evidence(
    risk_dict: Dict[str, Any],
    cold_chain_dict: Dict[str, Any],
    route_dict: Dict[str, Any],
    fleet_dict: Dict[str, Any],
    shipment_attrs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build evidence for the "shipment_risk" use case.

    Parameters
    ----------
    risk_dict        : dataclasses.asdict(ShipmentRiskResult)
    cold_chain_dict  : dataclasses.asdict(ExcursionResult)
    route_dict       : dataclasses.asdict(RouteOptimizerResult)
    fleet_dict       : dataclasses.asdict(FleetMatchResult)
    shipment_attrs   : plain dict with id, origin, destination,
                       cargo_type, cargo_category from the Shipment ORM row

    Returns
    -------
    JSON-serialisable dict
    """
    scored_routes: List[Dict] = route_dict.get("scored_routes") or []
    scored_assets: List[Dict] = fleet_dict.get("scored_assets") or []

    cold = {
        "is_in_excursion": cold_chain_dict.get("is_in_excursion"),
        "is_destructive": cold_chain_dict.get("is_destructive"),
        "severity": _sev(cold_chain_dict.get("severity")),
        "cargo_temp_c": cold_chain_dict.get("cargo_temp_c"),
        "allowed_min_c": cold_chain_dict.get("allowed_min_c"),
        "allowed_max_c": cold_chain_dict.get("allowed_max_c"),
        "deviation_c": cold_chain_dict.get("deviation_c"),
        "compliance_standard": cold_chain_dict.get("compliance_standard"),
    }

    return {
        "use_case": "shipment_risk",
        "entity_id": risk_dict.get("shipment_id"),
        "cargo_type": shipment_attrs.get("cargo_type"),
        "cargo_category": shipment_attrs.get("cargo_category"),
        "origin": shipment_attrs.get("origin"),
        "destination": shipment_attrs.get("destination"),
        # Engine score 0–100 (MD-09: never use Shipment.current_risk_score 0–1)
        "risk_score": risk_dict.get("total_score"),
        "severity": _sev(risk_dict.get("severity")),
        "sub_scores": {
            "r_disruption": risk_dict.get("r_disruption"),
            "r_weather": risk_dict.get("r_weather"),
            "r_route": risk_dict.get("r_route"),
            "r_cold_chain": risk_dict.get("r_cold_chain"),
            "r_business": risk_dict.get("r_business"),
        },
        "contributing_disruption_ids": risk_dict.get("contributing_disruption_ids") or [],
        "cold_chain": cold,
        "top_route": _top_route(scored_routes),
        "no_route_found": route_dict.get("no_route_found"),
        "top_fleet_asset": _top_fleet_asset(scored_assets),
        "no_asset_found": fleet_dict.get("no_asset_found"),
    }


def build_cold_chain_evidence(
    cold_chain_dict: Dict[str, Any],
    shipment_attrs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build evidence for the "cold_chain" use case.

    Parameters
    ----------
    cold_chain_dict : dataclasses.asdict(ExcursionResult)
    shipment_attrs  : plain dict with id, cargo_type, cargo_category
    """
    return {
        "use_case": "cold_chain",
        "entity_id": cold_chain_dict.get("shipment_id"),
        "cargo_category": shipment_attrs.get("cargo_category"),
        "cargo_type": shipment_attrs.get("cargo_type"),
        "compliance_standard": cold_chain_dict.get("compliance_standard"),
        "is_in_excursion": cold_chain_dict.get("is_in_excursion"),
        "is_destructive": cold_chain_dict.get("is_destructive"),
        "severity": _sev(cold_chain_dict.get("severity")),
        "cargo_temp_c": cold_chain_dict.get("cargo_temp_c"),
        "allowed_min_c": cold_chain_dict.get("allowed_min_c"),
        "allowed_max_c": cold_chain_dict.get("allowed_max_c"),
        "max_allowable_excursion_temp_c": cold_chain_dict.get(
            "max_allowable_excursion_temp_c"
        ),
        "deviation_c": cold_chain_dict.get("deviation_c"),
        "cargo_rule_found": cold_chain_dict.get("cargo_rule_found"),
    }


def build_route_recommendation_evidence(
    route_dict: Dict[str, Any],
    shipment_attrs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build evidence for the "route_recommendation" use case.

    Parameters
    ----------
    route_dict     : dataclasses.asdict(RouteOptimizerResult)
    shipment_attrs : plain dict with id, origin, destination, cargo_type
    """
    scored_routes: List[Dict] = route_dict.get("scored_routes") or []
    route_summaries = [
        {
            "route_name": r.get("route_name"),
            "total_score": r.get("total_score"),
            "eta_hours": r.get("eta_hours"),
            "disruption_factor": r.get("disruption_factor"),
            "weather_factor": r.get("weather_factor"),
            "cold_chain_factor": r.get("cold_chain_factor"),
            "recommended": r.get("recommended"),
            "warnings": r.get("warnings", []),
        }
        for r in scored_routes
    ]

    return {
        "use_case": "route_recommendation",
        "entity_id": route_dict.get("shipment_id"),
        "cargo_type": shipment_attrs.get("cargo_type"),
        "origin": shipment_attrs.get("origin"),
        "destination": shipment_attrs.get("destination"),
        "no_route_found": route_dict.get("no_route_found"),
        "route_count": len(scored_routes),
        "scored_routes": route_summaries,
        # Convenience field: the recommended route for easy prompt reference
        "top_route": _top_route(scored_routes),
        # severity is not directly available from RouteOptimizer;
        # use a neutral value — the router will set it from context
        "severity": "INFO",
    }


def build_fleet_match_evidence(
    fleet_dict: Dict[str, Any],
    shipment_attrs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build evidence for the "fleet_match" use case.

    Parameters
    ----------
    fleet_dict     : dataclasses.asdict(FleetMatchResult)
    shipment_attrs : plain dict with id, origin, destination, cargo_category
    """
    scored_assets: List[Dict] = fleet_dict.get("scored_assets") or []
    asset_summaries = [
        {
            "asset_id": a.get("asset_id"),
            "vehicle_type": a.get("vehicle_type"),
            "cooling_capability": a.get("cooling_capability"),
            "total_score": a.get("total_score"),
            "proximity_km": a.get("proximity_km"),
            "cargo_compat_score": a.get("cargo_compat_score"),
            "refrigeration_score": a.get("refrigeration_score"),
            "recommended": a.get("recommended"),
        }
        for a in scored_assets
    ]

    return {
        "use_case": "fleet_match",
        "entity_id": fleet_dict.get("shipment_id"),
        "cargo_category": shipment_attrs.get("cargo_category"),
        "origin": shipment_attrs.get("origin"),
        "destination": shipment_attrs.get("destination"),
        "no_asset_found": fleet_dict.get("no_asset_found"),
        "asset_count": len(scored_assets),
        "scored_assets": asset_summaries,
        "top_fleet_asset": _top_fleet_asset(scored_assets),
        # severity not directly from fleet match; neutral placeholder
        "severity": "INFO",
    }


def build_disruption_impact_evidence(
    disruption_impact_dict: Dict[str, Any],
    disruption_attrs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build evidence for the "disruption_impact" use case.

    Parameters
    ----------
    disruption_impact_dict : dict with keys matching DisruptionImpactResponse
                             (computed inline from the disruption proximity check)
    disruption_attrs       : plain dict with id, type, severity, description,
                             affected_corridor from the Disruption ORM row
    """
    affected: List[Dict] = disruption_impact_dict.get("affected_shipments") or []
    return {
        "use_case": "disruption_impact",
        "entity_id": disruption_impact_dict.get("disruption_id"),
        "disruption_type": disruption_impact_dict.get("disruption_type"),
        "disruption_severity": disruption_impact_dict.get("disruption_severity"),
        "severity": str(disruption_impact_dict.get("disruption_severity", "UNKNOWN")),
        "proximity_radius_km": disruption_impact_dict.get("proximity_radius_km"),
        "affected_count": len(affected),
        "affected_shipments": [
            {
                "shipment_id": s.get("shipment_id"),
                "shipment_status": s.get("shipment_status"),
                "distance_km": s.get("distance_km"),
            }
            for s in affected
        ],
        "affected_corridor": disruption_attrs.get("affected_corridor"),
        "description": disruption_attrs.get("description"),
    }
