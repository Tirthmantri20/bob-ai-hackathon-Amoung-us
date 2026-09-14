# Step 2 Prototype Assumptions — SupplyGuard AI

**Scope:** `src/backend/risk_engine/`, `src/backend/cold_chain/`, `src/backend/optimizer/`

These nine assumptions govern implementation decisions in Step 2 where the documentation
was silent, ambiguous, or where fixture data does not match narrative descriptions.
Each assumption is centralized in code as named constants or maps, never scattered as
magic numbers, and labelled with the assumption ID in comments.

---

## MD-01 — Cold-Chain Excursion Severity Thresholds

**Issue:** `docs/solution-overview.md` names three severity levels (`WARNING`, `HIGH`,
`CRITICAL`) for cold-chain excursions but provides no numeric boundaries between them.
Duration-based classification requires a time series; the seed fixture has only one
telemetry record per shipment.

**Chosen rule (implemented in `cold_chain/rules.py`):**

*Single-reading / no duration history (current prototype path):*

| Scenario | Condition | Severity |
|---|---|---|
| Warm excursion | `cargo_temp_c > max_allowable_excursion_temp_c` | `CRITICAL` |
| Warm excursion | `cargo_temp_c ≤ max_allowable_excursion_temp_c` | `WARNING` |
| Cold excursion | deviation `< −10.0°C` below `min_temp_c` | `HIGH` |
| Cold excursion | deviation `≥ −10.0°C` below `min_temp_c` | `WARNING` |
| Within bounds | — | `OK` |

Constant: `COLD_EXCURSION_HIGH_THRESHOLD_C = -10.0` in `cold_chain/rules.py`.

*Duration-based path (future time-series):*

| Duration | Condition | Severity |
|---|---|---|
| `≥ max_excursion_duration_minutes` OR destructive temp | — | `CRITICAL` |
| `≥ 50% of max_excursion_duration_minutes` | below/above bounds | `HIGH` |
| `< 50% of max_excursion_duration_minutes` | below/above bounds | `WARNING` |

`excursion_duration_minutes` is always `None` in Step 2.

**Limitation:** The −10°C cold-excursion threshold is invented. Production systems
use validated ISO/regulatory SOPs per cargo type.

**Production requirement:** Per-cargo-grade regulatory threshold table.

---

## MD-02 — Route Score Direction

**Issue:** `docs/architecture.md` and `docs/solution-overview.md` appear to present the
Route Score from opposing sign conventions.

**Chosen rule:** `docs/architecture.md` is canonical. Formula uses `(1 − normalized_factor)`.
Higher score = preferred route.

Implemented as: `Score_route = Σ weight_i × (1 − hat_i)`

**Rationale:** The architecture doc's `(1 − x)` form is mathematically unambiguous.

**Production requirement:** None; this is a design choice, not a prototype workaround.

---

## MD-03 — Route Cost Proxy

**Issue:** No monetary route cost field exists in any fixture or model.

**Chosen rule:** `Cost_hat` is min-max normalized from `Route.distance_km`. Longer
routes are treated as more expensive.

Implemented in `optimizer/route_optimizer.py` as `raw_Cost_i = route.distance_km`.

**Limitation:** Does not reflect carrier tariffs, toll structures, or fuel prices.

**Production requirement:** Route costing API or carrier tariff table.

---

## MD-04 — Weather → Numeric Risk Mapping

**Issue:** No documented numeric conversion from `road_condition` string or weather
fields to a 0–1 risk value.

**Chosen rule (centralized in `risk_engine/sub_scores.py`):**

| `road_condition` | numeric risk |
|---|---|
| `ICY_BLOCKED` | `1.0` |
| `ICY` | `0.8` |
| `WET` | `0.5` |
| `DRY` | `0.1` |
| `None` or unrecognized | `0.3` |

Combined R_weather formula (§3.4):
`R_weather = 0.50 × road_risk + 0.30 × precip_risk + 0.20 × heat_risk`

**Additional prototype note — no geometry on Weather model:**
`docs/step2-implementation-plan.md` §3.4 specifies "find the closest weather station
using Haversine distance". The `Weather` ORM model and fixture contain no latitude/longitude
columns. Step 2 therefore uses a **conservative max-road-risk** approach: the station with
the highest `road_risk` value is used for R_weather. This is operationally conservative
(never under-estimates weather risk) and does not require geometry data.

