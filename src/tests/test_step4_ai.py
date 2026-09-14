"""
Step 4 — watsonx.ai / Granite AI Explanation Layer tests

Run:
    pytest src/tests/test_step4_ai.py -v

ZERO live network calls.
All ibm_watsonx_ai SDK interactions are mocked.

Strategy
--------
- app.dependency_overrides[get_watsonx_service] injects a MockWatsonxService
  for all API endpoint tests — identical pattern to Step 3 get_db override.
- unittest.mock.patch on ModelInference used in WatsonxService unit tests.
- WATSONX_APIKEY is intentionally unset for credential-absent tests.

Test groups
-----------
SH-xx   Schema validation (AIExplainRequest, AIExplanationResponse)
EB-xx   Evidence builder contracts
FB-xx   Fallback generator correctness
WS-xx   WatsonxService unit tests (credential-absent, parse paths, SDK errors)
AI-xx   API endpoint integration tests (mock service, seeded DB)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)

from src.backend.ai.evidence_builder import (
    build_cold_chain_evidence,
    build_disruption_impact_evidence,
    build_fleet_match_evidence,
    build_route_recommendation_evidence,
    build_shipment_risk_evidence,
)
from src.backend.ai.fallback import build_fallback
from src.backend.ai.watsonx_service import WatsonxService
from src.backend.api.explain import get_watsonx_service
from src.backend.db.database import Base, get_db
from src.backend.db.seed import seed_database
from src.backend.main import app
from src.backend.schemas.ai_response import AIExplainRequest, AIExplanationResponse


# ---------------------------------------------------------------------------
# MockWatsonxService — injected for all API endpoint tests
# ---------------------------------------------------------------------------

class MockWatsonxService:
    """
    Always returns a valid AIExplanationResponse with ai_generated=True.
    No network calls — no ibm_watsonx_ai imports.
    """

    def generate_explanation(
        self, use_case: str, evidence: Dict[str, Any]
    ) -> AIExplanationResponse:
        return AIExplanationResponse(
            use_case=use_case,
            entity_id=str(evidence.get("entity_id", "MOCK")),
            headline=f"Mock headline for {use_case}.",
            explanation="Mock explanation grounded in deterministic evidence.",
            recommended_action="Mock action for dispatcher.",
            severity=str(evidence.get("severity", "LOW")),
            ai_generated=True,
            model_id="mock/model-test",
            generated_at=datetime.now(tz=timezone.utc),
        )


# ---------------------------------------------------------------------------
# Shared seeded DB + TestClient fixture (scope=module, same as Step 3)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """
    Isolated in-memory SQLite DB, seeded, with get_db and
    get_watsonx_service overridden for the entire module.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    test_session = TestSession()
    seed_database(test_session)

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_watsonx_service] = lambda: MockWatsonxService()

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()
    test_session.close()


# ---------------------------------------------------------------------------
# Minimal evidence dicts for unit tests (no DB required)
# ---------------------------------------------------------------------------

def _risk_dict(
    shipment_id: str = "SHP-TEST",
    score: float = 72.0,
    severity: str = "HIGH",
) -> dict:
    return {
        "shipment_id": shipment_id,
        "total_score": score,
        "severity": severity,
        "r_disruption": 0.6,
        "r_weather": 0.5,
        "r_route": 0.4,
        "r_cold_chain": 0.6,
        "r_business": 0.5,
        "contributing_disruption_ids": ["DIS-501"],
        "weather_fallback": False,
        "cold_chain_fallback": False,
        "route_fallback": False,
    }


def _cold_dict(
    shipment_id: str = "SHP-TEST",
    is_in_excursion: bool = True,
    severity: str = "WARNING",
    deviation_c: float = 0.8,
) -> dict:
    return {
        "shipment_id": shipment_id,
        "telemetry_id": "TEL-001",
        "cargo_rule_found": True,
        "is_in_excursion": is_in_excursion,
        "is_destructive": False,
        "cargo_temp_c": -17.2,
        "allowed_min_c": -22.0,
        "allowed_max_c": -18.0,
        "max_allowable_excursion_temp_c": -15.0,
        "deviation_c": deviation_c,
        "severity": severity,
        "excursion_duration_minutes": None,
        "compliance_standard": "FDA HACCP",
        "cargo_category": "Perishable Frozen",
        "grade": "Perishable Frozen",
    }


