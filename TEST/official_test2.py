#!/usr/bin/env python3
"""TEST ONLY (not used by the app). Bigger run: asks the official market site for ALL ids in ids.json + ids-extra.json
(chunks of 50, one request at a time, 0.5 s apart), several rounds, parses every answer, counts missing ids,
and keeps one arsha request per round for comparison. Writes TEST/results/full-<time>.json and prices-official-sample.json (last round, all parsed)."""
import json, time, os, urllib.request, urllib.error, datetime
OFFICIAL = "https://eu-trade.naeu.playblackdesert.com/Trademarket/GetWorldMarketSearchList"
ARSHA = "https://api.arsha.io/v2/eu/GetWorldMarketSubList?lang=en&id="
def load(p):
    d = json.load(open(p)); return list(d) if not isinstance(d, dict) else [int(k) for k in d]
ids = sorted(set(load("../ids.json")) | set(load("../ids-extra.json")))
CHUNK = 50; ROUNDS = int(os.environ.get("ROUNDS", "6")); GAP = int(os.environ.get("GAP", "20"))
def post(chunk):
    body = json.dumps({"searchResult": ",".join(map(str, chunk))}).encode()
    req = urllib.request.Request(OFFICIAL, data=body, headers={"Content-Type": "application/json", "User-Agent": "BlackDesert"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=25) as r: code, raw = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e: code, raw = e.code, e.read().decode("utf-8", "replace")
    except Exception as e: code, raw = None, "ERR " + str(e)[:100]
    return code, raw, round(time.time() - t, 2)
def parse(raw):
    try: m = json.loads(raw)["resultMsg"]
    except Exception: return None
    out = {}
    for e in m.split("|"):
        p = e.split("-")
        if len(p) >= 4 and p[0].isdigit(): out[int(p[0])] = [int(x) for x in p[1:4]]
    return out
res = {"started": datetime.datetime.utcnow().isoformat() + "Z", "ids": len(ids), "rounds": []}
last = {}
for rd in range(ROUNDS):
    got = {}; codes = {}; times = []; bad = []
    for k in range(0, len(ids), CHUNK):
        c = ids[k:k + CHUNK]; code, raw, secs = post(c)
        codes[str(code)] = codes.get(str(code), 0) + 1; times.append(secs)
        pr = parse(raw) if code == 200 else None
        if pr is None: bad.append({"first_id": c[0], "code": code, "head": raw[:200]})
        else: got.update(pr)
        time.sleep(0.5)
    try:
        with urllib.request.urlopen(urllib.request.Request(ARSHA + "4901,8198", headers={"User-Agent": "garmoth-price-feed"}), timeout=25) as r: ac = r.status
    except urllib.error.HTTPError as e: ac = e.code
    except Exception as e: ac = str(e)[:60]
    missing = [i for i in ids if i not in got]
    row = {"round": rd, "requests": sum(codes.values()), "codes": codes, "max_secs": max(times), "avg_secs": round(sum(times) / len(times), 2),
           "ids_returned": len(got), "ids_missing": len(missing), "missing_sample": missing[:30], "zero_stock": sum(1 for v in got.values() if v[0] == 0), "bad": bad[:5], "arsha_single_batch_http": ac}
    print(json.dumps(row), flush=True); res["rounds"].append(row); last = got
    if rd < ROUNDS - 1: time.sleep(GAP)
os.makedirs("results", exist_ok=True)
json.dump(res, open("results/full-%s.json" % res["started"][:19].replace(":", ""), "w"), indent=1)
json.dump({"t": int(time.time()), "fields": "id: [stock, basePrice, totalTrades]", "items": {str(k): v for k, v in last.items()}}, open("results/prices-official-sample.json", "w"))
