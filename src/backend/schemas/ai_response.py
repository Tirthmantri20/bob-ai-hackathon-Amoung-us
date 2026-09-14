"""
AI Explanation Schemas — Step 4 watsonx.ai Integration Layer

Pydantic v2 models for the POST /api/explain/* endpoints.

AIExplainRequest  — request body accepted by all five explain endpoints.
AIExplanationResponse — response returned by all five explain endpoints,
    regardless of whether the AI path or the deterministic fallback was used.

The `ai_generated` flag is the auditable proof token:
    True  → narrative was produced by watsonx.ai / Granite
    False → narrative was produced by the deterministic fallback

The `severity` field always carries the engine-derived classification
(LOW / MEDIUM / HIGH / CRITICAL / OK / UNKNOWN).  It is NEVER overwritten
by the model response; the model only produces headline/explanation/action.

No imports from ibm_watsonx_ai, engine modules, or database modules here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request body
# ---------------------------------------------------------------------------

class AIExplainRequest(BaseModel):
    """
    Request body for all POST /api/explain/* endpoints.

    entity_id  — shipment ID (SHP-xxxx) for shipment-related use cases, or
                 disruption ID (DIS-xxx) for disruption-impact.
    use_case   — one of: "shipment_risk", "cold_chain",
                 "route_recommendation", "fleet_match", "disruption_impact".
                 The router validates the value via the endpoint path, so
                 this field is primarily informational / for logging.
    """

    model_config = ConfigDict(from_attributes=False)

    entity_id: str = Field(
        ...,
        description="Shipment ID or Disruption ID to explain.",
        examples=["SHP-1002", "DIS-501"],
    )
    use_case: str = Field(
        ...,
        description=(
            "Use-case identifier: shipment_risk | cold_chain | "
            "route_recommendation | fleet_match | disruption_impact"
        ),
        examples=["shipment_risk"],
    )


# ---------------------------------------------------------------------------
# Response body
# ---------------------------------------------------------------------------

class AIExplanationResponse(BaseModel):
    """
    Unified response returned by all POST /api/explain/* endpoints.

    Fields populated by the deterministic engine layer (never by the model):
        use_case, entity_id, severity

    Fields populated by watsonx.ai / Granite (or fallback):
        headline, explanation, recommended_action

    Proof / audit fields:
        ai_generated — True iff the narrative came from a live Granite call
        model_id     — echoed model identifier when ai_generated=True; None otherwise
        generated_at — UTC timestamp of this response
    """

    model_config = ConfigDict(from_attributes=False)

    use_case: str = Field(
        ...,
        description="Use-case identifier echoed from the request.",
    )
    entity_id: str = Field(
        ...,
        description="Shipment or disruption ID echoed from the request.",
    )

    # --- Narrative fields (AI or fallback) ---
    headline: str = Field(
        ...,
        description="One-sentence operational summary (≤ 120 characters).",
    )
    explanation: str = Field(
        ...,
        description=(
            "2–4 sentence narrative grounded exclusively in the "
            "structured evidence from the deterministic engines."
        ),
    )
    recommended_action: str = Field(
        ...,
        description="Immediate concrete action for the operations dispatcher.",
    )

    # --- Engine-derived field (never model-derived) ---
    severity: str = Field(
        ...,
        description=(
            "Risk/excursion severity echoed from the deterministic engine: "
            "LOW | MEDIUM | HIGH | CRITICAL | OK | UNKNOWN"
        ),
    )

    # --- Proof / audit fields ---
    ai_generated: bool = Field(
        ...,
        description=(
            "True if the headline/explanation/recommended_action were produced "
            "by a live watsonx.ai / Granite call. "
            "False if the deterministic fallback was used."
        ),
    )
    model_id: Optional[str] = Field(
        default=None,
        description=(
            "Granite model identifier used for generation "
            "(e.g. 'ibm/granite-3-8b-instruct'). "
            "None when ai_generated=False."
        ),
    )
    generated_at: datetime = Field(
        ...,
        description="UTC timestamp at which this response was produced.",
    )
