# System Architecture — SupplyGuard AI

## System Architecture

SupplyGuard AI is structured as a decoupled, service-oriented architecture designed to handle real-time geospatial analysis, telematics monitoring, deterministic optimization, and agentic AI co-piloting.

```mermaid
flowchart TD
    subgraph ClientLayer [Client & Interaction Layer]
        FE[Next.js Control Tower<br/>React + Tailwind + MapLibre]
        BOB[IBM Bob CLI / Agent<br/>Conversational Co-Pilot]
    end

    subgraph InterfaceLayer [API & Protocol Layer]
        API[FastAPI Backend Gateway<br/>REST Endpoints /docs]
        MCP[SupplyGuard MCP Server<br/>Model Context Protocol Tools]
    end

    subgraph ComputeEngines [Core Analytical & Decision Engines]
        RISK[Risk Scoring Engine<br/>Disruption + Weather + Cold Chain]
        OPT[Multi-Criteria Optimizer<br/>Routes + Carriers + Fleet]
        CC[Cold-Chain Engine<br/>Excursion Detection & Prediction]
        WX[Environmental Service<br/>Heatmap & Corridor Weather]
        AI[watsonx.ai Service<br/>Granite 3.0 Explanations]
    end

    subgraph DataPersistence [Data & Knowledge Persistence Layer]
        DB[(PostgreSQL + PostGIS<br/>Geospatial Corridors & Shipments)]
        FIXTURES[(Seed Data Fixtures<br/>Shipments, Fleet, Telemetry, Rules)]
    end

    FE -->|REST API Requests| API
    BOB -->|Tool Invocations via JSON-RPC| MCP
    MCP -->|Internal Service Calls| API

    API --> RISK
    API --> OPT
    API --> CC
    API --> WX
    API --> AI

    RISK --> DB
    OPT --> DB
    CC --> DB
    WX --> DB

    DB --- FIXTURES
```

---

## Component Breakdown

| Component | Technology | Responsibility |
|---|---|---|
| **Next.js Control Tower** | Next.js 14, React, Tailwind CSS, MapLibre GL / Leaflet, Recharts | Interactive operations console rendering multi-layer thermal heat maps, live shipment statuses, fleet allocation boards, and AI chat panels. |
| **Backend API Gateway** | Python 3.11+, FastAPI, Pydantic v2, Uvicorn | High-performance RESTful API orchestrating analytical engines, parameter validation, and client routing. |
| **Risk Scoring Engine** | Python, NumPy, Pandas | Deterministic multi-variable risk calculator generating normalized (0–100) scores for shipments, corridors, and delays. |
| **Optimization Engine** | Python, Scipy / Google OR-Tools | Multi-objective routing, carrier ranking, and idle fleet redeployment matcher based on distance, cargo suitability, and SLA bounds. |
| **Cold-Chain Engine** | Python, Time-Series Algorithms | Evaluates telematics streams against cargo temperature bounds; computes excursion durations and predictive environmental heat loads. |
| **watsonx.ai Integration** | `ibm-watsonx-ai` SDK, IBM Granite 3.0 | Translates structured engine metrics into executive summaries, action plans, and natural language explanations without hallucinations. |
| **MCP Server** | Python MCP SDK (stdio / SSE) | Exposes 10 operational supply-chain tools to IBM Bob, enabling autonomous inquiry and dispatch action. |
| **Geospatial Database** | PostgreSQL 16 + PostGIS 3.4 / GeoAlchemy2 | Stores spatial routes, geofences, waypoint geometries, and handles spatial corridor intersection queries. |

---

## End-to-End Data Flow

```mermaid
sequenceDiagram
    autonumber
    actor Dispatcher as Operations Dispatcher
    participant FE as Next.js Control Tower
    participant API as FastAPI Backend
    participant CC as Cold Chain Engine
    participant OPT as Optimization Engine
    participant AI as watsonx.ai Service
    participant MCP as MCP Server
    participant Bob as IBM Bob

    Note over API,CC: 1. Continuous Ingestion & Monitoring
    API->>CC: Ingest IoT Telemetry & Corridor Forecast
    CC->>CC: Detect out-of-range sensor readings & predict thermal exposure
    
    Note over Dispatcher,FE: 2. Disruption Trigger & Detection
    Dispatcher->>FE: Inspect active Mumbai Port Strike / Extreme Heat alert
    FE->>API: GET /api/disruptions/D01/impact
    API->>FE: Return affected shipments [S204, S102] with elevated risk scores
    
    Note over FE,OPT: 3. Automated Mitigation & Optimization
    FE->>API: POST /api/shipments/S204/optimize-route
    API->>OPT: Compute feasible routes, carriers & idle fleet matches
    OPT->>API: Return Ranked Routes (R2 bypass) & Redeployment (TRK-102 reefer)
    
    Note over API,AI: 4. Narrative Synthesis
    API->>AI: Generate explanation for S204 reroute & reefer transfer
    AI->>API: Return auditable natural language operational rationale
    API->>FE: Display recommendation card with trade-off metrics
    
    Note over Bob,MCP: 5. Agentic Co-Pilot Inquiry
    Bob->>MCP: Call tool: get_shipment_risk(shipment_id="S204")
    MCP->>API: Fetch live evaluation
    API->>MCP: Return structured telemetry & predictive heat exposure
    Bob->>Dispatcher: Deliver actionable advice & confirm reroute execution
```

