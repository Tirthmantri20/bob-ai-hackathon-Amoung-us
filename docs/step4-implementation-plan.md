# Step 4 Implementation Plan — watsonx.ai / Granite AI Explanation Layer
# SupplyGuard AI

**Scope:**
`src/backend/ai/watsonx_service.py`, `src/backend/ai/evidence_builder.py`,
`src/backend/ai/fallback.py`, `src/backend/schemas/ai_response.py`,
`src/backend/api/explain.py`, `src/tests/test_step4_ai.py`,
`requirements.txt`, `src/.env.example`, `src/backend/main.py` (router registration only)

**Source of truth:**
`docs/architecture.md`, `docs/solution-overview.md`,
`docs/step2-assumptions.md`, `docs/step3-implementation-plan.md`,
Step 4 Discovery session

**Out of scope:**
MCP (Step 5), frontend, POST/PATCH/DELETE on existing resources,
persistent AI output storage, auth, OR-Tools, PostGIS,
background jobs, streaming responses

**Immutable constraints:**
- Step 2 engine files are read-only (no imports of `ibm_watsonx_ai`, `fastapi`, or `pydantic`)
- Step 3 router and test files are read-only
- AI service never queries the database directly
- Deterministic engines always run first; AI only annotates their output
- The API must return `200 OK` for every `POST /api/explain/*` regardless of AI availability

---

## Architecture Overview

```
POST /api/explain/{use_case}
        │
        ▼
explain.py router
  ├─ 1. DB lookup → ORM object (404 on missing ID)
  ├─ 2. Run relevant Step 2 engines (identical pattern to Step 3 routers)
  ├─ 3. evidence_builder.build_*_evidence(engine_result_dicts)
  ├─ 4. watsonx_service.generate_explanation(use_case, evidence)
  │      ├─ credentials present → SDK call → parse → AIExplanationResponse
  │      └─ credentials absent / any failure → fallback.build_*(evidence)
  └─ 5. Return AIExplanationResponse (ai_generated=True|False)
```

Dependency direction (no cycles):
```
Step 2 Engines (pure Python)
    └─► evidence_builder.py (pure Python)
          └─► watsonx_service.py (ibm_watsonx_ai + fallback)
                └─► fallback.py (pure Python)
                      └─► ai_response.py (Pydantic v2)
                            └─► explain.py (FastAPI router)
                                  └─► main.py (include_router only)
```

---

## Phase 1 — SDK Version Strategy and Dependency Pinning

### Intent
Establish the exact `ibm-watsonx-ai` package version, confirm the import
surface (`Credentials`, `ModelInference`), and add the package to
`requirements.txt`.  All subsequent phases depend on knowing the exact
class and method signatures.

### Expected Outcomes
- `requirements.txt` contains `ibm-watsonx-ai>=1.0.3,<2` (or the pinned
  range confirmed below)
- `src/.env.example` contains `WATSONX_MODEL_ID=ibm/granite-3-8b-instruct`
  as a non-secret default example
- All existing tests still pass after the new dependency is added
- No application code is written yet

### Todo List
1. Confirm the current stable release of `ibm-watsonx-ai` on PyPI (≥1.0.3
   as of early 2025; use `>=1.0.3,<2` to allow patch updates while
   guarding against breaking minor bumps).
2. Confirm the correct Python import path:
   ```python
   from ibm_watsonx_ai import Credentials
   from ibm_watsonx_ai.foundation_models import ModelInference
   ```
   Both classes exist in `ibm-watsonx-ai>=1.0.3`.  `ModelInference.generate_text()`
   is the synchronous text generation method used in this plan.
3. Add to `requirements.txt` after the `pandas` line:
   ```
   # --- IBM watsonx.ai SDK (Step 4 AI explanation layer) ---
   ibm-watsonx-ai>=1.0.3,<2
   ```
4. Add to `src/.env.example` after the existing `WATSONX_URL` line:
   ```
   # Granite model identifier — do not hard-code in application logic
   WATSONX_MODEL_ID=ibm/granite-3-8b-instruct
   ```
5. Verify that `pip install -r requirements.txt` completes without error
   in a clean virtualenv (the SDK bundles its own HTTP transport;
   no separate `requests` or `httpx` is needed for watsonx calls).
6. Run `pytest src/tests/ -v` — all existing tests must still pass (no
   new imports have been introduced into application code yet).

### Relevant Context
- `requirements.txt` current deps: `fastapi`, `uvicorn[standard]`,
  `pydantic>=2,<3`, `sqlalchemy>=2`, `python-dotenv`, `numpy`, `pandas`
- `src/.env.example` already has `WATSONX_APIKEY`, `WATSONX_PROJECT_ID`,
  `WATSONX_URL` — only `WATSONX_MODEL_ID` is missing
