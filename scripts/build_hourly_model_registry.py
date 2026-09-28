#!/usr/bin/env python3
"""Build a fail-closed hourly model registry from statistical evidence."""

from __future__ import annotations
import argparse, json
from pathlib import Path

HORIZONS=(1,2,3,4,12)

def build(judge: dict, prospective: dict | None=None) -> dict:
    rows={int(r["horizon_hours"]):r for r in judge.get("results",[])}
    if set(rows)!=set(HORIZONS):
        raise ValueError("Judge must cover locked hourly horizons")
    prospective_rows={}
    if prospective:
        prospective_rows={(r["version"],int(r["horizon_hours"])):r for r in prospective.get("results",[])}
    entries=[]
    for h in HORIZONS:
        row=rows[h]
        challenger=row["selected_on_validation"]
        historical_ok=row.get("decision")=="CHALLENGER_ELIGIBLE_FOR_FURTHER_VALIDATION"
        matching=[r for (_v,hh),r in prospective_rows.items() if hh==h and r.get("prospective_evidence")=="STATISTICALLY_CONFIRMED_RESEARCH_EDGE"]
        prospective_ok=bool(matching)
        champion=challenger if historical_ok and prospective_ok else "persistence"
        entries.append({
            "horizon_hours":h,
            "champion":champion,
            "challenger":challenger,
            "historical_gate_passed":historical_ok,
            "prospective_gate_passed":prospective_ok,
            "live_authorized":historical_ok and prospective_ok,
            "fallback":"persistence",
        })
    return {
        "status":"HOURLY_MODEL_REGISTRY_V1",
        "policy":"fail_closed_historical_plus_prospective_confirmation",
        "automatic_promotion":False,
        "entries":entries,
    }

def main():
    p=argparse.ArgumentParser(); p.add_argument("--judge",type=Path,required=True); p.add_argument("--prospective",type=Path); p.add_argument("--output",type=Path,required=True); a=p.parse_args()
    judge=json.loads(a.judge.read_text()); prospective=json.loads(a.prospective.read_text()) if a.prospective and a.prospective.exists() else None
    result=build(judge,prospective); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,indent=2))
if __name__=="__main__": main()
