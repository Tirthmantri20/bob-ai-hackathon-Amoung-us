"""
Deterministic Fallback Generator — Step 4 AI Explanation Layer

Produces a valid AIExplanationResponse from structured evidence dicts
without any external calls.  This module is activated whenever:

  - watsonx.ai credentials are absent or incomplete
  - the SDK raises any exception during a generation call
  - the model returns non-JSON or JSON that fails schema validation

Guarantees
----------
- Never raises an exception.
- Always returns a fully-populated AIExplanationResponse.
- ai_generated is always False.
- model_id is always None.
- All narrative values reference only fields present in the evidence dict.
- Same input → same output (deterministic).

No imports from ibm_watsonx_ai, FastAPI, engine modules, or database modules.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from src.backend.schemas.ai_response import AIExplanationResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity → recommended_action lookup
# ---------------------------------------------------------------------------

_RISK_ACTION_MAP: Dict[str, str] = {
    "CRITICAL": (
        "Immediately initiate emergency carrier transfer and "
        "pre-position a cold-depot hold to prevent further cargo exposure."
    ),
    "HIGH": (
        "Evaluate reroute options without delay and pre-position the "
        "nearest idle refrigerated fleet asset for potential transfer."
    ),
    "MEDIUM": (
        "Monitor closely; validate carrier ETA and confirm telemetry "
        "readings at the next scheduled ping interval."
    ),
    "LOW": (
        "No immediate action required — continue scheduled transit "
        "and maintain standard monitoring cadence."
    ),
}
_DEFAULT_RISK_ACTION = (
    "Review shipment status and confirm current telemetry with the carrier."
)

_CC_ACTION_MAP: Dict[str, str] = {
    "CRITICAL": (
        "Halt transit immediately — cargo may be irreversibly compromised. "
        "Initiate regulatory non-conformance protocol and notify quality assurance."
    ),
    "HIGH": (
        "Pre-position a replacement refrigerated unit and notify the quality "
        "team. Consider cold-depot transfer at the nearest qualified facility."
    ),
    "WARNING": (
        "Increase monitoring frequency. Contact the carrier to inspect "
        "the reefer compressor and verify door-seal integrity."
    ),
    "OK": (
        "No action required — cargo temperature is within specification."
    ),
}
_DEFAULT_CC_ACTION = (
    "Verify telemetry sensor calibration and confirm cargo rule applicability."
)

_DISRUPTION_ACTION_MAP: Dict[str, str] = {
    "CRITICAL": (
        "Immediately reroute all affected shipments and notify impacted "
        "customers. Activate contingency carriers for the affected corridor."
    ),
    "HIGH": (
        "Evaluate alternative corridors for affected shipments and "
        "pre-position idle fleet assets in adjacent logistics zones."
    ),
    "MEDIUM": (
        "Monitor disruption status closely and prepare reroute options "
        "for affected shipments."
    ),
    "LOW": (
        "Track disruption development and review SLA exposure for "
        "any shipments within the proximity radius."
    ),
}
_DEFAULT_DISRUPTION_ACTION = (
    "Review affected shipment list and assess rerouting feasibility."
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _dominant_sub_score(sub_scores: Dict[str, Any]) -> str:
    """Return the name of the highest sub-score dimension."""
    if not sub_scores:
        return "overall risk"
    labels = {
        "r_disruption": "disruption exposure",
        "r_weather": "weather conditions",
        "r_route": "route corridor risk",
        "r_cold_chain": "cold-chain integrity",
        "r_business": "business urgency",
    }
    best_key = max(sub_scores, key=lambda k: sub_scores.get(k) or 0.0)
    return labels.get(best_key, best_key)


# ---------------------------------------------------------------------------
# Public builders — one per use case
# ---------------------------------------------------------------------------

def build_shipment_risk_fallback(evidence: Dict[str, Any]) -> AIExplanationResponse:
    """Deterministic explanation for the shipment_risk use case."""
    entity_id = evidence.get("entity_id", "UNKNOWN")
    severity = str(evidence.get("severity", "UNKNOWN")).upper()
    risk_score = evidence.get("risk_score")
    sub_scores = evidence.get("sub_scores") or {}
    cold = evidence.get("cold_chain") or {}
    origin = evidence.get("origin", "origin")
    destination = evidence.get("destination", "destination")

    # Headline
    score_str = f"{risk_score:.1f}/100" if risk_score is not None else "N/A"
    headline = (
        f"Shipment {entity_id} is at {severity} risk (score: {score_str})."
    )

    # Explanation
    dominant = _dominant_sub_score(sub_scores)
    explanation_parts = [
        f"Shipment {entity_id} travelling from {origin} to {destination} "
        f"has been assessed at {severity} risk with a composite score of "
        f"{score_str}."
    ]
    if dominant:
        explanation_parts.append(
            f"The primary risk driver is {dominant}."
        )
    if cold.get("is_in_excursion"):
        dev = cold.get("deviation_c")
        cc_sev = cold.get("severity", "")
        dev_str = f"{dev:+.2f}°C" if dev is not None else "unknown"
        explanation_parts.append(
            f"An active cold-chain excursion ({cc_sev}) has been detected "
            f"with a temperature deviation of {dev_str}."
        )
    top_route = evidence.get("top_route")
    if top_route:
        explanation_parts.append(
            f"Recommended route '{top_route.get('route_name', 'N/A')}' "
            f"has an estimated ETA of {top_route.get('eta_hours', 'N/A')} hours."
        )

    explanation = " ".join(explanation_parts)

    recommended_action = _RISK_ACTION_MAP.get(severity, _DEFAULT_RISK_ACTION)

    return AIExplanationResponse(
        use_case="shipment_risk",
        entity_id=entity_id,
        headline=headline,
        explanation=explanation,
        recommended_action=recommended_action,
        severity=severity,
        ai_generated=False,
        model_id=None,
        generated_at=_now_utc(),
    )


def build_cold_chain_fallback(evidence: Dict[str, Any]) -> AIExplanationResponse:
    """Deterministic explanation for the cold_chain use case."""
    entity_id = evidence.get("entity_id", "UNKNOWN")
    severity = str(evidence.get("severity", "UNKNOWN")).upper()
    is_in_excursion = evidence.get("is_in_excursion", False)
    is_destructive = evidence.get("is_destructive", False)
    deviation_c = evidence.get("deviation_c")
    cargo_temp_c = evidence.get("cargo_temp_c")
    allowed_min_c = evidence.get("allowed_min_c")
    allowed_max_c = evidence.get("allowed_max_c")
    compliance = evidence.get("compliance_standard", "applicable standard")
    cargo_cat = evidence.get("cargo_category", "cargo")

    if not is_in_excursion:
        headline = (
            f"Shipment {entity_id} cold-chain is intact — "
            f"no excursion detected ({severity})."
        )
        explanation = (
            f"The most recent telemetry for {cargo_cat} shipment {entity_id} "
            f"shows cargo temperature within the allowable range "
            f"({allowed_min_c}°C to {allowed_max_c}°C) per {compliance}. "
            f"Thermal integrity is confirmed."
        )
    elif is_destructive:
        dev_str = f"{deviation_c:+.2f}°C" if deviation_c is not None else "unknown"
        headline = (
            f"CRITICAL: Shipment {entity_id} cargo may be irreversibly "
            f"compromised — destructive threshold breached."
        )
        explanation = (
            f"Cargo temperature for {entity_id} ({cargo_cat}) has exceeded "
            f"the destructive threshold. "
            f"Deviation from allowable maximum: {dev_str}. "
            f"Under {compliance}, this level of exposure may render the "
            f"cargo non-compliant and unfit for use."
        )
    else:
        dev_str = f"{deviation_c:+.2f}°C" if deviation_c is not None else "unknown"
        temp_str = f"{cargo_temp_c}°C" if cargo_temp_c is not None else "unknown"
        headline = (
            f"Shipment {entity_id} cold-chain excursion detected "
            f"— severity: {severity}."
        )
        explanation = (
            f"Current cargo temperature for {entity_id} ({cargo_cat}) is "
            f"{temp_str}, with a deviation of {dev_str} from the "
            f"allowable range ({allowed_min_c}°C to {allowed_max_c}°C). "
            f"This constitutes a {severity} excursion under {compliance}."
        )

    recommended_action = _CC_ACTION_MAP.get(
        severity, _DEFAULT_CC_ACTION
    )

    return AIExplanationResponse(
        use_case="cold_chain",
        entity_id=entity_id,
        headline=headline,
        explanation=explanation,
        recommended_action=recommended_action,
        severity=severity,
        ai_generated=False,
        model_id=None,
        generated_at=_now_utc(),
    )


def build_route_recommendation_fallback(
    evidence: Dict[str, Any],
) -> AIExplanationResponse:
    """Deterministic explanation for the route_recommendation use case."""
    entity_id = evidence.get("entity_id", "UNKNOWN")
    no_route_found = evidence.get("no_route_found", True)
    top_route = evidence.get("top_route")
    route_count = evidence.get("route_count", 0)
    origin = evidence.get("origin", "origin")
    destination = evidence.get("destination", "destination")

    if no_route_found or not top_route:
        headline = (
            f"No route corridor found for shipment {entity_id} "
            f"({origin} → {destination})."
        )
        explanation = (
            f"The route optimizer could not locate a matching corridor for "
            f"shipment {entity_id} between {origin} and {destination}. "
            f"This may indicate a data gap in the route fixture. "
            f"Manual dispatch review is required."
        )
        recommended_action = (
            "Manually assign a route and carrier for this shipment; "
            "escalate to the dispatch supervisor if no corridor is available."
        )
        severity = "INFO"
    else:
        route_name = top_route.get("route_name", "N/A")
        eta = top_route.get("eta_hours", "N/A")
        score = top_route.get("total_score")
        score_str = f"{score:.3f}" if score is not None else "N/A"
        dis_factor = top_route.get("disruption_factor", 0)
        weather_factor = top_route.get("weather_factor", 0)
        warnings = top_route.get("warnings") or []

        headline = (
            f"Recommended route for shipment {entity_id}: "
            f"'{route_name}' (score: {score_str})."
        )

        explanation_parts = [
            f"Among {route_count} evaluated corridor(s) for {entity_id}, "
            f"'{route_name}' scores highest at {score_str} with an "
            f"estimated transit time of {eta} hours."
        ]
        if dis_factor and float(dis_factor) > 0.3:
            explanation_parts.append(
                f"Note: this route carries a disruption exposure factor of "
                f"{dis_factor:.2f}."
            )
        if weather_factor and float(weather_factor) > 0.3:
            explanation_parts.append(
                f"Weather risk factor is {weather_factor:.2f} — "
                f"confirm road conditions before dispatch."
            )
        if warnings:
            explanation_parts.append(
                f"Active warnings: {'; '.join(warnings[:2])}."
            )

        explanation = " ".join(explanation_parts)
        recommended_action = (
            f"Dispatch shipment {entity_id} via '{route_name}'. "
            "Confirm carrier availability and obtain ETA acknowledgement."
        )
        severity = "INFO"

    return AIExplanationResponse(
        use_case="route_recommendation",
        entity_id=entity_id,
        headline=headline,
        explanation=explanation,
        recommended_action=recommended_action,
        severity=severity,
        ai_generated=False,
        model_id=None,
        generated_at=_now_utc(),
    )


def build_fleet_match_fallback(evidence: Dict[str, Any]) -> AIExplanationResponse:
    """Deterministic explanation for the fleet_match use case."""
    entity_id = evidence.get("entity_id", "UNKNOWN")
    no_asset_found = evidence.get("no_asset_found", True)
    top_asset = evidence.get("top_fleet_asset")
    cargo_cat = evidence.get("cargo_category", "cargo")
    asset_count = evidence.get("asset_count", 0)

    if no_asset_found or not top_asset:
        headline = (
            f"No replacement fleet asset available for shipment {entity_id}."
        )
        explanation = (
            f"The fleet matcher found no eligible replacement assets for "
            f"{entity_id} ({cargo_cat}). "
            f"All available assets may already be assigned or insufficient "
            f"in capacity or cooling capability."
        )
        recommended_action = (
            "Contact regional fleet coordinators to identify an available "
            "refrigerated asset or engage a spot-market carrier."
        )
        severity = "INFO"
    else:
        asset_id = top_asset.get("asset_id", "N/A")
        v_type = top_asset.get("vehicle_type", "N/A")
        cooling = top_asset.get("cooling_capability", "N/A")
        prox = top_asset.get("proximity_km")
        score = top_asset.get("total_score")
        score_str = f"{score:.3f}" if score is not None else "N/A"
        prox_str = f"{prox:.1f} km" if prox is not None else "unknown distance"

        headline = (
            f"Best fleet match for shipment {entity_id}: "
            f"{asset_id} ({v_type}) — score {score_str}."
        )
        explanation = (
            f"Among {asset_count} candidate asset(s) evaluated for "
            f"{entity_id} ({cargo_cat}), asset {asset_id} ({v_type}) "
            f"ranks highest with a match score of {score_str}. "
            f"It is approximately {prox_str} from the shipment and "
            f"has {cooling} capability."
        )
        recommended_action = (
            f"Redeploy asset {asset_id} to shipment {entity_id}. "
            "Confirm driver availability and initiate transfer authorisation."
        )
        severity = "INFO"

    return AIExplanationResponse(
        use_case="fleet_match",
        entity_id=entity_id,
        headline=headline,
        explanation=explanation,
        recommended_action=recommended_action,
        severity=severity,
        ai_generated=False,
        model_id=None,
        generated_at=_now_utc(),
    )


def build_disruption_impact_fallback(
    evidence: Dict[str, Any],
) -> AIExplanationResponse:
    """Deterministic explanation for the disruption_impact use case."""
    entity_id = evidence.get("entity_id", "UNKNOWN")
    dis_type = evidence.get("disruption_type", "disruption")
    dis_sev = str(evidence.get("disruption_severity", "UNKNOWN")).upper()
    severity = str(evidence.get("severity", dis_sev)).upper()
    radius_km = evidence.get("proximity_radius_km")
    affected_count = evidence.get("affected_count", 0)
    corridor = evidence.get("affected_corridor") or "the affected corridor"
    description = evidence.get("description", "")

    radius_str = f"{radius_km:.0f} km" if radius_km is not None else "N/A"

    if affected_count == 0:
        headline = (
            f"Disruption {entity_id} ({dis_sev} {dis_type}): "
            f"no active shipments within {radius_str} radius."
        )
        explanation = (
            f"The {dis_sev} {dis_type} event {entity_id} has a monitored "
            f"proximity radius of {radius_str} around {corridor}. "
            f"No active in-transit shipments were found within this radius "
            f"at the time of assessment."
        )
        recommended_action = (
            "Continue monitoring. No immediate rerouting action is required."
        )
    else:
        headline = (
            f"Disruption {entity_id} ({dis_sev} {dis_type}) affects "
            f"{affected_count} active shipment(s) within {radius_str}."
        )
        desc_suffix = f" {description}" if description else ""
        explanation = (
            f"The {dis_sev} {dis_type} event {entity_id} is active in "
            f"the vicinity of {corridor}.{desc_suffix} "
            f"Within the {radius_str} monitoring radius, {affected_count} "
            f"in-transit shipment(s) are potentially affected."
        )
        recommended_action = _DISRUPTION_ACTION_MAP.get(
            dis_sev, _DEFAULT_DISRUPTION_ACTION
        )

    return AIExplanationResponse(
        use_case="disruption_impact",
        entity_id=entity_id,
        headline=headline,
        explanation=explanation,
        recommended_action=recommended_action,
        severity=severity,
        ai_generated=False,
        model_id=None,
        generated_at=_now_utc(),
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_FALLBACK_BUILDERS = {
    "shipment_risk": build_shipment_risk_fallback,
    "cold_chain": build_cold_chain_fallback,
    "route_recommendation": build_route_recommendation_fallback,
    "fleet_match": build_fleet_match_fallback,
    "disruption_impact": build_disruption_impact_fallback,
}


def build_fallback(use_case: str, evidence: Dict[str, Any]) -> AIExplanationResponse:
    """
    Route to the appropriate fallback builder by use_case string.

    Falls back to a safe generic response for unrecognised use_case values —
    never raises an exception.
    """
    builder = _FALLBACK_BUILDERS.get(use_case)
    if builder is not None:
        try:
            return builder(evidence)
        except Exception as exc:  # pragma: no cover — defensive only
            logger.error(
                "Fallback builder for '%s' raised unexpectedly: %s — "
                "returning generic safe response.",
                use_case,
                exc,
            )

    # Generic safe response for unknown use_case or unexpected builder error
    entity_id = evidence.get("entity_id", "UNKNOWN")
    severity = str(evidence.get("severity", "UNKNOWN")).upper()
    return AIExplanationResponse(
        use_case=use_case or "unknown",
        entity_id=entity_id,
        headline=f"Operational assessment for entity {entity_id}.",
        explanation=(
            "A deterministic assessment has been completed for this entity. "
            "Please consult the structured engine output for detailed scores "
            "and classifications."
        ),
        recommended_action=(
            "Review the detailed engine output and consult your operations "
            "supervisor for the appropriate course of action."
        ),
        severity=severity,
        ai_generated=False,
        model_id=None,
        generated_at=_now_utc(),
    )