def _route_dict(shipment_id: str = "SHP-TEST", no_route: bool = False) -> dict:
    if no_route:
        return {
            "shipment_id": shipment_id,
            "scored_routes": [],
            "no_route_found": True,
        }
    return {
        "shipment_id": shipment_id,
        "scored_routes": [
            {
                "route_id": "RT-001",
                "route_name": "Test Route",
                "total_score": 0.82,
                "eta_hours": 22.5,
                "eta_factor": 0.4,
                "cost_factor": 0.3,
                "disruption_factor": 0.2,
                "weather_factor": 0.15,
                "cold_chain_factor": 0.1,
                "recommended": True,
                "warnings": [],
            }
        ],
        "no_route_found": False,
    }


def _fleet_dict(shipment_id: str = "SHP-TEST", no_asset: bool = False) -> dict:
    if no_asset:
        return {
            "shipment_id": shipment_id,
            "scored_assets": [],
            "no_asset_found": True,
        }
    return {
        "shipment_id": shipment_id,
        "scored_assets": [
            {
                "asset_id": "FLT-302",
                "vehicle_type": "Refrigerated Semi-Trailer",
                "cooling_capability": "STANDARD_COLD",
                "total_score": 0.85,
                "proximity_km": 42.1,
                "proximity_score": 0.9,
                "cargo_compat_score": 0.8,
                "refrigeration_score": 0.9,
                "capacity_score": 1.0,
                "availability_score": 1.0,
                "estimated_shipment_weight_kg": 5000,
                "asset_capacity_kg": 20000,
                "recommended": True,
            }
        ],
        "no_asset_found": False,
    }


def _disruption_impact_dict(entity_id: str = "DIS-TEST", count: int = 2) -> dict:
    return {
        "disruption_id": entity_id,
        "disruption_type": "SEVERE_WEATHER",
        "disruption_severity": "HIGH",
        "proximity_radius_km": 200.0,
        "affected_shipments": [
            {"shipment_id": f"SHP-{i}", "shipment_status": "IN_TRANSIT", "distance_km": 50.0 + i}
            for i in range(count)
        ],
    }


def _shp_attrs(shp_id: str = "SHP-TEST") -> dict:
    return {
        "id": shp_id,
        "origin": "Chicago, IL",
        "destination": "Atlanta, GA",
        "cargo_type": "Pharmaceuticals",
        "cargo_category": "Cold Chain Grade A",
    }


def _dis_attrs(dis_id: str = "DIS-TEST") -> dict:
    return {
        "id": dis_id,
        "type": "SEVERE_WEATHER",
        "severity": "HIGH",
        "title": "Snoqualmie Pass Winter Storm",
        "affected_corridor": "I-90",
        "description": "Snoqualmie Pass Winter Storm",
    }


# ===========================================================================
# SH — Schema validation tests
# ===========================================================================

class TestSchemaValidation:
    def test_sh01_explain_request_valid(self):
        """AIExplainRequest accepts valid entity_id + use_case."""
        req = AIExplainRequest(entity_id="SHP-1001", use_case="shipment_risk")
        assert req.entity_id == "SHP-1001"
        assert req.use_case == "shipment_risk"

    def test_sh02_explain_response_full(self):
        """AIExplanationResponse validates a fully populated dict."""
        resp = AIExplanationResponse(
            use_case="shipment_risk",
            entity_id="SHP-1001",
            headline="Risk is HIGH.",
            explanation="Explanation text.",
            recommended_action="Take action now.",
            severity="HIGH",
            ai_generated=True,
            model_id="ibm/granite-3-8b-instruct",
            generated_at=datetime.now(tz=timezone.utc),
        )
        assert resp.ai_generated is True
        assert resp.model_id == "ibm/granite-3-8b-instruct"

    def test_sh03_explain_response_fallback(self):
        """AIExplanationResponse validates with ai_generated=False, model_id=None."""
        resp = AIExplanationResponse(
            use_case="cold_chain",
            entity_id="SHP-1002",
            headline="Excursion detected.",
            explanation="Details here.",
            recommended_action="Act.",
            severity="WARNING",
            ai_generated=False,
            model_id=None,
            generated_at=datetime.now(tz=timezone.utc),
        )
        assert resp.ai_generated is False
        assert resp.model_id is None

    def test_sh04_explain_response_missing_required_field(self):
        """AIExplanationResponse raises ValidationError when required field is missing."""
        with pytest.raises(ValidationError):
            AIExplanationResponse(
                use_case="shipment_risk",
                # entity_id missing
                headline="H",
                explanation="E",
                recommended_action="A",
                severity="LOW",
                ai_generated=False,
                generated_at=datetime.now(tz=timezone.utc),
            )

    def test_sh05_explain_request_missing_required(self):
        """AIExplainRequest raises ValidationError when entity_id is missing."""
        with pytest.raises(ValidationError):
            AIExplainRequest(use_case="shipment_risk")


