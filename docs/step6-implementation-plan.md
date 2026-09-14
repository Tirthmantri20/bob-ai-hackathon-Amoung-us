# Step 6 Implementation Plan — Next.js Control Tower Frontend
# SupplyGuard AI

**Scope:**
`src/frontend/` (entire directory, built from scratch)
`src/.env.example` (remove stale Mapbox placeholder)

**Source of truth:**
`docs/architecture.md`, `docs/solution-overview.md`,
`docs/setup-guide.md`, Step 6 Discovery session,
Step 6 Final Decision set (decisions 1–28 from the plan prompt)

**Out of scope:**
All `src/backend/` files (engines, routers, schemas, main.py, AI layer, MCP)
All `src/tests/` files
`docs/` files other than this plan
`requirements.txt`
`src/data/` fixtures
Database, credentials, or any live external service

**Immutable constraints:**
- All 237 existing Step 1–5 Python tests must remain green
- No secrets in NEXT_PUBLIC_* variables
- No watsonx credentials in any frontend file
- No database access from browser
- No risk scoring, route scoring, fleet matching, or cold-chain classification in TypeScript
- Frontend calls FastAPI only; MCP/Bob remains a separate integration path
- No Mapbox; Leaflet + OpenStreetMap tiles only (no API key)
- All response fields used in UI must exist in actual Pydantic backend schemas
- SHP-1002 pre-selected on load (strongest demo scenario)
- score scale: ShipmentRisk.total_score is 0–100 (engine scale); Shipment.current_risk_score is 0–1 (DB field) — UI always uses engine scale for the risk gauge

---

## Architecture Overview

```
Browser (Next.js 14 App Router — http://localhost:3000)
  │
  │  fetch() calls — NEXT_PUBLIC_API_URL=http://localhost:8000
  ▼
FastAPI Backend (src/backend/main.py — http://localhost:8000)
  │
  ├─ GET  /api/shipments/
  ├─ GET  /api/shipments/{id}
  ├─ GET  /api/shipments/{id}/risk
  ├─ GET  /api/shipments/{id}/cold-chain
  ├─ GET  /api/shipments/{id}/routes
  ├─ GET  /api/shipments/{id}/fleet-match
  ├─ GET  /api/risk/active
  ├─ GET  /api/disruptions/
  ├─ GET  /api/disruptions/{id}/affected-shipments
  ├─ GET  /api/fleet/
  ├─ GET  /api/routes/
  ├─ POST /api/explain/shipment-risk
  ├─ POST /api/explain/disruption-impact
  └─ GET  /health

IBM Bob → MCP Server → FastAPI   (independent path; frontend does NOT call MCP)
```

## Dependency Direction (no cycles)

```
app/page.tsx
  └─ components/Dashboard.tsx         (orchestrator, all state)
       ├─ components/Header.tsx
       ├─ components/ShipmentRoster.tsx
       ├─ components/ShipmentDetailPanel.tsx
       │    ├─ components/RiskScoreGauge.tsx
       │    ├─ components/SubScoreBar.tsx       (×5)
       │    ├─ components/ColdChainPanel.tsx
       │    ├─ components/RoutePanel.tsx
       │    ├─ components/FleetMatchPanel.tsx
       │    └─ components/AIBriefPanel.tsx
       ├─ components/DisruptionMonitor.tsx
       ├─ components/DisruptionImpactPanel.tsx
       └─ maps/ControlTowerMap.tsx              (loaded ssr:false)

services/
  ├─ api.ts     ← typed fetch client
  └─ types.ts   ← all TypeScript interfaces

__tests__/   ← Jest + Testing Library
```

---

## Score Scale Reference (critical — must be encoded once and reused)

| Field | Scale | Source endpoint | Display rule |
|---|---|---|---|
| `ShipmentRiskResponse.total_score` | 0–100 | `GET /shipments/{id}/risk` | Use for risk gauge |
| `Shipment.current_risk_score` | 0–1 | `GET /shipments/` | Do NOT use for risk gauge |
| `RouteScoreResponse.total_score` | 0–1 | `GET /shipments/{id}/routes` | Display as percentage (×100) or 0.xx |
| `FleetMatchScoreResponse.total_score` | 0–1 | `GET /shipments/{id}/fleet-match` | Display as percentage (×100) or 0.xx |
| All five `r_*` sub-scores | 0–1 | `GET /shipments/{id}/risk` | Tailwind bar width = value × 100% |

---

## Severity / Status Color System

| Value | Tailwind classes | Usage |
|---|---|---|
| CRITICAL | bg-red-600 text-white | ShipmentRisk, ColdChain, Disruption |
| HIGH | bg-orange-500 text-white | ShipmentRisk, ColdChain |
| MEDIUM | bg-yellow-400 text-gray-900 | ShipmentRisk, Disruption |
| LOW | bg-green-600 text-white | ShipmentRisk |
| OK | bg-green-500 text-white | ColdChain |
| WARNING | bg-amber-500 text-white | ColdChain |
| UNKNOWN | bg-gray-400 text-white | Any unresolvable state |
| IDLE | bg-green-600 text-white | FleetAsset status |
| ACTIVE | bg-blue-500 text-white | FleetAsset status |
| EN_ROUTE | bg-purple-500 text-white | FleetAsset status |

---

## Phase Execution Order

1. Phase 0 — Repository cleanup and environment setup
2. Phase 1 — package.json, Next.js config, Tailwind, TypeScript config
3. Phase 2 — TypeScript types (services/types.ts)
4. Phase 3 — Typed API client (services/api.ts)
5. Phase 4 — Shared primitive components
6. Phase 5 — Shipment panels (roster + detail + sub-panels)
7. Phase 6 — Disruption panels
8. Phase 7 — AI brief panel
9. Phase 8 — Leaflet map
10. Phase 9 — Dashboard orchestrator + page shell
11. Phase 10 — Frontend tests
12. Phase 11 — Final validation

---

## Phase 0 — Repository Cleanup

### Intent
Remove the stale `NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN` placeholder from
`src/.env.example` because the implementation uses Leaflet/OSM (no token
required) and the variable must never be referenced by any frontend code.
This is the only backend-adjacent file touched in Step 6.

### Expected Outcomes
- `src/.env.example` no longer contains `NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN`
- `NEXT_PUBLIC_API_URL=http://localhost:8000` remains
- All other `.env.example` entries are unchanged
- 237 existing Python tests still pass

### Todo List
- [ ] In `src/.env.example`, remove the line:
      `NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN=your-mapbox-access-token-here`
- [ ] Verify no other file in the repository references
      `NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN` (grep to confirm)
- [ ] Run `pytest src/tests/ -v` to confirm all 237 tests still pass

### Relevant Context
- `src/.env.example` line 31: the stale placeholder to remove
- `.gitignore` already ignores `.env.local`, `.env.production`
- No frontend code exists yet that could reference this variable

### Status
[ ] pending

---

## Phase 1 — Project Bootstrap (package.json + Config Files)

### Intent
Create the minimum set of configuration files so that `npm install` and
`npm run dev` work inside `src/frontend/`. This phase produces no UI code —
it only wires together the framework, TypeScript, Tailwind, and test runner.

The `package.json` must live at `src/frontend/package.json`. The repository
root must NOT gain a `package.json`.

### Expected Outcomes
- `npm install` succeeds inside `src/frontend/`
- `npm run dev` starts Next.js on port 3000 (renders a blank page)
- `npm run build` succeeds (no TypeScript errors, no Tailwind errors)
- `npm run lint` passes
- `npm test` runs Jest with zero failures (no tests yet — zero suites pass)
- The `.next/` build output is git-ignored (already in `.gitignore`)
- `node_modules/` is git-ignored (already in `.gitignore`)

### Todo List

#### A — package.json

Create `src/frontend/package.json` with:

**Runtime dependencies:**
- `next`: `"14.2.x"` — stable Next.js 14 LTS release
- `react`: `"^18"` — React 18 (required by Next.js 14)
- `react-dom`: `"^18"` — React DOM
- `leaflet`: `"^1.9"` — Leaflet map library
- `react-leaflet`: `"^4.2"` — React wrapper for Leaflet

