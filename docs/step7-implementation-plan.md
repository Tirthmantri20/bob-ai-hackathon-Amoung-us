# Step 7 Implementation Plan — Final Validation, Documentation, Submission & Demo Readiness
# SupplyGuard AI

**Scope:**
`README.md`, `submission.yaml`, `docs/setup-guide.md`, `docs/architecture.md`,
`docs/solution-overview.md`, `demo/README.md`, `demo/live-demo-url.txt`,
`demo/demo-video-link.txt` (only when real URL exists),
`demo/screenshots/` (5 new PNG files), `presentation/slides.pdf`

**Source of truth:**
All existing `docs/` files, `src/` implementation, `submission.yaml`,
`src/data/*.json` fixture files, `src/.env.example`, `.github/workflows/validate.yml`,
`.bob/mcp.json`, `requirements.txt`

**Out of scope:**
`src/backend/`, `src/mcp/`, `src/frontend/`, `src/data/`, any Step 1–6 test files,
`.github/workflows/validate.yml` (read-only), `src/.env.example` (already correct),
`.bob/mcp.json` (already correct)

**Immutable constraints:**
- All 237 Python tests must remain passing throughout Step 7
- All 89 frontend tests must remain passing throughout Step 7
- No new application features
- No fake URLs, invented deployments, or fabricated metrics
- `demo/demo-video-link.txt` must NOT be updated until a real hosted video URL exists
- No secrets committed in any file
- Every doc change must be grounded in actual code/fixture/test evidence

---

## Known facts established in Step 7 Discovery (source of truth for all phases)

### Fixture IDs (canonical)
- Shipments: `SHP-1001`, `SHP-1002`, `SHP-1003`
- Fleet: `FLT-302`, `FLT-109`, `FLT-514`
- Disruptions: `DIS-501` (Winter Storm, I-90 / Snoqualmie Pass), `DIS-502` (Roadwork I-65), `DIS-503` (Newark port customs outage)
- Routes: `RT-CHI-ATL-01` (`"Chicago, IL"` → `"Atlanta, GA"`), `RT-SEA-DEN-01` (`"Seattle, WA"` → `"Denver, CO"`)
- Telemetry: `TEL-FLT-302`, `TEL-FLT-109`, `TEL-FLT-514`

### Key engine facts (for correct documentation)
- Risk score: 0–100 engine output (DB stores 0–1 reference fractions)
- SHP-1002: best demo shipment — `ALERT_DISRUPTION`, cargo `-17.2°C` vs max `-18°C` (WARNING excursion)
- All 3 shipment origins do NOT match fixture route origins (exact-string mismatch) → `no_route_found=True` for all
- All 3 fleet assets have `status: "ACTIVE"` — none are truly idle
- `FleetAsset.current_lat/lon` are null — GPS from telemetry used as fallback
- Database: SQLite (not PostgreSQL); `supply_chain.db` auto-created on first backend start
- Map: Leaflet + OpenStreetMap tiles (no API key required; no Mapbox)
- MCP transport: `stdio` (not SSE)

### CI checks that currently FAIL
1. `demo/demo-video-link.txt` line 1 is `https://youtu.be/your-demo-video-link-here`
2. `README.md` contains `[Your Project Title Here]` and `[Your Team Name]`

### Confirmed documentation errors (must fix)
- `docs/setup-guide.md` install command: `pip install fastapi uvicorn pydantic requests` → wrong
- `docs/setup-guide.md` backend command: `cd src/backend && uvicorn main:app ...` → wrong
- `docs/setup-guide.md` MCP command: `python3 src/mcp/server.py` → wrong
- `docs/setup-guide.md` MCP_TRANSPORT default: shows `sse` → should be `stdio`
- `docs/setup-guide.md` troubleshooting: Mapbox entry → stale (removed in Step 6)
- `docs/architecture.md` sequence diagram: `S204`, `S102`, `TRK-102`, `D01`, `Mumbai Port Strike`, `POST /api/shipments/S204/optimize-route` → all fictional
- `docs/architecture.md` component table: `MapLibre GL` → should be `Leaflet`, `PostgreSQL+PostGIS` → SQLite (PostGIS is future roadmap), `Scipy/OR-Tools` → pure Python
- `docs/architecture.md` Mermaid diagram node labels: `MapLibre`, `PostgreSQL + PostGIS` → stale
- `docs/solution-overview.md` IBM Bob example query: `S204`, `Mumbai port strike` → fictional
- `submission.yaml` `solution_summary`: claims "Through Step 3" only
- `submission.yaml` `known_limitations`: claims Steps 4–6 are "planned"
- All 3 demo screenshots are blank navy placeholder images
- `presentation/slides.pdf` is corrupt/unreadable

---

## Phase 1 — Submission Metadata

**File:** `submission.yaml`
**Status:** `[ ] pending`

### Intent
Update the four fields that are factually wrong due to being written at the Step 3
checkpoint. The team registration fields are already correct and must not change.

### Fields to update

**`submission.solution_summary`** (multi-line YAML block scalar `>`)

Replace the current text (which ends at "Step 3") with a summary that accurately
describes the complete system. The new summary must:
- Name all four deterministic engines (risk scoring, cold-chain excursion detection,
  route optimization, fleet matching)
- Reference watsonx.ai / IBM Granite for natural-language explanation
- Reference the MCP server with 10 tools and IBM Bob integration
- Reference the Next.js + Tailwind control tower with Leaflet map
- Not claim specific deployment URLs or live production use
- Stay within 5–6 sentences

