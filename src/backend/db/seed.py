"""
Seed loader for SupplyGuard AI.

Reads the 7 JSON fixture files from src/data/ and populates the database with
the canonical seed data.  All operations use a skip-if-exists strategy: if a
record with the same primary key (or, for CargoRule, the same category) already
exists it is silently skipped.  This makes the loader safe to run on every
application startup without duplicating records or overwriting runtime state
(e.g., risk scores updated by the engine between restarts).

Loading order
-------------
FK dependency order is enforced explicitly:

  1. CargoRule  — no FK dependencies
  2. Carrier    — no FK dependencies
  3. Route      — no FK dependencies
  4. Weather    — no FK dependencies
  5. FleetAsset — no FK dependencies
  6. Disruption — no FK dependencies
  7. Shipment   — FK → FleetAsset, Carrier
  8. Telemetry  — FK → FleetAsset, Shipment

Error handling
--------------
- Missing fixture file  → FileNotFoundError (startup aborted)
- Invalid JSON          → json.JSONDecodeError (startup aborted)
- Missing required key  → KeyError with record index (startup aborted)
- DB commit failure     → rolls back, re-raises (startup aborted)

Public API
----------
    seed_database(session: Session) -> None
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from src.backend.models.cargo_rule import CargoRule
from src.backend.models.carrier import Carrier
from src.backend.models.disruption import Disruption
from src.backend.models.fleet_asset import FleetAsset
from src.backend.models.route import Route
from src.backend.models.shipment import Shipment
from src.backend.models.telemetry import Telemetry
from src.backend.models.weather import Weather

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixture directory resolution
# ---------------------------------------------------------------------------

def _data_dir() -> Path:
    """
    Return the absolute path to src/data/ regardless of where the process is
    started from.  Uses this file's location as the anchor point.

    File layout:
        src/backend/db/seed.py          ← this file
        src/data/                       ← 3 levels up, then into data/
    """
    return Path(__file__).resolve().parent.parent.parent / "data"


def _load_fixture(name: str) -> List[Dict[str, Any]]:
    """Load and parse a JSON fixture file.  Raises FileNotFoundError or
    json.JSONDecodeError on failure."""
    path = _data_dir() / name
    if not path.exists():
        raise FileNotFoundError(
            f"Required fixture file not found: {path}\n"
            f"Ensure src/data/{name} exists before starting the application."
        )
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(
            f"Fixture {name} must be a JSON array at the top level, "
            f"got {type(data).__name__}."
        )
    return data


# ---------------------------------------------------------------------------
# ISO 8601 datetime helper
# ---------------------------------------------------------------------------

def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO 8601 UTC datetime string.  Returns None for None input."""
    if value is None:
        return None
    # Python 3.11+ fromisoformat handles the trailing 'Z'; for 3.10 compatibility
    # we normalise 'Z' → '+00:00' first.
    normalised = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalised)


# ---------------------------------------------------------------------------
# Individual entity seeders
# ---------------------------------------------------------------------------

def _seed_cargo_rules(session: Session, records: List[Dict[str, Any]]) -> int:
    inserted = 0
    for i, rec in enumerate(records):
        try:
            category = rec["category"]
        except KeyError as exc:
            raise KeyError(
                f"cargo_rules.json record[{i}] missing required key: {exc}"
            ) from exc

        existing = (
            session.query(CargoRule).filter_by(category=category).first()
        )
        if existing:
            logger.debug("CargoRule category=%r already exists — skipping.", category)
            continue

        session.add(
            CargoRule(
                category=category,
                grade=rec["grade"],
                min_temp_c=float(rec["min_temp_c"]),
                max_temp_c=float(rec["max_temp_c"]),
                max_excursion_duration_minutes=int(
                    rec["max_excursion_duration_minutes"]
                ),
                max_allowable_excursion_temp_c=float(
                    rec["max_allowable_excursion_temp_c"]
                ),
                humidity_max_percent=rec.get("humidity_max_percent"),
                inspection_frequency_hours=float(rec["inspection_frequency_hours"]),
                requires_continuous_logger=bool(rec["requires_continuous_logger"]),
                compliance_standard=rec.get("compliance_standard"),
            )
        )
        inserted += 1
    return inserted


def _seed_carriers(session: Session, records: List[Dict[str, Any]]) -> int:
    inserted = 0
    for i, rec in enumerate(records):
        try:
            pk = rec["carrier_id"]
        except KeyError as exc:
            raise KeyError(
                f"carriers.json record[{i}] missing required key: {exc}"
            ) from exc

        if session.get(Carrier, pk):
            logger.debug("Carrier carrier_id=%r already exists — skipping.", pk)
            continue

        certifications_raw = rec.get("certifications")
        session.add(
            Carrier(
                carrier_id=pk,
                name=rec["name"],
                contact_email=rec.get("contact_email"),
                phone=rec.get("phone"),
                compliance_rating=float(rec["compliance_rating"]),
                on_time_delivery_rate=float(rec["on_time_delivery_rate"]),
                active_fleet_size=int(rec["active_fleet_size"]),
                certifications=(
                    json.dumps(certifications_raw)
                    if certifications_raw is not None
                    else None
                ),
            )
        )
        inserted += 1
    return inserted