- `docs/architecture.md` line 61 confirms `ibm-watsonx-ai` as the SDK

### Status
[ ] pending

---

## Phase 2 — AI Response Schema

### Intent
Define the Pydantic v2 response model that `POST /api/explain/*` endpoints
return.  This schema is the contract shared by both the live AI path and
the deterministic fallback path.  It is defined before any service code
so all subsequent phases can import it without circular dependencies.

### Expected Outcomes
- `src/backend/schemas/ai_response.py` exists and is importable
- `AIExplanationResponse` validates both live and fallback payloads
- `AIExplainRequest` captures the `shipment_id` / `disruption_id` input
- No imports from `ibm_watsonx_ai`, `fastapi`, or any engine module

### Todo List
1. Create `src/backend/schemas/ai_response.py` with two models.

   **`AIExplainRequest`** (request body for all five endpoints):
   ```
   Fields:
     entity_id: str          # shipment_id or disruption_id
     use_case: str           # "shipment_risk" | "cold_chain" |
                             # "route_recommendation" | "fleet_match" |
                             # "disruption_impact"
   ```

   **`AIExplanationResponse`** (response from all five endpoints):
   ```
   Fields:
     use_case: str
     entity_id: str
     headline: str                   # ≤ 120 chars, one sentence
     explanation: str                # 2–4 sentences grounded in evidence
     recommended_action: str         # Immediate concrete dispatcher action
     severity: str                   # Echoed from engine: LOW/MEDIUM/HIGH/CRITICAL/OK/UNKNOWN
     ai_generated: bool              # True = live Granite; False = deterministic fallback
     model_id: Optional[str]         # "ibm/granite-3-8b-instruct" or None if fallback
     generated_at: datetime
   ```

2. Both models use `model_config = ConfigDict(from_attributes=False)`.
3. Add `AIExplainRequest` and `AIExplanationResponse` to
   `src/backend/schemas/__init__.py` exports.

### Relevant Context
- Follows the same Pydantic v2 pattern as `src/backend/schemas/engine_responses.py`
- `ai_generated` is the auditable proof flag: judges can see at a glance
  whether a response came from Granite or from the rule-based fallback
- `severity` is always engine-derived, never model-derived, preserving auditability

### Status
[ ] pending

---

## Phase 3 — Evidence Builder

### Intent
Provide one pure-Python function per use case that converts Step 2
engine result dataclass dicts (produced by `dataclasses.asdict()`) into
a compact, typed evidence dictionary suitable for inclusion in an AI
prompt.  This module has no external dependencies beyond the Python
standard library.

### Expected Outcomes
- `src/backend/ai/evidence_builder.py` exists
- Five public functions, one per use case, all accepting plain `dict`
  inputs (never ORM objects) and returning `dict`
- Scores use **engine output scale** (risk = 0–100; route/fleet = 0–1),
  never `Shipment.current_risk_score` (0–1 DB column)
- The module is importable with no side effects

### Todo List
1. Create `src/backend/ai/evidence_builder.py`.

2. Implement `build_shipment_risk_evidence(risk_dict, cold_chain_dict,
   route_dict, fleet_dict, shipment_orm_dict) -> dict`:
   ```
   Returns:
     use_case, entity_id, cargo_type, cargo_category, origin, destination,
     risk_score (0–100), severity,
     sub_scores: {r_disruption, r_weather, r_route, r_cold_chain, r_business},
     contributing_disruption_ids,
     cold_chain: {is_in_excursion, severity, cargo_temp_c, allowed_min_c,
                  allowed_max_c, deviation_c, compliance_standard},
     top_route: {route_name, eta_hours, disruption_factor, recommended} or None,
     top_fleet_asset: {asset_id, vehicle_type, cooling_capability,
                       proximity_km, total_score} or None
   ```

3. Implement `build_cold_chain_evidence(cold_chain_dict, shipment_orm_dict)
   -> dict`:
   ```
   Returns:
     use_case, entity_id, cargo_category, compliance_standard,
     is_in_excursion, is_destructive, severity,
     cargo_temp_c, allowed_min_c, allowed_max_c,
     max_allowable_excursion_temp_c, deviation_c
   ```

4. Implement `build_route_recommendation_evidence(route_dict,
   shipment_orm_dict) -> dict`:
   ```
   Returns:
     use_case, entity_id, cargo_type, origin, destination,
     no_route_found,
     scored_routes: list of {route_name, total_score, eta_hours,
                             disruption_factor, weather_factor,
                             cold_chain_factor, recommended, warnings}
   ```

5. Implement `build_fleet_match_evidence(fleet_dict, shipment_orm_dict)
   -> dict`:
   ```
   Returns:
     use_case, entity_id, cargo_category, origin, destination,
     no_asset_found,
     scored_assets: list of {asset_id, vehicle_type, cooling_capability,
                             total_score, proximity_km, cargo_compat_score,
                             refrigeration_score, recommended}
   ```

