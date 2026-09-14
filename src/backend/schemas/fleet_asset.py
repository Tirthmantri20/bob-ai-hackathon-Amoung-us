"""
FleetAsset Pydantic v2 schemas.

Schema hierarchy:
  FleetAssetBase     — shared readable fields (no PK)
  FleetAssetCreate   — FleetAssetBase + id
  FleetAssetResponse — FleetAssetCreate + from_attributes=True

current_lat / current_lon are nullable; they are not populated from seed
fixtures and will be updated at runtime by the telematics service.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FleetAssetBase(BaseModel):
    vehicle_type: str
    license_plate: Optional[str] = None
    status: str
    fuel_type: Optional[str] = None
    cooling_system_type: Optional[str] = None
    capacity_kg: int = Field(..., ge=0)
    battery_charge_percent: Optional[int] = Field(None, ge=0, le=100)
    fuel_level_percent: Optional[int] = Field(None, ge=0, le=100)
    driver_name: Optional[str] = None
    telemetry_stream_id: Optional[str] = None
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None


class FleetAssetCreate(FleetAssetBase):
    id: str


class FleetAssetResponse(FleetAssetCreate):
    model_config = ConfigDict(from_attributes=True)
