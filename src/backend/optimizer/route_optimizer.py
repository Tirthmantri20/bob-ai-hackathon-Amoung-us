"""
Route Optimizer — multi-criteria route scoring.

Formula (docs/architecture.md — canonical, MD-02):
    Score_route = 0.30 × (1 - ETA_hat)
                + 0.20 × (1 - Cost_hat)
                + 0.25 × (1 - E_disruption_hat)
                + 0.15 × (1 - E_weather_hat)
                + 0.10 × (1 - E_cold_chain_hat)

Higher score = preferred route.

Weight invariant: 0.30 + 0.20 + 0.25 + 0.15 + 0.10 == 1.00

No FastAPI, Pydantic, MCP, or watsonx.ai imports are allowed here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.backend.models.disruption import Disruption
from src.backend.models.route import Route
from src.backend.models.shipment import Shipment
from src.backend.models.weather import Weather
from src.backend.optimizer.normalizer import min_max_normalize
from src.backend.risk_engine.sub_scores import (
    DISRUPTION_RADIUS_KM,
    ROAD_CONDITION_RISK_MAP,
    SEVERITY_WEIGHT_MAP,
    _DEFAULT_DISRUPTION_RADIUS_KM,
    _DEFAULT_ROAD_CONDITION_RISK,
    _DEFAULT_SEVERITY_WEIGHT,
    _delay_factor,
    _severity_weight,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Route formula weights — must sum to 1.00
# ---------------------------------------------------------------------------
W_ETA: float = 0.30
W_COST: float = 0.20
W_DISRUPTION: float = 0.25
W_WEATHER: float = 0.15
W_COLD_CHAIN: float = 0.10

assert abs((W_ETA + W_COST + W_DISRUPTION + W_WEATHER + W_COLD_CHAIN) - 1.0) < 1e-9, (
    "Route optimizer weights must sum to 1.0"
)

# Heat-risk constants (same as sub_scores.py)
_HEAT_STRESS_BASELINE_C: float = 20.0
_HEAT_STRESS_RANGE_C: float = 20.0

# Weather factor sub-weights for route optimizer (§5.6)
_ROUTE_WEATHER_ROAD_W: float = 0.6
_ROUTE_WEATHER_PRECIP_W: float = 0.4


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RouteScore:
    """Scored candidate route for a shipment."""

    route_id: str
    route_name: str
    total_score: float              # 0–1, higher = better
    eta_hours: float                # raw ETA including disruption delay
    eta_factor: float               # min-max normalized, 0–1
    cost_factor: float              # min-max normalized, 0–1
    disruption_factor: float        # min-max normalized, 0–1
    weather_factor: float           # min-max normalized, 0–1
    cold_chain_factor: float        # min-max normalized, 0–1
    recommended: bool               # True for the highest-scoring route
    warnings: list[str] = field(default_factory=list)


@dataclass
class RouteOptimizerResult:
    """Result produced by the Route Optimizer for a single shipment."""

    shipment_id: str
    scored_routes: list[RouteScore]
    no_route_found: bool
    assessed_at: datetime


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

class RouteOptimizer:
    """
    Scores candidate routes for a shipment using a five-factor weighted formula.

    Designed to be instantiated per-request with an active SQLAlchemy session.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def optimize_for_shipment(self, shipment: Shipment) -> RouteOptimizerResult:
        """
        Score all routes matching the shipment's origin/destination and return
        a ranked ``RouteOptimizerResult``.

        Parameters
        ----------
        shipment :
            ORM ``Shipment`` loaded from the active session.

        Returns
        -------
        RouteOptimizerResult
        """
        now = datetime.now(tz=timezone.utc)

        # MD-05: exact string equality
        candidates: list[Route] = (
            self._session.query(Route)
            .filter(
                Route.origin == shipment.origin,
                Route.destination == shipment.destination,
            )
            .all()
        )

        if not candidates:
            logger.warning(
                "No routes found for shipment %s (%r → %r)",
                shipment.id,
                shipment.origin,
                shipment.destination,
            )
            return RouteOptimizerResult(
                shipment_id=shipment.id,
                scored_routes=[],
                no_route_found=True,
                assessed_at=now,
            )

        disruptions: list[Disruption] = self._session.query(Disruption).all()
        weather_stations: list[Weather] = self._session.query(Weather).all()

        is_cold_chain = shipment.required_temp_max_c < 10.0

        # ------------------------------------------------------------------
        # Compute raw factors for each candidate
        # ------------------------------------------------------------------
        raw_etas: list[float] = []
        raw_costs: list[float] = []
        raw_disruptions: list[float] = []
        raw_weathers: list[float] = []
        raw_cold_chains: list[float] = []
        route_warnings: list[list[str]] = []

        for route in candidates:
            highways_lower = [h.lower() for h in route.get_highways_list()]

            # ETA factor (§5.3)
            disruption_delay = 0.0
            for dis in disruptions:
                if dis.affected_corridor is None:
                    continue
                corridor_lower = dis.affected_corridor.lower()
                if any(
                    corridor_lower in hw or hw in corridor_lower
                    for hw in highways_lower
                ):
                    disruption_delay += (dis.impact_delay_hours or 0.0)
            raw_eta = route.typical_duration_hours + disruption_delay
            raw_etas.append(raw_eta)

            # Cost factor: MD-03 — distance_km proxy
            raw_costs.append(route.distance_km)

            # Disruption exposure (§5.5) — same severity×delay sum as R_disruption
            exp_disruption = 0.0
            for dis in disruptions:
                if dis.affected_corridor is None:
                    continue
                corridor_lower = dis.affected_corridor.lower()
                if any(
                    corridor_lower in hw or hw in corridor_lower
                    for hw in highways_lower
                ):
                    exp_disruption += _severity_weight(dis) * _delay_factor(dis)
            raw_disruptions.append(min(exp_disruption, 1.0))

            # Weather exposure (§5.6) — worst road condition among all stations
            # (no geometry on Weather — same conservative approach as sub_scores)
            raw_exp_weather = 0.0
            if weather_stations:
                best_road_risk = max(
                    ROAD_CONDITION_RISK_MAP.get(
                        wx.road_condition or "", _DEFAULT_ROAD_CONDITION_RISK
                    )
                    for wx in weather_stations
                )
                best_precip = max(
                    (wx.precipitation_prob_percent or 0) for wx in weather_stations
                ) / 100.0
                raw_exp_weather = (
                    _ROUTE_WEATHER_ROAD_W * best_road_risk
                    + _ROUTE_WEATHER_PRECIP_W * best_precip
                )
            raw_weathers.append(raw_exp_weather)

            # Cold-chain environmental exposure (§5.7)
            raw_cold_chain = 0.0
            if is_cold_chain and weather_stations:
                max_ambient = max(wx.ambient_temp_c for wx in weather_stations)
                heat_stress = max(
                    0.0,
                    (max_ambient - _HEAT_STRESS_BASELINE_C) / _HEAT_STRESS_RANGE_C,
                )
                raw_cold_chain = min(heat_stress, 1.0)
            raw_cold_chains.append(raw_cold_chain)

            # Feasibility warnings (§5.9)
            warnings: list[str] = []
            for wx in weather_stations:
                if wx.road_condition == "ICY_BLOCKED":
                    warnings.append(
                        f"Weather station '{wx.location}' reports ICY_BLOCKED road condition."
                    )
            for dis in disruptions:
                if dis.severity == "CRITICAL" and dis.affected_corridor:
                    corridor_lower = dis.affected_corridor.lower()
                    if any(
                        corridor_lower in hw or hw in corridor_lower
                        for hw in highways_lower
                    ):
                        warnings.append(
                            f"CRITICAL disruption '{dis.id}' affects corridor "
                            f"'{dis.affected_corridor}'."
                        )
            route_warnings.append(warnings)

        # ------------------------------------------------------------------
        # Normalize all factor vectors
        # ------------------------------------------------------------------
        hat_etas = min_max_normalize(raw_etas)
        hat_costs = min_max_normalize(raw_costs)
        hat_disruptions = min_max_normalize(raw_disruptions)
        hat_weathers = min_max_normalize(raw_weathers)
        hat_cold_chains = min_max_normalize(raw_cold_chains)

        # ------------------------------------------------------------------
        # Compute total scores
        # ------------------------------------------------------------------
        scored: list[RouteScore] = []
        for i, route in enumerate(candidates):
            total = (
                W_ETA * (1 - hat_etas[i])
                + W_COST * (1 - hat_costs[i])
                + W_DISRUPTION * (1 - hat_disruptions[i])
                + W_WEATHER * (1 - hat_weathers[i])
                + W_COLD_CHAIN * (1 - hat_cold_chains[i])
            )
            total = max(0.0, min(1.0, total))
            scored.append(
                RouteScore(
                    route_id=route.route_id,
                    route_name=route.name,
                    total_score=total,
                    eta_hours=raw_etas[i],
                    eta_factor=hat_etas[i],
                    cost_factor=hat_costs[i],
                    disruption_factor=hat_disruptions[i],
                    weather_factor=hat_weathers[i],
                    cold_chain_factor=hat_cold_chains[i],
                    recommended=False,
                    warnings=route_warnings[i],
                )
            )

        # Mark recommended (highest score)
        best = max(scored, key=lambda r: r.total_score)
        best.recommended = True

        # Sort descending by score
        scored.sort(key=lambda r: r.total_score, reverse=True)

        return RouteOptimizerResult(
            shipment_id=shipment.id,
            scored_routes=scored,
            no_route_found=False,
            assessed_at=now,
        )
