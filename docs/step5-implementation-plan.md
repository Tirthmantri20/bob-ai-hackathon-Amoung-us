# Step 5 Implementation Plan — MCP + IBM Bob Integration
# SupplyGuard AI

**Scope:**
`src/mcp/server.py`, `src/mcp/tools/__init__.py`, `src/mcp/tools/shipments.py`,
`src/mcp/tools/disruptions.py`, `src/mcp/tools/explain.py`, `src/mcp/client.py`,
`src/tests/test_step5_mcp.py`, `.bob/mcp.json`,
`requirements.txt` (2 new dependencies), `src/.env.example` (MCP section update)

**Source of truth:**
`docs/architecture.md`, `docs/solution-overview.md`, Step 5 Discovery session,
Step 5 API/SDK Verification session, Implementation Final Decisions

**Out of scope:**
Step 2 engine files, Step 3 router files, Step 4 AI files, `src/backend/main.py`,
frontend, auth, persistent storage, OR-Tools, PostGIS, background jobs,
streaming responses, docs/step5-implementation-plan.md (this file)

**Immutable constraints:**
- Step 2 engines are read-only; no imports of them in MCP code
- Step 3 and Step 4 router/AI files are read-only
- MCP server never imports ORM models, `get_db`, or SQLAlchemy sessions
- All 192 existing Step 1–4 tests must remain passing
- No secrets in `.bob/mcp.json` or any committed file
- stdout must remain clean for the MCP stdio protocol channel (all logs to stderr)

---

## Architecture Overview

```
IBM Bob
  │
  │  JSON-RPC 2.0 over stdio (stdin/stdout)
  │  Bob spawns: python -m src.mcp.server
  ▼
src/mcp/server.py        (FastMCP instance, 10 registered tools, mcp.run())
  │
  │  HTTP GET/POST via httpx.Client (src/mcp/client.py)
  │  base URL: SUPPLYGUARD_API_URL env var (default: http://localhost:8000)
  ▼
FastAPI Backend (src/backend/main.py, port 8000)
  │
  ├─ GET /api/shipments/
  ├─ GET /api/shipments/{id}
  ├─ GET /api/shipments/{id}/risk
  ├─ GET /api/shipments/{id}/cold-chain
  ├─ GET /api/shipments/{id}/routes
  ├─ GET /api/shipments/{id}/fleet-match
  ├─ GET /api/disruptions/
  ├─ GET /api/disruptions/{id}/affected-shipments
  ├─ POST /api/explain/shipment-risk         ← Granite load-bearing chain
  └─ POST /api/explain/disruption-impact     ← Granite load-bearing chain
```

### Load-bearing Granite demonstration chain (tools 9–10)

```
IBM Bob
  → explain_shipment_risk(shipment_id="SHP-1002")
  → POST /api/explain/shipment-risk  {"entity_id": "SHP-1002", "use_case": "shipment_risk"}
  → FastAPI explain.py router
  → RiskEngine + ColdChainEngine + RouteOptimizer + FleetMatcher (deterministic)
  → evidence_builder.build_shipment_risk_evidence(…)
  → WatsonxService.generate_explanation("shipment_risk", evidence)
  → ModelInference.generate_text(prompt)   ← IBM Granite via watsonx.ai
  → AIExplanationResponse(ai_generated=True, model_id="ibm/granite-3-8b-instruct", …)
  → MCP tool returns JSON verbatim (ai_generated + model_id visible to Bob)
  → IBM Bob delivers operational narrative to dispatcher
```

---

## Dependency Direction (no cycles)

```
requirements.txt
  └─ mcp>=1.28,<2            (FastMCP, stdio transport)
  └─ httpx>=0.25.0           (sync HTTP client)

src/mcp/client.py            (shared httpx helper, reads SUPPLYGUARD_API_URL)
  └─ no src/backend imports

src/mcp/tools/shipments.py   (tools 1–6) → imports client only
src/mcp/tools/disruptions.py (tools 7–8) → imports client only
src/mcp/tools/explain.py     (tools 9–10) → imports client only

src/mcp/tools/__init__.py    (re-exports all 10 tool functions)

src/mcp/server.py            (FastMCP instance, registers 10 tools, mcp.run())
  └─ imports from src/mcp/tools/__init__ and mcp.server.fastmcp only
```

---

## Phase 0 — Pre-Implementation Verification

