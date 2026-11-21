"""Conservative point-in-time halving-cycle calendar feature for BTC V2.

The existing older hybrid model encodes pre-first-halving history as 0 days
since a halving. This isolated research feature uses explicit missingness:
before the first halving it is unknown, NOT zero.

The shared calendar contains DATE resolution only. Consequently a halving on
the cutoff's same UTC date is NOT yet eligible; it becomes usable the next UTC
day, avoiding an unverified pre-event intra-day leak. No new historic first-
observed timestamp or independent on-chain attestation is claimed.

Label-blind, research-only, no model fit, forecast, promotion or live change.
"""

from __future__ import annotations

from datetime import date

from crypto_intelligence_os.hybrid_forecasting import HALVINGS
from scripts.btc_v2_news_evidence import utc


def halving_cycle_snapshot(cutoff_utc: str) -> dict:
    """Expose past, conservatively knowable Bitcoin halving *dates* as a feature."""
    if not isinstance(cutoff_utc, str):
        raise ValueError("UTC forecast cutoff string required")
    cutoff = utc(cutoff_utc)
    issue_day: date = cutoff.date()
    eligible = [event for event in HALVINGS if event < issue_day]
    last_known = eligible[-1] if eligible else None
    elapsed = (issue_day - last_known).days if last_known is not None else None
    return {
        "cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "metric_id": "btc_halving_elapsed_days",
        "value": float(elapsed) if elapsed is not None else None,
        "has_value": elapsed is not None,
        "last_conservatively_known_halving_date": (
            last_known.isoformat() if last_known is not None else None
        ),
        "same_day_halving_excluded": any(event == issue_day for event in HALVINGS),
        "calendar_date_precision_only": True,
        "independent_chain_timestamp_verified": False,
        "train_eligible": False,
        "research_status": "OFFLINE_CYCLE_FEATURE_NO_ATTESTED_CHAIN_EVENT_TIMES",
    }
