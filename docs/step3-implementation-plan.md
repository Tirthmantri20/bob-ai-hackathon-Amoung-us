# Step 3 Implementation Plan — API Integration Layer
# SupplyGuard AI

**Scope:** `src/backend/api/`, `src/backend/schemas/engine_responses.py`,
schema fixes in `route.py` and `carrier.py`, `src/backend/main.py` (router
registration only), `src/tests/test_step3_api.py`

**Source of truth:** `docs/architecture.md`, `docs/solution-overview.md`,
`docs/step2-assumptions.md`, Step 3 Discovery session

**Out of scope:** watsonx.ai, Granite, MCP, frontend, auth,
POST/PATCH/DELETE, PostGIS, OR-Tools, background jobs,
persistent risk-score updates

---

## 1. Objective

Connect the four deterministic Step 2 intelligence engines to FastAPI through
a thin, clean API integration layer. The layer follows a single pattern:

```
HTTP GET → DB lookup (404 on missing) → Engine(session) → Result dataclass
         → Pydantic response schema → JSON HTTP Response
```

No business logic moves into the router files. All scoring, weighting, and
classification stays in the Step 2 engines.

---

## 2. Architecture

### 2.1 Module Structure

```
src/backend/
├── api/
│   ├── __init__.py          (unchanged — stays empty)
│   ├── shipments.py         APIRouter — all /api/shipments/* + /api/risk/active
│   ├── disruptions.py       APIRouter — all /api/disruptions/*
│   ├── fleet.py             APIRouter — all /api/fleet/*
│   └── routes.py            APIRouter — all /api/routes/*
│
├── schemas/
│   └── engine_responses.py  NEW — Pydantic v2 schemas wrapping Step 2 dataclasses
│
└── main.py                  MODIFIED — add four include_router() calls only
```

### 2.2 Dependency Direction

```
Step 2 Engines (pure Python, no Pydantic)
    └─► API Routers (FastAPI, Depends(get_db))
          └─► engine_responses.py (Pydantic v2 schemas)
                └─► JSON HTTP Response
```

Routers are allowed to import:
- `fastapi` (APIRouter, Depends, HTTPException)
- `sqlalchemy.orm.Session`
- `src.backend.db.database.get_db`
- `src.backend.models.*`
- `src.backend.schemas.*` (existing Step 1 schemas + new engine_responses)
- Step 2 engine classes:
  `RiskEngine`, `ColdChainEngine`, `RouteOptimizer`, `FleetMatcher`
- `src.backend.risk_engine.sub_scores` constants for the `affected-shipments`
  proximity check

Routers are NOT allowed to import:
- `mcp`, `ibm_watsonx_ai`, `fastapi.BackgroundTasks` (Step 4+)
- Sub-score calculators directly (engines orchestrate those)

---

## 3. ORM Serialization Fixes

Two existing `field_validator` gaps must be fixed BEFORE writing the routers,
because route handlers call `model_validate(orm_obj)` and those will crash
without the fixes.

### 3.1 `src/backend/schemas/route.py` — JSON text → list

**Problem:** `Route.highways`, `Route.waypoints`, and `Route.cold_storage_depots`
are `Text` columns (JSON string). `RouteBase.highways` is declared
`Optional[List[str]]`. Pydantic v2 `model_validate(route_orm)` receives a `str`
where it expects a `list`, which causes a `ValidationError`.

**Fix:** Add a `field_validator` on all three fields in `RouteBase`:

```
@field_validator("highways", "waypoints", "cold_storage_depots", mode="before")
@classmethod
def parse_json_text(cls, v):
    if isinstance(v, str):
        import json
        return json.loads(v)
    return v
```

This validator runs before type coercion. It converts the stored JSON text to
a Python list. If `v` is already a list (e.g. from a dict), it passes through
unchanged. `None` is untouched. No change to the SQLAlchemy model or the
database representation.

**Verification:** After this fix, `RouteResponse.model_validate(route_orm)`
must succeed and return `highways` as a Python list.

### 3.2 `src/backend/schemas/carrier.py` — JSON text → list + EmailStr cleanup

**Problem 1:** `Carrier.certifications` is stored as JSON text `Text`. `CarrierBase.certifications`
is declared `Optional[List[str]]`. Same crash as above.

**Fix:** Add the same `field_validator` pattern on `certifications`:

```
@field_validator("certifications", mode="before")
@classmethod
def parse_certifications(cls, v):
    if isinstance(v, str):
        import json
        return json.loads(v)
    return v
```

**Problem 2:** `from pydantic import BaseModel, ConfigDict, EmailStr, Field` —
`EmailStr` is imported but never used. `contact_email` is typed `Optional[str]`.

**Fix:** Remove `EmailStr` from the import. Change to:
`from pydantic import BaseModel, ConfigDict, Field`

No runtime behavior change. Removes a lint warning.

---

## 4. New Schema File — `src/backend/schemas/engine_responses.py`

A new file that contains Pydantic v2 `BaseModel` classes corresponding to each
Step 2 `@dataclass` result. These exist solely in the API layer; the engines
themselves never import them.

All schemas use `model_config = ConfigDict(from_attributes=False)` because they
are constructed from dataclass instances via `model_validate(dataclasses.asdict(result))`,
NOT from ORM objects.

### Score scale constraints

| Engine | Output scale | DB field (`current_risk_score`) |
|---|---|---|
| Risk Engine | 0–100 | 0–1 (DO NOT write engine output to DB in Step 3) |
| Route Optimizer | 0–1 | N/A |
| Fleet Matcher | 0–1 | N/A |

`ShipmentRiskResponse.total_score` has `Field(ge=0.0, le=100.0)` — 0–100 scale.
Route and fleet scores have `Field(ge=0.0, le=1.0)`.

### Schemas to define

```python
class ShipmentRiskResponse(BaseModel):
    """Serializes ShipmentRiskResult (risk_engine/scorer.py)."""
    shipment_id: str
    total_score: float              # Field(ge=0.0, le=100.0) — 0 to 100
    severity: str                   # "LOW"/"MEDIUM"/"HIGH"/"CRITICAL"
    r_disruption: float             # Field(ge=0.0, le=1.0)
    r_weather: float                # Field(ge=0.0, le=1.0)
    r_route: float                  # Field(ge=0.0, le=1.0)
    r_cold_chain: float             # Field(ge=0.0, le=1.0)
    r_business: float               # Field(ge=0.0, le=1.0)
    contributing_disruption_ids: list[str]
    weather_fallback: bool
    cold_chain_fallback: bool
    route_fallback: bool
    assessed_at: datetime

class ColdChainResponse(BaseModel):
    """Serializes ExcursionResult (cold_chain/engine.py)."""
    shipment_id: str
    telemetry_id: Optional[str]
    cargo_rule_found: bool
    is_in_excursion: bool
    is_destructive: bool
    cargo_temp_c: Optional[float]
    allowed_min_c: Optional[float]
    allowed_max_c: Optional[float]
    max_allowable_excursion_temp_c: Optional[float]
    deviation_c: Optional[float]    # positive = too warm; negative = too cold
    severity: str                   # "OK"/"WARNING"/"HIGH"/"CRITICAL"/"UNKNOWN"
    excursion_duration_minutes: Optional[int]
    compliance_standard: Optional[str]
    cargo_category: str
    grade: Optional[str]
    assessed_at: datetime

class RouteScoreResponse(BaseModel):
    """Serializes RouteScore (optimizer/route_optimizer.py)."""
    route_id: str
    route_name: str
    total_score: float              # Field(ge=0.0, le=1.0)
    eta_hours: float
    eta_factor: float               # Field(ge=0.0, le=1.0)
    cost_factor: float              # Field(ge=0.0, le=1.0)
    disruption_factor: float        # Field(ge=0.0, le=1.0)
    weather_factor: float           # Field(ge=0.0, le=1.0)
    cold_chain_factor: float        # Field(ge=0.0, le=1.0)
    recommended: bool
    warnings: list[str]

class RouteOptimizerResponse(BaseModel):
    """Serializes RouteOptimizerResult (optimizer/route_optimizer.py)."""
    shipment_id: str
    scored_routes: list[RouteScoreResponse]
    no_route_found: bool
    assessed_at: datetime

class FleetMatchScoreResponse(BaseModel):
    """Serializes FleetMatchScore (optimizer/fleet_matcher.py)."""
    asset_id: str
    vehicle_type: str
    cooling_capability: str         # "ULTRA_COLD"/"STANDARD_COLD"/"AMBIENT"
    total_score: float              # Field(ge=0.0, le=1.0)
    proximity_km: Optional[float]
    proximity_score: float          # Field(ge=0.0, le=1.0)
    cargo_compat_score: float       # Field(ge=0.0, le=1.0)
    refrigeration_score: float      # Field(ge=0.0, le=1.0)
    capacity_score: float           # Field(ge=0.0, le=1.0)
    availability_score: float       # Field(ge=0.0, le=1.0)
    estimated_shipment_weight_kg: int
    asset_capacity_kg: int
    recommended: bool

class FleetMatchResponse(BaseModel):
    """Serializes FleetMatchResult (optimizer/fleet_matcher.py)."""
    shipment_id: str
    scored_assets: list[FleetMatchScoreResponse]
    no_asset_found: bool
    assessed_at: datetime

class AffectedShipmentEntry(BaseModel):
    """Single shipment affected by a disruption."""
    shipment_id: str
    shipment_status: str
    distance_km: float              # Haversine distance to disruption epicentre

class DisruptionImpactResponse(BaseModel):
    """Result of GET /api/disruptions/{id}/affected-shipments."""
    disruption_id: str
    disruption_type: str
    disruption_severity: str
    proximity_radius_km: float
    affected_shipments: list[AffectedShipmentEntry]
    assessed_at: datetime
```