Example facts to include (grounded in code):
- Multi-factor risk scores 0–100 across 5 sub-scores
- Cold-chain excursion detection against regulatory cargo rules
- Route and fleet optimization via min-max normalization
- AI explanation via `ibm-watsonx-ai` SDK / Granite 3.0 with deterministic fallback
- 10 MCP tools exposed to IBM Bob via FastAPI REST proxy
- Next.js 14 + React + Tailwind control tower with Leaflet/OpenStreetMap map

**`submission.key_features`** (YAML list, minimum 5 entries, maximum 8)

Replace all 5 existing entries (which stop at Step 3) with entries that cover Steps 1–6:
1. Multi-factor deterministic shipment risk scoring (0–100) across disruption proximity,
   weather conditions, route exposure, cold-chain status, and business impact
2. Automated cold-chain excursion detection comparing live telemetry against
   regulatory cargo rules (WHO-grade cold chain, perishable frozen, ultra-cold)
3. Multi-criteria route and fleet optimization using min-max normalization across
   ETA, cost, disruption avoidance, weather risk, and cargo compatibility
4. IBM Granite AI-powered operational explanations via watsonx.ai with deterministic
   fallback when credentials are absent
5. 10 MCP tools registered on an IBM Bob-compatible server enabling natural-language
   supply-chain queries and AI-synthesized incident briefs
6. Next.js 14 control tower with Leaflet map, risk gauges, cold-chain panels, and
   AI brief panels

**`submission.tech_stack`**

```yaml
tech_stack:
  languages: ["Python", "TypeScript"]
  frameworks: ["FastAPI", "SQLAlchemy", "Pydantic v2", "Next.js 14", "React 18", "Tailwind CSS"]
  ibm_technologies: ["watsonx.ai", "IBM Granite 3.0", "IBM Bob", "Model Context Protocol (MCP)"]
  databases: ["SQLite"]
  other: ["Leaflet", "OpenStreetMap", "ibm-watsonx-ai SDK", "MCP SDK", "httpx", "Uvicorn", "pytest", "Jest", "React Testing Library"]
```

**`submission.what_we_are_most_proud_of`** (multi-line block scalar `>`)

Replace the Step-3 text. New text must:
- Mention the complete 237-test Python + 89-test frontend test suite
- Highlight the clean separation between deterministic engines and AI annotation
- Mention the MCP/Bob integration and watsonx.ai fallback resilience
- Mention the three-layer evidence model concept
- Not overclaim (no "production-ready", no live deployment)

**`submission.known_limitations`** (multi-line block scalar `>`)

Replace the text that claims Steps 4–6 are "planned". Actual limitations:
- Route matching uses exact string equality on origin/destination; none of the 3
  prototype shipment origins match the 2 seeded fixture routes → `no_route_found=True`
  for all prototype shipments (documented MD-05)
- Fleet asset GPS coordinates are not seeded; telemetry GPS is used as a proxy fallback
- All 3 prototype fleet assets have `status: "ACTIVE"` (none are truly idle); the fleet
  matcher scores them but cannot guarantee a free asset in production
- Disruption proximity uses Haversine radius from a single point coordinate; production
  requires polygon-based geofencing (PostGIS roadmap item)
- watsonx.ai live inference requires valid IBM Cloud credentials
  (`WATSONX_APIKEY`, `WATSONX_PROJECT_ID`); without them, the system uses a
  deterministic text fallback — all APIs still return HTTP 200
- Database is SQLite; a PostgreSQL + PostGIS migration is a documented roadmap item
- No authentication layer; API endpoints are open for local/hackathon evaluation
- Map renders shipment GPS from telemetry data; fleet markers are omitted because
  seeded fleet assets carry no GPS coordinates

### Validation
- `yq '.' submission.yaml` parses without error
- `yq '.team.name' submission.yaml` → `"Amoung-US"` (unchanged)
- `yq '.team.track' submission.yaml` → `"AI"` (unchanged)
- `yq '.submission.solution_summary' submission.yaml` does NOT contain "Through Step 3"
- `yq '.submission.known_limitations' submission.yaml` does NOT contain "planned in subsequent steps"
- `yq '.submission.tech_stack.languages' submission.yaml` contains `"TypeScript"`
- CI step 3 passes (all required YAML fields filled, track is `AI`)

### Acceptance criteria
- `submission.yaml` accurately and completely describes Steps 1–6
- No team registration fields changed
- No fabricated data (URLs, metrics, customers)
- All YAML scalar values are double-quoted strings
- CI YAML validation (step 3) passes

---

## Phase 2 — README

**File:** `README.md`
**Status:** `[ ] pending`

### Intent
Completely replace the template README. This is the primary document judges read.
It must describe the actual project, give correct setup steps, and contain zero
placeholder text to pass the two CI placeholder checks.

### Required sections and their content

**Title and badge line**
```
# 🛡️ SupplyGuard AI
### Supply Chain Disruption Assistant & Fleet Utilization Optimizer
```

**Team table**
Populate from `submission.yaml`: Team Amoung-US, AI Track, lead Ahmedabbas Momin,
members Tirth Mantri, Vivek Muliya, Anuj Patel. Use actual email addresses already
in `submission.yaml`.

**Problem statement** (3–4 sentences)
Ground in `docs/problem-statement.md`. Mention: reactive supply-chain management,
cold-chain losses, fleet idle time. Do not duplicate the entire problem-statement.md.
Link to it for depth.