6. Implement `build_disruption_impact_evidence(disruption_impact_dict,
   disruption_orm_dict) -> dict`:
   ```
   Returns:
     use_case, entity_id, disruption_type, disruption_severity,
     proximity_radius_km, affected_count,
     affected_shipments: list of {shipment_id, shipment_status, distance_km}
   ```

7. Each function must use only keys present in its input dicts.  If an
   optional field is absent (e.g. `top_route` when `no_route_found=True`),
   set it to `None` rather than omitting the key.

### Relevant Context
- Input dicts come from `dataclasses.asdict()` applied to Step 2 engine
  result dataclasses — the same conversion used in Step 3 routers
- `ShipmentRiskResult` fields are in `src/backend/risk_engine/scorer.py`
- `ExcursionResult` fields are in `src/backend/cold_chain/engine.py`
- `RouteOptimizerResult` / `RouteScore` are in
  `src/backend/optimizer/route_optimizer.py`
- `FleetMatchResult` / `FleetMatchScore` are in
  `src/backend/optimizer/fleet_matcher.py`
- Risk score is 0–100 from the engine (MD-09); never use
  `Shipment.current_risk_score` (0–1 DB column)

### Status
[ ] pending

---

## Phase 4 — Deterministic Fallback Generator

### Intent
Provide a pure-Python module that generates a valid `AIExplanationResponse`
from a structured evidence dict without any external calls.  This module
activates whenever watsonx.ai is unavailable, credentials are missing,
or model output is invalid.  It must never return a `None` or raise an
exception.

### Expected Outcomes
- `src/backend/ai/fallback.py` exists
- Five public functions matching the five use cases
- Each function accepts a `dict` evidence and returns a fully populated
  `AIExplanationResponse` with `ai_generated=False`, `model_id=None`
- Narrative is deterministic (same input → same output), readable, and
  references only values present in the evidence dict

### Todo List
1. Create `src/backend/ai/fallback.py`.

2. Implement `build_shipment_risk_fallback(evidence: dict)
   -> AIExplanationResponse`:
   - `headline`: `"Shipment {entity_id} is at {severity} risk
     (score: {risk_score:.1f}/100)."`
   - `explanation`: Branch on `severity`:
     - `CRITICAL/HIGH`: note the highest sub-score dimension(s) and
       any cold-chain excursion, citing exact values from evidence
     - `MEDIUM`: note the most elevated sub-score
     - `LOW`: confirm all dimensions are within safe bounds
   - `recommended_action`: Lookup table by severity:
     - `CRITICAL` → "Immediately initiate emergency carrier transfer
       and pre-position cold-depot hold."
     - `HIGH` → "Evaluate reroute options; pre-position idle refrigerated
       fleet asset."
     - `MEDIUM` → "Monitor closely; validate carrier ETA at next
       telemetry ping."
     - `LOW` → "No immediate action required; continue scheduled transit."

3. Implement `build_cold_chain_fallback(evidence: dict)
   -> AIExplanationResponse`:
   - If `is_in_excursion=False`: headline confirms thermal integrity OK
   - If `is_in_excursion=True` and `is_destructive=False`: headline names
     severity, deviation value, compliance standard
   - If `is_destructive=True`: headline marks cargo as potentially
     irreversibly compromised
   - `recommended_action` based on severity: OK / WARNING / HIGH / CRITICAL

4. Implement `build_route_recommendation_fallback(evidence: dict)
   -> AIExplanationResponse`:
   - If `no_route_found=True`: explain no corridor match; recommend manual
     dispatch review
   - If routes present: name the recommended route, its ETA, and note the
     highest-risk avoided factor (disruption or weather)

5. Implement `build_fleet_match_fallback(evidence: dict)
   -> AIExplanationResponse`:
   - If `no_asset_found=True`: note no replacement available in current data
   - If assets present: name the top-ranked asset, its type, proximity,
     and cooling capability

6. Implement `build_disruption_impact_fallback(evidence: dict)
   -> AIExplanationResponse`:
   - State the number of affected shipments, disruption type and severity,
     proximity radius
   - If 0 affected: confirm no active shipments within radius
   - `recommended_action` scaled by `disruption_severity`

7. Add a dispatcher function `build_fallback(use_case: str, evidence: dict)
   -> AIExplanationResponse` that routes to the correct function by
   `use_case` string.  If `use_case` is unrecognised, return a safe generic
   response rather than raising.

### Relevant Context
- `AIExplanationResponse` is defined in Phase 2
- Evidence dict shapes are defined in Phase 3
- This module must import from `src.backend.schemas.ai_response` only;
  no engine imports, no `ibm_watsonx_ai` imports, no DB imports

### Status
[ ] pending

---

## Phase 5 — WatsonxService

