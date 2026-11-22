#!/usr/bin/env python3
"""TEST ONLY: what does the official GetWorldMarketSubList (one item, all enchant levels) answer? Prints raw replies."""
import json, urllib.request, urllib.error, time
H = "https://eu-trade.naeu.playblackdesert.com/Trademarket/"
def post(ep, body):
    req = urllib.request.Request(H + ep, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "User-Agent": "BlackDesert"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r: return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e: return e.code, e.read().decode("utf-8", "replace")
    except Exception as e: return None, str(e)
out = []
for ep, body in [("GetWorldMarketSubList", {"keyType": 0, "mainKey": 4901}),
                 ("GetWorldMarketSubList", {"keyType": 0, "mainKey": 11628}),
                 ("GetWorldMarketSubList", {"keyType": 0, "mainKey": 10210}),
                 ("GetWorldMarketSubList", {"keyType": 0, "mainKey": 595}),
                 ("GetWorldMarketSubList", {"keyType": 0, "mainKey": 2}),
                 ("GetWorldMarketSearchList", {"searchResult": "4901,11628"}),
                 ("GetMarketPriceInfo", {"keyType": 0, "mainKey": 4901, "subKey": 0})]:
    c, raw = post(ep, body); print(ep, body, "->", c, len(raw), flush=True); print(raw[:1500], flush=True); out.append({"ep": ep, "body": body, "code": c, "raw": raw[:6000]}); time.sleep(1)
import os; os.makedirs("results", exist_ok=True); json.dump(out, open("results/probe-sublist.json", "w"), indent=1)
