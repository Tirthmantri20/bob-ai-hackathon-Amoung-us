"""
Risk API router — /api/risk/*

Endpoints
---------
GET /api/risk/active   Run RiskEngine.evaluate_all_active() for all active shipments

Separated into its own router so /api/shipments keeps a clean consistent prefix.
"""

import dataclasses

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.backend.db.database import get_db
from src.backend.risk_engine.scorer import RiskEngine
from src.backend.schemas.engine_responses import ShipmentRiskResponse

router = APIRouter()


@router.get("/active", response_model=list[ShipmentRiskResponse])
def get_active_risk(db: Session = Depends(get_db)):
    """
    Run the Risk Engine for all active shipments (status IN_TRANSIT or
    ALERT_DISRUPTION).

    Returns a list of ShipmentRiskResponse — one per active shipment.
    Results are NOT persisted to the database.
    """
    engine = RiskEngine(db)
    results = engine.evaluate_all_active()
    return [ShipmentRiskResponse.model_validate(dataclasses.asdict(r)) for r in results]
