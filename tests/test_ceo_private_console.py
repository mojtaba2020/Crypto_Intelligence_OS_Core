"""Private CEO HTML must be truthful, escaped and linked to real authenticated controls."""

from __future__ import annotations

import pytest

from scripts.render_ceo_private_console import render_console


def facts() -> dict[str, str | int]:
    return {
        "archive_total_count": 90,
        "first_archived_bar_utc": "2026-06-21T00:00:00+00:00",
        "last_archived_bar_utc": "2026-09-18T00:00:00+00:00",
        "last_ingestion_run_id": "123-1",
        "last_ingestion_completed_at_utc": "2026-09-19T17:00:00+00:00",
        "sqlite_sha256": "a" * 64,
    }


def test_private_console_has_real_links_and_no_fake_controls() -> None:
    output = render_console(facts(), "98765")
    assert "90" in output
    assert "Not deployed" in output
    assert "actions/runs/98765" in output
    assert "actions/workflows/ceo_mission_control.yml" in output
    assert "does not refresh automatically" in output
    assert "<script" not in output


def test_private_console_escapes_untrusted_metadata() -> None:
    data = facts()
    data["last_ingestion_run_id"] = '<img src=x onerror=alert(1)>'
    output = render_console(data, "98765")
    assert "&lt;img src=x onerror=alert(1)&gt;" in output
    assert "<img src=x" not in output


def test_private_console_rejects_fake_run_or_invalid_archive() -> None:
    with pytest.raises(ValueError, match="numeric"):
        render_console(facts(), "fake-run")
    data = facts()
    data["sqlite_sha256"] = "not-a-sha"
    with pytest.raises(ValueError, match="digest"):
        render_console(data, "98765")