**Solution** (3–4 sentences)
Ground in `docs/solution-overview.md`. Mention: Three-Layer Evidence Model,
deterministic engines → AI annotation → MCP dispatch.

**Core capabilities** (bulleted list, 6 items)
Map to the 6 key features in the updated `submission.yaml`.

**Architecture overview**
Single-paragraph description: SQLite ↔ FastAPI engines ↔ watsonx.ai ↔ MCP ↔ IBM Bob;
separately, Next.js frontend ↔ FastAPI REST. Link to `docs/architecture.md` for the
full diagram.

**Technology stack** (table)
Populate from updated `submission.yaml` tech_stack. Four rows:
Languages, Frameworks, IBM Technologies, Other Tools/DBs.

**Repository structure**
Use the actual tree from the real repository:
```
├── src/
│   ├── backend/           # FastAPI backend + 4 intelligence engines
│   ├── mcp/               # MCP server + 10 tools
│   ├── frontend/          # Next.js 14 control tower
│   ├── data/              # Seed fixture JSON files (read-only)
│   └── tests/             # 237 Python tests
├── docs/                  # Architecture, setup, solution docs
├── demo/                  # Screenshots and video link
├── presentation/          # Slide deck
├── .bob/mcp.json          # IBM Bob MCP server configuration
└── submission.yaml        # Hackathon submission metadata
```

**Local setup** (step-by-step)

Step 1 — Clone:
```bash
git clone https://github.com/Tirthmantri20/bob-ai-hackathon-Amoung-us.git
cd bob-ai-hackathon-Amoung-us
```

Step 2 — Python environment and dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Step 3 — Environment configuration:
```bash
cp src/.env.example src/.env
# For watsonx.ai live mode: edit src/.env and set WATSONX_APIKEY,
# WATSONX_PROJECT_ID, WATSONX_URL, WATSONX_MODEL_ID.
# Without these, the system uses a deterministic fallback (fully functional).
```

Step 4 — Start the backend (from repository root):
```bash
source .venv/bin/activate
python -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --reload
```
Health check: `http://localhost:8000/health`
Swagger UI: `http://localhost:8000/docs`
Note: database and seed data are created automatically on first startup.

Step 5 — Start the frontend:
```bash
cd src/frontend
npm install    # or: npm ci
npm run dev
```
Control Tower: `http://localhost:3000`

Step 6 — Start the MCP server (for IBM Bob):
```bash
# From repository root, with venv activated:
python -m src.mcp.server
```
IBM Bob reads `.bob/mcp.json` at the project root. No additional Bob configuration
is required.

**watsonx.ai configuration**
Two-sentence explanation: set the four env vars for live Granite inference; without
them the fallback returns a deterministic text response with `ai_generated: false`.
All API endpoints return HTTP 200 in both modes.

**Test commands**
```bash
# Python suite (237 tests)
source .venv/bin/activate
pytest src/tests/ -v

# Frontend suite (89 tests, 13 suites)
cd src/frontend
npm test -- --runInBand
npm run lint
npm run build
```

**Demo links**
| Artifact | Link |
|---|---|
| Demo Video | See `demo/demo-video-link.txt` |
| Live Demo | See `demo/live-demo-url.txt` |
| Screenshots | `demo/screenshots/` |
| Presentation | `presentation/slides.pdf` |

**Known limitations**
5 bullets from the updated `submission.yaml` known_limitations. Do not duplicate
the full text — summarize.

**What we are most proud of**
3–4 sentences from `submission.yaml`. Mention: clean engine/AI boundary, 237+89
tests, MCP/Bob integration, watsonx fallback resilience.

### Validation
- `grep -q "\[Your Project Title Here\]" README.md` → exit 1 (not found = pass)
- `grep -q "\[Your Team Name\]" README.md` → exit 1 (not found = pass)
- No `[placeholder]` bracket patterns remain
- Both CI checks (steps 5 and 6 in validate.yml) pass

### Acceptance criteria
- Zero template placeholders
- All code references (commands, endpoints, ports, paths) are accurate
- Links to `docs/` files are valid relative paths
- Team information matches `submission.yaml`

---

## Phase 3 — Documentation Consistency

**Files:** `docs/architecture.md`, `docs/solution-overview.md`
**Status:** `[ ] pending`

### Intent
Fix stale IDs, stale technology claims, and pre-implementation assumptions that
are now contradicted by the actual running system. Minimal changes only — do not
redesign the architecture narrative.

### 3A — `docs/architecture.md` changes

**End-to-end data flow sequence diagram (lines 69–104)**

Replace all legacy identifiers with actual fixture IDs. Changes:

| Current (wrong) | Correct |
|---|---|
| `GET /api/disruptions/D01/impact` | `GET /api/disruptions/DIS-501/affected-shipments` |
| `Return affected shipments [S204, S102]` | `Return affected shipments near DIS-501` |
| `POST /api/shipments/S204/optimize-route` | `GET /api/shipments/SHP-1002/routes` |
| `Return Ranked Routes (R2 bypass) & Redeployment (TRK-102 reefer)` | `Return route recommendations and fleet-match result` |
| `Generate explanation for S204 reroute` | `Generate explanation for SHP-1002 disruption risk` |
| `get_shipment_risk(shipment_id="S204")` | `evaluate_shipment_risk(shipment_id="SHP-1002")` |
| `"Mumbai Port Strike / Extreme Heat"` | `"Winter Storm DIS-501 / Cold-Chain Excursion SHP-1002"` |