**Dev dependencies:**
- `typescript`: `"^5"` — TypeScript compiler
- `@types/react`: `"^18"` — React TypeScript types
- `@types/react-dom`: `"^18"` — React DOM TypeScript types
- `@types/node`: `"^20"` — Node.js TypeScript types
- `@types/leaflet`: `"^1.9"` — Leaflet TypeScript types
- `tailwindcss`: `"^3.4"` — Tailwind CSS
- `postcss`: `"^8"` — PostCSS (required by Tailwind)
- `autoprefixer`: `"^10"` — Autoprefixer (required by Tailwind)
- `eslint`: `"^8"` — Linter
- `eslint-config-next`: `"14.2.x"` — Next.js ESLint config
- `jest`: `"^29"` — Test runner
- `jest-environment-jsdom`: `"^29"` — JSDOM for component tests
- `@testing-library/react`: `"^14"` — React Testing Library
- `@testing-library/jest-dom`: `"^6"` — Custom DOM matchers
- `@testing-library/user-event`: `"^14"` — User event simulation

**Scripts:**
```json
{
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "next lint",
  "test": "jest --passWithNoTests"
}
```

**Note:** Recharts is deliberately omitted (decision 17). The five
risk sub-score bars and fleet-match comparison use Tailwind CSS bars.

#### B — tsconfig.json

Create `src/frontend/tsconfig.json` using the standard Next.js 14
TypeScript configuration:
- `"target": "ES2017"`
- `"lib": ["dom", "dom.iterable", "esnext"]`
- `"allowJs": true`
- `"skipLibCheck": true`
- `"strict": true`
- `"forceConsistentCasingInFileNames": true`
- `"noEmit": true`
- `"esModuleInterop": true`
- `"module": "esnext"`
- `"moduleResolution": "bundler"`
- `"resolveJsonModule": true`
- `"isolatedModules": true`
- `"jsx": "preserve"`
- `"incremental": true`
- `"plugins": [{"name": "next"}]`
- `"paths": {"@/*": ["./*"]}`
- `include: ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"]`
- `exclude: ["node_modules"]`

#### C — next.config.ts

Create `src/frontend/next.config.ts` — minimal configuration:
- No special plugins
- No `images.domains` (no remote images used)
- Export a `NextConfig` object

#### D — Tailwind setup

Create `src/frontend/tailwind.config.ts`:
- `content`: `["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./maps/**/*.{ts,tsx}"]`
- No custom theme extensions needed for the hackathon

Create `src/frontend/postcss.config.js`:
- Standard PostCSS config: `tailwindcss` + `autoprefixer` plugins

#### E — Jest setup

Create `src/frontend/jest.config.ts`:
- `testEnvironment: "jsdom"`
- `setupFilesAfterFramework: ["<rootDir>/jest.setup.ts"]`
- `moduleNameMapper` for CSS imports (map `\.css$` to `identity-obj-proxy`)
- Transform TypeScript with `next/jest` transformer

Create `src/frontend/jest.setup.ts`:
- Import `@testing-library/jest-dom`

Install dev dependency: `identity-obj-proxy` (for CSS module mocking in Jest)

#### F — ESLint

Create `src/frontend/.eslintrc.json`:
- `extends: ["next/core-web-vitals"]`

#### G — .gitkeep removal

The following `.gitkeep` files will be replaced by real files and can be
deleted as their directories gain real content:
- `src/frontend/app/.gitkeep`
- `src/frontend/components/.gitkeep`
- `src/frontend/maps/.gitkeep`
- `src/frontend/services/.gitkeep`
- `src/frontend/public/.gitkeep` — keep until a real asset is added

### Relevant Context
- `src/frontend/` currently contains only 5 `.gitkeep` files
- `.gitignore` already ignores `node_modules/`, `.next/`
- `docs/setup-guide.md` specifies `cd src/frontend && npm run dev`
- `docs/architecture.md` names Next.js 14, TypeScript, Tailwind CSS

### Status
[ ] pending

---

## Phase 2 — TypeScript Type Contracts (services/types.ts)

### Intent
Define all TypeScript interfaces that mirror the actual Pydantic backend
response schemas. This is the single source of truth for all type
information in the frontend. No field may be invented; every field must
exist in a confirmed Pydantic model.

### Expected Outcomes
- `src/frontend/services/types.ts` compiles with zero TypeScript errors
- Every API response used in the UI has a corresponding TypeScript interface
- The score scale comment is encoded in the file (total_score 0–100 vs
  current_risk_score 0–1)
- All nullable fields from the Pydantic models are `| null` in TypeScript

### Todo List

#### Interfaces to define (in order)

**From `schemas/shipment.py` → `ShipmentResponse`:**
```
interface Shipment {
  id: string
  tracking_number: string | null
  origin: string
  destination: string
  cargo_type: string
  cargo_category: string
  required_temp_min_c: number
  required_temp_max_c: number
  status: string
  assigned_vehicle_id: string | null
  carrier_id: string | null
  estimated_departure: string | null   // ISO datetime
  estimated_arrival: string | null
  current_risk_score: number | null    // 0–1 DB field — NOT the engine score
  current_lat: number | null
  current_lon: number | null
  current_location_name: string | null
}
```

**From `schemas/engine_responses.py` → `ShipmentRiskResponse`:**
```
interface ShipmentRisk {
  shipment_id: string
  total_score: number           // 0–100 ENGINE SCALE — use for risk gauge
  severity: RiskSeverity        // 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  r_disruption: number          // 0–1
  r_weather: number             // 0–1
  r_route: number               // 0–1
  r_cold_chain: number          // 0–1
  r_business: number            // 0–1
  contributing_disruption_ids: string[]
  weather_fallback: boolean
  cold_chain_fallback: boolean
  route_fallback: boolean
  assessed_at: string
}
type RiskSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
```

**From `schemas/engine_responses.py` → `ColdChainResponse`:**
```
interface ColdChainStatus {
  shipment_id: string
  telemetry_id: string | null
  cargo_rule_found: boolean
  is_in_excursion: boolean
  is_destructive: boolean
  cargo_temp_c: number | null
  allowed_min_c: number | null
  allowed_max_c: number | null
  max_allowable_excursion_temp_c: number | null
  deviation_c: number | null          // signed: positive=too warm, negative=too cold
  severity: ColdChainSeverity
  excursion_duration_minutes: number | null
  compliance_standard: string | null
  cargo_category: string
  grade: string | null
  assessed_at: string
}
type ColdChainSeverity = 'OK' | 'WARNING' | 'HIGH' | 'CRITICAL' | 'UNKNOWN'
```

**From `schemas/engine_responses.py` → `RouteScoreResponse` + `RouteOptimizerResponse`:**
```
interface RouteScore {
  route_id: string
  route_name: string
  total_score: number          // 0–1
  eta_hours: number
  eta_factor: number
  cost_factor: number
  disruption_factor: number
  weather_factor: number
  cold_chain_factor: number
  recommended: boolean
  warnings: string[]
}
interface RouteRecommendation {
  shipment_id: string
  scored_routes: RouteScore[]
  no_route_found: boolean
  assessed_at: string
}
```

**From `schemas/engine_responses.py` → `FleetMatchScoreResponse` + `FleetMatchResponse`:**
```
interface FleetMatchScore {
  asset_id: string
  vehicle_type: string
  cooling_capability: CoolingCapability
  total_score: number          // 0–1
  proximity_km: number | null
  proximity_score: number
  cargo_compat_score: number
  refrigeration_score: number
  capacity_score: number
  availability_score: number
  estimated_shipment_weight_kg: number
  asset_capacity_kg: number
  recommended: boolean
}
type CoolingCapability = 'ULTRA_COLD' | 'STANDARD_COLD' | 'AMBIENT'
interface FleetMatch {
  shipment_id: string
  scored_assets: FleetMatchScore[]
  no_asset_found: boolean
  assessed_at: string
}
```

