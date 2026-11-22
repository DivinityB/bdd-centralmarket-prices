#!/usr/bin/env python3
"""Price feed: asks the official Black Desert web market for the central market price of every item in ids.json (+ ids-extra.json) and writes prices-<region>.json.
Runs every 5 minutes on GitHub Actions (see .github/workflows/update.yml); the app only reads the written file.
  python3 fetch_prices.py [out_dir]          env: REGIONS=eu (comma list: eu, na), SLICE=50, DEADLINE_S=360
The official site limits requests (about 100 a minute from one address, then it answers with a block page), so each run is gentle: one request at a time, a pause between requests.
 1. GetWorldMarketSearchList (50 ids per request): base price of every item, every run.  POST https://<region>-trade.naeu.playblackdesert.com/Trademarket/GetWorldMarketSearchList  {"searchResult":"id,id,..."}  -> "id-stock-basePrice-totalTrades|..."  (ids the market does not know are missing)
 2. GetWorldMarketSubList (one item per request): last sale price + allowed price range. Only SLICE items per run, the ones not refreshed for the longest time (a full round takes about 47 runs). POST .../GetWorldMarketSubList {"keyType":0,"mainKey":id} -> "id-minEnh-maxEnh-basePrice-stock-totalTrades-capMin-capMax-lastSoldPrice-lastSoldTime|..."
Header on every request: User-Agent: BlackDesert.
Output per region (unchanged format, the app reads it): {"t": unix time, "region": "eu", "p": {"<item id>": [cheapest listing (base price), last sale price]}, "n": [ids the market does not know], "z": counts, "zv": 2, "stale": [ids not fetched this time]}
An id that could not be fetched keeps its previous value (from the old file in out_dir). Extra file limits-<region>.json (the app does not use it): {"p": {"<id>": [lowest allowed price, highest allowed price, stock, total trades]}, "ts": {"<id>": unix time of the last SubList}}."""
import json, os, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
HOSTS = {"eu": "https://eu-trade.naeu.playblackdesert.com", "na": "https://na-trade.naeu.playblackdesert.com"}
SLICE = int(os.environ.get("SLICE", 50))
DEADLINE = time.time() + float(os.environ.get("DEADLINE_S", 360))
GAP_BATCH, GAP_ONE = 0.6, 0.8             # seconds between requests
class Blocked(Exception): pass

def call(region, endpoint, body, tries=3):
    last = None
    for i in range(tries):
        if time.time() > DEADLINE: break
        try:
            req = urllib.request.Request(HOSTS[region] + "/Trademarket/" + endpoint, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "User-Agent": "BlackDesert"})
            with urllib.request.urlopen(req, timeout=20) as r: raw = r.read().decode("utf-8", "replace")
            if not raw.startswith("{"): raise Blocked("block page, not json")          # Imperva answers HTTP 200 with a html page when the limit is hit
            j = json.loads(raw)
            if j.get("resultCode") != 0 or not isinstance(j.get("resultMsg"), str): raise ValueError("resultCode %s" % j.get("resultCode"))
            return j["resultMsg"]
        except Exception as e:
            last = e; print("  request failed (%s): %s" % (type(e).__name__, str(e)[:100]), flush=True)
            time.sleep(20 if isinstance(e, Blocked) else 2 * (i + 1))                 # after a block wait for the limit to reset
    raise last

def parse_search(msg):
    out = {}
    for e in msg.split("|"):
        f = e.split("-")
        if len(f) >= 4 and f[0].isdigit(): out[int(f[0])] = [int(x) for x in f[1:4]]       # stock, base price, total trades
    return out

def parse_sub(msg, item_id):
    best = None
    for e in msg.split("|"):
        f = e.split("-")
        if len(f) < 10 or not f[0].isdigit() or int(f[0]) != item_id: continue
        if best is None or int(f[1]) < best[0]: best = (int(f[1]), [int(x) for x in f[3:10]])       # lowest enchant group = the base item
    return best[1] if best else None            # base, stock, trades, capMin, capMax, lastSold, lastSoldTime

