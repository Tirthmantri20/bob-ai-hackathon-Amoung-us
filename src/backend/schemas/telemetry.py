"""
Telemetry Pydantic v2 schemas.

Schema hierarchy:
  TelemetryBase     — shared readable fields (no PK)
  TelemetryCreate   — TelemetryBase + telemetry_id
  TelemetryResponse — TelemetryCreate + from_attributes=True

GPS fields are flattened from the fixture's nested gps dict.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TelemetryBase(BaseModel):
    vehicle_id: str
    shipment_id: str
    timestamp: datetime
    cargo_temp_c: float
    cargo_temp_target_c: Optional[float] = None
    temp_deviation_c: Optional[float] = None
    cargo_humidity_percent: Optional[float] = None
    reefer_compressor_status: Optional[str] = None
    door_sensor: Optional[str] = None
    vibration_g: Optional[float] = None
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    gps_speed_kmh: Optional[float] = None
    gps_heading_deg: Optional[float] = None


class TelemetryCreate(TelemetryBase):
    telemetry_id: str


class TelemetryResponse(TelemetryCreate):
    model_config = ConfigDict(from_attributes=True)