def _seed_routes(session: Session, records: List[Dict[str, Any]]) -> int:
    inserted = 0
    for i, rec in enumerate(records):
        try:
            pk = rec["route_id"]
        except KeyError as exc:
            raise KeyError(
                f"routes.json record[{i}] missing required key: {exc}"
            ) from exc

        if session.get(Route, pk):
            logger.debug("Route route_id=%r already exists — skipping.", pk)
            continue

        session.add(
            Route(
                route_id=pk,
                name=rec["name"],
                origin=rec["origin"],
                destination=rec["destination"],
                distance_km=float(rec["distance_km"]),
                typical_duration_hours=float(rec["typical_duration_hours"]),
                highways=(
                    json.dumps(rec["highways"]) if rec.get("highways") else None
                ),
                waypoints=(
                    json.dumps(rec["waypoints"]) if rec.get("waypoints") else None
                ),
                cold_storage_depots=(
                    json.dumps(rec["cold_storage_depots"])
                    if rec.get("cold_storage_depots")
                    else None
                ),
            )
        )
        inserted += 1
    return inserted


def _seed_weather(session: Session, records: List[Dict[str, Any]]) -> int:
    inserted = 0
    for i, rec in enumerate(records):
        try:
            pk = rec["station_id"]
        except KeyError as exc:
            raise KeyError(
                f"weather.json record[{i}] missing required key: {exc}"
            ) from exc

        if session.get(Weather, pk):
            logger.debug("Weather station_id=%r already exists — skipping.", pk)
            continue

        session.add(
            Weather(
                station_id=pk,
                location=rec["location"],
                ambient_temp_c=float(rec["ambient_temp_c"]),
                condition=rec.get("condition"),
                precipitation_prob_percent=rec.get("precipitation_prob_percent"),
                wind_speed_kmh=(
                    float(rec["wind_speed_kmh"])
                    if rec.get("wind_speed_kmh") is not None
                    else None
                ),
                road_condition=rec.get("road_condition"),
                updated_at=_parse_dt(rec.get("updated_at")),
            )
        )
        inserted += 1
    return inserted


def _seed_fleet_assets(session: Session, records: List[Dict[str, Any]]) -> int:
    inserted = 0
    for i, rec in enumerate(records):
        try:
            pk = rec["id"]
        except KeyError as exc:
            raise KeyError(
                f"fleet.json record[{i}] missing required key: {exc}"
            ) from exc

        if session.get(FleetAsset, pk):
            logger.debug("FleetAsset id=%r already exists — skipping.", pk)
            continue

        session.add(
            FleetAsset(
                id=pk,
                vehicle_type=rec["vehicle_type"],
                license_plate=rec.get("license_plate"),
                status=rec["status"],
                fuel_type=rec.get("fuel_type"),
                cooling_system_type=rec.get("cooling_system_type"),
                capacity_kg=int(rec["capacity_kg"]),
                battery_charge_percent=rec.get("battery_charge_percent"),
                fuel_level_percent=rec.get("fuel_level_percent"),
                driver_name=rec.get("driver_name"),
                telemetry_stream_id=rec.get("telemetry_stream_id"),
                # current_lat / current_lon intentionally not set from fixture.
            )
        )
        inserted += 1
    return inserted


def _seed_disruptions(session: Session, records: List[Dict[str, Any]]) -> int:
    inserted = 0
    for i, rec in enumerate(records):
        try:
            pk = rec["id"]
        except KeyError as exc:
            raise KeyError(
                f"disruptions.json record[{i}] missing required key: {exc}"
            ) from exc

        if session.get(Disruption, pk):
            logger.debug("Disruption id=%r already exists — skipping.", pk)
            continue

        coords = rec.get("coordinates", {})
        session.add(
            Disruption(
                id=pk,
                type=rec["type"],
                severity=rec["severity"],
                title=rec["title"],
                affected_corridor=rec.get("affected_corridor"),
                start_time=_parse_dt(rec["start_time"]),
                expected_end_time=_parse_dt(rec.get("expected_end_time")),
                impact_delay_hours=(
                    float(rec["impact_delay_hours"])
                    if rec.get("impact_delay_hours") is not None
                    else None
                ),
                recommended_reroute=rec.get("recommended_reroute"),
                geometry_lat=float(coords["lat"]) if coords.get("lat") is not None else None,
                geometry_lon=float(coords["lon"]) if coords.get("lon") is not None else None,
            )
        )
        inserted += 1
    return inserted


