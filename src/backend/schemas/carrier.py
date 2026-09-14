"""
Carrier Pydantic v2 schemas.

Schema hierarchy:
  CarrierBase     — shared readable fields (no PK)
  CarrierCreate   — CarrierBase + carrier_id (used by seed loader & future POST)
  CarrierResponse — CarrierCreate + from_attributes=True (ORM → API)

JSON text → list fix (Step 3):
  The SQLAlchemy Carrier model stores certifications as a JSON text (Text
  column).  The field_validator below deserialises that string before
  Pydantic's type coercion, so model_validate(carrier_orm) works correctly.

  EmailStr was previously imported but unused (contact_email is Optional[str]).
  It has been removed to eliminate the lint warning.
"""

import json
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CarrierBase(BaseModel):
    name: str
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    compliance_rating: float = Field(..., ge=0.0, le=1.0)
    on_time_delivery_rate: float = Field(..., ge=0.0, le=1.0)
    active_fleet_size: int = Field(..., ge=0)
    certifications: Optional[List[str]] = None

    @field_validator("certifications", mode="before")
    @classmethod
    def parse_certifications(cls, v: Any) -> Any:
        """
        Deserialise JSON-text ORM value to a Python list before type coercion.

        Accepts:
          - str  → json.loads(v) (SQLAlchemy Text column value)
          - list → returned unchanged (already deserialised)
          - None → returned unchanged (optional field)
        """
        if isinstance(v, str):
            return json.loads(v)
        return v


class CarrierCreate(CarrierBase):
    carrier_id: str


class CarrierResponse(CarrierCreate):
    model_config = ConfigDict(from_attributes=True)
