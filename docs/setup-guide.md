# Setup Guide — SupplyGuard AI

> **This setup guide provides exact, tested steps to run SupplyGuard AI locally or via containerized services.**

---

## Prerequisites

Ensure you have the following installed on your host machine:

- **Python:** Version 3.11 or higher (`python3 --version`)
- **Node.js:** Version 18.x or 20.x LTS (`node --version`)
- **npm:** Version 9.x or higher (`npm --version`)
- **Docker & Docker Compose (Optional):** For PostgreSQL/PostGIS containerized deployment
- **IBM Cloud Account (Optional):** Required only if enabling live watsonx.ai inference (mock fallback included for offline evaluation)

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
| `DATABASE_URL` | PostgreSQL or SQLite connection string | `sqlite:///./supply_chain.db` | Yes |
| `WATSONX_APIKEY` | IBM Cloud API key for watsonx.ai | `your-watsonx-apikey` | For live AI |
| `WATSONX_PROJECT_ID` | IBM Cloud Project GUID | `your-watsonx-project-id` | For live AI |
| `WATSONX_URL` | watsonx.ai service regional endpoint | `https://us-south.ml.cloud.ibm.com` | For live AI |
| `IBM_BOB_API_KEY` | IBM Bob integration token | `your-ibm-bob-api-key` | Optional |
| `MCP_SERVER_HOST` | Host address for MCP server | `0.0.0.0` | Yes |
| `MCP_SERVER_PORT` | Port for MCP server | `8001` | Yes |
| `MCP_TRANSPORT` | MCP transport layer (`stdio` or `sse`) | `sse` | Yes |
| `NEXT_PUBLIC_API_URL`| URL pointing to FastAPI backend | `http://localhost:8000` | Yes |

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

# Install backend dependencies
pip install --upgrade pip
pip install fastapi uvicorn pydantic requests
```

### 3. Frontend Setup

```bash
cd src/frontend

# Install dependencies
npm install

cd ../..
```

---

## Running the Application

### Option A: Local Development (Recommended for Judges)

#### 1. Start the FastAPI Backend
In Terminal 1:
```bash
source .venv/bin/activate
cd src/backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
- **API Health Check:** [http://localhost:8000/health](http://localhost:8000/health)
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

#### 2. Start the MCP Server (for IBM Bob)
In Terminal 2:
```bash
source .venv/bin/activate
python3 src/mcp/server.py
```
- The MCP server initializes and registers supply-chain risk and rerouting tools.

#### 3. Start the Next.js Frontend Control Tower
In Terminal 3:
```bash
cd src/frontend
npm run dev
```
- **Control Tower Web UI:** [http://localhost:3000](http://localhost:3000)

---

### Option B: Docker Compose

If running full database containers:
```bash
docker compose up --build
```

---

## Running Automated Tests

Run the test suite across risk calculations, route ranking, and excursion detection:

```bash
source .venv/bin/activate
pytest src/tests/ -v
```

---

## Executing the Three Demo Scenarios

SupplyGuard AI includes pre-configured deterministic test fixtures in `src/data/` for immediate validation:

### Scenario A: Mumbai Port Strike (Disruption Interception)
- **Input:** Disruption `DIS-501` / `DIS-503` active in transit corridor.
- **Verification:** Query `GET /health` and inspect `src/data/disruptions.json`. Shipments `SHP-1001` and `SHP-1002` are immediately flagged with delay and detour options.

### Scenario B: Extreme Heat / Cold-Chain Risk (Predictive Thermal Load)
- **Input:** Biologics shipment `SHP-1003` with allowable range `-80°C to -60°C`.
- **Verification:** Inspect `src/data/telemetry.json` and `src/data/weather.json`. Environmental heat exposure triggers a predicted cold-chain breach alert prior to delivery.

### Scenario C: Idle Fleet Redeployment (Asset Matching)
- **Input:** High risk on shipment `SHP-1002`; refrigerated unit needed.
- **Verification:** Inspect `src/data/fleet.json`. Idle reefer asset `FLT-302` is matched and ranked #1 for proactive cargo transfer.

---

## Troubleshooting Guide

| Issue | Likely Cause | Solution |
|---|---|---|
| `Address already in use (Port 8000)` | Another process is occupying port 8000 | Kill process with `lsof -ti:8000 \| xargs kill -9` or change `PORT=8080` in `.env`. |
| `ModuleNotFoundError: No module named 'fastapi'` | Virtual environment not activated | Activate virtual environment: `source .venv/bin/activate` and run `pip install fastapi uvicorn`. |
| `watsonx.ai 401 Unauthorized` | Invalid or expired IBM Cloud API Key | Ensure `WATSONX_APIKEY` is valid in `src/.env`. The backend gracefully falls back to deterministic local explanations if live key is omitted. |
| `Next.js map not rendering tiles` | Missing Mapbox / MapLibre access token | The frontend falls back to open-source OpenStreetMap / Leaflet tiles automatically if `NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN` is unset. |
| `CORS Error in Browser Console` | Frontend port mismatch | Ensure `CORS_ORIGINS` includes `http://localhost:3000` (FastAPI `CORSMiddleware` in `src/backend/main.py` is configured for development). |