### Dataclass → Pydantic conversion

The engine result `@dataclass` instances are converted in the router via:

```python
import dataclasses

result = engine.evaluate_shipment(shipment)
response = ShipmentRiskResponse.model_validate(dataclasses.asdict(result))
```

`dataclasses.asdict()` recursively converts dataclass fields — including nested
enums — to plain Python dicts. **One edge case**: `ColdChainSeverity` and
`RiskSeverity` are `str` enums (inheriting from `str`), so `asdict()` preserves
them as strings transparently. No special handling required.

**Do not** add `from_attributes=True` — these schemas are not ORM-backed.

---

## 5. Router Design

### 5.1 Shared pattern

Every router handler follows this exact structure:

```python
@router.get("/path/{id}", response_model=SomeResponse)
def handler(id: str, db: Session = Depends(get_db)):
    obj = db.get(ModelClass, id)           # Step 1: DB lookup
    if obj is None:
        raise HTTPException(status_code=404, detail="X not found")
    engine = EngineClass(db)               # Step 2: Engine instantiation
    result = engine.method(obj)            # Step 3: Engine computation
    return ResponseSchema.model_validate(  # Step 4: Serialize
        dataclasses.asdict(result)
    )
```

Pure DB-read handlers (list/get) skip the engine step and use
`model_validate(orm_obj)` directly.

### 5.2 `src/backend/api/shipments.py`

Router prefix: `/api/shipments`

```
GET  /                       → list all shipments
     DB: session.query(Shipment).all()
     Response: list[ShipmentResponse]

GET  /{shipment_id}          → get one shipment
     DB: session.get(Shipment, id) → 404 if None
     Response: ShipmentResponse.model_validate(orm_obj)

GET  /{shipment_id}/risk     → run RiskEngine for one shipment
     DB: session.get(Shipment, id) → 404 if None
     Engine: RiskEngine(db).evaluate_shipment(shp)
     Response: ShipmentRiskResponse.model_validate(asdict(result))
     NOTE: Does NOT persist result to DB. Does NOT write total_score
           (0–100) into Shipment.current_risk_score (0–1 field).

GET  /{shipment_id}/cold-chain   → run ColdChainEngine for one shipment
     DB: session.get(Shipment, id) → 404 if None
     Engine: ColdChainEngine(db).evaluate_shipment(shp)
     Response: ColdChainResponse.model_validate(asdict(result))

GET  /{shipment_id}/routes   → run RouteOptimizer for one shipment
     DB: session.get(Shipment, id) → 404 if None
     Engine: RouteOptimizer(db).optimize_for_shipment(shp)
     Response: RouteOptimizerResponse.model_validate(asdict(result))
     NOTE: no_route_found=True is a valid 200 response, not a 404.

GET  /{shipment_id}/fleet-match  → run FleetMatcher for one shipment
     DB: session.get(Shipment, id) → 404 if None
     Engine: FleetMatcher(db).match_for_shipment(shp)
     Response: FleetMatchResponse.model_validate(asdict(result))
     NOTE: no_asset_found=True is a valid 200 response, not a 404.
```

