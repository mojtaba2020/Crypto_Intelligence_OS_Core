"""Tests for the locked preregistered hourly-regime confirmation guards."""

import copy
import json
import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from crypto_intelligence_os.adapters.market_data.historical_archive import (
    HistoricalOHLCVArchive,
    canonical_bar_fingerprint,
)
from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe
import scripts.confirm_hourly_regime_hypothesis as confirm
from scripts.confirm_hourly_regime_hypothesis import (
    _assert_exact_primary_period,
    _assert_independent_period,
    _assert_locked_walk_forward_design,
    _validate_ingestion_chain,
    _evaluate_preregistered_feature,
    _validate_locked_preregistration,
)


EXPLORATORY = "2024-01-01T00:00:00Z/2024-12-31T23:00:00Z"
PRIMARY = "2023-01-01T00:00:00Z/2023-12-31T23:00:00Z"


def test_independent_period_guard_rejects_exploratory_overlap():
    with pytest.raises(ValueError, match="overlaps the exploratory period"):
        _assert_independent_period(
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 12, 31, 23, tzinfo=UTC),
            EXPLORATORY,
        )


def test_independent_period_guard_accepts_locked_primary_year():
    _assert_independent_period(
        datetime(2023, 1, 1, tzinfo=UTC),
        datetime(2023, 12, 31, 23, tzinfo=UTC),
        EXPLORATORY,
    )


def test_exact_primary_period_guard_accepts_full_2023_archive():
    _assert_exact_primary_period(
        datetime(2023, 1, 1, tzinfo=UTC),
        datetime(2023, 12, 31, 23, tzinfo=UTC),
        PRIMARY,
    )


@pytest.mark.parametrize(
    ("first_open", "last_open"),
    [
        (
            datetime(2023, 1, 1, 1, tzinfo=UTC),
            datetime(2023, 12, 31, 23, tzinfo=UTC),
        ),
        (
            datetime(2023, 1, 1, tzinfo=UTC),
            datetime(2023, 12, 31, 22, tzinfo=UTC),
        ),
        (
            datetime(2022, 12, 31, 23, tzinfo=UTC),
            datetime(2023, 12, 31, 23, tzinfo=UTC),
        ),
    ],
)
def test_exact_primary_period_guard_rejects_partial_or_extra_archive(
    first_open, last_open
):
    with pytest.raises(ValueError, match="exactly match"):
        _assert_exact_primary_period(first_open, last_open, PRIMARY)




def _provenance_bar(hour: int) -> OHLCVBar:
    opened = datetime(2023, 1, 1, tzinfo=UTC) + timedelta(hours=hour)
    closed = opened + timedelta(hours=1)
    price = Decimal("20000")
    return OHLCVBar(
        instrument_id=confirm.INSTRUMENT_ID,
        timeframe=Timeframe.ONE_HOUR,
        status=BarStatus.FINAL,
        open_time=opened,
        close_time=closed,
        available_at=closed,
        ingested_at=datetime(2026, 9, 27, tzinfo=UTC),
        open=price,
        high=price + Decimal("10"),
        low=price - Decimal("10"),
        close=price,
        volume=Decimal("1"),
        source_id=confirm.SOURCE_ID,
    )

def _ingestion_report_for(bars):
    return {
        "status": "BITSTAMP_LONG_HISTORY_INGESTED",
        "requested_start_utc": "2023-01-01T00:00:00+00:00",
        "requested_end_utc": "2024-01-01T00:00:00+00:00",
        "source_id": confirm.SOURCE_ID,
        "instrument_id": confirm.INSTRUMENT_ID,
        "timeframe": "1h",
        "expected_count": len(bars),
        "fetched_count": len(bars),
        "stored_count": len(bars),
        "missing_count": 0,
        "first_open_utc": bars[0].open_time.isoformat(),
        "last_open_utc": bars[-1].open_time.isoformat(),
        "continuity": "PASS",
        "sqlite_integrity": "PASS",
        "canonical_data_sha256": canonical_bar_fingerprint(bars),
    }


def test_ingestion_chain_accepts_exact_archive_identity():
    bars = tuple(_provenance_bar(hour) for hour in range(4))
    fingerprint = _validate_ingestion_chain(_ingestion_report_for(bars), bars)
    assert fingerprint == canonical_bar_fingerprint(bars)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("requested_start_utc", "2022-01-01T00:00:00+00:00"),
        ("requested_end_utc", "2023-12-31T00:00:00+00:00"),
        ("canonical_data_sha256", "0" * 64),
        ("stored_count", 3),
        ("missing_count", 1),
        ("source_id", "source:other"),
    ],
)
def test_ingestion_chain_rejects_provenance_drift(field, bad_value):
    bars = tuple(_provenance_bar(hour) for hour in range(4))
    report = _ingestion_report_for(bars)
    report[field] = bad_value
    with pytest.raises(ValueError, match="chain-of-custody mismatch"):
        _validate_ingestion_chain(report, bars)

