"""
Route Pydantic v2 schemas.

Schema hierarchy:
  RouteBase     — shared readable fields (no PK)
  RouteCreate   — RouteBase + route_id
  RouteResponse — RouteCreate + from_attributes=True

JSON text → list fix (Step 3):
  The SQLAlchemy Route model stores highways, waypoints, and
  cold_storage_depots as JSON text (Text column).  The field_validator
  below deserialises those strings before Pydantic's type coercion runs,
  so model_validate(route_orm) works correctly.
"""

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RouteBase(BaseModel):
    name: str
    origin: str
    destination: str
    distance_km: float = Field(..., gt=0)
    typical_duration_hours: float = Field(..., gt=0)
    highways: Optional[List[str]] = None
    waypoints: Optional[List[Dict[str, Any]]] = None
    cold_storage_depots: Optional[List[Dict[str, Any]]] = None

    @field_validator("highways", "waypoints", "cold_storage_depots", mode="before")
    @classmethod
    def parse_json_text(cls, v: Any) -> Any:
        """
        Deserialise JSON-text ORM values to Python lists before type coercion.

        Accepts:
          - str  → json.loads(v) (SQLAlchemy Text column value)
          - list → returned unchanged (already deserialised)
          - None → returned unchanged (optional field)
        """
        if isinstance(v, str):
            return json.loads(v)
        return v


class RouteCreate(RouteBase):
    route_id: str


class RouteResponse(RouteCreate):
    model_config = ConfigDict(from_attributes=True)
