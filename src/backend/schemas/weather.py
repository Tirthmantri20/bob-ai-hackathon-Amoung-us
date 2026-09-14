"""
Weather Pydantic v2 schemas.

Schema hierarchy:
  WeatherBase     — shared readable fields (no PK)
  WeatherCreate   — WeatherBase + station_id
  WeatherResponse — WeatherCreate + from_attributes=True

CONFLICT-06: forecast_vector is omitted in Step 1; will be added in Step 4.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WeatherBase(BaseModel):
    location: str
    ambient_temp_c: float
    condition: Optional[str] = None
    precipitation_prob_percent: Optional[int] = None
    wind_speed_kmh: Optional[float] = None
    road_condition: Optional[str] = None
    updated_at: Optional[datetime] = None


class WeatherCreate(WeatherBase):
    station_id: str


class WeatherResponse(WeatherCreate):
    model_config = ConfigDict(from_attributes=True)
