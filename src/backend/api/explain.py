"""
Explain API router — /api/explain/*

Endpoints
---------
POST /api/explain/shipment-risk          Full synthesis: risk + cold-chain + routes + fleet
POST /api/explain/cold-chain             Cold-chain excursion explanation
POST /api/explain/route-recommendation   Route optimizer explanation
POST /api/explain/fleet-match            Fleet asset match explanation
POST /api/explain/disruption-impact      Disruption proximity impact explanation

Orchestration pattern (same for all five endpoints)
----------------------------------------------------
1. Validate request body (FastAPI/Pydantic — 422 on bad input).
2. Fetch required entity from DB (404 if missing).
3. Run deterministic Step 2 engines (same session pattern as Step 3 routers).
4. Build structured evidence dict via evidence_builder.build_*().
5. Call WatsonxService.generate_explanation(use_case, evidence).
6. Return AIExplanationResponse (200 always; fallback if AI unavailable).

Design rules
------------
- No business logic lives in this file.
- The AI service is never called with ORM objects.
- The AI service never touches the database.
- Engine risk score 0–100 is used (not Shipment.current_risk_score 0–1).
- All five endpoints return HTTP 200 even when AI is unavailable.
- 404 is returned only when the requested entity does not exist.
"""

from __future__ import annotations

import dataclasses
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.backend.ai.evidence_builder import (
    build_cold_chain_evidence,
    build_disruption_impact_evidence,
    build_fleet_match_evidence,
    build_route_recommendation_evidence,
    build_shipment_risk_evidence,
)
from src.backend.ai.watsonx_service import WatsonxService
from src.backend.cold_chain.engine import ColdChainEngine
from src.backend.db.database import get_db
from src.backend.models.disruption import Disruption
from src.backend.models.shipment import Shipment
from src.backend.optimizer.fleet_matcher import FleetMatcher
from src.backend.optimizer.route_optimizer import RouteOptimizer
from src.backend.risk_engine.haversine import haversine
from src.backend.risk_engine.scorer import RiskEngine
from src.backend.risk_engine.sub_scores import (
    DISRUPTION_RADIUS_KM,
    _DEFAULT_DISRUPTION_RADIUS_KM,
)
from src.backend.schemas.ai_response import AIExplainRequest, AIExplanationResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency — WatsonxService (injectable for tests)
# ---------------------------------------------------------------------------

def get_watsonx_service(request: Request) -> WatsonxService:
    """
    FastAPI dependency that retrieves the WatsonxService singleton from
    app.state.  Tests replace this via app.dependency_overrides.
    """
    return request.app.state.watsonx_service


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_shipment_or_404(entity_id: str, db: Session) -> Shipment:
    shp = db.get(Shipment, entity_id)
    if shp is None:
        raise HTTPException(
            status_code=404,
            detail=f"Shipment {entity_id!r} not found",
        )
    return shp


def _get_disruption_or_404(entity_id: str, db: Session) -> Disruption:
    dis = db.get(Disruption, entity_id)
    if dis is None:
        raise HTTPException(
            status_code=404,
            detail=f"Disruption {entity_id!r} not found",
        )
    return dis


def _shipment_attrs(shp: Shipment) -> dict:
    """
    Extract the minimal set of Shipment attributes needed by the evidence
    builders.  Never passes the ORM object into the AI package.
    """
    return {
        "id": shp.id,
        "origin": shp.origin,
        "destination": shp.destination,
        "cargo_type": shp.cargo_type,
        "cargo_category": shp.cargo_category,
    }


def _disruption_attrs(dis: Disruption) -> dict:
    """
    Extract the minimal set of Disruption attributes needed by the evidence
    builders.  Never passes the ORM object into the AI package.
    """
    return {
        "id": dis.id,
        "type": dis.type,
        "severity": dis.severity,
        "title": dis.title,
        "affected_corridor": dis.affected_corridor,
        "description": dis.title,  # Disruption has no 'description' column; use title
    }


