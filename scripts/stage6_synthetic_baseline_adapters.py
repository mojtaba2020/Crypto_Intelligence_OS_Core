"""Offline synthetic-only comparator adapters for the 13-horizon output contract.

PERSISTENCE predicts the most recently claimed price; ONE_BAR_MOMENTUM uses
only two claimed completed source bars. Neither strategy is fitted, calibrated,
approved or demonstrated accurate. No network, files, credentials or prices are
read by this module. A caller must NOT use real/restricted inputs under NO_RUN.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime

from scripts.stage6_dual_target_forecast_contract import (
    HORIZONS,
    _canonical_origin,
    _digest,
    _price,
    _target_end,
    _utc_timestamp,
    validate_full_13_horizon_batch,
)

INPUT_KEYS = frozenset(
    {
        "horizon",
        "origin_cutoff_utc",
        "previous_cutoff_utc",
        "previous_price_usd",
        "origin_price_usd",
        "previous_observed_at_utc",
        "origin_observed_at_utc",
        "forecast_issued_at_utc",
        "source_market_id",
        "feature_code_sha256",
        "dataset_manifest_sha256",
    }
)
CANDIDATES = ("persistence", "one_bar_momentum")
MODEL_HASH_KEYS = frozenset(CANDIDATES)


def _inspect_synthetic_window(window: Mapping[str, object]) -> dict[str, object]:
    """Validate two adjacent claimed completed bars without trusting the claims."""
    if type(window) is not dict or set(window) != INPUT_KEYS:
        raise ValueError("Synthetic window must have an exact metadata-and-price schema")
    horizon = window["horizon"]
    if type(horizon) is not str or horizon not in HORIZONS:
        raise ValueError("Unsupported synthetic comparison horizon")
    family, bars = HORIZONS[horizon]
    origin, origin_dt = _utc_timestamp(window["origin_cutoff_utc"], "origin")
    previous, previous_dt = _utc_timestamp(window["previous_cutoff_utc"], "previous")
    if (
        not _canonical_origin(origin_dt, family)
        or not _canonical_origin(previous_dt, family)
        or _target_end(previous, family, 1) != origin
    ):
        raise ValueError("Synthetic windows require contiguous canonical UTC bar cutoffs")
    issued, _ = _utc_timestamp(window["forecast_issued_at_utc"], "issuance")
    end = _target_end(origin, family, bars)
    if not origin < issued < end:
        raise ValueError("Synthetic forecast issuance must precede target close")

    earlier, _ = _utc_timestamp(window["previous_observed_at_utc"], "previous observation")
    latest, _ = _utc_timestamp(window["origin_observed_at_utc"], "origin observation")
    if not (previous <= earlier <= issued and origin <= latest <= issued):
        raise ValueError("Synthetic source observation later than claimed issuance")
    previous_price = _price(window["previous_price_usd"], "previous price")
    origin_price = _price(window["origin_price_usd"], "origin price")

    market = window["source_market_id"]
    # The canonical forecast validator checks the market allowlist; this
    # snapshot must remain ordinary immutable-by-value text.
    if type(market) is not str:
        raise ValueError("Synthetic market identifier must be a string")
    feature_sha = _digest(window["feature_code_sha256"], "feature code digest")
    manifest_sha = _digest(window["dataset_manifest_sha256"], "manifest digest")
    return {
        "horizon": horizon,
        "bars": bars,
        "origin_cutoff_utc": origin,
        "forecast_issued_at_utc": issued,
        "target_end_utc": end,
        "previous_price_usd": previous_price,
        "origin_price_usd": origin_price,
        "source_market_id": market,
        "feature_code_sha256": feature_sha,
        "dataset_manifest_sha256": manifest_sha,
    }


def _illustrative_intervals(point: float) -> tuple[float, float, float, float]:
    """Fixed placeholder widths. 80/95 names do NOT imply measured coverage."""
    return (point * 0.95, point * 1.05, point * 0.90, point * 1.10)


def build_synthetic_comparator_batches(
    windows: list[dict[str, object]],
    model_code_sha256: Mapping[str, object],
) -> dict[str, object]:
    """Produce exactly two model interfaces for all 13 claimed synthetic windows.

    This does not run either underlying live/research model, prove the sources,
    estimate uncertainty, compute errors or choose a winning candidate.
    """
    if type(windows) is not list or len(windows) != len(HORIZONS):
        raise ValueError("Exactly 13 synthetic windows are required")
    if type(model_code_sha256) is not dict or set(model_code_sha256) != MODEL_HASH_KEYS:
        raise ValueError("Both fixed model-code digest claims are required")
    hashes = {key: _digest(model_code_sha256[key], key) for key in CANDIDATES}

    inspected = [_inspect_synthetic_window(window) for window in windows]
    if set(str(row["horizon"]) for row in inspected) != set(HORIZONS):
        raise ValueError("Missing or duplicate synthetic horizon windows")

    candidate_outputs: dict[str, object] = {}
    for candidate in CANDIDATES:
        raw_records: list[dict[str, object]] = []
        for row in inspected:
            origin_price = float(row["origin_price_usd"])
            previous_price = float(row["previous_price_usd"])
            bars = int(row["bars"])
            if candidate == "persistence":
                point = origin_price
            else:
                # Clamp an entirely illustrative two-observation log-return
                # extrapolation to +/-20%; no learned coefficient or calibration.
                signal = bars * (math.log(origin_price) - math.log(previous_price))
                point = origin_price * math.exp(max(-0.20, min(0.20, signal)))
            if not math.isfinite(point) or point <= 0:
                raise ValueError("Synthetic comparator output is not a finite positive price")
            low80, high80, low95, high95 = _illustrative_intervals(point)
            raw_records.append(
                {
                    "horizon": row["horizon"],
                    "origin_cutoff_utc": row["origin_cutoff_utc"],
                    "forecast_issued_at_utc": row["forecast_issued_at_utc"],
                    "target_end_utc": row["target_end_utc"],
                    "source_market_id": row["source_market_id"],
                    "origin_price_usd": origin_price,
                    "predicted_target_price_usd": point,
                    "predicted_direction": (
                        "up" if point > origin_price else "down" if point < origin_price else "flat"
                    ),
                    "interval_80_low_usd": low80,
                    "interval_80_high_usd": high80,
                    "interval_95_low_usd": low95,
                    "interval_95_high_usd": high95,
                    "model_code_sha256": hashes[candidate],
                    "feature_code_sha256": row["feature_code_sha256"],
                    "dataset_manifest_sha256": row["dataset_manifest_sha256"],
                }
            )
        candidate_outputs[candidate] = validate_full_13_horizon_batch(raw_records)

    return {
        "status": "SYNTHETIC_TWO_BASELINES_ONLY",
        "candidate_names": list(CANDIDATES),
        "candidates": candidate_outputs,
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
        "real_data_evaluated": False,
        "forecast_issuance_authenticated": False,
        "interval_80_95_calibrated": False,
        "candidate_superiority_evaluated": False,
        "locked_oos_access": False,
    }
