"""
Telemetry ORM model.

Maps to the `telemetry` table.
Source fixture: src/data/telemetry.json

The fixture stores GPS data as a nested dict
  { "lat": ..., "lon": ..., "speed_kmh": ..., "heading_deg": ... }
which is flattened to four columns.

Foreign keys:
  - vehicle_id  → fleet_assets.id
  - shipment_id → shipments.id

Index on `shipment_id` because the cold-chain engine will query all telemetry
records for a given shipment.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.backend.db.database import Base

if TYPE_CHECKING:
    from src.backend.models.fleet_asset import FleetAsset
    from src.backend.models.shipment import Shipment


class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (Index("ix_telemetry_shipment_id", "shipment_id"),)

    telemetry_id: Mapped[str] = mapped_column(String, primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(
        String, ForeignKey("fleet_assets.id"), nullable=False
    )
    shipment_id: Mapped[str] = mapped_column(
        String, ForeignKey("shipments.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cargo_temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    cargo_temp_target_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temp_deviation_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cargo_humidity_percent: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    reefer_compressor_status: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    door_sensor: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    vibration_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Flattened from fixture gps dict.
    gps_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_speed_kmh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_heading_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    vehicle: Mapped["FleetAsset"] = relationship(
        "FleetAsset", back_populates="telemetry_records", lazy="select"
    )
    shipment: Mapped["Shipment"] = relationship(
        "Shipment", back_populates="telemetry_records", lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<Telemetry id={self.telemetry_id!r} vehicle={self.vehicle_id!r} "
            f"temp={self.cargo_temp_c}°C>"
        )