def _compute_disruption_impact(dis: Disruption, db: Session) -> dict:
    """
    Compute disruption impact inline (same logic as disruptions.py).
    Returns a plain dict matching DisruptionImpactResponse shape.
    """
    from datetime import datetime, timezone

    radius_km = DISRUPTION_RADIUS_KM.get(dis.type, _DEFAULT_DISRUPTION_RADIUS_KM)
    affected = []

    if dis.geometry_lat is not None and dis.geometry_lon is not None:
        active_shipments = (
            db.query(Shipment)
            .filter(Shipment.status.in_(["IN_TRANSIT", "ALERT_DISRUPTION"]))
            .all()
        )
        for shp in active_shipments:
            if shp.current_lat is None or shp.current_lon is None:
                continue
            dist = haversine(
                dis.geometry_lat, dis.geometry_lon,
                shp.current_lat, shp.current_lon,
            )
            if dist <= radius_km:
                affected.append({
                    "shipment_id": shp.id,
                    "shipment_status": shp.status,
                    "distance_km": round(dist, 3),
                })

    return {
        "disruption_id": dis.id,
        "disruption_type": dis.type,
        "disruption_severity": dis.severity,
        "proximity_radius_km": radius_km,
        "affected_shipments": affected,
        "assessed_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Endpoint 1 — Shipment Risk (richest evidence: all four engines)
# ---------------------------------------------------------------------------

@router.post("/shipment-risk", response_model=AIExplanationResponse)
def explain_shipment_risk(
    body: AIExplainRequest,
    db: Session = Depends(get_db),
    ai: WatsonxService = Depends(get_watsonx_service),
) -> AIExplanationResponse:
    """
    Generate an AI-synthesized explanation for a shipment's composite risk.

    Runs all four deterministic engines (RiskEngine, ColdChainEngine,
    RouteOptimizer, FleetMatcher) and synthesizes their outputs into an
    operational narrative via watsonx.ai / Granite.

    Falls back to deterministic text if watsonx.ai is unavailable.
    """
    shp = _get_shipment_or_404(body.entity_id, db)

    risk_result = RiskEngine(db).evaluate_shipment(shp)
    cold_result = ColdChainEngine(db).evaluate_shipment(shp)
    route_result = RouteOptimizer(db).optimize_for_shipment(shp)
    fleet_result = FleetMatcher(db).match_for_shipment(shp)

    evidence = build_shipment_risk_evidence(
        risk_dict=dataclasses.asdict(risk_result),
        cold_chain_dict=dataclasses.asdict(cold_result),
        route_dict=dataclasses.asdict(route_result),
        fleet_dict=dataclasses.asdict(fleet_result),
        shipment_attrs=_shipment_attrs(shp),
    )

    return ai.generate_explanation("shipment_risk", evidence)


# ---------------------------------------------------------------------------
# Endpoint 2 — Cold-Chain Excursion
# ---------------------------------------------------------------------------

@router.post("/cold-chain", response_model=AIExplanationResponse)
def explain_cold_chain(
    body: AIExplainRequest,
    db: Session = Depends(get_db),
    ai: WatsonxService = Depends(get_watsonx_service),
) -> AIExplanationResponse:
    """
    Generate an AI-synthesized explanation for a cold-chain excursion status.

    Runs ColdChainEngine and synthesizes the excursion classification,
    deviation magnitude, and regulatory implications via watsonx.ai / Granite.
    """
    shp = _get_shipment_or_404(body.entity_id, db)

    cold_result = ColdChainEngine(db).evaluate_shipment(shp)

    evidence = build_cold_chain_evidence(
        cold_chain_dict=dataclasses.asdict(cold_result),
        shipment_attrs=_shipment_attrs(shp),
    )

    return ai.generate_explanation("cold_chain", evidence)


# ---------------------------------------------------------------------------
# Endpoint 3 — Route Recommendation
# ---------------------------------------------------------------------------

@router.post("/route-recommendation", response_model=AIExplanationResponse)
def explain_route_recommendation(
    body: AIExplainRequest,
    db: Session = Depends(get_db),
    ai: WatsonxService = Depends(get_watsonx_service),
) -> AIExplanationResponse:
    """
    Generate an AI-synthesized explanation for the recommended route.

    Runs RouteOptimizer and synthesizes the multi-criteria ranking rationale
    (ETA, disruption avoidance, weather, cost, cold-chain exposure) via
    watsonx.ai / Granite.
    """
    shp = _get_shipment_or_404(body.entity_id, db)

    route_result = RouteOptimizer(db).optimize_for_shipment(shp)

    evidence = build_route_recommendation_evidence(
        route_dict=dataclasses.asdict(route_result),
        shipment_attrs=_shipment_attrs(shp),
    )

    return ai.generate_explanation("route_recommendation", evidence)


# ---------------------------------------------------------------------------
# Endpoint 4 — Fleet Match
# ---------------------------------------------------------------------------

@router.post("/fleet-match", response_model=AIExplanationResponse)
def explain_fleet_match(
    body: AIExplainRequest,
    db: Session = Depends(get_db),
    ai: WatsonxService = Depends(get_watsonx_service),
) -> AIExplanationResponse:
    """
    Generate an AI-synthesized explanation for the top fleet asset match.

    Runs FleetMatcher and synthesizes the proximity, cooling capability, and
    cargo compatibility rationale via watsonx.ai / Granite.
    """
    shp = _get_shipment_or_404(body.entity_id, db)

    fleet_result = FleetMatcher(db).match_for_shipment(shp)

    evidence = build_fleet_match_evidence(
        fleet_dict=dataclasses.asdict(fleet_result),
        shipment_attrs=_shipment_attrs(shp),
    )

    return ai.generate_explanation("fleet_match", evidence)


# ---------------------------------------------------------------------------
# Endpoint 5 — Disruption Impact
# ---------------------------------------------------------------------------

@router.post("/disruption-impact", response_model=AIExplanationResponse)
def explain_disruption_impact(
    body: AIExplainRequest,
    db: Session = Depends(get_db),
    ai: WatsonxService = Depends(get_watsonx_service),
) -> AIExplanationResponse:
    """
    Generate an AI-synthesized explanation for a disruption's impact on
    active shipments.

    Computes disruption proximity inline (same logic as the Step 3
    affected-shipments endpoint) and synthesizes the operational impact
    via watsonx.ai / Granite.
    """
    dis = _get_disruption_or_404(body.entity_id, db)

    impact_dict = _compute_disruption_impact(dis, db)

    evidence = build_disruption_impact_evidence(
        disruption_impact_dict=impact_dict,
        disruption_attrs=_disruption_attrs(dis),
    )

    return ai.generate_explanation("disruption_impact", evidence)