def _seed_shipments(session: Session, records: List[Dict[str, Any]]) -> int:
    inserted = 0
    for i, rec in enumerate(records):
        try:
            pk = rec["id"]
        except KeyError as exc:
            raise KeyError(
                f"shipments.json record[{i}] missing required key: {exc}"
            ) from exc

        if session.get(Shipment, pk):
            logger.debug("Shipment id=%r already exists — skipping.", pk)
            continue

        loc = rec.get("current_location", {})
        session.add(
            Shipment(
                id=pk,
                tracking_number=rec.get("tracking_number"),
                origin=rec["origin"],
                destination=rec["destination"],
                cargo_type=rec["cargo_type"],
                cargo_category=rec["cargo_category"],
                required_temp_min_c=float(rec["required_temp_min_c"]),
                required_temp_max_c=float(rec["required_temp_max_c"]),
                status=rec["status"],
                assigned_vehicle_id=rec.get("assigned_vehicle_id"),
                carrier_id=rec.get("carrier_id"),
                estimated_departure=_parse_dt(rec.get("estimated_departure")),
                estimated_arrival=_parse_dt(rec.get("estimated_arrival")),
                current_risk_score=(
                    float(rec["current_risk_score"])
                    if rec.get("current_risk_score") is not None
                    else None
                ),
                current_lat=float(loc["lat"]) if loc.get("lat") is not None else None,
                current_lon=float(loc["lon"]) if loc.get("lon") is not None else None,
                current_location_name=loc.get("name"),
            )
        )
        inserted += 1
    return inserted


def _seed_telemetry(session: Session, records: List[Dict[str, Any]]) -> int:
    inserted = 0
    for i, rec in enumerate(records):
        try:
            pk = rec["telemetry_id"]
        except KeyError as exc:
            raise KeyError(
                f"telemetry.json record[{i}] missing required key: {exc}"
            ) from exc

        if session.get(Telemetry, pk):
            logger.debug("Telemetry telemetry_id=%r already exists — skipping.", pk)
            continue

        gps = rec.get("gps", {})
        session.add(
            Telemetry(
                telemetry_id=pk,
                vehicle_id=rec["vehicle_id"],
                shipment_id=rec["shipment_id"],
                timestamp=_parse_dt(rec["timestamp"]),
                cargo_temp_c=float(rec["cargo_temp_c"]),
                cargo_temp_target_c=(
                    float(rec["cargo_temp_target_c"])
                    if rec.get("cargo_temp_target_c") is not None
                    else None
                ),
                temp_deviation_c=(
                    float(rec["temp_deviation_c"])
                    if rec.get("temp_deviation_c") is not None
                    else None
                ),
                cargo_humidity_percent=(
                    float(rec["cargo_humidity_percent"])
                    if rec.get("cargo_humidity_percent") is not None
                    else None
                ),
                reefer_compressor_status=rec.get("reefer_compressor_status"),
                door_sensor=rec.get("door_sensor"),
                vibration_g=(
                    float(rec["vibration_g"])
                    if rec.get("vibration_g") is not None
                    else None
                ),
                gps_lat=float(gps["lat"]) if gps.get("lat") is not None else None,
                gps_lon=float(gps["lon"]) if gps.get("lon") is not None else None,
                gps_speed_kmh=(
                    float(gps["speed_kmh"])
                    if gps.get("speed_kmh") is not None
                    else None
                ),
                gps_heading_deg=(
                    float(gps["heading_deg"])
                    if gps.get("heading_deg") is not None
                    else None
                ),
            )
        )
        inserted += 1
    return inserted


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def seed_database(session: Session) -> None:
    """
    Populate the database from JSON fixtures in src/data/.

    This function is idempotent: calling it multiple times will not create
    duplicate rows.  Records that already exist (identified by PK or unique
    business key) are silently skipped.

    The loading order respects FK constraints:
      CargoRule → Carrier → Route → Weather → FleetAsset → Disruption
        → Shipment → Telemetry

    Raises
    ------
    FileNotFoundError   if a required fixture file is absent.
    json.JSONDecodeError if a fixture file contains invalid JSON.
    KeyError            if a fixture record is missing a required field.
    Exception           any DB error; the session is rolled back before re-raise.
    """
    steps = [
        ("cargo_rules.json",  _seed_cargo_rules),
        ("carriers.json",     _seed_carriers),
        ("routes.json",       _seed_routes),
        ("weather.json",      _seed_weather),
        ("fleet.json",        _seed_fleet_assets),
        ("disruptions.json",  _seed_disruptions),
        ("shipments.json",    _seed_shipments),
        ("telemetry.json",    _seed_telemetry),
    ]

    try:
        total_inserted = 0
        for fixture_name, seeder_fn in steps:
            records = _load_fixture(fixture_name)
            inserted = seeder_fn(session, records)
            logger.info(
                "Seed %-25s  %d fixture records, %d inserted.",
                fixture_name,
                len(records),
                inserted,
            )
            total_inserted += inserted

        session.commit()
        logger.info("Seed complete.  Total records inserted: %d.", total_inserted)

    except Exception:
        session.rollback()
        logger.exception("Seed failed — database rolled back.")
        raise
