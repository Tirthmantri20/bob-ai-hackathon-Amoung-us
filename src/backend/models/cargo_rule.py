"""
CargoRule ORM model.

Maps to the `cargo_rules` table.
Source fixture: src/data/cargo_rules.json

The fixture has no natural primary key field, so a surrogate auto-integer PK
is used.  A unique constraint on `category` enforces business uniqueness and
supports idempotent seeding (existence checked by category, not by id).

The `cargo_category` field on Shipment is matched against `category` in
application code rather than through a foreign-key constraint, because the
fixture uses a plain string for the relationship.
"""

from typing import Optional

from sqlalchemy import Boolean, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.backend.db.database import Base


class CargoRule(Base):
    __tablename__ = "cargo_rules"
    __table_args__ = (UniqueConstraint("grade", name="uq_cargo_rules_grade"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    grade: Mapped[str] = mapped_column(String, nullable=False)
    min_temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    max_temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    max_excursion_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    max_allowable_excursion_temp_c: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    humidity_max_percent: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    inspection_frequency_hours: Mapped[float] = mapped_column(Float, nullable=False)
    requires_continuous_logger: Mapped[bool] = mapped_column(Boolean, nullable=False)
    compliance_standard: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<CargoRule id={self.id} category={self.category!r}>"
