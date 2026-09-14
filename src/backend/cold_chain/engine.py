"""
Cold-Chain Engine — excursion detection and severity classification.

Evaluates the most recent telemetry record for a shipment against its cargo
regulatory rule and produces an ``ExcursionResult`` dataclass.

No FastAPI, Pydantic, MCP, or watsonx.ai imports are allowed in this module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from sqlalchemy.orm import Session

from src.backend.models.shipment import Shipment
from src.backend.models.telemetry import Telemetry
from src.backend.cold_chain.rules import (
    ColdChainSeverity,
    classify_severity,
    resolve_cargo_rule,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ExcursionResult:
    """
    Result produced by the Cold-Chain Engine for a single shipment evaluation.
    """

    shipment_id: str
    telemetry_id: str | None           # None if no telemetry available
    cargo_rule_found: bool
    is_in_excursion: bool
    is_destructive: bool
    cargo_temp_c: float | None
    allowed_min_c: float | None
    allowed_max_c: float | None
    max_allowable_excursion_temp_c: float | None
    deviation_c: float | None          # signed; positive = too warm; negative = too cold
    severity: ColdChainSeverity        # OK / WARNING / HIGH / CRITICAL / UNKNOWN
    excursion_duration_minutes: int | None  # None for single-reading evaluations
    compliance_standard: str | None
    cargo_category: str
    grade: str | None
    assessed_at: datetime


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ColdChainEngine:
    """
    Evaluates shipment telemetry against cargo temperature rules.

    Designed to be instantiated per-request with an active SQLAlchemy session.

    No external dependencies beyond the Python standard library and the Step 1
    ORM models.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def evaluate_shipment(self, shipment: Shipment) -> ExcursionResult:
        """
        Evaluate the cold-chain status of a single shipment.

        Queries the most recent ``Telemetry`` record (by ``timestamp DESC``).
        With the current fixture data there is one record per shipment; this
        ordering future-proofs the engine for time-series scenarios.

        Parameters
        ----------
        shipment :
            ORM ``Shipment`` object loaded from the database.

        Returns
        -------
        ExcursionResult
        """
        now = datetime.now(tz=timezone.utc)

        # ------------------------------------------------------------------
        # Step 1: Resolve cargo rule
        # ------------------------------------------------------------------
        rule = resolve_cargo_rule(shipment, self._session)

        if rule is None:
            return ExcursionResult(
                shipment_id=shipment.id,
                telemetry_id=None,
                cargo_rule_found=False,
                is_in_excursion=False,
                is_destructive=False,
                cargo_temp_c=None,
                allowed_min_c=None,
                allowed_max_c=None,
                max_allowable_excursion_temp_c=None,
                deviation_c=None,
                severity=ColdChainSeverity.UNKNOWN,
                excursion_duration_minutes=None,
                compliance_standard=None,
                cargo_category=shipment.cargo_category,
                grade=None,
                assessed_at=now,
            )

        # ------------------------------------------------------------------
        # Step 2: Retrieve most recent telemetry record
        # ------------------------------------------------------------------
        telemetry = (
            self._session.query(Telemetry)
            .filter(Telemetry.shipment_id == shipment.id)
            .order_by(Telemetry.timestamp.desc())
            .first()
        )

        if telemetry is None:
            logger.warning(
                "No telemetry found for shipment %s — cannot evaluate cold-chain status.",
                shipment.id,
            )
            return ExcursionResult(
                shipment_id=shipment.id,
                telemetry_id=None,
                cargo_rule_found=True,
                is_in_excursion=False,
                is_destructive=False,
                cargo_temp_c=None,
                allowed_min_c=rule.min_temp_c,
                allowed_max_c=rule.max_temp_c,
                max_allowable_excursion_temp_c=rule.max_allowable_excursion_temp_c,
                deviation_c=None,
                severity=ColdChainSeverity.OK,
                excursion_duration_minutes=None,
                compliance_standard=rule.compliance_standard,
                cargo_category=shipment.cargo_category,
                grade=rule.grade,
                assessed_at=now,
            )

        # ------------------------------------------------------------------
        # Step 3: Excursion detection
        # ------------------------------------------------------------------
        temp = telemetry.cargo_temp_c
        is_warm = temp > rule.max_temp_c
        is_cold = temp < rule.min_temp_c
        is_in_excursion = is_warm or is_cold

        if is_warm:
            deviation_c = temp - rule.max_temp_c   # positive
        elif is_cold:
            deviation_c = temp - rule.min_temp_c   # negative
        else:
            deviation_c = 0.0

        # ------------------------------------------------------------------
        # Step 4: Destructive threshold
        # ------------------------------------------------------------------
        is_destructive = is_warm and (temp > rule.max_allowable_excursion_temp_c)

        # ------------------------------------------------------------------
        # Step 5: Severity (single-reading path; excursion_duration = None)
        # ------------------------------------------------------------------
        severity = classify_severity(
            cargo_temp_c=temp,
            rule=rule,
            excursion_duration_minutes=None,
        )

        return ExcursionResult(
            shipment_id=shipment.id,
            telemetry_id=telemetry.telemetry_id,
            cargo_rule_found=True,
            is_in_excursion=is_in_excursion,
            is_destructive=is_destructive,
            cargo_temp_c=temp,
            allowed_min_c=rule.min_temp_c,
            allowed_max_c=rule.max_temp_c,
            max_allowable_excursion_temp_c=rule.max_allowable_excursion_temp_c,
            deviation_c=deviation_c,
            severity=severity,
            excursion_duration_minutes=None,
            compliance_standard=rule.compliance_standard,
            cargo_category=shipment.cargo_category,
            grade=rule.grade,
            assessed_at=now,
        )

    def evaluate_all_active(self) -> list[ExcursionResult]:
        """
        Evaluate all shipments with status ``IN_TRANSIT`` or
        ``ALERT_DISRUPTION``.

        Returns
        -------
        list[ExcursionResult]
        """
        active_statuses = ("IN_TRANSIT", "ALERT_DISRUPTION")
        shipments = (
            self._session.query(Shipment)
            .filter(Shipment.status.in_(active_statuses))
            .all()
        )
        return [self.evaluate_shipment(s) for s in shipments]
