# Step 1 — Backend Data & Schema Foundation
# Implementation Plan — SupplyGuard AI

**Scope:** `src/requirements.txt`, `src/backend/models/`, `src/backend/schemas/`, `src/backend/db/`, `src/backend/main.py`
**Source of truth:** `docs/architecture.md`, `src/data/*.json`
**Out of scope:** frontend, MCP, risk_engine, cold_chain, optimizer, ai, REST business routes

---

## 1. Step Objective

Step 1 establishes the persistent, typed data foundation that every subsequent component depends on.
By the end of this step:

- All 8 domain entities have SQLAlchemy ORM model definitions that map onto the seed fixture fields.
- All 8 entities have corresponding Pydantic v2 schemas providing a clean JSON ↔ Python type boundary.
- A database module under `src/backend/db/` manages the engine, session factory, and table creation.
- A seed loader reads the 7 existing JSON fixtures from `src/data/` and populates the database idempotently on every startup.
- `src/backend/main.py` initializes the database and triggers the seed loader at startup, while keeping the existing `/` and `/health` endpoints intact.
- A `requirements.txt` pinning the exact Step 1 dependencies is present so judges can install the backend with a single `pip install -r requirements.txt`.

Nothing from later steps (REST business routes, risk scoring, cold-chain calculations, watsonx.ai, MCP, frontend) is implemented here.

---

## 2. Existing Architecture Alignment

The plan maps directly onto `docs/architecture.md` as follows:

| Architecture section | What this step implements |
|---|---|
| "Data Models & Schema" — lists all 8 entity definitions | SQLAlchemy models and Pydantic schemas for all 8 |
| "Component Breakdown" — Backend API Gateway: Python 3.11+, FastAPI, Pydantic v2, Uvicorn | Covered by `requirements.txt` and `main.py` update |
| "Component Breakdown" — Geospatial Database: PostgreSQL + PostGIS / GeoAlchemy2 | Database layer is designed for portability; PostGIS NOT implemented yet |
| "Data & Knowledge Persistence Layer" — Seed Data Fixtures | Seed loader reads existing `src/data/*.json` |
| "Security & Reliability" — No hardcoded credentials | `DATABASE_URL` loaded from environment via `.env` |
| "End-to-End Data Flow" step 1 — "Continuous Ingestion & Monitoring" | Seed data provides the baseline records the monitoring engine will query |

The architecture document explicitly names GeoAlchemy2 as the spatial extension layer. This step defers that entirely. All geometry fields mentioned in the architecture (e.g., `disruptions.geometry polygon / radius`) are stored as plain strings or JSON text in Step 1 so that a later GeoAlchemy2 migration can replace them without touching domain logic.

---

## 3. Domain Model Design

The 8 entities below are grounded in two sources:
1. The "Data Models & Schema" section of `docs/architecture.md`.
2. The actual field names and types in the `src/data/*.json` fixture files.

Where the two sources agree, that definition is used. Conflicts are surfaced in Section 13.

---

### 3.1 Carrier

**Source fixture:** `src/data/carriers.json`

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `carrier_id` | String (PK) | No | e.g. `"CRR-401"` |
| `name` | String | No | |
| `contact_email` | String | Yes | Not in architecture doc; present in fixture |
| `phone` | String | Yes | Not in architecture doc; present in fixture |
| `compliance_rating` | Float | No | 0.0–1.0 |
| `on_time_delivery_rate` | Float | No | 0.0–1.0 |
| `active_fleet_size` | Integer | No | |
| `certifications` | JSON / Text | Yes | Stored as JSON array text |

**Relationships:** referenced by `Shipment.carrier_id` (FK).
**Index:** none beyond PK.

---

### 3.2 Route

**Source fixture:** `src/data/routes.json`

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `route_id` | String (PK) | No | e.g. `"RT-CHI-ATL-01"` |
| `name` | String | No | |
| `origin` | String | No | |
| `destination` | String | No | |
| `distance_km` | Float | No | |
| `typical_duration_hours` | Float | No | |
| `highways` | JSON / Text | Yes | Stored as JSON array text |
| `waypoints` | JSON / Text | Yes | Array of `{name, lat, lon}` stored as JSON text |
| `cold_storage_depots` | JSON / Text | Yes | Array of `{name, lat, lon}` stored as JSON text |

**Relationships:** not directly FK-linked in seed data; the optimizer will reference routes by `route_id`.
**Index:** none beyond PK.

