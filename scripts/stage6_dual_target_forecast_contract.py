"""Pure offline schema for dual-target BTC forecasts on exactly 13 UTC horizons.

This is NOT a predictor, a source-vintage authenticator, an evaluation or a
license to run models. All times, prices and digests are caller claims.
No I/O, API, provider, training or reserved/OOS access.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

HORIZONS: dict[str, tuple[str, int]] = {
    "1h": ("hourly", 1),
    "2h": ("hourly", 2),
    "3h": ("hourly", 3),
    "4h": ("hourly", 4),
    "12h": ("hourly", 12),
    "1d": ("daily", 1),
    "2d": ("daily", 2),
    "3d": ("daily", 3),
    "1w": ("weekly", 1),
    "2w": ("weekly", 2),
    "3w": ("weekly", 3),
    "1mo": ("monthly", 1),
    "3mo": ("monthly", 3),
}

REQUIRED = frozenset(
    {
        "horizon",
        "origin_cutoff_utc",
        "forecast_issued_at_utc",
        "target_end_utc",
        "source_market_id",
        "origin_price_usd",
        "predicted_target_price_usd",
        "predicted_direction",
        "interval_80_low_usd",
        "interval_80_high_usd",
        "interval_95_low_usd",
        "interval_95_high_usd",
        "model_code_sha256",
        "feature_code_sha256",
        "dataset_manifest_sha256",
    }
)
SOURCE_MARKETS = frozenset({"bitstamp:BTCUSD:spot", "bitfinex:BTCUSD:spot"})
DIRECTIONS = frozenset({"up", "down", "flat"})


def _utc_timestamp(value: object, label: str) -> tuple[int, datetime]:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{label} must be a positive UTC epoch-second integer")
    try:
        stamp = datetime.fromtimestamp(value, tz=UTC)
    except (OverflowError, ValueError, OSError) as exc:
        raise ValueError(f"{label} exceeds the supported UTC calendar") from exc
    return value, stamp


def _target_end(origin: int, family: str, bars: int) -> int:
    _, stamp = _utc_timestamp(origin, "origin")
    if family == "monthly":
        absolute_month = stamp.year * 12 + stamp.month - 1 + bars
        year, month_index = divmod(absolute_month, 12)
        try:
            return int(datetime(year, month_index + 1, 1, tzinfo=UTC).timestamp())
        except ValueError as exc:
            raise ValueError("Monthly target exceeds supported calendar") from exc
    step = {"hourly": 3_600, "daily": 86_400, "weekly": 604_800}[family]
    end = origin + bars * step
    _utc_timestamp(end, "target")
    return end


def _canonical_origin(stamp: datetime, family: str) -> bool:
    if stamp.minute or stamp.second or stamp.microsecond:
        return False
    if family == "hourly":
        return True
    if stamp.hour:
        return False
    if family == "daily":
        return True
    if family == "weekly":
        return stamp.weekday() == 0
    return stamp.day == 1


def _price(value: object, label: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be a finite positive numeric price")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label} must be finite") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be a finite positive numeric price")
    return number


def _digest(value: object, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{label} must be an exact lowercase SHA-256 hex digest")
    return value


def validate_dual_target_forecast(record: Mapping[str, object]) -> dict[str, object]:
    """Check one caller-supplied forecast WITHOUT claiming issuance or correctness."""
    if not isinstance(record, Mapping) or set(record) != REQUIRED:
        raise ValueError("Unexpected forecast schema: outcomes and extra fields are forbidden")
    horizon = record["horizon"]
    if type(horizon) is not str or horizon not in HORIZONS:
        raise ValueError("Unsupported requested forecast horizon")
    family, bars = HORIZONS[horizon]
    origin, origin_dt = _utc_timestamp(record["origin_cutoff_utc"], "origin")
    issued, _ = _utc_timestamp(record["forecast_issued_at_utc"], "issuance")
    declared_end, _ = _utc_timestamp(record["target_end_utc"], "target")
    if not _canonical_origin(origin_dt, family):
        raise ValueError("Noncanonical UTC origin for horizon calendar")
    computed_end = _target_end(origin, family, bars)
    if declared_end != computed_end:
        raise ValueError("Target end mismatches exact horizon calendar")
    if not origin < issued < computed_end:
        raise ValueError("Claimed forecast issue must precede the future target end")
    if type(record["source_market_id"]) is not str or record["source_market_id"] not in SOURCE_MARKETS:
        raise ValueError("Unrecognized BTCUSD source market identity")
    for field in ("model_code_sha256", "feature_code_sha256", "dataset_manifest_sha256"):
        _digest(record[field], field)

    origin_price = _price(record["origin_price_usd"], "origin price")
    point = _price(record["predicted_target_price_usd"], "predicted target price")
    lo80 = _price(record["interval_80_low_usd"], "80% lower")
    hi80 = _price(record["interval_80_high_usd"], "80% upper")
    lo95 = _price(record["interval_95_low_usd"], "95% lower")
    hi95 = _price(record["interval_95_high_usd"], "95% upper")
    if not lo95 <= lo80 <= point <= hi80 <= hi95:
        raise ValueError("Unnested or point-excluding 80%/95% forecast intervals")
    direction = "up" if point > origin_price else "down" if point < origin_price else "flat"
    if type(record["predicted_direction"]) is not str or record["predicted_direction"] not in DIRECTIONS:
        raise ValueError("Direction must be up, down or flat")
    if record["predicted_direction"] != direction:
        raise ValueError("Direction contradicts the predicted price and origin price")

    # Rebuild the exact closed schema; never echo arbitrary caller objects.
    normalized: dict[str, object] = {
        "horizon": horizon,
        "origin_cutoff_utc": origin,
        "forecast_issued_at_utc": issued,
        "target_end_utc": computed_end,
        "source_market_id": record["source_market_id"],
        "origin_price_usd": origin_price,
        "predicted_target_price_usd": point,
        "predicted_direction": direction,
        "interval_80_low_usd": lo80,
        "interval_80_high_usd": hi80,
        "interval_95_low_usd": lo95,
        "interval_95_high_usd": hi95,
        "model_code_sha256": record["model_code_sha256"],
        "feature_code_sha256": record["feature_code_sha256"],
        "dataset_manifest_sha256": record["dataset_manifest_sha256"],
    }
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return {
        **normalized,
        "local_record_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "status": "UNVERIFIED_DUAL_TARGET_CONTRACT_ONLY",
        "forecast_issuance_authenticated": False,
        "source_vintage_authenticated": False,
        "forecast_accuracy_evaluated": False,
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
    }


def validate_full_13_horizon_batch(
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Require exactly one complete 13-horizon set, with no partial success."""
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise ValueError("Expected a bounded sequence of all 13 forecast records")
    if len(records) != len(HORIZONS):
        raise ValueError("All 13 requested horizons must be present once")
    checked = [validate_dual_target_forecast(record) for record in records]
    seen = [str(record["horizon"]) for record in checked]
    if len(set(seen)) != len(HORIZONS) or set(seen) != set(HORIZONS):
        raise ValueError("Duplicated or missing horizon in complete forecast batch")
    order = {name: index for index, name in enumerate(HORIZONS)}
    checked.sort(key=lambda record: order[str(record["horizon"])])
    return {
        "status": "UNVERIFIED_DUAL_TARGET_BATCH_ONLY",
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
        "forecast_issuance_authenticated": False,
        "source_vintage_authenticated": False,
        "forecast_accuracy_evaluated": False,
        "horizon_count": len(checked),
        "forecasts": checked,
    }
