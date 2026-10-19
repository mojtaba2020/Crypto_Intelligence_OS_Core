"""Offline, price-blind elapsed-lead audit for BTC hourly forecast claims.

All GitHub run IDs and publication timestamps are caller-supplied assertions,
not authenticated receipts. No network, model fitting, scoring, or promotion.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

HORIZONS = (1, 4, 12, 24)
CLAIM_SEMANTICS = ("bar_aligned", "minimum_elapsed")
LEAD_STATUSES = frozenset({"CLAIMED_PRE_CLOSE_UNVERIFIED", "INSUFFICIENT_CLAIMED_ELAPSED_HORIZON"})
HOUR = 3_600
MAX_HOURS = 168
PLAN_FIELDS = frozenset(
    {"first_origin_utc", "stop_origin_exclusive_utc", "horizons_hours", "claim_semantics"}
)
RECORD_FIELDS = frozenset(
    {
        "github_run_id",
        "origin_hour_utc",
        "horizon_hours",
        "claimed_issued_at_utc",
        "claimed_publication_upper_bound_utc",
        "target_close_utc",
    }
)


def _second(value: object, field: str) -> int:
    if type(value) is not int or not 0 < value < 10**11:
        raise ValueError(f"{field} must be bounded positive integer UTC seconds")
    return value


def audit_elapsed_lead(
    plan: Mapping[str, object], records: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Report actual *claimed* elapsed leads and every missing scheduled slot.

    The nominal hourly horizon counts future bars, NOT guaranteed elapsed lead
    from independently published forecast to target maturity. No safety margin
    or 'good lead' decision may be inferred from this metadata-only report.
    """
    if not isinstance(plan, Mapping) or set(plan) != PLAN_FIELDS:
        raise ValueError("Exact, price-free hourly plan required")
    if type(plan["horizons_hours"]) is not tuple or plan["horizons_hours"] != HORIZONS:
        raise ValueError("All four canonical hourly horizons required")
    semantics = plan["claim_semantics"]
    if type(semantics) is not str or semantics not in CLAIM_SEMANTICS:
        raise ValueError("Explicit bar_aligned or minimum_elapsed claim semantics required")
    start = _second(plan["first_origin_utc"], "start")
    stop = _second(plan["stop_origin_exclusive_utc"], "stop")
    if start % HOUR or stop % HOUR or stop <= start or stop - start > MAX_HOURS * HOUR:
        raise ValueError("Invalid bounded hourly plan")
    origin_count = (stop - start) // HOUR
    if (
        not isinstance(records, Sequence)
        or isinstance(records, (bytes, str))
        or len(records) > origin_count * len(HORIZONS)
    ):
        raise ValueError("Invalid or oversized records")

    observed: dict[tuple[int, int], dict[str, object]] = {}
    run_origins: dict[int, int] = {}
    origin_runs: dict[int, int] = {}
    run_issuance: dict[int, int] = {}
    inconsistent_origins: set[int] = set()
    for record in records:
        if not isinstance(record, Mapping) or set(record) != RECORD_FIELDS:
            raise ValueError("Exact price-free forecast metadata required")
        run_id = _second(record["github_run_id"], "github_run_id")
        origin = _second(record["origin_hour_utc"], "origin_hour_utc")
        horizon = record["horizon_hours"]
        if type(horizon) is not int or horizon not in HORIZONS:
            raise ValueError("Unrecognized horizon")
        if not start <= origin < stop or origin % HOUR:
            raise ValueError("Forecast origin outside fixed schedule")
        if (origin, horizon) in observed:
            raise ValueError("Duplicate origin/horizon forecast claim")
        if run_id in run_origins and run_origins[run_id] != origin:
            raise ValueError("Same claimed run ID reused for different origins")
        if origin in origin_runs and origin_runs[origin] != run_id:
            raise ValueError("Different runs cannot silently replenish one origin")
        run_origins[run_id] = origin
        origin_runs[origin] = run_id
        issued = _second(record["claimed_issued_at_utc"], "claimed_issued_at_utc")
        if run_id in run_issuance and run_issuance[run_id] != issued:
            inconsistent_origins.add(origin)
        else:
            run_issuance[run_id] = issued
        seen_raw = record["claimed_publication_upper_bound_utc"]
        seen = None if seen_raw is None else _second(seen_raw, "publication upper bound")
        close = _second(record["target_close_utc"], "target_close_utc")
        if close != origin + (horizon + 1) * HOUR:
            raise ValueError("Target close conflicts with nominal completed-bar convention")

        if issued < origin + HOUR:
            status = "ISSUANCE_CLAIM_BEFORE_ORIGIN_BAR_CLOSED"
        elif issued >= close:
            status = "ISSUANCE_CLAIM_AT_OR_AFTER_MATURITY"
        elif seen is None:
            status = "NO_PUBLICATION_WITNESS_CLAIM"
        elif seen < issued:
            status = "PUBLICATION_CLAIM_BEFORE_ISSUANCE_CLAIM"
        elif seen >= close:
            status = "PUBLICATION_CLAIM_AT_OR_AFTER_MATURITY"
        elif semantics == "minimum_elapsed" and close - seen < horizon * HOUR:
            # Do not relabel a bar-aligned forecast as a full elapsed-horizon claim.
            status = "INSUFFICIENT_CLAIMED_ELAPSED_HORIZON"
        else:
            status = "CLAIMED_PRE_CLOSE_UNVERIFIED"

        observed[origin, horizon] = {
            "origin_hour_utc": origin,
            "horizon_hours": horizon,
            "github_run_id_claim": run_id,
            "status": status,
            "claimed_issued_at_utc": issued,
            "claimed_publication_upper_bound_utc": seen,
            "target_close_utc": close,
            "claimed_elapsed_lead_seconds": close - seen if status in LEAD_STATUSES else None,
        }

    # The deployed producer samples one issuance instant per four-horizon batch.
    # Flag *every* received row for a contradictory claimed batch, not just
    # whichever row arrived second. Never let it contribute to lead summaries.
    for origin in inconsistent_origins:
        for horizon in HORIZONS:
            row = observed.get((origin, horizon))
            if row is not None:
                row["status"] = "INCONSISTENT_BATCH_ISSUANCE_CLAIMS"
                row["claimed_elapsed_lead_seconds"] = None

    rows: list[dict[str, object]] = []
    horizon_summaries: list[dict[str, object]] = []
    for origin in range(start, stop, HOUR):
        for horizon in HORIZONS:
            row = observed.get((origin, horizon))
            if row is None:
                row = {
                    "origin_hour_utc": origin,
                    "horizon_hours": horizon,
                    "status": "MISSING_SCHEDULED_FORECAST_CLAIM",
                    "claimed_elapsed_lead_seconds": None,
                }
            rows.append(row)
    for horizon in HORIZONS:
        subset = [r for r in rows if r["horizon_hours"] == horizon]
        leads = [
            r["claimed_elapsed_lead_seconds"]
            for r in subset
            if r["status"] == "CLAIMED_PRE_CLOSE_UNVERIFIED"
        ]
        horizon_summaries.append(
            {
                "horizon_hours": horizon,
                "scheduled_count": origin_count,
                "missing_count": sum(
                    r["status"] == "MISSING_SCHEDULED_FORECAST_CLAIM" for r in subset
                ),
                "claimed_preclose_count": len(leads),
                "short_elapsed_horizon_count": sum(
                    r["status"] == "INSUFFICIENT_CLAIMED_ELAPSED_HORIZON" for r in subset
                ),
                "blocked_or_unknown_claim_count": sum(
                    r["status"]
                    not in (
                        "MISSING_SCHEDULED_FORECAST_CLAIM",
                        "CLAIMED_PRE_CLOSE_UNVERIFIED",
                    )
                    for r in subset
                ),
                "min_claimed_elapsed_lead_seconds": min(leads) if leads else None,
                "max_claimed_elapsed_lead_seconds": max(leads) if leads else None,
            }
        )
    missing_count = sum(summary["missing_count"] for summary in horizon_summaries)
    blocked_count = sum(summary["blocked_or_unknown_claim_count"] for summary in horizon_summaries)
    return {
        "status": (
            "BLOCKED" if missing_count or blocked_count else "UNVERIFIED_ELAPSED_LEAD_METADATA_ONLY"
        ),
        "missing_slot_count": missing_count,
        "blocked_or_unknown_claim_count": blocked_count,
        "scheduled_origin_count": origin_count,
        "claim_semantics": semantics,
        "elapsed_horizon_claim_independently_verified": False,
        "expected_origin_horizon_slots": origin_count * len(HORIZONS),
        "received_claim_count": len(observed),
        "github_run_identity_independently_verified": False,
        "github_publication_timestamps_independently_verified": False,
        "source_first_available_at_origin_authenticated": False,
        "minimum_safe_lead_threshold_approved": False,
        "independent_effective_n": "UNKNOWN",
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
        "by_horizon": horizon_summaries,
        "slots": rows,
    }


