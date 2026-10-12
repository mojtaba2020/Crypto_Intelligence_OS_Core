"""Negative leakage/scope tests; no CatBoost dependency or live provider calls."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import challenger_v3_catboost_exploratory as exploratory


def _candles(n: int = 114) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(n):
        close = 100 * math.exp(0.001 * index + 0.004 * math.sin(index / 3))
        rows.append(
            {
                "timestamp": 1_704_067_200 + index * 604_800,
                "is_complete": True,
                "source_bars": 168,
                "expected_source_bars": 168,
                "open": close * 0.998,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1000.0 + index,
            }
        )
    return rows


def _folds(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return exploratory.build_folds(
        rows,
        family="weekly",
        horizon=2,
        train_end=102,
        stride=3,
        source_interval_seconds=3600,
        max_folds=3,
    )


def test_mature_labels_only_and_no_future_feature_injection() -> None:
    candles = _candles()
    folds = _folds(candles)
    assert [fold["origin"] for fold in folds] == [102, 105, 108]
    assert all(fold["last_train_target_index"] <= fold["origin"] for fold in folds)
    first = folds[0]
    candles[112]["close"] = float(candles[112]["close"]) * 1.1
    candles[112]["open"] = float(candles[112]["close"]) * 0.998
    candles[112]["high"] = float(candles[112]["close"]) * 1.01
    candles[112]["low"] = float(candles[112]["close"]) * 0.99
    # Rows after the first target cannot affect that fold's training or features.
    first_after = _folds(candles)[0]
    assert (first_after["x"], first_after["y"], first_after["forecast_x"]) == (
        first["x"],
        first["y"],
        first["forecast_x"],
    )


@pytest.mark.parametrize("corruption", ["incomplete", "gap", "nan"])
def test_missing_or_incomplete_candles_fail_closed(corruption: str) -> None:
    rows = _candles()
    if corruption == "incomplete":
        rows[65]["is_complete"] = False
    elif corruption == "gap":
        rows[65]["timestamp"] = int(rows[65]["timestamp"]) + 604_800
    else:
        rows[65]["close"] = float("nan")
    with pytest.raises(ValueError):
        _folds(rows)


def _write_approved_slice(
    tmp_path: Path,
    payload: dict[str, object] | None = None,
) -> tuple[Path, Path, dict[str, object]]:
    candles = _candles()
    data: dict[str, object] = payload or {
        "scope": exploratory.SCOPE,
        "source": "synthetic-weekly-hourly",
        "candles": candles,
    }
    input_path = tmp_path / "fixture.development.json"
    raw = json.dumps(data, sort_keys=True).encode()
    input_path.write_bytes(raw)
    manifest = {
        "scope": exploratory.SCOPE,
        "source": "synthetic-weekly-hourly",
        "family": "weekly",
        "slice_sha256": hashlib.sha256(raw).hexdigest(),
        "source_interval_seconds": 3600,
        "first_open_timestamp": candles[0]["timestamp"],
        "last_open_timestamp": candles[-1]["timestamp"],
        "approved_dev_end_exclusive": candles[-1]["timestamp"] + 604_800,
        "extraction_asof_timestamp": candles[-1]["timestamp"] + 604_801,
        "source_audit_sha256": "a" * 64,
    }
    manifest_path = tmp_path / "operator.audit.json"
    manifest_bytes = json.dumps(manifest).encode()
    manifest_path.write_bytes(manifest_bytes)
    params: dict[str, object] = {
        "approved_root": tmp_path,
        "manifest_path": manifest_path,
        "manifest_root": tmp_path,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "family": "weekly",
    }
    return input_path, manifest_path, params


def test_scope_inputs_refused_before_modeling(tmp_path: Path) -> None:
    path, _, params = _write_approved_slice(tmp_path)
    payload = json.loads(path.read_text())
    payload["scope"] = "fresh_locked_oos"
    # Even if input content hash is updated, the scope must be rejected.
    bad = json.dumps(payload).encode()
    path.write_bytes(bad)
    manifest = json.loads(Path(params["manifest_path"]).read_text())
    manifest["slice_sha256"] = hashlib.sha256(bad).hexdigest()
    manifest_raw = json.dumps(manifest).encode()
    Path(params["manifest_path"]).write_bytes(manifest_raw)
    params["manifest_sha256"] = hashlib.sha256(manifest_raw).hexdigest()
    with pytest.raises(ValueError, match="Locked OOS"):
        exploratory.load_development_slice(path, **params)
    with pytest.raises(ValueError, match="forbidden"):
        exploratory._safe_path(
            tmp_path / "fresh_locked_oos.development.json",
            root=tmp_path,
            suffix=".development.json",
        )


def test_manifest_pin_enforces_exact_loaded_bytes(tmp_path: Path) -> None:
    path, _, params = _write_approved_slice(tmp_path)
    rows, manifest, digest = exploratory.load_development_slice(path, **params)
    original = path.read_bytes()
    assert digest == hashlib.sha256(original).hexdigest()
    assert len(rows) == len(_candles())
    assert manifest["family"] == "weekly"
    path.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="SHA-256"):
        exploratory.load_development_slice(path, **params)
    assert digest == hashlib.sha256(original).hexdigest()


def test_parent_symlinks_refused_for_input_and_output(tmp_path: Path) -> None:
    inner = tmp_path / "real"
    inner.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(inner, target_is_directory=True)
    for suffix in (".development.json", ".exploratory.json"):
        with pytest.raises(ValueError, match="Symlink"):
            exploratory._safe_path(alias / ("fixture" + suffix), root=tmp_path, suffix=suffix)


def test_inconsistent_source_counts_rejected_even_when_complete(tmp_path: Path) -> None:
    payload = {
        "scope": exploratory.SCOPE,
        "source": "synthetic-weekly-hourly",
        "candles": _candles(),
    }
    payload["candles"][5]["source_bars"] = 1
    path, _, params = _write_approved_slice(tmp_path, payload)
    with pytest.raises(ValueError, match="completeness"):
        exploratory.load_development_slice(path, **params)


def test_weekly_origin_must_be_monday_utc() -> None:
    rows = _candles()
    rows[0]["timestamp"] += 1
    with pytest.raises(ValueError, match="Noncanonical"):
        _folds(rows)


def test_daily_and_monthly_calendar_reject_bad_alignment() -> None:
    assert exploratory._canonical_open(1_704_067_200, "daily")
    assert exploratory._canonical_open(1_704_067_200, "weekly")
    assert exploratory._canonical_open(1_704_067_200, "monthly")
    assert not exploratory._canonical_open(1_704_067_201, "daily")
    assert not exploratory._canonical_open(1_704_067_201, "weekly")
    assert not exploratory._canonical_open(1_706_832_000, "monthly")


def test_first_future_bar_does_not_affect_features() -> None:
    rows = _candles()
    before = _folds(rows)[0]
    target = rows[103]  # immediately after first diagnostic origin 102
    for key in ("open", "high", "low", "close", "volume"):
        target[key] = float(target[key]) * 1.01
    after = _folds(rows)[0]
    assert (before["x"], before["y"], before["forecast_x"]) == (
        after["x"],
        after["y"],
        after["forecast_x"],
    )
    assert before["target_maturity_timestamp"] == after["target_maturity_timestamp"]


def test_catboost_missing_dependency_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_name: str) -> None:
        raise ImportError("not installed")

    monkeypatch.setattr(exploratory.importlib, "import_module", missing)
    with pytest.raises(RuntimeError, match="Optional CatBoost is not installed"):
        exploratory._new_estimator()


def test_fold_isolation_seed_and_descriptive_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    constructed: list[object] = []
    seeds: list[int] = []

    class FakeCatBoost:
        def __init__(self, **kwargs: object):
            constructed.append(self)
            seeds.append(int(kwargs["random_seed"]))
            assert kwargs["allow_writing_files"] is False
            assert kwargs["thread_count"] == 1
            self.prediction = 0.0

        def fit(self, x: list[list[float]], y: list[float]) -> None:
            assert len(x) == len(y)
            self.prediction = sum(y) / len(y)

        def predict(self, x: list[list[float]]) -> list[float]:
            assert len(x) == 1
            return [self.prediction]

    monkeypatch.setattr(
        exploratory.importlib,
        "import_module",
        lambda _: SimpleNamespace(CatBoostRegressor=FakeCatBoost),
    )
    kw = {
        "family": "weekly",
        "horizon": 2,
        "train_end": 102,
        "stride": 3,
        "source_interval_seconds": 3600,
        "max_folds": 3,
    }
    first = exploratory.evaluate_exploratory(_candles(), **kw)
    second = exploratory.evaluate_exploratory(_candles(), **kw)
    assert first == second
    assert first["status"] == "EXPLORATORY_ONLY"
    assert first["freeze"] == "NO_FREEZE"
    assert first["fresh_locked_oos_access"] is False
    assert first["n_origins"] == 3
    assert len(constructed) == 6
    assert len(set(map(id, constructed))) == 6
    assert seeds == [exploratory.SEED] * 6


def test_cost_bounds_and_immature_diagnostic_rejected() -> None:
    with pytest.raises(ValueError, match="budget"):
        exploratory.build_folds(
            _candles(),
            family="weekly",
            horizon=2,
            train_end=102,
            stride=1,
            source_interval_seconds=3600,
            max_folds=13,
        )
    with pytest.raises(ValueError, match="insufficient"):
        exploratory.build_folds(
            _candles(),
            family="weekly",
            horizon=2,
            train_end=113,
            stride=1,
            source_interval_seconds=3600,
        )


@pytest.mark.parametrize(("source_interval", "expected_bars"), [(3600, 168), (86400, 7)])
def test_audited_source_cadence_propagates_from_loader_to_full_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_interval: int,
    expected_bars: int,
) -> None:
    """Real parser/loader/folds/output; synthetic data and stubbed estimator only."""
    input_root = tmp_path / "input"
    manifest_root = tmp_path / "manifests"
    output_root = tmp_path / "outputs"
    for root in (input_root, manifest_root, output_root):
        root.mkdir()
    path, manifest_path, _ = _write_approved_slice(input_root)
    payload = json.loads(path.read_text())
    for row in payload["candles"]:
        row["source_bars"] = expected_bars
        row["expected_source_bars"] = expected_bars
    input_bytes = json.dumps(payload).encode()
    path.write_bytes(input_bytes)
    manifest = json.loads(manifest_path.read_text())
    manifest["source_interval_seconds"] = source_interval
    manifest["slice_sha256"] = hashlib.sha256(input_bytes).hexdigest()
    manifest_path = manifest_path.replace(manifest_root / "operator.audit.json")
    manifest_bytes = json.dumps(manifest).encode()
    manifest_path.write_bytes(manifest_bytes)
    pinned_hash = hashlib.sha256(manifest_bytes).hexdigest()

    class StubEstimator:
        def fit(self, x: list[list[float]], y: list[float]) -> None:
            assert len(x) == len(y)

        def predict(self, rows: list[list[float]]) -> list[float]:
            return [0.0] * len(rows)

    monkeypatch.setattr(exploratory, "_new_estimator", StubEstimator)
    monkeypatch.setattr(exploratory.importlib.metadata, "version", lambda _: "stub-only")
    output_path = output_root / "synthetic.exploratory.json"
    argv = [
        "catboost-lane",
        "--enable-exploratory",
        "--approved-input-root",
        str(input_root),
        "--approved-output-root",
        str(output_root),
        "--approved-manifest-root",
        str(manifest_root),
        "--input",
        str(path),
        "--manifest",
        str(manifest_path),
        "--approved-manifest-sha256",
        pinned_hash,
        "--output",
        str(output_path),
        "--family",
        "weekly",
        "--horizon",
        "2",
        "--train-end",
        "102",
        "--stride",
        "3",
        "--max-folds",
        "3",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    exploratory.main()
    result = json.loads(output_path.read_text())
    assert result["source_interval_seconds"] == source_interval
    assert result["input_sha256"] == manifest["slice_sha256"]
    assert result["n_origins"] == 3
    assert result["freeze"] == "NO_FREEZE"
    assert result["catboost_version"] == "stub-only"
    with pytest.raises(SystemExit):
        exploratory.main()  # O_EXCL/output-preservation guard


@pytest.mark.parametrize(("parent", "child"), [(0, 1), (1, 0), (0, 2), (2, 0), (1, 2), (2, 1)])
def test_every_pair_of_nested_approved_roots_is_rejected(
    tmp_path: Path, parent: int, child: int
) -> None:
    roots = [tmp_path / "input", tmp_path / "output", tmp_path / "manifest"]
    roots[child] = roots[parent] / "nested"
    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="pairwise disjoint"):
        exploratory._isolated_roots(*roots)


def test_separate_sibling_roots_are_accepted(tmp_path: Path) -> None:
    roots = [tmp_path / name for name in ("input", "output", "manifest")]
    for root in roots:
        root.mkdir()
    exploratory._isolated_roots(*roots)


@pytest.mark.skipif(
    not hasattr(os, "mkfifo") or not hasattr(os, "O_NONBLOCK"),
    reason="POSIX FIFO support needed",
)
def test_fifo_input_rejected_without_blocking(tmp_path: Path) -> None:
    """A regression to blocking os.open must fail by subprocess timeout."""
    fifo = tmp_path / "synthetic-pipe"
    os.mkfifo(fifo)
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "from scripts import challenger_v3_catboost_exploratory as lane\n"
        "try:\n"
        "    lane._read_bounded(Path(sys.argv[1]), 100)\n"
        "except ValueError:\n"
        "    print('rejected')\n"
        "else:\n"
        "    raise SystemExit(3)\n"
    )
    # Trusted sys.executable, literal inline test program, temporary FIFO, fixed timeout.
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script, str(fifo)],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "rejected"