**Architecture note:** `docs/architecture.md` mentions "waypoints, known cold-storage depots" without specifying normalization. Step 1 stores both as embedded JSON text to avoid premature normalization. Step 3 (optimizer) may refactor into separate tables if needed.

---

### 3.3 CargoRule

**Source fixture:** `src/data/cargo_rules.json`

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `id` | Integer (PK, auto) | No | Surrogate key; fixture has no natural PK |
| `category` | String | No | e.g. `"Pharmaceuticals"` — unique |
| `grade` | String | No | e.g. `"Cold Chain Grade A"` |
| `min_temp_c` | Float | No | |
| `max_temp_c` | Float | No | |
| `max_excursion_duration_minutes` | Integer | No | |
| `max_allowable_excursion_temp_c` | Float | No | |
| `humidity_max_percent` | Integer | Yes | |
| `inspection_frequency_hours` | Float | No | |
| `requires_continuous_logger` | Boolean | No | |
| `compliance_standard` | String | Yes | |

**Relationships:** `Shipment.cargo_category` can be matched against `CargoRule.category` in application code. No FK constraint imposed at DB level in Step 1 (the fixture field name is `cargo_category`, not `cargo_rule_id`).
**Index:** unique index on `category` to support idempotent seeding.

---

### 3.4 FleetAsset

**Source fixture:** `src/data/fleet.json`

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `id` | String (PK) | No | e.g. `"FLT-302"` |
| `vehicle_type` | String | No | |
| `license_plate` | String | Yes | |
| `status` | String | No | `ACTIVE`, `IDLE`, `EN_ROUTE` etc. |
| `fuel_type` | String | Yes | |
| `cooling_system_type` | String | Yes | |
| `capacity_kg` | Integer | No | |
| `battery_charge_percent` | Integer | Yes | |
| `fuel_level_percent` | Integer | Yes | |
| `driver_name` | String | Yes | |
| `telemetry_stream_id` | String | Yes | Links to `Telemetry.telemetry_id` in app logic |
| `current_lat` | Float | Yes | Not in fixture; reserved for runtime GPS updates |
| `current_lon` | Float | Yes | Not in fixture; reserved for runtime GPS updates |

**Architecture note:** `docs/architecture.md` describes fleet fields including "current coordinates, status, capacity, refrigeration specs, temp range capability, fuel/battery level." The fixture omits `current_lat`/`current_lon` and `temp_range_min_c`/`temp_range_max_c`. The model adds lat/lon as nullable columns (nullable = runtime data). Temp range fields are omitted because no fixture data or architecture formula requires them in Step 1.
**Relationships:** referenced by `Shipment.assigned_vehicle_id` (FK).
**Index:** none beyond PK.

---

### 3.5 Disruption

**Source fixture:** `src/data/disruptions.json`

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `id` | String (PK) | No | e.g. `"DIS-501"` |
| `type` | String | No | `SEVERE_WEATHER`, `PORT_CONTAINER_HOLD`, `ROADWORK_CONGESTION` |
| `severity` | String | No | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `title` | String | No | |
| `affected_corridor` | String | Yes | |
| `start_time` | DateTime | No | ISO 8601 UTC |
| `expected_end_time` | DateTime | Yes | |
| `impact_delay_hours` | Float | Yes | |
| `recommended_reroute` | String | Yes | |
| `geometry_lat` | Float | Yes | From fixture `coordinates.lat` |
| `geometry_lon` | Float | Yes | From fixture `coordinates.lon` |

**Architecture note:** `docs/architecture.md` mentions "geometry polygon / radius" as the geometry field for disruptions. The fixture stores only a single `coordinates: {lat, lon}` point. Step 1 stores this as two Float columns (`geometry_lat`, `geometry_lon`). A future PostGIS migration step will replace these with a proper `GEOMETRY(Point, 4326)` column via GeoAlchemy2.
**Relationships:** no FK in seed data; the risk engine will perform radius proximity checks against shipment coordinates.
**Index:** none beyond PK in Step 1.

---

### 3.6 Weather

**Source fixture:** `src/data/weather.json`

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `station_id` | String (PK) | No | e.g. `"WX-CHI-01"` |
| `location` | String | No | |
| `ambient_temp_c` | Float | No | |
| `condition` | String | Yes | |
| `precipitation_prob_percent` | Integer | Yes | |
| `wind_speed_kmh` | Float | Yes | |
| `road_condition` | String | Yes | `DRY`, `ICY_BLOCKED`, etc. |
| `updated_at` | DateTime | Yes | ISO 8601 UTC |