# Parse GitHub-hosted job-log envelopes, not timestamps printed by the forecast program.
# This is an evidence *consistency* check, not independent remote attestation.
_GITHUB_PUSH = re.compile(
    r"^(?P<when>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z)"
    r"\s+(?P<old>[0-9a-f]{7,40})\.\.(?P<new>[0-9a-f]{7,40})"
    r"\s+HEAD -> main$"
)
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HOURLY_PATH = ".github/workflows/btc_hourly_prospective.yml"
_ROW_META = frozenset(
    {"origin_hour_utc", "issued_at_utc", "target_close_utc", "horizon_hours", "version"}
)


def _parse_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be UTC text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds():
        raise ValueError(f"{field} must be UTC")
    return parsed.astimezone(UTC)


def _sha(value: object) -> str:
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise ValueError("Exact full commit SHA required")
    return value


_GITHUB_COMPLETED_RUN_UTC = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(?P<fraction>\d{1,9}))?Z$"
)


def _ceil_github_run_second(value: object) -> int:
    """Return a conservative whole-second upper bound for GitHub run updates.

    datetime.fromisoformat truncates beyond microseconds; inspect all nine
    fractional digits before rounding *toward the future*, not into the past.
    """
    if not isinstance(value, str):
        raise ValueError("GitHub run update must be UTC Z timestamp")
    match = _GITHUB_COMPLETED_RUN_UTC.fullmatch(value)
    if match is None:
        raise ValueError("GitHub run update must be UTC Z timestamp")
    whole = _parse_utc(value, "GitHub run update").replace(microsecond=0)
    fraction = match.group("fraction") or ""
    return int(whole.timestamp()) + int(any(digit != "0" for digit in fraction))


