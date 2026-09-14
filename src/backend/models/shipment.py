"""
Shipment ORM model.

Maps to the `shipments` table.
Source fixture: src/data/shipments.json

The fixture stores the current shipment location as a nested dict
  { "lat": ..., "lon": ..., "name": ... }
which is flattened to three columns: current_lat, current_lon,
current_location_name.

Foreign keys:
  - assigned_vehicle_id → fleet_assets.id  (nullable)
  - carrier_id          → carriers.carrier_id  (nullable)

CONFLICT-01 note: docs/solution-overview.md references legacy shipment IDs
(S204, S102) that do not match the fixture IDs (SHP-1001, SHP-1002, SHP-1003).
No code change is needed here.  MCP tool docstrings and example queries will
use the correct fixture IDs when Step 5 is implemented.

Index on `status` because the risk engine will frequently filter by status.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.backend.db.database import Base

if TYPE_CHECKING:
    from src.backend.models.carrier import Carrier
    from src.backend.models.fleet_asset import FleetAsset
    from src.backend.models.telemetry import Telemetry


class Shipment(Base):
    __tablename__ = "shipments"
    __table_args__ = (Index("ix_shipments_status", "status"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tracking_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    origin: Mapped[str] = mapped_column(String, nullable=False)
    destination: Mapped[str] = mapped_column(String, nullable=False)
    cargo_type: Mapped[str] = mapped_column(String, nullable=False)
    cargo_category: Mapped[str] = mapped_column(String, nullable=False)
    required_temp_min_c: Mapped[float] = mapped_column(Float, nullable=False)
    required_temp_max_c: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    assigned_vehicle_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("fleet_assets.id"), nullable=True
    )
    carrier_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("carriers.carrier_id"), nullable=True
    )
    estimated_departure: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    estimated_arrival: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    # Seed value from fixture; updated by the risk engine at runtime.
    current_risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Flattened from fixture current_location dict.
    current_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_location_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    vehicle: Mapped[Optional["FleetAsset"]] = relationship(
        "FleetAsset", back_populates="shipments", lazy="select"
    )
    carrier: Mapped[Optional["Carrier"]] = relationship(
        "Carrier", back_populates="shipments", lazy="select"
    )
    telemetry_records: Mapped[list["Telemetry"]] = relationship(
        "Telemetry", back_populates="shipment", lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<Shipment id={self.id!r} status={self.status!r} "
            f"cargo={self.cargo_type!r}>"
        )
