import pytest
from pydantic import ValidationError

from crypto_intelligence_os.assets import BITCOIN, USD, AssetClass, CanonicalAsset, get_asset


def test_bitcoin_has_stable_provider_neutral_identity() -> None:
    assert BITCOIN.asset_id == "asset:bitcoin"
    assert BITCOIN.symbol == "BTC"
    assert BITCOIN.network_id == "network:bitcoin-mainnet"
    assert BITCOIN.decimals == 8
    assert get_asset("asset:bitcoin") is BITCOIN


def test_usd_is_not_bound_to_a_blockchain() -> None:
    assert USD.asset_class is AssetClass.FIAT
    assert USD.network_id is None


def test_ticker_is_not_accepted_as_canonical_asset_id() -> None:
    with pytest.raises(ValidationError):
        CanonicalAsset(
            asset_id="BTC",
            symbol="BTC",
            name="Bitcoin",
            asset_class=AssetClass.NATIVE_CRYPTO,
            network_id="network:bitcoin-mainnet",
        )


def test_native_crypto_requires_network_identity() -> None:
    with pytest.raises(ValidationError, match="network_id"):
        CanonicalAsset(
            asset_id="asset:testcoin",
            symbol="TEST",
            name="Test Coin",
            asset_class=AssetClass.NATIVE_CRYPTO,
        )


def test_unknown_asset_fails_explicitly() -> None:
    with pytest.raises(KeyError, match="Unknown canonical asset_id"):
        get_asset("asset:not-registered")