# ===========================================================================
# EB — Evidence builder tests
# ===========================================================================

class TestEvidenceBuilder:
    def test_eb01_shipment_risk_has_required_keys(self):
        """build_shipment_risk_evidence returns all required top-level keys."""
        ev = build_shipment_risk_evidence(
            _risk_dict(), _cold_dict(), _route_dict(), _fleet_dict(), _shp_attrs()
        )
        for key in ("use_case", "entity_id", "risk_score", "severity", "sub_scores",
                    "cold_chain", "top_route", "top_fleet_asset"):
            assert key in ev, f"Missing key: {key}"

    def test_eb02_risk_score_uses_engine_scale(self):
        """Risk score in evidence is 0–100 (engine scale), not 0–1 DB scale."""
        ev = build_shipment_risk_evidence(
            _risk_dict(score=72.4), _cold_dict(), _route_dict(), _fleet_dict(), _shp_attrs()
        )
        assert ev["risk_score"] == 72.4
        assert ev["risk_score"] > 1.0, "Risk score must use 0-100 engine scale"

    def test_eb03_top_route_none_when_no_route(self):
        """top_route is None when no_route_found=True."""
        ev = build_shipment_risk_evidence(
            _risk_dict(), _cold_dict(), _route_dict(no_route=True), _fleet_dict(), _shp_attrs()
        )
        assert ev["top_route"] is None
        assert ev["no_route_found"] is True

    def test_eb04_top_fleet_none_when_no_asset(self):
        """top_fleet_asset is None when no_asset_found=True."""
        ev = build_shipment_risk_evidence(
            _risk_dict(), _cold_dict(), _route_dict(), _fleet_dict(no_asset=True), _shp_attrs()
        )
        assert ev["top_fleet_asset"] is None
        assert ev["no_asset_found"] is True

    def test_eb05_cold_chain_evidence_keys(self):
        """build_cold_chain_evidence returns correct excursion fields."""
        ev = build_cold_chain_evidence(_cold_dict(), _shp_attrs())
        for key in ("is_in_excursion", "severity", "deviation_c", "compliance_standard",
                    "allowed_min_c", "allowed_max_c"):
            assert key in ev, f"Missing key: {key}"

    def test_eb06_route_evidence_empty_routes(self):
        """build_route_recommendation_evidence handles empty routes."""
        ev = build_route_recommendation_evidence(_route_dict(no_route=True), _shp_attrs())
        assert ev["no_route_found"] is True
        assert ev["scored_routes"] == []
        assert ev["top_route"] is None

    def test_eb07_fleet_evidence_empty_assets(self):
        """build_fleet_match_evidence handles empty assets."""
        ev = build_fleet_match_evidence(_fleet_dict(no_asset=True), _shp_attrs())
        assert ev["no_asset_found"] is True
        assert ev["scored_assets"] == []
        assert ev["top_fleet_asset"] is None

    def test_eb08_disruption_impact_counts_correctly(self):
        """build_disruption_impact_evidence counts affected shipments correctly."""
        ev = build_disruption_impact_evidence(
            _disruption_impact_dict(count=3), _dis_attrs()
        )
        assert ev["affected_count"] == 3
        assert len(ev["affected_shipments"]) == 3

    def test_eb09_severity_is_plain_string(self):
        """
        Severity in evidence is a plain uppercase string, not 'RiskSeverity.HIGH'.
        This is the regression test for the Enum serialisation fix.
        """
        ev = build_shipment_risk_evidence(
            _risk_dict(severity="HIGH"), _cold_dict(severity="WARNING"),
            _route_dict(), _fleet_dict(), _shp_attrs()
        )
        assert ev["severity"] == "HIGH", f"Expected 'HIGH', got {ev['severity']!r}"
        assert "." not in ev["severity"], "Severity must not contain a dot (e.g. 'RiskSeverity.HIGH')"
        # Also check cold_chain sub-dict
        assert "." not in ev["cold_chain"]["severity"]

    def test_eb10_evidence_is_json_serialisable(self):
        """All five evidence builders produce JSON-serialisable dicts."""
        from src.backend.ai.evidence_builder import _sev
        evs = [
            build_shipment_risk_evidence(
                _risk_dict(), _cold_dict(), _route_dict(), _fleet_dict(), _shp_attrs()
            ),
            build_cold_chain_evidence(_cold_dict(), _shp_attrs()),
            build_route_recommendation_evidence(_route_dict(), _shp_attrs()),
            build_fleet_match_evidence(_fleet_dict(), _shp_attrs()),
            build_disruption_impact_evidence(_disruption_impact_dict(), _dis_attrs()),
        ]
        for ev in evs:
            try:
                json.dumps(ev, default=str)
            except (TypeError, ValueError) as exc:
                pytest.fail(f"Evidence not JSON-serialisable: {exc}")