Additionally on this router (prefix `/api/risk`):

```
GET  /api/risk/active        → run RiskEngine.evaluate_all_active()
     Engine: RiskEngine(db).evaluate_all_active()
     Response: list[ShipmentRiskResponse]
     Implementation: [ShipmentRiskResponse.model_validate(asdict(r)) for r in results]
```

This extra endpoint is added to the `shipments.py` router with a separate prefix
or, more cleanly, as a separate router `risk.py`. Given the small scope, a
`risk.py` router with prefix `/api/risk` is cleaner and avoids mixing prefixes
in one file.

**Revised plan:** Create `src/backend/api/risk.py` as a fifth router file,
`prefix="/api/risk"`:

```
GET  /active     → RiskEngine(db).evaluate_all_active()
                   Response: list[ShipmentRiskResponse]
```

This keeps `shipments.py` prefix-consistent at `/api/shipments`.

### 5.3 `src/backend/api/disruptions.py`

Router prefix: `/api/disruptions`

```
GET  /                          → list all disruptions
     DB: session.query(Disruption).all()
     Response: list[DisruptionResponse]

GET  /{disruption_id}           → get one disruption
     DB: session.get(Disruption, id) → 404 if None
     Response: DisruptionResponse.model_validate(dis)

GET  /{disruption_id}/affected-shipments
     DB: session.get(Disruption, id) → 404 if None
     Logic (INLINE — minimal, uses imported constants):
       1. radius_km = DISRUPTION_RADIUS_KM.get(dis.type, _DEFAULT_DISRUPTION_RADIUS_KM)
       2. If dis.geometry_lat/lon is None → return DisruptionImpactResponse
          with affected_shipments=[], proximity_radius_km=radius_km
       3. active_shipments = session.query(Shipment)
              .filter(Shipment.status.in_(["IN_TRANSIT","ALERT_DISRUPTION"])).all()
       4. For each shipment with non-None coordinates:
              dist = haversine(dis.geometry_lat, dis.geometry_lon,
                               shp.current_lat, shp.current_lon)
              if dist <= radius_km: add AffectedShipmentEntry
     Response: DisruptionImpactResponse(...)
     NOTE: The proximity calculation re-uses imported constants from
           sub_scores.py — DISRUPTION_RADIUS_KM, _DEFAULT_DISRUPTION_RADIUS_KM,
           haversine — it does NOT re-implement the logic, it reads the same
           centralized map.
```

The `affected-shipments` endpoint is the one place where a router calls a
utility function (`haversine`) and reads a constant map (`DISRUPTION_RADIUS_KM`)
directly. This is acceptable because:
- It is read-only parameter lookup, not scoring logic.
- No engine exposes a "which shipments are affected by this disruption" method.
- Creating a dedicated engine method for this one use case would add unnecessary
  complexity to Step 2 engines.
- It still contains no novel business logic — just a loop over the same function
  and constant already used by the Risk Engine sub-scores.

### 5.4 `src/backend/api/fleet.py`

Router prefix: `/api/fleet`

```
GET  /               → list all fleet assets
     DB: session.query(FleetAsset).all()
     Response: list[FleetAssetResponse]

GET  /{asset_id}     → get one fleet asset
     DB: session.get(FleetAsset, id) → 404 if None
     Response: FleetAssetResponse.model_validate(asset)
```

Pure DB reads. No engine involvement.

### 5.5 `src/backend/api/routes.py`

Router prefix: `/api/routes`

```
GET  /               → list all routes
     DB: session.query(Route).all()
     Response: list[RouteResponse]
     NOTE: RouteResponse.model_validate(route_orm) WORKS only after the
           field_validator fix in §3.1 is in place.

GET  /{route_id}     → get one route
     DB: session.get(Route, route_id) → 404 if None
     Response: RouteResponse.model_validate(route)
```

The `route_id` path parameter maps to `Route.route_id` (the primary key).

---

## 6. `src/backend/main.py` Changes

The ONLY changes to `main.py` are the import block and `include_router()` calls.
No lifespan, middleware, or existing endpoints are touched.

### New imports to add:

```python
from src.backend.api import shipments as shipments_router
from src.backend.api import disruptions as disruptions_router
from src.backend.api import fleet as fleet_router
from src.backend.api import routes as routes_router
from src.backend.api import risk as risk_router
```

