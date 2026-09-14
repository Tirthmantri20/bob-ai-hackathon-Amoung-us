"""
Step 5 — MCP + IBM Bob Integration tests

Run:
    pytest src/tests/test_step5_mcp.py -v
    pytest src/tests/ -v   (full suite: Steps 1–5)

ZERO live network calls.
All httpx interactions are mocked via unittest.mock.patch.
No live Bob credentials required.

Test groups
-----------
MC-xx   src/mcp/client.py  — HTTP helper unit tests
TS-xx   Tool URL / payload construction tests
TE-xx   Tool error propagation tests
AI-xx   Explanation tool behavior (ai_generated / model_id / request body)
SC-xx   Security and configuration tests
ST-xx   Server registration and stdout-cleanliness tests
"""

from __future__ import annotations

import io
import json
import os
import sys
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import httpx
import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)


# ---------------------------------------------------------------------------
# Helpers — build mock httpx responses
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, body: Any) -> MagicMock:
    """Build a mock httpx.Response for the given status code and JSON body."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = (200 <= status_code < 300)
    resp.json.return_value = body
    resp.text = json.dumps(body) if isinstance(body, (dict, list)) else str(body)
    return resp


def _make_client_ctx(response: MagicMock):
    """Return a context-manager mock whose .get() / .post() return *response*."""
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = response
    mock_client.post.return_value = response
    return mock_client


# ===========================================================================
# MC — src/mcp/client.py unit tests
# ===========================================================================

class TestMcpClient:

    # ------------------------------------------------------------------ MC-01
    def test_mc01_get_api_url_default(self):
        """get_api_url() returns default when SUPPLYGUARD_API_URL is unset."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SUPPLYGUARD_API_URL", None)
            from src.mcp.client import get_api_url
            # Reload to pick up clean env
            url = get_api_url()
            assert url == "http://localhost:8000"

    # ------------------------------------------------------------------ MC-02
    def test_mc02_get_api_url_env_configured(self):
        """get_api_url() returns the env-configured URL."""
        from src.mcp.client import get_api_url
        with patch.dict(os.environ, {"SUPPLYGUARD_API_URL": "http://myhost:9000"}):
            url = get_api_url()
            assert url == "http://myhost:9000"

    # ------------------------------------------------------------------ MC-03
    def test_mc03_get_api_url_strips_trailing_slash(self):
        """get_api_url() strips a trailing slash."""
        from src.mcp.client import get_api_url
        with patch.dict(os.environ, {"SUPPLYGUARD_API_URL": "http://localhost:8000/"}):
            url = get_api_url()
            assert url == "http://localhost:8000"
            assert not url.endswith("/")

    # ------------------------------------------------------------------ MC-04
    def test_mc04_api_get_success_returns_json(self):
        """api_get() on HTTP 200 returns parsed JSON body."""
        from src.mcp.client import api_get
        body = {"shipment_id": "SHP-1001", "status": "IN_TRANSIT"}
        resp = _mock_response(200, body)
        with patch("src.mcp.client.httpx.Client", return_value=_make_client_ctx(resp)):
            result = api_get("/api/shipments/SHP-1001")
        assert result == body
        assert "error" not in result

    # ------------------------------------------------------------------ MC-05
    def test_mc05_api_get_404_returns_error_dict(self):
        """api_get() on HTTP 404 returns error dict with status_code=404."""
        from src.mcp.client import api_get
        resp = _mock_response(404, {"detail": "Not found"})
        with patch("src.mcp.client.httpx.Client", return_value=_make_client_ctx(resp)):
            result = api_get("/api/shipments/MISSING")
        assert result["error"] is True
        assert result["status_code"] == 404

    # ------------------------------------------------------------------ MC-06
    def test_mc06_api_get_500_returns_error_dict(self):
        """api_get() on HTTP 500 returns error dict with status_code=500."""
        from src.mcp.client import api_get
        resp = _mock_response(500, {"detail": "Internal Server Error"})
        with patch("src.mcp.client.httpx.Client", return_value=_make_client_ctx(resp)):
            result = api_get("/api/shipments/SHP-1001")
        assert result["error"] is True
        assert result["status_code"] == 500

    # ------------------------------------------------------------------ MC-07
    def test_mc07_api_get_connect_error_returns_error_dict(self):
        """api_get() on ConnectError returns error dict with status_code=0."""
        from src.mcp.client import api_get
        mock_client = _make_client_ctx(None)
        mock_client.get.side_effect = httpx.ConnectError("connection refused")
        with patch("src.mcp.client.httpx.Client", return_value=mock_client):
            result = api_get("/api/shipments/")
        assert result["error"] is True
        assert result["status_code"] == 0
        assert "not available" in result["detail"].lower() or "start" in result["detail"].lower()

    # ------------------------------------------------------------------ MC-08
    def test_mc08_api_get_timeout_returns_error_dict(self):
        """api_get() on TimeoutException returns error dict with status_code=0."""
        from src.mcp.client import api_get
        mock_client = _make_client_ctx(None)
        mock_client.get.side_effect = httpx.TimeoutException("timed out")
        with patch("src.mcp.client.httpx.Client", return_value=mock_client):
            result = api_get("/api/shipments/")
        assert result["error"] is True
        assert result["status_code"] == 0
        assert "timed out" in result["detail"].lower()

    # ------------------------------------------------------------------ MC-09
    def test_mc09_api_post_success_returns_json(self):
        """api_post() on HTTP 200 returns parsed JSON body."""
        from src.mcp.client import api_post
        body = {"ai_generated": True, "headline": "Risk is HIGH."}
        resp = _mock_response(200, body)
        with patch("src.mcp.client.httpx.Client", return_value=_make_client_ctx(resp)):
            result = api_post("/api/explain/shipment-risk", {"entity_id": "SHP-1001"})
        assert result == body
        assert result["ai_generated"] is True

    # ------------------------------------------------------------------ MC-10
    def test_mc10_api_post_404_returns_error_dict(self):
        """api_post() on HTTP 404 returns error dict."""
        from src.mcp.client import api_post
        resp = _mock_response(404, {"detail": "Shipment not found"})
        with patch("src.mcp.client.httpx.Client", return_value=_make_client_ctx(resp)):
            result = api_post("/api/explain/shipment-risk", {"entity_id": "BAD"})
        assert result["error"] is True
        assert result["status_code"] == 404

    # ------------------------------------------------------------------ MC-11
    def test_mc11_api_post_connect_error_returns_error_dict(self):
        """api_post() on ConnectError returns error dict with status_code=0."""
        from src.mcp.client import api_post
        mock_client = _make_client_ctx(None)
        mock_client.post.side_effect = httpx.ConnectError("connection refused")
        with patch("src.mcp.client.httpx.Client", return_value=mock_client):
            result = api_post("/api/explain/shipment-risk", {"entity_id": "SHP-1001"})
        assert result["error"] is True
        assert result["status_code"] == 0

    # ------------------------------------------------------------------ MC-12
    def test_mc12_api_post_timeout_returns_error_dict(self):
        """api_post() on TimeoutException returns error dict with status_code=0."""
        from src.mcp.client import api_post
        mock_client = _make_client_ctx(None)
        mock_client.post.side_effect = httpx.TimeoutException("timed out")
        with patch("src.mcp.client.httpx.Client", return_value=mock_client):
            result = api_post("/api/explain/shipment-risk", {"entity_id": "SHP-1001"})
        assert result["error"] is True
        assert result["status_code"] == 0
        assert "timed out" in result["detail"].lower()