### Intent
Implement the service class that wraps the `ibm-watsonx-ai` SDK.  It is
responsible for credential detection, `ModelInference` initialization,
prompt construction, SDK invocation, JSON response parsing, and activating
the fallback on every failure path.  This is the only module in the project
that imports `ibm_watsonx_ai`.

### Expected Outcomes
- `src/backend/ai/watsonx_service.py` exists
- `WatsonxService` is instantiable with or without valid credentials
- With credentials: makes exactly one `ModelInference.generate_text()` call
  per `generate_explanation()` invocation
- Without credentials: returns fallback immediately, zero SDK calls
- Any SDK exception → fallback, `200 OK`, logged at `WARNING`
- Invalid/malformed model JSON output → fallback (no regex extraction)
- Returns `AIExplanationResponse` in all cases

### Todo List

#### A — SDK Version Strategy (verified in Phase 1)

The `ibm-watsonx-ai` SDK version `>=1.0.3,<2` exposes:
```python
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
```
`ModelInference.generate_text(prompt: str) -> str` is the synchronous
single-call text generation method.  No streaming, no async variant needed.

#### B — Credential Detection

```python
_api_key    = os.getenv("WATSONX_APIKEY", "").strip()
_project_id = os.getenv("WATSONX_PROJECT_ID", "").strip()
_url        = os.getenv("WATSONX_URL", "").strip()
_model_id   = os.getenv("WATSONX_MODEL_ID", "").strip()

_WATSONX_AVAILABLE: bool = bool(_api_key and _project_id and _url and _model_id)
```

All four variables must be non-empty strings.  This check runs once at
module import time and is stored as a module-level constant.

#### C — ModelInference Initialization

```python
# Called once during WatsonxService.__init__ if _WATSONX_AVAILABLE is True
credentials = Credentials(url=_url, api_key=_api_key)
self._model = ModelInference(
    model_id=_model_id,
    project_id=_project_id,
    credentials=credentials,
    params={
        "max_new_tokens": 400,
        "temperature": 0,            # deterministic output
        "decoding_method": "greedy", # greedy = temperature 0 equivalent
    },
)
```

If `_WATSONX_AVAILABLE is False`, `self._model = None`.

The SDK does not expose a simple `timeout=` parameter on `ModelInference`;
do not invent one.  If timeout control is needed, it must be provided by
wrapping the call in `concurrent.futures.ThreadPoolExecutor` with a
`future.result(timeout=30)`.  This is a documented fallback pattern.
**Do not add timeout wrapper in Phase 5 unless confirmed available in the
chosen SDK version.** If absent, log a note and accept the SDK default.

#### D — Prompt Construction

Each use case has a dedicated private prompt-builder method.
Structure: system prompt block + evidence block + output instruction.

**System prompt (shared across all use cases):**
```
You are a logistics operations assistant for SupplyGuard AI.
You must only use the facts provided in the JSON evidence object below.
Do not invent shipment IDs, route names, temperatures, scores,
regulations, carrier names, or asset IDs not present in the evidence.
Respond with a JSON object using exactly these keys:
  "headline"           — one sentence, ≤ 120 characters
  "explanation"        — 2 to 4 sentences grounded in the evidence values
  "recommended_action" — one concrete immediate action for the dispatcher
Do not add any text outside the JSON object.
```

**User message (per use case):**
```
Use case: {use_case}
Evidence:
{json.dumps(evidence, indent=2, default=str)}

Respond only with the JSON object described above.
```

Full prompt = system_prompt + "\n\n" + user_message.

There is no separate "system" role parameter for `generate_text()` —
the full instruction is passed as a single prompt string.

#### E — JSON Parsing and Validation Strategy

```
raw_text = self._model.generate_text(prompt=full_prompt)

Step 1: raw_text.strip()
Step 2: Locate the first '{' and last '}' in the stripped string.
        If either is absent → fallback (no regex; no partial extraction).
Step 3: candidate = raw_text[first_brace : last_brace + 1]
Step 4: parsed = json.loads(candidate)
        → json.JSONDecodeError → fallback
Step 5: Validate that all three required keys exist and are non-empty strings:
        "headline", "explanation", "recommended_action"
        → KeyError or empty string → fallback
Step 6: Construct AIExplanationResponse from parsed dict + metadata fields
        (use_case, entity_id, severity, ai_generated=True, model_id, generated_at)
        → Any remaining exception → fallback
```

The brace-isolation in Step 2 is permissible because it is structural
extraction (find JSON boundaries), not regex-based partial content parsing.
Regex extraction of individual field values is explicitly forbidden.

#### F — `generate_explanation()` Method Signature

```python
def generate_explanation(
    self,
    use_case: str,
    evidence: dict,
) -> AIExplanationResponse:
```