### Intent
Verify `mcp>=1.28,<2` installs cleanly and `FastMCP` is importable before writing application code.

### Status
[x] done

### Verified facts
- `mcp` version installed: **1.30.0** (satisfies `>=1.28,<2`)
- `httpx` version installed: **0.28.1** (satisfies `>=0.25.0`)
- `from mcp.server.fastmcp import FastMCP` → imports cleanly
- `FastMCP` class confirmed at `mcp.server.fastmcp.server.FastMCP`
- `mcp.tool()(fn)` registration confirmed working for externally-defined functions
- 192 existing tests: all pass before any Step 5 code

---

## Phase 1 — Dependency and Configuration Updates

### Intent
Add two new packages to `requirements.txt` and correct the stale SSE transport
placeholder in `src/.env.example`.

### Status
[x] done

### Changes made

**`requirements.txt`** — two new blocks appended after `ibm-watsonx-ai`:
```
# --- MCP server (Step 5 IBM Bob integration layer) ---
mcp>=1.28,<2

# --- HTTP client (MCP tools call FastAPI REST endpoints) ---
httpx>=0.25.0
```

**`src/.env.example`** — MCP section updated:
- `MCP_TRANSPORT=sse` → `MCP_TRANSPORT=stdio`
- Added clarification comments that HOST/PORT are unused for stdio
- Added `SUPPLYGUARD_API_URL=http://localhost:8000` (not a secret)

---

## Phase 2 — Shared HTTP Client (`src/mcp/client.py`)

### Intent
Single point of truth for HTTP communication from MCP to FastAPI.
All four failure modes handled: success, 4xx/5xx, connection refused, timeout.
Zero imports from `src/backend/`.

### Status
[x] done

### API surface

| Function | Description |
|---|---|
| `get_api_url() -> str` | Reads `SUPPLYGUARD_API_URL` env var, defaults to `http://localhost:8000`, strips trailing slash |
| `api_get(path: str) -> dict` | HTTP GET; returns JSON body on 2xx; returns error dict on any failure |
| `api_post(path, body) -> dict` | HTTP POST with JSON body; same error handling as api_get |

### Error dict contract

```python
{"error": True, "status_code": int, "detail": str}
# status_code=0 means transport/connection failure
```

**Note:** These are application-level error dicts. They are returned by tool
functions as plain Python dicts. They do not automatically set the MCP
protocol-level `isError` flag. This is correct — the tool returns a structured
error payload that Bob can read and present to the user.

### Timeout
`httpx.Timeout(10.0)` — all four timeout dimensions (connect/read/write/pool).

### Logging
All logging via `logging.basicConfig(stream=sys.stderr)`.
Never `print()`. Never `sys.stdout`.

---

## Phase 3 — Shipment Tools (`src/mcp/tools/shipments.py`)

### Intent
Implement tools 1–6 as one-line HTTP delegations. Tool docstrings are
optimized for Bob tool-selection (contain parameter names, return field names,
and operational context).

### Status
[x] done

### Tool inventory

| # | Function | FastAPI endpoint | Args |
|---|---|---|---|
| 1 | `get_active_shipments()` | `GET /api/shipments/` | none |
| 2 | `get_shipment_detail(shipment_id)` | `GET /api/shipments/{id}` | `shipment_id: str` |
| 3 | `evaluate_shipment_risk(shipment_id)` | `GET /api/shipments/{id}/risk` | `shipment_id: str` |
| 4 | `evaluate_cold_chain(shipment_id)` | `GET /api/shipments/{id}/cold-chain` | `shipment_id: str` |
| 5 | `get_route_recommendations(shipment_id)` | `GET /api/shipments/{id}/routes` | `shipment_id: str` |
| 6 | `match_fleet_asset(shipment_id)` | `GET /api/shipments/{id}/fleet-match` | `shipment_id: str` |

---

## Phase 4 — Disruption Tools (`src/mcp/tools/disruptions.py`)

### Intent
Implement tools 7–8.

### Status
[x] done

| # | Function | FastAPI endpoint | Args |
|---|---|---|---|
| 7 | `get_active_disruptions()` | `GET /api/disruptions/` | none |
| 8 | `get_disruption_impact(disruption_id)` | `GET /api/disruptions/{id}/affected-shipments` | `disruption_id: str` |

---

## Phase 5 — AI Explanation Tools (`src/mcp/tools/explain.py`)