### New `include_router()` calls (placed after the existing middleware block):

```python
app.include_router(shipments_router.router, prefix="/api/shipments", tags=["shipments"])
app.include_router(disruptions_router.router, prefix="/api/disruptions", tags=["disruptions"])
app.include_router(fleet_router.router, prefix="/api/fleet", tags=["fleet"])
app.include_router(routes_router.router, prefix="/api/routes", tags=["routes"])
app.include_router(risk_router.router, prefix="/api/risk", tags=["risk"])
```

Each `APIRouter` object inside its file is declared WITHOUT a prefix (the prefix
is applied at `include_router()` time in `main.py`). This keeps the router files
self-contained and testable in isolation.

---

## 7. Error Handling Strategy

### 7.1 HTTP status codes

| Condition | Status | Detail string |
|---|---|---|
| `session.get(Shipment, id)` returns `None` | 404 | `"Shipment {id} not found"` |
| `session.get(Disruption, id)` returns `None` | 404 | `"Disruption {id} not found"` |
| `session.get(FleetAsset, id)` returns `None` | 404 | `"Fleet asset {id} not found"` |
| `session.get(Route, route_id)` returns `None` | 404 | `"Route {route_id} not found"` |
| Engine: `no_route_found=True` | 200 | Part of response body |
| Engine: `no_asset_found=True` | 200 | Part of response body |
| Engine: `cold_chain_fallback=True` | 200 | Part of response body |
| Engine: `weather_fallback=True` | 200 | Part of response body |
| Engine: `cargo_rule_found=False` | 200 | Part of response body |
| Unhandled exception | 500 | Default FastAPI handler |

### 7.2 Rule

Only explicitly requested database entities produce 404s. Engine fallback states
(missing telemetry, no matching route, no cargo rule) are valid operational
outcomes surfaced in 200 response bodies as boolean flags.

---

## 8. Database Dependency and Testing Strategy

### 8.1 The `engine` singleton constraint

`database.py` creates `engine` and `SessionLocal` at **module import time** using
`DATABASE_URL` from the environment (defaulting to `supply_chain.db`). This
cannot be changed without modifying `database.py` (which is out of scope).

### 8.2 Installed version constraint

**Starlette 1.6.0 / FastAPI 0.141.1** are installed. Inspecting the `TestClient`
source confirms:

- `TestClient.__init__` does NOT accept a `lifespan` keyword argument.
- `TestClient.__enter__` unconditionally starts the lifespan by calling
  `self.lifespan()`, which sends `lifespan.startup` to the ASGI app.
- There is no `lifespan="off"` option in this version.

**Consequence**: When `TestClient(app)` is used as a context manager with the real
`app`, the lifespan fires, which calls `init_db()` + `seed_database()` against
`supply_chain.db` (the file-based default). This is acceptable because:
- `supply_chain.db` is already in `.gitignore`.
- `seed_database()` is idempotent — running it twice does not corrupt data.
- The test session created by `dependency_overrides` uses a **separate**
  in-memory SQLite database, so test data is isolated.
- The only side-effect is that `supply_chain.db` is touched during tests, which
  is pre-existing behavior (Step 1 `TestFastAPIEndpoints` has the same issue).

### 8.3 Correct test pattern for Step 3

```python
@pytest.fixture(scope="module")
def client():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from src.backend.db.database import Base, get_db
    from src.backend.db.seed import seed_database
    from src.backend.main import app
    from fastapi.testclient import TestClient

    # 1. Build a completely isolated in-memory SQLite engine for tests.
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    test_session = TestSession()
    seed_database(test_session)

    # 2. Override get_db to always yield the test session.
    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    # 3. Use TestClient as a context manager (triggers lifespan against
    #    supply_chain.db — acceptable, see §8.2).
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    # 4. Teardown.
    app.dependency_overrides.clear()
    test_session.close()
```

### 8.4 Session scope

The test session is `scope="module"` — one session shared across all tests in
the module. This matches the Step 1 and Step 2 test pattern and keeps test
runs fast. No transactions are committed between tests; synthetic rows added
within individual tests are flushed but not committed, and are rolled back
manually in the test teardown.

---

## 9. Test Plan — `src/tests/test_step3_api.py`

