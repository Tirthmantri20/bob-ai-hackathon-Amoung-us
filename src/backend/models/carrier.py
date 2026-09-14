"""
Carrier ORM model.

Maps to the `carriers` table.
Source fixture: src/data/carriers.json

Relationships:
  - Shipment.carrier_id → Carrier.carrier_id (FK)
"""

import json
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.backend.db.database import Base

if TYPE_CHECKING:
    from src.backend.models.shipment import Shipment


class Carrier(Base):
    __tablename__ = "carriers"

    carrier_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    contact_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    compliance_rating: Mapped[float] = mapped_column(Float, nullable=False)
    on_time_delivery_rate: Mapped[float] = mapped_column(Float, nullable=False)
    active_fleet_size: Mapped[int] = mapped_column(Integer, nullable=False)
    # Stored as a JSON-serialised string; deserialised by the schema layer.
    certifications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships (back-populated by Shipment)
    shipments: Mapped[List["Shipment"]] = relationship(
        "Shipment", back_populates="carrier", lazy="select"
    )

    def get_certifications_list(self) -> List[str]:
        """Convenience helper — returns certifications as a Python list."""
        if self.certifications is None:
            return []
        return json.loads(self.certifications)

    def __repr__(self) -> str:
        return f"<Carrier id={self.carrier_id!r} name={self.name!r}>"
