"""
Shipment Pydantic v2 schemas.

Schema hierarchy:
  ShipmentBase     — shared readable fields (no PK)
  ShipmentCreate   — ShipmentBase + id
  ShipmentResponse — ShipmentCreate + from_attributes=True

current_lat / current_lon / current_location_name are flattened from the
fixture's nested current_location dict.

current_risk_score is seeded from the fixture but will be updated at runtime
by the risk engine (Step 2).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ShipmentBase(BaseModel):
    tracking_number: Optional[str] = None
    origin: str
    destination: str
    cargo_type: str
    cargo_category: str
    required_temp_min_c: float
    required_temp_max_c: float
    status: str
    assigned_vehicle_id: Optional[str] = None
    carrier_id: Optional[str] = None
    estimated_departure: Optional[datetime] = None
    estimated_arrival: Optional[datetime] = None
    current_risk_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    current_location_name: Optional[str] = None


class ShipmentCreate(ShipmentBase):
    id: str


class ShipmentResponse(ShipmentCreate):
    model_config = ConfigDict(from_attributes=True)
