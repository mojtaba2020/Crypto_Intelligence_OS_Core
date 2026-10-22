"""Synthetic-only adversarial checks of the 13-horizon dual-target contract."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from scripts.stage6_dual_target_forecast_contract import (
    HORIZONS,
    _target_end,
    validate_dual_target_forecast,
    validate_full_13_horizon_batch,
)

DAY = 86_400
JAN_1 = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp())
JAN_2 = JAN_1 + DAY
MONDAY = int(datetime(2026, 1, 5, tzinfo=UTC).timestamp())
FEB_1 = int(datetime(2026, 2, 1, tzinfo=UTC).timestamp())


def _record(horizon: str = "1d") -> dict[str, object]:
    family, bars = HORIZONS[horizon]
    origin = MONDAY if family == "weekly" else JAN_1 if family == "monthly" else JAN_2
    return {
        "horizon": horizon,
        "origin_cutoff_utc": origin,
        "forecast_issued_at_utc": origin + 60,
        "target_end_utc": _target_end(origin, family, bars),
        "source_market_id": "bitstamp:BTCUSD:spot",
        "origin_price_usd": 100.0,
        "predicted_target_price_usd": 110.0,
        "predicted_direction": "up",
        "interval_80_low_usd": 105.0,
        "interval_80_high_usd": 115.0,
        "interval_95_low_usd": 95.0,
        "interval_95_high_usd": 125.0,
        "model_code_sha256": "a" * 64,
        "feature_code_sha256": "b" * 64,
        "dataset_manifest_sha256": "c" * 64,
    }


@pytest.mark.parametrize("horizon", list(HORIZONS))
def test_each_requested_horizon_accepts_synthetic_dual_target_only(horizon: str) -> None:
    result = validate_dual_target_forecast(_record(horizon))
    assert result["horizon"] == horizon
    assert result["predicted_direction"] == "up"
    assert result["forecast_accuracy_evaluated"] is False
    assert result["forecast_issuance_authenticated"] is False
    assert result["source_vintage_authenticated"] is False
    assert result["scientific_authorization"] == "NO_RUN"
    assert result["stage7_freeze_authorized"] is False
    assert len(str(result["local_record_sha256"])) == 64


def test_complete_batch_has_all_13_once_in_canonical_order() -> None:
    batch = validate_full_13_horizon_batch([_record(x) for x in reversed(HORIZONS)])
    assert batch["horizon_count"] == 13
    assert [r["horizon"] for r in batch["forecasts"]] == list(HORIZONS)
    assert batch["scientific_authorization"] == "NO_RUN"
    assert batch["forecast_accuracy_evaluated"] is False


def test_batch_rejects_missing_duplicate_and_extra_horizon() -> None:
    records = [_record(x) for x in HORIZONS]
    with pytest.raises(ValueError, match="All 13"):
        validate_full_13_horizon_batch(records[:-1])
    duplicate = [row.copy() for row in records]
    duplicate[-1] = duplicate[0]
    with pytest.raises(ValueError, match="Duplicated or missing"):
        validate_full_13_horizon_batch(duplicate)
    with pytest.raises(ValueError, match="All 13"):
        validate_full_13_horizon_batch([*records, records[0]])


def test_exact_flat_is_not_mislabelled_up() -> None:
    row = _record()
    row["predicted_target_price_usd"] = row["origin_price_usd"]
    row["predicted_direction"] = "flat"
    row["interval_80_low_usd"] = 95.0
    row["interval_80_high_usd"] = 105.0
    row["interval_95_low_usd"] = 90.0
    row["interval_95_high_usd"] = 110.0
    assert validate_dual_target_forecast(row)["predicted_direction"] == "flat"
    row["predicted_direction"] = "up"
    with pytest.raises(ValueError, match="contradicts"):
        validate_dual_target_forecast(row)


@pytest.mark.parametrize(
    ("target", "direction"),
    [(90.0, "up"), (110.0, "down"), (110.0, "flat"), (110.0, 1), (110.0, "hold")],
)
def test_wrong_or_invalid_price_direction_rejected(target: object, direction: object) -> None:
    row = _record()
    row["predicted_target_price_usd"] = target
    row["predicted_direction"] = direction
    if target == 90.0:
        row["interval_80_low_usd"] = 85.0
        row["interval_80_high_usd"] = 95.0
        row["interval_95_low_usd"] = 80.0
        row["interval_95_high_usd"] = 100.0
    with pytest.raises(ValueError, match="Direction"):
        validate_dual_target_forecast(row)


@pytest.mark.parametrize("field", ["origin_price_usd", "predicted_target_price_usd"])
@pytest.mark.parametrize("bad", [0, -1, math.nan, math.inf, -math.inf, True, "100", 10**400])
def test_origin_and_prediction_prices_must_be_positive_finite_numbers(
    field: str, bad: object
) -> None:
    row = _record()
    row[field] = bad
    with pytest.raises(ValueError, match=r"finite|precision"):
        validate_dual_target_forecast(row)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("interval_95_low_usd", 106.0),
        ("interval_80_low_usd", 111.0),
        ("interval_80_high_usd", 109.0),
        ("interval_95_high_usd", 114.0),
        ("interval_80_low_usd", math.nan),
        ("interval_95_high_usd", math.inf),
    ],
)
def test_invalid_or_unnested_intervals_rejected(field: str, bad: float) -> None:
    row = _record()
    row[field] = bad
    with pytest.raises(ValueError, match=r"Unnested|finite"):
        validate_dual_target_forecast(row)


def test_exact_boundary_coverage_is_allowed_as_a_schema_not_probability_proof() -> None:
    row = _record()
    row["interval_80_low_usd"] = 110
    row["interval_80_high_usd"] = 110
    row["interval_95_low_usd"] = 110
    row["interval_95_high_usd"] = 110
    checked = validate_dual_target_forecast(row)
    assert checked["forecast_accuracy_evaluated"] is False


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("forecast_issued_at_utc", JAN_2),
        ("forecast_issued_at_utc", JAN_2 + DAY),
        ("target_end_utc", JAN_2 + 2 * DAY),
        ("origin_cutoff_utc", JAN_2 + 1),
        ("forecast_issued_at_utc", True),
        ("target_end_utc", 10**400),
    ],
)
def test_issue_time_target_calendar_and_type_require_strict_order(field: str, bad: object) -> None:
    row = _record()
    row[field] = bad
    with pytest.raises(ValueError, match=r"target|issue|origin|calendar|issuance"):
        validate_dual_target_forecast(row)


def test_monthly_three_months_are_calendar_months_and_not_ninety_days() -> None:
    row = _record("3mo")
    row["origin_cutoff_utc"] = FEB_1
    row["forecast_issued_at_utc"] = FEB_1 + 60
    row["target_end_utc"] = int(datetime(2026, 5, 1, tzinfo=UTC).timestamp())
    validate_dual_target_forecast(row)
    row["target_end_utc"] = FEB_1 + 90 * DAY
    with pytest.raises(ValueError, match="mismatches"):
        validate_dual_target_forecast(row)


def test_weekly_requires_monday_and_three_week_target_end() -> None:
    row = _record("3w")
    row["origin_cutoff_utc"] = MONDAY + DAY
    row["forecast_issued_at_utc"] = MONDAY + DAY + 60
    row["target_end_utc"] = MONDAY + 22 * DAY
    with pytest.raises(ValueError, match="Noncanonical"):
        validate_dual_target_forecast(row)


@pytest.mark.parametrize(
    "field", ["model_code_sha256", "feature_code_sha256", "dataset_manifest_sha256"]
)
@pytest.mark.parametrize("digest", ["A" * 64, "g" * 64, "a" * 63, True])
def test_self_asserted_fingerprints_are_at_least_canonical(field: str, digest: object) -> None:
    row = _record()
    row[field] = digest
    with pytest.raises(ValueError, match="SHA-256"):
        validate_dual_target_forecast(row)


@pytest.mark.parametrize("source", ["coinbase:BTCUSD:spot", "bitstamp:BTCUSD:1m", True])
def test_incorrect_market_identity_does_not_enter_report(source: object) -> None:
    row = _record()
    row["source_market_id"] = source
    with pytest.raises(ValueError, match="market identity"):
        validate_dual_target_forecast(row)


@pytest.mark.parametrize("field", ["actual_price", "future_return", "target_label", "private_key"])
def test_extra_future_outcome_or_secret_field_is_rejected(field: str) -> None:
    row = _record()
    row[field] = 1337
    with pytest.raises(ValueError, match="Unexpected forecast schema"):
        validate_dual_target_forecast(row)


def test_missing_required_field_is_rejected_not_silently_defaulted() -> None:
    row = _record()
    del row["interval_95_high_usd"]
    with pytest.raises(ValueError, match="Unexpected forecast schema"):
        validate_dual_target_forecast(row)


def test_copy_of_same_record_has_stable_local_hash_but_no_authenticity() -> None:
    row = _record()
    first = validate_dual_target_forecast(row)
    second = validate_dual_target_forecast(row.copy())
    assert first["local_record_sha256"] == second["local_record_sha256"]
    second_row = row.copy()
    second_row["predicted_target_price_usd"] = 109.0
    assert (
        validate_dual_target_forecast(second_row)["local_record_sha256"]
        != first["local_record_sha256"]
    )
    assert second["forecast_issuance_authenticated"] is False


def test_no_fake_batch_from_text_or_unbounded_source() -> None:
    with pytest.raises(ValueError, match="bounded sequence"):
        validate_full_13_horizon_batch("thirteen")
    with pytest.raises(ValueError, match="All 13 requested horizons"):
        validate_full_13_horizon_batch([_record(x) for x in HORIZONS] + [{}] * 1000)


@pytest.mark.parametrize("field", ["origin_price_usd", "predicted_target_price_usd"])
def test_integer_above_binary64_exact_precision_is_not_silently_rounded(field: str) -> None:
    row = _record()
    row[field] = 2**53 + 1
    with pytest.raises(ValueError, match="integer precision"):
        validate_dual_target_forecast(row)


def test_distinct_huge_integer_prices_cannot_masquerade_as_flat_forecast() -> None:
    row = _record()
    row["origin_price_usd"] = 2**53
    row["predicted_target_price_usd"] = 2**53 + 1
    row["predicted_direction"] = "flat"
    with pytest.raises(ValueError, match="integer precision"):
        validate_dual_target_forecast(row)


def test_stateful_dict_subclass_cannot_swap_validated_sha_after_check() -> None:
    class SwappingDict(dict):
        def __getitem__(self, key: object) -> object:
            if key == "model_code_sha256":
                self.calls = getattr(self, "calls", 0) + 1
                return "a" * 64 if self.calls == 1 else "forged"
            return super().__getitem__(key)

    row = SwappingDict(_record())
    with pytest.raises(ValueError, match="Unexpected forecast schema"):
        validate_dual_target_forecast(row)


def test_deceptive_list_subclass_cannot_claim_thirteen_but_yield_fourteen() -> None:
    class DeceptiveList(list):
        def __len__(self) -> int:
            return 13

    rows = DeceptiveList([_record(h) for h in HORIZONS] + [_record("1h")])
    with pytest.raises(ValueError, match="bounded sequence"):
        validate_full_13_horizon_batch(rows)