Internal flow:
1. If `self._model is None`: call `fallback.build_fallback(use_case, evidence)`
2. Build prompt via private `_build_prompt(use_case, evidence)`
3. `raw = self._model.generate_text(prompt=prompt)` inside a `try/except Exception`
4. On any exception: log `WARNING` with exception message; call fallback
5. On success: parse with the 6-step strategy above
6. On parse failure: log `WARNING`; call fallback
7. Return `AIExplanationResponse` in all cases

#### G — Service Lifecycle / Dependency Injection

`WatsonxService` is a **process-level singleton** created once during the
FastAPI `lifespan` startup event and stored on `app.state.watsonx_service`.

Router access via a FastAPI dependency:
```python
def get_watsonx_service(request: Request) -> WatsonxService:
    return request.app.state.watsonx_service
```

Tests override this dependency via `app.dependency_overrides` — the
identical pattern used for `get_db` in Step 3:
```python
app.dependency_overrides[get_watsonx_service] = lambda: mock_service
```

One log message at startup: `"WatsonxService: live mode (Granite)"` or
`"WatsonxService: fallback mode (credentials not configured)"`.

#### H — Logging and Error Handling Rules

| Event | Level | Message |
|---|---|---|
| Credentials absent at startup | INFO | "WatsonxService: fallback mode — credentials not configured" |
| SDK call succeeds | DEBUG | "WatsonxService: generated explanation for {use_case}/{entity_id}" |
| SDK raises any exception | WARNING | "WatsonxService: SDK error for {use_case} — {exception_type}: {message}" |
| JSON parse fails | WARNING | "WatsonxService: model output not valid JSON for {use_case}" |
| Required key missing in parsed JSON | WARNING | "WatsonxService: model response missing required key '{key}' for {use_case}" |
| Fallback activated | INFO | "WatsonxService: returning deterministic fallback for {use_case}/{entity_id}" |

No `ERROR`-level logs for expected operational failures (credential issues,
model output problems).  `ERROR` is reserved for unexpected exceptions in
the service's own code paths.

### Relevant Context
- `src/backend/ai/__init__.py` is currently empty — import `WatsonxService`
  from `watsonx_service.py` only; do not re-export from `__init__.py`
- `fallback.build_fallback()` is the single entry point for all fallback paths
- `AIExplanationResponse` from `src/backend/schemas/ai_response.py`

### Status
[ ] pending

---

## Phase 6 — Explain API Router

### Intent
Create the five `POST /api/explain/*` endpoints.  Each endpoint follows
the same orchestration pattern: DB lookup → deterministic engines → evidence
builder → watsonx service → response.  No business logic lives in this file.

### Expected Outcomes
- `src/backend/api/explain.py` exists with five POST endpoints
- All five endpoints return `AIExplanationResponse`
- All five return `200 OK` regardless of AI availability
- Engine invocation is identical to Step 3 routers (same session pattern)
- `src/backend/main.py` registers the router at `/api/explain`

### Todo List

#### Endpoint Contracts

All five endpoints accept `POST` with body `AIExplainRequest` and return
`AIExplanationResponse`.  All are `200 OK` on success; `404` only if the
entity ID does not exist in the database.

**1. `POST /api/explain/shipment-risk`**
- Lookup: `Shipment` by `entity_id` (404 on missing)
- Engines: `RiskEngine`, `ColdChainEngine`, `RouteOptimizer`, `FleetMatcher`
- Builder: `build_shipment_risk_evidence(risk_dict, cold_chain_dict, route_dict, fleet_dict, shipment_orm_dict)`
- This endpoint is the *comprehensive* use case and uses all four engines

**2. `POST /api/explain/cold-chain`**
- Lookup: `Shipment` by `entity_id`
- Engines: `ColdChainEngine`
- Builder: `build_cold_chain_evidence(cold_chain_dict, shipment_orm_dict)`

**3. `POST /api/explain/route-recommendation`**
- Lookup: `Shipment` by `entity_id`
- Engines: `RouteOptimizer`
- Builder: `build_route_recommendation_evidence(route_dict, shipment_orm_dict)`

**4. `POST /api/explain/fleet-match`**
- Lookup: `Shipment` by `entity_id`
- Engines: `FleetMatcher`
- Builder: `build_fleet_match_evidence(fleet_dict, shipment_orm_dict)`

**5. `POST /api/explain/disruption-impact`**
- Lookup: `Disruption` by `entity_id` (404 on missing)
- Engine computation: inline proximity calculation (same logic as
  `disruptions.py` `get_affected_shipments`) **or** call the existing
  helper directly; prefer reuse over duplication
- Builder: `build_disruption_impact_evidence(impact_dict, disruption_orm_dict)`

#### Implementation Pattern (same for all five)