**Architecture note:** `docs/architecture.md` lists `forecast_vector` as a weather field. The fixture does not include it. The model omits this field in Step 1. A JSON text column can be added when the environmental service is built in Step 4.
**Relationships:** none in seed data; the risk engine queries weather by proximity in application code.
**Index:** none beyond PK.

---

### 3.7 Shipment

**Source fixture:** `src/data/shipments.json`

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `id` | String (PK) | No | e.g. `"SHP-1001"` |
| `tracking_number` | String | Yes | |
| `origin` | String | No | |
| `destination` | String | No | |
| `cargo_type` | String | No | |
| `cargo_category` | String | No | Matches `CargoRule.category` in app logic |
| `required_temp_min_c` | Float | No | |
| `required_temp_max_c` | Float | No | |
| `status` | String | No | `IN_TRANSIT`, `ALERT_DISRUPTION`, etc. |
| `assigned_vehicle_id` | String (FK → FleetAsset.id) | Yes | |
| `carrier_id` | String (FK → Carrier.carrier_id) | Yes | |
| `estimated_departure` | DateTime | Yes | |
| `estimated_arrival` | DateTime | Yes | |
| `current_risk_score` | Float | Yes | 0.0–1.0 seed value; updated by risk engine later |
| `current_lat` | Float | Yes | From fixture `current_location.lat` |
| `current_lon` | Float | Yes | From fixture `current_location.lon` |
| `current_location_name` | String | Yes | From fixture `current_location.name` |

**Relationships:**
- `assigned_vehicle_id` → `FleetAsset.id` (FK; nullable because a shipment may not yet have an assigned vehicle)
- `carrier_id` → `Carrier.carrier_id` (FK; nullable for same reason)

**Index:** index on `status` (risk engine will filter by status frequently).

---

### 3.8 Telemetry

**Source fixture:** `src/data/telemetry.json`

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `telemetry_id` | String (PK) | No | e.g. `"TEL-FLT-302"` |
| `vehicle_id` | String (FK → FleetAsset.id) | No | |
| `shipment_id` | String (FK → Shipment.id) | No | |
| `timestamp` | DateTime | No | ISO 8601 UTC |
| `cargo_temp_c` | Float | No | |
| `cargo_temp_target_c` | Float | Yes | |
| `temp_deviation_c` | Float | Yes | |
| `cargo_humidity_percent` | Float | Yes | |
| `reefer_compressor_status` | String | Yes | `NORMAL_CYCLING`, `WARNING_HIGH_LOAD`, etc. |
| `door_sensor` | String | Yes | `CLOSED`, `OPEN` |
| `vibration_g` | Float | Yes | |
| `gps_lat` | Float | Yes | From fixture `gps.lat` |
| `gps_lon` | Float | Yes | From fixture `gps.lon` |
| `gps_speed_kmh` | Float | Yes | |
| `gps_heading_deg` | Float | Yes | |

**Relationships:**
- `vehicle_id` → `FleetAsset.id` (FK)
- `shipment_id` → `Shipment.id` (FK)

**Index:** index on `shipment_id` (cold-chain engine will query by shipment).

---

## 4. Pydantic Schema Design

Each entity has a three-level schema hierarchy following Pydantic v2 conventions. The `model_config = ConfigDict(from_attributes=True)` is set on all response schemas to enable ORM-mode deserialization.

### Schema Hierarchy Pattern

```
EntityBase          — shared readable fields, no PK
    ↑
EntityCreate        — fields required to create a new record (used by seed loader and future POST routes)
EntityResponse      — EntityBase + PK + any computed/read-only fields; from_attributes=True
```

Update schemas are NOT introduced in Step 1 because no PATCH/PUT routes are implemented here. They belong to Step 3.

---

### 4.1 CarrierBase / CarrierCreate / CarrierResponse

- **Base:** `name`, `compliance_rating`, `on_time_delivery_rate`, `active_fleet_size`, `certifications` (list[str]), `contact_email`, `phone`
- **Create:** inherits Base; no PK (PK is in fixture data so seed loader passes it explicitly)
- **Response:** Base + `carrier_id`

**Note:** since fixture PKs are string IDs (not DB-generated), the seed loader passes the full fixture dict including the PK field. `CarrierCreate` therefore includes `carrier_id`.

### 4.2 RouteBase / RouteCreate / RouteResponse

