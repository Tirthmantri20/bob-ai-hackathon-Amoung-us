"""
SupplyGuard MCP tool package.

Re-exports all 10 tool functions for registration in server.py.
No logic lives here — only import re-exports.
"""

from src.mcp.tools.disruptions import (
    get_active_disruptions,
    get_disruption_impact,
)
from src.mcp.tools.explain import (
    explain_disruption_impact,
    explain_shipment_risk,
)
from src.mcp.tools.shipments import (
    evaluate_cold_chain,
    evaluate_shipment_risk,
    get_active_shipments,
    get_route_recommendations,
    get_shipment_detail,
    match_fleet_asset,
)

__all__ = [
    "get_active_shipments",
    "get_shipment_detail",
    "evaluate_shipment_risk",
    "evaluate_cold_chain",
    "get_route_recommendations",
    "match_fleet_asset",
    "get_active_disruptions",
    "get_disruption_impact",
    "explain_shipment_risk",
    "explain_disruption_impact",
]
