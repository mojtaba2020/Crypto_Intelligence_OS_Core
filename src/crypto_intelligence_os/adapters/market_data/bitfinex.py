"""Bitfinex public hourly BTC/USD adapter normalized to provider-neutral OHLCV."""
from __future__ import annotations
import json, urllib.parse, urllib.request
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe

API="https://api-pub.bitfinex.com/v2/candles/trade:1h:tBTCUSD/hist"
SOURCE_ID="source:bitfinex.public"
INSTRUMENT_ID="market:bitfinex:spot:btc-usd"
HEADERS={"User-Agent":"Crypto-Intelligence-OS/1.0","Accept":"application/json"}

def parse_hourly(payload:list, *, ingested_at:datetime)->tuple[OHLCVBar,...]:
    bars=[]
    for row in payload:
        if len(row)<6: raise ValueError("Malformed Bitfinex candle")
        mts,o,c,h,l,v=row[:6]; opened=datetime.fromtimestamp(int(mts)/1000,UTC)
        bars.append(OHLCVBar(instrument_id=INSTRUMENT_ID,timeframe=Timeframe.ONE_HOUR,status=BarStatus.FINAL,open_time=opened,close_time=opened+timedelta(hours=1),available_at=opened+timedelta(hours=1),ingested_at=ingested_at,open=Decimal(str(o)),high=Decimal(str(h)),low=Decimal(str(l)),close=Decimal(str(c)),volume=Decimal(str(v)),source_id=SOURCE_ID))
    return tuple(sorted(bars,key=lambda b:b.open_time))

def fetch_hourly(*,start:datetime,end:datetime,limit:int=10000)->tuple[OHLCVBar,...]:
    q=urllib.parse.urlencode({"start":int(start.timestamp()*1000),"end":int(end.timestamp()*1000)-1,"limit":min(limit,10000),"sort":1})
    req=urllib.request.Request(API+"?"+q,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=30) as response: payload=json.load(response)  # noqa: S310
    if not isinstance(payload,list): raise ValueError("Unexpected Bitfinex response")
    return parse_hourly(payload,ingested_at=datetime.now(UTC))