### Intent
Implement tools 9–10. These are the load-bearing IBM Granite proof tools.
They call `POST /api/explain/*` and return the `AIExplanationResponse` verbatim
to Bob, preserving `ai_generated`, `model_id`, `headline`, `explanation`,
`recommended_action`, and `severity`.

### Status
[x] done

| # | Function | FastAPI endpoint | Request body |
|---|---|---|---|
| 9 | `explain_shipment_risk(shipment_id)` | `POST /api/explain/shipment-risk` | `{"entity_id": id, "use_case": "shipment_risk"}` |
| 10 | `explain_disruption_impact(disruption_id)` | `POST /api/explain/disruption-impact` | `{"entity_id": id, "use_case": "disruption_impact"}` |

**Key design principle:** The MCP tool adds zero interpretation. It calls
`api_post()` and returns the result verbatim. The deterministic engines,
evidence builder, and Granite inference all live inside FastAPI (Step 4).
If watsonx credentials are absent, the Step 4 fallback returns
`ai_generated=False` with a deterministic narrative — the MCP tool
transparently passes this back to Bob.

---

## Phase 6 — Tool Package Init (`src/mcp/tools/__init__.py`)

### Intent
Populate `__init__.py` with import re-exports so `server.py` can import
all 10 tools from a single location.

### Status
[x] done

---

## Phase 7 — MCP Server Entry Point (`src/mcp/server.py`)

### Intent
Replace the non-functional stub with a real FastMCP server.
- `FastMCP("supplyguard", instructions=…)` — named server with Bob-visible instructions
- `mcp.tool()(fn)` — programmatic registration of all 10 imported tool functions
- `mcp.run()` — starts stdio event loop (no arguments = stdio transport)
- All logging to `sys.stderr`

### Status
[x] done

### Launch command
```bash
python -m src.mcp.server
```

---

## Phase 8 — IBM Bob Project Configuration (`.bob/mcp.json`)

### Intent
Create the project-level Bob MCP config so Bob auto-discovers and spawns
the SupplyGuard server.

### Status
[x] done

### File contents
```json
{
  "mcpServers": {
    "supplyguard": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "cwd": ".",
      "env": {
        "SUPPLYGUARD_API_URL": "http://localhost:8000"
      },
      "alwaysAllow": [],
      "disabled": false
    }
  }
}
```

### `cwd: "."` note
`"."` resolves to the directory from which Bob was launched. Since Bob opens
the project from the repository root, this should work correctly. If it does
not, replace `"."` with the absolute path to the repository root and update
the setup guide accordingly.

### Security
Only `SUPPLYGUARD_API_URL=http://localhost:8000` is in the `env` block.
This is a localhost URL, not a secret. No API keys, passwords, or tokens.
Safe to commit to version control.

---

## Phase 9 — Tests (`src/tests/test_step5_mcp.py`)

### Intent
Full test suite for the MCP layer. Zero live network calls.
All httpx interactions mocked via `unittest.mock.patch`.

### Status
[x] done

### Test groups and counts

| Group | Count | What is tested |
|---|---|---|
| MC — `client.py` HTTP helper | 12 | get_api_url, api_get, api_post: success / 404 / 500 / connect error / timeout |
| TS — Tool URL construction | 10 | All 10 tools call the correct FastAPI endpoint path |
| TE — Error propagation | 6 | 404, connection refused, timeout, 500, no-exception guarantee |
| AI — Explanation tools | 6 | Request body shape, ai_generated/model_id preservation, 404 handling |
| SC — Security/config | 5 | .bob/mcp.json existence, command, no secrets, localhost URL, module launch args |
| ST — Server registration | 6 | FastMCP import, instance type, 10 tools, stdout cleanliness, no backend imports |
| **Total** | **45** | |

### Running the tests
```bash
pytest src/tests/test_step5_mcp.py -v        # Step 5 only: 45 tests
pytest src/tests/ -v                          # Full suite: 237 tests
```

---

## Phase 10 — Documentation

### Status
[x] done (this file)

---

## Phase 11 — Validation Results

### Automated tests
```
pytest src/tests/ -v
237 passed, 0 failed, 2 warnings (pre-existing deprecation warnings, not new)
```

**Breakdown:**
- Step 1: 30 passing (unchanged)
- Step 2 risk engine: 10 passing (unchanged)
- Step 2 cold chain: 11 passing (unchanged)
- Step 2 fleet matcher: 13 passing (unchanged)
- Step 2 route optimizer: 13 passing (unchanged)
- Step 3 API: 67 passing (unchanged)
- Step 4 AI: 49 passing (unchanged)
- **Step 5 MCP: 45 passing (new)**

