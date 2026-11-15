"""Run against the real immutable research dependencies via test_btc4h_delivery.sh."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from scripts import btc4h_continuous_forward as engine
from scripts.btc4h_delivery_integrity import canonical_digest

ORIGIN = datetime(2026, 11, 15, 8, tzinfo=UTC)


@pytest.fixture
def market():
    hourly = {ORIGIN - timedelta(hours=i): (67000 + i * 0.3, 100 + i % 13) for i in range(1, 266)}
    targets = {
        ORIGIN - timedelta(days=10) + timedelta(hours=i * 4 + 4, minutes=10): 67100 + i
        for i in range(59)
    }
    return hourly, targets


def forecast(market, minute=12):
    hourly, targets = market
    return engine.calculate_issue(
        issued_at=ORIGIN + timedelta(minutes=minute),
        hourly_fetched_at=ORIGIN + timedelta(minutes=10),
        target_fetched_at=ORIGIN + timedelta(minutes=11),
        hourly=hourly,
        closed_targets=targets,
    )


@pytest.mark.parametrize("minute", [5, 16, 42, 80, 204, 255])
def test_late_or_early_calculation_never_issues(market, minute):
    with pytest.raises(ValueError, match="MISS_ISSUE_WINDOW"):
        forecast(market, minute)


@pytest.mark.parametrize("minute", [11, 12, 14.999])
def test_genuine_horizon_and_matched_training(market, minute):
    row = forecast(market, minute)
    assert 14400 <= row["horizon_seconds"] <= 14700
    assert row["mature_historical_training_examples"] == 59
    assert row["version"] == engine.VERSION


def test_empty_history_refuses_forecast():
    with pytest.raises(ValueError, match="incomplete"):
        forecast(({}, {}))


@pytest.mark.parametrize("minute", [5, 16, 42, 80])
def test_late_dispatch_does_not_access_market_or_backfill(tmp_path, monkeypatch, minute):
    def forbidden(*args, **kwargs):
        pytest.fail("market accessed outside bounded prefetch window")

    monkeypatch.setattr(engine, "fetch_candles", forbidden)
    monkeypatch.setattr(engine, "fetch_public_hourly_close_volume", forbidden)
    result = engine.run_once(
        ledger=tmp_path / "f.jsonl",
        score_ledger=tmp_path / "s.jsonl",
        report=tmp_path / "r.json",
        phase="issue",
        clock=lambda: ORIGIN + timedelta(minutes=minute),
    )
    assert result["newly_issued"] == 0
    assert not (tmp_path / "f.jsonl").exists()
    if minute > 15:
        assert result["research_status"] == "missed_due_to_late_dispatch"


def test_duplicate_runner_no_new_forecast(tmp_path, market):
    ledger = tmp_path / "f.jsonl"
    engine._append(ledger, forecast(market))
    result = engine.run_once(
        ledger=ledger,
        score_ledger=tmp_path / "s.jsonl",
        report=tmp_path / "r.json",
        phase="issue",
        clock=lambda: ORIGIN + timedelta(minutes=13),
    )
    assert result["newly_issued"] == 0
    assert result["research_status"] == "already_issued"
    assert len(ledger.read_text().splitlines()) == 1


def test_fetch_crossing_deadline_refuses_issue(tmp_path, market, monkeypatch):
    monkeypatch.setattr(engine, "fetch_public_hourly_close_volume", lambda *a: market[0])
    monkeypatch.setattr(engine, "fetch_candles", lambda *a, **kw: market[1])
    stamps = iter([ORIGIN + timedelta(minutes=n) for n in (12, 13, 14, 16)])
    result = engine.run_once(
        ledger=tmp_path / "f.jsonl",
        score_ledger=tmp_path / "s.jsonl",
        report=tmp_path / "r.json",
        phase="issue",
        clock=lambda: next(stamps),
    )
    assert result["newly_issued"] == 0


def test_pre_target_score_refused_and_score_binds_canonical_row(market):
    row = forecast(market)
    with pytest.raises(ValueError, match="pre-target"):
        engine.calculate_score(row, actual=67100, target_received_at=ORIGIN)
    score = engine.calculate_score(
        row, actual=67100, target_received_at=ORIGIN + timedelta(hours=5)
    )
    assert score["forecast_canonical_line_sha256"] == canonical_digest(row)
    assert score["horizon_seconds"] == row["horizon_seconds"]


def test_missing_mature_candle_is_pending(tmp_path, market, monkeypatch):
    engine._append(tmp_path / "f.jsonl", forecast(market))
    monkeypatch.setattr(engine, "fetch_candles", lambda *a, **kw: {})
    result = engine.run_once(
        ledger=tmp_path / "f.jsonl",
        score_ledger=tmp_path / "s.jsonl",
        report=tmp_path / "r.json",
        phase="score",
        clock=lambda: ORIGIN + timedelta(hours=5),
    )
    assert result["research_status"] == "score_pending"
    assert result["newly_scored"] == 0


def test_missing_receipt_blocks_mature_score(tmp_path, market, monkeypatch):
    row = forecast(market)
    engine._append(tmp_path / "f.jsonl", row)
    opened = datetime.fromisoformat(row["target_5m_bar_open_utc"].replace("Z", "+00:00"))
    monkeypatch.setattr(engine, "fetch_candles", lambda *a, **kw: {opened: 67100})
    with pytest.raises(ValueError, match="missing or duplicate publication receipt"):
        engine.run_once(
            ledger=tmp_path / "f.jsonl",
            score_ledger=tmp_path / "s.jsonl",
            report=tmp_path / "r.json",
            phase="score",
            clock=lambda: ORIGIN + timedelta(hours=5),
        )
    assert not (tmp_path / "s.jsonl").exists()


def test_actual_issue_clock_after_calculation(tmp_path, market, monkeypatch):
    monkeypatch.setattr(engine, "fetch_public_hourly_close_volume", lambda *a: market[0])
    monkeypatch.setattr(engine, "fetch_candles", lambda *a, **kw: market[1])
    stamps = iter([ORIGIN + timedelta(minutes=n) for n in (10, 10, 11, 12, 13)])
    result = engine.run_once(
        ledger=tmp_path / "f.jsonl",
        score_ledger=tmp_path / "s.jsonl",
        report=tmp_path / "r.json",
        phase="issue",
        clock=lambda: next(stamps),
    )
    row = json.loads((tmp_path / "f.jsonl").read_text())
    assert result["newly_issued"] == 1
    assert row["issued_at_utc"].startswith("2026-11-15T08:13:")
    assert row["horizon_seconds"] == 242 * 60


def test_bounded_early_prefetch_wait(tmp_path, market, monkeypatch):
    monkeypatch.setattr(engine, "fetch_public_hourly_close_volume", lambda *a: market[0])
    monkeypatch.setattr(engine, "fetch_candles", lambda *a, **kw: market[1])
    stamps = iter([ORIGIN + timedelta(minutes=n) for n in (8, 8, 8, 8, 10, 11)])
    sleeps = []
    result = engine.run_once(
        ledger=tmp_path / "f.jsonl",
        score_ledger=tmp_path / "s.jsonl",
        report=tmp_path / "r.json",
        phase="issue",
        clock=lambda: next(stamps),
        sleeper=sleeps.append,
    )
    assert sleeps == [120]
    assert result["newly_issued"] == 1


def test_computation_crossing_deadline_never_backdates(tmp_path, market, monkeypatch):
    monkeypatch.setattr(engine, "fetch_public_hourly_close_volume", lambda *a: market[0])
    monkeypatch.setattr(engine, "fetch_candles", lambda *a, **kw: market[1])
    stamps = iter([ORIGIN + timedelta(minutes=n) for n in (10, 10, 11, 12, 16)])
    result = engine.run_once(
        ledger=tmp_path / "f.jsonl",
        score_ledger=tmp_path / "s.jsonl",
        report=tmp_path / "r.json",
        phase="issue",
        clock=lambda: next(stamps),
    )
    assert result["newly_issued"] == 0
    assert not (tmp_path / "f.jsonl").exists()


def test_full_synthetic_issue_receipt_then_mature_score(tmp_path, market, monkeypatch):
    import shutil
    import subprocess

    from scripts.btc4h_delivery_integrity import canonical_line, make_receipt

    monkeypatch.chdir(tmp_path)
    git = shutil.which("git") or "/usr/bin/git"
    for args in (
        ["init"],
        ["config", "user.name", "Synthetic test"],
        ["config", "user.email", "test@example.invalid"],
    ):
        subprocess.run([git, *args], check=True, capture_output=True)  # noqa: S603
    row = forecast(market)
    ledger = engine.Path("research/btc4h_continuous_forecasts.jsonl")
    engine._append(ledger, row)
    subprocess.run([git, "add", "."], check=True, capture_output=True)  # noqa: S603
    subprocess.run([git, "commit", "-m", "synthetic forecast"], check=True, capture_output=True)  # noqa: S603
    sha = subprocess.run(  # noqa: S603 - fixed local Git command.
        [git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    witness = make_receipt(
        row,
        remote_sha=sha,
        remote_content=canonical_line(row),
        confirmed_at=ORIGIN + timedelta(minutes=13),
        run_id="synthetic",
    )
    engine._append(engine.Path("research/btc4h_continuous_publication_receipts.jsonl"), witness)
    opened = datetime.fromisoformat(row["target_5m_bar_open_utc"].replace("Z", "+00:00"))
    monkeypatch.setattr(engine, "fetch_candles", lambda *a, **kw: {opened: 67100})

    def run():
        return engine.run_once(
            ledger=ledger,
            score_ledger=engine.Path("research/scores.jsonl"),
            report=engine.Path("report.json"),
            phase="score",
            clock=lambda: ORIGIN + timedelta(hours=5),
        )

    result = run()
    assert result["newly_scored"] == 1
    assert result["research_status"] == "score_matured"
    assert run()["newly_scored"] == 0
    assert len(engine.Path("research/scores.jsonl").read_text().splitlines()) == 1