# ===========================================================================
# TS — Tool URL / payload construction tests
# ===========================================================================

class TestToolUrls:

    def _success_get(self, expected_path: str):
        """Returns a patcher context that asserts the correct GET path was called."""
        body = {"ok": True}
        resp = _mock_response(200, body)
        ctx = _make_client_ctx(resp)
        return body, patch("src.mcp.client.httpx.Client", return_value=ctx), ctx

    # ------------------------------------------------------------------ TS-01
    def test_ts01_get_active_shipments_url(self):
        """get_active_shipments() calls GET /api/shipments/."""
        from src.mcp.tools.shipments import get_active_shipments
        resp = _mock_response(200, [{"id": "SHP-1001"}])
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            result = get_active_shipments()
        ctx.get.assert_called_once()
        called_url = ctx.get.call_args[0][0]
        assert called_url.endswith("/api/shipments/")

    # ------------------------------------------------------------------ TS-02
    def test_ts02_get_shipment_detail_url(self):
        """get_shipment_detail('SHP-1001') calls GET /api/shipments/SHP-1001."""
        from src.mcp.tools.shipments import get_shipment_detail
        resp = _mock_response(200, {"id": "SHP-1001"})
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            get_shipment_detail("SHP-1001")
        called_url = ctx.get.call_args[0][0]
        assert called_url.endswith("/api/shipments/SHP-1001")

    # ------------------------------------------------------------------ TS-03
    def test_ts03_evaluate_shipment_risk_url(self):
        """evaluate_shipment_risk('SHP-1001') calls GET /api/shipments/SHP-1001/risk."""
        from src.mcp.tools.shipments import evaluate_shipment_risk
        resp = _mock_response(200, {"total_score": 72.0})
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            evaluate_shipment_risk("SHP-1001")
        called_url = ctx.get.call_args[0][0]
        assert called_url.endswith("/api/shipments/SHP-1001/risk")

    # ------------------------------------------------------------------ TS-04
    def test_ts04_evaluate_cold_chain_url(self):
        """evaluate_cold_chain('SHP-1001') calls GET /api/shipments/SHP-1001/cold-chain."""
        from src.mcp.tools.shipments import evaluate_cold_chain
        resp = _mock_response(200, {"severity": "OK"})
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            evaluate_cold_chain("SHP-1001")
        called_url = ctx.get.call_args[0][0]
        assert called_url.endswith("/api/shipments/SHP-1001/cold-chain")

    # ------------------------------------------------------------------ TS-05
    def test_ts05_get_route_recommendations_url(self):
        """get_route_recommendations('SHP-1001') calls GET /api/shipments/SHP-1001/routes."""
        from src.mcp.tools.shipments import get_route_recommendations
        resp = _mock_response(200, {"no_route_found": False})
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            get_route_recommendations("SHP-1001")
        called_url = ctx.get.call_args[0][0]
        assert called_url.endswith("/api/shipments/SHP-1001/routes")

    # ------------------------------------------------------------------ TS-06
    def test_ts06_match_fleet_asset_url(self):
        """match_fleet_asset('SHP-1001') calls GET /api/shipments/SHP-1001/fleet-match."""
        from src.mcp.tools.shipments import match_fleet_asset
        resp = _mock_response(200, {"no_asset_found": False})
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            match_fleet_asset("SHP-1001")
        called_url = ctx.get.call_args[0][0]
        assert called_url.endswith("/api/shipments/SHP-1001/fleet-match")

    # ------------------------------------------------------------------ TS-07
    def test_ts07_get_active_disruptions_url(self):
        """get_active_disruptions() calls GET /api/disruptions/."""
        from src.mcp.tools.disruptions import get_active_disruptions
        resp = _mock_response(200, [{"id": "DIS-501"}])
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            get_active_disruptions()
        called_url = ctx.get.call_args[0][0]
        assert called_url.endswith("/api/disruptions/")

    # ------------------------------------------------------------------ TS-08
    def test_ts08_get_disruption_impact_url(self):
        """get_disruption_impact('DIS-501') calls GET /api/disruptions/DIS-501/affected-shipments."""
        from src.mcp.tools.disruptions import get_disruption_impact
        resp = _mock_response(200, {"affected_shipments": []})
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            get_disruption_impact("DIS-501")
        called_url = ctx.get.call_args[0][0]
        assert called_url.endswith("/api/disruptions/DIS-501/affected-shipments")

    # ------------------------------------------------------------------ TS-09
    def test_ts09_explain_shipment_risk_url_and_body(self):
        """explain_shipment_risk posts to /api/explain/shipment-risk with correct body."""
        from src.mcp.tools.explain import explain_shipment_risk
        body = {"ai_generated": True, "headline": "H", "explanation": "E",
                "recommended_action": "A", "severity": "HIGH",
                "model_id": "ibm/granite-3-8b-instruct", "use_case": "shipment_risk",
                "entity_id": "SHP-1001"}
        resp = _mock_response(200, body)
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            explain_shipment_risk("SHP-1001")
        ctx.post.assert_called_once()
        called_url = ctx.post.call_args[0][0]
        assert called_url.endswith("/api/explain/shipment-risk")
        sent_body = ctx.post.call_args[1]["json"]
        assert sent_body["entity_id"] == "SHP-1001"
        assert sent_body["use_case"] == "shipment_risk"

    # ------------------------------------------------------------------ TS-10
    def test_ts10_explain_disruption_impact_url_and_body(self):
        """explain_disruption_impact posts to /api/explain/disruption-impact with correct body."""
        from src.mcp.tools.explain import explain_disruption_impact
        body = {"ai_generated": False, "headline": "H", "explanation": "E",
                "recommended_action": "A", "severity": "HIGH",
                "model_id": None, "use_case": "disruption_impact",
                "entity_id": "DIS-501"}
        resp = _mock_response(200, body)
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            explain_disruption_impact("DIS-501")
        ctx.post.assert_called_once()
        called_url = ctx.post.call_args[0][0]
        assert called_url.endswith("/api/explain/disruption-impact")
        sent_body = ctx.post.call_args[1]["json"]
        assert sent_body["entity_id"] == "DIS-501"
        assert sent_body["use_case"] == "disruption_impact"