```python
@router.post("/shipment-risk", response_model=AIExplanationResponse)
def explain_shipment_risk(
    body: AIExplainRequest,
    db: Session = Depends(get_db),
    ai: WatsonxService = Depends(get_watsonx_service),
):
    shp = _get_shipment_or_404(body.entity_id, db)
    risk_result = RiskEngine(db).evaluate_shipment(shp)
    cold_result = ColdChainEngine(db).evaluate_shipment(shp)
    route_result = RouteOptimizer(db).optimize_for_shipment(shp)
    fleet_result = FleetMatcher(db).match_for_shipment(shp)
    evidence = build_shipment_risk_evidence(
        dataclasses.asdict(risk_result),
        dataclasses.asdict(cold_result),
        dataclasses.asdict(route_result),
        dataclasses.asdict(fleet_result),
        _shipment_to_dict(shp),       # thin helper, not a schema import
    )
    return ai.generate_explanation("shipment_risk", evidence)
```

`_shipment_to_dict(shp)` is a private helper in `explain.py` that extracts
only the fields needed by the evidence builder (`id`, `origin`,
`destination`, `cargo_type`, `cargo_category`) — it does not use Pydantic
and does not import from engine modules.

#### main.py Change

Add to `src/backend/main.py`:
```python
# In lifespan startup, after seed:
from src.backend.ai.watsonx_service import WatsonxService
app.state.watsonx_service = WatsonxService()

# Router import (at module level with other router imports):
from src.backend.api import explain as explain_router

# In router registration block:
app.include_router(
    explain_router.router,
    prefix="/api/explain",
    tags=["ai-explain"],
)
```

Also add `get_watsonx_service` function in `explain.py` (not in `main.py`)
to keep the dependency definition co-located with its router.

### Relevant Context
- Step 3 routers in `src/backend/api/` are the pattern to follow exactly
- `_get_shipment_or_404` helper exists in `shipments.py` — reproduce the
  same pattern locally in `explain.py` (do not import from another router)
- `dataclasses.asdict()` + engine invocation pattern is established in
  `src/backend/api/shipments.py`

### Status
[ ] pending

---

## Phase 7 — Step 4 Tests

### Intent
Verify the complete Step 4 layer — schema validation, evidence building,
fallback correctness, service behaviour in all failure modes, and API
endpoint responses — without any live watsonx.ai network calls.

### Expected Outcomes
- `src/tests/test_step4_ai.py` exists
- All Step 4 tests pass
- Zero network calls to watsonx.ai during any test run
- All existing Step 1–3 tests continue to pass
- Coverage spans: schema validation, all five evidence builders, all five
  fallbacks, service credential-absent mode, service malformed-output mode,
  service SDK-exception mode, all five API endpoints

### Todo List

#### P — Guaranteeing No Network Calls

Two-layer approach:
1. `unittest.mock.patch` on `ibm_watsonx_ai.foundation_models.ModelInference`
   at the `watsonx_service` import path, applied in every test that touches
   `WatsonxService` in live mode.
2. `app.dependency_overrides[get_watsonx_service]` to inject a
   `MockWatsonxService` for all API endpoint tests — the override bypasses
   the real service entirely.

`MockWatsonxService` is a plain class defined inside the test file:
```python
class MockWatsonxService:
    def generate_explanation(self, use_case, evidence):
        return AIExplanationResponse(
            use_case=use_case,
            entity_id=evidence.get("entity_id", "TEST"),
            headline="Mock headline",
            explanation="Mock explanation.",
            recommended_action="Mock action.",
            severity=evidence.get("severity", "LOW"),
            ai_generated=True,
            model_id="mock/model",
            generated_at=datetime.now(tz=timezone.utc),
        )
```

#### Test Groups

**SH — Schema tests** (no DB, no SDK)
- `SH-01`: `AIExplainRequest` accepts valid `entity_id` + `use_case`
- `SH-02`: `AIExplanationResponse` validates fully populated dict
- `SH-03`: `AIExplanationResponse` validates with `ai_generated=False`,
  `model_id=None`
- `SH-04`: Missing required field in `AIExplanationResponse` raises
  `ValidationError`

**EB — Evidence builder tests** (no DB, no SDK)
- `EB-01`: `build_shipment_risk_evidence` returns all required keys
- `EB-02`: Risk score field uses 0–100 scale
- `EB-03`: `top_route=None` when `no_route_found=True`
- `EB-04`: `top_fleet_asset=None` when `no_asset_found=True`
- `EB-05`: `build_cold_chain_evidence` returns correct excursion fields
- `EB-06`: `build_route_recommendation_evidence` with empty routes
- `EB-07`: `build_fleet_match_evidence` with empty assets
- `EB-08`: `build_disruption_impact_evidence` counts affected correctly

**FB — Fallback tests** (no DB, no SDK)
- `FB-01`: `build_fallback("shipment_risk", evidence)` returns valid
  `AIExplanationResponse` with `ai_generated=False`
