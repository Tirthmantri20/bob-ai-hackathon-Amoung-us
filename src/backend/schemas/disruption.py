"""
Disruption Pydantic v2 schemas.

Schema hierarchy:
  DisruptionBase     — shared readable fields (no PK)
  DisruptionCreate   — DisruptionBase + id
  DisruptionResponse — DisruptionCreate + from_attributes=True

geometry_lat / geometry_lon represent the Step 1 point approximation of
the disruption zone.  A future PostGIS migration will replace these.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DisruptionBase(BaseModel):
    type: str
    severity: str
    title: str
    affected_corridor: Optional[str] = None
    start_time: datetime
    expected_end_time: Optional[datetime] = None
    impact_delay_hours: Optional[float] = None
    recommended_reroute: Optional[str] = None
    geometry_lat: Optional[float] = None
    geometry_lon: Optional[float] = None


class DisruptionCreate(DisruptionBase):
    id: str


class DisruptionResponse(DisruptionCreate):
    model_config = ConfigDict(from_attributes=True)
