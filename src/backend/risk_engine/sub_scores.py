"""
Risk Engine sub-score calculators.

Each function computes one of the five weighted sub-scores for the Shipment
Risk formula.  All outputs are in [0.0, 1.0].

Centralized constants
---------------------
DISRUPTION_RADIUS_KM      Proximity radius (km) per disruption type (MD-08)
SEVERITY_WEIGHT_MAP       Severity string → numeric weight
ROAD_CONDITION_RISK_MAP   road_condition string → numeric risk (MD-04)
CARGO_URGENCY_MAP         cargo_type string → urgency weight (R_business)

No FastAPI, Pydantic, MCP, or watsonx.ai imports are allowed here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from sqlalchemy.orm import Session

from src.backend.models.disruption import Disruption
from src.backend.models.route import Route
from src.backend.models.shipment import Shipment
from src.backend.models.telemetry import Telemetry
from src.backend.models.weather import Weather
from src.backend.risk_engine.haversine import haversine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MD-08 — Disruption proximity radii (km) per disruption type
# ---------------------------------------------------------------------------
DISRUPTION_RADIUS_KM: dict[str, float] = {
    "SEVERE_WEATHER": 200.0,
    "PORT_CONTAINER_HOLD": 50.0,
    "ROADWORK_CONGESTION": 30.0,
}
_DEFAULT_DISRUPTION_RADIUS_KM: float = 100.0

# ---------------------------------------------------------------------------
# Severity weight map — shared by R_disruption and R_route corridor overlap
# ---------------------------------------------------------------------------
SEVERITY_WEIGHT_MAP: dict[str, float] = {
    "MEDIUM": 0.4,
    "HIGH": 0.7,
    "CRITICAL": 1.0,
}
_DEFAULT_SEVERITY_WEIGHT: float = 0.4

# ---------------------------------------------------------------------------
# MD-04 — Road condition → numeric risk
# ---------------------------------------------------------------------------
ROAD_CONDITION_RISK_MAP: dict[str, float] = {
    "ICY_BLOCKED": 1.0,
    "ICY": 0.8,
    "WET": 0.5,
    "DRY": 0.1,
}
_DEFAULT_ROAD_CONDITION_RISK: float = 0.3

# ---------------------------------------------------------------------------
# R_business — cargo type urgency weights
# ---------------------------------------------------------------------------
CARGO_URGENCY_MAP: dict[str, float] = {
    "Biologics & Vaccines": 1.0,
    "Pharmaceuticals": 0.8,
    "Fresh Seafood": 0.5,
}
_DEFAULT_CARGO_URGENCY: float = 0.3

# Internal R_weather sub-weights (prototype)
_WEATHER_ROAD_W: float = 0.5
_WEATHER_PRECIP_W: float = 0.3
_WEATHER_HEAT_W: float = 0.2

# Heat-risk reference temperature (°C) — ambient above this stresses reefers
_HEAT_STRESS_BASELINE_C: float = 20.0
_HEAT_STRESS_RANGE_C: float = 20.0

# R_weather weather station search radius (km)
WEATHER_STATION_MAX_PROXIMITY_KM: float = 500.0

# R_route duration normalization reference (hours)
_ROUTE_DURATION_REFERENCE_H: float = 48.0

# R_business urgency normalization reference (hours)
_BUSINESS_URGENCY_REFERENCE_H: float = 72.0


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _delay_factor(disruption: Disruption) -> float:
    """Return min(impact_delay_hours / 24.0, 1.0); 0.0 if None."""
    if disruption.impact_delay_hours is None:
        return 0.0
    return min(disruption.impact_delay_hours / 24.0, 1.0)


def _severity_weight(disruption: Disruption) -> float:
    return SEVERITY_WEIGHT_MAP.get(disruption.severity, _DEFAULT_SEVERITY_WEIGHT)


# ---------------------------------------------------------------------------
# Sub-score: R_disruption  (weight 0.30)
# ---------------------------------------------------------------------------

def compute_r_disruption(
    shipment: Shipment, session: Session
) -> tuple[float, list[str]]:
    """
    Compute R_disruption for *shipment*.

    Returns
    -------
    (r_disruption, contributing_disruption_ids)
    """
    if shipment.current_lat is None or shipment.current_lon is None:
        logger.warning(
            "Shipment %s has no current coordinates — R_disruption = 0.0",
            shipment.id,
        )
        return 0.0, []

    disruptions: list[Disruption] = session.query(Disruption).all()
    if not disruptions:
        return 0.0, []

    total_score = 0.0
    contributing_ids: list[str] = []

    for dis in disruptions:
        if dis.geometry_lat is None or dis.geometry_lon is None:
            continue

        radius_km = DISRUPTION_RADIUS_KM.get(dis.type, _DEFAULT_DISRUPTION_RADIUS_KM)
        distance_km = haversine(
            dis.geometry_lat, dis.geometry_lon,
            shipment.current_lat, shipment.current_lon,
        )

        if distance_km > radius_km:
            continue

        score_i = _severity_weight(dis) * _delay_factor(dis)
        total_score += score_i
        contributing_ids.append(dis.id)

    r_disruption = min(total_score, 1.0)
    return r_disruption, contributing_ids


# ---------------------------------------------------------------------------
# Sub-score: R_weather  (weight 0.25)
# ---------------------------------------------------------------------------

def compute_r_weather(
    shipment: Shipment, session: Session
) -> tuple[float, bool]:
    """
    Compute R_weather for *shipment*.

    Returns
    -------
    (r_weather, weather_fallback)
        weather_fallback is True if no weather station was found within range.
    """
    if shipment.current_lat is None or shipment.current_lon is None:
        logger.warning(
            "Shipment %s has no current coordinates — R_weather = 0.0",
            shipment.id,
        )
        return 0.0, True

    stations: list[Weather] = session.query(Weather).all()
    if not stations:
        return 0.0, True

    # Find closest station
    closest: Weather | None = None
    closest_dist = float("inf")
    for wx in stations:
        # Weather has no lat/lon columns; we approximate from location string.
        # The plan calls for proximity to shipment position using Weather coords.
        # Weather model has no lat/lon — use the disruption fallback approach:
        # since Weather has no coordinates, we use station location name proximity.
        # Per plan §3.4: "Find the closest weather station to the shipment's
        # current position using Haversine distance."
        # Weather table has no geometry columns.  We must infer coords from
        # context.  In the fixture data, we know approximate coords for each
        # station from their location names.  However, to stay data-driven
        # we note that Weather has no lat/lon in the ORM.
        # We'll assign all weather stations equal distance 0 so the closest
        # station is the first one, then pick it by index — but that is
        # wrong for real data.
        #
        # CORRECT approach: the plan does NOT require that Weather has a
        # geometry column.  Instead, we use a best-effort: for stations with
        # no geometry, fall back to 0.0 distance so any station is considered
        # "closest".  We iterate all stations and always use the closest one
        # by position.  Since Weather has no lat/lon, we cannot rank them by
        # distance — we use all stations and take the worst-case (max) road_risk
        # to be conservative, or use the first station.
        #
        # Re-reading the plan: Weather has ambient_temp_c, road_condition,
        # precipitation_prob_percent — all needed.  The plan expects a Haversine
        # call.  But Weather ORM has no lat/lon.  The correct resolution is:
        # use station index 0 (all stations are considered equally relevant)
        # since we cannot measure proximity without coordinates.  Log a warning.
        #
        # Actually: re-check the Weather model. It has no lat/lon in the ORM.
        # The fixture also has no lat/lon for weather. So "closest by Haversine"
        # is not possible. The conservative and safe approach is to pick the
        # weather station with the highest road_risk (worst-case), which is
        # operationally correct — we never under-estimate weather risk.
        # This is a prototype limitation acknowledged in step2-assumptions.md.
        #
        # We implement: pick the station with the worst (highest) road_risk.
        break  # exit early — handled below

    # Weather stations have no geometry → use max road_risk across all stations
    # within the dataset (conservative; documented as prototype limitation).
    logger.debug(
        "Weather stations have no geometry columns — using max road_risk "
        "across all %d stations (conservative proxy).",
        len(stations),
    )

    best_wx: Weather | None = None
    best_road_risk = -1.0

    for wx in stations:
        road_risk = ROAD_CONDITION_RISK_MAP.get(
            wx.road_condition or "", _DEFAULT_ROAD_CONDITION_RISK
        )
        if road_risk > best_road_risk:
            best_road_risk = road_risk
            best_wx = wx

    if best_wx is None:
        return 0.0, True

    road_risk = ROAD_CONDITION_RISK_MAP.get(
        best_wx.road_condition or "", _DEFAULT_ROAD_CONDITION_RISK
    )
    precip_risk = (best_wx.precipitation_prob_percent or 0) / 100.0

    # Heat risk for cold-chain shipments
    if shipment.required_temp_max_c < 10.0:
        heat_stress = max(
            0.0,
            (best_wx.ambient_temp_c - _HEAT_STRESS_BASELINE_C) / _HEAT_STRESS_RANGE_C,
        )
        heat_risk = min(heat_stress, 1.0)
    else:
        heat_risk = 0.0

    r_weather = (
        _WEATHER_ROAD_W * road_risk
        + _WEATHER_PRECIP_W * precip_risk
        + _WEATHER_HEAT_W * heat_risk
    )
    return r_weather, False


# ---------------------------------------------------------------------------
# Sub-score: R_route  (weight 0.20)
# ---------------------------------------------------------------------------

def compute_r_route(
    shipment: Shipment, session: Session
) -> tuple[float, bool]:
    """
    Compute R_route for *shipment*.

    Returns
    -------
    (r_route, route_fallback)
        route_fallback is True if no route matched origin/destination.
    """
    # MD-05: exact string equality on origin + destination
    candidates: list[Route] = (
        session.query(Route)
        .filter(
            Route.origin == shipment.origin,
            Route.destination == shipment.destination,
        )
        .all()
    )

    if not candidates:
        logger.warning(
            "No route found for shipment %s (%r → %r) — R_route = 0.5",
            shipment.id,
            shipment.origin,
            shipment.destination,
        )
        return 0.5, True

    route = candidates[0]

    # Duration risk
    duration_risk = min(route.typical_duration_hours / _ROUTE_DURATION_REFERENCE_H, 1.0)

    # Corridor overlap with active disruptions
    disruptions: list[Disruption] = session.query(Disruption).all()
    highway_list = [h.lower() for h in route.get_highways_list()]

    corridor_score = 0.0
    for dis in disruptions:
        if dis.affected_corridor is None:
            continue
        corridor_lower = dis.affected_corridor.lower()
        if any(corridor_lower in hw or hw in corridor_lower for hw in highway_list):
            corridor_score += _severity_weight(dis)

    corridor_overlap = min(corridor_score, 1.0)
    r_route = (0.5 * duration_risk) + (0.5 * corridor_overlap)
    return r_route, False


# ---------------------------------------------------------------------------
# Sub-score: R_cold_chain  (weight 0.15)
# ---------------------------------------------------------------------------

_COLD_CHAIN_SEVERITY_SCORE: dict[str, float] = {
    "OK": 0.0,
    "WARNING": 0.3,
    "HIGH": 0.6,
    "CRITICAL": 1.0,
    "UNKNOWN": 0.0,
}


def compute_r_cold_chain(
    shipment: Shipment, session: Session
) -> tuple[float, bool]:
    """
    Compute R_cold_chain for *shipment* by delegating to ColdChainEngine.

    Returns
    -------
    (r_cold_chain, cold_chain_fallback)
        cold_chain_fallback is True if no telemetry was found.
    """
    # Import here to avoid circular imports (ColdChainEngine → sub_scores would
    # be circular if sub_scores imported ColdChainEngine at module level).
    from src.backend.cold_chain.engine import ColdChainEngine

    engine = ColdChainEngine(session)
    result = engine.evaluate_shipment(shipment)

    if result.telemetry_id is None and result.cargo_rule_found:
        # No telemetry available — fallback
        return 0.0, True

    score = _COLD_CHAIN_SEVERITY_SCORE.get(result.severity.value, 0.0)
    return score, False


# ---------------------------------------------------------------------------
# Sub-score: R_business  (weight 0.10)
# ---------------------------------------------------------------------------

def compute_r_business(shipment: Shipment) -> float:
    """
    Compute R_business for *shipment*.

    Uses cargo type urgency and remaining time-to-delivery as a proxy for
    business exposure.  Returns a value in [0.0, 1.0].
    """
    cargo_urgency = CARGO_URGENCY_MAP.get(shipment.cargo_type, _DEFAULT_CARGO_URGENCY)

    # Time pressure
    if shipment.estimated_arrival is not None:
        now = datetime.now(tz=timezone.utc)
        arrival = shipment.estimated_arrival
        # Make arrival timezone-aware if stored as naive UTC
        if arrival.tzinfo is None:
            arrival = arrival.replace(tzinfo=timezone.utc)
        hours_remaining = (arrival - now).total_seconds() / 3600.0
        urgency = max(0.0, 1.0 - (hours_remaining / _BUSINESS_URGENCY_REFERENCE_H))
    else:
        urgency = 0.0

    r_business = (0.6 * cargo_urgency) + (0.4 * urgency)
    return r_business