All tests use the `client` fixture from §8.3.

### 9.1 Shipment CRUD

| ID | Description | Assert |
|---|---|---|
| S-01 | `GET /api/shipments` → 200 | `len(body) == 3`, each has `id` and `status` |
| S-02 | `GET /api/shipments/SHP-1001` → 200 | `body["origin"] == "Chicago Logistics Hub, IL"` |
| S-03 | `GET /api/shipments/SHP-NOTEXIST` → 404 | `body["detail"]` contains "not found" |
| S-04 | `GET /api/shipments/SHP-1002` → 200 | `body["status"] == "ALERT_DISRUPTION"` |

### 9.2 Risk Engine via API

| ID | Description | Assert |
|---|---|---|
| R-01 | `GET /api/shipments/SHP-1001/risk` → 200 | `body["total_score"] <= 50.0`, `body["severity"] in ["LOW","MEDIUM"]` |
| R-02 | `GET /api/shipments/SHP-1002/risk` → 200 | `body["r_cold_chain"] > 0.0` (warm excursion detected) |
| R-03 | `GET /api/shipments/SHP-NOTEXIST/risk` → 404 | `body["detail"]` contains "not found" |
| R-04 | `GET /api/risk/active` → 200 | `len(body) == 3`, each has `total_score`, `severity` |
| R-05 | All active risk scores in range | For each result: `0.0 <= body["total_score"] <= 100.0` |
| R-06 | `GET /api/shipments/SHP-1002/risk` → 200 | `body["severity"] in ["MEDIUM","HIGH","CRITICAL"]` |

### 9.3 Cold-Chain Engine via API

| ID | Description | Assert |
|---|---|---|
| CC-01 | `GET /api/shipments/SHP-1001/cold-chain` → 200 | `body["is_in_excursion"] == false`, `body["severity"] == "OK"` |
| CC-02 | `GET /api/shipments/SHP-1002/cold-chain` → 200 | `body["is_in_excursion"] == true`, `body["severity"] == "WARNING"`, `body["deviation_c"] > 0` |
| CC-03 | `GET /api/shipments/SHP-1003/cold-chain` → 200 | `body["is_in_excursion"] == false` |
| CC-04 | `GET /api/shipments/SHP-NOTEXIST/cold-chain` → 404 | `body["detail"]` contains "not found" |
| CC-05 | `GET /api/shipments/SHP-1002/cold-chain` → 200 | `body["cargo_rule_found"] == true`, `body["grade"] == "Perishable Frozen"` |

### 9.4 Route Optimizer via API

| ID | Description | Assert |
|---|---|---|
| RO-01 | `GET /api/shipments/SHP-1002/routes` → 200 | `body["no_route_found"] == false`, `len(body["scored_routes"]) == 1`, route is `RT-SEA-DEN-01` |
| RO-02 | `GET /api/shipments/SHP-1001/routes` → 200 | `body["no_route_found"] == true` (origin "Chicago Logistics Hub, IL" ≠ "Chicago, IL") |
| RO-03 | `GET /api/shipments/SHP-NOTEXIST/routes` → 404 | `body["detail"]` contains "not found" |
| RO-04 | RO-01 scored_routes have warnings | ICY_BLOCKED warning appears in any `warnings` list of `scored_routes` |
| RO-05 | Route response score field bounds | Each `total_score` in `[0.0, 1.0]` |
| RO-06 | Exactly one route is `recommended` | `sum(r["recommended"] for r in body["scored_routes"]) == 1` |

### 9.5 Fleet Matcher via API

| ID | Description | Assert |
|---|---|---|
| FM-01 | `GET /api/shipments/SHP-1003/fleet-match` → 200 | `body["no_asset_found"] == false`, FLT-514 not in `scored_assets` (assigned to SHP-1003) |
| FM-02 | `GET /api/shipments/SHP-1003/fleet-match` → 200 | All `scored_assets` have `cargo_compat_score <= 0.1` (STANDARD_COLD for cryo shipment) |
| FM-03 | `GET /api/shipments/SHP-NOTEXIST/fleet-match` → 404 | `body["detail"]` contains "not found" |
| FM-04 | `GET /api/shipments/SHP-1001/fleet-match` → 200 | `body["no_asset_found"] == false`, scores in `[0.0, 1.0]` |
| FM-05 | Exactly one asset is `recommended` | `sum(a["recommended"] for a in body["scored_assets"]) == 1` |

