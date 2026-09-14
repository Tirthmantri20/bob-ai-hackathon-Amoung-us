# 🛡️ SupplyGuard AI
### Supply Chain Disruption Assistant & Fleet Utilization Optimizer

> **IBM Bob AI Hackathon — Team Amoung-US | AI Track**

---

## 👥 Team

| Field | Value |
|---|---|
| **Team Name** | Amoung-US |
| **Track** | AI |
| **Team Lead** | Ahmedabbas Momin |
| **Members** | Tirth Mantri, Vivek Muliya, Anuj Patel |

---

## 🎯 Problem Statement

Global supply chains and temperature-sensitive cold chains lose billions annually due to reactive management. Logistics dispatchers manually cross-reference news feeds, weather alerts, and telematics portals to identify which active shipments intersect a disruption — by which time freight is already trapped. Cold-chain monitoring relies on threshold sensors that alert *after* a temperature breach, leaving no time to intervene. Fleet redeployment is ad-hoc, conducted via phone calls and spreadsheets while compatible refrigerated assets sit idle in adjacent corridors.

See [`docs/problem-statement.md`](docs/problem-statement.md) for full context and quantified impact.

---

## 💡 Solution

SupplyGuard AI is a full-stack autonomous control tower that moves operations from **reactive panic to proactive decision intelligence**. A deterministic multi-factor risk engine scores every shipment across five sub-scores (disruption proximity, weather, route, cold-chain, business impact). IBM Granite via watsonx.ai synthesizes auditable natural-language explanations from those scores — with a deterministic fallback when credentials are absent. Ten MCP tools expose every engine capability to IBM Bob through natural language. A Next.js control tower provides real-time operational visibility on an interactive Leaflet map.

See [`docs/solution-overview.md`](docs/solution-overview.md) for the Three-Layer Evidence Model and capability detail.

---

## ✨ Core Capabilities

- **Multi-factor risk scoring (0–100)** across disruption proximity, weather, route exposure, cold-chain status, and business impact — pure deterministic Python, no hallucinations
- **Cold-chain excursion detection** — compares live telemetry against regulatory cargo rules (WHO Cold Chain Grade A, Perishable Frozen, Ultra Cold Chain) and classifies severity
- **Route & fleet optimization** — min-max normalization across ETA, cost, disruption avoidance, weather risk, and cargo compatibility
- **IBM Granite AI explanations** via watsonx.ai — structured evidence → natural language operational brief; graceful deterministic fallback when credentials are absent
- **IBM Bob / MCP integration** — 10 tools on a stdio MCP server; natural-language supply-chain queries, risk evaluation, cold-chain status, fleet matching, and AI-synthesized incident briefs
- **Next.js 14 control tower** — Leaflet/OpenStreetMap map, risk gauges, sub-score bars, cold-chain panels, disruption monitor, fleet match panel, and AI brief panel

---

## 🏗️ Architecture Overview

```
IBM Bob ──MCP/stdio──► MCP Server (10 tools) ──HTTP──► FastAPI Backend
                                                              │
Next.js Control Tower ──────────REST GET/POST───────────────►│
                                                              │
                              ┌───────────────────────────────┤
                         Risk Engine   Cold-Chain   Route+Fleet
                          (0–100)      Excursion    Optimizer
                              └───────────────────────────────┤
                                           SQLite (SQLAlchemy) │
                                                              │
                                        watsonx.ai / Granite  │
                                        (AI explanation layer)│
```

See [`docs/architecture.md`](docs/architecture.md) for the full component breakdown, data flow sequence diagram, and mathematical formulas.

---

## 🛠️ Technology Stack

| Category | Technologies |
|---|---|
| **Languages** | Python, TypeScript |
| **Frameworks** | FastAPI, SQLAlchemy, Pydantic v2, Next.js 14, React 18, Tailwind CSS |
| **IBM Technologies** | watsonx.ai, IBM Granite 3.0, IBM Bob, Model Context Protocol (MCP) |
| **Database** | SQLite |
| **Other** | Leaflet, OpenStreetMap, ibm-watsonx-ai SDK, MCP SDK, httpx, Uvicorn, pytest, Jest, React Testing Library |

---

## 📁 Repository Structure

