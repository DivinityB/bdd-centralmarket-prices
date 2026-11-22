#!/usr/bin/env python3
"""TEST ONLY: find how fast single-item requests to the official market can go. Sequential, fixed delay, logs the first failures in detail."""
import json, time, urllib.request, urllib.error
ids = sorted(set(json.load(open("../ids.json"))))[:400]
URL = "https://eu-trade.naeu.playblackdesert.com/Trademarket/GetWorldMarketSubList"
def one(i):
    req = urllib.request.Request(URL, data=json.dumps({"keyType": 0, "mainKey": i}).encode(), headers={"Content-Type": "application/json", "User-Agent": "BlackDesert"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r: return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e: return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)
    except Exception as e: return None, str(e), {}
res = []
for delay in (0.5, 0.25, 0.1):
    ok = bad = 0; first = None; t = time.time(); w = 0
    for i in ids[:150]:
        c, b, h = one(i)
        good = c == 200 and b.startswith("{")
        ok += good; bad += not good
        if not good and first is None: first = {"after": ok, "code": c, "body": b[:200], "headers": {k: v for k, v in h.items() if k.lower() in ("retry-after", "x-cdn", "server", "content-type", "x-iinfo", "set-cookie", "content-length")}}
        time.sleep(delay)
    r = {"delay": delay, "ok": ok, "bad": bad, "secs": round(time.time() - t), "first_failure": first}; print(json.dumps(r), flush=True); res.append(r)
    time.sleep(60)                         # let any limit reset between the three tries
json.dump(res, open("results/ratetest.json", "w"), indent=1)