**From `schemas/disruption.py` → `DisruptionResponse`:**
```
interface Disruption {
  id: string
  type: string
  severity: string
  title: string
  affected_corridor: string | null
  start_time: string
  expected_end_time: string | null
  impact_delay_hours: number | null
  recommended_reroute: string | null
  geometry_lat: number | null
  geometry_lon: number | null
}
```

**From `schemas/engine_responses.py` → `DisruptionImpactResponse`:**
```
interface DisruptionImpact {
  disruption_id: string
  disruption_type: string
  disruption_severity: string
  proximity_radius_km: number
  affected_shipments: AffectedShipment[]
  assessed_at: string
}
interface AffectedShipment {
  shipment_id: string
  shipment_status: string
  distance_km: number
}
```

**From `schemas/fleet_asset.py` → `FleetAssetResponse`:**
```
interface FleetAsset {
  id: string
  vehicle_type: string
  license_plate: string | null
  status: string
  fuel_type: string | null
  cooling_system_type: string | null
  capacity_kg: number
  battery_charge_percent: number | null
  fuel_level_percent: number | null
  driver_name: string | null
  telemetry_stream_id: string | null
  current_lat: number | null
  current_lon: number | null
}
```

**From `schemas/route.py` → `RouteResponse`:**
```
interface RouteWaypoint {
  name: string
  lat: number
  lon: number
}
interface ColdStorageDepot {
  name: string
  lat: number
  lon: number
}
interface RouteData {
  route_id: string
  name: string
  origin: string
  destination: string
  distance_km: number
  typical_duration_hours: number
  highways: string[] | null
  waypoints: RouteWaypoint[] | null
  cold_storage_depots: ColdStorageDepot[] | null
}
```

**From `schemas/ai_response.py` → `AIExplanationResponse`:**
```
interface AIExplanation {
  use_case: string
  entity_id: string
  headline: string
  explanation: string
  recommended_action: string
  severity: string
  ai_generated: boolean
  model_id: string | null
  generated_at: string
}
```

**From `/health`:**
```
interface HealthResponse {
  status: string
  timestamp: string
}
```

**Carrier display-only lookup (no backend endpoint):**
```
// Display metadata only — not business logic
const CARRIER_NAMES: Record<string, string> = {
  'CRR-401': 'FrostLine Logistics',
  'CRR-402': 'Apex Cargo Transporters',
  'CRR-403': 'Cascade Frozen Freight',
}
```

### Relevant Context
- `src/backend/schemas/shipment.py` — ShipmentBase → ShipmentResponse
- `src/backend/schemas/engine_responses.py` — ShipmentRiskResponse,
  ColdChainResponse, RouteOptimizerResponse, RouteScoreResponse,
  FleetMatchResponse, FleetMatchScoreResponse, DisruptionImpactResponse
- `src/backend/schemas/disruption.py` — DisruptionResponse
- `src/backend/schemas/fleet_asset.py` — FleetAssetResponse
- `src/backend/schemas/route.py` — RouteResponse
- `src/backend/schemas/ai_response.py` — AIExplanationResponse
- Score scale rule: `ShipmentRisk.total_score` is 0–100 (MD-09)

### Status
[ ] pending

---

## Phase 3 — Typed API Client (services/api.ts)

### Intent
Create a single typed fetch client that wraps all FastAPI endpoints used
by the UI. This is the only place in the frontend that constructs fetch
URLs. All components call functions from this module — no component
constructs its own fetch URL.

### Expected Outcomes
- `src/frontend/services/api.ts` compiles with zero TypeScript errors
- Every used endpoint has a typed function
- `BASE_URL` reads from `process.env.NEXT_PUBLIC_API_URL` with a fallback
  to `'http://localhost:8000'`
- A custom `ApiError` class carries HTTP status + body text
- No retry logic (single attempt; error surfaces to caller)
- No `axios`, no `react-query`

### Todo List

#### A — ApiError class

```typescript
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}
```

#### B — apiFetch generic helper

```typescript
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`
  const res = await fetch(url, options)
  if (!res.ok) {
    const text = await res.text()
    throw new ApiError(res.status, text)
  }
  return res.json() as Promise<T>
}
```

#### C — Endpoint functions (all using confirmed Pydantic shapes)

```typescript
export const api = {
  // Health
  checkHealth: () =>
    apiFetch<HealthResponse>('/health'),

  // Shipments
  getShipments: () =>
    apiFetch<Shipment[]>('/api/shipments/'),
  getShipment: (id: string) =>
    apiFetch<Shipment>(`/api/shipments/${id}`),
  getShipmentRisk: (id: string) =>
    apiFetch<ShipmentRisk>(`/api/shipments/${id}/risk`),
  getShipmentColdChain: (id: string) =>
    apiFetch<ColdChainStatus>(`/api/shipments/${id}/cold-chain`),
  getShipmentRoutes: (id: string) =>
    apiFetch<RouteRecommendation>(`/api/shipments/${id}/routes`),
  getShipmentFleetMatch: (id: string) =>
    apiFetch<FleetMatch>(`/api/shipments/${id}/fleet-match`),

  // Risk batch
  getActiveRisk: () =>
    apiFetch<ShipmentRisk[]>('/api/risk/active'),

  // Disruptions
  getDisruptions: () =>
    apiFetch<Disruption[]>('/api/disruptions/'),
  getDisruptionImpact: (id: string) =>
    apiFetch<DisruptionImpact>(`/api/disruptions/${id}/affected-shipments`),

  // Fleet
  getFleetAssets: () =>
    apiFetch<FleetAsset[]>('/api/fleet/'),

  // Routes catalog
  getRoutes: () =>
    apiFetch<RouteData[]>('/api/routes/'),

  // AI explain
  explainShipmentRisk: (entityId: string) =>
    apiFetch<AIExplanation>('/api/explain/shipment-risk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entity_id: entityId, use_case: 'shipment_risk' }),
    }),
  explainDisruptionImpact: (entityId: string) =>
    apiFetch<AIExplanation>('/api/explain/disruption-impact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entity_id: entityId, use_case: 'disruption_impact' }),
    }),
}
```

### Relevant Context
- `src/.env.example` — `NEXT_PUBLIC_API_URL=http://localhost:8000`
- `src/backend/main.py` — CORS wildcard `allow_origins=["*"]` in dev
- `src/backend/api/explain.py` — POST body is `{entity_id, use_case}`

### Status
[ ] pending

---

## Phase 4 — Shared Primitive Components

### Intent
Build the small, stateless, reusable UI primitives that all larger
components depend on. These have no API calls or state — only props-in,
JSX-out. Building them first lets every subsequent phase use them
consistently.

### Expected Outcomes
- `SeverityBadge`, `StatusBadge`, `LoadingSpinner`, `ErrorBanner` exist
- All follow the severity/status color table defined in this plan
- Color is never the only differentiator (text label always present)
- Each has `aria-label` for accessibility

### Todo List

#### A — SeverityBadge (components/SeverityBadge.tsx)

Props: `{ severity: string; size?: 'sm' | 'md' }`

Severity → Tailwind classes mapping (from plan color table):
- CRITICAL → `bg-red-600 text-white`
- HIGH → `bg-orange-500 text-white`
- MEDIUM → `bg-yellow-400 text-gray-900`
- LOW → `bg-green-600 text-white`
- OK → `bg-green-500 text-white`
- WARNING → `bg-amber-500 text-white`
- UNKNOWN (default) → `bg-gray-400 text-white`

Design: uppercase pill, rounded-full, bold, compact padding.
Includes `aria-label={Severity: ${severity}}`.

#### B — StatusBadge (components/StatusBadge.tsx)

Props: `{ status: string }`

Status → Tailwind classes:
- IDLE → `bg-green-600 text-white`
- ACTIVE → `bg-blue-500 text-white`
- EN_ROUTE → `bg-purple-500 text-white`
- ALERT_DISRUPTION → `bg-red-600 text-white`
- IN_TRANSIT → `bg-blue-400 text-white`
- default → `bg-gray-400 text-white`

#### C — LoadingSpinner (components/LoadingSpinner.tsx)