- **Base:** `name`, `origin`, `destination`, `distance_km`, `typical_duration_hours`, `highways` (list[str]), `waypoints` (list[dict]), `cold_storage_depots` (list[dict])
- **Create:** Base + `route_id`
- **Response:** Base + `route_id`

### 4.3 CargoRuleBase / CargoRuleCreate / CargoRuleResponse

- **Base:** all non-PK fields
- **Create:** Base (PK is auto-integer)
- **Response:** Base + `id`

### 4.4 FleetAssetBase / FleetAssetCreate / FleetAssetResponse

- **Base:** all non-PK fields
- **Create:** Base + `id`
- **Response:** Base + `id`

### 4.5 DisruptionBase / DisruptionCreate / DisruptionResponse

- **Base:** `type`, `severity`, `title`, `affected_corridor`, `start_time`, `expected_end_time`, `impact_delay_hours`, `recommended_reroute`, `geometry_lat`, `geometry_lon`
- **Create:** Base + `id`
- **Response:** Base + `id`

### 4.6 WeatherBase / WeatherCreate / WeatherResponse

- **Base:** all non-PK fields
- **Create:** Base + `station_id`
- **Response:** Base + `station_id`

### 4.7 ShipmentBase / ShipmentCreate / ShipmentResponse

- **Base:** `tracking_number`, `origin`, `destination`, `cargo_type`, `cargo_category`, `required_temp_min_c`, `required_temp_max_c`, `status`, `assigned_vehicle_id`, `carrier_id`, `estimated_departure`, `estimated_arrival`, `current_risk_score`, `current_lat`, `current_lon`, `current_location_name`
- **Create:** Base + `id`
- **Response:** Base + `id`

### 4.8 TelemetryBase / TelemetryCreate / TelemetryResponse

- **Base:** `vehicle_id`, `shipment_id`, `timestamp`, `cargo_temp_c`, `cargo_temp_target_c`, `temp_deviation_c`, `cargo_humidity_percent`, `reefer_compressor_status`, `door_sensor`, `vibration_g`, `gps_lat`, `gps_lon`, `gps_speed_kmh`, `gps_heading_deg`
- **Create:** Base + `telemetry_id`
- **Response:** Base + `telemetry_id`

---

## 5. Database Design

### 5.1 File Layout

```
src/backend/db/
├── __init__.py      — re-exports Base, engine, SessionLocal, get_db
├── database.py      — engine and session factory
└── seed.py          — fixture loader
```

`src/backend/models/__init__.py` imports all model classes so they are registered on `Base.metadata` before `create_all()` is called.

### 5.2 Base

A single `declarative_base()` instance is created in `src/backend/db/database.py` and imported by all model files. This ensures all tables share the same metadata registry.

### 5.3 Engine

The engine is constructed from `DATABASE_URL` read from the environment (via `os.getenv` or a thin settings object). Default: `sqlite:///./supply_chain.db`.

SQLite requires one connection-level argument: `check_same_thread=False`. This argument must NOT be passed for PostgreSQL. The engine factory uses a conditional:

```
if DATABASE_URL starts with "sqlite":
    engine = create_engine(url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(url)
```

This is the only SQLite-specific code path. All other code is backend-agnostic.

### 5.4 Session Management

A `SessionLocal` session factory is created with `autocommit=False, autoflush=False`. A `get_db()` generator yields a session and closes it in a `finally` block. This is the standard FastAPI dependency injection pattern and is compatible with PostgreSQL without change.

### 5.5 Table Creation

`Base.metadata.create_all(bind=engine)` is called once at startup. This is non-destructive (uses `CREATE TABLE IF NOT EXISTS` semantics). Existing tables and their data are preserved on restart.

### 5.6 PostgreSQL Compatibility

The database layer is designed so that switching `DATABASE_URL` from SQLite to PostgreSQL requires only the environment variable change. No code changes are needed for Step 1 functionality. PostGIS geometry columns are NOT added in this step. When they are added in a future step, GeoAlchemy2 column types can be introduced in the model files without disrupting other fields.

### 5.7 Settings Object

A lightweight `Settings` dataclass or `BaseSettings` Pydantic model in `src/backend/db/database.py` (or `src/backend/config.py`) reads `DATABASE_URL`, `DEBUG`, `PORT`, and `HOST` from environment. This avoids scattered `os.getenv` calls and makes the configuration testable.

---

## 6. Seed Strategy

### 6.1 Fixture Loading Order

The seeding must respect foreign key dependencies:

```
1. CargoRule        — no FK dependencies
2. Carrier          — no FK dependencies
3. Route            — no FK dependencies
4. Weather          — no FK dependencies
5. FleetAsset       — no FK dependencies
6. Disruption       — no FK dependencies
7. Shipment         — depends on FleetAsset (vehicle_id FK), Carrier (carrier_id FK)
8. Telemetry        — depends on FleetAsset (vehicle_id FK), Shipment (shipment_id FK)
```

Steps 1–6 can be seeded in any order relative to each other. Steps 7 and 8 must follow steps 5 and 2 respectively.

### 6.2 JSON Parsing and Type Conversion

Each fixture file is read with `json.load()`. Field-level conversions required:

| Fixture | Raw field | Model field | Conversion |
|---|---|---|---|
| `disruptions.json` | `coordinates.lat` / `.lon` | `geometry_lat` / `geometry_lon` | dict extraction |
| `disruptions.json` | `start_time`, `expected_end_time` | DateTime columns | `datetime.fromisoformat()` |
| `shipments.json` | `current_location.lat/lon/name` | `current_lat`, `current_lon`, `current_location_name` | dict extraction |
| `shipments.json` | `estimated_departure`, `estimated_arrival` | DateTime columns | `datetime.fromisoformat()` |
| `telemetry.json` | `gps.lat/lon/speed_kmh/heading_deg` | `gps_lat`, etc. | dict extraction |
| `telemetry.json` | `timestamp` | DateTime | `datetime.fromisoformat()` |
| `weather.json` | `updated_at` | DateTime | `datetime.fromisoformat()` |
| `carriers.json` | `certifications` | JSON text | `json.dumps()` for storage; Pydantic deserializes on read |
| `routes.json` | `highways`, `waypoints`, `cold_storage_depots` | JSON text | `json.dumps()` |

### 6.3 Idempotency / Upsert Behavior

The seed loader checks for existence before inserting using `session.get(ModelClass, primary_key)`. If the record already exists, it is skipped (no update). This makes the loader safe to run on every application startup without duplicating or overwriting runtime-modified records (e.g., updated `current_risk_score` on a shipment).

An explicit `merge()` strategy is NOT used because it would overwrite runtime state (e.g., risk scores updated by the engine after startup).

For `CargoRule` (auto-integer PK), existence is checked by `category` (unique index) using `session.query(CargoRule).filter_by(category=...).first()`.

### 6.4 Error Handling

- If a fixture file is missing: raise `FileNotFoundError` with the full path and fixture name. The application must not start with an incomplete seed.
- If a fixture file is invalid JSON: the `json.JSONDecodeError` propagates up with the file name in the message.
- If a required field is missing from a fixture record: a `KeyError` or Pydantic `ValidationError` surfaces. The record index is included in the error message.
- All errors abort startup via exception propagation (FastAPI lifespan raises, Uvicorn exits non-zero).

### 6.5 Reusability

The seed loader exposes a single public function: `seed_database(session: Session) -> None`. It is called from `main.py` startup. It can also be called directly in tests by passing a test session, enabling isolated unit testing without Uvicorn.

---

## 7. Startup Flow

```
uvicorn src/backend/main:app --host 0.0.0.0 --port 8000
    │
    ▼
FastAPI app object is constructed
    │
    ▼
@app.on_event("startup") handler fires  [or lifespan context manager]
    │
    ├─► import db.database: create engine from DATABASE_URL
    │
    ├─► Base.metadata.create_all(bind=engine)
    │       → CREATE TABLE IF NOT EXISTS for all 8 entities
    │
    ├─► open SessionLocal()
    │
    ├─► seed_database(session)
    │       → load 8 fixture files in dependency order
    │       → skip-if-exists check per record
    │       → session.commit()
    │
    └─► session.close()
    │
    ▼
FastAPI routes registered and active
    │
    ▼
GET /        → returns {"status": "online", ...}
GET /health  → returns {"status": "healthy", ...}
```

The startup event is implemented using FastAPI's `@app.on_event("startup")` decorator (compatible with FastAPI versions used in the project) or the modern `lifespan` async context manager. Either is acceptable; the `lifespan` approach is preferred for Pydantic v2 + FastAPI 0.100+ projects and should be documented clearly.

---

## 8. Dependencies

`src/requirements.txt` will contain exactly the following for Step 1:

| Package | Version constraint | Reason |
|---|---|---|
| `fastapi` | `>=0.100.0` | Core web framework; already in use in `main.py` |
| `uvicorn[standard]` | `>=0.23.0` | ASGI server for FastAPI |
| `pydantic` | `>=2.0.0,<3` | Schema validation; v2 required per architecture |
| `sqlalchemy` | `>=2.0.0` | ORM for all 8 entity models |
| `python-dotenv` | `>=1.0.0` | Loads `.env` into environment at startup |
| `numpy` | `>=1.25.0` | Required by architecture; not used in Step 1 directly but imported by future engine modules that will be co-located in the same virtualenv |
| `pandas` | `>=2.0.0` | Same rationale as NumPy |

**Why NumPy and Pandas in Step 1:**
The setup guide instructs judges to do a single `pip install -r requirements.txt` before running the backend. The risk engine (Step 2) is co-located in the same virtualenv. Including NumPy and Pandas in the base manifest ensures the environment is complete from the first install and avoids judges having to re-install between steps. They are not imported or used in any Step 1 module.

**Not included in Step 1:**
- `ibm-watsonx-ai` (Step 4)
- `mcp` SDK (Step 5)
- `psycopg2-binary` / `asyncpg` (Step 3/DB upgrade)
- `geoalchemy2` (Step 3/DB upgrade)
- `scipy` / `ortools` (Step 2)
- `requests` (already listed in setup guide but not imported in Step 1)

**Note:** The `docs/setup-guide.md` currently instructs judges to run `pip install fastapi uvicorn pydantic requests` manually without a `requirements.txt`. Step 1 fixes this by providing `requirements.txt`. The setup guide should be updated in a later cleanup step to reference `pip install -r requirements.txt` instead. That update is NOT part of Step 1 to avoid scope creep.

---

## 9. Files to Create / Modify

### Files to CREATE

| File | Purpose |
|---|---|
| `src/requirements.txt` | Python dependency manifest for the entire backend virtualenv |
| `src/backend/db/database.py` | `Base`, `engine`, `SessionLocal`, `get_db()`, DATABASE_URL config |
| `src/backend/db/seed.py` | `seed_database(session)` function; reads all 7 JSON fixtures |
| `src/backend/models/shipment.py` | `Shipment` SQLAlchemy model |
| `src/backend/models/fleet_asset.py` | `FleetAsset` SQLAlchemy model |
| `src/backend/models/disruption.py` | `Disruption` SQLAlchemy model |
| `src/backend/models/weather.py` | `Weather` SQLAlchemy model |
| `src/backend/models/telemetry.py` | `Telemetry` SQLAlchemy model |
| `src/backend/models/cargo_rule.py` | `CargoRule` SQLAlchemy model |
| `src/backend/models/route.py` | `Route` SQLAlchemy model |
| `src/backend/models/carrier.py` | `Carrier` SQLAlchemy model |
| `src/backend/schemas/shipment.py` | Pydantic v2 Shipment schemas |
| `src/backend/schemas/fleet_asset.py` | Pydantic v2 FleetAsset schemas |
| `src/backend/schemas/disruption.py` | Pydantic v2 Disruption schemas |
| `src/backend/schemas/weather.py` | Pydantic v2 Weather schemas |
| `src/backend/schemas/telemetry.py` | Pydantic v2 Telemetry schemas |
| `src/backend/schemas/cargo_rule.py` | Pydantic v2 CargoRule schemas |
| `src/backend/schemas/route.py` | Pydantic v2 Route schemas |
| `src/backend/schemas/carrier.py` | Pydantic v2 Carrier schemas |

### Files to MODIFY

| File | Change |
|---|---|
| `src/backend/db/__init__.py` | Re-export `Base`, `engine`, `SessionLocal`, `get_db` from `database.py` |
| `src/backend/models/__init__.py` | Import all 8 model classes so they register on `Base.metadata` |
| `src/backend/schemas/__init__.py` | Import and re-export all schema classes for convenience |
| `src/backend/main.py` | Add startup event: call `create_all` + `seed_database`; add `python-dotenv` load; keep existing `/` and `/health` routes unchanged |

### Files NOT touched

`src/backend/ai/`, `src/backend/api/`, `src/backend/cold_chain/`, `src/backend/optimizer/`, `src/backend/risk_engine/`, `src/backend/services/`, `src/mcp/`, `src/frontend/`, `src/tests/`, `src/data/*.json`, `docs/`, `README.md`, `submission.yaml`, `demo/`, `presentation/`

---

## 10. Validation Strategy

These checks are performed manually and/or via pytest after Step 1 is complete. Actual test files are written in Step 7; this section defines the scenarios they will exercise.