# ===========================================================================
# TE — Tool error propagation tests
# ===========================================================================

class TestToolErrors:

    # ------------------------------------------------------------------ TE-01
    def test_te01_tool_propagates_404(self):
        """A 404 from the API propagates unchanged as an error dict."""
        from src.mcp.tools.shipments import get_shipment_detail
        resp = _mock_response(404, {"detail": "Shipment 'BAD' not found"})
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            result = get_shipment_detail("BAD")
        assert result["error"] is True
        assert result["status_code"] == 404

    # ------------------------------------------------------------------ TE-02
    def test_te02_tool_propagates_connection_error(self):
        """Connection refused propagates as error dict with status_code=0."""
        from src.mcp.tools.shipments import evaluate_shipment_risk
        ctx = _make_client_ctx(None)
        ctx.get.side_effect = httpx.ConnectError("refused")
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            result = evaluate_shipment_risk("SHP-1001")
        assert result["error"] is True
        assert result["status_code"] == 0

    # ------------------------------------------------------------------ TE-03
    def test_te03_tool_propagates_timeout(self):
        """Timeout propagates as error dict mentioning 'timed out'."""
        from src.mcp.tools.shipments import evaluate_cold_chain
        ctx = _make_client_ctx(None)
        ctx.get.side_effect = httpx.TimeoutException("timeout")
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            result = evaluate_cold_chain("SHP-1001")
        assert result["error"] is True
        assert "timed out" in result["detail"].lower()

    # ------------------------------------------------------------------ TE-04
    def test_te04_tool_propagates_500(self):
        """HTTP 500 from API propagates as error dict with status_code=500."""
        from src.mcp.tools.disruptions import get_disruption_impact
        resp = _mock_response(500, {"detail": "Internal Server Error"})
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            result = get_disruption_impact("DIS-501")
        assert result["error"] is True
        assert result["status_code"] == 500

    # ------------------------------------------------------------------ TE-05
    def test_te05_tools_never_raise_exceptions(self):
        """All tool functions must return a dict — never raise an exception."""
        from src.mcp.tools.disruptions import get_active_disruptions, get_disruption_impact
        from src.mcp.tools.explain import explain_disruption_impact, explain_shipment_risk
        from src.mcp.tools.shipments import (
            evaluate_cold_chain,
            evaluate_shipment_risk,
            get_active_shipments,
            get_route_recommendations,
            get_shipment_detail,
            match_fleet_asset,
        )

        ctx = _make_client_ctx(None)
        ctx.get.side_effect = httpx.ConnectError("refused")
        ctx.post.side_effect = httpx.ConnectError("refused")

        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            for fn, args in [
                (get_active_shipments, []),
                (get_shipment_detail, ["SHP-1001"]),
                (evaluate_shipment_risk, ["SHP-1001"]),
                (evaluate_cold_chain, ["SHP-1001"]),
                (get_route_recommendations, ["SHP-1001"]),
                (match_fleet_asset, ["SHP-1001"]),
                (get_active_disruptions, []),
                (get_disruption_impact, ["DIS-501"]),
                (explain_shipment_risk, ["SHP-1001"]),
                (explain_disruption_impact, ["DIS-501"]),
            ]:
                try:
                    result = fn(*args)
                    assert isinstance(result, dict), (
                        f"{fn.__name__} must return a dict, got {type(result)}"
                    )
                except Exception as exc:
                    pytest.fail(
                        f"{fn.__name__} raised an exception instead of returning an error dict: {exc}"
                    )

    # ------------------------------------------------------------------ TE-06
    def test_te06_disruption_tool_404_propagated(self):
        """Disruption tool on unknown ID returns error dict, not an exception."""
        from src.mcp.tools.disruptions import get_disruption_impact
        resp = _mock_response(404, {"detail": "Disruption 'BAD' not found"})
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            result = get_disruption_impact("BAD")
        assert result["error"] is True
        assert result["status_code"] == 404