def _github_numeric_id(value: object, field: str) -> int:
    if type(value) is not int or not 0 < value < 10**16:
        raise ValueError(f"{field} must be a positive GitHub ID")
    return value


def reconcile_github_push_bundle(
    run: Mapping[str, object],
    job: Mapping[str, object],
    commit: Mapping[str, object],
    log_lines: Sequence[str],
    rows: Sequence[Mapping[str, object]],
    claim_semantics: str,
) -> dict[str, object]:
    """Check a projected GitHub-run/commit/push bundle; never certify its origin.

    Inputs MUST be fetched and source-authenticated separately by an independent
    reviewer. This code has no network, no data-provider access and no credentials.
    The rows are a *price-free projection*, not proof that those bytes occur in
    the pushed commit; matching their SHA needs a separately trusted reviewer.
    For time eligibility, this function uses the completed GitHub run update
    timestamp as a *conservative* claimed publication upper bound, not the
    earlier log push timestamp. Both inputs still require external authentication.
    """
    if not all(isinstance(x, Mapping) for x in (run, job, commit)):
        raise ValueError("Run/job/commit objects required")
    if (
        run.get("path") != _HOURLY_PATH
        or run.get("event") != "schedule"
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or job.get("name") != "hourly"
        or job.get("status") != "completed"
        or job.get("conclusion") != "success"
    ):
        raise ValueError("Successful scheduled hourly run and job required")
    run_id = _github_numeric_id(run.get("id"), "run ID")
    _github_numeric_id(job.get("id"), "job ID")
    if job.get("run_id") != run_id:
        raise ValueError("Job does not belong to the claimed run")
    if not isinstance(log_lines, Sequence) or isinstance(log_lines, (str, bytes)):
        raise ValueError("Bounded GitHub job log lines required")
    if len(log_lines) > 2_000 or sum(len(line) for line in log_lines) > 1_000_000:
        raise ValueError("GitHub log too large")
    if any(not isinstance(line, str) for line in log_lines):
        raise ValueError("Invalid log line")
    push_lines = [match for line in log_lines if (match := _GITHUB_PUSH.fullmatch(line))]
    if len(push_lines) != 1:
        raise ValueError("Exactly one GitHub-hosted push-line claim required")
    push = push_lines[0]
    push_at = _parse_utc(push.group("when"), "GitHub push log")
    run_started = _parse_utc(run.get("created_at"), "GitHub run creation")
    run_updated = _parse_utc(run.get("updated_at"), "GitHub run update")
    conservative_publication_second = _ceil_github_run_second(run.get("updated_at"))
    if not run_started <= push_at <= run_updated:
        raise ValueError("GitHub push event lies outside the recorded run")
    commit_sha = _sha(commit.get("sha"))
    parent = _sha(run.get("head_sha"))
    parents = commit.get("parents")
    if (
        not isinstance(parents, (list, tuple))
        or len(parents) != 1
        or parents[0] != parent
        or not parent.startswith(push.group("old"))
        or not commit_sha.startswith(push.group("new"))
    ):
        raise ValueError("Push SHA, checkout head and commit parent conflict")
    changed_paths = commit.get("changed_paths")
    if (
        not isinstance(changed_paths, (list, tuple))
        or "research/hourly_forecasts.jsonl" not in changed_paths
        or any(not isinstance(p, str) for p in changed_paths)
        or len(changed_paths) != len(set(changed_paths))
        or not set(changed_paths)
        <= {"research/hourly_forecasts.jsonl", "research/hourly_scores.jsonl"}
    ):
        raise ValueError("Unexpected ledger commit paths")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or len(rows) != 4:
        raise ValueError("Four metadata-only forecast rows required")
    projected: list[dict[str, object]] = []
    origin_time: datetime | None = None
    claimed_issued: datetime | None = None
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != _ROW_META:
            raise ValueError("Exact price-free ledger projection required")
        origin = _parse_utc(row["origin_hour_utc"], "Origin")
        issued = _parse_utc(row["issued_at_utc"], "Issued")
        close = _parse_utc(row["target_close_utc"], "Target close")
        if issued > push_at or origin.minute or origin.second or origin.microsecond:
            raise ValueError("Late/or malformed origin or issuance versus GitHub push")
        if row["version"] != "hourly-hybrid-ridge-v2":
            raise ValueError("Unknown existing deployed model version")
        if origin_time is None:
            origin_time = origin
            claimed_issued = issued
        if origin != origin_time or issued != claimed_issued:
            raise ValueError("Contradictory four-horizon origin or issuance")
        projected.append(
            {
                "github_run_id": run_id,
                "origin_hour_utc": int(origin.timestamp()),
                "horizon_hours": row["horizon_hours"],
                "claimed_issued_at_utc": int(issued.timestamp()),
                # A successful completed run is a conservative LATER upper bound
                # than its push-log event. Never qualify a forecast on the
                # earlier log clock if the job/run finishes after maturity.
                "claimed_publication_upper_bound_utc": conservative_publication_second,
                "target_close_utc": int(close.timestamp()),
            }
        )
    assert origin_time is not None
    observation = audit_elapsed_lead(
        {
            "first_origin_utc": int(origin_time.timestamp()),
            "stop_origin_exclusive_utc": int(origin_time.timestamp()) + HOUR,
            "horizons_hours": HORIZONS,
            "claim_semantics": claim_semantics,
        },
        projected,
    )
    if observation["missing_slot_count"]:
        raise ValueError("Incomplete four-horizon committed batch")
    return {
        # Only run/push metadata is cross-checked. The projected forecast rows
        # are NOT cryptographically bound to the claimed Git commit bytes.
        "status": (
            "GITHUB_RUN_PUSH_PROJECTION_BLOCKED"
            if observation["status"] == "BLOCKED"
            else "GITHUB_RUN_PUSH_PROJECTION_ONLY_UNVERIFIED"
        ),
        "run_id_claim": run_id,
        "commit_sha_claim": commit_sha,
        "push_at_utc_claim": push_at.isoformat(),
        "conservative_publication_upper_bound_utc_claim": run["updated_at"],
        "conservative_publication_upper_bound_ceiled_epoch_second": conservative_publication_second,
        "publication_bound_source": "github_completed_run_updated_at",
        "github_data_origin_authenticated_by_this_code": False,
        "projected_forecast_bytes_cryptographically_confirmed": False,
        "independent_first_publication_attested": False,
        "scientific_authorization": "NO_RUN",
        "observation": observation,
    }