def _locked_preregistration():
    path = Path("research/prereg_range_mean_6h_down_low_vol_12h_v1.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_locked_preregistration_is_accepted_unchanged():
    _validate_locked_preregistration(_locked_preregistration())


@pytest.mark.parametrize(
    ("section", "key", "bad_value"),
    [
        ("hypothesis", "feature", "other_feature"),
        ("hypothesis", "horizon_hours", 24),
        ("hypothesis", "regime", "up__low_vol"),
        ("hypothesis", "model", "ridge_alpha_2"),
        ("hypothesis", "scaling", "global_zscore"),
        ("hypothesis", "benchmark", "zero_return"),
        ("hypothesis", "loss", "squared_error"),
        ("acceptance_rule", "minimum_regime_samples", 39),
        ("acceptance_rule", "bootstrap_method", "iid"),
        ("acceptance_rule", "calendar_block_length_days", 3),
        ("acceptance_rule", "bootstrap_repetitions", 9999),
        ("acceptance_rule", "bootstrap_seed", 1),
        ("acceptance_rule", "must_beat_persistence", False),
        ("acceptance_rule", "independent_period_required", False),
        ("acceptance_rule", "promotion_after_single_pass", True),
        ("acceptance_rule", "promotion_requires_replication", False),
        (
            "acceptance_rule",
            "primary_requirement",
            "point estimate improvement > 0",
        ),
        (
            "created_from_exploratory_dataset",
            "period",
            "2022-01-01T00:00:00Z/2022-12-31T23:00:00Z",
        ),
        (
            "confirmatory_data",
            "primary_period",
            "2022-01-01T00:00:00Z/2022-12-31T23:00:00Z",
        ),
        ("confirmatory_data", "primary_source", "OtherExchange"),
        (
            "confirmatory_data",
            "no_threshold_tuning_on_confirmatory_data",
            False,
        ),
    ],
)
def test_locked_preregistration_rejects_parameter_drift(
    section, key, bad_value
):
    prereg = copy.deepcopy(_locked_preregistration())
    prereg[section][key] = bad_value
    with pytest.raises(ValueError):
        _validate_locked_preregistration(prereg)


def test_locked_preregistration_rejects_unlocked_status():
    prereg = copy.deepcopy(_locked_preregistration())
    prereg["status"] = "EXPLORATORY"
    with pytest.raises(ValueError, match="not in locked preregistered status"):
        _validate_locked_preregistration(prereg)


def test_locked_preregistration_rejects_post_access_method_change():
    prereg = copy.deepcopy(_locked_preregistration())
    prereg["methodology_amendment_before_confirmatory_data_access"][
        "status"
    ] = "CHANGED_AFTER_DATA_ACCESS"
    with pytest.raises(ValueError, match="not locked before confirmation"):
        _validate_locked_preregistration(prereg)


def _synthetic_candles(count=900):
    candles = []
    price = 100.0
    for index in range(count):
        price *= math.exp(0.0002 * math.sin(index / 17.0))
        candles.append(
            {
                "open": price * 0.999,
                "high": price * 1.002,
                "low": price * 0.998,
                "close": price,
                "volume": 1000.0 + index,
            }
        )
    return candles


def test_walk_forward_first_prediction_ignores_future_mutation():
    candles = _synthetic_candles()
    before = _evaluate_preregistered_feature(copy.deepcopy(candles))
    assert before["origins"][0] == 720

    mutated = copy.deepcopy(candles)
    first_origin = before["origins"][0]
    first_target = first_origin + 12
    for row in mutated[first_target + 1 :]:
        row["close"] *= 50.0
        row["high"] *= 50.0
        row["low"] *= 50.0
        row["open"] *= 50.0
        row["volume"] *= 10.0

    after = _evaluate_preregistered_feature(mutated)
    assert after["model_losses"][0] == before["model_losses"][0]
    assert after["baseline_losses"][0] == before["baseline_losses"][0]
    assert after["direction_hits"][0] == before["direction_hits"][0]


def test_walk_forward_training_targets_end_at_test_origin():
    test_origin = 720
    train_origins = list(range(168, test_origin - 12 + 1))
    assert train_origins[-1] + 12 == test_origin
    assert all(origin + 12 <= test_origin for origin in train_origins)


def test_locked_walk_forward_design_is_accepted():
    _assert_locked_walk_forward_design()


def _bitstamp_bar(opened: datetime) -> OHLCVBar:
    closed = opened + timedelta(hours=1)
    return OHLCVBar(
        instrument_id=confirm.INSTRUMENT_ID,
        timeframe=Timeframe.ONE_HOUR,
        status=BarStatus.FINAL,
        open_time=opened,
        close_time=closed,
        available_at=closed,
        ingested_at=datetime(2026, 1, 1, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal("101"),
        volume=Decimal("5"),
        source_id=confirm.SOURCE_ID,
    )


@pytest.fixture(scope="module")
def primary_2023_database(tmp_path_factory):
    database = tmp_path_factory.mktemp("confirm-primary") / "primary-2023.sqlite"
    start = datetime(2023, 1, 1, tzinfo=UTC)
    bars = tuple(_bitstamp_bar(start + timedelta(hours=i)) for i in range(8760))
    with HistoricalOHLCVArchive(database) as archive:
        assert archive.persist(bars) == 8760
    return database


def test_locked_confirmation_run_writes_self_auditing_result(
    tmp_path, monkeypatch, primary_2023_database
):
    database = primary_2023_database

    origins = list(range(720, 720 + 50 * 24, 24))
    monkeypatch.setattr(
        confirm,
        "_evaluate_preregistered_feature",
        lambda candles: {
            "origins": origins,
            "model_losses": [0.01] * len(origins),
            "baseline_losses": [0.02] * len(origins),
            "direction_hits": [1] * len(origins),
        },
    )
    monkeypatch.setattr(
        confirm,
        "classify_regime",
        lambda candles, origin: confirm.TARGET_REGIME,
    )
    monkeypatch.setattr(
        confirm,
        "calendar_regime_block_bootstrap",
        lambda *args, **kwargs: {
            "gate": "PASS",
            "ci_95": [0.001, 0.02],
        },
    )

    output = tmp_path / "confirmation.json"
    result = confirm.run(
        database,
        Path("research/prereg_range_mean_6h_down_low_vol_12h_v1.json"),
        output,
    )

    assert result["decision"] == "CONFIRMATORY_PASS_PENDING_REPLICATION"
    assert result["validated_bar_count"] == 8760
    assert result["expected_primary_bar_count"] == 8760
    assert result["ridge_alpha"] == 1.0
    assert result["walk_forward_step_hours"] == 24
    assert result["calendar_block_length_days"] == 7
    assert result["bootstrap_repetitions"] == 10000
    assert result["bootstrap_seed"] == 20260927
    assert json.loads(output.read_text(encoding="utf-8")) == result


@pytest.mark.parametrize(
    ("sample_count", "gate", "model_loss", "baseline_loss", "expected"),
    [
        (39, "PASS", 0.01, 0.02, "INSUFFICIENT_SAMPLES"),
        (50, "FAIL", 0.01, 0.02, "CONFIRMATORY_FAIL"),
        (50, "PASS", 0.03, 0.02, "CONFIRMATORY_FAIL"),
    ],
)
def test_locked_confirmation_decision_contract(
    tmp_path,
    monkeypatch,
    sample_count,
    gate,
    model_loss,
    baseline_loss,
    expected,
    primary_2023_database,
):
    database = primary_2023_database

    origins = list(range(720, 720 + sample_count * 24, 24))
    monkeypatch.setattr(
        confirm,
        "_evaluate_preregistered_feature",
        lambda candles: {
            "origins": origins,
            "model_losses": [model_loss] * sample_count,
            "baseline_losses": [baseline_loss] * sample_count,
            "direction_hits": [1] * sample_count,
        },
    )
    monkeypatch.setattr(
        confirm,
        "classify_regime",
        lambda candles, origin: confirm.TARGET_REGIME,
    )
    monkeypatch.setattr(
        confirm,
        "calendar_regime_block_bootstrap",
        lambda *args, **kwargs: {
            "gate": gate,
            "ci_95": [0.001, 0.02] if gate == "PASS" else [-0.001, 0.02],
        },
    )

    result = confirm.run(
        database,
        Path("research/prereg_range_mean_6h_down_low_vol_12h_v1.json"),
        tmp_path / "decision.json",
    )
    assert result["decision"] == expected
