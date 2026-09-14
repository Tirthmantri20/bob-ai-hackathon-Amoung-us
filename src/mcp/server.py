"""
SupplyGuard MCP Server — IBM Bob Integration Entry Point
=========================================================

Exposes 10 supply-chain tools to IBM Bob via the Model Context Protocol
(stdio transport).  This process runs independently from the FastAPI backend.

Runtime requirements
--------------------
- The FastAPI backend must be running at SUPPLYGUARD_API_URL
  (default: http://localhost:8000) before IBM Bob invokes any tool.
- Launch with:  python -m src.mcp.server
- Bob configuration:  .bob/mcp.json  (project root)

Immutable architecture constraints
-----------------------------------
- NEVER import from src.backend (no engines, no ORM, no database sessions).
- ALL logging must go to sys.stderr.
- stdout is the MCP stdio protocol channel — any non-JSON write to stdout
  will corrupt the connection.

Tool inventory
--------------
1.  get_active_shipments       — list all tracked shipments
2.  get_shipment_detail        — single shipment by ID
3.  evaluate_shipment_risk     — deterministic Risk Engine (0–100 score)
4.  evaluate_cold_chain        — cold-chain excursion status
5.  get_route_recommendations  — ranked alternative routes
6.  match_fleet_asset          — top idle fleet asset for rescue
7.  get_active_disruptions     — list all disruption events
8.  get_disruption_impact      — shipments within disruption radius
9.  explain_shipment_risk      — Granite-backed full risk narrative
10. explain_disruption_impact  — Granite-backed disruption incident brief
"""

import logging
import sys

from mcp.server.fastmcp import FastMCP

from src.mcp.tools import (
    evaluate_cold_chain,
    evaluate_shipment_risk,
    explain_disruption_impact,
    explain_shipment_risk,
    get_active_disruptions,
    get_active_shipments,
    get_disruption_impact,
    get_route_recommendations,
    get_shipment_detail,
    match_fleet_asset,
)

# ---------------------------------------------------------------------------
# Logging — ALL output to stderr; stdout must stay clean for MCP JSON-RPC
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s  %(levelname)-8s  mcp.server — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "supplyguard",
    instructions=(
        "SupplyGuard AI supply-chain operations server. "
        "Use the available tools to inspect shipments, assess risk, "
        "evaluate cold-chain integrity, find route alternatives, match "
        "idle fleet assets, and get AI-synthesized operational briefings "
        "powered by IBM Granite via watsonx.ai."
    ),
)

# ---------------------------------------------------------------------------
# Tool registration — 10 tools registered from src/mcp/tools/
# mcp.tool()(fn) is the programmatic equivalent of @mcp.tool() when the
# tool function is defined in a separate module.
# ---------------------------------------------------------------------------
mcp.tool()(get_active_shipments)
mcp.tool()(get_shipment_detail)
mcp.tool()(evaluate_shipment_risk)
mcp.tool()(evaluate_cold_chain)
mcp.tool()(get_route_recommendations)
mcp.tool()(match_fleet_asset)
mcp.tool()(get_active_disruptions)
mcp.tool()(get_disruption_impact)
mcp.tool()(explain_shipment_risk)
mcp.tool()(explain_disruption_impact)

# ---------------------------------------------------------------------------
# STDIO startup
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("SupplyGuard MCP server starting on stdio …")
    mcp.run()
