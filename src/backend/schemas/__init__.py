"""
src/backend/schemas package.

Re-exports all Pydantic v2 schema classes so application code can import them
from a single location:

    from src.backend.schemas import ShipmentResponse, CarrierResponse, ...
"""

from src.backend.schemas.cargo_rule import (  # noqa: F401
    CargoRuleBase,
    CargoRuleCreate,
    CargoRuleResponse,
)
from src.backend.schemas.carrier import (  # noqa: F401
    CarrierBase,
    CarrierCreate,
    CarrierResponse,
)
from src.backend.schemas.disruption import (  # noqa: F401
    DisruptionBase,
    DisruptionCreate,
    DisruptionResponse,
)
from src.backend.schemas.fleet_asset import (  # noqa: F401
    FleetAssetBase,
    FleetAssetCreate,
    FleetAssetResponse,
)
from src.backend.schemas.route import (  # noqa: F401
    RouteBase,
    RouteCreate,
    RouteResponse,
)
from src.backend.schemas.shipment import (  # noqa: F401
    ShipmentBase,
    ShipmentCreate,
    ShipmentResponse,
)
from src.backend.schemas.telemetry import (  # noqa: F401
    TelemetryBase,
    TelemetryCreate,
    TelemetryResponse,
)
from src.backend.schemas.weather import (  # noqa: F401
    WeatherBase,
    WeatherCreate,
    WeatherResponse,
)
from src.backend.schemas.engine_responses import (  # noqa: F401
    AffectedShipmentEntry,
    ColdChainResponse,
    DisruptionImpactResponse,
    FleetMatchResponse,
    FleetMatchScoreResponse,
    RouteOptimizerResponse,
    RouteScoreResponse,
    ShipmentRiskResponse,
)

__all__ = [
    # CargoRule
    "CargoRuleBase", "CargoRuleCreate", "CargoRuleResponse",
    # Carrier
    "CarrierBase", "CarrierCreate", "CarrierResponse",
    # Disruption
    "DisruptionBase", "DisruptionCreate", "DisruptionResponse",
    # FleetAsset
    "FleetAssetBase", "FleetAssetCreate", "FleetAssetResponse",
    # Route
    "RouteBase", "RouteCreate", "RouteResponse",
    # Shipment
    "ShipmentBase", "ShipmentCreate", "ShipmentResponse",
    # Telemetry
    "TelemetryBase", "TelemetryCreate", "TelemetryResponse",
    # Weather
    "WeatherBase", "WeatherCreate", "WeatherResponse",
    # Engine responses (Step 3)
    "ShipmentRiskResponse",
    "ColdChainResponse",
    "RouteScoreResponse",
    "RouteOptimizerResponse",
    "FleetMatchScoreResponse",
    "FleetMatchResponse",
    "AffectedShipmentEntry",
    "DisruptionImpactResponse",
]
