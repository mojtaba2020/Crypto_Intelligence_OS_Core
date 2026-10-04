#!/usr/bin/env python3
"""Deterministic research-agent curriculum for broad V3 model development.

Agents do not vote models into production. They allocate development attention
across horizons/model families and emit bounded hypotheses for the tournament.
"""
from __future__ import annotations
import json

HORIZONS=("1d","2d","3d","1w","2w","3w")
AGENTS=(
 "V3-CLASSICAL","V3-ROBUST","V3-TREES","V3-REGIME",
 "V3-STATS","V3-AUDIT","V3-DEVIL","V3-ORCH",
)
MODEL_FAMILIES={
 "linear_regularized":("ridge","elastic_net","huber","bayesian_ridge"),
 "randomized_trees":("random_forest","random_forest_sqrt","random_forest_leaf10","extra_trees","extra_trees_sqrt","extra_trees_leaf10"),
 "boosting":("boosting","hist_gradient_boosting","gradient_boosting_huber","gradient_boosting_absolute","hist_gradient_boosting_absolute","ada_boost"),
}
def plan():
    tasks=[]
    for h in HORIZONS:
        for family,models in MODEL_FAMILIES.items():
            tasks.append({"horizon":h,"family":family,"models":models,
              "objective":"beat persistence on causal development evidence without tuning on locked OOS",
              "required_checks":["paired losses","chronological stability","feature ablation","leakage audit"]})
    return {"status":"V3_BROAD_MODEL_CURRICULUM_DEVELOPMENT_ONLY",
      "agents":AGENTS,"tasks":tasks,"fresh_locked_oos_access":False,
      "v2_locked_oos_used_for_tuning":False,"production_eligible":False,
      "rule":"expand model-family diversity before deep tuning; no agent vote can crown a champion"}
if __name__=="__main__": print(json.dumps(plan(),indent=2))