Also fix the note label `2. Disruption Trigger & Detection` example text to use
`DIS-501` (Winter Storm Warning, Snoqualmie Pass) not "Mumbai Port Strike".

**Component breakdown table (lines 54–63)**

| Row | Current | Correct |
|---|---|---|
| Next.js Control Tower | `MapLibre GL / Leaflet, Recharts` | `Leaflet, react-leaflet, OpenStreetMap tiles` |
| Optimization Engine | `Scipy / Google OR-Tools` | `Pure-Python min-max normalization` |
| Geospatial Database | `PostgreSQL 16 + PostGIS 3.4 / GeoAlchemy2` | `SQLite (SQLAlchemy 2.0) — PostgreSQL/PostGIS is a documented future roadmap item` |

**Mermaid flowchart node labels (lines 7–48)**

| Node | Current | Correct |
|---|---|---|
| `FE` | `MapLibre` | `Leaflet / OpenStreetMap` |
| `DB` | `PostgreSQL + PostGIS` | `SQLite + SQLAlchemy` |

### 3B — `docs/solution-overview.md` changes

**IBM Bob example query (line 71)**

Current:
```
"Which shipments are impacted by the Mumbai port strike and what idle reefer can rescue S204?"
```

Replace with:
```
"What is the risk level for shipment SHP-1002 and which fleet asset can support it?"
```
This is directly executable against the real MCP tools (`evaluate_shipment_risk` +
`match_fleet_asset`).

**Key design decisions table (line 82)**

Row: `PostgreSQL / PostGIS Geospatial Layer`

This row describes a future roadmap decision. Rename the "Decision" cell to make
its status clear:
```
PostgreSQL / PostGIS (roadmap — prototype uses SQLite)
```
Do not remove the row — it correctly explains the intended production direction.

