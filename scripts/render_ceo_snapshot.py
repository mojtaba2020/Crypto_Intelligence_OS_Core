#!/usr/bin/env python3
"""Render a factual, static CEO snapshot from one completed data-ingestion run."""

from __future__ import annotations

import html
import json
from pathlib import Path

REPORT_PATH = Path("data/btc_ingestion_report.json")
OUTPUT_PATH = Path("ceo_ingestion_snapshot.html")


def render_snapshot(report: dict[str, str | int]) -> str:
    def field(key: str) -> str:
        return html.escape(str(report[key]), quote=True)

    if report.get("status") != "COMPLETED":
        raise ValueError("Only a genuinely completed run may be shown as completed")
    if report.get("worker_type") != "DETERMINISTIC_MARKET_DATA_PIPELINE_NOT_AI_AGENT":
        raise ValueError("Unsupported worker identity")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Crypto Intelligence OS — CEO Run Snapshot</title>
<style>
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:#0b1020;color:#ecf0ff;font:16px system-ui,sans-serif}}
main{{max-width:890px;margin:auto;padding:28px 18px 64px}}
h1{{font-size:clamp(24px,5vw,38px);margin:8px 0}}
p{{color:#aebbd5;line-height:1.65}}
.tag{{color:#76e6ac;font-weight:700;letter-spacing:.05em}}
.panel{{background:#16213a;border:1px solid #324361;border-radius:14px;padding:20px;margin:16px 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px}}
.value{{font-size:30px;font-weight:750;color:#76e6ac}}
small{{color:#aebbd5}} dl{{display:grid;grid-template-columns:minmax(120px,1fr) 2fr;gap:12px}}
dt{{color:#aebbd5}}dd{{margin:0;overflow-wrap:anywhere}}
.notice{{border-left:4px solid #f1c670;padding-left:12px}}
</style>
</head>
<body><main>
<div class="tag">CRYPTO INTELLIGENCE OS · CEO CONTROL TOWER</div>
<h1>Verified ingestion run</h1>
<p>This is a saved snapshot of <strong>one actual GitHub Actions run</strong>, not a
live dashboard or an autonomous AI agent. The collector and validator ran as
deterministic Python software.</p>
<div class="grid">
<div class="panel"><small>Task status</small><div class="value">{field("status")}</div></div>
<div class="panel"><small>Archived BTC/USD candles</small>
<div class="value">{field("archive_total_count")}</div></div>
<div class="panel"><small>Newly archived</small>
<div class="value">{field("inserted_count")}</div></div>
<div class="panel"><small>Validated this run</small>
<div class="value">{field("fetched_count")}</div></div>
</div>
<section class="panel"><h2>Mission trace</h2><dl>
<dt>Run ID</dt><dd>{field("run_id")}</dd>
<dt>Worker</dt><dd>Deterministic data collector + quality validator</dd>
<dt>Data source</dt><dd>{field("source")}</dd>
<dt>Start UTC</dt><dd>{field("started_at_utc")}</dd>
<dt>End UTC</dt><dd>{field("completed_at_utc")}</dd>
<dt>Last candle UTC</dt><dd>{field("last_archived_bar_utc")}</dd>
<dt>Database checksum</dt><dd><code>{field("sqlite_sha256")}</code></dd>
<dt>Storage</dt><dd>Private GitHub branch: data/btc-usd-daily</dd>
</dl></section>
<p class="notice">NOT DEPLOYED: autonomous research agents, CEO live controls,
financial execution, and customer-facing dashboard. Historical candles were
retrieved after the fact; they were not known by this system when they closed.</p>
</main></body></html>"""


def main() -> int:
    report: dict[str, str | int] = json.loads(REPORT_PATH.read_text())
    OUTPUT_PATH.write_text(render_snapshot(report))
    print(f"CEO SNAPSHOT: {OUTPUT_PATH} (static, real run only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
