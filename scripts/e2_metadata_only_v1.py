"""Stage-6 opt-in coverage of custodian-projected metadata; no prices or I/O."""

import hashlib
import json
import re
from calendar import monthrange
from datetime import UTC, datetime, timedelta

VENUES = ("bitstamp", "bitfinex")
HORIZONS = {
    "1h": (2200, ("1h", "2h", "3h", "4h", "12h")),
    "1d": (1460, ("1d", "2d", "3d")),
    "1w": (260, ("1w", "2w", "3w")),
    "1mo": (120, ("1mo", "3mo", "6mo", "1y")),
}


def _keys(obj, expected):
    if type(obj) is not dict or set(obj) != set(expected.split()):
        raise ValueError("unexpected or missing fields")


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("invalid SHA-256")


def projection_digest(rows):
    """Canonical digest of ordered projection, not of upstream OHLCV."""
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _day(value):
    dt = datetime.strptime(value, "%Y-%m-%dT00:00:00Z").replace(tzinfo=UTC)
    if dt.strftime("%Y-%m-%dT00:00:00Z") != value:
        raise ValueError("noncanonical UTC midnight")
    return dt


def _calendar(start, end, family):
    cursor = start
    if family == "1w":
        cursor -= timedelta(days=cursor.weekday())
    elif family == "1mo":
        cursor = cursor.replace(day=1)
    grid = {}
    while cursor < end:
        step = {
            "1h": timedelta(hours=1),
            "1d": timedelta(days=1),
            "1w": timedelta(days=7),
            "1mo": timedelta(days=monthrange(cursor.year, cursor.month)[1]),
        }[family]
        following = cursor + step
        if cursor >= start and following <= end:
            grid[int(cursor.timestamp())] = step.days
        cursor = following
    return grid


def audit(approval, packets, *, now=None):
    """Require caller-supplied approval; its independent authenticity is NOT verified.

    Approval must come through a separate trusted channel in actual use. This
    function verifies equality and integrity, not signatures or upstream prices.
    """
    _keys(approval, "start end development_end receipt_sha256 projections")
    _sha(approval["receipt_sha256"])
    start, end, dev = (_day(approval[k]) for k in ("start", "end", "development_end"))
    clock = now if now is not None else datetime.now(UTC)
    if clock.tzinfo is None or not (
        datetime(2014, 1, 1, tzinfo=UTC) <= start < end <= dev
        and timedelta(days=2) <= end - start <= timedelta(days=120)
        and end <= clock - timedelta(days=2)
    ):
        raise ValueError("unapproved or unbounded UTC window")
    expected = {f"{v}:{f}" for v in VENUES for f in HORIZONS}
    if type(approval["projections"]) is not dict or set(approval["projections"]) != expected:
        raise ValueError("approval must bind all eight projections")
    if type(packets) is not list or len(packets) != len(expected):
        raise ValueError("exactly eight packets required")
    grids = {f: _calendar(start, end, f) for f in HORIZONS}
    complete = {}
    upstream = {}
    for packet in packets:
        _keys(packet, "venue family rows projection_sha256 upstream_sha256")
        venue, family = packet["venue"], packet["family"]
        key = f"{venue}:{family}"
        if key not in expected or key in complete:
            raise ValueError("unknown or duplicate packet")
        binding = approval["projections"][key]
        _keys(binding, "projection_sha256 upstream_sha256")
        for field in ("projection_sha256", "upstream_sha256"):
            _sha(packet[field])
            if packet[field] != binding[field]:
                raise ValueError("approval digest mismatch")
        rows, grid = packet["rows"], grids[family]
        if type(rows) is not list or len(rows) > len(grid):
            raise ValueError("invalid row count")
        valid = set()
        previous = None
        for row in rows:
            fields = "timestamp" if family == "1h" else (
                "timestamp source_bars expected_source_bars is_complete"
            )
            _keys(row, fields)
            ts = row["timestamp"]
            if type(ts) is not int or ts not in grid or (previous is not None and ts <= previous):
                raise ValueError("out-of-window, partial, duplicate or unordered bucket")
            previous = ts
            if family != "1h":
                n, e, flag = (row[k] for k in ("source_bars", "expected_source_bars", "is_complete"))
                if (type(n) is not int or type(e) is not int or type(flag) is not bool
                        or e != grid[ts] or not 0 <= n <= e or flag != (n == e)):
                    raise ValueError("invalid completeness metadata")
                if not flag:
                    continue
            valid.add(ts)
        if projection_digest(rows) != packet["projection_sha256"]:
            raise ValueError("projection digest mismatch")
        complete[key] = valid
        upstream[key] = packet["upstream_sha256"]
    result = {}
    for family, (minimum, labels) in HORIZONS.items():
        shared = complete[f"bitstamp:{family}"] & complete[f"bitfinex:{family}"]
        streak = longest = origins = 0
        for ts in grids[family]:
            streak = streak + 1 if ts in shared else 0
            longest = max(longest, streak)
            origins += streak >= minimum
        for label in labels:
            result[label] = {
                "expected": len(grids[family]), "shared": len(shared), "longest": longest,
                "missing": len(grids[family]) - len(shared),
                "history_deficit": max(0, minimum - longest), "eligible_closes": origins,
                "exploratory": label in ("6mo", "1y"),
            }
    return {
        "status": "STAGE6_METADATA_ONLY_UNATTESTED", "horizons": result,
        "receipt_sha256": approval["receipt_sha256"], "upstream_claims": upstream,
        "independent_custody_verified": False, "upstream_prices_verified": False,
        "eligible_for_training_or_stage7": False,
    }
