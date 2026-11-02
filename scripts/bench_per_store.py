"""Benchmark: shared model against per-store models on data/samples/large (needs the ground-truth file).

Run from the repository root: python scripts/bench_per_store.py
"""
import io, os, time, resource, sys
from pathlib import Path
import pandas as pd
from freshcast.byod import analyze as A
from freshcast.byod.forecast_cache import FORECASTS
S=Path(__file__).resolve().parents[1] / "data/samples/large"
sales=(S/"absatz_gross.csv").read_bytes()
truth=pd.read_csv(S/"zukunft_wahrheit.csv",sep=";",encoding="utf-8-sig",dayfirst=True)
truth["Datum"]=pd.to_datetime(truth["Datum"],dayfirst=True)
def cpu():
    r=resource.getrusage(resource.RUSAGE_SELF);return r.ru_utime+r.ru_stime
def run(mode):
    FORECASTS.clear();c0,t0=cpu(),time.time()
    out=A.analyze(sales,None,None,per_store=mode)
    return out,time.time()-t0,cpu()-c0
res={}
for mode in (False,True):
    out,w,c=run(mode)
    rows=[]
    for it in out["items"]:
        for p in it["series"]:
            if p["actual"] is None:
                rows.append((it["store_id"],it["sku"],pd.Timestamp(p["date"]),p["point"],p["lower"],p["upper"]))
    f=pd.DataFrame(rows,columns=["Filiale","Artikelnummer","Datum","point","lower","upper"]).merge(truth,on=["Filiale","Artikelnummer","Datum"])
    wape=(f.point-f.Menge).abs().sum()/f.Menge.sum()
    cov=((f.Menge>=f.lower)&(f.Menge<=f.upper)).mean()
    bias=(f.point.sum()-f.Menge.sum())/f.Menge.sum()
    res[mode]=(wape,cov,bias,w,c,len(f))
    print("per_store" if mode else "shared   ","n=%d WAPE=%.4f coverage=%.3f bias=%+.3f wall=%.1fs cpu=%.1fs"%(len(f),wape,cov,bias,w,c),flush=True)
# change one store only
import re
txt=sales.decode("utf-8-sig")
lines=txt.split("\n")
store=sorted({l.split(";")[0] for l in lines[1:] if l})[0]
last=max(i for i,l in enumerate(lines) if l.startswith(store+";"))
parts=lines[last].split(";");parts[4]=str(int(parts[4])+7);lines[last]=";".join(parts)
changed=("﻿"+"\n".join(lines)).encode("utf-8")
FORECASTS.clear();A.analyze(sales,None,None,per_store=True)
c0,t0=cpu(),time.time();A.analyze(changed,None,None,per_store=True);print("per_store, 1 of 3 stores changed: wall=%.1fs cpu=%.1fs hits=%d misses=%d"%(time.time()-t0,cpu()-c0,FORECASTS.hits,FORECASTS.misses))