Props: `{ label?: string }`
A Tailwind CSS animated spinner (border-based spin animation).
Includes `role="status"` and `aria-label`.

Used as: panel-level loading state while API calls are in-flight.

#### D — ErrorBanner (components/ErrorBanner.tsx)

Props: `{ message: string; onRetry?: () => void }`
Red banner with warning icon, message text, and optional retry button.
Uses `role="alert"`.

Scenarios:
- Backend offline: "Backend unavailable — start FastAPI on port 8000"
- 404: "Entity not found: {id}"
- Generic: displays the error message string

### Relevant Context
- Severity values confirmed from:
  `src/backend/risk_engine/scorer.py` (RiskSeverity enum)
  `src/backend/cold_chain/rules.py` (ColdChainSeverity enum)
  `src/backend/schemas/disruption.py` (severity string field)

### Status
[ ] pending

---

## Phase 5 — Shipment Panels

### Intent
Build all components needed to display a selected shipment's full
operational picture: risk score, five sub-scores, cold-chain status,
route recommendation, and fleet rescue recommendation.

These panels are populated by the parallel fetch triggered when a
shipment is selected from the roster.

### Expected Outcomes
- `ShipmentRoster` renders all shipments from `GET /api/shipments/`
  with severity badges from `GET /api/risk/active`
- Clicking a row sets the selected shipment and triggers the parallel fetch
- `ShipmentDetailPanel` shows full risk data when loaded
- `ColdChainPanel` correctly renders excursion state + deviation
- `RoutePanel` correctly renders `no_route_found: true` state without
  presenting it as an error
- `FleetMatchPanel` correctly renders `no_asset_found: true` state
- SHP-1002 is pre-selected on initial load (decision 15)

### Todo List

#### A — RiskScoreGauge (components/RiskScoreGauge.tsx)

Props: `{ score: number; severity: RiskSeverity }`

Displays the 0–100 risk score (ALWAYS from `ShipmentRisk.total_score`).
Visual: large number + Tailwind bar (width = `${score}%`).
Bar color follows severity color table.
Explicit comment in code: "score is 0–100 from engine endpoint".

**Do NOT accept current_risk_score (0–1) as a prop.**

#### B — SubScoreBar (components/SubScoreBar.tsx)

Props: `{ label: string; value: number; fallback?: boolean }`

`value` is a 0–1 sub-score. Bar width = `${value * 100}%`.
Label maps: `r_disruption` → "Disruption", `r_weather` → "Weather",
`r_route` → "Route", `r_cold_chain` → "Cold Chain", `r_business` → "Business".
If `fallback` is true, shows a small "ⓘ estimated" annotation.

Color: fixed blue gradient (`bg-blue-500`). Severity-derived colors
apply to `SeverityBadge`, not these bars.

#### C — ShipmentRoster (components/ShipmentRoster.tsx)

Props:
```typescript
{
  shipments: Shipment[]
  activeRisks: Map<string, ShipmentRisk>
  selectedId: string | null
  onSelect: (id: string) => void
}
```

Renders a table/card list with: ID, cargo_type, origin→destination,
status badge (StatusBadge), and severity badge (SeverityBadge — from
activeRisks map; UNKNOWN if not yet loaded).

SHP-1002 row has `bg-red-50` highlight when it is the highest-severity
shipment. Selected row gets `ring-2 ring-blue-500`.

`onSelect` is called on row click.

**Note:** `Shipment.current_risk_score` (0–1) is NOT displayed in this
component. It is used nowhere in the UI.

#### D — ColdChainPanel (components/ColdChainPanel.tsx)

Props: `{ data: ColdChainStatus | null; loading: boolean }`

When `loading`: shows `LoadingSpinner`.
When `data` is null and not loading: shows empty state.

Key display elements:
- `SeverityBadge` for `data.severity`
- `is_in_excursion` → green "Within Spec" or red "EXCURSION ACTIVE" banner
- `is_destructive` → yellow "⚠ Destructive Threshold" warning
- `cargo_temp_c` vs `allowed_min_c`/`allowed_max_c` (display as range)
- `deviation_c` (signed: "+" too warm, "−" too cold; "N/A" if null)
- `compliance_standard` (e.g., "FDA HACCP Seafood Guidelines")
- `grade` label
- If `cargo_rule_found: false` → "No cargo rule configured for this
  cargo category" empty state

#### E — RoutePanel (components/RoutePanel.tsx)

Props: `{ data: RouteRecommendation | null; loading: boolean }`

When `loading`: shows `LoadingSpinner`.
When `data` is null and not loading: shows empty state.

Key display elements:
- If `no_route_found: true`: "No route match found for this shipment
  corridor. The route optimizer requires an exact origin/destination
  match." — no error styling, just an informational empty state.
- If routes exist: cards for each `RouteScore` in `scored_routes`,
  sorted by `total_score` descending (already sorted by backend).
  Each card shows:
  - route_name
  - `recommended` → green "⭐ Recommended" badge
  - `total_score` as percentage (value × 100, one decimal place)
  - `eta_hours` in hours
  - `disruption_factor` bar (mini)
  - `weather_factor` bar (mini)
  - `warnings[]` — each shown as a yellow warning pill

**Decision 20/21:** `no_route_found` is represented honestly. The
general `/api/routes/` catalog is NOT presented as a recommendation.

#### F — FleetMatchPanel (components/FleetMatchPanel.tsx)

Props: `{ data: FleetMatch | null; loading: boolean }`

When `loading`: shows `LoadingSpinner`.
When `data` is null: shows empty state.

Key display elements:
- If `no_asset_found: true`: "No alternative fleet assets available
  for this shipment." — informational empty state.
- If assets exist: cards for each `FleetMatchScore` in `scored_assets`.
  Each card shows:
  - asset_id, vehicle_type
  - `recommended` → green "⭐ Top Match" badge
  - `cooling_capability` badge (ULTRA_COLD/STANDARD_COLD/AMBIENT)
  - `total_score` as percentage
  - `proximity_km` (e.g., "245 km" or "N/A" if null)
  - mini bars for `cargo_compat_score`, `refrigeration_score`

#### G — ShipmentDetailPanel (components/ShipmentDetailPanel.tsx)

Props:
```typescript
{
  shipment: Shipment | null
  risk: ShipmentRisk | null
  coldChain: ColdChainStatus | null
  routes: RouteRecommendation | null
  fleetMatch: FleetMatch | null
  loading: boolean
  onRequestAIBrief: () => void
}
```

When `loading`: panel-wide LoadingSpinner.
When `shipment` is null: "Select a shipment to view details."

Assembles:
- Shipment metadata (cargo_type, origin→destination, ETA, carrier display
  using the CARRIER_NAMES lookup)
- `RiskScoreGauge` (from `risk.total_score`)
- `SeverityBadge` (from `risk.severity`)
- 5× `SubScoreBar` for each r_* field
  (passes `fallback=true` if the corresponding `*_fallback` flag is set)
- `contributing_disruption_ids` list
- `ColdChainPanel`
- `RoutePanel`
- `FleetMatchPanel`
- "Get AI Brief" button (calls `onRequestAIBrief`)

### Relevant Context
- `src/backend/schemas/engine_responses.py` — all five response types
- Scale rule: `ShipmentRisk.total_score` 0–100; `r_*` 0–1
- SHP-1002 fixture: status ALERT_DISRUPTION, cargo_temp -17.2°C (deviation +2.8°C)
- `src/data/fleet.json` — FLT-302 (ACTIVE), FLT-109 (ACTIVE), FLT-514 (ACTIVE)

### Status
[ ] pending

---

## Phase 6 — Disruption Panels

### Intent
Build the disruption monitor (list view) and disruption impact panel
(detail view showing affected shipments within the disruption radius).
These are independent from the shipment-selection flow.

### Expected Outcomes
- `DisruptionMonitor` renders all three disruptions with severity badges
- Clicking a disruption card fetches and displays impact data
- Impact panel shows affected shipments with distance_km
- Empty state for zero affected shipments is clear and non-alarming

### Todo List

