"""
WatsonxService — Step 4 AI Explanation Layer

Wraps the ibm-watsonx-ai SDK (v1.7.x) to generate natural-language
explanations from structured deterministic engine evidence.

Architecture constraints
------------------------
- This is the ONLY module in the project that imports ibm_watsonx_ai.
- The AI service never queries the database and never calls engine modules.
- Deterministic engines always run first; this service only annotates.
- Every code path returns a valid AIExplanationResponse (never None).
- HTTP 200 is always achievable — failures fall back to deterministic text.

SDK facts (verified against ibm-watsonx-ai==1.7.2)
---------------------------------------------------
  from ibm_watsonx_ai import Credentials
  from ibm_watsonx_ai.foundation_models import ModelInference
  from ibm_watsonx_ai.wml_client_error import WMLClientError

  ModelInference(
      model_id=str,
      project_id=str,
      credentials=Credentials,
      params=dict,   # plain dict with string keys
  )

  ModelInference.generate_text(prompt: str) -> str | list | dict
      Returns the generated text as a str in the common case.

  Credential detection: all four env vars must be non-empty.

Failure modes handled
---------------------
  1. Credentials absent/incomplete → immediate fallback, zero SDK calls
  2. SDK init failure (ImportError or WMLClientError) → fallback mode
  3. generate_text() raises any exception → fallback for that request
  4. generate_text() returns non-str value → fallback
  5. JSON parse fails (non-JSON output) → fallback
  6. JSON parses but missing required keys → fallback
  7. JSON parses but fields are empty strings → fallback
  8. Pydantic validation of parsed dict fails → fallback
  Regex extraction of partial content is never used (decision 12).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.backend.ai.fallback import build_fallback
from src.backend.schemas.ai_response import AIExplanationResponse

# ---------------------------------------------------------------------------
# Conditional SDK import — module-level so tests can patch these names
# directly at 'src.backend.ai.watsonx_service.ModelInference'.
# The try/except allows the service to be imported without the SDK installed.
# ---------------------------------------------------------------------------
try:
    from ibm_watsonx_ai import Credentials  # noqa: F401 — re-exported for patching
    from ibm_watsonx_ai.foundation_models import ModelInference  # noqa: F401
    _SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    Credentials = None  # type: ignore[assignment,misc]
    ModelInference = None  # type: ignore[assignment]
    _SDK_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required environment variable names
# ---------------------------------------------------------------------------
_ENV_APIKEY = "WATSONX_APIKEY"
_ENV_PROJECT_ID = "WATSONX_PROJECT_ID"
_ENV_URL = "WATSONX_URL"
_ENV_MODEL_ID = "WATSONX_MODEL_ID"

# ---------------------------------------------------------------------------
# System prompt — shared across all use cases
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are a logistics operations assistant for SupplyGuard AI.
You must only use the facts provided in the JSON evidence object below.
Do not invent shipment IDs, route names, temperatures, scores, regulations, \
carrier names, or asset IDs that are not present in the evidence.
Respond with a JSON object using exactly these three keys:
  "headline"           — one sentence, no more than 120 characters
  "explanation"        — 2 to 4 sentences grounded exclusively in the evidence values
  "recommended_action" — one concrete immediate action for the operations dispatcher
Do not add any text, markdown, or commentary outside the JSON object.\
"""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class WatsonxService:
    """
    Generates AI explanations from structured deterministic evidence.

    Lifecycle
    ---------
    Instantiated once during FastAPI lifespan startup and stored on
    app.state.watsonx_service.  Tests inject a mock via
    app.dependency_overrides[get_watsonx_service].

    Parameters
    ----------
    All configuration is read from environment variables at construction time.
    No arguments are required; this allows the service to be constructed with
    defaults in production and overridden in tests.
    """

    def __init__(self) -> None:
        api_key = os.getenv(_ENV_APIKEY, "").strip()
        project_id = os.getenv(_ENV_PROJECT_ID, "").strip()
        url = os.getenv(_ENV_URL, "").strip()
        model_id = os.getenv(_ENV_MODEL_ID, "").strip()

        self._model_id: Optional[str] = model_id if model_id else None
        self._model = None  # ModelInference | None

        # All four variables must be non-empty for live mode.
        if not (api_key and project_id and url and model_id):
            logger.info(
                "WatsonxService: fallback mode — one or more credentials "
                "not configured (%s, %s, %s, %s).",
                _ENV_APIKEY,
                _ENV_PROJECT_ID,
                _ENV_URL,
                _ENV_MODEL_ID,
            )
            return

        # Guard: SDK may not be installed (e.g. stripped environment).
        if not _SDK_AVAILABLE or Credentials is None or ModelInference is None:
            logger.warning(
                "WatsonxService: ibm-watsonx-ai package not installed — fallback mode."
            )
            return

        # Attempt SDK initialization; fall back gracefully on any error.
        # Credentials and ModelInference are module-level names (patchable in tests).
        try:
            credentials = Credentials(url=url, api_key=api_key)  # type: ignore[call-arg]
            self._model = ModelInference(
                model_id=model_id,
                project_id=project_id,
                credentials=credentials,
                params={
                    "decoding_method": "greedy",
                    "max_new_tokens": 400,
                    "temperature": 0,
                },
            )
            logger.info(
                "WatsonxService: live mode — model=%s project=%s",
                model_id,
                project_id,
            )
        except Exception as exc:  # pragma: no cover — only reachable without credentials
            logger.warning(
                "WatsonxService: SDK init failed (%s: %s) — fallback mode.",
                type(exc).__name__,
                exc,
            )
            self._model = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def is_live(self) -> bool:
        """True when a ModelInference instance is available."""
        return self._model is not None

    def generate_explanation(
        self,
        use_case: str,
        evidence: Dict[str, Any],
    ) -> AIExplanationResponse:
        """
        Generate an AI explanation for the given use case and evidence.

        Returns a valid AIExplanationResponse in all cases:
          - ai_generated=True  when Granite produced a valid response
          - ai_generated=False when any failure triggered the fallback

        Parameters
        ----------
        use_case : str
            One of: "shipment_risk", "cold_chain", "route_recommendation",
            "fleet_match", "disruption_impact".
        evidence : dict
            Structured evidence dict produced by evidence_builder.build_*().
            Must be JSON-serialisable.
        """
        if self._model is None:
            return build_fallback(use_case, evidence)

        entity_id = str(evidence.get("entity_id", "UNKNOWN"))
        severity = str(evidence.get("severity", "UNKNOWN"))

        # Build prompt
        prompt = self._build_prompt(use_case, evidence)

        # Call SDK
        try:
            raw = self._model.generate_text(prompt=prompt)
        except Exception as exc:
            logger.warning(
                "WatsonxService: SDK error for %s/%s — %s: %s",
                use_case,
                entity_id,
                type(exc).__name__,
                exc,
            )
            logger.info(
                "WatsonxService: returning deterministic fallback for %s/%s",
                use_case,
                entity_id,
            )
            return build_fallback(use_case, evidence)

        # Parse and validate response
        result = self._parse_response(raw, use_case, entity_id, severity)
        if result is not None:
            logger.debug(
                "WatsonxService: generated explanation for %s/%s",
                use_case,
                entity_id,
            )
            return result

        logger.info(
            "WatsonxService: returning deterministic fallback for %s/%s",
            use_case,
            entity_id,
        )
        return build_fallback(use_case, evidence)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, use_case: str, evidence: Dict[str, Any]) -> str:
        """Construct the full prompt string sent to ModelInference."""
        evidence_json = json.dumps(evidence, indent=2, default=str)
        user_message = (
            f"Use case: {use_case}\n"
            f"Evidence:\n{evidence_json}\n\n"
            f"Respond only with the JSON object described above."
        )
        return f"{_SYSTEM_PROMPT}\n\n{user_message}"

    def _parse_response(
        self,
        raw: Any,
        use_case: str,
        entity_id: str,
        severity: str,
    ) -> Optional[AIExplanationResponse]:
        """
        Parse and validate the raw model output.

        Returns an AIExplanationResponse on success, or None on any failure.
        No regex extraction is used — invalid output triggers None immediately.

        6-step strategy (per plan §5 item E):
          1. Coerce to str; strip whitespace
          2. Locate outermost { ... } by character scan
          3. json.loads() the candidate substring
          4. Verify all three required keys exist
          5. Verify all three required values are non-empty strings
          6. Construct AIExplanationResponse
        """
        # Step 1 — coerce to str
        if not isinstance(raw, str):
            logger.warning(
                "WatsonxService: model output not a string for %s "
                "(got %s) — fallback.",
                use_case,
                type(raw).__name__,
            )
            return None

        text = raw.strip()
        if not text:
            logger.warning(
                "WatsonxService: model returned empty string for %s — fallback.",
                use_case,
            )
            return None

        # Step 2 — locate outermost braces by character scan (no regex)
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
            logger.warning(
                "WatsonxService: model output not valid JSON for %s "
                "(no brace pair found) — fallback.",
                use_case,
            )
            return None

        candidate = text[first_brace: last_brace + 1]

        # Step 3 — parse JSON
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            logger.warning(
                "WatsonxService: model output not valid JSON for %s — fallback.",
                use_case,
            )
            return None

        if not isinstance(parsed, dict):
            logger.warning(
                "WatsonxService: parsed JSON is not a dict for %s — fallback.",
                use_case,
            )
            return None

        # Step 4 — required keys present
        required_keys = ("headline", "explanation", "recommended_action")
        for key in required_keys:
            if key not in parsed:
                logger.warning(
                    "WatsonxService: model response missing required key '%s' "
                    "for %s — fallback.",
                    key,
                    use_case,
                )
                return None

        # Step 5 — values are non-empty strings
        for key in required_keys:
            val = parsed[key]
            if not isinstance(val, str) or not val.strip():
                logger.warning(
                    "WatsonxService: model response key '%s' is empty or "
                    "non-string for %s — fallback.",
                    key,
                    use_case,
                )
                return None

        # Step 6 — construct response; severity ALWAYS comes from the engine
        try:
            return AIExplanationResponse(
                use_case=use_case,
                entity_id=entity_id,
                headline=parsed["headline"].strip(),
                explanation=parsed["explanation"].strip(),
                recommended_action=parsed["recommended_action"].strip(),
                severity=severity,          # engine-derived; never model-derived
                ai_generated=True,
                model_id=self._model_id,
                generated_at=datetime.now(tz=timezone.utc),
            )
        except Exception as exc:
            logger.warning(
                "WatsonxService: response construction failed for %s: %s "
                "— fallback.",
                use_case,
                exc,
            )
            return None