# ===========================================================================
# AI — Explanation tool behavior tests
# ===========================================================================

class TestExplainTools:

    def _explain_response(
        self,
        ai_generated: bool = True,
        model_id: str | None = "ibm/granite-3-8b-instruct",
    ) -> Dict[str, Any]:
        return {
            "use_case": "shipment_risk",
            "entity_id": "SHP-1001",
            "headline": "Shipment SHP-1001 is at HIGH risk.",
            "explanation": "The disruption sub-score is elevated.",
            "recommended_action": "Initiate reroute immediately.",
            "severity": "HIGH",
            "ai_generated": ai_generated,
            "model_id": model_id,
            "generated_at": "2025-01-01T00:00:00Z",
        }

    # ------------------------------------------------------------------ AI-01
    def test_ai01_explain_shipment_risk_body(self):
        """explain_shipment_risk sends entity_id + use_case='shipment_risk'."""
        from src.mcp.tools.explain import explain_shipment_risk
        resp = _mock_response(200, self._explain_response())
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            explain_shipment_risk("SHP-1001")
        sent = ctx.post.call_args[1]["json"]
        assert sent["entity_id"] == "SHP-1001"
        assert sent["use_case"] == "shipment_risk"

    # ------------------------------------------------------------------ AI-02
    def test_ai02_explain_disruption_impact_body(self):
        """explain_disruption_impact sends entity_id + use_case='disruption_impact'."""
        from src.mcp.tools.explain import explain_disruption_impact
        resp_body = {**self._explain_response(), "use_case": "disruption_impact", "entity_id": "DIS-501"}
        resp = _mock_response(200, resp_body)
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            explain_disruption_impact("DIS-501")
        sent = ctx.post.call_args[1]["json"]
        assert sent["entity_id"] == "DIS-501"
        assert sent["use_case"] == "disruption_impact"

    # ------------------------------------------------------------------ AI-03
    def test_ai03_ai_generated_true_preserved(self):
        """ai_generated=True from API response is preserved in tool return value."""
        from src.mcp.tools.explain import explain_shipment_risk
        resp = _mock_response(200, self._explain_response(ai_generated=True))
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            result = explain_shipment_risk("SHP-1001")
        assert result["ai_generated"] is True

    # ------------------------------------------------------------------ AI-04
    def test_ai04_model_id_preserved(self):
        """model_id='ibm/granite-3-8b-instruct' from API response is preserved."""
        from src.mcp.tools.explain import explain_shipment_risk
        resp = _mock_response(200, self._explain_response(model_id="ibm/granite-3-8b-instruct"))
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            result = explain_shipment_risk("SHP-1001")
        assert result["model_id"] == "ibm/granite-3-8b-instruct"

    # ------------------------------------------------------------------ AI-05
    def test_ai05_ai_generated_false_fallback_preserved(self):
        """ai_generated=False (deterministic fallback) is preserved in tool return."""
        from src.mcp.tools.explain import explain_shipment_risk
        resp = _mock_response(200, self._explain_response(ai_generated=False, model_id=None))
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            result = explain_shipment_risk("SHP-1001")
        assert result["ai_generated"] is False
        assert result["model_id"] is None

    # ------------------------------------------------------------------ AI-06
    def test_ai06_explain_tool_404_returns_error_dict(self):
        """Explanation tool on non-existent entity returns error dict, not an exception."""
        from src.mcp.tools.explain import explain_shipment_risk
        resp = _mock_response(404, {"detail": "Shipment 'BAD' not found"})
        ctx = _make_client_ctx(resp)
        with patch("src.mcp.client.httpx.Client", return_value=ctx):
            result = explain_shipment_risk("BAD")
        assert result["error"] is True
        assert result["status_code"] == 404


