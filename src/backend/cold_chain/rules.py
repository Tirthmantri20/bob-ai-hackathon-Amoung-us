"""
Cold-Chain rule resolution and severity classification.

Constants
---------
COLD_EXCURSION_HIGH_THRESHOLD_C
    Deviation below min_temp_c that triggers HIGH severity (MD-01).
    A prototype assumption — see docs/step2-assumptions.md.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from src.backend.models.cargo_rule import CargoRule
from src.backend.models.shipment import Shipment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prototype assumption MD-01: cold-excursion HIGH boundary
# ---------------------------------------------------------------------------

# A cold excursion that is MORE than this many °C below min_temp_c is HIGH.
# One that is less severe (closer to min_temp_c) is WARNING.
# This value is a prototype assumption; production systems use per-cargo SOPs.
COLD_EXCURSION_HIGH_THRESHOLD_C: float = -10.0  # MD-01


# ---------------------------------------------------------------------------
# Severity enum
# ---------------------------------------------------------------------------

class ColdChainSeverity(str, Enum):
    """Cold-chain integrity severity levels."""

    OK = "OK"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"  # No cargo rule found; cannot classify


# ---------------------------------------------------------------------------
# CargoRule lookup (canonical — all callers must use this function)
# ---------------------------------------------------------------------------

def resolve_cargo_rule(shipment: Shipment, session: "Session") -> CargoRule | None:
    """
    Return the ``CargoRule`` matching the shipment's cargo grade.

    Critical data relationship (Step 2 discovery):
      ``Shipment.cargo_category`` stores the **grade** string,
      e.g. ``"Cold Chain Grade A"`` or ``"Perishable Frozen"``.
      ``CargoRule.grade`` stores the same grade value.
      The lookup is therefore on ``CargoRule.grade``, NOT ``CargoRule.category``.

    Returns ``None`` if no matching rule exists.
    """
    rule = (
        session.query(CargoRule)
        .filter(CargoRule.grade == shipment.cargo_category)
        .first()
    )
    if rule is None:
        logger.warning(
            "No CargoRule found for shipment %s with cargo_category=%r",
            shipment.id,
            shipment.cargo_category,
        )
    return rule


# ---------------------------------------------------------------------------
# Severity classifier
# ---------------------------------------------------------------------------

def classify_severity(
    cargo_temp_c: float,
    rule: CargoRule,
    excursion_duration_minutes: int | None,
) -> ColdChainSeverity:
    """
    Classify excursion severity given current temperature and (optionally) elapsed
    excursion duration.

    With only a single telemetry reading, ``excursion_duration_minutes`` is
    ``None`` and classification falls back to temperature-evidence-only rules
    (MD-01 in docs/step2-assumptions.md).

    Parameters
    ----------
    cargo_temp_c :
        Current cargo temperature in °C.
    rule :
        Resolved ``CargoRule`` for the shipment's cargo grade.
    excursion_duration_minutes :
        Elapsed excursion duration in minutes, or ``None`` if unavailable.

    Returns
    -------
    ColdChainSeverity
    """
    within_bounds = rule.min_temp_c <= cargo_temp_c <= rule.max_temp_c
    if within_bounds:
        return ColdChainSeverity.OK

    is_warm = cargo_temp_c > rule.max_temp_c
    deviation_c = (
        cargo_temp_c - rule.max_temp_c if is_warm else cargo_temp_c - rule.min_temp_c
    )

    # ------------------------------------------------------------------
    # Duration-based classification (future time-series path)
    # ------------------------------------------------------------------
    if excursion_duration_minutes is not None:
        is_destructive = is_warm and (cargo_temp_c > rule.max_allowable_excursion_temp_c)
        if is_destructive or excursion_duration_minutes >= rule.max_excursion_duration_minutes:
            return ColdChainSeverity.CRITICAL
        halfway = rule.max_excursion_duration_minutes * 0.5
        if excursion_duration_minutes >= halfway:
            return ColdChainSeverity.HIGH
        return ColdChainSeverity.WARNING

    # ------------------------------------------------------------------
    # Temperature-evidence-only classification (single-reading path, MD-01)
    # ------------------------------------------------------------------
    if is_warm:
        if cargo_temp_c > rule.max_allowable_excursion_temp_c:
            return ColdChainSeverity.CRITICAL
        return ColdChainSeverity.WARNING
    else:
        # Cold excursion: deviation_c is negative
        if deviation_c < COLD_EXCURSION_HIGH_THRESHOLD_C:
            return ColdChainSeverity.HIGH
        return ColdChainSeverity.WARNING
