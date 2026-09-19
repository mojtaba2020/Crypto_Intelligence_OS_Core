from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from crypto_intelligence_os.adapters.market_data import (
    COINBASE_BTC_USD,
    COINBASE_SOURCE_ID,
    CoinbasePublicCandleSource,
    HttpResponseError,
    UnsupportedTimeframeError,
)
from crypto_intelligence_os.market_data import Timeframe

JsonObject = dict[str, Any]


class RecordingTransport:
    def __init__(self, responses: list[JsonObject | Exception]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, str, Mapping[str, str]]] = []

    def get_json(
        self,
        *,
        host: str,
        path: str,
        timeout_seconds: float,
        headers: Mapping[str, str] | None = None,
    ) -> JsonObject:
        assert timeout_seconds > 0
        request_headers = dict(headers or {})
        self.requests.append((host, path, request_headers))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def candle(start: datetime, *, close: str = "101") -> JsonObject:
    return {
        "start": str(int(start.timestamp())),
        "low": "90",
        "high": "110",
        "open": "100",
        "close": close,
        "volume": "12.5",
    }


def test_coinbase_fetches_only_final_market_available_bars() -> None:
    first = datetime(2026, 9, 15, 0, 0, tzinfo=UTC)
    second = first + timedelta(hours=1)
    transport = RecordingTransport([{"candles": [candle(second), candle(first)]}])
    ingested_at = second + timedelta(hours=2)
    source = CoinbasePublicCandleSource(
        transport=transport,
        clock=lambda: ingested_at,
    )

    bars = source.fetch_final_bars(
        timeframe=Timeframe.ONE_HOUR,
        start=first,
        end=second + timedelta(hours=1),
        as_of=second + timedelta(seconds=1),
    )

    assert len(bars) == 1
    assert bars[0].open_time == first
    assert bars[0].available_at == second + timedelta(seconds=1)
    assert bars[0].ingested_at == ingested_at
    assert bars[0].source_id == COINBASE_SOURCE_ID
    assert bars[0].instrument_id == COINBASE_BTC_USD.instrument_id

    host, path, headers = transport.requests[0]
    assert host == "api.coinbase.com"
    assert path.startswith("/api/v3/brokerage/market/products/BTC-USD/candles?")
    assert headers["Cache-Control"] == "no-cache"
    assert "Authorization" not in headers


def test_coinbase_chunks_ranges_larger_than_provider_limit() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=351)
    transport = RecordingTransport([{"candles": []}, {"candles": []}])
    source = CoinbasePublicCandleSource(transport=transport, clock=lambda: end)

    bars = source.fetch_final_bars(
        timeframe=Timeframe.ONE_HOUR,
        start=start,
        end=end,
        as_of=end,
    )

    assert bars == ()
    assert len(transport.requests) == 2
    first_query = parse_qs(urlsplit(transport.requests[0][1]).query)
    second_query = parse_qs(urlsplit(transport.requests[1][1]).query)
    assert first_query["limit"] == ["350"]
    assert second_query["limit"] == ["350"]
    assert int(second_query["start"][0]) == int((start + timedelta(hours=350)).timestamp())


def test_coinbase_retries_transient_rate_limit() -> None:
    now = datetime(2026, 9, 15, 6, 0, tzinfo=UTC)
    error = HttpResponseError(
        status_code=429,
        reason="Too Many Requests",
        headers={"retry-after": "0"},
        body_preview="rate limited",
    )
    transport = RecordingTransport([error, {"candles": []}])
    sleeps: list[float] = []
    source = CoinbasePublicCandleSource(
        transport=transport,
        clock=lambda: now,
        sleeper=sleeps.append,
        max_retries=1,
    )

    assert (
        source.fetch_final_bars(
            timeframe=Timeframe.ONE_HOUR,
            start=now - timedelta(hours=1),
            end=now,
            as_of=now,
        )
        == ()
    )
    assert sleeps == [0.0]
    assert len(transport.requests) == 2


def test_coinbase_raises_after_retry_budget_is_exhausted() -> None:
    now = datetime(2026, 9, 15, 6, 0, tzinfo=UTC)
    error = HttpResponseError(
        status_code=503,
        reason="Service Unavailable",
        headers={},
        body_preview="down",
    )
    transport = RecordingTransport([error, error])
    source = CoinbasePublicCandleSource(
        transport=transport,
        clock=lambda: now,
        sleeper=lambda _: None,
        max_retries=1,
    )

    with pytest.raises(HttpResponseError):
        source.fetch_final_bars(
            timeframe=Timeframe.ONE_HOUR,
            start=now - timedelta(hours=1),
            end=now,
            as_of=now,
        )


def test_coinbase_rejects_unsupported_weekly_timeframe() -> None:
    now = datetime(2026, 9, 15, 6, 0, tzinfo=UTC)
    source = CoinbasePublicCandleSource(transport=RecordingTransport([]), clock=lambda: now)

    with pytest.raises(UnsupportedTimeframeError):
        source.fetch_final_bars(
            timeframe=Timeframe.ONE_WEEK,
            start=now - timedelta(weeks=1),
            end=now,
            as_of=now,
        )


def test_coinbase_server_time_uses_public_response() -> None:
    transport = RecordingTransport([{"epochMillis": "1789442400123"}])
    source = CoinbasePublicCandleSource(transport=transport)

    value = source.fetch_server_time()

    assert value == datetime.fromtimestamp(1789442400.123, tz=UTC)
    _, path, headers = transport.requests[0]
    assert path == "/api/v3/brokerage/time"
    assert "Authorization" not in headers


def test_coinbase_bar_ids_are_stable_across_repeated_fetches() -> None:
    start = datetime(2026, 9, 15, 0, 0, tzinfo=UTC)
    cutoff = start + timedelta(hours=2)
    payload = {"candles": [candle(start)]}
    first_transport = RecordingTransport([payload])
    second_transport = RecordingTransport([payload])
    first = CoinbasePublicCandleSource(transport=first_transport, clock=lambda: cutoff)
    second = CoinbasePublicCandleSource(transport=second_transport, clock=lambda: cutoff)

    first_bar = first.fetch_final_bars(
        timeframe=Timeframe.ONE_HOUR,
        start=start,
        end=start + timedelta(hours=1),
        as_of=cutoff,
    )[0]
    second_bar = second.fetch_final_bars(
        timeframe=Timeframe.ONE_HOUR,
        start=start,
        end=start + timedelta(hours=1),
        as_of=cutoff,
    )[0]

    assert first_bar.bar_id == second_bar.bar_id


def test_system_known_snapshot_uses_post_ingestion_cutoff() -> None:
    start = datetime(2026, 9, 15, 0, 0, tzinfo=UTC)
    server_time = start + timedelta(hours=2)
    ingested_at = server_time + timedelta(seconds=2)
    completed_at = ingested_at + timedelta(seconds=1)
    transport = RecordingTransport(
        [
            {"epochMillis": str(int(server_time.timestamp() * 1000))},
            {"candles": [candle(start)]},
        ]
    )
    clock_values = iter([ingested_at, completed_at])
    source = CoinbasePublicCandleSource(transport=transport, clock=lambda: next(clock_values))

    snapshot = source.fetch_system_known_snapshot(
        timeframe=Timeframe.ONE_HOUR,
        start=start,
        end=start + timedelta(hours=1),
    )

    assert snapshot.data_cutoff_time == completed_at
    assert snapshot.bars[0].ingested_at == ingested_at
    assert snapshot.knowledge_mode.value == "SYSTEM_KNOWN"
