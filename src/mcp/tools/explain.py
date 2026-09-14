"""
SupplyGuard MCP — AI Explanation Tools (tools 9–10)
=====================================================

Two tools that trigger the full IBM Granite-backed explanation chain:

    IBM Bob
      → MCP tool
      → POST /api/explain/*
      → FastAPI router (explain.py)
      → Step 2 deterministic engines (RiskEngine, ColdChainEngine, etc.)
      → evidence_builder.build_*_evidence()
      → WatsonxService.generate_explanation()  ← IBM Granite via watsonx.ai
      → AIExplanationResponse
      → MCP (returned verbatim)
      → IBM Bob

These tools are the load-bearing proof that watsonx.ai / Granite is genuinely
integrated, not merely mentioned.  The response always includes:

    ai_generated : bool   — True = live Granite response; False = deterministic fallback
    model_id     : str    — "ibm/granite-3-8b-instruct" when ai_generated=True; null otherwise
    headline     : str    — one-sentence operational summary (≤ 120 chars)
    explanation  : str    — 2–4 sentences grounded in deterministic engine evidence
    recommended_action : str — concrete dispatcher action
    severity     : str    — engine-derived: LOW / MEDIUM / HIGH / CRITICAL / OK / UNKNOWN

If watsonx credentials are not configured, the Step 4 fallback returns a
deterministic explanation with ai_generated=False.  This is transparent to
the MCP tool — it returns whatever FastAPI returns without interpretation.

Imports allowed: src.mcp.client only.
Forbidden imports: src.backend.*, SQLAlchemy, ORM models, engine classes,
                   ibm_watsonx_ai.
"""

from __future__ import annotations

from typing import Any, Dict

from src.mcp.client import api_post


def explain_shipment_risk(shipment_id: str) -> Dict[str, Any]:
    """
    Generate a full AI-synthesized operational explanation for a shipment's
    composite risk status using IBM Granite via watsonx.ai.

    Internally runs all four deterministic engines (Risk, Cold-Chain, Route
    Optimizer, Fleet Matcher), builds structured evidence, and passes it to
    Granite to produce a human-readable operational brief. Returns:
      - headline: one-sentence summary (≤ 120 chars)
      - explanation: 2–4 sentences grounded exclusively in engine evidence
      - recommended_action: concrete immediate action for the dispatcher
      - severity: engine-derived classification (LOW/MEDIUM/HIGH/CRITICAL)
      - ai_generated: true = live Granite response; false = deterministic fallback
      - model_id: 'ibm/granite-3-8b-instruct' when ai_generated=true; null otherwise
    The response is HTTP 200 even when watsonx is unavailable (fallback engages).
    Use this tool when a dispatcher needs to understand WHY a shipment is at
    risk and WHAT to do about it in plain operational language.
    """
    body: Dict[str, Any] = {"entity_id": shipment_id, "use_case": "shipment_risk"}
    return api_post("/api/explain/shipment-risk", body)


def explain_disruption_impact(disruption_id: str) -> Dict[str, Any]:
    """
    Generate an AI-synthesized operational explanation for a disruption event's
    impact on active shipments using IBM Granite via watsonx.ai.

    Computes which shipments fall within the disruption's proximity radius,
    builds structured impact evidence, and passes it to Granite to produce an
    operator-ready incident brief. Returns headline, explanation,
    recommended_action, severity, ai_generated flag, and model_id.
    ai_generated=true when a live Granite response was obtained; false when
    the deterministic fallback was used (e.g. watsonx credentials not set).
    The response is HTTP 200 even when watsonx is unavailable.
    Use this tool to brief a dispatcher on a port strike, weather event, or
    road closure and to identify which shipments require immediate mitigation.
    """
    body: Dict[str, Any] = {"entity_id": disruption_id, "use_case": "disruption_impact"}
    return api_post("/api/explain/disruption-impact", body)
