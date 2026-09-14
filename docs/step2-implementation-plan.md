# Step 2 Implementation Plan — Core Intelligence Engines
# SupplyGuard AI

**Scope:** `src/backend/risk_engine/`, `src/backend/cold_chain/`, `src/backend/optimizer/`,
`src/tests/test_step2_*.py`, `docs/step2-assumptions.md`

**Source of truth:** `docs/architecture.md`, `docs/solution-overview.md`,
`docs/step1-backend-foundation-plan.md`, Step 2 discovery session

**Out of scope:** FastAPI routes, watsonx.ai, MCP, frontend, OR-Tools, PostGIS

---

## 1. Objective

Step 2 delivers the four deterministic intelligence engines that constitute the core analytical
capability of SupplyGuard AI:

1. **Risk Engine** — scores each active shipment 0–100 across five weighted risk dimensions and
   classifies it as LOW / MEDIUM / HIGH / CRITICAL.
2. **Cold-Chain Engine** — resolves cargo regulatory rules, detects temperature excursions from
   telemetry, and classifies excursion severity as OK / WARNING / HIGH / CRITICAL.
3. **Route Optimizer** — scores candidate routes against a five-factor weighted formula and
   recommends the best option for a given shipment.
4. **Fleet Matcher** — scores idle or available fleet assets against five matching criteria and
   recommends the best asset for emergency cargo transfer.

All four engines:
- Accept SQLAlchemy ORM objects (or collections of them) from the Step 1 data layer.
- Return plain Python dataclasses — no FastAPI, no Pydantic, no MCP, no watsonx.ai imports.
- Are fully exercised by pytest tests using the existing in-memory SQLite fixture pattern.

Nine prototype assumptions (MD-01 through MD-09) are documented in
`docs/step2-assumptions.md` and incorporated precisely where they govern implementation
decisions.

---

## 2. Architecture

### Dependency Direction

```
Step 1 Models (SQLAlchemy ORM)
  └─► Core Intelligence Engines (pure Python)
        └─► Structured Domain Result Dataclasses
              └─► Step 3 FastAPI Routes        [not in Step 2]
                    └─► Step 4 watsonx.ai      [not in Step 2]
                          └─► Step 5 MCP/Bob   [not in Step 2]
                                └─► Step 6 UI  [not in Step 2]
```

### Shared Internal Utilities

Two small utilities are shared across engines and must have no external dependencies beyond
the Python standard library:

| Utility | Location | Purpose |
|---|---|---|
| Haversine distance | `risk_engine/haversine.py` | Pure-Python great-circle distance (km) |
| Min-max normalizer | `optimizer/normalizer.py` | Normalize a list of floats to [0, 1]; handles edge cases |

### What Engines May Import

- `src.backend.models.*` — ORM model classes (read-only)
- `src.backend.risk_engine.haversine` — distance utility
- `src.backend.optimizer.normalizer` — normalization utility
- Python standard library only (`dataclasses`, `datetime`, `math`, `typing`, `enum`, `logging`)
- **FORBIDDEN:** `fastapi`, `uvicorn`, `pydantic`, `mcp`, `ibm_watsonx_ai`, anything from
  `src.backend.schemas`, anything from `src.backend.api`

---

## 3. Risk Engine Design

### 3.1 Formula

From `docs/architecture.md` — canonical, weights must not be altered:

```
Risk_score_0_to_1 = 0.30 × R_disruption
                  + 0.25 × R_weather
                  + 0.20 × R_route
                  + 0.15 × R_cold_chain
                  + 0.10 × R_business

Final_score_0_to_100 = Risk_score_0_to_1 × 100
```

Each sub-score `R_*` is independently normalized to `[0.0, 1.0]` before multiplication by its
weight. The final score is clamped to `[0.0, 100.0]` after multiplication.

**Weight invariant** (must be asserted in tests): `0.30 + 0.25 + 0.20 + 0.15 + 0.10 == 1.00`

### 3.2 Classification Thresholds

Exactly as documented in `docs/architecture.md`:

| Score range | Severity label |
|---|---|
| 0.0 – 25.0 | `LOW` |
| 25.1 – 50.0 | `MEDIUM` |
| 50.1 – 75.0 | `HIGH` |
| 75.1 – 100.0 | `CRITICAL` |

