"""Contract tests for the zero-cost locked 2023 confirmation entry point."""

from pathlib import Path

import scripts.run_free_2023_confirmation as free_run


def test_locked_free_runner_period_is_exact_2023():
    assert free_run.START.isoformat() == "2023-01-01T00:00:00+00:00"
    assert free_run.END.isoformat() == "2024-01-01T00:00:00+00:00"
    assert free_run.EXPECTED_BARS == 8760


def test_free_runner_requires_matching_provenance(monkeypatch, tmp_path: Path):
    fingerprint = "a" * 64

    def fake_backfill(**kwargs):
        return {
            "stored_count": 8760,
            "canonical_data_sha256": fingerprint,
        }

    def fake_confirm(*args):
        return {
            "validated_bar_count": 8760,
            "ingestion_chain_of_custody": "PASS",
            "canonical_data_sha256": fingerprint,
            "preregistration_sha256": "b" * 64,
            "runner_git_sha": "deadbeef",
            "decision": "CONFIRMATORY_PASS_PENDING_REPLICATION",
        }

    monkeypatch.setattr(free_run.backfill, "run", fake_backfill)
    monkeypatch.setattr(free_run.confirm, "run", fake_confirm)

    result = free_run.run(tmp_path)
    assert result["bars"] == 8760
    assert result["data_sha256"] == fingerprint
    assert result["git_sha"] == "deadbeef"
