"""
CargoRule Pydantic v2 schemas.

Schema hierarchy:
  CargoRuleBase     — shared readable fields (no PK)
  CargoRuleCreate   — CargoRuleBase (auto-int PK; not supplied on create)
  CargoRuleResponse — CargoRuleBase + id + from_attributes=True
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CargoRuleBase(BaseModel):
    category: str
    grade: str
    min_temp_c: float
    max_temp_c: float
    max_excursion_duration_minutes: int = Field(..., ge=0)
    max_allowable_excursion_temp_c: float
    humidity_max_percent: Optional[int] = None
    inspection_frequency_hours: float = Field(..., ge=0)
    requires_continuous_logger: bool
    compliance_standard: Optional[str] = None


class CargoRuleCreate(CargoRuleBase):
    """Used by the seed loader.  The PK is auto-assigned by the database."""
    pass


class CargoRuleResponse(CargoRuleBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
