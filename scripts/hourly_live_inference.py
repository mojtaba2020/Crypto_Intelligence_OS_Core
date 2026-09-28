#!/usr/bin/env python3
"""Deterministic live inference adapters matching locked hourly tournament families."""
from __future__ import annotations
import math
try:
    from .train_hourly_ridge_tournament import _features as ridge_features, _ridge_fit
    from .train_hourly_extra_trees_tournament import _features as tree_features, _forest_predict
    from .train_hourly_boosting_tournament import _features as boost_features, _boost_predict
except ImportError:
    from train_hourly_ridge_tournament import _features as ridge_features, _ridge_fit
    from train_hourly_extra_trees_tournament import _features as tree_features, _forest_predict
    from train_hourly_boosting_tournament import _features as boost_features, _boost_predict

SUPPORTED=("ridge","extra_trees","boosting")

def predict(model:str, closes:list[float], horizon:int)->float:
    if model not in SUPPORTED: raise ValueError("Unsupported hourly model: "+model)
    if horizon not in (1,2,3,4,12): raise ValueError("Unsupported hourly horizon")
    if len(closes)<241 or any(x<=0 for x in closes): raise ValueError("Need >=241 positive closed hourly prices")
    test_origin=len(closes)-1
    xs=[]; ys=[]
    feature_fn={"ridge":ridge_features,"extra_trees":tree_features,"boosting":boost_features}[model]
    for origin in range(48,test_origin-horizon+1):
        xs.append(feature_fn(closes,origin))
        ys.append(math.log(closes[origin+horizon]/closes[origin]))
    x=feature_fn(closes,test_origin)
    if model=="ridge": ret=sum(w*v for w,v in zip(_ridge_fit(xs,ys,1.0),x,strict=True))
    elif model=="extra_trees": ret=_forest_predict(xs,ys,x,seed=10_000*horizon+test_origin)
    else: ret=_boost_predict(xs,ys,x)
    return closes[-1]*math.exp(ret)
