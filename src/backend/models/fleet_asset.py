"""
FleetAsset ORM model.

Maps to the `fleet_assets` table.
Source fixture: src/data/fleet.json

current_lat / current_lon are nullable and not populated from fixtures —
they are reserved for runtime GPS updates from the telematics system.

CONFLICT-05 note: docs/architecture.md mentions "temp range capability" but
the fixture omits temp_range_min_c / temp_range_max_c.  These fields are NOT
added in Step 1.  They will be addressed in Step 2 (optimizer implementation).

Relationships:
  - Shipment.assigned_vehicle_id → FleetAsset.id (FK)
  - Telemetry.vehicle_id → FleetAsset.id (FK)
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.backend.db.database import Base

if TYPE_CHECKING:
    from src.backend.models.shipment import Shipment
    from src.backend.models.telemetry import Telemetry


class FleetAsset(Base):
    __tablename__ = "fleet_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    vehicle_type: Mapped[str] = mapped_column(String, nullable=False)
    license_plate: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    fuel_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cooling_system_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    capacity_kg: Mapped[int] = mapped_column(Integer, nullable=False)
    battery_charge_percent: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    fuel_level_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    driver_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Links to Telemetry.telemetry_id in application logic (not a FK constraint).
    telemetry_stream_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Runtime GPS coordinates — not seeded from fixture.
    current_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    shipments: Mapped[List["Shipment"]] = relationship(
        "Shipment", back_populates="vehicle", lazy="select"
    )
    telemetry_records: Mapped[List["Telemetry"]] = relationship(
        "Telemetry", back_populates="vehicle", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<FleetAsset id={self.id!r} type={self.vehicle_type!r} status={self.status!r}>"
