"""
Shipments API router — /api/shipments/*

Endpoints
---------
GET  /api/shipments                       List all shipments
POST /api/shipments                       Create a new shipment
GET  /api/shipments/{shipment_id}         Get one shipment
GET  /api/shipments/{shipment_id}/risk    Run Risk Engine for one shipment
GET  /api/shipments/{shipment_id}/cold-chain  Run Cold-Chain Engine
GET  /api/shipments/{shipment_id}/routes      Run Route Optimizer
GET  /api/shipments/{shipment_id}/fleet-match Run Fleet Matcher

All engine-compute endpoints follow the same thin pattern:
  DB lookup → 404 if missing → Engine(session) → dataclasses.asdict()
  → Pydantic response schema → JSON

Engine fallback states (no_route_found, cold_chain_fallback, etc.) remain
200 OK responses — they are valid operational outcomes, not errors.

Risk scores are NOT persisted to Shipment.current_risk_score.  The engine
outputs 0–100; the DB column is a 0–1 field (MD-09).
"""

import dataclasses

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.backend.cold_chain.engine import ColdChainEngine
from src.backend.db.database import get_db
from src.backend.models.shipment import Shipment
from src.backend.optimizer.fleet_matcher import FleetMatcher
from src.backend.optimizer.route_optimizer import RouteOptimizer
from src.backend.risk_engine.scorer import RiskEngine
from src.backend.schemas.engine_responses import (
    ColdChainResponse,
    FleetMatchResponse,
    RouteOptimizerResponse,
    ShipmentRiskResponse,
)
from src.backend.schemas.shipment import ShipmentCreate, ShipmentResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_shipment_or_404(shipment_id: str, db: Session) -> Shipment:
    shp = db.get(Shipment, shipment_id)
    if shp is None:
        raise HTTPException(
            status_code=404,
            detail=f"Shipment {shipment_id!r} not found",
        )
    return shp


# ---------------------------------------------------------------------------
# List all shipments
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[ShipmentResponse])
def list_shipments(db: Session = Depends(get_db)):
    """Return all shipments from the database."""
    shipments = db.query(Shipment).all()
    return [ShipmentResponse.model_validate(s) for s in shipments]


# ---------------------------------------------------------------------------
# Create a new shipment
# ---------------------------------------------------------------------------

@router.post("/", response_model=ShipmentResponse, status_code=201)
def create_shipment(payload: ShipmentCreate, db: Session = Depends(get_db)):
    """Create a new shipment record.  Returns 409 if the ID already exists."""
    existing = db.get(Shipment, payload.id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Shipment {payload.id!r} already exists",
        )
    shp = Shipment(**payload.model_dump())
    db.add(shp)
    db.commit()
    db.refresh(shp)
    return ShipmentResponse.model_validate(shp)


# ---------------------------------------------------------------------------
# Get one shipment
# ---------------------------------------------------------------------------

@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_shipment(shipment_id: str, db: Session = Depends(get_db)):
    """Return a single shipment by ID.  404 if not found."""
    shp = _get_shipment_or_404(shipment_id, db)
    return ShipmentResponse.model_validate(shp)


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------

@router.get("/{shipment_id}/risk", response_model=ShipmentRiskResponse)
def get_shipment_risk(shipment_id: str, db: Session = Depends(get_db)):
    """
    Run the deterministic Risk Engine for one shipment.

    Returns a 0–100 total_score with per-dimension sub-scores.
    Result is NOT persisted to the database.
    """
    shp = _get_shipment_or_404(shipment_id, db)
    engine = RiskEngine(db)
    result = engine.evaluate_shipment(shp)
    return ShipmentRiskResponse.model_validate(dataclasses.asdict(result))


# ---------------------------------------------------------------------------
# Cold-chain assessment
# ---------------------------------------------------------------------------

@router.get("/{shipment_id}/cold-chain", response_model=ColdChainResponse)
def get_shipment_cold_chain(shipment_id: str, db: Session = Depends(get_db)):
    """
    Run the Cold-Chain Engine for one shipment.

    Evaluates the most recent telemetry record against the cargo's regulatory
    rule.  Returns OK/WARNING/HIGH/CRITICAL/UNKNOWN severity.
    cold_chain_fallback flags are returned as 200 — they are valid outcomes.
    """
    shp = _get_shipment_or_404(shipment_id, db)
    engine = ColdChainEngine(db)
    result = engine.evaluate_shipment(shp)
    return ColdChainResponse.model_validate(dataclasses.asdict(result))


# ---------------------------------------------------------------------------
# Route optimization
# ---------------------------------------------------------------------------

@router.get("/{shipment_id}/routes", response_model=RouteOptimizerResponse)
def get_shipment_routes(shipment_id: str, db: Session = Depends(get_db)):
    """
    Run the Route Optimizer for one shipment.

    Scores all routes matching the shipment's exact origin/destination strings
    (MD-05: exact string equality).  no_route_found=True is a valid 200 outcome
    (not a 404) — it means no route in the DB matches this shipment's corridor.
    """
    shp = _get_shipment_or_404(shipment_id, db)
    optimizer = RouteOptimizer(db)
    result = optimizer.optimize_for_shipment(shp)
    return RouteOptimizerResponse.model_validate(dataclasses.asdict(result))


# ---------------------------------------------------------------------------
# Fleet matching
# ---------------------------------------------------------------------------

@router.get("/{shipment_id}/fleet-match", response_model=FleetMatchResponse)
def get_shipment_fleet_match(shipment_id: str, db: Session = Depends(get_db)):
    """
    Run the Fleet Matcher for one shipment.

    Scores all fleet assets (excluding the shipment's own assigned vehicle) as
    candidates for emergency reassignment.  no_asset_found=True is a valid 200
    outcome — it means the shipment's vehicle is the only asset in the DB.
    """
    shp = _get_shipment_or_404(shipment_id, db)
    matcher = FleetMatcher(db)
    result = matcher.match_for_shipment(shp)
    return FleetMatchResponse.model_validate(dataclasses.asdict(result))
