#!/usr/bin/env python3
"""Evaluate locked hourly model families on an independent exchange archive."""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
try:
    from .paired_block_bootstrap import paired_block_bootstrap
    from .hourly_live_inference import predict
except ImportError:
    from paired_block_bootstrap import paired_block_bootstrap
    from hourly_live_inference import predict
from crypto_intelligence_os.adapters.market_data.historical_archive import HistoricalOHLCVArchive,validate_hourly_continuity

HORIZONS=(1,2,3,4,12)

def evaluate(database:Path,source:str,instrument:str,model:str,step:int=24)->dict:
    with HistoricalOHLCVArchive(database) as a: bars=a.read(instrument_id=instrument,timeframe="1h",source_id=source)
    validate_hourly_continuity(bars); closes=[float(b.close) for b in bars]
    rows=[]
    for h in HORIZONS:
        ml=[]; bl=[]
        for origin in range(240,len(closes)-h,step):
            history=closes[:origin+1]; pred=predict(model,history,h); actual=closes[origin+h]; current=closes[origin]
            ml.append(abs(pred-actual)/actual); bl.append(abs(current-actual)/actual)
        if len(ml)<40: raise ValueError("Independent replication requires >=40 samples per horizon")
        gate=paired_block_bootstrap(ml,bl,block_length=min(7,len(ml)))
        rows.append({"horizon_hours":h,"samples":len(ml),"model":model,"model_mape_pct":100*sum(ml)/len(ml),"persistence_mape_pct":100*sum(bl)/len(bl),"statistical_gate":gate})
    ordered=sorted(rows,key=lambda r:(r["statistical_gate"]["one_sided_null_centered_p_value"],r["horizon_hours"])); open_=True
    for rank,row in enumerate(ordered,1):
        g=row["statistical_gate"]; threshold=.05/(len(ordered)-rank+1); reject=open_ and g["one_sided_null_centered_p_value"]<=threshold
        if not reject: open_=False
        g.update({"holm_rank":rank,"holm_threshold":threshold,"holm_reject":reject})
        row["replication_decision"]="REPLICATED_RESEARCH_EDGE" if reject and g["gate"]=="PASS" else "NOT_REPLICATED"
    return {"status":"INDEPENDENT_EXCHANGE_REPLICATION_V1","source_id":source,"instrument_id":instrument,"model":model,"familywise_alpha":.05,"multiple_comparison_method":"holm_bonferroni_5_horizons","automatic_promotion":False,"rows":rows}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--database",type=Path,required=True); p.add_argument("--source",required=True); p.add_argument("--instrument",required=True); p.add_argument("--model",choices=["ridge","extra_trees","boosting"],required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args()
    r=evaluate(a.database,a.source,a.instrument,a.model); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(r,indent=2)+"\n"); print(json.dumps(r,indent=2))
if __name__=="__main__": main()
