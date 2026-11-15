"""Persian snapshot of first-party evidence, kept separate by research track."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.btc4h_delivery_integrity import at, validate_score_match, verify_stored_receipt


def read(path):
    return (
        [json.loads(s) for s in path.read_text().splitlines() if s.strip()] if path.exists() else []
    )


def track(root, prefix, now, start, *, limit=None, remote_root="research"):
    forecasts = read(root / f"{prefix}_forecasts.jsonl")
    receipts = read(root / f"{prefix}_publication_receipts.jsonl")
    scores = read(root / f"{prefix}_scores.jsonl")
    accepted = []
    for row in forecasts:
        if at(row["origin_utc"]) < start:
            continue
        matches = [r for r in receipts if r.get("origin_utc") == row["origin_utc"]]
        if len(matches) != 1:
            continue
        try:
            verify_stored_receipt(row, matches[0], f"{remote_root}/{prefix}_forecasts.jsonl")
        except (
            ValueError,
            TypeError,
            KeyError,
            OSError,
            RuntimeError,
            subprocess.CalledProcessError,
        ):
            # One malformed receipt is unverified evidence, not a reason to
            # suppress the whole run's missed-slot and heartbeat report.
            continue
        accepted.append(row)
    due = max(0, int((now - start - timedelta(minutes=15)).total_seconds() // 14400) + 1)
    if limit is not None:
        due = min(limit, due)
    qualified = [
        r
        for r in accepted
        if 14400 <= (at(r["target_5m_close_utc"]) - at(r["issued_at_utc"])).total_seconds() <= 14700
    ]
    issued_due = {
        r["origin_utc"] for r in qualified if at(r["origin_utc"]) + timedelta(minutes=15) <= now
    }
    lines = [
        f"نوبت موعدرسیده: {due}؛ انتشار تأییدشده: {len(accepted)}؛ "
        f"چهارساعت معتبر: {len(qualified)}؛ ازدست‌رفته: {max(0, due - len(issued_due))}"
    ]
    if not forecasts:
        return [*lines, "پیش‌بینی زنده ثبت نشده است؛ موفقیت job شاهد صدور نیست."]
    latest = forecasts[-1]
    lead = (at(latest["target_5m_close_utc"]) - at(latest["issued_at_utc"])).total_seconds() / 60
    lines += [
        f"آخرین صدور UTC: {latest['issued_at_utc']}؛ افق واقعی: {lead:.2f} دقیقه.",
        "نوع: " + ("چهارساعته" if 240 <= lead <= 245 else "کوتاه‌تر/متفاوت؛ خارج از شرط چهار ساعت"),
        "رسید Git: " + ("تأییدشده، صرفاً شخص اول" if latest in accepted else "نامعتبر/مفقود"),
    ]
    matching = []
    for score in scores:
        if score.get("origin_utc") != latest["origin_utc"]:
            continue
        try:
            validate_score_match(latest, score)
        except (ValueError, KeyError, TypeError, OverflowError):
            continue
        matching.append(score)
    if latest in accepted and len(matching) == 1:
        score = matching[0]
        actual = score["actual_close_usd"]
        prices = latest["price_forecasts_usd"]
        lines += [
            f"نتیجه ثبت‌شده: {actual:.2f} دلار؛ "
            f"خطای مدل: {abs(prices['volume_interaction'] - actual):.2f}؛ "
            f"خطای Persistence: {abs(prices['persistence'] - actual):.2f} دلار."
        ]
    else:
        lines += ["score_pending: نتیجه معتبر ثبت نشده؛ نتیجه حدس زده نمی‌شود."]
    resolved = []
    for row in accepted:
        for score in scores:
            if score.get("origin_utc") != row["origin_utc"]:
                continue
            try:
                validate_score_match(row, score)
            except (ValueError, KeyError, TypeError, OverflowError):
                continue
            resolved.append((row, score))
    if resolved and resolved[-1][0] != latest:
        row, score = resolved[-1]
        errors = score["absolute_log_price_errors"]
        lead = (at(row["target_5m_close_utc"]) - at(row["issued_at_utc"])).total_seconds() / 60
        lines += [
            f"آخرین نتیجه قبلی: origin={row['origin_utc']}؛ افق={lead:.2f} دقیقه؛ "
            f"واقعی={score['actual_close_usd']:.2f} دلار؛ "
            f"خطای لگاریتمی مدل={errors['volume_interaction']:.6f}؛ "
            f"Persistence={errors['persistence']:.6f}."
        ]
    return lines


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    now = datetime.now(UTC)
    formal = Path(".research/formal")
    protocol = json.loads((formal / "btc4h_30d_protocol_20261109.json").read_text())
    root = Path("research")
    start = at((root / "btc4h_continuous_start_utc.txt").read_text().strip())
    start = start.replace(hour=start.hour // 4 * 4, minute=0, second=0, microsecond=0)
    lines = [
        "# گزارش وضعیت واقعی BTC/USD",
        f"Run ID: {args.run_id}؛ UTC: {now.isoformat()}",
        f"اعتبار heartbeat تا UTC: {(now + timedelta(hours=4, minutes=30)).isoformat()}",
        "## آزمایش رسمی منجمد — بدون تغییر",
        *track(formal, "btc4h_shadow", now, at(protocol["period_start_utc"]), limit=180),
        "## مسیر rolling — مستقل از آزمایش رسمی",
        *track(root, "btc4h_continuous", now, start),
        "نمونه کوچک است؛ برتری مدل اثبات نشده. رسید Git گواه زمانی مستقل نیست.",
        "GitHub cron تضمین زمان ندارد؛ missed_due_to_late_dispatch موفقیت صدور نیست.",
    ]
    for phase in ("issue", "score"):
        file = Path(f".research/continuous_{phase}.json")
        lines += [
            f"{phase}: " + (file.read_text() if file.exists() else "اجرا نشده یا issue_failed")
        ]
    args.output.write_text("\n\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