# ===========================================================================
# FB — Fallback generator tests
# ===========================================================================

class TestFallback:
    def test_fb01_shipment_risk_fallback_valid_response(self):
        """build_fallback('shipment_risk') returns valid AIExplanationResponse."""
        ev = build_shipment_risk_evidence(
            _risk_dict(severity="HIGH"), _cold_dict(), _route_dict(),
            _fleet_dict(), _shp_attrs()
        )
        resp = build_fallback("shipment_risk", ev)
        assert isinstance(resp, AIExplanationResponse)
        assert resp.ai_generated is False
        assert resp.model_id is None
        assert resp.use_case == "shipment_risk"
        assert resp.severity == "HIGH"

    def test_fb02_critical_severity_urgent_action(self):
        """CRITICAL fallback recommended_action contains urgency language."""
        ev = build_shipment_risk_evidence(
            _risk_dict(severity="CRITICAL", score=88.0), _cold_dict(),
            _route_dict(), _fleet_dict(), _shp_attrs()
        )
        resp = build_fallback("shipment_risk", ev)
        action = resp.recommended_action.lower()
        assert any(word in action for word in ("immediately", "emergency", "initiate")), (
            f"CRITICAL action should be urgent, got: {resp.recommended_action!r}"
        )

    def test_fb03_low_severity_no_immediate_action(self):
        """LOW fallback recommended_action contains 'no immediate action'."""
        ev = build_shipment_risk_evidence(
            _risk_dict(severity="LOW", score=15.0), _cold_dict(is_in_excursion=False),
            _route_dict(), _fleet_dict(), _shp_attrs()
        )
        resp = build_fallback("shipment_risk", ev)
        assert "no immediate action" in resp.recommended_action.lower(), (
            f"LOW action should be calm, got: {resp.recommended_action!r}"
        )

    def test_fb04_cold_chain_fallback_references_deviation(self):
        """Cold-chain fallback references the deviation value when in excursion."""
        ev = build_cold_chain_evidence(_cold_dict(is_in_excursion=True, deviation_c=0.8), _shp_attrs())
        resp = build_fallback("cold_chain", ev)
        assert resp.ai_generated is False
        # Deviation or excursion keyword should appear
        assert any(s in resp.explanation for s in ("0.8", "excursion", "WARNING")), (
            f"Expected deviation reference in explanation: {resp.explanation!r}"
        )

    def test_fb05_route_recommendation_no_route_fallback(self):
        """Route recommendation fallback notes no corridor match when no_route_found."""
        ev = build_route_recommendation_evidence(_route_dict(no_route=True), _shp_attrs())
        resp = build_fallback("route_recommendation", ev)
        assert resp.ai_generated is False
        assert "no" in resp.headline.lower() or "not" in resp.explanation.lower(), (
            f"Expected no-route message: {resp.headline!r}"
        )

    def test_fb06_fleet_match_no_asset_fallback(self):
        """Fleet match fallback notes no replacement available."""
        ev = build_fleet_match_evidence(_fleet_dict(no_asset=True), _shp_attrs())
        resp = build_fallback("fleet_match", ev)
        assert resp.ai_generated is False
        assert "no" in resp.headline.lower(), (
            f"Expected no-asset message: {resp.headline!r}"
        )

    def test_fb07_disruption_impact_fallback_states_count(self):
        """Disruption impact fallback states affected shipment count."""
        ev = build_disruption_impact_evidence(_disruption_impact_dict(count=3), _dis_attrs())
        resp = build_fallback("disruption_impact", ev)
        assert resp.ai_generated is False
        assert "3" in resp.headline or "3" in resp.explanation, (
            f"Expected count '3' in narrative: headline={resp.headline!r}"
        )

    def test_fb08_unknown_use_case_safe_response(self):
        """Unknown use_case string → safe generic response, no exception raised."""
        resp = build_fallback("totally_unknown_use_case", {"entity_id": "X", "severity": "LOW"})
        assert isinstance(resp, AIExplanationResponse)
        assert resp.ai_generated is False
        assert resp.entity_id == "X"

    def test_fb09_cold_chain_ok_headline(self):
        """Cold-chain OK (no excursion) fallback confirms thermal integrity."""
        ev = build_cold_chain_evidence(_cold_dict(is_in_excursion=False, severity="OK"), _shp_attrs())
        resp = build_fallback("cold_chain", ev)
        assert "intact" in resp.headline.lower() or "no excursion" in resp.headline.lower(), (
            f"OK fallback headline should confirm integrity: {resp.headline!r}"
        )


