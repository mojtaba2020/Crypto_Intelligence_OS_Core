from datetime import UTC, datetime, timedelta

import pytest

from crypto_intelligence_os.market_data import PointInTimeViolation, validate_decision_cutoff


def test_decision_cutoff_can_equal_decision_time() -> None:
    decision = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
    validate_decision_cutoff(data_cutoff_time=decision, decision_time=decision)


def test_future_cutoff_is_rejected() -> None:
    decision = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
    with pytest.raises(PointInTimeViolation):
        validate_decision_cutoff(
            data_cutoff_time=decision + timedelta(microseconds=1),
            decision_time=decision,
        )
