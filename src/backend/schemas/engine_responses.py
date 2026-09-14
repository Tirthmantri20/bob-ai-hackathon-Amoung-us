"""
Engine Response Schemas — Step 3 API Integration Layer

Pydantic v2 response models that serialize the Step 2 @dataclass results
for HTTP JSON output.  These models live exclusively in the API layer;
the Step 2 engines themselves never import Pydantic.

Conversion pattern used in routers:
    import dataclasses
    result = engine.evaluate_shipment(shipment)
    response = ShipmentRiskResponse.model_validate(dataclasses.asdict(result))

All schemas use from_attributes=False (the default) because they are built
from plain dicts produced by dataclasses.asdict(), NOT from ORM objects.

Score scale constraints:
    Risk Engine     → total_score  0–100  (DO NOT write to Shipment.current_risk_score)
    Route Optimizer → total_score  0–1
    Fleet Matcher   → total_score  0–1
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Risk Engine response  (wraps ShipmentRiskResult)
# ---------------------------------------------------------------------------

class ShipmentRiskResponse(BaseModel):
    """
    Serializes ``ShipmentRiskResult`` from ``risk_engine/scorer.py``.

    total_score is on the 0–100 scale as output by the engine.
    It is NOT written back to ``Shipment.current_risk_score`` (0–1 DB field).
    """

    model_config = ConfigDict(from_attributes=False)

    shipment_id: str
    total_score: float = Field(..., ge=0.0, le=100.0)   # 0–100
    severity: str                                         # LOW/MEDIUM/HIGH/CRITICAL
    r_disruption: float = Field(..., ge=0.0, le=1.0)
    r_weather: float = Field(..., ge=0.0, le=1.0)
    r_route: float = Field(..., ge=0.0, le=1.0)
    r_cold_chain: float = Field(..., ge=0.0, le=1.0)
    r_business: float = Field(..., ge=0.0, le=1.0)
    contributing_disruption_ids: List[str]
    weather_fallback: bool
    cold_chain_fallback: bool
    route_fallback: bool
    assessed_at: datetime


# ---------------------------------------------------------------------------
# Cold-Chain Engine response  (wraps ExcursionResult)
# ---------------------------------------------------------------------------

class ColdChainResponse(BaseModel):
    """Serializes ``ExcursionResult`` from ``cold_chain/engine.py``."""

    model_config = ConfigDict(from_attributes=False)

    shipment_id: str
    telemetry_id: Optional[str] = None
    cargo_rule_found: bool
    is_in_excursion: bool
    is_destructive: bool
    cargo_temp_c: Optional[float] = None
    allowed_min_c: Optional[float] = None
    allowed_max_c: Optional[float] = None
    max_allowable_excursion_temp_c: Optional[float] = None
    deviation_c: Optional[float] = None    # positive = too warm; negative = too cold
    severity: str                           # OK/WARNING/HIGH/CRITICAL/UNKNOWN
    excursion_duration_minutes: Optional[int] = None
    compliance_standard: Optional[str] = None
    cargo_category: str
    grade: Optional[str] = None
    assessed_at: datetime


# ---------------------------------------------------------------------------
# Route Optimizer responses  (wrap RouteScore / RouteOptimizerResult)
# ---------------------------------------------------------------------------

class RouteScoreResponse(BaseModel):
    """Serializes ``RouteScore`` from ``optimizer/route_optimizer.py``."""

    model_config = ConfigDict(from_attributes=False)

    route_id: str
    route_name: str
    total_score: float = Field(..., ge=0.0, le=1.0)
    eta_hours: float
    eta_factor: float = Field(..., ge=0.0, le=1.0)
    cost_factor: float = Field(..., ge=0.0, le=1.0)
    disruption_factor: float = Field(..., ge=0.0, le=1.0)
    weather_factor: float = Field(..., ge=0.0, le=1.0)
    cold_chain_factor: float = Field(..., ge=0.0, le=1.0)
    recommended: bool
    warnings: List[str]


class RouteOptimizerResponse(BaseModel):
    """Serializes ``RouteOptimizerResult`` from ``optimizer/route_optimizer.py``."""

    model_config = ConfigDict(from_attributes=False)

    shipment_id: str
    scored_routes: List[RouteScoreResponse]
    no_route_found: bool
    assessed_at: datetime


# ---------------------------------------------------------------------------
# Fleet Matcher responses  (wrap FleetMatchScore / FleetMatchResult)
# ---------------------------------------------------------------------------

class FleetMatchScoreResponse(BaseModel):
    """Serializes ``FleetMatchScore`` from ``optimizer/fleet_matcher.py``."""

    model_config = ConfigDict(from_attributes=False)

    asset_id: str
    vehicle_type: str
    cooling_capability: str                                 # ULTRA_COLD/STANDARD_COLD/AMBIENT
    total_score: float = Field(..., ge=0.0, le=1.0)
    proximity_km: Optional[float] = None
    proximity_score: float = Field(..., ge=0.0, le=1.0)
    cargo_compat_score: float = Field(..., ge=0.0, le=1.0)
    refrigeration_score: float = Field(..., ge=0.0, le=1.0)
    capacity_score: float = Field(..., ge=0.0, le=1.0)
    availability_score: float = Field(..., ge=0.0, le=1.0)
    estimated_shipment_weight_kg: int
    asset_capacity_kg: int
    recommended: bool


class FleetMatchResponse(BaseModel):
    """Serializes ``FleetMatchResult`` from ``optimizer/fleet_matcher.py``."""

    model_config = ConfigDict(from_attributes=False)

    shipment_id: str
    scored_assets: List[FleetMatchScoreResponse]
    no_asset_found: bool
    assessed_at: datetime


# ---------------------------------------------------------------------------
# Disruption impact response  (computed inline in the disruptions router)
# ---------------------------------------------------------------------------

class AffectedShipmentEntry(BaseModel):
    """A single active shipment that falls within a disruption's proximity radius."""

    model_config = ConfigDict(from_attributes=False)

    shipment_id: str
    shipment_status: str
    distance_km: float


class DisruptionImpactResponse(BaseModel):
    """Result of GET /api/disruptions/{disruption_id}/affected-shipments."""

    model_config = ConfigDict(from_attributes=False)

    disruption_id: str
    disruption_type: str
    disruption_severity: str
    proximity_radius_km: float
    affected_shipments: List[AffectedShipmentEntry]
    assessed_at: datetime