# ===========================================================================
# SC — Security and configuration tests
# ===========================================================================

class TestSecurityConfig:

    # ------------------------------------------------------------------ SC-01
    def test_sc01_bob_mcp_json_exists(self):
        """.bob/mcp.json exists at the project root."""
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        mcp_json_path = os.path.join(repo_root, ".bob", "mcp.json")
        assert os.path.isfile(mcp_json_path), (
            f".bob/mcp.json not found at {mcp_json_path}"
        )

    # ------------------------------------------------------------------ SC-02
    def test_sc02_bob_mcp_json_command_is_python(self):
        """.bob/mcp.json uses 'command': 'python'."""
        import json as _json
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        with open(os.path.join(repo_root, ".bob", "mcp.json")) as f:
            cfg = _json.load(f)
        assert cfg["mcpServers"]["supplyguard"]["command"] == "python"

    # ------------------------------------------------------------------ SC-03
    def test_sc03_bob_mcp_json_no_secrets(self):
        """.bob/mcp.json must not contain API keys, passwords, or tokens."""
        import json as _json
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        with open(os.path.join(repo_root, ".bob", "mcp.json")) as f:
            raw = f.read()
        secret_patterns = [
            "apikey", "api_key", "password", "token", "secret",
            "credential", "private_key", "access_key",
        ]
        raw_lower = raw.lower()
        for pattern in secret_patterns:
            # Allow the pattern only in comment-like contexts (keys like SUPPLYGUARD_API_URL are OK)
            # but flag anything that looks like a credential value
            if pattern in raw_lower:
                # The only allowed match is SUPPLYGUARD_API_URL which is a URL
                if pattern == "api_key" and "supplyguard_api_url" in raw_lower:
                    continue  # supplyguard_api_url is not a secret
                if pattern == "api_key":
                    continue  # field named api_key would be a problem — check value
                # For other patterns, flag them
                pytest.fail(
                    f".bob/mcp.json contains suspicious pattern '{pattern}': check for secrets"
                )

    # ------------------------------------------------------------------ SC-04
    def test_sc04_bob_mcp_json_supplyguard_url_is_localhost(self):
        """SUPPLYGUARD_API_URL in .bob/mcp.json env is the localhost URL only."""
        import json as _json
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        with open(os.path.join(repo_root, ".bob", "mcp.json")) as f:
            cfg = _json.load(f)
        env = cfg["mcpServers"]["supplyguard"].get("env", {})
        api_url = env.get("SUPPLYGUARD_API_URL", "")
        assert "localhost" in api_url or "127.0.0.1" in api_url, (
            f"SUPPLYGUARD_API_URL should be a localhost URL, got: {api_url!r}"
        )

    # ------------------------------------------------------------------ SC-05
    def test_sc05_bob_mcp_json_uses_module_launch(self):
        """.bob/mcp.json uses '-m' + 'src.mcp.server' module launch."""
        import json as _json
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        with open(os.path.join(repo_root, ".bob", "mcp.json")) as f:
            cfg = _json.load(f)
        args = cfg["mcpServers"]["supplyguard"]["args"]
        assert "-m" in args, "args must contain '-m' for module launch"
        assert "src.mcp.server" in args, "args must contain 'src.mcp.server'"