### 9.6 Disruptions

| ID | Description | Assert |
|---|---|---|
| D-01 | `GET /api/disruptions` → 200 | `len(body) == 3` |
| D-02 | `GET /api/disruptions/DIS-501` → 200 | `body["type"] == "SEVERE_WEATHER"`, `body["severity"] == "HIGH"` |
| D-03 | `GET /api/disruptions/DIS-NOTEXIST` → 404 | `body["detail"]` contains "not found" |
| D-04 | `GET /api/disruptions/DIS-503/affected-shipments` → 200 | `body["disruption_id"] == "DIS-503"`, `body["proximity_radius_km"] == 50.0` (PORT_CONTAINER_HOLD) |
| D-05 | D-04 affected_shipments structure | Each entry has `shipment_id`, `distance_km`, `shipment_status` |
| D-06 | `GET /api/disruptions/DIS-502/affected-shipments` → 200 | ROADWORK radius 30 km — SHP-1001 at Indianapolis, DIS-502 at 39.55°N, 86.05°W; distance ≈ 25 km; may appear |

### 9.7 Fleet and Routes Data Endpoints

| ID | Description | Assert |
|---|---|---|
| FL-01 | `GET /api/fleet` → 200 | `len(body) == 3` |
| FL-02 | `GET /api/fleet/FLT-514` → 200 | `body["vehicle_type"] == "Specialized Cryo-Reefer Van"` |
| FL-03 | `GET /api/fleet/FLT-NOTEXIST` → 404 | `body["detail"]` contains "not found" |
| RT-01 | `GET /api/routes` → 200 | `len(body) == 2` |
| RT-02 | `GET /api/routes/RT-SEA-DEN-01` → 200 | `body["highways"]` is a **list**, `"I-90 E" in body["highways"]` |
| RT-03 | `GET /api/routes/RT-NOTEXIST` → 404 | `body["detail"]` contains "not found" |
| RT-04 | Routes list highways are lists | For each route in `GET /api/routes`: `isinstance(route["highways"], list)` |

RT-02 and RT-04 directly validate the §3.1 `field_validator` fix.

---

## 10. Files to Create

```
src/backend/api/shipments.py
src/backend/api/disruptions.py
src/backend/api/fleet.py
src/backend/api/routes.py
src/backend/api/risk.py
src/backend/schemas/engine_responses.py
src/tests/test_step3_api.py
```

---

## 11. Files to Modify

```
src/backend/schemas/route.py
    + add field_validator for highways / waypoints / cold_storage_depots
    + add json import

src/backend/schemas/carrier.py
    + add field_validator for certifications
    + remove unused EmailStr import

src/backend/main.py
    + import 5 router modules
    + add 5 include_router() calls
    (no other changes)

src/backend/schemas/__init__.py
    + re-export engine_responses.py schemas
```

---

## 12. Files NOT Touched

```
src/data/*.json                    (never modify fixtures)
src/backend/risk_engine/*          (Step 2 — stable)
src/backend/cold_chain/*           (Step 2 — stable)
src/backend/optimizer/*            (Step 2 — stable)
src/backend/models/*               (Step 1 — stable)
src/backend/db/*                   (Step 1 — stable)
src/tests/test_step1.py            (Step 1 — must stay green)
src/tests/test_step2_*.py          (Step 2 — must stay green)
submission.yaml
README.md
.github/workflows/validate.yml
demo/
presentation/
```

---

## 13. Additional Dependencies

None. All required packages are already in `requirements.txt`:
- `fastapi>=0.100.0` — routing, `Depends`, `HTTPException`, `APIRouter`
- `pydantic>=2.0.0` — `field_validator`, `ConfigDict`, `BaseModel`
- `sqlalchemy>=2.0.0` — ORM session
- `python-dotenv` — already loaded

No `pip install` changes.

---

## 14. Validation Commands

After implementation, run:

```bash
# Full test suite (must include Step 1 and Step 2 — no regressions)
.venv/bin/python -m pytest src/tests/ -v --tb=short

# API tests only
.venv/bin/python -m pytest src/tests/test_step3_api.py -v --tb=short

# Quick import sanity check
.venv/bin/python -c "from src.backend.main import app; print('Import OK')"
```

---

