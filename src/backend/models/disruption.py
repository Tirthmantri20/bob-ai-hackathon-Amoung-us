"""
Disruption ORM model.

Maps to the `disruptions` table.
Source fixture: src/data/disruptions.json

CONFLICT-02 note: docs/architecture.md describes disruption geometry as
"geometry polygon / radius".  The fixture contains only a single point
(coordinates.lat / coordinates.lon).  Step 1 stores the point as two Float
columns (geometry_lat, geometry_lon).  A future PostGIS migration will replace
these with a GEOMETRY(Point, 4326) column via GeoAlchemy2 without affecting
other fields.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from src.backend.db.database import Base


class Disruption(Base):
    __tablename__ = "disruptions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    affected_corridor: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expected_end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    impact_delay_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recommended_reroute: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Step 1 point representation; will become a PostGIS geometry column in a
    # future step.
    geometry_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geometry_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Disruption id={self.id!r} type={self.type!r} severity={self.severity!r}>"
        )
