#!/usr/bin/env python3
# ruff: noqa: E501
"""Offline, private CEO mobile console generated from one verified completed mission.

Never publish this HTML to public Pages: download the artifact from the private run.
"""

from __future__ import annotations

import html
import os
import re
from pathlib import Path

from scripts.ceo_inspect_archive import inspect_archive

REPO = "mojtaba2020/Crypto_Intelligence_OS_Core"
OUTPUT = Path("ceo_private_console.html")


def render_console(facts: dict[str, str | int], run_id: str) -> str:
    if not run_id.isdecimal() or not run_id.isascii():
        raise ValueError("A real numeric GitHub run ID is required")
    if type(facts.get("archive_total_count")) is not int or facts["archive_total_count"] < 1:
        raise ValueError("Invalid archive count")
    digest = facts.get("sqlite_sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("Invalid archive digest")
    for key in (
        "first_archived_bar_utc",
        "last_archived_bar_utc",
        "last_ingestion_run_id",
        "last_ingestion_completed_at_utc",
    ):
        if not isinstance(facts.get(key), str) or not facts[key]:
            raise ValueError(f"Missing verified fact: {key}")

    def safe(key: str) -> str:
        return html.escape(str(facts[key]), quote=True)

    run_url = f"https://github.com/{REPO}/actions/runs/{run_id}"
    mission_url = f"https://github.com/{REPO}/actions/workflows/ceo_mission_control.yml"
    data_url = f"https://github.com/{REPO}/tree/data/btc-usd-daily/data"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer">
<title>Crypto Intelligence OS | CEO Private Console</title>
<style>
:root{{color-scheme:dark;font-family:system-ui,-apple-system,sans-serif}}
*{{box-sizing:border-box}}body{{background:#080e1b;color:#edf3ff;margin:0}}
main{{max-width:900px;margin:auto;padding:26px 17px 70px}}
header{{display:flex;align-items:center;justify-content:space-between;gap:12px}}
.brand{{color:#8aefc0;letter-spacing:.1em;font-size:12px;font-weight:750}}
h1{{font-size:clamp(26px,6vw,42px);margin:12px 0}}
h2{{font-size:19px;margin:0 0 14px}}p,small,dt{{color:#aabbd5;line-height:1.6}}
.badge{{border:1px solid #368a66;color:#a3f1c8;border-radius:30px;padding:6px 10px;font-size:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.panel{{background:#142139;border:1px solid #2c415f;border-radius:16px;padding:18px;margin:14px 0}}
.metric{{font-size:32px;font-weight:800;color:#a3f1c8;margin-top:7px;overflow-wrap:anywhere}}
dl{{display:grid;grid-template-columns:minmax(100px,1fr) 2fr;gap:10px}}
dd{{margin:0;overflow-wrap:anywhere}}a.action{{display:block;text-decoration:none;background:#244b82;
color:#fff;border-radius:12px;padding:15px;margin:10px 0;font-weight:650}}
a.action:focus-visible{{outline:3px solid #a3f1c8}}
.note{{border-left:3px solid #f2c76f;padding-left:12px}}
code{{overflow-wrap:anywhere;font-size:12px}}
</style></head><body><main>
<header><span class="brand">CRYPTO INTELLIGENCE OS</span><span class="badge">PRIVATE · CEO</span></header>
<h1>Mission Control</h1>
<p>Verified historical snapshot of one completed GitHub Actions mission. This downloaded
file does not refresh automatically or control active jobs.</p>
<div class="grid">
<div class="panel"><small>Archive inspection</small><div class="metric">PASS</div></div>
<div class="panel"><small>Daily BTC/USD candles</small><div class="metric">{safe("archive_total_count")}</div></div>
<div class="panel"><small>Autonomous AI agents</small><div class="metric">0</div><small>Not deployed</small></div>
</div>
<section class="panel"><h2>Verified mission evidence</h2><dl>
<dt>Current inspection run</dt><dd>{html.escape(run_id)}</dd>
<dt>First archived candle UTC</dt><dd>{safe("first_archived_bar_utc")}</dd>
<dt>Last archived candle UTC</dt><dd>{safe("last_archived_bar_utc")}</dd>
<dt>Last successful ingestion</dt><dd>{safe("last_ingestion_completed_at_utc")}</dd>
<dt>Ingestion run ID</dt><dd>{safe("last_ingestion_run_id")}</dd>
<dt>SQLite SHA-256</dt><dd><code>{safe("sqlite_sha256")}</code></dd>
</dl></section>
<section class="panel"><h2>CEO actions · authenticated GitHub</h2>
<p>These links open the actual private GitHub control plane; this static file never
pretends that a click has started or cancelled a job.</p>
<a class="action" href="{run_url}" rel="noreferrer">View real job state, logs and cancel active run ↗</a>
<a class="action" href="{mission_url}" rel="noreferrer">Start a new approved read-only mission ↗</a>
<a class="action" href="{data_url}" rel="noreferrer">Inspect persistent private BTC/USD archive ↗</a>
</section>
<p class="note">No live agent activity, exchange credentials, trades, withdrawals, or
unverified predictions. Open GitHub for current run status. Keep this downloaded
research report private.</p>
</main></body></html>"""


def main() -> int:
    facts = inspect_archive(
        Path("data/btc_usd_daily.sqlite"), Path("data/btc_ingestion_report.json")
    )
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    OUTPUT.write_text(render_console(facts, run_id), encoding="utf-8")
    print(f"CEO PRIVATE CONSOLE GENERATED: {OUTPUT} from verified run {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