## 15. Acceptance Criteria

- [ ] `src/backend/api/shipments.py`, `disruptions.py`, `fleet.py`, `routes.py`,
      `risk.py` exist and declare `router = APIRouter()`.
- [ ] `src/backend/schemas/engine_responses.py` exists with all 7 response schemas.
- [ ] `main.py` registers all 5 routers via `include_router()`.
- [ ] `GET /api/shipments` → 200, returns array of 3 shipments.
- [ ] `GET /api/shipments/SHP-NOTEXIST` → 404.
- [ ] `GET /api/shipments/SHP-1002/risk` → 200, `r_cold_chain > 0`, `total_score ≤ 100`.
- [ ] `GET /api/shipments/SHP-1002/cold-chain` → 200, `is_in_excursion=true`,
      `severity="WARNING"`.
- [ ] `GET /api/shipments/SHP-1002/routes` → 200, `no_route_found=false`,
      `scored_routes[0].route_id = "RT-SEA-DEN-01"`.
- [ ] `GET /api/shipments/SHP-1001/routes` → 200, `no_route_found=true`
      (string mismatch — correct behavior, not a bug).
- [ ] `GET /api/routes/RT-SEA-DEN-01` → 200, `highways` is a JSON **list**
      (not a raw string).
- [ ] `GET /api/risk/active` → 200, all `total_score` values in `[0.0, 100.0]`.
- [ ] `GET /api/disruptions/DIS-503/affected-shipments` → 200, `proximity_radius_km = 50.0`.
- [ ] `Risk Engine does NOT persist total_score` into `Shipment.current_risk_score`
      (confirmed by: calling `/risk` does not change `current_risk_score` returned
      by `/api/shipments/SHP-1001`).
- [ ] `RouteResponse.highways` is a list at the API layer (validates §3.1 fix).
- [ ] All Step 1 and Step 2 tests remain green (99 tests pass, 0 failures).
- [ ] All Step 3 tests pass (0 failures).
- [ ] No fixture JSON files modified.

---

## 16. Risks and Mitigations

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| RISK-S3-01 | `TestClient.__enter__` fires lifespan against `supply_chain.db` | LOW | Acceptable — `.gitignore` covers `*.db`; seeding is idempotent; test requests hit the `override_get_db` session |
| RISK-S3-02 | `RouteResponse.model_validate(orm_route)` crashes if `field_validator` missing | HIGH | Fix §3.1 BEFORE writing any route handler that calls `model_validate` |
| RISK-S3-03 | Handler writes `total_score` (0–100) into `Shipment.current_risk_score` (0–1 with `le=1.0` validator) | HIGH | Step 3 handlers are read-only; explicitly document in router code comments |
| RISK-S3-04 | `dataclasses.asdict()` fails on nested `ColdChainSeverity` / `RiskSeverity` enums | LOW | Both are `str` enums — `asdict()` preserves them as strings; verify in tests |
| RISK-S3-05 | `DisruptionImpactResponse` computation re-imports `haversine` from `risk_engine` — potential circular import | LOW | `haversine.py` imports nothing from `backend`; import is one-directional and safe |
| RISK-S3-06 | Introducing `json` import in `field_validator` for `RouteBase` causes import-time side-effects | NONE | `json` is stdlib; no side effects |
| RISK-S3-07 | `scope="module"` test session shared across tests leaks state from synthetic rows | LOW | Follow same pattern as Step 2 tests: `db_session.delete(obj); db_session.flush()` in each test's teardown |

---

## 17. Out of Scope

- watsonx.ai / Granite (Step 4)
- MCP server / IBM Bob tools (Step 5)
- Frontend / Next.js (Step 6)
- Authentication (no API key or JWT layer)
- POST / PATCH / DELETE endpoints (read-only API in Step 3)
- Persisting calculated risk scores to `Shipment.current_risk_score`
- PostGIS / GeoAlchemy2
- OR-Tools / Scipy optimization libraries
- Background jobs or async task queues
- Rate limiting or request throttling
- `GET /api/shipments/{id}/disruption-impact` (the inverse direction is
  served by `GET /api/disruptions/{id}/affected-shipments`)
- CONFLICT-07 resolution (FLT-302 fixture vs Scenario C narrative — fleet
  matcher correctly uses actual DB state; test must not assert FLT-302 ranks
  first)
