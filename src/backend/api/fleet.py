"""
Fleet API router — /api/fleet/*

Endpoints
---------
GET /api/fleet              List all fleet assets
GET /api/fleet/{asset_id}   Get one fleet asset

Pure database reads — no engine computation.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.backend.db.database import get_db
from src.backend.models.fleet_asset import FleetAsset
from src.backend.schemas.fleet_asset import FleetAssetResponse

router = APIRouter()


@router.get("/", response_model=list[FleetAssetResponse])
def list_fleet(db: Session = Depends(get_db)):
    """Return all fleet assets from the database."""
    assets = db.query(FleetAsset).all()
    return [FleetAssetResponse.model_validate(a) for a in assets]


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
