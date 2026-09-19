import pytest

from crypto_intelligence_os.core.ids import is_valid_id, new_id, stable_id


def test_new_id_is_valid_and_unique() -> None:
    first = new_id("trace")
    second = new_id("trace")
    assert first != second
    assert is_valid_id(first)
    assert is_valid_id(second)


@pytest.mark.parametrize("prefix", ["X", "1bad", "bad-dash", "a", "bad space"])
def test_new_id_rejects_invalid_prefix(prefix: str) -> None:
    with pytest.raises(ValueError):
        new_id(prefix)


def test_stable_id_is_deterministic_and_canonical() -> None:
    first = stable_id("bar", "coinbase|btc-usd|1h|2026-09-15T00:00:00+00:00")
    second = stable_id("bar", "coinbase|btc-usd|1h|2026-09-15T00:00:00+00:00")
    other = stable_id("bar", "coinbase|btc-usd|1h|2026-09-15T01:00:00+00:00")

    assert first == second
    assert first != other
    assert is_valid_id(first)