Classification is an enum: `RiskSeverity.LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.

### 3.3 Sub-Score: R_disruption (weight 0.30)

**Goal:** quantify the degree to which active disruptions threaten this shipment's corridor.

**Inputs used:**
- `Disruption.geometry_lat`, `geometry_lon` — disruption epicentre
- `Disruption.severity` — `MEDIUM`, `HIGH`, `CRITICAL`
- `Disruption.impact_delay_hours` — additional transit time
- `Disruption.type` — used for radius selection (see MD-08)
- `Shipment.current_lat`, `current_lon` — current shipment position

**Algorithm:**

1. Load all `Disruption` records from the session.
2. For each disruption, compute Haversine distance from disruption epicentre to shipment's
   current position.
3. Compare distance against the disruption-type-specific proximity radius (MD-08).
4. For disruptions within radius, compute a per-disruption score:
   ```
   disruption_score_i = severity_weight × delay_factor
   ```
   Where:
   - `severity_weight`: `MEDIUM=0.4`, `HIGH=0.7`, `CRITICAL=1.0` (centralized map, MD-08)
   - `delay_factor`: `min(impact_delay_hours / 24.0, 1.0)` — normalizes delay against a
     24-hour ceiling
5. Combine: `R_disruption = min(sum of all disruption_score_i, 1.0)`

**Fallback (no disruptions or none within radius):** `R_disruption = 0.0`

**Rationale for sum-then-clamp:** Multiple overlapping disruptions compound risk; clamping
at 1.0 prevents the sub-score from exceeding the sub-score range.

### 3.4 Sub-Score: R_weather (weight 0.25)

**Goal:** quantify adverse weather risk along the shipment's current corridor.

**Inputs used:**
- `Weather.road_condition` — categorical risk indicator
- `Weather.precipitation_prob_percent` — 0–100
- `Weather.ambient_temp_c` — extreme heat stresses reefer units
- `Shipment.current_lat`, `current_lon` — proximity matching

**Algorithm:**

1. Find the closest weather station to the shipment's current position using Haversine distance.
2. If no weather station within 500 km, return `R_weather = 0.0` with a warning flag.
3. Compute `road_risk` from the centralized road-condition map (MD-04):
   - `ICY_BLOCKED` → `1.0`
   - `ICY` → `0.8`
   - `WET` → `0.5`
   - `DRY` → `0.1`
   - unrecognised or `None` → `0.3`
4. Compute `precip_risk = precipitation_prob_percent / 100.0`
5. Compute `heat_risk`: thermal stress on cargo. For shipments with `required_temp_max_c < 10°C`
   (cold-chain cargo), high ambient temperature increases risk:
   ```
   heat_stress = max(0.0, (ambient_temp_c - 20.0) / 20.0)
   heat_risk = min(heat_stress, 1.0)
   ```
   For ambient temperatures ≤ 20°C, `heat_risk = 0.0`.
6. Combine:
   ```
   R_weather = (0.5 × road_risk) + (0.3 × precip_risk) + (0.2 × heat_risk)
   ```
   Result is already in `[0, 1]` by construction.

**Internal weights (0.5, 0.3, 0.2) are prototype assumptions** — centralized in a constants
block, not scattered.

**Fallback (no weather data):** `R_weather = 0.0`, `weather_fallback = True` in result.

### 3.5 Sub-Score: R_route (weight 0.20)

**Goal:** quantify inherent route risk from distance/duration and known disruption intersections.

**Inputs used:**
- `Route.distance_km`
- `Route.typical_duration_hours`
- `Route.highways` (JSON text list — deserialized via `get_highways_list()`)
- `Disruption.affected_corridor`

**Algorithm:**

1. Find candidate routes matching the shipment's `origin` and `destination` by string equality
   (MD-05). Use the first match; if none, return `R_route = 0.5` with a `no_route_match` flag
   (not 0.0, because absence of route data should not falsely suppress risk).
2. Normalize route duration against a reference maximum of 48 hours:
   ```
   duration_risk = min(typical_duration_hours / 48.0, 1.0)
   ```
3. Check whether any active disruption's `affected_corridor` is a substring of any highway
   name in the route's highway list (case-insensitive string match). If a match exists, add
   a `corridor_overlap_penalty`:
   - per matching disruption: `severity_weight` (same map as R_disruption)
   - `corridor_overlap = min(sum of matched severity weights, 1.0)`
4. Combine:
   ```
   R_route = (0.5 × duration_risk) + (0.5 × corridor_overlap)
   ```

**Fallback (no route match):** `R_route = 0.5`, `route_fallback = True`.

### 3.6 Sub-Score: R_cold_chain (weight 0.15)

**Goal:** quantify cold-chain integrity risk from current telemetry.

**Inputs used:** Result from the Cold-Chain Engine (Section 4), specifically `ExcursionResult`.

**Algorithm:**

The Risk Engine calls the Cold-Chain Engine internally. If the Cold-Chain Engine returns a
valid result:

| Cold-Chain severity | R_cold_chain value |
|---|---|
| `OK` | `0.0` |
| `WARNING` | `0.3` |
| `HIGH` | `0.6` |
| `CRITICAL` | `1.0` |

**Fallback (no telemetry for this shipment):** `R_cold_chain = 0.0`, `cold_chain_fallback = True`.

This represents an assumption: a shipment with no telemetry data has unknown, not elevated,
cold-chain risk. The flag alerts operators that monitoring is absent.

### 3.7 Sub-Score: R_business (weight 0.10)

**Goal:** approximate business exposure and urgency based on available data.

**No cargo value, SLA, or customer priority fields exist in Step 1 models.** This is a
prototype approximation documented in MD-09 / R_business section.

**Inputs used:**
- `Shipment.cargo_type` — categorical urgency
- `Shipment.estimated_arrival` — time pressure

**Algorithm:**

1. Cargo-type urgency map (centralized, easy to replace with real SLA data):
   - `"Biologics & Vaccines"` → `1.0`
   - `"Pharmaceuticals"` → `0.8`
   - `"Fresh Seafood"` → `0.5`
   - all others → `0.3`
2. If `estimated_arrival` is available and in the future, compute time-pressure factor:
   ```
   hours_remaining = (estimated_arrival - now).total_seconds() / 3600
   urgency = max(0.0, 1.0 - (hours_remaining / 72.0))
   ```
   A shipment due in < 72 hours has increasing urgency; one due in ≤ 0 hours → `1.0`.
3. Combine:
   ```
   R_business = (0.6 × cargo_urgency) + (0.4 × urgency)
   ```

**Fallback (no ETA):** `urgency = 0.0`; only cargo urgency contributes.

### 3.8 ShipmentRiskResult Dataclass

```
@dataclass
ShipmentRiskResult:
  shipment_id: str
  total_score: float               # 0–100
  severity: RiskSeverity           # LOW / MEDIUM / HIGH / CRITICAL
  r_disruption: float              # 0–1
  r_weather: float                 # 0–1
  r_route: float                   # 0–1
  r_cold_chain: float              # 0–1
  r_business: float                # 0–1
  contributing_disruption_ids: list[str]    # IDs of disruptions within proximity
  weather_fallback: bool           # True if no weather station data was found
  cold_chain_fallback: bool        # True if no telemetry was found
  route_fallback: bool             # True if no route matched origin/destination
  assessed_at: datetime
```

### 3.9 RiskEngine Class Interface

Module: `src/backend/risk_engine/scorer.py`

```
class RiskEngine:
    def __init__(self, session: Session)
    def evaluate_shipment(self, shipment: Shipment) -> ShipmentRiskResult
    def evaluate_all_active(self) -> list[ShipmentRiskResult]