_GIT_LEDGER_MAX_BYTES = 8_000_000
_DEPLOYED_FORECAST_KEYS = frozenset(
    {
        "version",
        "issued_at_utc",
        "origin_hour_utc",
        "target_hour_utc",
        "target_close_utc",
        "horizon_hours",
        "origin_close_usd",
        "forecast_usd",
        "persistence_usd",
        "observed_volatility_hourly",
        "training_hours",
        "resolved_training_examples",
        "holdout_selected_blend",
        "source",
        "research_only",
    }
)


def _git_blob_hash(payload: bytes) -> str:
    """Verify the Git object format, NOT third-party first-publication custody."""
    header = b"blob " + str(len(payload)).encode("ascii") + b"\0"
    # The Git object store uses SHA-1. Its known collision limitations are
    # separate from the additional SHA-256 digest returned for custody work.
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    found: dict[str, object] = {}
    for name, value in pairs:
        if name in found:
            raise ValueError("Duplicate key in appended forecast JSON")
        found[name] = value
    return found


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite or invalid forecast JSON value: {value}")


def bind_supplied_git_ledger_append(
    parent_blob: bytes,
    child_blob: bytes,
    parent_git_blob_sha: str,
    child_git_blob_sha: str,
    expected_projection: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Byte-bind four forecast metadata projections to supplied Git blobs.

    This has no network and no price calculations. Raw files *can contain*
    forecast prices; never pass locked outcomes or return their numeric values.
    SHA identifiers and bytes remain caller-supplied unless an independent
    reviewer authenticates both commits' Git trees and returned blob bodies.
    """
    if type(parent_blob) is not bytes or type(child_blob) is not bytes:
        raise ValueError("Both ledger Git blobs must be exact bytes")
    if (
        not parent_blob
        or not parent_blob.endswith(b"\n")
        or not child_blob.endswith(b"\n")
        or len(child_blob) > _GIT_LEDGER_MAX_BYTES
        or len(parent_blob) > _GIT_LEDGER_MAX_BYTES
    ):
        raise ValueError("Invalid or oversized newline-complete Git ledger blobs")
    if _git_blob_hash(parent_blob) != _sha(parent_git_blob_sha):
        raise ValueError("Parent Git blob SHA differs from supplied ledger bytes")
    if _git_blob_hash(child_blob) != _sha(child_git_blob_sha):
        raise ValueError("Child Git blob SHA differs from supplied ledger bytes")
    if not child_blob.startswith(parent_blob):
        raise ValueError("Child ledger is not byte-for-byte append-only")
    appendix = child_blob[len(parent_blob) :]
    if not appendix or b"\r" in appendix:
        raise ValueError("Noncanonical appended forecast ledger bytes")
    appended_lines = appendix.splitlines(keepends=True)
    if len(appended_lines) != len(HORIZONS) or any(
        not line.endswith(b"\n") or not line.strip() for line in appended_lines
    ):
        raise ValueError("Exactly four newline-complete appended forecast records required")
    if (
        not isinstance(expected_projection, Sequence)
        or isinstance(expected_projection, (str, bytes))
        or len(expected_projection) != len(HORIZONS)
    ):
        raise ValueError("Exactly four expected price-free metadata projections required")

    bound_projection: list[dict[str, object]] = []
    for index, line in enumerate(appended_lines):
        try:
            row = json.loads(
                line.decode("utf-8"),
                object_pairs_hook=_reject_duplicate_json_keys,
                parse_constant=_reject_json_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Malformed appended forecast JSON") from exc
        if (
            type(row) is not dict
            or set(row) != _DEPLOYED_FORECAST_KEYS
            or row.get("research_only") is not True
            or row.get("source") != "coinbase:exchange:BTC-USD:1h:close"
            or row.get("version") != "hourly-hybrid-ridge-v2"
            or type(row.get("horizon_hours")) is not int
        ):
            raise ValueError("Unexpected deployed forecast row schema")
        horizon = row["horizon_hours"]
        origin = _parse_utc(row["origin_hour_utc"], "Origin")
        issued = _parse_utc(row["issued_at_utc"], "Issued")
        target_hour = _parse_utc(row["target_hour_utc"], "Target hour")
        target_close = _parse_utc(row["target_close_utc"], "Target close")
        if origin != origin.replace(minute=0, second=0, microsecond=0):
            raise ValueError("Forecast origin must be UTC hour-aligned")
        if target_hour != origin + timedelta(hours=horizon):
            raise ValueError("Target hour inconsistent with origin and horizon")
        if target_close != target_hour + timedelta(hours=1):
            raise ValueError("Target close inconsistent with target hour")
        if issued < origin + timedelta(hours=1):
            raise ValueError("Claimed issuance precedes source candle close")
        projected = {key: row[key] for key in _ROW_META}
        expected = expected_projection[index]
        if not isinstance(expected, Mapping) or set(expected) != _ROW_META:
            raise ValueError("Exact price-free expected projection required")
        if projected != expected:
            raise ValueError("Claimed forecast projection differs from committed blob row")
        bound_projection.append(projected)
    if sorted(row["horizon_hours"] for row in bound_projection) != list(HORIZONS):
        raise ValueError("Four canonical forecast horizons required in appended blob")
    if len({row["origin_hour_utc"] for row in bound_projection}) != 1:
        raise ValueError("Append contains mismatched forecast origins")
    if len({row["issued_at_utc"] for row in bound_projection}) != 1:
        raise ValueError("Append contains mismatched issuance timestamps")

    return {
        "status": "SUPPLIED_GIT_FORECAST_APPEND_BYTES_MATCH_UNAUTHENTICATED",
        "forecast_rows_bound_to_supplied_git_blob_bytes": True,
        "appended_forecast_count": len(bound_projection),
        "parent_git_blob_sha_claim": parent_git_blob_sha,
        "child_git_blob_sha_claim": child_git_blob_sha,
        "parent_blob_sha256": hashlib.sha256(parent_blob).hexdigest(),
        "child_blob_sha256": hashlib.sha256(child_blob).hexdigest(),
        "github_tree_shas_independently_authenticated_by_this_code": False,
        "independent_first_publication_attested": False,
        "price_or_outcome_values_returned": False,
        "scientific_authorization": "NO_RUN",
        "projected_metadata": bound_projection,
    }


_FORECAST_LEDGER_GIT_PATH = "research/hourly_forecasts.jsonl"
_ALLOWED_APPEND_COMMIT_PATHS = frozenset(
    {"research/hourly_forecasts.jsonl", "research/hourly_scores.jsonl"}
)


def _tree_leaf_identifiers(
    tree: Mapping[str, object],
) -> dict[str, tuple[str, str, str]]:
    """Project every supplied non-directory Git tree leaf to its identity.

    Recursive tree listings include directory nodes whose tree SHA necessarily
    changes when a child changes. Compare the leaf identities, not directories.
    """
    if not isinstance(tree, Mapping):
        raise ValueError("Exact Git tree metadata required")
    _sha(tree.get("sha"))
    entries = tree.get("entries")
    if (
        tree.get("truncated") is not False
        or not isinstance(entries, (list, tuple))
        or len(entries) > 100_000
    ):
        raise ValueError("Complete bounded Git tree entries required")
    all_paths: set[str] = set()
    leaves: dict[str, tuple[str, str, str]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("Malformed Git tree entry")
        path = entry.get("path")
        if not isinstance(path, str) or not path or path in all_paths:
            raise ValueError("Duplicate or invalid Git tree path")
        all_paths.add(path)
        kind = entry.get("type")
        mode = entry.get("mode")
        sha = _sha(entry.get("sha"))
        if kind not in ("tree", "blob", "commit") or not isinstance(mode, str):
            raise ValueError("Unexpected Git tree leaf identity")
        if kind != "tree":
            leaves[path] = (kind, mode, sha)
    forecast = leaves.get(_FORECAST_LEDGER_GIT_PATH)
    if forecast is None:
        raise ValueError("Forecast ledger leaf missing or duplicated in Git tree")
    if forecast[:2] != ("blob", "100644"):
        raise ValueError("Forecast ledger must be an ordinary Git blob")
    return leaves


def bind_supplied_git_commit_tree_chain(
    parent_commit: Mapping[str, object],
    child_commit: Mapping[str, object],
    parent_tree: Mapping[str, object],
    child_tree: Mapping[str, object],
    parent_forecast_blob: bytes,
    child_forecast_blob: bytes,
    expected_projection: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Cross-check supplied Git commit ancestry/tree paths and ledger byte append.

    Callers must independently fetch all objects from a trusted GitHub API,
    verify endpoint identity, and preserve the fetched responses. This helper
    does NOT authenticate the server, timestamp, or full Git tree object bytes.
    """
    if not isinstance(parent_commit, Mapping) or not isinstance(child_commit, Mapping):
        raise ValueError("Supplied Git commit metadata required")
    parent_sha = _sha(parent_commit.get("sha"))
    child_sha = _sha(child_commit.get("sha"))
    if parent_sha == child_sha:
        raise ValueError("Child Git commit must differ from its parent")
    parents = child_commit.get("parents")
    if type(parents) not in (tuple, list) or parents != [parent_sha]:
        raise ValueError("Child Git commit must have exactly the supplied parent SHA")
    parent_tree_sha = _sha(parent_commit.get("tree_sha"))
    child_tree_sha = _sha(child_commit.get("tree_sha"))
    if (
        _sha(parent_tree.get("sha")) != parent_tree_sha
        or _sha(child_tree.get("sha")) != child_tree_sha
    ):
        raise ValueError("Git tree SHA does not match its claimed commit")
    changed_paths = child_commit.get("changed_paths")
    if (
        type(changed_paths) not in (tuple, list)
        or not all(isinstance(path, str) for path in changed_paths)
        or len(changed_paths) != len(set(changed_paths))
        or _FORECAST_LEDGER_GIT_PATH not in changed_paths
        or not set(changed_paths) <= _ALLOWED_APPEND_COMMIT_PATHS
    ):
        raise ValueError("Unexpected Git commit paths or no appended forecast ledger")
    parent_leaves = _tree_leaf_identifiers(parent_tree)
    child_leaves = _tree_leaf_identifiers(child_tree)
    actual_changes = {
        path
        for path in parent_leaves.keys() | child_leaves.keys()
        if parent_leaves.get(path) != child_leaves.get(path)
    }
    if actual_changes != set(changed_paths):
        raise ValueError("Git tree changed paths disagree with commit change list")
    parent_blob_sha = parent_leaves[_FORECAST_LEDGER_GIT_PATH][2]
    child_blob_sha = child_leaves[_FORECAST_LEDGER_GIT_PATH][2]
    if parent_blob_sha == child_blob_sha or parent_tree_sha == child_tree_sha:
        raise ValueError("Forecast Git blob/tree unchanged by alleged append commit")
    byte_binding = bind_supplied_git_ledger_append(
        parent_forecast_blob,
        child_forecast_blob,
        parent_blob_sha,
        child_blob_sha,
        expected_projection,
    )
    return {
        "status": "SUPPLIED_GIT_COMMIT_TREE_FORECAST_APPEND_MATCH_UNAUTHENTICATED",
        "claimed_parent_commit_sha": parent_sha,
        "claimed_child_commit_sha": child_sha,
        "claimed_parent_tree_sha": parent_tree_sha,
        "claimed_child_tree_sha": child_tree_sha,
        "claimed_parent_forecast_git_blob_sha": parent_blob_sha,
        "claimed_child_forecast_git_blob_sha": child_blob_sha,
        "forecast_rows_bound_to_supplied_tree_and_blob_metadata": True,
        "fetched_git_tree_objects_independently_authenticated_by_this_code": False,
        "server_first_publication_independently_attested": False,
        "scientific_authorization": "NO_RUN",
        "byte_binding": byte_binding,
    }