### 10.1 Database Initialization

- Start the backend from a clean state (no `supply_chain.db`).
- Verify `supply_chain.db` is created.
- Use a SQLite browser or SQLAlchemy `inspect()` to confirm all 8 tables exist.

### 10.2 Model Creation (schema parity)

- For each of the 8 models, verify `Base.metadata.tables` contains the expected table name.
- Verify column names match the fixture fields after transformation.

### 10.3 Schema Validation

- Instantiate each `*Response` schema from a sample fixture dict; verify no `ValidationError` is raised.
- Test that a schema with a missing required field raises `ValidationError`.
- Test that `datetime` strings from the fixtures parse correctly through the schema.

### 10.4 Seed Loading

- After startup, query each table and assert row counts match fixture lengths:
  - `carriers` → 3 rows
  - `cargo_rules` → 3 rows
  - `fleet_assets` → 3 rows
  - `disruptions` → 3 rows
  - `weather` → 4 rows
  - `routes` → 2 rows
  - `shipments` → 3 rows
  - `telemetry` → 3 rows

- Verify specific field values, e.g.:
  - `Shipment` with `id="SHP-1002"` has `status="ALERT_DISRUPTION"` and `current_risk_score=0.78`.
  - `Telemetry` with `telemetry_id="TEL-FLT-109"` has `reefer_compressor_status="WARNING_HIGH_LOAD"`.
  - `FleetAsset` with `id="FLT-514"` has `vehicle_type="Specialized Cryo-Reefer Van"`.

### 10.5 Repeat Seed Execution

- Call `seed_database()` twice in the same session.
- Verify row counts remain unchanged (no duplicates).
- Verify no exception is raised.

### 10.6 Fixture Relationships

- Query `Shipment` with `id="SHP-1001"`:
  - `assigned_vehicle_id` should match an existing `FleetAsset.id` (`"FLT-302"`).
  - `carrier_id` should match an existing `Carrier.carrier_id` (`"CRR-401"`).
- Query `Telemetry` with `telemetry_id="TEL-FLT-302"`:
  - `vehicle_id` (`"FLT-302"`) should resolve to a `FleetAsset` row.
  - `shipment_id` (`"SHP-1001"`) should resolve to a `Shipment` row.

### 10.7 FastAPI Startup

- Run `uvicorn src.backend.main:app --port 8000`.
- Verify no startup exceptions in the Uvicorn log.
- Verify log includes confirmation that tables were created and seed completed.

### 10.8 /health Endpoint

- `GET http://localhost:8000/health` returns HTTP 200.
- Response body contains `{"status": "healthy", ...}`.
- `GET http://localhost:8000/` returns HTTP 200 with service metadata.

---

## 11. Acceptance Criteria

- [ ] `src/requirements.txt` exists and `pip install -r src/requirements.txt` completes without error in a clean virtualenv.
- [ ] `uvicorn` starts the FastAPI app without any import errors or exceptions.
- [ ] All 8 SQLAlchemy tables are created in `supply_chain.db` on first startup.
- [ ] `GET /health` returns HTTP 200.
- [ ] All 8 fixture files are loaded: 3 + 3 + 3 + 4 + 2 + 3 + 3 + 3 = **24 seed rows** are present across all tables.
- [ ] Restarting the server does not create duplicate rows.
- [ ] Correct FK relationships: `SHP-1001` links to `FLT-302` and `CRR-401`; `TEL-FLT-302` links to `FLT-302` and `SHP-1001`.
- [ ] All Pydantic response schemas instantiate correctly from fixture dicts without validation errors.
- [ ] A missing fixture file causes a `FileNotFoundError` at startup (fail loudly).
- [ ] No files outside the defined Step 1 scope have been modified.
- [ ] No `.env` file or database file is committed to Git.

---

## 12. Out of Scope

The following are explicitly NOT implemented in Step 1:

- REST business routes (shipment list, disruption impact, route optimization)
- Risk scoring calculations (Step 2)
- Cold-chain excursion detection (Step 2)
- Multi-criteria route optimization (Step 2)
- Fleet redeployment matching (Step 2)
- watsonx.ai / Granite 3.0 integration (Step 4)
- MCP server tools and transport (Step 5)
- Next.js frontend, any UI components (Step 6)
- pytest test files (Step 7 — validation in this step is manual)
- PostGIS geometry column types and GeoAlchemy2
- Docker Compose configuration
- README.md content update
- submission.yaml content update
- Demo screenshots, video, or presentation changes
- Any modification to `src/data/*.json` fixture files