```

`evaluate_all_active()` queries all shipments with `status IN ('IN_TRANSIT', 'ALERT_DISRUPTION')`
and calls `evaluate_shipment()` for each.

The engine does not commit to the database. Callers (Step 3 routes) decide whether to
persist the updated `current_risk_score`.

### 3.10 Missing-Data Handling Summary

| Missing data | Fallback value | Flag |
|---|---|---|
| No active disruptions | `R_disruption = 0.0` | None needed |
| No disruption within radius | `R_disruption = 0.0` | None needed |
| No weather station | `R_weather = 0.0` | `weather_fallback = True` |
| No matching route | `R_route = 0.5` | `route_fallback = True` |
| No telemetry | `R_cold_chain = 0.0` | `cold_chain_fallback = True` |
| No ETA | `urgency = 0.0` in R_business | None needed |
| Unknown cargo type | `cargo_urgency = 0.3` | None needed |

---

## 4. Cold-Chain Engine Design

### 4.1 CargoRule Lookup

**Critical data relationship (from Step 2 discovery):**

`Shipment.cargo_category` stores the **grade** value (e.g., `"Cold Chain Grade A"`).
`CargoRule.category` stores the **cargo type name** (e.g., `"Pharmaceuticals"`).
`CargoRule.grade` stores the grade value (e.g., `"Cold Chain Grade A"`).

Therefore the lookup MUST be:

```
rule = session.query(CargoRule).filter(CargoRule.grade == shipment.cargo_category).first()
```

NOT `CargoRule.category == shipment.cargo_category`.

This is implemented in `cold_chain/rules.py` as the canonical lookup function
`resolve_cargo_rule(shipment, session)`. All callers use this single function.

**Fallback:** If no matching `CargoRule` is found, `ExcursionResult` has
`cargo_rule_found = False` and `severity = ColdChainSeverity.UNKNOWN`. The engine does not
crash and does not silently suppress the anomaly.

### 4.2 Excursion Detection

Inputs: `Telemetry.cargo_temp_c`, `CargoRule.min_temp_c`, `CargoRule.max_temp_c`.

Three conditions:

| Condition | Expression | Meaning |
|---|---|---|
| Within bounds | `min_temp_c ≤ cargo_temp_c ≤ max_temp_c` | No excursion |
| Warm excursion | `cargo_temp_c > max_temp_c` | Temperature too high |
| Cold excursion | `cargo_temp_c < min_temp_c` | Temperature too low |

`is_in_excursion = (cargo_temp_c < min_temp_c) OR (cargo_temp_c > max_temp_c)`

**Temperature deviation** (signed):
```
deviation_c = cargo_temp_c - max_temp_c     if warm excursion (positive value)
deviation_c = cargo_temp_c - min_temp_c     if cold excursion (negative value)
deviation_c = 0.0                           if within bounds
```

### 4.3 Destructive Threshold Detection

`CargoRule.max_allowable_excursion_temp_c` defines the upper temperature beyond which cargo
is permanently destroyed.

For warm excursions only (the only documented threshold direction):
```
is_destructive = cargo_temp_c > rule.max_allowable_excursion_temp_c
```

For cold excursions (below `min_temp_c`): no destructive threshold is defined in the
documentation. Cold excursions are classified by magnitude of deviation, not by a documented
destruction point. This is noted as a limitation in `docs/step2-assumptions.md`.

### 4.4 Severity Classification (MD-01)

This is a **prototype assumption** — see `docs/step2-assumptions.md` MD-01.

**Duration handling:** The seed data provides one telemetry record per shipment.
Elapsed excursion duration is not computable without a time series. Duration fields in
`ExcursionResult` will be `None` for single-record evaluations. Classification falls back
to temperature-evidence-only rules.

**Temperature-evidence severity rules (single reading, no duration history):**

For **warm excursions** (`cargo_temp_c > max_temp_c`):

| Condition | Severity |
|---|---|
| `cargo_temp_c > max_allowable_excursion_temp_c` | `CRITICAL` |
| `cargo_temp_c ≤ max_allowable_excursion_temp_c` | `WARNING` |

For **cold excursions** (`cargo_temp_c < min_temp_c`):

| Condition | Severity |
|---|---|
| `deviation_c < -10.0°C` below `min_temp_c` | `HIGH` |
| `deviation_c < 0` but `≥ -10.0°C` below `min_temp_c` | `WARNING` |

The -10°C cold-excursion boundary is a prototype assumption (MD-01). It is centralized as a
named constant `COLD_EXCURSION_HIGH_THRESHOLD_C = -10.0` in `cold_chain/rules.py`.

**Duration-based severity rules (when a duration is available, for future use):**

| Duration | Temperature | Severity |
|---|---|---|
| `≥ max_excursion_duration_minutes` OR destructive temp | — | `CRITICAL` |
| `≥ 50% of max_excursion_duration_minutes` | below/above bounds | `HIGH` |
| `< 50% of max_excursion_duration_minutes` | below/above bounds | `WARNING` |

**No excursion:** `OK`

### 4.5 ExcursionResult Dataclass

```
@dataclass
ExcursionResult:
  shipment_id: str
  telemetry_id: str | None             # None if no telemetry available
  cargo_rule_found: bool
  is_in_excursion: bool
  is_destructive: bool
  cargo_temp_c: float | None
  allowed_min_c: float | None
  allowed_max_c: float | None
  max_allowable_excursion_temp_c: float | None
  deviation_c: float | None            # signed; positive = too warm; negative = too cold
  severity: ColdChainSeverity          # OK / WARNING / HIGH / CRITICAL / UNKNOWN
  excursion_duration_minutes: int | None   # None for single-reading evaluations
  compliance_standard: str | None
  cargo_category: str
  grade: str | None
  assessed_at: datetime
```

`ColdChainSeverity` is an enum: `OK`, `WARNING`, `HIGH`, `CRITICAL`, `UNKNOWN`.

### 4.6 ColdChainEngine Class Interface

Module: `src/backend/cold_chain/engine.py`

```
class ColdChainEngine:
    def __init__(self, session: Session)
    def evaluate_shipment(self, shipment: Shipment) -> ExcursionResult
    def evaluate_all_active(self) -> list[ExcursionResult]
```

The engine queries the most recent `Telemetry` record for the shipment (by `timestamp DESC`
LIMIT 1). With the current fixture data there is exactly one record per shipment; this
ordering future-proofs the engine for time-series scenarios.

---

## 5. Route Optimizer Design

### 5.1 Canonical Formula

From `docs/architecture.md` — this formulation is canonical (MD-02). Higher score = better route.

```
Score_route = 0.30 × (1 - ETA_hat)
            + 0.20 × (1 - Cost_hat)
            + 0.25 × (1 - E_disruption_hat)
            + 0.15 × (1 - E_weather_hat)
            + 0.10 × (1 - E_cold_chain_hat)
```

All `_hat` values are min-max normalized across the candidate set.

**Weight invariant:** `0.30 + 0.20 + 0.25 + 0.15 + 0.10 == 1.00`

### 5.2 Candidate Route Selection (MD-05)

```
candidates = [route for route in all_routes
              if route.origin == shipment.origin
              AND route.destination == shipment.destination]
```

String equality is used. Case is preserved as-in the fixture (`"Chicago, IL"` etc.).

If `candidates` is empty: return `RouteOptimizerResult` with `candidates=[]` and
`no_route_found = True`. Do not evaluate unrelated routes.

**Single-route case:** If `len(candidates) == 1`, min-max normalization produces
`hat = 0.0` for all factors, so `Score_route = 1.0` (best possible, since there
is no alternative to rank against). The normalizer must handle the equal-min/max edge
case by returning `0.0` for all values when `min == max` (see Section 5.7).

### 5.3 Factor: ETA

```
raw_ETA_i = route.typical_duration_hours + total_disruption_delay_i
```

Where `total_disruption_delay_i` is the sum of `impact_delay_hours` for all disruptions
whose `affected_corridor` string appears in the route's highway list (case-insensitive
substring match). This reuses the same corridor-match logic as `R_route`.

`ETA_hat` = min-max normalize across `raw_ETA_i` values.

### 5.4 Factor: Cost (MD-03 — prototype proxy)

```
raw_Cost_i = route.distance_km
```

`Cost_hat` = min-max normalize `raw_Cost_i` across candidates.

This is explicitly documented as a proxy. No monetary data exists.

### 5.5 Factor: Disruption Exposure

```
raw_E_disruption_i = sum of (severity_weight × delay_factor) for each disruption
                     that has a corridor match against this route's highways