---

## Core Mathematical Formulations

### 1. Shipment Risk Scoring
$$\text{Shipment Risk} = 0.30 \times R_{\text{disruption}} + 0.25 \times R_{\text{weather}} + 0.20 \times R_{\text{route}} + 0.15 \times R_{\text{cold\_chain}} + 0.10 \times R_{\text{business}}$$
- **Normalized Scale:** 0 to 100.
- **Classification:** 0–25 `LOW` | 26–50 `MEDIUM` | 51–75 `HIGH` | 76–100 `CRITICAL`.

### 2. Candidate Route Optimization
$$\text{Score}_{\text{route}} = 0.30 \times (1 - \hat{\text{ETA}}) + 0.20 \times (1 - \hat{\text{Cost}}) + 0.25 \times (1 - \hat{E}_{\text{disruption}}) + 0.15 \times (1 - \hat{E}_{\text{weather}}) + 0.10 \times (1 - \hat{E}_{\text{cold\_chain}})$$
*(Where all hat variables represent min-max normalized factors).*

### 3. Idle Fleet Asset Matching
$$\text{Score}_{\text{fleet}} = 0.30 \times \text{Proximity} + 0.25 \times \text{Cargo Compatibility} + 0.20 \times \text{Refrigeration Match} + 0.15 \times \text{Capacity Match} + 0.10 \times \text{Availability}$$

---

## Data Models & Schema

- **`shipments`**: ID, origin, destination, current GPS coordinates, cargo type, cargo value, status, required temp bounds ($T_{\min}, T_{\max}$), assigned carrier, ETA.
- **`fleet_assets`**: ID, vehicle type, current coordinates, status (`IDLE`, `EN_ROUTE`), capacity (kg), refrigeration specs, temp range capability, fuel/battery level.
- **`disruptions`**: ID, category (`PORT_STRIKE`, `SEVERE_WEATHER`, `ROAD_CLOSURE`), geometry polygon / radius, severity, delay factor, active window.
- **`weather`**: Station ID, coordinates, ambient temperature, precipitation, wind speed, road condition, forecast vector.
- **`telemetry`**: Sensor ID, vehicle ID, shipment ID, timestamp, cargo temperature, humidity, vibration, compressor operational mode, GPS vector.
- **`cargo_rules`**: Cargo classification, regulatory standard (e.g., WHO TRS 961), allowable excursions, maximum duration before critical status.
- **`routes`**: ID, corridor name, origin/destination, distance, typical transit time, waypoints, known cold-storage depots.
- **`carriers`**: ID, carrier name, compliance rating, on-time delivery rate, active fleet size, certifications.

---

## Security & Reliability Considerations

1. **Zero Secret Leakage:** No credentials, API tokens, or database passwords are hardcoded or tracked in Git. All secrets load via `.env` (validated against `.env.example`).
2. **CORS & Input Validation:** Strict Pydantic models validate all incoming API payloads; CORS middleware restricts unauthorized origins.
3. **Sandboxed AI Invocations:** watsonx.ai receives structured JSON dictionaries rather than raw database dumps or unbounded system prompts, preventing prompt injection and data exfiltration.
4. **Deterministic Auditing:** LLM output is paired with mathematical proof points, ensuring full reproducibility and auditability for regulatory bodies.

---

## Scalability & Production Roadmap

- **Horizontal Scaling:** FastAPI instances run stateless behind Nginx or AWS ALB.
- **Event Streaming:** Ingest high-velocity IoT streams using Apache Kafka or AWS Kinesis into a TimescaleDB time-series hypertable.
- **Distributed Optimization:** Offload complex multi-depot vehicle routing problems (VRP) to Celery/Redis worker pools executing OR-Tools or cuGraph.
- **Edge Intelligence:** Deploy lightweight predictive cold-chain scoring models directly onto reefer IoT telematics units for disconnected in-transit alerting.