#### A — DisruptionMonitor (components/DisruptionMonitor.tsx)

Props:
```typescript
{
  disruptions: Disruption[]
  selectedId: string | null
  onSelect: (id: string) => void
}
```

Renders a list of cards. Each card shows:
- `id`, `type`, `title`
- `SeverityBadge` for `severity`
- `affected_corridor` (or "—" if null)
- `impact_delay_hours` ("+X hr delay" or "—")
- `recommended_reroute` (small italic text or "—")
- `start_time` → `expected_end_time` time range

Selected card gets `ring-2 ring-blue-500` highlight.
Sorted by severity: CRITICAL first, then HIGH, MEDIUM, LOW.

#### B — DisruptionImpactPanel (components/DisruptionImpactPanel.tsx)

Props:
```typescript
{
  disruption: Disruption | null
  impact: DisruptionImpact | null
  loading: boolean
  onRequestAIBrief: () => void
}
```

When loading: `LoadingSpinner`.
When no disruption selected: "Select a disruption to view impact."

Shows:
- Disruption title + severity badge
- `proximity_radius_km` ("Impact radius: X km")
- `affected_shipments` list:
  - Each row: shipment_id, shipment_status badge, distance_km
  - If empty: "No active shipments within the X km impact radius."
- "Get AI Brief" button (calls `onRequestAIBrief`)

### Relevant Context
- `src/backend/api/disruptions.py` — affected-shipments endpoint
- `src/data/disruptions.json` — 3 disruptions, all with geometry_lat/lon
- DIS-501 (SEVERE_WEATHER HIGH) radius = 200 km
- DIS-503 (PORT_CONTAINER_HOLD CRITICAL) radius = 50 km
- DIS-502 (ROADWORK_CONGESTION MEDIUM) radius = 30 km

### Status
[ ] pending

---

## Phase 7 — AI Brief Panel

### Intent
Build the AI brief panel that displays the output of
`POST /api/explain/shipment-risk` or `POST /api/explain/disruption-impact`.
This panel must make the Granite AI contribution explicitly visible:
ai_generated=true vs ai_generated=false must be distinctly styled,
and model_id must be shown when available.

### Expected Outcomes
- Live Granite output shows green `🤖 IBM Granite` badge + model_id
- Deterministic fallback shows gray `⚙️ Deterministic Fallback` badge
- Both states render identically in terms of layout (headline, explanation, action)
- Neither state shows an error — both are valid operational outcomes
- Loading state shows skeleton content

### Todo List

#### A — AIBriefPanel (components/AIBriefPanel.tsx)

Props:
```typescript
{
  explanation: AIExplanation | null
  loading: boolean
  onRequest: () => void
  entityId: string | null
}
```

States:
1. **No entity selected** (`entityId` null): "Select a shipment or
   disruption and click 'Get AI Brief' to generate an operational summary."
2. **Not yet requested** (explanation null, loading false): "Get AI Brief"
   button with IBM/AI icon
3. **Loading** (loading true): skeleton with three lines (headline,
   explanation, action) animated with Tailwind `animate-pulse`
4. **Live Granite** (ai_generated true):
   ```
   [Green badge] 🤖 IBM Granite  [model_id in small gray text]
   [SeverityBadge for severity]
   ─────────────────────────────
   [headline — bold, 18px]
   
   Situation Analysis
   [explanation — body text]
   
   Dispatcher Action
   [recommended_action — highlighted box]
   
   Generated: [generated_at formatted as local time]
   ```
5. **Deterministic fallback** (ai_generated false):
   Same layout but with gray `⚙️ Deterministic Fallback` badge.
   `model_id` is null and not shown.

**Critical:** `severity` in `AIExplanation` always comes from the engine
(set by the backend). The UI displays it as-is — never overrides it.

#### B — AI badge helper

```typescript
function AIBadge({ aiGenerated, modelId }: { aiGenerated: boolean; modelId: string | null }) {
  if (aiGenerated) {
    return (
      <div className="bg-green-700 text-white ...">
        🤖 IBM Granite
        {modelId && <span className="ml-2 text-xs text-green-200">{modelId}</span>}
      </div>
    )
  }
  return (
    <div className="bg-gray-500 text-white ...">
      ⚙️ Deterministic Fallback
    </div>
  )
}
```

### Relevant Context
- `src/backend/schemas/ai_response.py` — AIExplanationResponse
- `src/backend/ai/fallback.py` — all five fallback builders
- `src/backend/ai/watsonx_service.py` — ai_generated=True only when
  ModelInference succeeds and response passes 6-step validation

### Status
[ ] pending

---

## Phase 8 — Leaflet Map (maps/ControlTowerMap.tsx)

### Intent
Build an operational Leaflet map showing shipment positions, disruption
zones, and route waypoints. The map must be loaded client-side only
(ssr: false) because Leaflet requires browser APIs.

All coordinates come exclusively from API responses — no invented values.

### Expected Outcomes
- Map renders correctly in the browser using OpenStreetMap tiles
- Three shipment markers (colored by severity) appear at their
  `current_lat`/`current_lon` positions
- Three disruption markers appear at `geometry_lat`/`geometry_lon`
- Disruption radius circles use `proximity_radius_km` from
  `DisruptionImpactResponse` (fetched per disruption)
- Route polylines render for routes with waypoints (from `GET /api/routes/`)
- Map does NOT require any API token
- No SSR errors (loaded via `next/dynamic` with `ssr: false`)

### Todo List

#### A — Leaflet CSS import

In `app/globals.css` or in `app/layout.tsx`, import:
`import 'leaflet/dist/leaflet.css'`

This import must be in a file that is loaded on the client. The best
place is `app/globals.css` which is imported from `app/layout.tsx`.

#### B — Leaflet default icon fix

Leaflet's default marker icons break in webpack-bundled builds because
the PNG assets are not resolved correctly. The fix:

```typescript
import L from 'leaflet'
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})
```

This uses the official CDN URLs — no local asset copying needed.

#### C — ControlTowerMap component

Create `src/frontend/maps/ControlTowerMap.tsx` as `"use client"` component.

Props:
```typescript
interface ControlTowerMapProps {
  shipments: Shipment[]
  activeRisks: Map<string, ShipmentRisk>
  disruptions: Disruption[]
  disruptionImpacts: Map<string, DisruptionImpact>   // keyed by disruption.id
  routes: RouteData[]
  selectedShipmentId: string | null
  selectedDisruptionId: string | null
}
```

Map elements:

**Shipment markers:**
- Position: `current_lat`, `current_lon` (skip if either is null)
- Icon color: derived from `activeRisks.get(shipment.id)?.severity`
  using custom DivIcon with Tailwind-equivalent colors:
  CRITICAL → red, HIGH → orange, MEDIUM → yellow, LOW/default → green
- Popup: `id`, `cargo_type`, `current_location_name`, severity
- Selected shipment marker is slightly larger (icon size 30×45 vs 25×41)

**Disruption markers:**
- Position: `geometry_lat`, `geometry_lon` (skip if either is null)
- Custom icon: orange/red triangle or exclamation DivIcon
- Popup: `id`, `title`, `type`, `severity`

**Disruption radius circles:**
- For each disruption with geometry and a loaded impact response:
  `L.circle([geometry_lat, geometry_lon], { radius: proximity_radius_km * 1000 })`
  (Leaflet radius is in meters; `proximity_radius_km * 1000`)
- Color: red for CRITICAL/HIGH disruptions, orange for MEDIUM, yellow for LOW
- `fillOpacity: 0.05`, `weight: 2` — subtle visual only

**Route polylines:**
- For each `RouteData` with `waypoints`:
  Draw polyline through waypoint lat/lon pairs
- Color: blue, `weight: 3`, `opacity: 0.7`
- Cold storage depot markers: small blue square DivIcon