```

Using the same severity map and delay factor as `R_disruption`.

`E_disruption_hat` = min-max normalize across candidates.

### 5.6 Factor: Weather Exposure (MD-04)

1. Find the weather station nearest to the route's destination using Haversine.
2. Compute `road_risk` from the centralized road-condition map (same map as R_weather).
3. Compute `precip_risk = precipitation_prob_percent / 100.0`.
4. `raw_E_weather_i = (0.6 × road_risk) + (0.4 × precip_risk)`

`E_weather_hat` = min-max normalize across candidates.

**Fallback (no weather station within 500 km):** `raw_E_weather_i = 0.0`.

### 5.7 Factor: Cold-Chain Environmental Exposure

```
raw_E_cold_chain_i = heat_risk from ambient_temp_c at destination weather station
```

Using the same heat-risk calculation as `R_weather`:
```
heat_stress = max(0.0, (ambient_temp_c - 20.0) / 20.0)
raw_E_cold_chain_i = min(heat_stress, 1.0)
```

`E_cold_chain_hat` = min-max normalize across candidates.

Applies only to cold-chain shipments (`required_temp_max_c < 10°C`). For non-cold-chain
shipments, `raw_E_cold_chain_i = 0.0` for all routes.

### 5.8 Normalization

`normalizer.py` exposes:

```
min_max_normalize(values: list[float]) -> list[float]
```

- Returns a list of the same length with values in `[0.0, 1.0]`.
- If `max == min` (all values identical, or single-element list): returns `[0.0] × n`.
  This means a single route or a set of identical routes all receive `hat = 0.0`,
  which yields the highest possible score `(1 - 0.0) = 1.0` for all factors.
- If `values` is empty: raises `ValueError` — callers must check for empty candidates first.

### 5.9 Route Feasibility

A route may receive an **infeasibility warning** but is still scored. Warnings are surfaced
in `RouteScore.warnings`. A route is flagged if:

- Any weather station along the route has `road_condition = "ICY_BLOCKED"`.
- A disruption with `severity = "CRITICAL"` has a corridor match against the route's highways.

No route is silently excluded — the optimizer surfaces warnings; the caller/dispatcher decides.

### 5.10 RouteScore and RouteOptimizerResult Dataclasses

```
@dataclass
RouteScore:
  route_id: str
  route_name: str
  total_score: float              # 0–1, higher = better
  eta_hours: float                # raw ETA including delay
  eta_factor: float               # min-max normalized, 0–1
  cost_factor: float              # min-max normalized, 0–1
  disruption_factor: float        # min-max normalized, 0–1
  weather_factor: float           # min-max normalized, 0–1
  cold_chain_factor: float        # min-max normalized, 0–1
  recommended: bool               # True for the highest-scoring route
  warnings: list[str]             # human-readable feasibility flags

@dataclass
RouteOptimizerResult:
  shipment_id: str
  scored_routes: list[RouteScore]
  no_route_found: bool
  assessed_at: datetime
```

### 5.11 RouteOptimizer Class Interface

Module: `src/backend/optimizer/route_optimizer.py`

```
class RouteOptimizer:
    def __init__(self, session: Session)
    def optimize_for_shipment(self, shipment: Shipment) -> RouteOptimizerResult
```

---

## 6. Fleet Matcher Design

### 6.1 Canonical Formula

From `docs/architecture.md`:

```
Score_fleet = 0.30 × Proximity
            + 0.25 × Cargo Compatibility
            + 0.20 × Refrigeration Match
            + 0.15 × Capacity Match
            + 0.10 × Availability
```

Higher score = better match. All sub-scores are in `[0.0, 1.0]`. The combined score is
therefore naturally in `[0.0, 1.0]`.

**Weight invariant:** `0.30 + 0.25 + 0.20 + 0.15 + 0.10 == 1.00`

### 6.2 Candidate Selection

All `FleetAsset` records that are not the shipment's own `assigned_vehicle_id` are evaluated.
This deliberately excludes the vehicle already attached to the distressed shipment — the
goal is to find a *replacement or reinforcement* asset, not to score the asset already
committed.

If no candidates exist, return `FleetMatchResult` with `candidates=[]` and
`no_asset_found = True`.

### 6.3 Proximity (weight 0.30)

**Position source for fleet asset (MD fleet GPS gap):**

`FleetAsset.current_lat` / `current_lon` are populated at runtime, not from seed.
For Step 2, use the most recent `Telemetry` record's `gps_lat` / `gps_lon` for the
vehicle as the position proxy. This is looked up via:
```
telemetry = session.query(Telemetry)
              .filter(Telemetry.vehicle_id == asset.id)
              .order_by(Telemetry.timestamp.desc())
              .first()
```

If no telemetry record exists for the vehicle: `proximity_km = None`,
`proximity_score = 0.0` (penalized but not excluded).

**Proximity score:**

```
distance_km = haversine(asset_lat, asset_lon, shipment_lat, shipment_lon)
proximity_score = max(0.0, 1.0 - (distance_km / MAX_PROXIMITY_KM))
```

Where `MAX_PROXIMITY_KM = 3000.0` is a prototype constant. Assets beyond 3000 km score 0.0.

Do NOT min-max normalize proximity across the fleet. The absolute distance score is more
meaningful than a relative one when a shipment may have no nearby assets at all.

### 6.4 Cargo Compatibility (weight 0.25) — MD-06

Based on `FleetAsset.cooling_system_type` classified into a cooling tier:

**Cooling capability classification (centralized in `optimizer/fleet_matcher.py`):**

```
def classify_cooling_capability(cooling_system_type: str | None) -> CoolingCapability:
    if cooling_system_type is None:
        return CoolingCapability.AMBIENT
    normalized = cooling_system_type.lower()
    if any(keyword in normalized for keyword in ["nitrogen", "cryo", "liquid"]):
        return CoolingCapability.ULTRA_COLD
    if any(keyword in normalized for keyword in ["transicold", "thermo king", "reefer"]):
        return CoolingCapability.STANDARD_COLD
    return CoolingCapability.AMBIENT