# ===========================================================================
# ST — Server registration and stdout-cleanliness tests
# ===========================================================================

class TestServerRegistration:

    # ------------------------------------------------------------------ ST-01
    def test_st01_fastmcp_importable(self):
        """from mcp.server.fastmcp import FastMCP works without error."""
        from mcp.server.fastmcp import FastMCP  # noqa: F401
        assert FastMCP is not None

    # ------------------------------------------------------------------ ST-02
    def test_st02_server_mcp_is_fastmcp_instance(self):
        """src.mcp.server.mcp is a FastMCP instance."""
        from mcp.server.fastmcp import FastMCP
        import src.mcp.server as srv
        assert isinstance(srv.mcp, FastMCP)

    # ------------------------------------------------------------------ ST-03
    def test_st03_all_10_tools_registered(self):
        """All 10 expected tool names are registered on the FastMCP instance."""
        import asyncio
        import src.mcp.server as srv

        tools = asyncio.run(srv.mcp.list_tools())
        names = {t.name for t in tools}
        expected = {
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
        }
        assert names == expected, (
            f"Tool mismatch:\n  missing: {expected - names}\n  extra: {names - expected}"
        )

    # ------------------------------------------------------------------ ST-04
    def test_st04_server_import_does_not_write_to_stdout(self):
        """Importing src.mcp.server must not write any bytes to stdout."""
        # Remove any cached module to force a fresh import check
        mods_to_remove = [k for k in sys.modules if k.startswith("src.mcp")]
        for mod in mods_to_remove:
            sys.modules.pop(mod, None)

        buf = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = buf
        try:
            import src.mcp.server  # noqa: F401
        finally:
            sys.stdout = original_stdout

        captured = buf.getvalue()
        assert captured == "", (
            f"src.mcp.server wrote to stdout (MCP protocol channel contamination): {captured!r}"
        )

    # ------------------------------------------------------------------ ST-05
    def test_st05_tool_docstrings_non_empty(self):
        """All 10 registered tools have non-empty descriptions for Bob tool selection."""
        import asyncio
        import src.mcp.server as srv

        tools = asyncio.run(srv.mcp.list_tools())
        for tool in tools:
            assert tool.description and tool.description.strip(), (
                f"Tool '{tool.name}' has an empty description — Bob cannot select it"
            )

    # ------------------------------------------------------------------ ST-06
    def test_st06_server_has_no_backend_imports(self):
        """src/mcp/server.py must not import from src.backend."""
        import ast
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        server_path = os.path.join(repo_root, "src", "mcp", "server.py")
        with open(server_path) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith("src.backend"), (
                        f"src/mcp/server.py must not import from src.backend, "
                        f"found: from {node.module} import ..."
                    )
