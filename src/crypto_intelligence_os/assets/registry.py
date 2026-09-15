"""Initial canonical asset registry.

The registry intentionally starts tiny.  Assets are added only when the product needs
them and when identity semantics are verified.
"""

from crypto_intelligence_os.assets.models import AssetClass, CanonicalAsset

BITCOIN = CanonicalAsset(
    asset_id="asset:bitcoin",
    symbol="BTC",
    name="Bitcoin",
    asset_class=AssetClass.NATIVE_CRYPTO,
    network_id="network:bitcoin-mainnet",
    decimals=8,
)

USD = CanonicalAsset(
    asset_id="asset:usd",
    symbol="USD",
    name="United States Dollar",
    asset_class=AssetClass.FIAT,
    decimals=2,
)

CANONICAL_ASSETS: dict[str, CanonicalAsset] = {
    BITCOIN.asset_id: BITCOIN,
    USD.asset_id: USD,
}


def get_asset(asset_id: str) -> CanonicalAsset:
    """Return a canonical asset or fail explicitly for an unknown ID."""
    try:
        return CANONICAL_ASSETS[asset_id]
    except KeyError as exc:
        raise KeyError(f"Unknown canonical asset_id: {asset_id}") from exc