- `FB-02`: Fallback for CRITICAL severity contains word "emergency" or
  "immediately" in `recommended_action`
- `FB-03`: Fallback for LOW severity contains "no immediate action"
- `FB-04`: `build_fallback("cold_chain", evidence)` with
  `is_in_excursion=True` references the deviation value
- `FB-05`: `build_fallback("route_recommendation", evidence)` with
  `no_route_found=True` notes no corridor match
- `FB-06`: `build_fallback("fleet_match", evidence)` with
  `no_asset_found=True` notes no replacement available
- `FB-07`: `build_fallback("disruption_impact", evidence)` states affected count
- `FB-08`: Unknown `use_case` string → safe generic response, no exception

**WS — WatsonxService unit tests** (mock SDK)
- `WS-01`: Service instantiates with empty env vars → `_model is None`
- `WS-02`: `generate_explanation()` with no credentials returns fallback
  with `ai_generated=False`
- `WS-03`: `generate_explanation()` with mocked `ModelInference` returning
  valid JSON → returns `ai_generated=True` response
- `WS-04`: Mock returns `"not valid json"` → returns fallback
  (`ai_generated=False`), no exception raised
- `WS-05`: Mock returns syntactically valid JSON missing `"headline"` key
  → returns fallback
- `WS-06`: Mock returns JSON with all keys as empty strings → returns fallback
- `WS-07`: Mock raises `Exception("SDK error")` → returns fallback,
  no exception propagated
- `WS-08`: `ai_generated=True` response echoes correct `use_case` and
  `entity_id`
- `WS-09`: `model_id` in response matches `WATSONX_MODEL_ID` env var when
  live path succeeds

**AI — API endpoint integration tests** (mock service, seeded DB)
- Use module-scoped `client` fixture identical to Step 3 pattern
- `app.dependency_overrides[get_watsonx_service] = lambda: MockWatsonxService()`
- `AI-01`: `POST /api/explain/shipment-risk {"entity_id": "SHP-1001", ...}`
  → 200, valid `AIExplanationResponse`
- `AI-02`: `POST /api/explain/shipment-risk {"entity_id": "SHP-NOTEXIST"}`
  → 404
- `AI-03`: `POST /api/explain/cold-chain {"entity_id": "SHP-1002"}` → 200,
  `severity` field is non-empty string
- `AI-04`: `POST /api/explain/route-recommendation {"entity_id": "SHP-1001"}`
  → 200, response is valid schema
- `AI-05`: `POST /api/explain/fleet-match {"entity_id": "SHP-1003"}` → 200
- `AI-06`: `POST /api/explain/disruption-impact {"entity_id": "DIS-501"}`
  → 200
- `AI-07`: `POST /api/explain/disruption-impact {"entity_id": "DIS-NOTEXIST"}`
  → 404
- `AI-08`: `ai_generated=True` in all mock-service responses (MockWatsonxService
  always sets it)
- `AI-09`: Response body conforms to `AIExplanationResponse` schema for
  all five endpoints (validate with `AIExplanationResponse.model_validate()`)
- `AI-10`: Calling `/api/explain/shipment-risk` does NOT persist anything
  to the DB (confirm `Shipment.current_risk_score` unchanged, same test
  pattern as Step 3 `test_r08_risk_does_not_persist`)

#### Fixture Isolation Pattern