**Map configuration:**
- Default center: `[39.8283, -98.5795]` (geographic center of USA)
- Default zoom: 4 (shows all three shipment positions simultaneously)
- TileLayer: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`
  attribution: `© OpenStreetMap contributors`

#### D — Dynamic import in Dashboard

In `Dashboard.tsx` or `app/page.tsx`:
```typescript
const ControlTowerMap = dynamic(
  () => import('../maps/ControlTowerMap'),
  { ssr: false, loading: () => <LoadingSpinner label="Loading map..." /> }
)
```

### Relevant Context
- Shipment GPS: SHP-1001 (39.7817, -86.1477), SHP-1002 (45.5152, -122.6784),
  SHP-1003 (39.9526, -75.1652) — confirmed from `src/data/shipments.json`
- Disruption geometry: DIS-501 (47.4243, -121.4138), DIS-502 (39.5521, -86.0543),
  DIS-503 (40.6895, -74.1745) — confirmed from `src/data/disruptions.json`
- Route waypoints with lat/lon confirmed from `src/data/routes.json`
- Fleet `current_lat`/`current_lon` = null in seed data → fleet markers
  NOT required (decision 19)
- `docs/setup-guide.md` explicitly names Leaflet as the fallback

### Status
[ ] pending

---

## Phase 9 — Dashboard Orchestrator and Page Shell

### Intent
Build the top-level `Dashboard.tsx` client component (all state lives
here) and the Next.js page shell (`app/layout.tsx`, `app/page.tsx`,
`app/globals.css`). This phase wires all panels together and implements
the data-fetch lifecycle.

### Expected Outcomes
- `npm run dev` renders a fully functional SupplyGuard control-tower
  dashboard
- All five API calls on mount complete (shipments, active risk, disruptions,
  fleet, routes)
- SHP-1002 is pre-selected on load
- Selecting SHP-1002 triggers parallel fetch of risk, cold-chain, routes,
  fleet-match
- "Get AI Brief" button on shipment panel calls explainShipmentRisk
- "Get AI Brief" button on disruption panel calls explainDisruptionImpact
- Header shows backend health indicator (green dot when `/health` returns ok)
- All loading and error states render correctly
- Map shows on the right-hand side of the layout

### Todo List

#### A — app/globals.css

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

Plus Leaflet CSS import (must be in a client-loaded file):
`@import 'leaflet/dist/leaflet.css';`

#### B — app/layout.tsx

Server component (no "use client").
Standard Next.js root layout:
- `<html lang="en">`
- `<body>` with Tailwind base classes: `bg-gray-950 text-gray-100 min-h-screen`
- Imports `./globals.css`
- Metadata: `title: "SupplyGuard AI — Control Tower"`,
  `description: "Autonomous Supply Chain Disruption Intelligence"`

#### C — app/page.tsx

Server component. Renders `<Dashboard />`.

```typescript
import Dashboard from '@/components/Dashboard'
export default function Page() {
  return <Dashboard />
}
```

#### D — Header (components/Header.tsx)

Props: `{ backendHealthy: boolean; watsonxLive: boolean | null }`

Displays:
- "SupplyGuard AI" wordmark (bold white)
- "Control Tower" subtitle (gray)
- Backend health: green dot "API Online" / red dot "API Offline"
- Granite status: green "🤖 AI Live" if `watsonxLive === true`,
  gray "⚙️ AI Fallback" if `watsonxLive === false`,
  nothing if null (not yet known)

`watsonxLive` is determined from the first `AIExplanation` response
by reading `ai_generated`.

#### E — Dashboard (components/Dashboard.tsx)

This is the only `"use client"` component that holds top-level state.

**State:**
```typescript
// Loaded on mount
const [shipments, setShipments] = useState<Shipment[]>([])
const [activeRisks, setActiveRisks] = useState<Map<string, ShipmentRisk>>(new Map())
const [disruptions, setDisruptions] = useState<Disruption[]>([])
const [fleetAssets, setFleetAssets] = useState<FleetAsset[]>([])
const [routes, setRoutes] = useState<RouteData[]>([])
const [mountLoading, setMountLoading] = useState(true)
const [mountError, setMountError] = useState<string | null>(null)
const [backendHealthy, setBackendHealthy] = useState(true)

// Selection state
const [selectedShipmentId, setSelectedShipmentId] = useState<string | null>('SHP-1002')
const [selectedDisruptionId, setSelectedDisruptionId] = useState<string | null>(null)

// Per-selection detail (fetched on selection)
const [shipmentRisk, setShipmentRisk] = useState<ShipmentRisk | null>(null)
const [coldChain, setColdChain] = useState<ColdChainStatus | null>(null)
const [routeRec, setRouteRec] = useState<RouteRecommendation | null>(null)
const [fleetMatch, setFleetMatch] = useState<FleetMatch | null>(null)
const [detailLoading, setDetailLoading] = useState(false)

// Disruption impact
const [disruptionImpact, setDisruptionImpact] = useState<DisruptionImpact | null>(null)
const [disruptionImpacts, setDisruptionImpacts] = useState<Map<string, DisruptionImpact>>(new Map())
const [impactLoading, setImpactLoading] = useState(false)

// AI state
const [aiExplanation, setAiExplanation] = useState<AIExplanation | null>(null)
const [aiLoading, setAiLoading] = useState(false)
const [watsonxLive, setWatsonxLive] = useState<boolean | null>(null)
const [aiTarget, setAiTarget] = useState<'shipment' | 'disruption' | null>(null)
```

**Mount effect (on first render):**
```
1. api.checkHealth() → set backendHealthy
2. Promise.all([
     api.getShipments(),
     api.getActiveRisk(),
     api.getDisruptions(),
     api.getFleetAssets(),
     api.getRoutes(),
   ])
3. Build activeRisks Map from risk array
4. Pre-select SHP-1002:
   trigger handleSelectShipment('SHP-1002')
```

**handleSelectShipment(id):**
```
1. setSelectedShipmentId(id)
2. setDetailLoading(true)
3. setShipmentRisk/setColdChain/setRouteRec/setFleetMatch to null
4. Promise.all([
     api.getShipmentRisk(id),
     api.getShipmentColdChain(id),
     api.getShipmentRoutes(id),
     api.getShipmentFleetMatch(id),
   ])
5. Set all four state vars
6. setDetailLoading(false)
7. catch ApiError → set detailError
```

**handleSelectDisruption(id):**
```
1. setSelectedDisruptionId(id)
2. setImpactLoading(true)
3. api.getDisruptionImpact(id)
4. Store in disruptionImpacts Map
5. setImpactLoading(false)
```

**handleRequestAIBrief:**
```
1. setAiLoading(true)
2. setAiExplanation(null)
3. If aiTarget === 'shipment' and selectedShipmentId:
     api.explainShipmentRisk(selectedShipmentId)
   If aiTarget === 'disruption' and selectedDisruptionId:
     api.explainDisruptionImpact(selectedDisruptionId)
4. setAiExplanation(result)
5. setWatsonxLive(result.ai_generated)
6. setAiLoading(false)
7. catch → setAiExplanation error state
```

**Layout (responsive Tailwind grid):**

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER                                                          │
├──────────────────────────┬──────────────────────────────────────┤
│  SHIPMENT ROSTER         │  MAP (Leaflet)                        │
│  (left column)           │  (right column, fixed height h-80)   │
├──────────────────────────┤                                       │
│  DISRUPTION MONITOR      │                                       │
│  (left column)           │                                       │
├──────────────────────────┴──────────────────────────────────────┤
│  SHIPMENT DETAIL PANEL                                           │
│  [Risk Gauge] [5 Sub-score bars] [Cold Chain] [Route] [Fleet]   │
├─────────────────────────────────────────────────────────────────┤
│  DISRUPTION IMPACT PANEL                                         │
├─────────────────────────────────────────────────────────────────┤
│  AI BRIEF PANEL                                                  │
└─────────────────────────────────────────────────────────────────┘
```

Tailwind classes:
- Outer wrapper: `min-h-screen bg-gray-950 text-gray-100`
- Upper section: `grid grid-cols-1 lg:grid-cols-2 gap-4`
- Detail section: `mt-4 p-4 bg-gray-900 rounded-lg`
- Each panel: `bg-gray-900 rounded-lg p-4 border border-gray-800`

