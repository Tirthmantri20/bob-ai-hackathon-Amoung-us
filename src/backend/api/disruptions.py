"""
Disruptions API router — /api/disruptions/*

Endpoints
---------
GET  /api/disruptions                                 List all disruptions
POST /api/disruptions                                 Create a new disruption
GET  /api/disruptions/{disruption_id}                 Get one disruption
GET  /api/disruptions/{disruption_id}/affected-shipments
    Compute which active shipments fall within the disruption's proximity radius.

The affected-shipments endpoint re-uses the same DISRUPTION_RADIUS_KM constant
map and haversine function already centralized in risk_engine/sub_scores.py and
risk_engine/haversine.py.  No new scoring logic is introduced here.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.backend.db.database import get_db
from src.backend.models.disruption import Disruption
from src.backend.models.shipment import Shipment
from src.backend.risk_engine.haversine import haversine
from src.backend.risk_engine.sub_scores import (
    DISRUPTION_RADIUS_KM,
    _DEFAULT_DISRUPTION_RADIUS_KM,
)
from src.backend.schemas.disruption import DisruptionCreate, DisruptionResponse
from src.backend.schemas.engine_responses import (
    AffectedShipmentEntry,
    DisruptionImpactResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_disruption_or_404(disruption_id: str, db: Session) -> Disruption:
    dis = db.get(Disruption, disruption_id)
    if dis is None:
        raise HTTPException(
            status_code=404,
            detail=f"Disruption {disruption_id!r} not found",
        )
    return dis


# ---------------------------------------------------------------------------
# List all disruptions
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[DisruptionResponse])
def list_disruptions(db: Session = Depends(get_db)):
    """Return all disruptions from the database."""
    disruptions = db.query(Disruption).all()
    return [DisruptionResponse.model_validate(d) for d in disruptions]


# ---------------------------------------------------------------------------
# Create a new disruption
# ---------------------------------------------------------------------------

@router.post("/", response_model=DisruptionResponse, status_code=201)
def create_disruption(payload: DisruptionCreate, db: Session = Depends(get_db)):
    """Create a new disruption record.  Returns 409 if the ID already exists."""
    existing = db.get(Disruption, payload.id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Disruption {payload.id!r} already exists",
        )
    dis = Disruption(**payload.model_dump())
    db.add(dis)
    db.commit()
    db.refresh(dis)
    return DisruptionResponse.model_validate(dis)


# ---------------------------------------------------------------------------
# Get one disruption
# ---------------------------------------------------------------------------

@router.get("/{disruption_id}", response_model=DisruptionResponse)
def get_disruption(disruption_id: str, db: Session = Depends(get_db)):
    """Return a single disruption by ID.  404 if not found."""
    dis = _get_disruption_or_404(disruption_id, db)
    return DisruptionResponse.model_validate(dis)


# ---------------------------------------------------------------------------
# Affected shipments
# ---------------------------------------------------------------------------

@router.get(
    "/{disruption_id}/affected-shipments",
    response_model=DisruptionImpactResponse,
)
def get_affected_shipments(disruption_id: str, db: Session = Depends(get_db)):
    """
    Return active shipments that fall within the disruption's proximity radius.

    Proximity radius is determined by disruption type (MD-08):
      SEVERE_WEATHER        → 200 km
      PORT_CONTAINER_HOLD   → 50 km
      ROADWORK_CONGESTION   → 30 km
      default               → 100 km

    Only shipments with status IN_TRANSIT or ALERT_DISRUPTION and with
    non-None current_lat/lon are evaluated.

    Returns an empty affected_shipments list if:
      - The disruption has no geometry (geometry_lat/lon is None).
      - No active shipment's position falls within the radius.

    This is always a 200 response — the 404 is reserved for a missing
    disruption entity only.
    """
    dis = _get_disruption_or_404(disruption_id, db)
    now = datetime.now(tz=timezone.utc)

    radius_km = DISRUPTION_RADIUS_KM.get(dis.type, _DEFAULT_DISRUPTION_RADIUS_KM)

    affected: list[AffectedShipmentEntry] = []

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
                affected.append(
                    AffectedShipmentEntry(
                        shipment_id=shp.id,
                        shipment_status=shp.status,
                        distance_km=round(dist, 3),
                    )
                )

    return DisruptionImpactResponse(
        disruption_id=dis.id,
        disruption_type=dis.type,
        disruption_severity=dis.severity,
        proximity_radius_km=radius_km,
        affected_shipments=affected,
        assessed_at=now,
    )
