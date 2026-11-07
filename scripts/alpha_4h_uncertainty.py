"""Past-error calibrated 4h uncertainty and ABSTAIN decisions, research only.

The forecast model has shown NO validated alpha. This layer never claims that
a nominal 90% historical interval guarantees 90% future coverage or direction.
No market fetching, no publication, no trading and no adaptive threshold search.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from scripts.alpha_4h_training_bridge import WalkForwardReport, WalkForwardScore

# These are DESIGN constants, deliberately not selected on observed outcomes.
CALIBRATION_ROWS = 32
NOMINAL_MIS_COVERAGE = 0.10
CALIBRATION_INDEX = math.ceil((CALIBRATION_ROWS + 1) * (1.0 - NOMINAL_MIS_COVERAGE)) - 1


@dataclass(frozen=True)
class CausalInterval:
    """One historical point prediction, with earlier matured residuals ONLY."""

    origin_utc: datetime
    issue_utc: datetime
    reference_usd: float
    calibration_rows: int
    threshold_abs_log_error: float
    lower_log_return: float
    upper_log_return: float
    lower_price_usd: float
    upper_price_usd: float
    signal: str  # UP / DOWN / ABSTAIN; not a trading instruction
    interval_hit: bool
    direction_correct: bool | None


@dataclass(frozen=True)
class UncertaintyAudit:
    """Historical diagnostic; NOT exchangeability or scientific approval."""

    total_scored_origins: int
    expected_origins_from_bridge: int
    without_prior_calibration: int
    calibrated_origins: int
    up_calls: int
    down_calls: int
    abstentions: int
    correct_calls: int
    interval_hits: int
    directional_call_rate_pct: float | None
    directional_hit_rate_on_calls_pct: float | None
    interval_coverage_pct: float | None
    all_bridge_expected_call_rate_pct: float
    decisions: tuple[CausalInterval, ...]


def _validate(row: WalkForwardScore) -> None:
    if not isinstance(row, WalkForwardScore):
        raise ValueError("invalid walk-forward row")
    origin, issue, observed = (
        row.origin_utc,
        row.issued_at_utc,
        row.target_first_observed_at_utc,
    )
    for moment in (origin, issue, observed):
        if (
            not isinstance(moment, datetime)
            or moment.tzinfo is None
            or moment.utcoffset() != timedelta(0)
        ):
            raise ValueError("all event clocks must be timezone-aware UTC")
    if (
        any((origin.minute, origin.second, origin.microsecond))
        or origin.hour % 4 != 0
        or issue < origin
        or issue > origin + timedelta(minutes=15)
        or observed < origin + timedelta(hours=4, minutes=15)
    ):
        raise ValueError("origin, issuance or result receipt violates 4h chronology")
    numbers = (
        row.candidate_predicted_log_return,
        row.candidate_abs_log_error,
        row.realized_log_return,
        row.reference_close_usd,
    )
    if not all(math.isfinite(v) for v in numbers) or row.reference_close_usd <= 0:
        raise ValueError("nonfinite price, label or prediction")
    expected_error = abs(row.candidate_predicted_log_return - row.realized_log_return)
    if not math.isclose(expected_error, row.candidate_abs_log_error, abs_tol=1e-12):
        raise ValueError("row error inconsistent with prediction and label")


def audit_causal_uncertainty(report: WalkForwardReport) -> UncertaintyAudit:
    """Fixed rolling 32-sample score quantile, never current/future outcomes.

    At each origin, only past historical forecast errors with outcome receipt
    no later than that origin's ISSUE may calibrate its interval. No favorable
    thresholds are selected from test outcomes. Serial dependence, source
    revision risk and prior exposure invalidate formal nominal-coverage claims.
    """
    rows = sorted(report.scored_rows, key=lambda row: row.origin_utc)
    origins: set[datetime] = set()
    for row in rows:
        _validate(row)
        if row.origin_utc in origins:
            raise ValueError("duplicate forecast origin")
        origins.add(row.origin_utc)
    expected = report.expected_slots_between_first_and_last
    if expected <= 0 or len(rows) > expected:
        raise ValueError("invalid all-slot denominator")
    if report.missing_origin_slots < 0 or report.cold_start_rows < 0:
        raise ValueError("invalid bridge accounting")
    decisions: list[CausalInterval] = []
    insufficient = 0
    for index, row in enumerate(rows):
        past = [
            previous
            for previous in rows[:index]
            if previous.target_first_observed_at_utc <= row.issued_at_utc
        ]
        if len(past) < CALIBRATION_ROWS:
            insufficient += 1
            continue
        recent = past[-CALIBRATION_ROWS:]
        residuals = sorted(item.candidate_abs_log_error for item in recent)
        threshold = residuals[CALIBRATION_INDEX]
        lower = row.candidate_predicted_log_return - threshold
        upper = row.candidate_predicted_log_return + threshold
        try:
            low_usd = row.reference_close_usd * math.exp(lower)
            high_usd = row.reference_close_usd * math.exp(upper)
        except OverflowError as exc:
            raise ValueError("nonfinite calibrated USD interval") from exc
        if not all(math.isfinite(x) and x > 0 for x in (low_usd, high_usd)):
            raise ValueError("nonfinite calibrated USD interval")
        signal = "UP" if lower > 0 else "DOWN" if upper < 0 else "ABSTAIN"
        correct = None
        if signal != "ABSTAIN":
            correct = (
                (row.realized_log_return > 0) if signal == "UP" else (row.realized_log_return < 0)
            )
        decisions.append(
            CausalInterval(
                origin_utc=row.origin_utc,
                issue_utc=row.issued_at_utc,
                reference_usd=row.reference_close_usd,
                calibration_rows=len(recent),
                threshold_abs_log_error=threshold,
                lower_log_return=lower,
                upper_log_return=upper,
                lower_price_usd=low_usd,
                upper_price_usd=high_usd,
                signal=signal,
                interval_hit=lower <= row.realized_log_return <= upper,
                direction_correct=correct,
            )
        )
    ups = sum(row.signal == "UP" for row in decisions)
    downs = sum(row.signal == "DOWN" for row in decisions)
    calls = ups + downs
    correct = sum(row.direction_correct is True for row in decisions)
    hits = sum(row.interval_hit for row in decisions)
    n = len(decisions)
    return UncertaintyAudit(
        total_scored_origins=len(rows),
        expected_origins_from_bridge=expected,
        without_prior_calibration=insufficient,
        calibrated_origins=n,
        up_calls=ups,
        down_calls=downs,
        abstentions=n - calls,
        correct_calls=correct,
        interval_hits=hits,
        directional_call_rate_pct=(100 * calls / n) if n else None,
        directional_hit_rate_on_calls_pct=(100 * correct / calls) if calls else None,
        interval_coverage_pct=(100 * hits / n) if n else None,
        all_bridge_expected_call_rate_pct=100 * calls / expected,
        decisions=tuple(decisions),
    )
