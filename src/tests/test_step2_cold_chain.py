"""
Step 2 — Cold-Chain Engine tests

Run:
    pytest src/tests/test_step2_cold_chain.py -v

Coverage:
    CC-01  Within bounds — no excursion (SHP-1001 / TEL-FLT-302)
    CC-02  Active warm excursion (SHP-1002 / TEL-FLT-109, -17.2°C, max bound -18°C)
    CC-03  Safe cryo (SHP-1003 / TEL-FLT-514, -71.4°C, bounds -80 to -60°C)
    CC-04  Destructive threshold breach (synthetic)
    CC-05  Cold-side excursion with large deviation (synthetic, -15°C below min)
    CC-06  Cold-side small excursion (synthetic, -5°C below min) → WARNING
    CC-07  Missing cargo rule → cargo_rule_found=False, severity=UNKNOWN
    CC-08  Grade-based lookup (SHP-1002 cargo_category="Perishable Frozen")
    CC-09  Missing telemetry → telemetry_id=None, is_in_excursion=False
    CC-10  Deviation sign correctness (warm +, cold -)
"""

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)

from src.backend.db.database import Base
from src.backend.db.seed import seed_database
from src.backend.models.shipment import Shipment
from src.backend.models.telemetry import Telemetry
from src.backend.cold_chain.engine import ColdChainEngine, ExcursionResult
from src.backend.cold_chain.rules import ColdChainSeverity

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def db_session():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    seed_database(session)
    yield session
    session.close()


# ---------------------------------------------------------------------------
# CC-01 — SHP-1001 within bounds
# ---------------------------------------------------------------------------

def test_cc01_within_bounds(db_session):
    # TEL-FLT-302: cargo_temp_c=4.2, bounds 2–8°C → OK
    shp = db_session.get(Shipment, "SHP-1001")
    engine = ColdChainEngine(db_session)
    result = engine.evaluate_shipment(shp)
    assert result.is_in_excursion is False
    assert result.severity == ColdChainSeverity.OK
    assert result.cargo_rule_found is True
    assert result.telemetry_id == "TEL-FLT-302"


# ---------------------------------------------------------------------------
# CC-02 — SHP-1002 warm excursion
# ---------------------------------------------------------------------------

def test_cc02_warm_excursion(db_session):
    # TEL-FLT-109: cargo_temp_c=-17.2, max_temp_c=-18 → warm by +0.8°C
    # max_allowable_excursion_temp_c=-15 → not destructive → WARNING
    shp = db_session.get(Shipment, "SHP-1002")
    engine = ColdChainEngine(db_session)
    result = engine.evaluate_shipment(shp)
    assert result.is_in_excursion is True
    assert result.severity == ColdChainSeverity.WARNING
    assert result.deviation_c is not None
    assert result.deviation_c > 0.0, f"Expected positive deviation, got {result.deviation_c}"
    assert abs(result.deviation_c - 0.8) < 0.01, (
        f"Expected deviation ≈ +0.8°C, got {result.deviation_c}"
    )
    assert result.is_destructive is False


# ---------------------------------------------------------------------------
# CC-03 — SHP-1003 safe cryo
# ---------------------------------------------------------------------------

def test_cc03_safe_cryo(db_session):
    # TEL-FLT-514: cargo_temp_c=-71.4, bounds -80 to -60°C → within bounds
    shp = db_session.get(Shipment, "SHP-1003")
    engine = ColdChainEngine(db_session)
    result = engine.evaluate_shipment(shp)
    assert result.is_in_excursion is False
    assert result.severity == ColdChainSeverity.OK
    assert result.cargo_rule_found is True


# ---------------------------------------------------------------------------
# CC-04 — Destructive threshold breach (synthetic)
# ---------------------------------------------------------------------------

def test_cc04_destructive_breach(db_session):
    # Perishable Frozen: max_temp_c=-18, max_allowable=-15
    # Synthetic telemetry: temp = -14.9 → above max_allowable → CRITICAL
    shp = db_session.get(Shipment, "SHP-1002")

    # Override telemetry with synthetic record
    from datetime import datetime, timezone
    synthetic_tel = Telemetry(
        telemetry_id="TEL-SYNTHETIC-DESTRUCT",
        vehicle_id="FLT-109",
        shipment_id="SHP-1002",
        timestamp=datetime(2026, 9, 14, 0, 0, 0, tzinfo=timezone.utc),
        cargo_temp_c=-14.9,  # above max_allowable_excursion_temp_c = -15.0
    )
    db_session.add(synthetic_tel)
    db_session.flush()

    engine = ColdChainEngine(db_session)
    result = engine.evaluate_shipment(shp)
    assert result.is_in_excursion is True
    assert result.is_destructive is True
    assert result.severity == ColdChainSeverity.CRITICAL

    db_session.delete(synthetic_tel)
    db_session.flush()


# ---------------------------------------------------------------------------
# CC-05 — Cold-side excursion, large deviation → HIGH
# ---------------------------------------------------------------------------

def test_cc05_cold_excursion_high(db_session):
    # Perishable Frozen: min_temp_c=-22
    # Synthetic: temp = -22 - 15 = -37°C → deviation = -37 - (-22) = -15°C < -10°C → HIGH
    from datetime import datetime, timezone
    shp = db_session.get(Shipment, "SHP-1002")

    original_tel = (
        db_session.query(Telemetry)
        .filter(Telemetry.shipment_id == "SHP-1002")
        .order_by(Telemetry.timestamp.desc())
        .first()
    )
    original_temp = original_tel.cargo_temp_c
    original_tel.cargo_temp_c = -37.0  # 15°C below min
    db_session.flush()

    engine = ColdChainEngine(db_session)
    result = engine.evaluate_shipment(shp)
    assert result.is_in_excursion is True
    assert result.deviation_c is not None and result.deviation_c < 0.0
    assert result.severity == ColdChainSeverity.HIGH, (
        f"Expected HIGH, got {result.severity} (deviation={result.deviation_c})"
    )

    # Restore
    original_tel.cargo_temp_c = original_temp
    db_session.flush()