### Relevant Context
- `src/data/shipments.json` — SHP-1002 has ALERT_DISRUPTION status
- `src/backend/main.py` — lifespan initializes WatsonxService at startup
- All engine endpoints return 200 always (no_route_found and no_asset_found
  are valid outcomes, not errors)

### Status
[ ] pending

---

## Phase 10 — Frontend Tests

### Intent
Write a comprehensive test suite covering all critical behaviors without
requiring live IBM credentials, live watsonx, or a running backend.
All tests mock either `fetch` or the `services/api.ts` module.

### Expected Outcomes
- At minimum 10 test files
- At minimum 20 meaningful test cases
- All tests pass with `npm test` in `src/frontend/`
- No test calls a live network endpoint
- No test requires `WATSONX_APIKEY`, `WATSONX_PROJECT_ID`, or any secret

### Todo List

#### Test file inventory (minimum 10 files, ~25+ test cases)

**File 1: `__tests__/api.test.ts`** — API client unit tests

Tests:
- `getShipments` constructs correct URL and returns typed data
- `getShipmentRisk` constructs correct URL
- `explainShipmentRisk` sends correct POST body
  (`{ entity_id: 'SHP-1002', use_case: 'shipment_risk' }`)
- `apiFetch` throws `ApiError` with correct status on 404
- `apiFetch` throws `ApiError` on 500
- `BASE_URL` defaults to `http://localhost:8000` when env var unset

Mock approach: `jest.spyOn(global, 'fetch').mockResolvedValue(...)`

**File 2: `__tests__/SeverityBadge.test.tsx`** — Color and text

Tests:
- CRITICAL renders with `bg-red-600`
- HIGH renders with `bg-orange-500`
- MEDIUM renders with `bg-yellow-400`
- LOW renders with `bg-green-600`
- OK renders with `bg-green-500`
- Unknown/undefined severity renders gray fallback
- Text label matches severity value (never color-only)

**File 3: `__tests__/AIBriefPanel.test.tsx`** — AI live vs fallback badge

Tests:
- `ai_generated: true` renders `🤖 IBM Granite` text
- `ai_generated: true` renders `model_id` text
- `ai_generated: false` renders `⚙️ Deterministic Fallback` text
- `ai_generated: false` does NOT render model_id
- Loading state renders skeleton/spinner
- Null state renders "Select a shipment" prompt
- `headline`, `explanation`, `recommended_action` all render
- `severity` badge renders from `AIExplanation.severity`

**File 4: `__tests__/RiskScoreGauge.test.tsx`** — Scale correctness

Tests:
- Score 82.4 renders as `82.4` (not 8240, not 0.824)
- Score 0 renders as `0`
- Score 100 renders as `100`
- Severity `CRITICAL` applies correct CSS class
- **Scale invariant test**: passing `total_score=0.824` renders as `0.824`, not `82.4`
  (verifies the component does not multiply by 100 internally)

**File 5: `__tests__/SubScoreBar.test.tsx`** — Bar width

Tests:
- Value 0.92 renders bar width `92%` (or contains `92`)
- Value 0.0 renders minimal/zero bar
- `fallback: true` shows estimated annotation
- Label prop renders correctly

**File 6: `__tests__/ShipmentRoster.test.tsx`** — List rendering + selection

Tests:
- Renders correct number of shipment rows (3 with fixture data)
- Each row shows `id`, `cargo_type`
- `SeverityBadge` renders for each shipment with a known risk
- Clicking a row calls `onSelect` with the correct shipment ID
- Selected row has highlighted style
- UNKNOWN severity shown for shipments with no risk data

**File 7: `__tests__/ColdChainPanel.test.tsx`** — Excursion state

Tests:
- `is_in_excursion: true` renders "EXCURSION ACTIVE" or equivalent text
- `is_in_excursion: false` renders "Within Spec" or equivalent
- `is_destructive: true` renders destructive warning
- `deviation_c: 2.8` renders `+2.8` or `2.8`
- `deviation_c: -1.4` renders `-1.4`
- `cargo_rule_found: false` renders no-rule empty state
- `compliance_standard` text renders

**File 8: `__tests__/RoutePanel.test.tsx`** — Route states

Tests:
- `no_route_found: true` renders informational (not error) message
- Recommended route shows "Recommended" badge
- `eta_hours` renders
- `warnings` list renders each warning text
- Score renders as percentage

**File 9: `__tests__/FleetMatchPanel.test.tsx`** — Fleet states

Tests:
- `no_asset_found: true` renders informational message
- Recommended asset shows "Top Match" badge
- `cooling_capability` renders
- `proximity_km: null` renders "N/A" or equivalent
- `total_score` renders as percentage

**File 10: `__tests__/DisruptionMonitor.test.tsx`** — Disruption rendering

Tests:
- Renders correct disruption count (3)
- Each disruption shows `title`
- Severity badges render
- `affected_corridor` renders
- Clicking a disruption calls `onSelect`

**File 11: `__tests__/ErrorBanner.test.tsx`** — Error states

Tests:
- Renders error message text
- `onRetry` callback invoked when retry button clicked
- `role="alert"` present

**File 12: `__tests__/Dashboard.test.tsx`** — Integration

Tests (mocking entire `services/api.ts` module):
- Dashboard fetches shipments on mount
- SHP-1002 is selected after initial load
- Selecting a different shipment triggers detail fetch
- "Get AI Brief" button calls `explainShipmentRisk` with correct ID
- `ai_generated: false` response renders fallback badge (no error)
- Backend error renders `ErrorBanner`

#### Test fixture helpers

Create `__tests__/fixtures.ts` with typed fixture data matching real
Pydantic shapes:
- `mockShipment(overrides?)` — returns SHP-1002-like `Shipment`
- `mockShipmentRisk(overrides?)` — total_score=82.4, CRITICAL
- `mockColdChain(overrides?)` — is_in_excursion=true, deviation_c=2.8
- `mockAIExplanation(aiGenerated: boolean)` — live or fallback

### Relevant Context
- `src/backend/schemas/` — all Pydantic shapes define the mock contract
- `src/data/shipments.json` — SHP-1002 is the reference demo scenario

### Status
[ ] pending

---

## Phase 11 — Final Validation

### Intent
Verify that the complete Step 6 implementation meets all acceptance
criteria before marking Step 6 complete.

### Expected Outcomes
- `npm run build` passes with zero TypeScript errors, zero Tailwind errors
- `npm run lint` passes with zero ESLint errors
- `npm test` passes with ≥10 test files and ≥20 test cases
- `npm run dev` loads the dashboard; SHP-1002 is pre-selected; AI brief
  renders (live or fallback)
- `pytest src/tests/ -v` still passes all 237 Python tests (unchanged)
- No `WATSONX_*` variables referenced in any frontend file
- No `NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN` present in `src/.env.example`
- Map renders at correct latitude/longitude positions
- Risk gauge displays `total_score` from engine endpoint (0–100), not
  `current_risk_score` (0–1)

### Todo List

- [ ] Run `npm run build` inside `src/frontend/`; fix any TypeScript errors
- [ ] Run `npm run lint`; fix any ESLint warnings
- [ ] Run `npm test`; confirm ≥10 files and ≥20 assertions pass
- [ ] Run `pytest src/tests/ -v`; confirm all 237 still pass (0 new failures)
- [ ] Grep `src/frontend/` for `WATSONX`; confirm zero matches
- [ ] Grep `src/frontend/` for `mapbox`; confirm zero matches
- [ ] Manual browser check: open http://localhost:3000; verify SHP-1002 pre-selected
- [ ] Manual AI brief test: click "Get AI Brief" for SHP-1002;
      verify `ai_generated` badge renders correctly
- [ ] Grep `src/backend/` for any changes; confirm zero lines modified

### Relevant Context
- All 237 Python tests are in `src/tests/`
- Backend test command: `pytest src/tests/ -v` from repository root
- Frontend test command: `npm test` from `src/frontend/`

### Status
[ ] pending

---

## Summary of Files Changed / Created

### Files CREATED (all new)

