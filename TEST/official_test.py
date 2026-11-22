#!/usr/bin/env python3
"""TEST ONLY. Does the official Black Desert web market answer requests from this machine (a GitHub runner),
and how often, compared with api.arsha.io? Writes results/<utc time>.json. Not used by the app.
Official site: POST https://eu-trade.naeu.playblackdesert.com/Trademarket/GetWorldMarketSearchList  body {"searchResult":"id,id"}  header User-Agent: BlackDesert"""
import json, time, sys, os, urllib.request, urllib.error, datetime
OFFICIAL = "https://eu-trade.naeu.playblackdesert.com/Trademarket/GetWorldMarketSearchList"
ARSHA = "https://api.arsha.io/v2/eu/GetWorldMarketSubList?lang=en&id="
ids = json.load(open("sample-ids.json"))
CHUNK = int(os.environ.get("CHUNK", "50")); ROUNDS = int(os.environ.get("ROUNDS", "5")); GAP = int(os.environ.get("GAP", "60"))

def official(chunk):
    body = json.dumps({"searchResult": ",".join(map(str, chunk))}).encode()
    req = urllib.request.Request(OFFICIAL, data=body, headers={"Content-Type": "application/json", "User-Agent": "BlackDesert"})
    return urllib.request.urlopen(req, timeout=25)

def arsha(chunk):
    return urllib.request.urlopen(urllib.request.Request(ARSHA + ",".join(map(str, chunk)), headers={"User-Agent": "garmoth-price-feed"}), timeout=25)

def attempt(fn, chunk):
    t = time.time(); r = {"n": len(chunk)}
    try:
        with fn(chunk) as resp:
            raw = resp.read().decode("utf-8", "replace"); r["http"] = resp.status
    except urllib.error.HTTPError as e:
        r["http"] = e.code; raw = e.read().decode("utf-8", "replace")
    except Exception as e:
        r["http"] = None; r["error"] = type(e).__name__ + ": " + str(e)[:150]; raw = ""
    r["secs"] = round(time.time() - t, 2); r["bytes"] = len(raw); r["head"] = raw[:300]
    r["blocked_hint"] = any(k in raw.lower() for k in ("imperva", "incapsula", "incident id", "_incap_"))
    r["ok"] = r.get("http") == 200 and not r["blocked_hint"] and len(raw) > 20
    return r

out = {"started": datetime.datetime.utcnow().isoformat() + "Z", "sample": len(ids), "chunk": CHUNK, "rounds": []}
chunks = [ids[i:i + CHUNK] for i in range(0, len(ids), CHUNK)]
for rd in range(ROUNDS):
    row = {"round": rd, "official": [attempt(official, c) for c in chunks], "arsha": [attempt(arsha, c) for c in chunks]}
    for k in ("official", "arsha"):
        print("round %d %-8s ok %d/%d  http %s" % (rd, k, sum(x["ok"] for x in row[k]), len(row[k]), [x["http"] for x in row[k]]), flush=True)
    out["rounds"].append(row)
    if rd < ROUNDS - 1: time.sleep(GAP)
for k in ("official", "arsha"):
    a = [x for r in out["rounds"] for x in r[k]]
    out["summary_" + k] = {"requests": len(a), "ok": sum(x["ok"] for x in a), "blocked_hint": sum(x["blocked_hint"] for x in a)}
print(json.dumps({k: v for k, v in out.items() if k.startswith("summary")}))
print("first official answer (head):", out["rounds"][0]["official"][0]["head"])
os.makedirs("results", exist_ok=True)
json.dump(out, open("results/%s.json" % out["started"][:19].replace(":", ""), "w"), indent=1)