**Production requirement:** Live weather API with geographic coverage, and geometry
columns on the Weather table.

---

## MD-05 — Shipment → Route Assignment

**Issue:** No `route_id` FK field on `Shipment`. The optimizer must determine which
routes to evaluate without an explicit link.

**Chosen rule:** Filter routes by exact string equality:
`route.origin == shipment.origin AND route.destination == shipment.destination`

City name strings must match exactly. "Chicago, IL" and "Chicago" would not match.
Fixture data is internally consistent (routes store full city names; shipments store
full city names) so this works in Step 2.

Implemented in both `risk_engine/sub_scores.py` (R_route) and
`optimizer/route_optimizer.py` (RouteOptimizer).

**Limitation:** String case and punctuation sensitivity.

**Production requirement:** `Shipment.route_id` FK, or a spatial origin/destination
lookup using PostGIS.

---

## MD-06 — Fleet Cooling Capability Classification

**Issue:** `FleetAsset.cooling_system_type` is free-form text. No structured temperature
range fields exist in the Step 1 model.

**Chosen rule (centralized in `optimizer/fleet_matcher.py`):**

| Keywords in `cooling_system_type.lower()` | `CoolingCapability` |
|---|---|
| `"nitrogen"`, `"cryo"`, `"liquid"` | `ULTRA_COLD` |
| `"transicold"`, `"thermo king"`, `"reefer"` | `STANDARD_COLD` |
| any other / `None` | `AMBIENT` |

**Fixture classification:**
- FLT-302 `"Carrier Transicold Vector 8500"` → `STANDARD_COLD`
- FLT-109 `"Thermo King Precedent S-600"` → `STANDARD_COLD`
- FLT-514 `"CryoTech Liquid Nitrogen Sub-zero System"` → `ULTRA_COLD`

**Limitation:** Depends on brand name keywords; a new brand would be classified as
`AMBIENT` unless added to the keyword list.

**Production requirement:** Structured equipment specification with certified
temperature range fields.

---

## MD-07 — Capacity Match Estimation

**Issue:** No `cargo_weight_kg` field on `Shipment` or in any fixture.

**Chosen rule (centralized in `optimizer/fleet_matcher.py`):**

| `cargo_category` | Estimated weight (kg) |
|---|---|
| `"Biologics & Vaccines"` / `"Ultra Cold Chain"` | 500 |
| `"Cold Chain Grade A"` / `"Pharmaceuticals"` | 5,000 |
| `"Perishable Frozen"` / `"Fresh Seafood"` | 15,000 |
| (default) | 10,000 |

These are representative lot sizes for their cargo categories, not actual shipment data.

**Production requirement:** `Shipment.cargo_weight_kg` from TMS integration.

---

## MD-08 — Disruption Proximity Radius

**Issue:** No documented radius for determining whether a disruption threatens a
specific shipment or route corridor.

**Chosen rule (centralized in `risk_engine/sub_scores.py`):**

| Disruption type | Radius (km) |
|---|---|
| `SEVERE_WEATHER` | 200 |
| `PORT_CONTAINER_HOLD` | 50 |
| `ROADWORK_CONGESTION` | 30 |
| (default / unrecognized) | 100 |

**Rationale:** Severe weather affects broad geographic corridors; port holds are
terminal-local; road work affects a narrow stretch.

**Production requirement:** Actual disruption polygon geometries via PostGIS
(the `geometry_lat/geometry_lon` columns are a step-1 placeholder for a future
`GEOMETRY(Point, 4326)` column).

---

## MD-09 — Risk Score Scale and Stored Values

**Issue:** `docs/architecture.md` specifies 0–100 output. Fixture seed values for
`current_risk_score` (0.22, 0.78, 0.15) are 0–1 fractions.

**Chosen rule:** The engine computes and returns scores on the 0–100 scale. The
`Shipment.current_risk_score` DB column holds 0–1 reference fractions from the fixture
seed; these are not rewritten in Step 2. Step 3 API routes will decide whether to persist
the engine output and in what scale.

**Consequence:** `RiskEngine.evaluate_shipment()` returns `total_score` in `[0.0, 100.0]`.
The stored `Shipment.current_risk_score` value of e.g. `0.78` is a fixture reference,
not a value the engine would reproduce exactly (the formula inputs and weights produce a
different number).

**Production requirement:** Align `current_risk_score` column scale to 0–100 and update
seed fixture accordingly.

---

*Last updated: Step 2 implementation*
