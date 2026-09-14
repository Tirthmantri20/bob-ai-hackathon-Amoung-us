"""
Route ORM model.

Maps to the `routes` table.
Source fixture: src/data/routes.json

Waypoints and cold-storage depot lists are stored as JSON text in Step 1.
A future PostGIS/optimizer step may normalise these into separate tables.
"""

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.backend.db.database import Base


class Route(Base):
    __tablename__ = "routes"

    route_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    origin: Mapped[str] = mapped_column(String, nullable=False)
    destination: Mapped[str] = mapped_column(String, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    typical_duration_hours: Mapped[float] = mapped_column(Float, nullable=False)
    # JSON-serialised list of highway codes, e.g. '["I-65 S", "I-24 E"]'
    highways: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON-serialised list of {name, lat, lon} dicts
    waypoints: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON-serialised list of {name, lat, lon} dicts
    cold_storage_depots: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def get_highways_list(self) -> List[str]:
        if self.highways is None:
            return []
        return json.loads(self.highways)

    def get_waypoints_list(self) -> List[Dict[str, Any]]:
        if self.waypoints is None:
            return []
        return json.loads(self.waypoints)

    def get_cold_storage_depots_list(self) -> List[Dict[str, Any]]:
        if self.cold_storage_depots is None:
            return []
        return json.loads(self.cold_storage_depots)

    def __repr__(self) -> str:
        return f"<Route id={self.route_id!r} {self.origin!r}→{self.destination!r}>"
