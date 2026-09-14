# Setup Guide — SupplyGuard AI

> **This setup guide provides exact, tested steps to run SupplyGuard AI locally.**

---

## Prerequisites

Ensure you have the following installed on your host machine:

- **Python:** Version 3.11 or higher (`python3 --version`)
- **Node.js:** Version 18.x or 20.x LTS (`node --version`)
- **npm:** Version 9.x or higher (`npm --version`)
- **IBM Cloud Account (Optional):** Required only if enabling live watsonx.ai inference — a deterministic fallback is included for offline evaluation

---

## Environment Variables

SupplyGuard AI maintains environment templates in `src/.env.example`. Create your local `.env`:

```bash
cp src/.env.example src/.env
```

| Variable | Description | Default / Example | Required |
|---|---|---|---|
| `PORT` | FastAPI backend server port | `8000` | Yes |
| `HOST` | FastAPI bind address | `0.0.0.0` | Yes |
| `DEBUG` | Verbose application logging | `True` | Yes |
| `DATABASE_URL` | SQLite connection string | `sqlite:///./supply_chain.db` | Yes |
| `WATSONX_APIKEY` | IBM Cloud API key for watsonx.ai | `your-watsonx-apikey-here` | For live AI |
| `WATSONX_PROJECT_ID` | IBM Cloud Project GUID | `your-watsonx-project-id-here` | For live AI |
| `WATSONX_URL` | watsonx.ai service regional endpoint | `https://us-south.ml.cloud.ibm.com` | For live AI |
| `WATSONX_MODEL_ID` | Granite model identifier | `ibm/granite-3-8b-instruct` | For live AI |
| `IBM_BOB_API_KEY` | IBM Bob integration token | `your-ibm-bob-api-key-here` | Optional |
| `MCP_SERVER_HOST` | Host address for MCP server (documentation only) | `0.0.0.0` | Optional |
| `MCP_SERVER_PORT` | Port for MCP server (documentation only) | `8001` | Optional |
| `MCP_TRANSPORT` | MCP transport layer | `stdio` | Yes |
| `NEXT_PUBLIC_API_URL` | URL pointing to FastAPI backend | `http://localhost:8000` | Yes |

> **watsonx.ai fallback:** If `WATSONX_APIKEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, and `WATSONX_MODEL_ID` are not all set, the backend automatically uses a deterministic text fallback. All API endpoints and MCP tools still return HTTP 200 with `ai_generated: false`. No live IBM credentials are required for local evaluation.

---

## Step-by-Step Installation

### 1. Clone Repository

```bash
git clone https://github.com/Tirthmantri20/bob-ai-hackathon-Amoung-us.git
cd bob-ai-hackathon-Amoung-us
```

### 2. Backend Setup

```bash
# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install all backend dependencies (FastAPI, SQLAlchemy, ibm-watsonx-ai, mcp, httpx, etc.)
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd src/frontend

# Install dependencies exactly as specified in package-lock.json
npm ci

cd ../..
```

---

## Running the Application

### Option A: Local Development (Recommended for Judges)

#### 1. Start the FastAPI Backend

In Terminal 1, from the **repository root**:
```bash
source .venv/bin/activate
python -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --reload
```
- **API Health Check:** [http://localhost:8000/health](http://localhost:8000/health)
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

> **Note:** The SQLite database (`supply_chain.db`) and all fixture data (shipments, fleet, routes, disruptions, telemetry, weather, cargo rules) are **created and seeded automatically** on first startup. No separate database migration step is required.

#### 2. Start the MCP Server (for IBM Bob)

In Terminal 2, from the **repository root**:
```bash
source .venv/bin/activate
python -m src.mcp.server
```
- The MCP server initializes on stdio and registers 10 supply-chain tools for IBM Bob.
- IBM Bob automatically discovers and launches this server using [`.bob/mcp.json`](.bob/mcp.json) at the project root.

#### 3. Start the Next.js Frontend Control Tower

In Terminal 3:
```bash
cd src/frontend
npm run dev
```
- **Control Tower Web UI:** [http://localhost:3000](http://localhost:3000)
- Shipment `SHP-1002` is pre-selected on dashboard load as the highest-risk demonstration shipment.

---

## Running Automated Tests

### Python Test Suite (237 tests, Steps 1–5)

```bash
source .venv/bin/activate
pytest src/tests/ -v
```

### Frontend Test Suite (89 tests, 13 suites)

```bash
cd src/frontend
npm test -- --runInBand   # Run all 89 tests serially
npm run lint              # ESLint — must be clean
npm run build             # Production static build verification
```

---

## Executing the Three Demo Scenarios

SupplyGuard AI includes pre-configured deterministic test fixtures in `src/data/` for immediate validation:

### Scenario A: Winter Storm Disruption Interception

- **Input:** Disruption `DIS-501` (Winter Storm Warning, Snoqualmie Pass, I-90) active in transit corridor.
- **Verification:** Call `GET /api/disruptions/DIS-501/affected-shipments`. Shipments near the disruption radius are flagged with elevated risk scores.

### Scenario B: Cold-Chain Excursion Detection

- **Input:** Frozen seafood shipment `SHP-1002` with `cargo_temp_c: -17.2°C` vs allowable max `-18.0°C`.
- **Verification:** Call `GET /api/shipments/SHP-1002/cold-chain`. The engine detects a warm excursion of +0.8°C above maximum, classifies severity as `WARNING`.

### Scenario C: Fleet Asset Matching

- **Input:** High risk on shipment `SHP-1002`; refrigerated unit evaluation needed.
- **Verification:** Call `GET /api/shipments/SHP-1002/fleet-match`. The fleet matcher scores all three prototype fleet assets (`FLT-302`, `FLT-109`, `FLT-514`) by proximity proxy, cargo compatibility, and cooling system capability.

> **Note:** All three prototype fleet assets have `status: ACTIVE` in the fixture data (assigned to shipments). The fleet matcher still produces a ranked recommendation based on scoring heuristics. See `docs/step2-assumptions.md` for CONFLICT-07 (documented prototype assumption).

---

## IBM Bob Configuration

IBM Bob reads [`.bob/mcp.json`](.bob/mcp.json) at the project root to discover and launch the MCP server. The configuration uses `python -m src.mcp.server` with stdio transport. No additional Bob configuration is needed — open IBM Bob in the repository root and the 10 SupplyGuard tools will be available.

---

## Troubleshooting Guide

| Issue | Likely Cause | Solution |
|---|---|---|
| `Address already in use (Port 8000)` | Another process is occupying port 8000 | Kill process with `lsof -ti:8000 \| xargs kill -9` or change `PORT=8080` in `src/.env`. |
| `ModuleNotFoundError: No module named 'fastapi'` | Virtual environment not activated or `pip install -r requirements.txt` not run | Activate: `source .venv/bin/activate` then `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'mcp'` | `pip install -r requirements.txt` not run | Run `pip install -r requirements.txt` from the repository root with venv activated. |
| `watsonx.ai 401 Unauthorized` | Invalid or expired IBM Cloud API Key | Ensure `WATSONX_APIKEY` is valid in `src/.env`. The backend gracefully falls back to deterministic local explanations if the live key is omitted or invalid. |
| `Next.js map not rendering tiles` | Network connectivity to `unpkg.com` CDN | The map uses OpenStreetMap tiles and Leaflet icon assets loaded from `unpkg.com`. Ensure internet access is available. No API key is required. |
| `CORS Error in Browser Console` | Frontend port mismatch | Ensure the frontend runs on port 3000. FastAPI `CORSMiddleware` in `src/backend/main.py` allows all origins for development. |
