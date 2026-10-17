"""Only synthetic two-point inputs: no venue data, fit, error scoring or OOS."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from scripts.stage6_dual_target_forecast_contract import HORIZONS, _target_end
from scripts.stage6_synthetic_baseline_adapters import (
    build_synthetic_comparator_batches,
)

JAN_2 = int(datetime(2026, 1, 2, tzinfo=UTC).timestamp())
JAN_1 = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp())
DEC_1 = int(datetime(2025, 12, 1, tzinfo=UTC).timestamp())
MONDAY = int(datetime(2026, 1, 5, tzinfo=UTC).timestamp())
DAY = 86_400
SHA = {"persistence": "a" * 64, "one_bar_momentum": "b" * 64}


def _window(horizon: str, *, previous_price: float = 100.0, price: float = 110.0) -> dict:
    family, _ = HORIZONS[horizon]
    if family == "monthly":
        origin, previous = JAN_1, DEC_1
    elif family == "weekly":
        origin, previous = MONDAY, MONDAY - 7 * DAY
    elif family == "daily":
        origin, previous = JAN_2, JAN_1
    else:
        origin, previous = JAN_2, JAN_2 - 3_600
    return {
        "horizon": horizon,
        "origin_cutoff_utc": origin,
        "previous_cutoff_utc": previous,
        "previous_price_usd": previous_price,
        "origin_price_usd": price,
        "previous_observed_at_utc": previous + 10,
        "origin_observed_at_utc": origin + 10,
        "forecast_issued_at_utc": origin + 60,
        "source_market_id": "bitstamp:BTCUSD:spot",
        "feature_code_sha256": "c" * 64,
        "dataset_manifest_sha256": "d" * 64,
    }


def _windows() -> list[dict]:
    return [_window(h) for h in HORIZONS]


def test_two_synthetic_comparators_emit_all_thirteen_validated_forecasts() -> None:
    result = build_synthetic_comparator_batches(list(reversed(_windows())), SHA)
    assert result["candidate_names"] == ["persistence", "one_bar_momentum"]
    assert result["scientific_authorization"] == "NO_RUN"
    assert result["stage7_freeze_authorized"] is False
    assert result["real_data_evaluated"] is False
    assert result["forecast_issuance_authenticated"] is False
    assert result["interval_80_95_calibrated"] is False
    assert result["candidate_superiority_evaluated"] is False
    assert result["locked_oos_access"] is False

    persistence = result["candidates"]["persistence"]
    momentum = result["candidates"]["one_bar_momentum"]
    assert persistence["horizon_count"] == momentum["horizon_count"] == 13
    assert [row["horizon"] for row in persistence["forecasts"]] == list(HORIZONS)
    assert [row["horizon"] for row in momentum["forecasts"]] == list(HORIZONS)
    for base, trend in zip(persistence["forecasts"], momentum["forecasts"], strict=True):
        assert base["predicted_target_price_usd"] == 110.0
        assert base["predicted_direction"] == "flat"
        assert trend["predicted_target_price_usd"] > 110.0
        assert trend["predicted_direction"] == "up"
        assert base["forecast_accuracy_evaluated"] is False
        assert base["local_record_sha256"] != trend["local_record_sha256"]


@pytest.mark.parametrize("horizon", list(HORIZONS))
def test_exact_calendar_target_and_before_maturity_issuance_for_all(horizon: str) -> None:
    report = build_synthetic_comparator_batches(_windows(), SHA)
    forecast = next(
        r for r in report["candidates"]["one_bar_momentum"]["forecasts"] if r["horizon"] == horizon
    )
    window = _window(horizon)
    family, bars = HORIZONS[horizon]
    assert forecast["target_end_utc"] == _target_end(window["origin_cutoff_utc"], family, bars)
    assert forecast["forecast_issued_at_utc"] < forecast["target_end_utc"]


def test_downward_and_flat_momentum_paths() -> None:
    down = build_synthetic_comparator_batches(
        [_window(h, previous_price=100.0, price=90.0) for h in HORIZONS], SHA
    )
    assert all(
        row["predicted_direction"] == "down"
        for row in down["candidates"]["one_bar_momentum"]["forecasts"]
    )
    flat = build_synthetic_comparator_batches(
        [_window(h, previous_price=100.0, price=100.0) for h in HORIZONS], SHA
    )
    assert all(
        row["predicted_direction"] == "flat"
        for row in flat["candidates"]["one_bar_momentum"]["forecasts"]
    )


def test_no_recovered_origin_when_horizon_is_missing_or_duplicated() -> None:
    with pytest.raises(ValueError, match="Exactly 13"):
        build_synthetic_comparator_batches(_windows()[:-1], SHA)
    windows = _windows()
    windows[-1] = windows[0].copy()
    with pytest.raises(ValueError, match="Missing or duplicate"):
        build_synthetic_comparator_batches(windows, SHA)


@pytest.mark.parametrize("horizon", ["1h", "1d", "1w", "3mo"])
def test_gap_or_noncanonical_previous_bar_fails_closed(horizon: str) -> None:
    windows = _windows()
    item = next(window for window in windows if window["horizon"] == horizon)
    item["previous_cutoff_utc"] -= DAY
    with pytest.raises(ValueError, match="contiguous canonical"):
        build_synthetic_comparator_batches(windows, SHA)


@pytest.mark.parametrize("horizon", ["1d", "1mo"])
def test_first_or_latest_observation_after_issuance_is_rejected(horizon: str) -> None:
    windows = _windows()
    item = next(window for window in windows if window["horizon"] == horizon)
    item["origin_observed_at_utc"] = item["forecast_issued_at_utc"] + 1
    with pytest.raises(ValueError, match="later than claimed issuance"):
        build_synthetic_comparator_batches(windows, SHA)


def test_no_hindsight_issuance_at_target_close() -> None:
    windows = _windows()
    item = windows[0]
    item["forecast_issued_at_utc"] = item["origin_cutoff_utc"] + 3_600
    with pytest.raises(ValueError, match="must precede target close"):
        build_synthetic_comparator_batches(windows, SHA)


def test_cannot_pass_actual_future_price_or_secret_in_synthetic_window() -> None:
    for field in ("actual_future_price", "future_return", "credential", "next_label"):
        windows = _windows()
        windows[0][field] = 1
        with pytest.raises(ValueError, match="exact metadata-and-price schema"):
            build_synthetic_comparator_batches(windows, SHA)


@pytest.mark.parametrize("price", [0, -10, True, "100", math.inf, math.nan, 10**400])
def test_bad_previous_synthetic_prices_fail_closed(price: object) -> None:
    windows = _windows()
    windows[0]["previous_price_usd"] = price
    with pytest.raises(ValueError, match=r"finite|precision"):
        build_synthetic_comparator_batches(windows, SHA)


def test_market_allowlist_rejects_other_venues() -> None:
    windows = _windows()
    windows[0]["source_market_id"] = "coinbase:BTCUSD:spot"
    with pytest.raises(ValueError, match="market identity"):
        build_synthetic_comparator_batches(windows, SHA)


def test_injected_code_hash_is_not_assumed_authenticated() -> None:
    windows = _windows()
    with pytest.raises(ValueError, match="digest"):
        build_synthetic_comparator_batches(
            windows, {"persistence": "g" * 64, "one_bar_momentum": "b" * 64}
        )
    with pytest.raises(ValueError, match="Both fixed"):
        build_synthetic_comparator_batches(windows, {"persistence": "a" * 64})


def test_custom_mapping_and_list_subclasses_are_not_accepted() -> None:
    class NaughtyDict(dict):
        pass

    class NaughtyList(list):
        def __len__(self) -> int:
            return 13

    windows = _windows()
    windows[0] = NaughtyDict(windows[0])
    with pytest.raises(ValueError, match="exact metadata-and-price schema"):
        build_synthetic_comparator_batches(windows, SHA)
    with pytest.raises(ValueError, match="Exactly 13"):
        build_synthetic_comparator_batches(NaughtyList(_windows()), SHA)


def test_synthetic_oversized_momentum_overflow_is_not_returned_as_a_forecast() -> None:
    windows = _windows()
    for row in windows:
        row["previous_price_usd"] = 1.0
        row["origin_price_usd"] = 1.79e308
    with pytest.raises(ValueError, match="finite positive numeric price"):
        build_synthetic_comparator_batches(windows, SHA)


def test_near_equal_one_ulp_rise_is_not_erased_by_log_cancellation() -> None:
    windows = _windows()
    row = next(item for item in windows if item["horizon"] == "12h")
    row["previous_price_usd"] = 100.0
    row["origin_price_usd"] = math.nextafter(100.0, math.inf)
    report = build_synthetic_comparator_batches(windows, SHA)
    forecasts = report["candidates"]["one_bar_momentum"]["forecasts"]
    target = next(item for item in forecasts if item["horizon"] == "12h")
    assert target["predicted_direction"] == "up"
    assert target["predicted_target_price_usd"] > row["origin_price_usd"]
    assert report["candidate_superiority_evaluated"] is False


def test_extreme_source_price_ratio_still_clamps_without_overflow() -> None:
    windows = _windows()
    for row in windows:
        row["previous_price_usd"] = 1e-100
        row["origin_price_usd"] = 100.0
    report = build_synthetic_comparator_batches(windows, SHA)
    for result in report["candidates"]["one_bar_momentum"]["forecasts"]:
        assert 100.0 < result["predicted_target_price_usd"] < 125.0


def test_subnormal_downtrend_cannot_silently_become_flat() -> None:
    windows = _windows()
    for row in windows:
        row["previous_price_usd"] = 2**-1073
        row["origin_price_usd"] = 2**-1074
    with pytest.raises(ValueError, match="lost direction to float underflow"):
        build_synthetic_comparator_batches(windows, SHA)


def test_extreme_small_but_representable_momentum_remains_down() -> None:
    windows = _windows()
    for row in windows:
        row["previous_price_usd"] = 1e-100
        row["origin_price_usd"] = 5e-101
    report = build_synthetic_comparator_batches(windows, SHA)
    assert all(
        row["predicted_direction"] == "down"
        for row in report["candidates"]["one_bar_momentum"]["forecasts"]
    )


def test_distinct_candidate_hashes_required_even_when_predictions_are_flat() -> None:
    same_digest = {"persistence": "a" * 64, "one_bar_momentum": "a" * 64}
    windows = [_window(h, previous_price=100.0, price=100.0) for h in HORIZONS]
    with pytest.raises(ValueError, match="Distinct model SHA-256"):
        build_synthetic_comparator_batches(windows, same_digest)
