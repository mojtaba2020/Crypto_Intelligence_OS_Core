"""Run the pinned PR 117 fundamental audit against synthetic as-of observations."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.e2_source_only_coverage_v1 import requested_horizon_readiness

WINDOW = {
    "requested_start_utc": "2020-01-01T00:00:00Z",
    "requested_end_utc": "2020-01-04T00:00:00Z",
}
AUDITED_LABELS = "1h 2h 3h 4h 1d 2d 3d 1w 2w 3w 1mo 3mo".split()
OBSERVATION = {
    "metric_id": "btc_spot_etf_net_flow_usd",
    "value": 100.0,
    "unit": "USD",
    "source": "synthetic",
    "source_url": "https://example.org/data",
    "observation_end_utc": "2020-01-01T20:00:00Z",
    "published_at_utc": "2020-01-02T01:00:00Z",
    "first_seen_at_utc": "2020-01-02T01:01:00Z",
    "fetched_at_utc": "2020-01-02T01:02:00Z",
    "revision_id": "v1",
}


class FundamentalIntegration(unittest.TestCase):
    def test_producer_and_consumer_agree_on_availability(self):
        producer = Path(os.environ["PR117_PRODUCER_DIR"]).resolve(strict=True)
        late = dict(
            OBSERVATION,
            first_seen_at_utc="2020-01-02T13:00:00Z",
            fetched_at_utc="2020-01-02T13:01:00Z",
        )
        cases = [("timely", [OBSERVATION], 1), ("late", [late], 0), ("absent", [], 0)]
        for name, observations, expected in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "input.json"
                result = Path(directory) / "output.json"
                origins = [
                    {"horizon": label, "cutoff_utc": "2020-01-02T12:00:00Z"}
                    for label in AUDITED_LABELS
                ]
                payload = {"origins": origins, "observations": observations}
                source.write_text(json.dumps(payload), encoding="utf-8")
                # CI checks out a pinned producer; this invokes its fixed module without a shell.
                subprocess.run(  # noqa: S603
                    [
                        sys.executable,
                        "-E",
                        "-m",
                        "scripts.btc_v2_fundamental_coverage_audit",
                        "--input",
                        str(source),
                        "--output",
                        str(result),
                    ],
                    cwd=producer,
                    check=True,
                    timeout=30,
                )
                audit = json.loads(result.read_text(encoding="utf-8"))
                report = requested_horizon_readiness(WINDOW, fundamental_audit=audit)
                for label in AUDITED_LABELS:
                    self.assertEqual(report[label]["fundamental_eligible_origins"], expected)
                    self.assertEqual(report[label]["fundamental_checked_origins"], 1)
                for label in ("6mo", "1y"):
                    self.assertEqual(report[label]["classification"], "اکتشافی")
                    self.assertEqual(report[label]["fundamental_status"], "اندازه‌گیری نشده")