---

## 13. Risks and Documentation Conflicts

### CONFLICT-01: Legacy Shipment IDs in solution-overview.md

**Where:** `docs/solution-overview.md` references shipment IDs `S204`, `S102`, and vehicle/carrier `TRK-102` in narrative examples.

**Actual fixture IDs:** `SHP-1001`, `SHP-1002`, `SHP-1003`, `FLT-302`, `FLT-109`, `FLT-514`.

**Impact:** No code impact in Step 1. The seed loader uses fixture IDs as-is. The MCP tools and IBM Bob query examples in Step 5 would fail if they hardcode the legacy IDs.

**Recommendation:** Do not modify either the fixtures or the docs in Step 1. Document the conflict here. In Step 5, use the correct fixture IDs (`SHP-1002`, `FLT-302`) in MCP tool docstrings and IBM Bob example prompts. Flag `docs/solution-overview.md` for a narrative update in the final cleanup step (Step 7).

---

### CONFLICT-02: Disruption geometry field mismatch

**Where:** `docs/architecture.md` describes disruption geometry as "geometry polygon / radius." The fixture `src/data/disruptions.json` stores only a single `coordinates: {lat, lon}` point, with no polygon or radius value.

**Impact:** Step 1 stores geometry as `geometry_lat` / `geometry_lon` Float columns. The risk engine (Step 2) cannot perform true polygon intersection without additional data.

**Recommendation:** Store the point coordinates as flat floats in Step 1. When the risk engine is built in Step 2, implement a configurable radius (e.g., `impact_radius_km` column defaulting to a sensible value) for proximity checks. If real polygon data is added later, a migration adds the PostGIS geometry column. Do not add `impact_radius_km` in Step 1 as it has no fixture value.

---

### CONFLICT-03: setup-guide.md pip install command is incomplete

**Where:** `docs/setup-guide.md` tells judges to run:
```
pip install fastapi uvicorn pydantic requests
```

This omits `sqlalchemy`, `python-dotenv`, `numpy`, and `pandas` — all of which are required by the Step 1 implementation.

**Impact:** Judges following the current setup guide will get `ModuleNotFoundError` at startup.

**Recommendation:** Step 1 creates `src/requirements.txt`. The setup guide should be updated to replace the manual pip install command with `pip install -r src/requirements.txt`. This update is a documentation fix and belongs to the final submission cleanup step (Step 7), not Step 1, to keep scope clean.

---

### CONFLICT-04: CargoRule has no natural primary key in the fixture

**Where:** `docs/architecture.md` describes `cargo_rules` as having "cargo classification, regulatory standard, allowable excursions, maximum duration" but does not specify a PK. The fixture has no `id` field.

**Impact:** A surrogate auto-integer PK is needed for the ORM model. Idempotency checking must use the `category` field (unique) instead of a stable PK lookup.

**Recommendation:** Use auto-integer surrogate PK as described in Section 3.3. Add a unique constraint on `category`. This is self-consistent and requires no documentation change.

---

### CONFLICT-05: FleetAsset temp-range fields mentioned in architecture but absent from fixture

**Where:** `docs/architecture.md` lists "temp range capability" as a fleet asset attribute. The fixture `src/data/fleet.json` does not include `temp_range_min_c` or `temp_range_max_c`.

**Impact:** The fleet matching formula in `docs/architecture.md` includes "Refrigeration Match" (weight 0.20). If temp range data is absent, this factor cannot be computed precisely.

**Recommendation:** Do not add the columns in Step 1 (no fixture data to populate them with). Flag for Step 2 (optimizer implementation) to either add the fields with hardcoded defaults per cooling system type, or derive them from `cooling_system_type` string mapping. No fixture file modification in Step 1.

---

### CONFLICT-06: Weather forecast_vector field in architecture but absent from fixture

**Where:** `docs/architecture.md` lists `forecast_vector` as a weather entity field. The fixture `src/data/weather.json` does not include it.

**Impact:** The environmental service (Step 4) needs this field for the Three-Layer Evidence Model (Layer 2: Environmental Forecast).

**Recommendation:** Omit the column in Step 1. Add a nullable JSON text column `forecast_vector` to the `Weather` model in Step 4 when the environmental service is implemented. No migration tooling is needed for SQLite (can use `ALTER TABLE` or recreate); for PostgreSQL, a migration script will be needed in Step 4.