```

`CoolingCapability` is an enum: `ULTRA_COLD`, `STANDARD_COLD`, `AMBIENT`.

**Compatibility against shipment's cargo temperature requirements:**

| Asset capability | Shipment required_temp_max_c | cargo_compat_score |
|---|---|---|
| ULTRA_COLD | ≤ -50°C (cryo) | 1.0 |
| ULTRA_COLD | -50°C to 0°C (frozen) | 0.6 (capable but overspec) |
| ULTRA_COLD | > 0°C (chilled/ambient) | 0.3 (overspec, inefficient) |
| STANDARD_COLD | ≤ -50°C (cryo) | 0.1 (incapable — wrong equipment) |
| STANDARD_COLD | -50°C to 0°C (frozen) | 1.0 |
| STANDARD_COLD | > 0°C (chilled/ambient) | 0.8 (capable) |
| AMBIENT | ≤ -50°C | 0.0 (incompatible) |
| AMBIENT | -50°C to 0°C | 0.1 (incompatible) |
| AMBIENT | > 0°C | 1.0 |

This matrix is centralized as a lookup, not scattered as if-else chains.

### 6.5 Refrigeration Match (weight 0.20)

Defined as the degree of temperature-range alignment between the fleet asset's inferred
capability and the shipment's required range (MD-06):

| Asset capability | Shipment category | refrigeration_score |
|---|---|---|
| ULTRA_COLD | Ultra Cold Chain (≤ -50°C) | 1.0 |
| ULTRA_COLD | Perishable Frozen (-50°C to -10°C) | 0.5 |
| ULTRA_COLD | Pharmaceuticals / Cold Chain A | 0.4 |
| STANDARD_COLD | Perishable Frozen | 1.0 |
| STANDARD_COLD | Pharmaceuticals / Cold Chain A | 0.9 |
| STANDARD_COLD | Ultra Cold Chain | 0.0 |
| AMBIENT | any cold-chain category | 0.0 |
| AMBIENT | no cold-chain requirement | 1.0 |

Category matching uses `Shipment.cargo_category` string (the grade value).

### 6.6 Capacity Match (weight 0.15) — MD-07

No shipment weight field exists. Use a **prototype category-based capacity estimate**,
centralized as a named constant map in `fleet_matcher.py`:

```
CATEGORY_ESTIMATED_WEIGHT_KG = {
    "Biologics & Vaccines":   500,
    "Cold Chain Grade A":    5_000,
    "Pharmaceuticals":       5_000,
    "Perishable Frozen":    15_000,
    "Fresh Seafood":        15_000,
}
DEFAULT_ESTIMATED_WEIGHT_KG = 10_000
```

These values are **explicitly labelled as prototype assumptions**. They are based on
typical logistic lot sizes for the cargo categories, not from any fixture data.

```
estimated_weight = CATEGORY_ESTIMATED_WEIGHT_KG.get(
    shipment.cargo_category, DEFAULT_ESTIMATED_WEIGHT_KG
)
capacity_ratio = min(estimated_weight / asset.capacity_kg, 1.0)  # 0 = overloaded, 1 = fits
capacity_match_score = 1.0 - capacity_ratio                       # higher = more spare capacity
```

Wait — this would reward over-large vehicles. A more balanced scoring:

```
if asset.capacity_kg < estimated_weight:
    capacity_match_score = asset.capacity_kg / estimated_weight   # below capacity → penalize
else:
    capacity_match_score = 1.0                                    # any vehicle that fits = 1.0
```

This is more operationally correct: any vehicle large enough scores full capacity marks.

### 6.7 Availability (weight 0.10)

Inputs: `FleetAsset.status`

**Availability score map** (prototype, centralized):

| Status | availability_score |
|---|---|
| `IDLE` | 1.0 |
| `ACTIVE` (not assigned to any shipment in the DB) | 0.7 |
| `ACTIVE` (assigned to another shipment) | 0.3 |
| `EN_ROUTE` | 0.2 |
| any other / unrecognized | 0.1 |

To determine "assigned to another shipment": check `session.query(Shipment).filter(
Shipment.assigned_vehicle_id == asset.id).first()`. If a shipment exists: assigned.

**Note on CONFLICT-07:** The fixture has all fleet assets with `status = "ACTIVE"` and
all assigned to shipments. The Setup Guide Scenario C states FLT-302 is "idle" but the
fixture shows it as ACTIVE/assigned. The fleet matcher will correctly compute the availability
score based on actual database state, not the narrative description.

### 6.8 Ranking

After all candidates are scored, sort by `total_score DESC`. Mark
`FleetMatchScore.recommended = True` for the highest-scoring asset only.

### 6.9 FleetMatchScore and FleetMatchResult Dataclasses

```
@dataclass
FleetMatchScore:
  asset_id: str
  vehicle_type: str
  cooling_capability: str          # "ULTRA_COLD" / "STANDARD_COLD" / "AMBIENT"
  total_score: float               # 0–1
  proximity_km: float | None
  proximity_score: float
  cargo_compat_score: float
  refrigeration_score: float
  capacity_score: float
  availability_score: float
  estimated_shipment_weight_kg: int
  asset_capacity_kg: int
  recommended: bool

@dataclass
FleetMatchResult:
  shipment_id: str
  scored_assets: list[FleetMatchScore]
  no_asset_found: bool
  assessed_at: datetime
```

### 6.10 FleetMatcher Class Interface

Module: `src/backend/optimizer/fleet_matcher.py`

```
class FleetMatcher:
    def __init__(self, session: Session)
    def match_for_shipment(self, shipment: Shipment) -> FleetMatchResult
