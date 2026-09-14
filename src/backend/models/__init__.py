"""
src/backend/models package.

Importing this package (or any symbol from it) causes all ORM model classes to
be imported, which registers their table definitions on Base.metadata.

This is the single import that init_db() / create_all() depends on.

Import order does not affect registration, but it documents the FK dependency
chain for clarity:

  Carrier, Route, CargoRule, Weather, FleetAsset, Disruption
      → referenced by Shipment
          → referenced by Telemetry
"""

from src.backend.models.cargo_rule import CargoRule  # noqa: F401
from src.backend.models.carrier import Carrier  # noqa: F401
from src.backend.models.disruption import Disruption  # noqa: F401
from src.backend.models.fleet_asset import FleetAsset  # noqa: F401
from src.backend.models.route import Route  # noqa: F401
from src.backend.models.shipment import Shipment  # noqa: F401
from src.backend.models.telemetry import Telemetry  # noqa: F401
from src.backend.models.weather import Weather  # noqa: F401

__all__ = [
    "CargoRule",
    "Carrier",
    "Disruption",
    "FleetAsset",
    "Route",
    "Shipment",
    "Telemetry",
    "Weather",
]
