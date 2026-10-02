"""Local fail-closed workers for Challenger V3 research tasks.

These workers produce auditable evidence packets from declared inputs. They do
not call model providers, access fresh OOS, authorize production, or trade.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.challenger_v3_orchestrator import build_plan


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _packet_path(repo_root: Path, task_id: str) -> Path:
    return repo_root / "artifacts" / "v3-agent-evidence" / f"{task_id}.json"


def _completed_upstream(repo_root: Path, task_id: str) -> bool:
    path = _packet_path(repo_root, task_id)
    if not path.is_file():
        return False
    packet = json.loads(path.read_text(encoding="utf-8"))
    return packet.get("result", {}).get("status") == "completed"


def _feature_spec() -> dict:
    return {
        "version": "v3-pit-features-1",
        "availability_rule": "feature_at_t_uses_information_available_at_or_before_t",
        "families": {
            "returns": ["log_return_1", "log_return_3", "log_return_7", "log_return_14", "log_return_30"],
            "trend": ["close_vs_sma_7", "close_vs_sma_30", "close_vs_sma_90", "sma_7_vs_30"],
            "volatility": ["realized_vol_7", "realized_vol_30", "true_range_14"],
            "range": ["distance_from_30d_high", "distance_from_30d_low", "range_position_30"],
            "volume": ["volume_z_30", "volume_change_7"],
            "calendar": ["day_of_week", "month_of_year"],
        },
        "forbidden": ["centered_windows", "future_fills", "future_normalization", "future_labels", "locked_oos_derived_features"],
        "fit_policy": "fit_scalers_and_encoders_on_each_training_fold_only",
    }


def _statistical_gate_spec() -> dict:
    return {
        "version": "v3-stat-gate-1",
        "champion": "persistence",
        "primary_loss": "absolute_percentage_error",
        "paired_unit": "forecast_origin",
        "alpha": 0.05,
        "confidence_interval": "95_percent_dependence_aware_moving_block_bootstrap",
        "multiplicity": "Holm_across_predeclared_horizon_family",
        "pass_rule": [
            "mean_loss_improvement_gt_0",
            "confidence_interval_lower_bound_gt_0",
            "holm_adjusted_null_rejected_true",
        ],
        "required_reporting": ["MAPE", "direction_accuracy", "sample_count", "origin_level_paired_losses"],
        "locked_oos_policy": "future_V3_locked_OOS_evaluated_once_after_freeze_and_never_used_for_tuning",
    }


def _classical_spec() -> dict:
    return {
        "version": "v3-classical-candidates-1",
        "target": "future_close_by_predeclared_horizon",
        "candidates": [
            {"name": "ridge", "config": {"alpha": 1.0, "scaler": "train_fold_only"}},
            {"name": "elastic_net", "config": {"alpha": 0.0001, "l1_ratio": 0.25, "max_iter": 5000, "random_state": 20261002}},
            {"name": "extra_trees", "config": {"n_estimators": 300, "min_samples_leaf": 5, "random_state": 20261002}},
            {"name": "random_forest", "config": {"n_estimators": 300, "min_samples_leaf": 5, "max_features": 0.75, "random_state": 20261002}},
            {"name": "hist_gradient_boosting", "config": {"learning_rate": 0.05, "max_iter": 200, "max_leaf_nodes": 15, "l2_regularization": 1.0, "random_state": 20261002}},
        ],
        "selection": "development_validation_only_then_deterministic_tie_break",
        "forbidden": ["fresh_locked_oos", "V2_locked_oos_tuning", "production_promotion"],
    }


def _neural_spec() -> dict:
    return {
        "version": "v3-neural-adapters-1",
        "status": "adapter_spec_only",
        "families": [
            {"name": "tcn", "input": "point_in_time_sequence", "seed": 20261002},
            {"name": "lstm", "input": "point_in_time_sequence", "seed": 20261002},
            {"name": "transformer_encoder", "input": "point_in_time_sequence", "seed": 20261002},
        ],
        "requirements": [
            "training_fold_only_normalization",
            "walk_forward_validation",
            "early_stopping_on_validation_only",
            "deterministic_seed_recorded",
            "parameter_count_reported",
        ],
        "forbidden": ["fresh_locked_oos", "V2_locked_oos_tuning", "production_promotion"],
    }


def execute_task(task: dict, *, repo_root: Path) -> dict:
    """Execute one bounded local task and return a contract-shaped packet."""
    evidence: list[dict] = []
    missing: list[str] = []

    if task["id"] == "data_manifest_audit":
        manifest = repo_root / "artifacts" / "prepared" / "prepared_manifest.json"
        if manifest.is_file():
            evidence.append(
                {
                    "path": str(manifest.relative_to(repo_root)),
                    "sha256": _sha256(manifest),
                    "bytes": manifest.stat().st_size,
                }
            )
        else:
            missing.append("artifacts/prepared/prepared_manifest.json")
    elif task["id"] in {"point_in_time_feature_spec", "statistical_gate_spec"}:
        if not _completed_upstream(repo_root, "data_manifest_audit"):
            missing.append("completed data_manifest_audit evidence packet")
        else:
            spec = _feature_spec() if task["id"] == "point_in_time_feature_spec" else _statistical_gate_spec()
            evidence.append({"upstream_task": "data_manifest_audit", "spec": spec})
    elif task["id"] in {"classical_candidate_spec", "neural_adapter_spec"}:
        if not _completed_upstream(repo_root, "point_in_time_feature_spec"):
            missing.append("completed point_in_time_feature_spec evidence packet")
        else:
            spec = _classical_spec() if task["id"] == "classical_candidate_spec" else _neural_spec()
            evidence.append({"upstream_task": "point_in_time_feature_spec", "spec": spec})
    else:
        missing.append("upstream task evidence packet")

    status = "completed" if not missing else "blocked"
    return {
        "schema_version": 1,
        "agent_id": task["agent"],
        "role": task["role"],
        "task_id": task["id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": task["scope"],
        "hypothesis": "Task can be evaluated from declared development/validation evidence.",
        "method": "bounded_local_worker_v1",
        "result": {"status": status},
        "evidence": evidence,
        "counterevidence": [],
        "missing_data": missing,
        "leakage_checks": {
            "fresh_oos_access": False,
            "production_eligible": False,
        },
        "reproducibility": {"worker": "scripts/challenger_v3_workers.py"},
        "recommendation": "continue" if status == "completed" else "audit",
        "production_eligible": False,
    }


def run_ready_tasks(*, repo_root: Path, output_dir: Path) -> list[Path]:
    """Run bounded V3 waves through classical/neural candidate specification."""
    plan = build_plan()
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for wave in plan["waves"][:3]:
        for task in wave:
            packet = execute_task(task, repo_root=repo_root)
            path = output_dir / f'{task["id"]}.json'
            path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            written.append(path)
    return written