```

---

## 7. Prototype Assumptions

All nine assumptions from the Step 2 discovery are documented here and in
`docs/step2-assumptions.md`. Each assumption is centralized in code (constants, maps)
and labelled as a prototype in comments.

### MD-01 — Cold-Chain Excursion Severity Thresholds

**Issue:** `docs/solution-overview.md` names three severity levels but provides no numeric
duration boundaries between WARNING and HIGH.

**Chosen rule:**
- Single-reading / no duration history: severity classified by temperature evidence only.
  - Warm excursion above destructive threshold → `CRITICAL`
  - Warm excursion below destructive threshold → `WARNING`
  - Cold excursion > 10°C below `min_temp_c` → `HIGH`
  - Cold excursion ≤ 10°C below `min_temp_c` → `WARNING`
- When duration data is available (future time series):
  - ≥ `max_excursion_duration_minutes` elapsed OR temp above `max_allowable_excursion_temp_c` → `CRITICAL`
  - ≥ 50% of `max_excursion_duration_minutes` elapsed → `HIGH`
  - < 50% elapsed → `WARNING`

**Rationale:** Uses only the two documented anchors. Duration-50% boundary is a reasonable
midpoint assumption.

**Limitation:** The -10°C cold-excursion threshold is invented. Production systems use
validated ISO/regulatory guidance per cargo type.

**Production requirement:** Per-cargo regulatory SOP for excursion classification.

### MD-02 — Route Score Direction

**Issue:** `docs/architecture.md` and `docs/solution-overview.md` present the Route Score
from opposing sign conventions.

**Chosen rule:** `docs/architecture.md` is canonical. `Score_route = sum of (1 - normalized_factor)`.
Higher score = preferred route.

**Rationale:** The architecture doc's `(1 - x)` form is mathematically unambiguous. The
solution-overview narrative uses the factors positively without the inversion; interpreting
that document as "minimize these factors" aligns both presentations.

### MD-03 — Route Cost Proxy

**Issue:** No monetary route cost exists in any fixture.

**Chosen rule:** `Cost_hat` is computed from `Route.distance_km` via min-max normalization.

**Rationale:** Longer distance → more fuel, tolls, and driver time.

**Limitation:** Does not reflect carrier tariffs, toll structures, or fuel prices.

**Production requirement:** Route costing API or carrier tariff table.

### MD-04 — Weather → Numeric Risk

**Issue:** No documented numeric conversion from `road_condition` string or weather fields
to a 0–1 risk value.

**Chosen rule:** Centralized map in `risk_engine/sub_scores.py` and `optimizer/route_optimizer.py`:
- `ICY_BLOCKED` → `1.0`
- `ICY` → `0.8`
- `WET` → `0.5`
- `DRY` → `0.1`
- `None` or unrecognized → `0.3`

Combined with precipitation: `road_risk × 0.5 + precip_risk × 0.3 + heat_risk × 0.2`.

**Production requirement:** Integration with a live weather API and validated meteorological
risk model.

### MD-05 — Shipment → Route Assignment

**Issue:** No `route_id` field on `Shipment`. The optimizer must determine which routes
to evaluate.

**Chosen rule:** Filter routes by `route.origin == shipment.origin AND route.destination ==
shipment.destination` (exact string equality).

**Limitation:** City names must match exactly. "Chicago, IL" and "Chicago" would not match.
Fixture data is internally consistent, so this works in Step 2.

**Production requirement:** Route entity FK on `Shipment`, or a spatial origin/destination
lookup.

### MD-06 — Fleet Cooling Capability Classification

**Issue:** `FleetAsset.cooling_system_type` is free text. No temp-range fields exist.

**Chosen rule:** Keyword classification:
- "nitrogen", "cryo", "liquid" → `ULTRA_COLD`
- "transicold", "thermo king", "reefer" → `STANDARD_COLD`
- otherwise → `AMBIENT`

Compatibility matrix is centralized in `fleet_matcher.py`.

**Production requirement:** Structured equipment specification with certified temperature
range fields.

### MD-07 — Capacity Match Estimation

**Issue:** No shipment weight field in `Shipment` or fixtures.

**Chosen rule:** Category-based prototype weight estimates centralized in `fleet_matcher.py`:
- `Biologics & Vaccines` → 500 kg
- `Cold Chain Grade A` / `Pharmaceuticals` → 5,000 kg
- `Perishable Frozen` / `Fresh Seafood` → 15,000 kg
- Default → 10,000 kg

**Limitation:** These are representative lot sizes, not actual shipment weights.

**Production requirement:** `Shipment.cargo_weight_kg` field from TMS integration.

### MD-08 — Disruption Proximity Radius

**Issue:** No radius is documented for determining whether a disruption affects a shipment
or route.

**Chosen rule:** Configurable per disruption type, centralized in `risk_engine/sub_scores.py`:
- `SEVERE_WEATHER` → 200 km
- `PORT_CONTAINER_HOLD` → 50 km
- `ROADWORK_CONGESTION` → 30 km
- default → 100 km

**Rationale:** Severe weather affects broad corridors; port holds affect specific terminals;
road work affects a narrow stretch.

**Production requirement:** Actual disruption polygon geometries via PostGIS.

### MD-09 — Risk Score Scale

**Issue:** Architecture specifies 0–100 output. Fixture `current_risk_score` values (0.22,
0.78, 0.15) are 0–1 fractions.

**Chosen rule:** Engine computes and returns scores on the 0–100 scale. Fixture seed values
are 0–1 reference fractions, not ground truth for the engine formula (the formula inputs
and weights are not sufficient to reproduce exact seed values). The `Shipment.current_risk_score`
column (0–1) is not rewritten in Step 2; Step 3 API routes will decide whether to persist
the engine output.

**Production requirement:** Align database column scale with canonical engine scale.

---

## 8. Module and File Plan

### Files to CREATE

```
src/backend/
├── risk_engine/
│   ├── __init__.py         Re-exports RiskEngine, ShipmentRiskResult, RiskSeverity
│   ├── scorer.py           RiskEngine class — orchestrates sub-scores
│   ├── sub_scores.py       Individual calculators: disruption, weather, route, cold_chain, business
│   │                       Also contains centralized constants:
│   │                         DISRUPTION_RADIUS_KM (by type)
│   │                         SEVERITY_WEIGHT_MAP
│   │                         ROAD_CONDITION_RISK_MAP
│   │                         CARGO_URGENCY_MAP
│   └── haversine.py        haversine(lat1, lon1, lat2, lon2) → float (km)
│
├── cold_chain/
│   ├── __init__.py         Re-exports ColdChainEngine, ExcursionResult, ColdChainSeverity
│   ├── engine.py           ColdChainEngine class
│   └── rules.py            resolve_cargo_rule(), classify_severity()
│                           Constants: COLD_EXCURSION_HIGH_THRESHOLD_C = -10.0
│
└── optimizer/
    ├── __init__.py         Re-exports RouteOptimizer, FleetMatcher, RouteScore, FleetMatchScore
    ├── route_optimizer.py  RouteOptimizer class
    │                       Constants: WEATHER_STATION_MAX_PROXIMITY_KM = 500
    ├── fleet_matcher.py    FleetMatcher class
    │                       Constants: CATEGORY_ESTIMATED_WEIGHT_KG, MAX_PROXIMITY_KM = 3000
    │                         CoolingCapability enum, COOLING_COMPAT_MATRIX, AVAILABILITY_SCORE_MAP
    └── normalizer.py       min_max_normalize(values) → list[float]