### Smoke test
```bash
python -m src.mcp.server
# stderr: "SupplyGuard MCP server starting on stdio …"
# stdout: empty (MCP protocol channel clean)
```

### Tool registration
All 10 tools confirmed via `asyncio.run(mcp.list_tools())`:
`get_active_shipments`, `get_shipment_detail`, `evaluate_shipment_risk`,
`evaluate_cold_chain`, `get_route_recommendations`, `match_fleet_asset`,
`get_active_disruptions`, `get_disruption_impact`, `explain_shipment_risk`,
`explain_disruption_impact`

### stdout cleanliness
Confirmed: `src.mcp.server` module import writes zero bytes to stdout.

---

## Bob Live Demo Procedure

### Prerequisites
1. FastAPI backend running in Terminal 1:
   ```bash
   uvicorn src.backend.main:app --host 0.0.0.0 --port 8000
   ```
2. Repository open in Bob IDE from the project root
3. `.bob/mcp.json` present — Bob will auto-discover and connect

### Demo flow

**Step 1** — Confirm 10 tools in Bob's MCP panel
Look for "supplyguard" server showing as connected with all 10 tools listed.

**Step 2** — Discover shipments (tool 1)
> "Show me all active shipments"
→ `get_active_shipments()` → list of SHP-1001 through SHP-1004

**Step 3** — Assess risk (tool 3)
> "What is the risk score for shipment SHP-1002?"
→ `evaluate_shipment_risk("SHP-1002")` → total_score (0–100), severity, sub-scores

**Step 4** — Check disruption impact (tools 7+8)
> "Which shipments are impacted by disruption DIS-501?"
→ `get_active_disruptions()` + `get_disruption_impact("DIS-501")` → affected shipments

**Step 5** — Fleet rescue (tool 6)
> "What idle fleet asset can rescue SHP-1002?"
→ `match_fleet_asset("SHP-1002")` → ranked assets with recommended=true

**Step 6** — Granite load-bearing demo (tool 9)
> "Explain why SHP-1002 is at risk and what action I should take"
→ `explain_shipment_risk("SHP-1002")`
→ Chain: MCP → FastAPI → 4 engines → Granite → AIExplanationResponse
→ With live credentials: `ai_generated=true`, `model_id="ibm/granite-3-8b-instruct"`
→ Without credentials: `ai_generated=false`, deterministic fallback (still coherent)

**Step 7** — Disruption AI briefing (tool 10)
> "Brief me on the impact of DIS-501 and what I should do"
→ `explain_disruption_impact("DIS-501")` → full AIExplanationResponse

---

## Files Changed

| File | Change type | Summary |
|---|---|---|
| `requirements.txt` | Modified | +`mcp>=1.28,<2`, +`httpx>=0.25.0` |
| `src/.env.example` | Modified | `MCP_TRANSPORT=stdio`, +`SUPPLYGUARD_API_URL` |
| `src/mcp/server.py` | Full replacement | Non-functional stub → real FastMCP server |
| `src/mcp/tools/__init__.py` | Full replacement | Empty → re-exports all 10 tools |
| `src/mcp/client.py` | New | Shared httpx HTTP helper |
| `src/mcp/tools/shipments.py` | New | Tools 1–6 |
| `src/mcp/tools/disruptions.py` | New | Tools 7–8 |
| `src/mcp/tools/explain.py` | New | Tools 9–10 (Granite load-bearing) |
| `.bob/mcp.json` | New | IBM Bob project MCP config |
| `src/tests/test_step5_mcp.py` | New | 45 MCP tests |
| `docs/step5-implementation-plan.md` | New | This file |

## Files Explicitly Forbidden from Modification

All Step 2 engine files (`risk_engine/`, `cold_chain/`, `optimizer/`),
all Step 3 router files (`api/shipments.py`, `api/disruptions.py`, `api/fleet.py`,
`api/routes.py`, `api/risk.py`), all Step 4 AI files (`ai/watsonx_service.py`,
`ai/evidence_builder.py`, `ai/fallback.py`, `api/explain.py`,
`schemas/ai_response.py`), `src/backend/main.py`, all existing test files
(Steps 1–4), all docs except this plan, all frontend files.
