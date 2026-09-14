"""
Fleet API router — /api/fleet/*

Endpoints
---------
GET  /api/fleet              List all fleet assets
POST /api/fleet              Create a new fleet asset
GET  /api/fleet/{asset_id}   Get one fleet asset

Pure database reads — no engine computation.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.backend.db.database import get_db
from src.backend.models.fleet_asset import FleetAsset
from src.backend.schemas.fleet_asset import FleetAssetCreate, FleetAssetResponse

router = APIRouter()


@router.get("/", response_model=list[FleetAssetResponse])
def list_fleet(db: Session = Depends(get_db)):
    """Return all fleet assets from the database."""
    assets = db.query(FleetAsset).all()
    return [FleetAssetResponse.model_validate(a) for a in assets]


@router.post("/", response_model=FleetAssetResponse, status_code=201)
def create_fleet_asset(payload: FleetAssetCreate, db: Session = Depends(get_db)):
    """Create a new fleet asset record.  Returns 409 if the ID already exists."""
    existing = db.get(FleetAsset, payload.id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Fleet asset {payload.id!r} already exists",
        )
    asset = FleetAsset(**payload.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return FleetAssetResponse.model_validate(asset)


@router.get("/{asset_id}", response_model=FleetAssetResponse)
def get_fleet_asset(asset_id: str, db: Session = Depends(get_db)):
    """Return a single fleet asset by ID.  404 if not found."""
    asset = db.get(FleetAsset, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=404,
            detail=f"Fleet asset {asset_id!r} not found",
        )
    return FleetAssetResponse.model_validate(asset)