# ---------------------------------------------------------------------------
# CC-06 — Cold-side small excursion → WARNING
# ---------------------------------------------------------------------------

def test_cc06_cold_excursion_warning(db_session):
    # Perishable Frozen: min_temp_c=-22
    # Synthetic: temp = -22 - 5 = -27°C → deviation = -5°C > -10°C → WARNING
    shp = db_session.get(Shipment, "SHP-1002")
    original_tel = (
        db_session.query(Telemetry)
        .filter(Telemetry.shipment_id == "SHP-1002")
        .order_by(Telemetry.timestamp.desc())
        .first()
    )
    original_temp = original_tel.cargo_temp_c
    original_tel.cargo_temp_c = -27.0  # 5°C below min
    db_session.flush()

    engine = ColdChainEngine(db_session)
    result = engine.evaluate_shipment(shp)
    assert result.severity == ColdChainSeverity.WARNING, (
        f"Expected WARNING, got {result.severity}"
    )

    original_tel.cargo_temp_c = original_temp
    db_session.flush()


# ---------------------------------------------------------------------------
# CC-07 — Missing cargo rule → UNKNOWN
# ---------------------------------------------------------------------------

def test_cc07_missing_cargo_rule(db_session):
    unknown_shp = Shipment(
        id="SHP-UNKNOWN-RULE",
        origin="Anywhere, XX",
        destination="Somewhere, YY",
        cargo_type="Exotic Cargo",
        cargo_category="No Such Grade",
        required_temp_min_c=0.0,
        required_temp_max_c=10.0,
        status="IN_TRANSIT",
    )
    db_session.add(unknown_shp)
    db_session.flush()

    engine = ColdChainEngine(db_session)
    result = engine.evaluate_shipment(unknown_shp)
    assert result.cargo_rule_found is False
    assert result.severity == ColdChainSeverity.UNKNOWN
    # Engine must not crash

    db_session.delete(unknown_shp)
    db_session.flush()


# ---------------------------------------------------------------------------
# CC-08 — Grade-based lookup: SHP-1002 → "Perishable Frozen"
# ---------------------------------------------------------------------------

def test_cc08_grade_lookup(db_session):
    shp = db_session.get(Shipment, "SHP-1002")
    assert shp.cargo_category == "Perishable Frozen"
    engine = ColdChainEngine(db_session)
    result = engine.evaluate_shipment(shp)
    assert result.cargo_rule_found is True
    assert result.grade == "Perishable Frozen"
    assert result.allowed_min_c == -22.0
    assert result.allowed_max_c == -18.0


# ---------------------------------------------------------------------------
# CC-09 — Missing telemetry
# ---------------------------------------------------------------------------

def test_cc09_missing_telemetry(db_session):
    no_tel_shp = Shipment(
        id="SHP-CCNOTEL",
        origin="Nowhere, XX",
        destination="Somewhere, YY",
        cargo_type="Pharmaceuticals",
        cargo_category="Cold Chain Grade A",
        required_temp_min_c=2.0,
        required_temp_max_c=8.0,
        status="IN_TRANSIT",
    )
    db_session.add(no_tel_shp)
    db_session.flush()

    engine = ColdChainEngine(db_session)
    result = engine.evaluate_shipment(no_tel_shp)
    assert result.telemetry_id is None
    assert result.is_in_excursion is False
    # Engine must not crash

    db_session.delete(no_tel_shp)
    db_session.flush()


# ---------------------------------------------------------------------------
# CC-10 — Deviation sign correctness
# ---------------------------------------------------------------------------

def test_cc10_deviation_sign(db_session):
    # Warm case: SHP-1002 → deviation > 0
    shp_warm = db_session.get(Shipment, "SHP-1002")
    engine = ColdChainEngine(db_session)
    warm_result = engine.evaluate_shipment(shp_warm)
    assert warm_result.deviation_c is not None
    assert warm_result.deviation_c > 0.0, (
        f"Warm excursion deviation should be positive, got {warm_result.deviation_c}"
    )

    # Cold case: modify SHP-1002 telemetry to be very cold
    original_tel = (
        db_session.query(Telemetry)
        .filter(Telemetry.shipment_id == "SHP-1002")
        .order_by(Telemetry.timestamp.desc())
        .first()
    )
    original_temp = original_tel.cargo_temp_c
    original_tel.cargo_temp_c = -30.0  # below min -22°C
    db_session.flush()

    cold_result = engine.evaluate_shipment(shp_warm)
    assert cold_result.deviation_c is not None
    assert cold_result.deviation_c < 0.0, (
        f"Cold excursion deviation should be negative, got {cold_result.deviation_c}"
    )

    original_tel.cargo_temp_c = original_temp
    db_session.flush()


# ---------------------------------------------------------------------------
# evaluate_all_active integration check
# ---------------------------------------------------------------------------

def test_evaluate_all_active(db_session):
    engine = ColdChainEngine(db_session)
    results = engine.evaluate_all_active()
    assert len(results) == 3
    ids = {r.shipment_id for r in results}
    assert ids == {"SHP-1001", "SHP-1002", "SHP-1003"}