# ===========================================================================
# WS — WatsonxService unit tests
# ===========================================================================

class TestWatsonxService:
    def test_ws01_no_credentials_model_is_none(self):
        """Service instantiates without credentials → _model is None."""
        with patch.dict(os.environ, {
            "WATSONX_APIKEY": "",
            "WATSONX_PROJECT_ID": "",
            "WATSONX_URL": "",
            "WATSONX_MODEL_ID": "",
        }):
            svc = WatsonxService()
            assert svc.is_live is False

    def test_ws02_no_credentials_returns_fallback(self):
        """generate_explanation() with no credentials returns ai_generated=False."""
        with patch.dict(os.environ, {
            "WATSONX_APIKEY": "",
            "WATSONX_PROJECT_ID": "",
            "WATSONX_URL": "",
            "WATSONX_MODEL_ID": "",
        }):
            svc = WatsonxService()
            ev = build_shipment_risk_evidence(
                _risk_dict(), _cold_dict(), _route_dict(), _fleet_dict(), _shp_attrs()
            )
            resp = svc.generate_explanation("shipment_risk", ev)
            assert resp.ai_generated is False
            assert resp.model_id is None

    def test_ws03_valid_json_response_returns_ai_generated_true(self):
        """Mock returning valid JSON → ai_generated=True with correct fields."""
        valid_json = json.dumps({
            "headline": "Risk is HIGH for this shipment.",
            "explanation": "The disruption sub-score is 0.63 and weather is 0.80.",
            "recommended_action": "Initiate reroute via bypass corridor immediately.",
        })

        with patch.dict(os.environ, {
            "WATSONX_APIKEY": "fake-key",
            "WATSONX_PROJECT_ID": "fake-project",
            "WATSONX_URL": "https://fake.ml.cloud.ibm.com",
            "WATSONX_MODEL_ID": "ibm/granite-3-8b-instruct",
        }):
            with patch(
                "src.backend.ai.watsonx_service.ModelInference"
            ) as MockModelInference:
                mock_instance = MagicMock()
                mock_instance.generate_text.return_value = valid_json
                MockModelInference.return_value = mock_instance

                svc = WatsonxService()
                ev = build_shipment_risk_evidence(
                    _risk_dict(severity="HIGH"), _cold_dict(), _route_dict(),
                    _fleet_dict(), _shp_attrs()
                )
                resp = svc.generate_explanation("shipment_risk", ev)

                assert resp.ai_generated is True
                assert resp.model_id == "ibm/granite-3-8b-instruct"
                assert resp.headline == "Risk is HIGH for this shipment."
                assert resp.severity == "HIGH"  # engine-derived, not from model

    def test_ws04_malformed_json_returns_fallback(self):
        """Mock returning 'not valid json' → ai_generated=False fallback."""
        with patch.dict(os.environ, {
            "WATSONX_APIKEY": "k",
            "WATSONX_PROJECT_ID": "p",
            "WATSONX_URL": "u",
            "WATSONX_MODEL_ID": "m",
        }):
            with patch(
                "src.backend.ai.watsonx_service.ModelInference"
            ) as MockModelInference:
                mock_instance = MagicMock()
                mock_instance.generate_text.return_value = "this is not json at all"
                MockModelInference.return_value = mock_instance

                svc = WatsonxService()
                ev = build_cold_chain_evidence(_cold_dict(), _shp_attrs())
                resp = svc.generate_explanation("cold_chain", ev)
                assert resp.ai_generated is False
                assert resp.model_id is None

    def test_ws05_valid_json_missing_headline_key_returns_fallback(self):
        """Valid JSON missing 'headline' key → fallback (ai_generated=False)."""
        bad_json = json.dumps({
            "explanation": "Some explanation.",
            "recommended_action": "Do something.",
            # "headline" intentionally absent
        })
        with patch.dict(os.environ, {
            "WATSONX_APIKEY": "k",
            "WATSONX_PROJECT_ID": "p",
            "WATSONX_URL": "u",
            "WATSONX_MODEL_ID": "m",
        }):
            with patch(
                "src.backend.ai.watsonx_service.ModelInference"
            ) as MockModelInference:
                mock_instance = MagicMock()
                mock_instance.generate_text.return_value = bad_json
                MockModelInference.return_value = mock_instance

                svc = WatsonxService()
                ev = build_cold_chain_evidence(_cold_dict(), _shp_attrs())
                resp = svc.generate_explanation("cold_chain", ev)
                assert resp.ai_generated is False

    def test_ws06_valid_json_empty_string_values_returns_fallback(self):
        """JSON with all keys but empty string values → fallback."""
        bad_json = json.dumps({
            "headline": "",
            "explanation": "",
            "recommended_action": "",
        })
        with patch.dict(os.environ, {
            "WATSONX_APIKEY": "k",
            "WATSONX_PROJECT_ID": "p",
            "WATSONX_URL": "u",
            "WATSONX_MODEL_ID": "m",
        }):
            with patch(
                "src.backend.ai.watsonx_service.ModelInference"
            ) as MockModelInference:
                mock_instance = MagicMock()
                mock_instance.generate_text.return_value = bad_json
                MockModelInference.return_value = mock_instance

                svc = WatsonxService()
                ev = build_cold_chain_evidence(_cold_dict(), _shp_attrs())
                resp = svc.generate_explanation("cold_chain", ev)
                assert resp.ai_generated is False

    def test_ws07_sdk_raises_exception_returns_fallback(self):
        """generate_text() raising Exception → fallback, no exception propagated."""
        with patch.dict(os.environ, {
            "WATSONX_APIKEY": "k",
            "WATSONX_PROJECT_ID": "p",
            "WATSONX_URL": "u",
            "WATSONX_MODEL_ID": "m",
        }):
            with patch(
                "src.backend.ai.watsonx_service.ModelInference"
            ) as MockModelInference:
                mock_instance = MagicMock()
                mock_instance.generate_text.side_effect = Exception("SDK network error")
                MockModelInference.return_value = mock_instance

                svc = WatsonxService()
                ev = build_fleet_match_evidence(_fleet_dict(), _shp_attrs())
                # Must not raise
                resp = svc.generate_explanation("fleet_match", ev)
                assert resp.ai_generated is False

    def test_ws08_ai_generated_true_echoes_correct_use_case_and_entity(self):
        """Live path: ai_generated=True response echoes correct use_case and entity_id."""
        valid_json = json.dumps({
            "headline": "Fleet match headline.",
            "explanation": "Explanation here.",
            "recommended_action": "Redeploy FLT-302.",
        })
        with patch.dict(os.environ, {
            "WATSONX_APIKEY": "k",
            "WATSONX_PROJECT_ID": "p",
            "WATSONX_URL": "u",
            "WATSONX_MODEL_ID": "ibm/granite-3-8b-instruct",
        }):
            with patch(
                "src.backend.ai.watsonx_service.ModelInference"
            ) as MockModelInference:
                mock_instance = MagicMock()
                mock_instance.generate_text.return_value = valid_json
                MockModelInference.return_value = mock_instance

                svc = WatsonxService()
                ev = build_fleet_match_evidence(_fleet_dict("SHP-9999"), _shp_attrs("SHP-9999"))
                resp = svc.generate_explanation("fleet_match", ev)
                assert resp.use_case == "fleet_match"
                assert resp.entity_id == "SHP-9999"
                assert resp.ai_generated is True

    def test_ws09_model_id_matches_env_var(self):
        """model_id in response matches WATSONX_MODEL_ID env var."""
        valid_json = json.dumps({
            "headline": "Disruption headline.",
            "explanation": "Disruption explanation.",
            "recommended_action": "Reroute.",
        })
        with patch.dict(os.environ, {
            "WATSONX_APIKEY": "k",
            "WATSONX_PROJECT_ID": "p",
            "WATSONX_URL": "u",
            "WATSONX_MODEL_ID": "ibm/granite-3-2b-instruct",
        }):
            with patch(
                "src.backend.ai.watsonx_service.ModelInference"
            ) as MockModelInference:
                mock_instance = MagicMock()
                mock_instance.generate_text.return_value = valid_json
                MockModelInference.return_value = mock_instance

                svc = WatsonxService()
                ev = build_disruption_impact_evidence(_disruption_impact_dict(), _dis_attrs())
                resp = svc.generate_explanation("disruption_impact", ev)
                assert resp.model_id == "ibm/granite-3-2b-instruct"

    def test_ws10_severity_always_from_engine_not_model(self):
        """
        Model response severity is IGNORED.
        severity in AIExplanationResponse must always come from the evidence
        (engine-derived), even if the model attempts to override it.
        """
        # Model tries to sneak severity into response — our parser ignores it
        json_with_extra = json.dumps({
            "headline": "Risk is CRITICAL.",
            "explanation": "Explanation.",
            "recommended_action": "Act now.",
            "severity": "CRITICAL",  # model should NOT be able to set this
        })
        with patch.dict(os.environ, {
            "WATSONX_APIKEY": "k",
            "WATSONX_PROJECT_ID": "p",
            "WATSONX_URL": "u",
            "WATSONX_MODEL_ID": "m",
        }):
            with patch(
                "src.backend.ai.watsonx_service.ModelInference"
            ) as MockModelInference:
                mock_instance = MagicMock()
                mock_instance.generate_text.return_value = json_with_extra
                MockModelInference.return_value = mock_instance

                svc = WatsonxService()
                # evidence has severity LOW — this must be preserved
                ev = build_shipment_risk_evidence(
                    _risk_dict(severity="LOW", score=15.0), _cold_dict(),
                    _route_dict(), _fleet_dict(), _shp_attrs()
                )
                resp = svc.generate_explanation("shipment_risk", ev)
                assert resp.severity == "LOW", (
                    f"severity must be engine-derived 'LOW', "
                    f"got {resp.severity!r}"
                )