```

### Files to CREATE — Tests

```
src/tests/
├── test_step2_risk_engine.py
├── test_step2_cold_chain.py
├── test_step2_route_optimizer.py
└── test_step2_fleet_matcher.py
```

### Files to CREATE — Documentation

```
docs/step2-assumptions.md     Full formal record of MD-01 through MD-09
```

### Files to POTENTIALLY MODIFY

- `requirements.txt` — No new packages are needed. NumPy and Pandas are already present.
  Pure-Python Haversine and min-max normalization need only `math`. No changes expected.
- `src/backend/risk_engine/__init__.py` — Will be created new; no conflict.
- `src/backend/cold_chain/__init__.py` — Will be created new; no conflict.
- `src/backend/optimizer/__init__.py` — Will be created new; no conflict.

### Files NOT TOUCHED

`src/data/*.json`, `src/frontend/`, `src/mcp/`, `src/backend/api/`,
`src/backend/services/`, `src/backend/main.py`, `submission.yaml`, `README.md`,
`demo/`, `presentation/`

---

## 9. Test Plan

All tests use the same in-memory SQLite with `StaticPool` pattern from `test_step1.py`.
Each test module seeds the database using `seed_database()` from the Step 1 infrastructure.

### 9.1 Risk Engine Tests (`test_step2_risk_engine.py`)

| ID | Scenario | Input | Assert |
|---|---|---|---|
| RE-01 | Low-risk shipment | SHP-1001 | `severity == LOW`, `total_score ≤ 50` |
| RE-02 | Disrupted shipment | SHP-1002 + DIS-501 active | `severity ≥ HIGH`, `r_disruption > 0` |
| RE-03 | Score always in [0, 100] | All 3 shipments | `0 ≤ total_score ≤ 100` for each |
| RE-04 | Threshold boundaries | Synthetic scores 25.0, 25.1, 50.0, 50.1, 75.0, 75.1 | Correct severity label per boundary |
| RE-05 | No disruptions near shipment | SHP-1001 (only DIS-503 at Newark, far away) | `r_disruption ≈ 0.0` |
| RE-06 | Missing telemetry | Shipment with no Telemetry record in DB | `r_cold_chain == 0.0`, `cold_chain_fallback == True`, no crash |
| RE-07 | Formula weight invariant | Constant check | `0.30 + 0.25 + 0.20 + 0.15 + 0.10 == 1.00` |
| RE-08 | Sub-scores all in [0, 1] | Any shipment | Each `r_*` value in `[0.0, 1.0]` |
| RE-09 | No weather station data | Remove all weather rows | `r_weather == 0.0`, `weather_fallback == True` |
| RE-10 | No matching route | Shipment with unusual origin/destination | `r_route == 0.5`, `route_fallback == True` |

### 9.2 Cold-Chain Engine Tests (`test_step2_cold_chain.py`)

| ID | Scenario | Input | Assert |
|---|---|---|---|
| CC-01 | Within bounds — no excursion | SHP-1001 / TEL-FLT-302 (4.2°C, bounds 2–8°C) | `is_in_excursion=False`, `severity=OK` |
| CC-02 | Active warm excursion | SHP-1002 / TEL-FLT-109 (-17.2°C, max bound -18°C) | `is_in_excursion=True`, `deviation_c ≈ +0.8`, `severity=WARNING` |
| CC-03 | Safe cryo | SHP-1003 / TEL-FLT-514 (-71.4°C, bounds -80 to -60°C) | `is_in_excursion=False`, `severity=OK` |
| CC-04 | Destructive threshold breach | Synthetic: temp = max_allowable + 0.1 | `is_destructive=True`, `severity=CRITICAL` |
| CC-05 | Cold-side excursion | Synthetic: temp = min_temp_c - 15 (below by 15°C) | `is_in_excursion=True`, `deviation_c < 0`, `severity=HIGH` |
| CC-06 | Cold-side small excursion | Synthetic: temp = min_temp_c - 5 | `severity=WARNING` |
| CC-07 | Missing cargo rule | Shipment with unknown `cargo_category` | `cargo_rule_found=False`, `severity=UNKNOWN`, no crash |
| CC-08 | Grade-based lookup correctness | SHP-1002 (`cargo_category="Perishable Frozen"`) | Resolves to `CargoRule.grade="Perishable Frozen"`, correct bounds |
| CC-09 | Missing telemetry | Shipment with no Telemetry in DB | `telemetry_id=None`, `is_in_excursion=False`, no crash |
| CC-10 | Deviation is correctly signed | CC-02 (warm) and CC-05 (cold) | Warm: `deviation_c > 0`; Cold: `deviation_c < 0` |

### 9.3 Route Optimizer Tests (`test_step2_route_optimizer.py`)

| ID | Scenario | Input | Assert |
|---|---|---|---|
| RO-01 | Disruption penalizes route | RT-SEA-DEN-01 vs DIS-501 (I-90 match) | `disruption_factor > 0`, lower total score vs clean route |
| RO-02 | Blocked weather penalizes route | RT-SEA-DEN-01 vs WX-SEA-02 ICY_BLOCKED | `weather_factor > 0`, feasibility warning present |
| RO-03 | Scores bounded [0, 1] | Any route set | `0.0 ≤ total_score ≤ 1.0` |
| RO-04 | Single-route safe normalization | One-candidate set | No crash; `total_score == 1.0` (all hats = 0) |
| RO-05 | Formula weight invariant | Constant check | `0.30 + 0.20 + 0.25 + 0.15 + 0.10 == 1.00` |
| RO-06 | Recommended route is highest-scoring | Two routes scored | Only one has `recommended=True`; it has `max(total_score)` |
| RO-07 | No route for shipment | Shipment with non-matching origin/dest | `no_route_found=True`, `scored_routes=[]` |
| RO-08 | Unrelated route not evaluated | SHP-1001 (Chicago→Atlanta) | Only RT-CHI-ATL-01 evaluated; RT-SEA-DEN-01 not in result |
| RO-09 | Equal-min/max normalizer safety | All routes with identical raw factor | `hat = 0.0` for all, no division-by-zero |

### 9.4 Fleet Matcher Tests (`test_step2_fleet_matcher.py`)

| ID | Scenario | Input | Assert |
|---|---|---|---|
| FM-01 | Cryo asset preferred for cryo shipment | SHP-1003 (ultra cold), FLT-514 vs FLT-302 | FLT-514 has higher `refrigeration_score` and `cargo_compat_score` |
| FM-02 | Closest asset by telemetry GPS | SHP-1002 at Portland, FLT-109 at Portland | FLT-109 has `proximity_km ≈ 0`, highest `proximity_score` |
| FM-03 | Scores bounded [0, 1] | All assets scored | `0.0 ≤ total_score ≤ 1.0` for each |
| FM-04 | Formula weight invariant | Constant check | `0.30 + 0.25 + 0.20 + 0.15 + 0.10 == 1.00` |
| FM-05 | Missing fleet GPS | Asset with no Telemetry record | `proximity_km=None`, `proximity_score=0.0`, no crash |
| FM-06 | Undercapacity asset penalized | Asset capacity < estimated shipment weight | `capacity_score < 1.0` |
| FM-07 | Recommended asset is highest-scoring | Multiple candidates | Only one `recommended=True`; it has `max(total_score)` |
| FM-08 | No candidates | Only the distressed shipment's own vehicle | `no_asset_found=True`, `scored_assets=[]` |
| FM-09 | Standard reefer incompatible for cryo | FLT-302 (Transicold) for SHP-1003 (ultra cold) | `cargo_compat_score ≤ 0.1`, low total score |
| FM-10 | Assigned vs unassigned availability | Asset assigned to other shipment | `availability_score = 0.3` |

---

## 10. Error and Edge-Case Handling

| Situation | Engine | Handling |
|---|---|---|
| Empty candidate route list | RouteOptimizer | Return `RouteOptimizerResult(no_route_found=True, scored_routes=[])` |
| Single candidate route | RouteOptimizer | All hats = 0.0; score = 1.0 (no crash in normalizer) |
| All routes have identical ETA | RouteOptimizer | `min == max`; normalizer returns 0.0 for all |
| Empty candidate fleet list | FleetMatcher | Return `FleetMatchResult(no_asset_found=True, scored_assets=[])` |
| No telemetry for shipment | RiskEngine, ColdChainEngine | Return safe result with fallback flag |
| No weather station within range | RiskEngine, RouteOptimizer | Use 0.0 for weather factors, set flag |
| No disruptions in DB | RiskEngine, RouteOptimizer | `R_disruption = 0.0`, `E_disruption = 0.0` |
| No cargo rule matching shipment | ColdChainEngine | `cargo_rule_found=False`, `severity=UNKNOWN` |
| Shipment with `None` coordinates | RiskEngine, FleetMatcher | Skip proximity check; log warning |
| Fleet asset with `None` coordinates and no telemetry | FleetMatcher | `proximity_score=0.0` |
| `estimated_arrival` in the past | RiskEngine (R_business) | `urgency = 1.0` (overdue shipment) |
| `impact_delay_hours = None` on disruption | RiskEngine | `delay_factor = 0.0`; only severity_weight contributes |
| Division by zero in normalizer | normalizer | `min == max` → return `[0.0] × n` |
| `min_max_normalize([])` call | normalizer | Raise `ValueError` — callers must guard against empty lists |

All engines log warnings (Python `logging`) for fallback conditions. They do not raise
exceptions for missing-but-recoverable data. They raise clearly for genuinely invalid
configuration (e.g., `ValueError` for empty list passed to normalizer, which indicates a
caller bug, not runtime missing data).

---

## 11. Step 2 Acceptance Criteria

- [ ] `src/backend/risk_engine/` exists with `scorer.py`, `sub_scores.py`, `haversine.py`, `__init__.py`.
- [ ] `src/backend/cold_chain/` exists with `engine.py`, `rules.py`, `__init__.py`.
- [ ] `src/backend/optimizer/` exists with `route_optimizer.py`, `fleet_matcher.py`, `normalizer.py`, `__init__.py`.
- [ ] `docs/step2-assumptions.md` exists documenting MD-01 through MD-09.
- [ ] No engine file imports `fastapi`, `pydantic`, `mcp`, or `ibm_watsonx_ai`.
- [ ] All four engine result types are plain `@dataclass` objects.
- [ ] `RiskEngine.evaluate_shipment(SHP-1001)` returns `severity=LOW` (or consistent with the formula).
- [ ] `RiskEngine.evaluate_shipment(SHP-1002)` returns `severity=HIGH` or `CRITICAL`.
- [ ] `ColdChainEngine.evaluate_shipment(SHP-1002)` returns `is_in_excursion=True`.
- [ ] `ColdChainEngine.evaluate_shipment(SHP-1001)` returns `is_in_excursion=False`.
- [ ] `RouteOptimizer.optimize_for_shipment(SHP-1002)` returns RT-SEA-DEN-01 in results with a feasibility warning.
- [ ] `FleetMatcher.match_for_shipment(SHP-1003)` ranks FLT-514 highest.
- [ ] All pytest tests in `src/tests/test_step2_*.py` pass: 0 failures.
- [ ] `R_disruption`, `R_weather`, `R_route`, `R_cold_chain`, `R_business` each stay in `[0.0, 1.0]`.
- [ ] Risk score stays in `[0.0, 100.0]`.
- [ ] Route score stays in `[0.0, 1.0]`.
- [ ] Fleet match score stays in `[0.0, 1.0]`.
- [ ] `0.30 + 0.25 + 0.20 + 0.15 + 0.10 == 1.00` (risk weights test).
- [ ] `0.30 + 0.20 + 0.25 + 0.15 + 0.10 == 1.00` (route weights test).
- [ ] `0.30 + 0.25 + 0.20 + 0.15 + 0.10 == 1.00` (fleet weights test).
- [ ] Step 1 tests remain green: `pytest src/tests/test_step1.py` still passes.
- [ ] No fixture JSON files were modified.

---

## 12. Out of Scope

The following are explicitly deferred to later steps and must NOT appear in Step 2:

- FastAPI route handlers (`/shipments/{id}/risk`, etc.) — Step 3
- Pydantic response schemas for engine results — Step 3
- watsonx.ai / Granite 3.0 narrative generation — Step 4
- MCP server tools and IBM Bob integration — Step 5
- Next.js frontend components — Step 6
- PostGIS geometry columns and GeoAlchemy2 — future migration
- OR-Tools / Scipy vehicle routing — future if required
- Updating `Shipment.current_risk_score` in the database — Step 3 (the engine computes
  but does not persist; API routes will decide to persist)
- Carrier ranking (mentioned in solution-overview.md alongside route scoring — deferred
  to Step 3 as a separate endpoint concern)
- Docker Compose changes
- README.md / submission.yaml updates

---

## 13. Risks

### RISK-01 — Fixture Scenario C (Fleet Matching) Cannot Exactly Match Documentation
`docs/setup-guide.md` says FLT-302 is "idle" and "ranked #1" for SHP-1002. The fixture has
all fleet assets ACTIVE and assigned. FLT-302 is farther from SHP-1002 than FLT-109 (which
is already assigned). The fleet matcher will NOT produce FLT-302 as #1 from pure formula
scoring with fixture data. The Step 2 implementation should produce an internally consistent
result; the setup guide narrative is aspirational, not a formula-derived guarantee.
Mitigation: Document in `step2-assumptions.md`; adjust the setup guide narrative in Step 7.

### RISK-02 — Cargo Category ↔ CargoRule Grade Mismatch Is a Silent Failure Risk
If the grade-based lookup (`CargoRule.grade == shipment.cargo_category`) is implemented
incorrectly as a category-based lookup (`CargoRule.category == shipment.cargo_category`),
the cold-chain engine will silently find no rules and return `UNKNOWN` severity for all
shipments. This will not error — it will silently degrade. Mitigation: CC-08 test directly
validates the grade-based lookup.

### RISK-03 — Sub-score Weight Constants Must Not Drift
If weight constants are defined independently in each sub-score function rather than as a
single named constant block, they will drift. Mitigation: Define all weights as named module-level
constants in each engine file, not as inline literals. Tests RE-07, RO-05, FM-04 assert the
weight sums.

### RISK-04 — Normalizer Division-by-Zero on Single Route
If the normalizer attempts `(x - min) / (max - min)` with `min == max`, a `ZeroDivisionError`
will crash the route optimizer for any single-route candidate set. Mitigation: The normalizer
must explicitly handle `min == max` as a special case. RO-04 and RO-09 test this.

### RISK-05 — Risk Score Scale Inconsistency with Stored Values
The engine outputs 0–100 but the `Shipment.current_risk_score` column stores 0–1. If any
code compares engine output directly against stored values without scale conversion, the
comparison will be wrong. Mitigation: Document clearly in `step2-assumptions.md` (MD-09)
and in the `ShipmentRiskResult` docstring.
