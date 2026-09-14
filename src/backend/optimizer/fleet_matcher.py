"""
Fleet Matcher — multi-criteria fleet asset scoring.

Formula (docs/architecture.md — canonical):
    Score_fleet = 0.30 × Proximity
                + 0.25 × Cargo Compatibility
                + 0.20 × Refrigeration Match
                + 0.15 × Capacity Match
                + 0.10 × Availability

Higher score = better match.

Weight invariant: 0.30 + 0.25 + 0.20 + 0.15 + 0.10 == 1.00

No FastAPI, Pydantic, MCP, or watsonx.ai imports are allowed here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.orm import Session

from src.backend.models.fleet_asset import FleetAsset
from src.backend.models.shipment import Shipment
from src.backend.models.telemetry import Telemetry
from src.backend.risk_engine.haversine import haversine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fleet formula weights — must sum to 1.00
# ---------------------------------------------------------------------------
W_PROXIMITY: float = 0.30
W_CARGO_COMPAT: float = 0.25
W_REFRIGERATION: float = 0.20
W_CAPACITY: float = 0.15
W_AVAILABILITY: float = 0.10

assert abs(
    (W_PROXIMITY + W_CARGO_COMPAT + W_REFRIGERATION + W_CAPACITY + W_AVAILABILITY) - 1.0
) < 1e-9, "Fleet matcher weights must sum to 1.0"

# ---------------------------------------------------------------------------
# MD-06 — Fleet cooling capability classification
# ---------------------------------------------------------------------------

class CoolingCapability(str, Enum):
    """Inferred cooling tier for a fleet asset."""
    ULTRA_COLD = "ULTRA_COLD"
    STANDARD_COLD = "STANDARD_COLD"
    AMBIENT = "AMBIENT"


_ULTRA_COLD_KEYWORDS = ["nitrogen", "cryo", "liquid"]
_STANDARD_COLD_KEYWORDS = ["transicold", "thermo king", "reefer"]


def classify_cooling_capability(cooling_system_type: str | None) -> CoolingCapability:
    """
    Classify a fleet asset's cooling capability from its free-text
    ``cooling_system_type`` field (MD-06).
    """
    if cooling_system_type is None:
        return CoolingCapability.AMBIENT
    normalized = cooling_system_type.lower()
    if any(kw in normalized for kw in _ULTRA_COLD_KEYWORDS):
        return CoolingCapability.ULTRA_COLD
    if any(kw in normalized for kw in _STANDARD_COLD_KEYWORDS):
        return CoolingCapability.STANDARD_COLD
    return CoolingCapability.AMBIENT


# ---------------------------------------------------------------------------
# MD-06 — Cooling compatibility matrix
#   Key: (CoolingCapability, temp_bucket)
#   temp_bucket: "cryo" (≤ -50), "frozen" (-50 to 0), "ambient_or_chilled" (> 0)
# ---------------------------------------------------------------------------

def _temp_bucket(required_temp_max_c: float) -> str:
    if required_temp_max_c <= -50.0:
        return "cryo"
    if required_temp_max_c <= 0.0:
        return "frozen"
    return "ambient_or_chilled"


_COOLING_COMPAT_MATRIX: dict[tuple[str, str], float] = {
    (CoolingCapability.ULTRA_COLD,    "cryo"):              1.0,
    (CoolingCapability.ULTRA_COLD,    "frozen"):            0.6,
    (CoolingCapability.ULTRA_COLD,    "ambient_or_chilled"): 0.3,
    (CoolingCapability.STANDARD_COLD, "cryo"):              0.1,
    (CoolingCapability.STANDARD_COLD, "frozen"):            1.0,
    (CoolingCapability.STANDARD_COLD, "ambient_or_chilled"): 0.8,
    (CoolingCapability.AMBIENT,       "cryo"):              0.0,
    (CoolingCapability.AMBIENT,       "frozen"):            0.1,
    (CoolingCapability.AMBIENT,       "ambient_or_chilled"): 1.0,
}


# ---------------------------------------------------------------------------
# MD-06 — Refrigeration match matrix
#   Based on cargo_category (grade string)
# ---------------------------------------------------------------------------

def _refrigeration_score(
    capability: CoolingCapability, cargo_category: str
) -> float:
    """
    Return refrigeration alignment score based on cooling capability and
    cargo category (the grade string from Shipment.cargo_category).
    """
    cat = cargo_category.lower()
    if capability == CoolingCapability.AMBIENT:
        # Ambient reefer is only suitable for non-cold-chain cargo
        cold_keywords = ["cold chain", "frozen", "ultra cold", "perishable", "cryo"]
        if any(kw in cat for kw in cold_keywords):
            return 0.0
        return 1.0

    if capability == CoolingCapability.ULTRA_COLD:
        if "ultra cold" in cat or "cryo" in cat:
            return 1.0
        if "perishable frozen" in cat or "frozen" in cat:
            return 0.5
        # Pharmaceuticals / Cold Chain Grade A
        return 0.4

    # STANDARD_COLD
    if "ultra cold" in cat or "cryo" in cat:
        return 0.0
    if "perishable frozen" in cat or "frozen" in cat:
        return 1.0
    # Pharmaceuticals / Cold Chain Grade A
    return 0.9


# ---------------------------------------------------------------------------
# MD-07 — Capacity estimation by cargo category (kg)
# ---------------------------------------------------------------------------

CATEGORY_ESTIMATED_WEIGHT_KG: dict[str, int] = {
    "Biologics & Vaccines":   500,
    "Ultra Cold Chain":       500,    # same category, different grade name
    "Cold Chain Grade A":   5_000,
    "Pharmaceuticals":      5_000,
    "Perishable Frozen":   15_000,
    "Fresh Seafood":       15_000,
}
DEFAULT_ESTIMATED_WEIGHT_KG: int = 10_000

# ---------------------------------------------------------------------------
# MD fleet GPS gap — proximity calculation
# ---------------------------------------------------------------------------
MAX_PROXIMITY_KM: float = 3_000.0


def _proximity_score(distance_km: float | None) -> float:
    if distance_km is None:
        return 0.0
    return max(0.0, 1.0 - (distance_km / MAX_PROXIMITY_KM))


# ---------------------------------------------------------------------------
# Availability score map
# ---------------------------------------------------------------------------

_AVAILABILITY_SCORE_MAP: dict[str, float] = {
    "IDLE": 1.0,
    "EN_ROUTE": 0.2,
}
_AVAILABILITY_ACTIVE_ASSIGNED: float = 0.3
_AVAILABILITY_ACTIVE_FREE: float = 0.7
_AVAILABILITY_DEFAULT: float = 0.1


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FleetMatchScore:
    """Scored fleet asset for a shipment reassignment evaluation."""

    asset_id: str
    vehicle_type: str
    cooling_capability: str          # "ULTRA_COLD" / "STANDARD_COLD" / "AMBIENT"
    total_score: float               # 0–1
    proximity_km: float | None
    proximity_score: float
    cargo_compat_score: float
    refrigeration_score: float
    capacity_score: float
    availability_score: float
    estimated_shipment_weight_kg: int
    asset_capacity_kg: int
    recommended: bool


@dataclass
class FleetMatchResult:
    """Result produced by the Fleet Matcher for a single shipment."""

    shipment_id: str
    scored_assets: list[FleetMatchScore]
    no_asset_found: bool
    assessed_at: datetime


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------

class FleetMatcher:
    """
    Scores fleet assets as candidates for emergency reassignment to a shipment.

    Designed to be instantiated per-request with an active SQLAlchemy session.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def match_for_shipment(self, shipment: Shipment) -> FleetMatchResult:
        """
        Score all eligible fleet assets for reassignment to *shipment*.

        Excludes the asset already assigned to the shipment (we are looking
        for a replacement/reinforcement, not the committed vehicle).

        Parameters
        ----------
        shipment :
            ORM ``Shipment`` loaded from the active session.

        Returns
        -------
        FleetMatchResult
        """
        now = datetime.now(tz=timezone.utc)

        # All assets except the one already assigned to this shipment
        all_assets: list[FleetAsset] = self._session.query(FleetAsset).all()
        candidates = [
            a for a in all_assets if a.id != shipment.assigned_vehicle_id
        ]

        if not candidates:
            return FleetMatchResult(
                shipment_id=shipment.id,
                scored_assets=[],
                no_asset_found=True,
                assessed_at=now,
            )

        # Estimated shipment weight (MD-07)
        estimated_weight = CATEGORY_ESTIMATED_WEIGHT_KG.get(
            shipment.cargo_category, DEFAULT_ESTIMATED_WEIGHT_KG
        )

        # Shipment position (for proximity calculation)
        shp_lat = shipment.current_lat
        shp_lon = shipment.current_lon

        scored: list[FleetMatchScore] = []

        for asset in candidates:
            # ----------------------------------------------------------
            # Proximity (weight 0.30) — MD fleet GPS gap
            # ----------------------------------------------------------
            # Attempt 1: FleetAsset.current_lat/lon (runtime GPS)
            # Attempt 2: most recent Telemetry.gps_lat/gps_lon
            asset_lat: float | None = asset.current_lat
            asset_lon: float | None = asset.current_lon

            if asset_lat is None or asset_lon is None:
                tel = (
                    self._session.query(Telemetry)
                    .filter(Telemetry.vehicle_id == asset.id)
                    .order_by(Telemetry.timestamp.desc())
                    .first()
                )
                if tel is not None and tel.gps_lat is not None and tel.gps_lon is not None:
                    asset_lat = tel.gps_lat
                    asset_lon = tel.gps_lon

            if (
                asset_lat is not None
                and asset_lon is not None
                and shp_lat is not None
                and shp_lon is not None
            ):
                distance_km: float | None = haversine(
                    asset_lat, asset_lon, shp_lat, shp_lon
                )
            else:
                distance_km = None
                logger.warning(
                    "Cannot compute proximity for asset %s or shipment %s "
                    "(missing GPS coordinates) — proximity_score = 0.0",
                    asset.id,
                    shipment.id,
                )

            prox_score = _proximity_score(distance_km)

            # ----------------------------------------------------------
            # Cargo compatibility (weight 0.25) — MD-06
            # ----------------------------------------------------------
            capability = classify_cooling_capability(asset.cooling_system_type)
            bucket = _temp_bucket(shipment.required_temp_max_c)
            cargo_compat = _COOLING_COMPAT_MATRIX.get(
                (capability, bucket), 0.0
            )

            # ----------------------------------------------------------
            # Refrigeration match (weight 0.20)
            # ----------------------------------------------------------
            refrig_score = _refrigeration_score(capability, shipment.cargo_category)

            # ----------------------------------------------------------
            # Capacity match (weight 0.15) — MD-07
            # ----------------------------------------------------------
            if asset.capacity_kg < estimated_weight:
                cap_score = asset.capacity_kg / estimated_weight
            else:
                cap_score = 1.0

            # ----------------------------------------------------------
            # Availability (weight 0.10)
            # ----------------------------------------------------------
            status = asset.status
            if status == "IDLE":
                avail_score = _AVAILABILITY_SCORE_MAP["IDLE"]
            elif status == "EN_ROUTE":
                avail_score = _AVAILABILITY_SCORE_MAP["EN_ROUTE"]
            elif status == "ACTIVE":
                # Check if assigned to another shipment
                assigned_to_other = (
                    self._session.query(Shipment)
                    .filter(Shipment.assigned_vehicle_id == asset.id)
                    .first()
                )
                avail_score = (
                    _AVAILABILITY_ACTIVE_ASSIGNED
                    if assigned_to_other
                    else _AVAILABILITY_ACTIVE_FREE
                )
            else:
                avail_score = _AVAILABILITY_DEFAULT

            # ----------------------------------------------------------
            # Total score
            # ----------------------------------------------------------
            total = (
                W_PROXIMITY * prox_score
                + W_CARGO_COMPAT * cargo_compat
                + W_REFRIGERATION * refrig_score
                + W_CAPACITY * cap_score
                + W_AVAILABILITY * avail_score
            )
            total = max(0.0, min(1.0, total))

            scored.append(
                FleetMatchScore(
                    asset_id=asset.id,
                    vehicle_type=asset.vehicle_type,
                    cooling_capability=capability.value,
                    total_score=total,
                    proximity_km=distance_km,
                    proximity_score=prox_score,
                    cargo_compat_score=cargo_compat,
                    refrigeration_score=refrig_score,
                    capacity_score=cap_score,
                    availability_score=avail_score,
                    estimated_shipment_weight_kg=estimated_weight,
                    asset_capacity_kg=asset.capacity_kg,
                    recommended=False,
                )
            )

        if not scored:
            return FleetMatchResult(
                shipment_id=shipment.id,
                scored_assets=[],
                no_asset_found=True,
                assessed_at=now,
            )

        # Mark recommended (highest score)
        best = max(scored, key=lambda s: s.total_score)
        best.recommended = True

        # Sort descending by score
        scored.sort(key=lambda s: s.total_score, reverse=True)

        return FleetMatchResult(
            shipment_id=shipment.id,
            scored_assets=scored,
            no_asset_found=False,
            assessed_at=now,
        )