Same `scope="module"` client fixture as `test_step3_api.py`:
```python
@pytest.fixture(scope="module")
def client():
    # in-memory SQLite engine, seed, override get_db + get_watsonx_service
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_watsonx_service] = lambda: MockWatsonxService()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

### Relevant Context
- Step 3 `test_step3_api.py` is the exact pattern to follow for client
  fixture and DB isolation
- `src/tests/test_step2_risk_engine.py` shows how to use `monkeypatch` or
  module-level patching when env vars need to be set for specific tests
- `app.dependency_overrides` is cleared in fixture teardown to avoid
  state leakage between test modules

### Status
[ ] pending

---

## Phase 8 — Demonstrating Granite is Load-Bearing (Item R)

### Intent
Establish concrete, observable evidence that watsonx.ai / Granite is not
merely mentioned but actively contributes to the operational output.

### Expected Outcomes
- The `/api/explain/shipment-risk` endpoint returns materially different
  text when `ai_generated=True` vs. the deterministic fallback
- The `ai_generated` boolean in every response is the auditable proof flag
- The setup guide documents how to observe the difference

### Implementation Notes (not separate files — incorporated into existing phases)

1. **`ai_generated` flag** (Phase 2): This boolean is present in every
   `AIExplanationResponse`.  Live Granite responses set it `True`; fallback
   responses set it `False`.  This is observable by judges without reading
   source code.

2. **`model_id` field** (Phase 2): When `ai_generated=True`, the exact
   Granite model identifier is echoed back (e.g.
   `"ibm/granite-3-8b-instruct"`).  When `ai_generated=False`, it is `None`.

3. **Prompt engineering constrains hallucination** (Phase 5): The system
   prompt forbids inventing values not in the evidence.  The model's output
   will reference specific numbers (e.g. deviation of `+0.8°C` against a
   `-18°C` max) that could only come from the structured evidence dict.
   The fallback uses fixed template phrases that are clearly different in
   style and cannot reference those specific numbers without the evidence.

4. **Narrative quality differentiation** (inherent): Granite synthesizes
   cross-dimensional context (e.g. "The elevated weather risk combined with
   the active cold-chain excursion creates compounding exposure…") in a way
   the rule-based fallback cannot.  The fallback addresses each dimension
   independently in fixed templates.

5. **Demo path** (note for setup guide update): To demonstrate live vs.
   fallback live:
   - With credentials set: `POST /api/explain/shipment-risk {"entity_id": "SHP-1002"}`
     → response shows `ai_generated: true`, Granite-composed narrative
   - With `WATSONX_APIKEY=""`: same call → `ai_generated: false`,
     template-based fallback

### Status
[ ] pending (notes only — incorporated into Phases 2, 5, and setup guide)

---

## Summary of Files Changed / Created

| File | Change Type | Phase |
|---|---|---|
| `requirements.txt` | MODIFY — add `ibm-watsonx-ai>=1.0.3,<2` | 1 |
| `src/.env.example` | MODIFY — add `WATSONX_MODEL_ID` | 1 |
| `src/backend/schemas/ai_response.py` | CREATE | 2 |
| `src/backend/schemas/__init__.py` | MODIFY — add new schema exports | 2 |
| `src/backend/ai/evidence_builder.py` | CREATE | 3 |
| `src/backend/ai/fallback.py` | CREATE | 4 |
| `src/backend/ai/watsonx_service.py` | CREATE | 5 |
| `src/backend/api/explain.py` | CREATE | 6 |
| `src/backend/main.py` | MODIFY — lifespan init + router registration | 6 |
| `src/tests/test_step4_ai.py` | CREATE | 7 |

**Files NOT changed:**
`src/backend/risk_engine/*.py`, `src/backend/cold_chain/*.py`,
`src/backend/optimizer/*.py`, `src/backend/api/shipments.py`,
`src/backend/api/disruptions.py`, `src/backend/api/fleet.py`,
`src/backend/api/routes.py`, `src/backend/api/risk.py`,
`src/backend/schemas/engine_responses.py`,
`src/tests/test_step1.py`, `src/tests/test_step2_*.py`,
`src/tests/test_step3_api.py`, `src/mcp/server.py`

---

## Validation Commands and Expected Coverage

```bash
# 1. Install updated dependencies
pip install -r requirements.txt

# 2. Full test suite — all steps
pytest src/tests/ -v

# Expected outcome:
#   test_step1.py           — all pass  (no change)
#   test_step2_*.py         — all pass  (no change)
#   test_step3_api.py       — all pass  (no change)
#   test_step4_ai.py        — all pass  (new)
#
# 0 failures, 0 errors, 0 new warnings

# 3. Step 4 only (faster iteration during development)
pytest src/tests/test_step4_ai.py -v

# 4. Confirm no live network calls during test run
#    (unset credentials and verify tests still pass)
WATSONX_APIKEY="" pytest src/tests/test_step4_ai.py -v

# 5. Manual live smoke test (requires real IBM credentials in src/.env)
uvicorn src.backend.main:app --reload
curl -X POST http://localhost:8000/api/explain/shipment-risk \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "SHP-1002", "use_case": "shipment_risk"}'
# Expect: 200 OK, ai_generated=true (with creds) or false (without)
```

**Test count targets:**
- Phase 7 adds ≥ 35 new tests (4 SH + 8 EB + 8 FB + 9 WS + 10 AI)
- Combined with existing tests, total suite ≥ 134 tests
- All tests must pass with `WATSONX_APIKEY` unset (CI environment)

---

## Phase Execution Order

```
Phase 1 — Dependency pinning     (no app code; verify install + existing tests)
Phase 2 — AI response schema     (Pydantic model; no logic)
Phase 3 — Evidence builder       (pure Python; no SDK; no DB)
Phase 4 — Fallback generator     (pure Python; no SDK; no DB)
Phase 5 — WatsonxService         (SDK wrapper; all failure paths)
Phase 6 — Explain API router     (FastAPI router + main.py registration)
Phase 7 — Step 4 tests           (mock-based; all code paths covered)
Phase 8 — Load-bearing evidence  (no code; notes incorporated into prior phases)
```

Each phase is independently reviewable and testable.  Phases 2–4 have no
external dependencies and can be verified with pure unit tests before the
SDK is exercised in Phase 5.
