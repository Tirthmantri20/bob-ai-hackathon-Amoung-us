"""
Weather ORM model.

Maps to the `weather` table.
Source fixture: src/data/weather.json

CONFLICT-06 note: docs/architecture.md lists `forecast_vector` as a weather
field.  The fixture does not include it.  This column is omitted in Step 1 and
will be added as a nullable JSON text column in Step 4 (environmental service).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.backend.db.database import Base


class Weather(Base):
    __tablename__ = "weather"

    station_id: Mapped[str] = mapped_column(String, primary_key=True)
    location: Mapped[str] = mapped_column(String, nullable=False)
    ambient_temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    condition: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    precipitation_prob_percent: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    wind_speed_kmh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    road_condition: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Weather station={self.station_id!r} location={self.location!r}>"
