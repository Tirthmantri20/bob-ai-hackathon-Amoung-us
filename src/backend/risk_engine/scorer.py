"""
Risk Engine scorer — orchestrates the five sub-score calculators.

Formula (docs/architecture.md — canonical):
    Risk_score_0_to_1 = 0.30 × R_disruption
                      + 0.25 × R_weather
                      + 0.20 × R_route
                      + 0.15 × R_cold_chain
                      + 0.10 × R_business

    Final_score_0_to_100 = Risk_score_0_to_1 × 100

Weight invariant (must equal 1.00):
    W_DISRUPTION + W_WEATHER + W_ROUTE + W_COLD_CHAIN + W_BUSINESS == 1.00

No FastAPI, Pydantic, MCP, or watsonx.ai imports are allowed here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.orm import Session

from src.backend.models.shipment import Shipment
from src.backend.risk_engine.sub_scores import (
    compute_r_business,
    compute_r_cold_chain,
    compute_r_disruption,
    compute_r_route,
    compute_r_weather,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Formula weights — must sum to exactly 1.00
# ---------------------------------------------------------------------------
W_DISRUPTION: float = 0.30
W_WEATHER: float = 0.25
W_ROUTE: float = 0.20
W_COLD_CHAIN: float = 0.15
W_BUSINESS: float = 0.10

assert (
    abs((W_DISRUPTION + W_WEATHER + W_ROUTE + W_COLD_CHAIN + W_BUSINESS) - 1.0) < 1e-9
), "Risk engine weights must sum to 1.0"

# ---------------------------------------------------------------------------
# Classification thresholds (docs/architecture.md)
# ---------------------------------------------------------------------------
#  0.0 – 25.0 → LOW
# 25.1 – 50.0 → MEDIUM
# 50.1 – 75.0 → HIGH
# 75.1 – 100.0 → CRITICAL


class RiskSeverity(str, Enum):
    """Shipment risk severity classification."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def _classify(score: float) -> RiskSeverity:
    if score <= 25.0:
        return RiskSeverity.LOW
    if score <= 50.0:
        return RiskSeverity.MEDIUM
    if score <= 75.0:
        return RiskSeverity.HIGH
    return RiskSeverity.CRITICAL


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ShipmentRiskResult:
    """
    Structured output of a single shipment risk evaluation.
    """

    shipment_id: str
    total_score: float                     # 0–100
    severity: RiskSeverity                 # LOW / MEDIUM / HIGH / CRITICAL
    r_disruption: float                    # 0–1
    r_weather: float                       # 0–1
    r_route: float                         # 0–1
    r_cold_chain: float                    # 0–1
    r_business: float                      # 0–1
    contributing_disruption_ids: list[str] = field(default_factory=list)
    weather_fallback: bool = False         # True if no weather station data
    cold_chain_fallback: bool = False      # True if no telemetry found
    route_fallback: bool = False           # True if no route matched
    assessed_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RiskEngine:
    """
    Deterministic multi-variable risk scorer for shipments.

    Designed to be instantiated per-request with an active SQLAlchemy session.

    Usage::

        engine = RiskEngine(session)
        result = engine.evaluate_shipment(shipment)
        # or:
        results = engine.evaluate_all_active()
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def evaluate_shipment(self, shipment: Shipment) -> ShipmentRiskResult:
        """
        Evaluate all five risk sub-scores for *shipment* and return a
        ``ShipmentRiskResult``.

        The engine does not persist anything to the database — that is the
        responsibility of the caller (Step 3 API routes).

        Parameters
        ----------
        shipment :
            ORM ``Shipment`` object loaded from the active session.

        Returns
        -------
        ShipmentRiskResult
        """
        now = datetime.now(tz=timezone.utc)

        r_disruption, contributing_ids = compute_r_disruption(
            shipment, self._session
        )
        r_weather, weather_fallback = compute_r_weather(shipment, self._session)
        r_route, route_fallback = compute_r_route(shipment, self._session)
        r_cold_chain, cold_chain_fallback = compute_r_cold_chain(
            shipment, self._session
        )
        r_business = compute_r_business(shipment)

        # Clamp each sub-score to [0, 1] defensively
        r_disruption = max(0.0, min(1.0, r_disruption))
        r_weather = max(0.0, min(1.0, r_weather))
        r_route = max(0.0, min(1.0, r_route))
        r_cold_chain = max(0.0, min(1.0, r_cold_chain))
        r_business = max(0.0, min(1.0, r_business))

        raw_score = (
            W_DISRUPTION * r_disruption
            + W_WEATHER * r_weather
            + W_ROUTE * r_route
            + W_COLD_CHAIN * r_cold_chain
            + W_BUSINESS * r_business
        )
        total_score = max(0.0, min(100.0, raw_score * 100.0))
        severity = _classify(total_score)

        logger.debug(
            "RiskEngine: shipment=%s score=%.1f severity=%s "
            "(disruption=%.3f weather=%.3f route=%.3f cold=%.3f biz=%.3f)",
            shipment.id,
            total_score,
            severity.value,
            r_disruption,
            r_weather,
            r_route,
            r_cold_chain,
            r_business,
        )

        return ShipmentRiskResult(
            shipment_id=shipment.id,
            total_score=total_score,
            severity=severity,
            r_disruption=r_disruption,
            r_weather=r_weather,
            r_route=r_route,
            r_cold_chain=r_cold_chain,
            r_business=r_business,
            contributing_disruption_ids=contributing_ids,
            weather_fallback=weather_fallback,
            cold_chain_fallback=cold_chain_fallback,
            route_fallback=route_fallback,
            assessed_at=now,
        )

    def evaluate_all_active(self) -> list[ShipmentRiskResult]:
        """
        Evaluate all shipments with status ``IN_TRANSIT`` or
        ``ALERT_DISRUPTION``.

        Returns
        -------
        list[ShipmentRiskResult]
        """
        active_statuses = ("IN_TRANSIT", "ALERT_DISRUPTION")
        shipments = (
            self._session.query(Shipment)
            .filter(Shipment.status.in_(active_statuses))
            .all()
        )
        return [self.evaluate_shipment(s) for s in shipments]