### Validation
- `grep "S204\|S102\|TRK-102\|Mumbai Port Strike" docs/architecture.md` → zero matches
- `grep "S204\|Mumbai port" docs/solution-overview.md` → zero matches
- `grep "MapLibre" docs/architecture.md` → zero matches (Mermaid node labels updated)
- `grep "OR-Tools\|Scipy" docs/architecture.md` → zero matches in component table
- All fixture IDs used in docs are present in `src/data/` fixture files
- `pytest src/tests/ -v` still shows 237 passed (docs changes don't affect tests)

### Acceptance criteria
- No fictional IDs (`S204`, `S102`, `TRK-102`, `D01`) in any architecture or solution doc
- Technology claims match the installed packages in `requirements.txt` and `package.json`
- PostgreSQL/PostGIS referenced only as future roadmap, clearly labelled
- MCP sequence uses actual tool names matching `src/mcp/server.py` registrations

---

## Phase 4 — Setup/Reproducibility

**File:** `docs/setup-guide.md`
**Status:** `[ ] pending`

### Intent
A judge following this guide from a clean clone must be able to start the entire
stack. Five confirmed errors must be fixed; correct content must be preserved.

### Changes

**Section 2 — Backend Setup (replace lines 55–63)**

Remove:
```bash
pip install --upgrade pip
pip install fastapi uvicorn pydantic requests
```

Replace with:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
Note: This installs all 9 required packages including `ibm-watsonx-ai`, `mcp`,
`sqlalchemy`, `numpy`, `pandas`, `python-dotenv`, `httpx`.

**Section "Start the FastAPI Backend" (replace line 87)**

Remove:
```bash
cd src/backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Replace with (run from repository root):
```bash
source .venv/bin/activate
python -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --reload
```
Add note: The backend auto-creates `supply_chain.db` and seeds all fixture data
on first startup. No separate migration step is required.

**Section "Start the MCP Server" (replace lines 94–98)**

Remove:
```bash
python3 src/mcp/server.py
```

Replace with:
```bash
source .venv/bin/activate
python -m src.mcp.server
```
Add note: The MCP server uses stdio transport. IBM Bob uses `.bob/mcp.json`
at the project root to discover and launch this server automatically. The MCP
server should be started from the repository root (not from inside `src/mcp/`).

**Environment variables table — MCP_TRANSPORT row (line 39)**

Change default/example value from `sse` to `stdio`.

Add a new row for `WATSONX_MODEL_ID`:
| `WATSONX_MODEL_ID` | Granite model identifier | `ibm/granite-3-8b-instruct` | For live AI |

**Add new section after "Running Automated Tests" — Frontend**

```markdown
### Running the Frontend Test Suite

In the `src/frontend` directory:

```bash
cd src/frontend
npm test -- --runInBand     # 89 tests, 13 suites
npm run lint                # ESLint — must be clean
npm run build               # Static build verification
```
```

**Troubleshooting table — remove Mapbox row**

Remove the row:
```
| `Next.js map not rendering tiles` | Missing Mapbox / MapLibre access token | ...
```
Replace with:
```
| `Next.js map not rendering tiles` | Network connectivity to `unpkg.com` CDN for Leaflet assets | The map uses OpenStreetMap tiles and Leaflet icon assets loaded from `unpkg.com`. Ensure internet access is available. No API key is required. |
```

**Update Scenario C (line 143–145)**

Current text claims FLT-302 is "idle" and "ranked #1". Fix to:
```
**Verification:** Inspect `src/data/fleet.json`. The fleet matcher scores all
three assets by proximity, cargo compatibility, and cooling system capability
against SHP-1002's requirements. In the prototype, all assets have `status: ACTIVE`
(assigned to shipments). The fleet matcher still produces a ranked recommendation
based on scoring heuristics. See `docs/step2-assumptions.md` for CONFLICT-07.
```

### Validation
- A clean clone + `pip install -r requirements.txt` installs all 9 packages
- `python -m uvicorn src.backend.main:app --port 8000` starts from repo root
- `python -m src.mcp.server` runs from repo root
- No Mapbox reference remains in the setup guide
- MCP_TRANSPORT shows `stdio` in the env var table
- `WATSONX_MODEL_ID` is documented
- Frontend test commands are present

### Acceptance criteria
- Every command in the guide runs successfully from a clean clone
- No stale references to `cd src/backend`, `python3 src/mcp/server.py`, or
  `pip install fastapi uvicorn pydantic requests`
- No Mapbox/MapLibre references
- Scenario C accurately reflects the actual fleet fixture data

---

## Phase 5 — Demo Screenshots

**Files:** `demo/screenshots/01-home-dashboard.png`, `02-shp1002-risk-detail.png`,
`03-cold-chain-excursion.png`, `04-ai-explanation.png`, `05-bob-mcp-tool-call.png`
(replace existing `01`, `02`, `03`)
**Status:** `[ ] pending`

### Intent
All 3 current screenshots are solid navy placeholder images with zero content.
They must be replaced with real browser captures of the running application.

### Manual capture procedure (human action required)

**Pre-conditions:**
- `pip install -r requirements.txt` complete (mcp and ibm-watsonx-ai installed)
- `python -m uvicorn src.backend.main:app --port 8000` running
- `cd src/frontend && npm install && npm run dev` running at `http://localhost:3000`
- Browser: Chrome or Firefox at 1280×800 or wider
- (Optional) `src/.env` configured with real watsonx credentials for screenshot 04

**Capture sequence:**

**Screenshot 01 — `01-dashboard-overview.png`**
URL: `http://localhost:3000`
Wait for: shipment roster loads (3 rows), disruption monitor shows 3 events, map
renders with markers.
Capture: full browser viewport. Shows the complete control tower state on load.
SHP-1002 is auto-selected (pre-wired in Dashboard.tsx).

**Screenshot 02 — `02-shp1002-risk-detail.png`**
Click SHP-1002 in the shipment roster.
Wait for: risk gauge renders, 5 sub-score bars visible, shipment detail panel open.
Capture: focus on the ShipmentDetailPanel + risk gauge area.
Must show: risk score gauge, SHP-1002 ID, `ALERT_DISRUPTION` status badge.

**Screenshot 03 — `03-cold-chain-excursion.png`**
With SHP-1002 selected, scroll to or expand the ColdChainPanel.
Wait for: cold-chain status loaded.
Capture: ColdChainPanel showing:
- `cargo_temp_c: -17.2°C`
- `max_temp_c: -18.0°C`
- severity badge: `WARNING`
- excursion indicator active

**Screenshot 04 — `04-ai-explanation.png`**
With SHP-1002 selected, click "Get AI Brief" button.
Wait for: AIBriefPanel renders with response.
Capture: AIBriefPanel showing the headline, explanation, and recommended_action text.
IMPORTANT: Label the screenshot accurately.
- If `ai_generated: true` is shown (live Granite) — this is the preferred capture.
- If `ai_generated: false` (deterministic fallback) — this is also acceptable;
  the caption in `demo/README.md` must say "Deterministic fallback mode" honestly.

**Screenshot 05 — `05-bob-mcp-tool-call.png`**
Open IBM Bob CLI.
Type: `Evaluate the risk for shipment SHP-1002`
Wait for: Bob calls `evaluate_shipment_risk` MCP tool and returns structured JSON.
Capture: Bob terminal/chat showing the natural language query and the structured
JSON response (shipment_id, total_score, severity, sub-scores).
If a second query is illustrative:
Type: `What is the cold-chain status for shipment SHP-1002?`
Capture the tool call and result.

### Naming
All files must be PNG format.
New files: `01-dashboard-overview.png`, `02-shp1002-risk-detail.png`,
`03-cold-chain-excursion.png`, `04-ai-explanation.png`, `05-bob-mcp-tool-call.png`
Delete old files: `01-home-dashboard.png`, `02-query-input.png`, `03-result-output.png`

### Validation
- Each PNG is a real browser capture (not a solid color fill)
- File sizes are > 50 KB (a real screenshot is typically 200 KB–2 MB)
- Content matches the described UI state above
- No API keys, passwords, or credentials visible in any screenshot

### Acceptance criteria
- 5 non-blank PNG screenshots in `demo/screenshots/`
- Screenshots visually match the actual `src/frontend/` components
- AI explanation screenshot is honestly captioned (live vs fallback)
- Bob/MCP screenshot shows a real tool call and structured response

---

## Phase 6 — Demo Documentation and Links

**Files:** `demo/README.md`, `demo/live-demo-url.txt`, `demo/demo-video-link.txt`
**Status:** `[ ] pending`

### Intent
Update demo documentation to match the new screenshots and accurately describe
what each artifact shows. Resolve the two placeholder URL files per the policy
below.

### `demo/README.md` — rewrite

Replace the current content with:

```markdown
# Demo Artifacts — SupplyGuard AI

## Screenshots

| File | What it shows |
|---|---|
| `01-dashboard-overview.png` | Full control tower dashboard: 3 active shipments in roster, Leaflet map with shipment/disruption markers, 3 active disruption events in monitor |
| `02-shp1002-risk-detail.png` | SHP-1002 selected — risk gauge, 5 sub-score bars (disruption, weather, route, cold-chain, business), ALERT_DISRUPTION status |
| `03-cold-chain-excursion.png` | Cold-chain panel for SHP-1002: -17.2°C cargo temp vs -18.0°C max, WARNING severity excursion |
| `04-ai-explanation.png` | AI brief panel — IBM Granite explanation (ai_generated: true) or deterministic fallback (ai_generated: false) |
| `05-bob-mcp-tool-call.png` | IBM Bob CLI calling evaluate_shipment_risk MCP tool for SHP-1002 and receiving structured JSON response |

## Demo Video

See `demo-video-link.txt` for the hosted walkthrough video.

## Live Demo

See `live-demo-url.txt`. The project is designed for local evaluation
following `docs/setup-guide.md`.
```

### `demo/live-demo-url.txt` — update

Replace the placeholder URL with:
```
NOT DEPLOYED — run locally using docs/setup-guide.md

The SupplyGuard AI stack runs fully on localhost:
  Backend:  python -m uvicorn src.backend.main:app --port 8000
  Frontend: cd src/frontend && npm run dev   (http://localhost:3000)
  MCP:      python -m src.mcp.server
```

### `demo/demo-video-link.txt` — BLOCKED

**Do NOT change this file until a real hosted video URL exists.**

The CI workflow will fail if line 1 contains `"your-demo-video-link-here"`.
This is the only remaining CI blocker that cannot be resolved without
a real external artifact (the recorded demo video).

The plan is:
1. Record the demo following the 5-step script in Phase 5 (above)
2. Upload to YouTube (public or unlisted), Loom, or IBM Box
3. Replace line 1 of `demo/demo-video-link.txt` with the real URL
4. Commit as part of the final submission commit (Commit D in Phase 11)

**Under no circumstances should a fake URL be placed here merely to pass CI.**

### Validation
- `demo/README.md` describes actual screenshots (matches Phase 5 captures)
- `demo/live-demo-url.txt` no longer contains `"your-live-demo-url-here.com"`
- `head -1 demo/demo-video-link.txt` does NOT contain `"your-demo-video-link-here"`
  (this is the CI check — it will remain failing until the real URL is added)

### Acceptance criteria
- `demo/README.md` is accurate and refers to the real screenshots by name
- `demo/live-demo-url.txt` gives clear local-run instructions
- `demo/demo-video-link.txt` contains a real hosted URL before final push

---

## Phase 7 — Presentation

**File:** `presentation/slides.pdf`
**Status:** `[ ] pending`

### Intent
The current `presentation/slides.pdf` is corrupt/unreadable (bad XRef entry —
likely a 0-byte or stub file). A valid 8-slide PDF must be created.

### Slide content specification

**Slide 1 — Title**
- Heading: SupplyGuard AI
- Subtitle: Supply Chain Disruption Assistant & Fleet Utilization Optimizer
- Team: Amoung-US | AI Track
- Members: Ahmedabbas Momin, Tirth Mantri, Vivek Muliya, Anuj Patel
- Hackathon: IBM Bob AI Hackathon

**Slide 2 — Problem**
Three pain points from `docs/problem-statement.md`:
- Blind disruption propagation (4–6 hr MTTR)
- Lagging cold-chain visibility (reactive IoT alerts after breach)
- Suboptimal fleet redeployment (20–35% idle time)
Quantified impact: $35B annual biopharma cold-chain losses (IQVIA citation from problem-statement.md)

**Slide 3 — Solution**
Three-Layer Evidence Model diagram (text-based or simple graphic):
- Layer 1: Observed Telemetry (in-transit sensor readings)
- Layer 2: Environmental Forecast (weather along route)
- Layer 3: Predicted Exposure Risk (deterministic inference)
Flow: Detect → Score → Explain → Act

**Slide 4 — Architecture**
Simplified text/diagram:
```
IBM Bob ──MCP/stdio──► MCP Server (10 tools)
                              │
Next.js Control Tower ──REST──► FastAPI Backend
                              │
              ┌───────────────┼───────────────┐
           Risk Engine  Cold-Chain    Route/Fleet
           (0-100)      Excursion     Optimizer
              │              │              │
              └──────── SQLite DB ──────────┘
                              │
                      watsonx.ai / Granite
                      (AI explanation layer)
```
Label: "PostgreSQL + PostGIS = future roadmap"

**Slide 5 — Demo (key screenshot)**
Insert Screenshot 01 (dashboard overview) and/or Screenshot 02 (SHP-1002 risk detail)
Caption: "SHP-1002: ALERT_DISRUPTION — risk score, cold-chain excursion, AI brief"

**Slide 6 — IBM Technologies**
Three sections:
1. **watsonx.ai / IBM Granite 3.0** — generates operational explanations from
   deterministic evidence. Fallback to deterministic text when unavailable.
   Never hallucinate metrics — AI explains, engines compute.
2. **IBM Bob** — conversational co-pilot. Natural language → MCP tool call →
   structured JSON → actionable response.
3. **Model Context Protocol (MCP)** — 10 tools registered; get_active_shipments,
   evaluate_shipment_risk, evaluate_cold_chain, match_fleet_asset, explain_shipment_risk,
   explain_disruption_impact, etc.

**Slide 7 — Results**
| Metric | Value |
|---|---|
| Python tests | 237 passed, 0 failed |
| Frontend tests | 89 passed, 13 suites |
| REST API endpoints | 14 GET + 2 POST = 16 |
| MCP tools (IBM Bob) | 10 |
| Frontend build | Static build ✅ |
| Lint | Clean ✅ |

**Slide 8 — Team**
| Name | Role |
|---|---|
| Ahmedabbas Momin (lead) | Backend, watsonx.ai, MCP |
| Tirth Mantri | Frontend, architecture |
| Vivek Muliya | Intelligence engines |
| Anuj Patel | Data models, testing |
(adjust roles if actual allocation is known; otherwise omit role column)

### Constraints
- Must NOT mention: PostgreSQL/PostGIS as implemented, MapLibre, OR-Tools,
  Scipy, S204/S102/TRK-102, streaming responses, fake production deployments
- Must be a valid, readable PDF (not a corrupt/empty file)
- Font size ≥ 20pt for readability
- Maximum 8 slides as per `presentation/README.md` guide

### Creation method
Generate using any available tool: Google Slides → Export PDF, LibreOffice Impress,
Keynote, or a Python PDF library (e.g., `reportlab`). The final file must be named
`presentation/slides.pdf`.

### Validation
- `file presentation/slides.pdf` reports `PDF document` (not `empty` or `data`)
- The PDF opens and renders in a standard PDF viewer
- All 8 slides are present and readable
- No corrupt/empty pages

### Acceptance criteria
- `presentation/slides.pdf` is a valid, non-corrupt, readable PDF
- Content matches the 8-slide specification above
- No placeholder text, fictional IDs, or stale technology claims

---

## Phase 8 — Security Validation

**Files:** (read-only inspection of all files)
**Status:** `[ ] pending`

### Checks to perform before final commit

| Check | How to verify | Expected result |
|---|---|---|
| No `.env` committed | `git ls-files \| grep -E "\.env$\|\.env\.local"` | Zero matches |
| No `supply_chain.db` tracked | `git ls-files \| grep supply_chain.db` | Zero matches |
| No `node_modules` tracked | `git ls-files src/frontend \| grep node_modules` | Zero matches |
| No `.next/` tracked | `git ls-files \| grep "\.next/"` | Zero matches |
| No real credentials in source | `grep -rn "WATSONX_APIKEY\s*=\s*[^y]" src/` | Zero matches |
| No real API key in .bob/mcp.json | File contains only `localhost:8000` | Confirmed in discovery |
| No Mapbox token | `grep -rn "MAPBOX_ACCESS_TOKEN" src/frontend/` | Zero matches |
| src/.env.example placeholders only | All values contain `your-…-here` | Confirmed in discovery |
| No coverage/ or htmlcov/ tracked | `git ls-files \| grep coverage` | Zero matches |

### Acceptance criteria
- `git status` is clean after all Phase 1–7 changes are committed
- `git log --oneline -1` shows the most recent Step 7 commit only
- `git diff HEAD --name-only` shows only intended Step 7 files

---

## Phase 9 — Full Test/Runtime Validation

**Status:** `[ ] pending`

This phase must be run after Phases 1–8 are committed.

### Full validation matrix

| Check | Command | Expected |
|---|---|---|
| Python full suite | `pytest src/tests/ -v` | 237 passed, 0 failed |
| Frontend tests | `cd src/frontend && npm test -- --runInBand` | 89 passed, 0 failed, 13 suites |
| Frontend lint | `cd src/frontend && npm run lint` | `✔ No ESLint warnings or errors` |
| Frontend build | `cd src/frontend && npm run build` | Static pages generated successfully |
| Backend startup | `python -m uvicorn src.backend.main:app --port 8000` | `SupplyGuard AI — ready to accept requests` |
| Backend health | `curl http://localhost:8000/health` | `{"status":"healthy",...}` |
| Backend root | `curl http://localhost:8000/` | `{"status":"online",...}` |
| Swagger UI | Open `http://localhost:8000/docs` | 14+ endpoints across 6 routers visible |
| MCP server | `python -m src.mcp.server` | `SupplyGuard MCP server starting on stdio …` |
| Frontend dev | `cd src/frontend && npm run dev` → open `http://localhost:3000` | Dashboard renders, SHP-1002 auto-selected, map loads |
| Bob tool discovery | IBM Bob reads `.bob/mcp.json` | 10 tools discoverable |
| Security scan | `git ls-files \| grep -E "\.env$\|supply_chain\.db\|node_modules"` | Zero matches |

### Acceptance criteria
- All 237 Python tests pass
- All 89 frontend tests pass
- Frontend lint clean
- Frontend build successful
- Backend starts and health check returns 200
- MCP server starts without errors (requires `mcp` package installed)
- No new failures introduced by any Phase 1–8 change

---

## Phase 10 — CI Readiness

**File:** `.github/workflows/validate.yml` (read-only — do not modify)
**Status:** `[ ] pending`

### CI checks and their resolution

| CI Step | Check | Resolution |
|---|---|---|
| 1 — Required files | All 7 required files exist | ✅ Already passing |
| 2 — YAML parseable | `yq '.' submission.yaml` | ✅ Already passing |
| 3 — Required YAML fields | team.name, track, lead, title, problem_statement, solution_summary, key_features ≥ 1 | ✅ After Phase 1 |
| 4 — src/ not empty | `find src/ -type f` ≥ 1 | ✅ Already passing |
| 5 — Video link not placeholder | `head -1 demo/demo-video-link.txt` ≠ `*your-demo-video-link-here*` | ⚠️ BLOCKED — needs real URL (Phase 6) |
| 6 — README placeholders removed | No `[Your Project Title Here]` or `[Your Team Name]` | After Phase 2 |

### Acceptance criteria
- Steps 1–4, 6 pass after Phases 1–2 are complete
- Step 5 passes only after a real demo video URL is committed (Phase 6/Commit D)
- No CI steps are "passing" via a fake URL

---

## Phase 11 — Git/Commit Plan

**Status:** `[ ] pending`

### Commit strategy

Four logical commits in order. Each commit must be atomic — all tests must pass
at each commit point.

**Commit A — `docs: finalize project documentation`**
Files:
- `docs/setup-guide.md` (Phase 4)
- `docs/architecture.md` (Phase 3A)
- `docs/solution-overview.md` (Phase 3B)

Pre-commit validation:
- `pytest src/tests/ -v` → 237 passed
- `grep "S204\|TRK-102\|MapLibre\|OR-Tools" docs/architecture.md` → zero matches
- All commands in setup guide are correct

**Commit B — `chore: finalize submission metadata`**
Files:
- `submission.yaml` (Phase 1)
- `README.md` (Phase 2)

Pre-commit validation:
- `pytest src/tests/ -v` → 237 passed
- CI steps 3 and 6 pass (YAML fields complete, README placeholders removed)
- `yq '.submission.known_limitations' submission.yaml` does not contain "planned"

**Commit C — `docs: add final presentation and demo materials`**
Files:
- `demo/README.md` (Phase 6)
- `demo/live-demo-url.txt` (Phase 6)
- `demo/screenshots/01-dashboard-overview.png` (Phase 5)
- `demo/screenshots/02-shp1002-risk-detail.png` (Phase 5)
- `demo/screenshots/03-cold-chain-excursion.png` (Phase 5)
- `demo/screenshots/04-ai-explanation.png` (Phase 5)
- `demo/screenshots/05-bob-mcp-tool-call.png` (Phase 5)
- `presentation/slides.pdf` (Phase 7)
- Delete: `demo/screenshots/01-home-dashboard.png` (blank placeholder)
- Delete: `demo/screenshots/02-query-input.png` (blank placeholder)
- Delete: `demo/screenshots/03-result-output.png` (blank placeholder)

Pre-commit validation:
- All 5 new PNG files are non-blank (file size > 50 KB each)
- `presentation/slides.pdf` is readable
- `pytest src/tests/ -v` → 237 passed
- `cd src/frontend && npm test -- --runInBand` → 89 passed

**Commit D — `chore: finalize submission links` (BLOCKED until video exists)**
Files:
- `demo/demo-video-link.txt` (Phase 6 — replace with real URL)

Pre-commit validation:
- `head -1 demo/demo-video-link.txt` does NOT contain `"your-demo-video-link-here"`
- CI step 5 passes
- All other CI steps still pass
- Full test matrix still green

**IMPORTANT:** Commit D must not be created with a fake URL. If no real video
exists at submission time, the submission must be delivered without Commit D and
the known CI failure on Step 5 must be acknowledged in the submission.

### Push strategy
- No force-push
- Push Commits A, B, C together or individually after local validation
- Push Commit D only after real video URL is confirmed
- Branch: `main` — no separate branch required for Step 7 doc/meta changes

### What must NOT happen
- No push with `demo-video-link.txt` containing a fake URL
- No push with `supply_chain.db` committed
- No push with any `.env` file committed
- No push where `pytest src/tests/ -v` shows failures

---

## Summary — Files Modified in Step 7

| File | Phase | Change type |
|---|---|---|
| `submission.yaml` | 1 | Update 5 stale fields |
| `README.md` | 2 | Complete rewrite (template → real content) |
| `docs/setup-guide.md` | 4 | Fix 5 confirmed errors, add frontend test section |
| `docs/architecture.md` | 3A | Fix sequence diagram IDs, component table tech stack |
| `docs/solution-overview.md` | 3B | Fix IBM Bob example query, label PostGIS as roadmap |
| `demo/README.md` | 6 | Rewrite to describe actual screenshots |
| `demo/live-demo-url.txt` | 6 | Replace fake URL with local-run instructions |
| `demo/demo-video-link.txt` | 6 | BLOCKED — update only when real URL exists |
| `demo/screenshots/01-dashboard-overview.png` | 5 | Replace blank with real capture |
| `demo/screenshots/02-shp1002-risk-detail.png` | 5 | New real capture |
| `demo/screenshots/03-cold-chain-excursion.png` | 5 | New real capture |
| `demo/screenshots/04-ai-explanation.png` | 5 | New real capture |
| `demo/screenshots/05-bob-mcp-tool-call.png` | 5 | New real capture |
| `demo/screenshots/01-home-dashboard.png` | 5 | **Delete** (blank placeholder) |
| `demo/screenshots/02-query-input.png` | 5 | **Delete** (blank placeholder) |
| `demo/screenshots/03-result-output.png` | 5 | **Delete** (blank placeholder) |
| `presentation/slides.pdf` | 7 | Replace corrupt file with valid 8-slide PDF |

**DO NOT MODIFY:**
- `src/backend/` — any file
- `src/mcp/` — any file
- `src/frontend/` — any file
- `src/data/` — any file
- `src/tests/` — any file
- `.github/workflows/validate.yml`
- `src/.env.example`
- `.bob/mcp.json`
- `requirements.txt`