def run(region, ids, out_dir):
    path = os.path.join(out_dir, "prices-%s.json" % region)
    lpath = os.path.join(out_dir, "limits-%s.json" % region)
    old, lim = {}, {}
    try: old = json.load(open(path))
    except Exception: pass
    try: lim = json.load(open(lpath))
    except Exception: pass
    op = old.get("p") or {}
    limp, ts = dict(lim.get("p") or {}), dict(lim.get("ts") or {})
    base, stale, zero = {}, [], set()
    blocked = 0
    for k in range(0, len(ids), 50):                              # step 1: base prices
        chunk = ids[k:k + 50]
        try: got = parse_search(call(region, "GetWorldMarketSearchList", {"searchResult": ",".join(map(str, chunk))}))
        except Exception as e:
            stale.extend(chunk); blocked += isinstance(e, Blocked)
            if blocked >= 2: stale.extend(ids[k + 50:]); break      # blocked twice: stop asking, keep old values
            continue
        for i in chunk:
            if i in got and got[i][1] > 0: base[i] = got[i][1]
            else: zero.add(i)                                     # missing or no price: only 'not on the market' after 3 passes in a row
        time.sleep(GAP_BATCH)
    last = {}                                                     # step 2: last sale price for the items not refreshed for the longest time
    todo = sorted((i for i in ids if i not in zero and i not in stale), key=lambda i: (ts.get(str(i), 0), i))[:SLICE]
    nblock = 0
    for i in todo:
        if time.time() > DEADLINE: break
        try: v = parse_sub(call(region, "GetWorldMarketSubList", {"keyType": 0, "mainKey": i}, tries=2), i)
        except Exception as e:
            nblock += isinstance(e, Blocked)
            if nblock >= 2: break
            continue
        if v:
            last[i] = v[5]; ts[str(i)] = int(time.time())
            if v[3] or v[4]: limp[str(i)] = [v[3], v[4], v[1], v[2]]
            if v[0] > 0: base[i] = v[0]
        time.sleep(GAP_ONE)
    p = {}
    for i in ids:
        if i in base:
            b = base[i]; l = last.get(i) or (op.get(str(i)) or [0, 0])[1] or b
            p[str(i)] = [int(b), int(l)]
    for i in stale:                                   # keep the last known value
        if str(i) in op and str(i) not in p: p[str(i)] = op[str(i)]
    oz = (old.get("z") or {}) if old.get("zv") == 2 else {}
    z, n = {}, set()
    for i in zero:
        z[str(i)] = int(oz.get(str(i), 0)) + 1
        if str(i) in op and z[str(i)] < 3: p[str(i)] = op[str(i)]       # keep the old price while the empty answer is not confirmed
        elif z[str(i)] >= 3: n.add(i)
    for i in stale:                                   # not fetched this pass: keep the count
        if str(i) in oz and int(oz[str(i)]) >= 3 and str(i) not in p: n.add(i); z[str(i)] = int(oz[str(i)])
    t = int(time.time())
    res = {"t": t, "region": region, "p": p, "n": sorted(n), "z": z, "zv": 2, "stale": sorted(i for i in stale if str(i) not in p and i not in n)}
    os.makedirs(out_dir, exist_ok=True)
    json.dump(res, open(path, "w"), separators=(",", ":"))
    json.dump({"t": t, "region": region, "fields": "p: id -> [lowest allowed price, highest allowed price, stock, total trades]; ts: id -> unix time of the last per-item request", "p": limp, "ts": ts}, open(lpath, "w"), separators=(",", ":"))
    print("%s: %d prices, %d not on the market, %d could not be fetched (%d kept from before), last sale refreshed for %d items" % (region, len(p), len(n), len(stale), sum(1 for i in stale if str(i) in p), len(last)))
    return res

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")
    ids = json.load(open(os.path.join(HERE, "ids.json")))
    try: ids = sorted(set(ids) | set(json.load(open(os.path.join(HERE, "ids-extra.json")))))      # extra ids that must stay when ids.json is regenerated
    except FileNotFoundError: pass
    for region in os.environ.get("REGIONS", "eu").split(","):
        res = run(region.strip(), sorted(ids), out)
        if not res["p"]: sys.exit("no prices at all for " + region)