# ===========================================================================
# AI — API endpoint integration tests (MockWatsonxService + seeded DB)
# ===========================================================================

class TestExplainEndpoints:
    def test_ai01_shipment_risk_200(self, client):
        """POST /api/explain/shipment-risk SHP-1001 → 200, valid response."""
        resp = client.post(
            "/api/explain/shipment-risk",
            json={"entity_id": "SHP-1001", "use_case": "shipment_risk"},
        )
        assert resp.status_code == 200
        body = resp.json()
        AIExplanationResponse.model_validate(body)  # schema validation
        assert body["entity_id"] == "SHP-1001"
        assert body["use_case"] == "shipment_risk"

    def test_ai02_shipment_risk_404(self, client):
        """POST /api/explain/shipment-risk with unknown ID → 404."""
        resp = client.post(
            "/api/explain/shipment-risk",
            json={"entity_id": "SHP-NOTEXIST", "use_case": "shipment_risk"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_ai03_cold_chain_200(self, client):
        """POST /api/explain/cold-chain SHP-1002 → 200, severity is non-empty."""
        resp = client.post(
            "/api/explain/cold-chain",
            json={"entity_id": "SHP-1002", "use_case": "cold_chain"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["severity"] not in ("", None)
        AIExplanationResponse.model_validate(body)

    def test_ai04_route_recommendation_200(self, client):
        """POST /api/explain/route-recommendation SHP-1001 → 200, valid schema."""
        resp = client.post(
            "/api/explain/route-recommendation",
            json={"entity_id": "SHP-1001", "use_case": "route_recommendation"},
        )
        assert resp.status_code == 200
        AIExplanationResponse.model_validate(resp.json())

    def test_ai05_fleet_match_200(self, client):
        """POST /api/explain/fleet-match SHP-1003 → 200."""
        resp = client.post(
            "/api/explain/fleet-match",
            json={"entity_id": "SHP-1003", "use_case": "fleet_match"},
        )
        assert resp.status_code == 200
        body = resp.json()
        AIExplanationResponse.model_validate(body)

    def test_ai06_disruption_impact_200(self, client):
        """POST /api/explain/disruption-impact DIS-501 → 200."""
        resp = client.post(
            "/api/explain/disruption-impact",
            json={"entity_id": "DIS-501", "use_case": "disruption_impact"},
        )
        assert resp.status_code == 200
        AIExplanationResponse.model_validate(resp.json())

    def test_ai07_disruption_impact_404(self, client):
        """POST /api/explain/disruption-impact with unknown ID → 404."""
        resp = client.post(
            "/api/explain/disruption-impact",
            json={"entity_id": "DIS-NOTEXIST", "use_case": "disruption_impact"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_ai08_mock_service_ai_generated_true(self, client):
        """MockWatsonxService always sets ai_generated=True."""
        resp = client.post(
            "/api/explain/shipment-risk",
            json={"entity_id": "SHP-1002", "use_case": "shipment_risk"},
        )
        assert resp.status_code == 200
        assert resp.json()["ai_generated"] is True

    def test_ai09_all_endpoints_conform_to_schema(self, client):
        """All five endpoints return a body that validates against AIExplanationResponse."""
        cases = [
            ("/api/explain/shipment-risk",        "SHP-1001"),
            ("/api/explain/cold-chain",           "SHP-1002"),
            ("/api/explain/route-recommendation", "SHP-1001"),
            ("/api/explain/fleet-match",          "SHP-1003"),
            ("/api/explain/disruption-impact",    "DIS-503"),
        ]
        for path, entity_id in cases:
            resp = client.post(path, json={"entity_id": entity_id, "use_case": "test"})
            assert resp.status_code == 200, f"Expected 200 for {path}"
            try:
                AIExplanationResponse.model_validate(resp.json())
            except ValidationError as exc:
                pytest.fail(f"{path} response failed schema validation: {exc}")

    def test_ai10_explain_does_not_persist_risk_score(self, client):
        """
        Calling /api/explain/shipment-risk must not change the stored
        current_risk_score on the shipment.
        """
        before = client.get("/api/shipments/SHP-1001").json()["current_risk_score"]
        client.post(
            "/api/explain/shipment-risk",
            json={"entity_id": "SHP-1001", "use_case": "shipment_risk"},
        )
        after = client.get("/api/shipments/SHP-1001").json()["current_risk_score"]
        assert before == after, (
            f"current_risk_score changed after explain call: {before} → {after}"
        )

    def test_ai11_severity_is_plain_string_in_api_response(self, client):
        """
        API response severity must be a plain string like 'MEDIUM', not
        'RiskSeverity.MEDIUM'. Regression test for Enum serialisation fix.
        """
        resp = client.post(
            "/api/explain/shipment-risk",
            json={"entity_id": "SHP-1002", "use_case": "shipment_risk"},
        )
        assert resp.status_code == 200
        severity = resp.json()["severity"]
        assert "." not in severity, (
            f"severity must be a plain string, got {severity!r}"
        )
        assert severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL", "OK", "UNKNOWN", "INFO"), (
            f"Unexpected severity value: {severity!r}"
        )

    def test_ai12_invalid_request_body_422(self, client):
        """POST with no body fields → 422 Unprocessable Entity."""
        resp = client.post("/api/explain/shipment-risk", json={})
        assert resp.status_code == 422

    def test_ai13_cold_chain_404(self, client):
        """POST /api/explain/cold-chain with unknown shipment → 404."""
        resp = client.post(
            "/api/explain/cold-chain",
            json={"entity_id": "SHP-NOTEXIST", "use_case": "cold_chain"},
        )
        assert resp.status_code == 404

    def test_ai14_fleet_match_404(self, client):
        """POST /api/explain/fleet-match with unknown shipment → 404."""
        resp = client.post(
            "/api/explain/fleet-match",
            json={"entity_id": "SHP-NOTEXIST", "use_case": "fleet_match"},
        )
        assert resp.status_code == 404

    def test_ai15_route_recommendation_404(self, client):
        """POST /api/explain/route-recommendation with unknown shipment → 404."""
        resp = client.post(
            "/api/explain/route-recommendation",
            json={"entity_id": "SHP-NOTEXIST", "use_case": "route_recommendation"},
        )
        assert resp.status_code == 404