```
├── src/
│   ├── backend/           # FastAPI app, 4 intelligence engines, ORM models, schemas
│   ├── mcp/               # MCP server + 10 IBM Bob tools
│   ├── frontend/          # Next.js 14 control tower (TypeScript + Tailwind)
│   ├── data/              # Seed fixture JSON files (read-only)
│   └── tests/             # 237 Python tests (Steps 1–5)
├── docs/                  # Architecture, setup guide, solution overview, step plans
├── demo/                  # Screenshots and video link
├── presentation/          # slides.pdf
├── .bob/mcp.json          # IBM Bob MCP server configuration
├── requirements.txt       # Python dependencies
└── submission.yaml        # Hackathon submission metadata
```

---

## ⚡ Local Setup

### Prerequisites
- Python 3.11+ (`python3 --version`)
- Node.js 18.x or 20.x LTS (`node --version`)
- npm 9.x+ (`npm --version`)

### 1. Clone the repository

```bash
git clone https://github.com/Tirthmantri20/bob-ai-hackathon-Amoung-us.git
cd bob-ai-hackathon-Amoung-us
```

### 2. Python environment and dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp src/.env.example src/.env
```

For **live watsonx.ai inference**, edit `src/.env` and set:
```
WATSONX_APIKEY=<your-ibm-cloud-api-key>
WATSONX_PROJECT_ID=<your-watsonx-project-id>
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-3-8b-instruct
```

Without these, the system uses a **deterministic fallback** — all 14 REST endpoints and 10 MCP tools remain fully functional and return HTTP 200 with `ai_generated: false`.

### 4. Start the FastAPI backend (from repository root)

```bash
source .venv/bin/activate
python -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

- Health check: http://localhost:8000/health
- Swagger UI: http://localhost:8000/docs
- **Database and seed data are created automatically on first startup — no migration step required.**

### 5. Start the Next.js frontend

```bash
cd src/frontend
npm install       # or: npm ci
npm run dev
```

- Control Tower: http://localhost:3000
- SHP-1002 is pre-selected on load (highest-risk demonstration shipment)

### 6. Start the MCP server (for IBM Bob)

```bash
# From repository root, with venv activated:
python -m src.mcp.server
```

IBM Bob uses [`.bob/mcp.json`](.bob/mcp.json) at the project root to discover and launch this server automatically. No additional Bob configuration is required.

---

## 🧪 Running Tests

```bash
# Python test suite — 237 tests (Steps 1–5)
source .venv/bin/activate
pytest src/tests/ -v

# Frontend test suite — 89 tests, 13 suites
cd src/frontend
npm test -- --runInBand
npm run lint
npm run build
```

---

## 🖥️ Demo

| Artifact | Link |
|---|---|
| 📹 Demo Video | [See demo/demo-video-link.txt](demo/demo-video-link.txt) |
| 🌐 Live Demo | [See demo/live-demo-url.txt](demo/live-demo-url.txt) |
| 🖼️ Screenshots | [demo/screenshots/](demo/screenshots/) |
| 📊 Presentation | [presentation/slides.pdf](presentation/slides.pdf) |

---

## ⚠️ Known Limitations

- **Route string mismatch:** Prototype shipment origin strings do not exactly match the two seeded fixture route origins, so `no_route_found=True` for all prototype shipments (documented prototype assumption MD-05 in [`docs/step2-assumptions.md`](docs/step2-assumptions.md))
- **Fleet GPS unavailable:** Seeded fleet assets carry no GPS coordinates; telemetry GPS is used as a positional proxy
- **All fleet assets are ACTIVE:** No idle assets in prototype fixtures; fleet matcher scores by compatibility heuristics only
- **SQLite database:** PostgreSQL + PostGIS (for polygon-based geofencing) is a documented future roadmap item
- **No authentication:** API endpoints are open for local/hackathon evaluation; not production-ready
- **watsonx.ai requires credentials:** Without `WATSONX_APIKEY` + `WATSONX_PROJECT_ID`, the system falls back to deterministic text explanations (`ai_generated: false`) — fully functional

---

## 🏅 What We're Most Proud Of

The strict architectural boundary between deterministic engines and the AI annotation layer: every risk score, excursion classification, route ranking, and fleet match is computed mathematically before IBM Granite synthesizes the operational explanation. This guarantees auditable, hallucination-free outputs — the LLM explains, the engines compute. The system is validated by 237 Python + 89 frontend tests with zero failures, and the watsonx.ai fallback design keeps the control tower fully operational regardless of credential availability.