**Root of `src/frontend/`:**
- `package.json`
- `tsconfig.json`
- `next.config.ts`
- `tailwind.config.ts`
- `postcss.config.js`
- `jest.config.ts`
- `jest.setup.ts`
- `.eslintrc.json`

**`app/`:**
- `app/layout.tsx`
- `app/page.tsx`
- `app/globals.css`

**`components/`:**
- `components/Header.tsx`
- `components/Dashboard.tsx`
- `components/ShipmentRoster.tsx`
- `components/ShipmentDetailPanel.tsx`
- `components/SeverityBadge.tsx`
- `components/StatusBadge.tsx`
- `components/RiskScoreGauge.tsx`
- `components/SubScoreBar.tsx`
- `components/ColdChainPanel.tsx`
- `components/RoutePanel.tsx`
- `components/FleetMatchPanel.tsx`
- `components/DisruptionMonitor.tsx`
- `components/DisruptionImpactPanel.tsx`
- `components/AIBriefPanel.tsx`
- `components/LoadingSpinner.tsx`
- `components/ErrorBanner.tsx`

**`maps/`:**
- `maps/ControlTowerMap.tsx`

**`services/`:**
- `services/types.ts`
- `services/api.ts`

**`__tests__/`:**
- `__tests__/fixtures.ts`
- `__tests__/api.test.ts`
- `__tests__/SeverityBadge.test.tsx`
- `__tests__/AIBriefPanel.test.tsx`
- `__tests__/RiskScoreGauge.test.tsx`
- `__tests__/SubScoreBar.test.tsx`
- `__tests__/ShipmentRoster.test.tsx`
- `__tests__/ColdChainPanel.test.tsx`
- `__tests__/RoutePanel.test.tsx`
- `__tests__/FleetMatchPanel.test.tsx`
- `__tests__/DisruptionMonitor.test.tsx`
- `__tests__/ErrorBanner.test.tsx`
- `__tests__/Dashboard.test.tsx`

**`.gitkeep` files deleted** (as real files replace their directories):
- `src/frontend/app/.gitkeep`
- `src/frontend/components/.gitkeep`
- `src/frontend/maps/.gitkeep`
- `src/frontend/services/.gitkeep`

### Files MODIFIED

- `src/.env.example` — remove one line: `NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN=...`

### Files EXPLICITLY FORBIDDEN FROM MODIFICATION

The following files must not be touched in Step 6:

**All Step 2 engine files:**
- `src/backend/risk_engine/scorer.py`
- `src/backend/risk_engine/sub_scores.py`
- `src/backend/risk_engine/haversine.py`
- `src/backend/cold_chain/engine.py`
- `src/backend/cold_chain/rules.py`
- `src/backend/optimizer/route_optimizer.py`
- `src/backend/optimizer/fleet_matcher.py`
- `src/backend/optimizer/normalizer.py`

**All Step 3 router files:**
- `src/backend/api/shipments.py`
- `src/backend/api/disruptions.py`
- `src/backend/api/fleet.py`
- `src/backend/api/routes.py`
- `src/backend/api/risk.py`
- `src/backend/api/explain.py`
- `src/backend/main.py`

**All Step 4 AI files:**
- `src/backend/ai/watsonx_service.py`
- `src/backend/ai/evidence_builder.py`
- `src/backend/ai/fallback.py`

**All Step 5 MCP files:**
- `src/mcp/server.py`
- `src/mcp/tools/`
- `src/mcp/client.py`
- `.bob/mcp.json`

**All schemas:**
- `src/backend/schemas/` (all files)

**All data fixtures:**
- `src/data/` (all JSON files)

**All existing tests:**
- `src/tests/` (all files)

**Project config:**
- `requirements.txt`

---

## Validation Commands

```bash
# 1. Verify existing Python tests unchanged
pytest src/tests/ -v
# Expected: 237 passed, 0 failed

# 2. Install frontend dependencies (from src/frontend/)
cd src/frontend
npm install

# 3. TypeScript + build check
npm run build
# Expected: compiled successfully, no type errors

# 4. Lint check
npm run lint
# Expected: no ESLint errors

# 5. Frontend tests
npm test
# Expected: ≥10 test suites, ≥20 tests passed, 0 failed

# 6. Development server
npm run dev
# Expected: http://localhost:3000 serves the dashboard
# SHP-1002 pre-selected, map renders, AI brief panel available

# 7. Security verification
grep -r "WATSONX" src/frontend/   # must return zero matches
grep -r "mapbox" src/frontend/    # must return zero matches
grep -ri "NEXT_PUBLIC_MAPBOX" src/.env.example  # must return zero matches
```

---

## Development Workflow

**Terminal 1 — FastAPI backend (required):**
```bash
source .venv/bin/activate
python -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --reload
```
API docs: http://localhost:8000/docs

**Terminal 2 — Next.js frontend (Step 6 focus):**
```bash
cd src/frontend
npm run dev
```
Control Tower: http://localhost:3000

**Terminal 3 — MCP server (optional; only for Bob integration testing):**
```bash
source .venv/bin/activate
python -m src.mcp.server
```
The frontend works independently of Terminal 3.

**Environment (create once, git-ignored):**
```bash
# src/frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Demo Flow for Judges

1. Open http://localhost:3000
2. Dashboard loads; SHP-1002 (CRITICAL, ALERT_DISRUPTION) is pre-selected
3. Risk score gauge shows 82+ CRITICAL in red
4. Five sub-score bars show high disruption (r_disruption) and cold-chain (r_cold_chain) components
5. Cold-chain panel shows "EXCURSION ACTIVE" — +2.8°C deviation, FDA HACCP
6. Route panel shows `no_route_found` informational state (honest representation)
7. Fleet match panel shows FLT-302 as top rescue asset
8. Click "Get AI Brief" → Granite synthesizes all four engine outputs into
   operational narrative; `🤖 IBM Granite` badge confirms live AI
9. Disruption monitor shows DIS-501 (HIGH, Snoqualmie Pass closure)
10. Click DIS-501 → disruption impact panel shows SHP-1002 within 200 km radius
11. Map shows shipment and disruption markers with radius circle

---

## Acceptance Criteria

- [ ] `npm run build` passes with zero TypeScript errors
- [ ] `npm run lint` passes with zero ESLint errors
- [ ] `npm test` produces ≥10 test files, ≥20 test cases, 0 failures
- [ ] `pytest src/tests/ -v` still passes all 237 Python tests
- [ ] SHP-1002 is pre-selected on http://localhost:3000 initial load
- [ ] Risk gauge displays engine `total_score` (0–100), never `current_risk_score` (0–1)
- [ ] `ai_generated: true` renders `🤖 IBM Granite` badge
- [ ] `ai_generated: false` renders `⚙️ Deterministic Fallback` badge (not an error)
- [ ] `no_route_found: true` renders informational message (not an error)
- [ ] `no_asset_found: true` renders informational message (not an error)
- [ ] Map renders shipment markers at correct lat/lon positions
- [ ] Disruption radius circles render for all three disruptions with geometry
- [ ] No `WATSONX_*` variables referenced in any frontend file
- [ ] `NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN` removed from `src/.env.example`
- [ ] No backend files modified

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Leaflet SSR crash | Map fails to render | dynamic import with ssr:false; LoadingSpinner fallback |
| Leaflet icon 404 | Markers invisible | CDN PNG workaround in Phase 8 |
| `no_route_found: true` for all shipments | Route panel always empty | Display honest informational state; documents fixture mismatch |
| Fleet `current_lat` null | No fleet markers on map | Decision 19: fleet markers not required; map still has shipment + disruption markers |
| `Promise.all` partial failure | Detail panels missing | Catch per-item; set individual states to null; show per-panel error |
| `NEXT_PUBLIC_API_URL` not set | All API calls fail to localhost:8000 | Fallback default encoded in api.ts; ErrorBanner shows "Backend unavailable" |
| Identity-obj-proxy missing | Jest CSS test failure | Add as devDependency in package.json |
| `process.env.NEXT_PUBLIC_API_URL` undefined in Jest | BASE_URL broken | Jest config sets env var or fallback default used |
