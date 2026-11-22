#!/usr/bin/env python3
"""Price feed: asks the official Black Desert web market for the central market price of every item in ids.json (+ ids-extra.json) and writes prices-<region>.json.
Runs every 5 minutes on GitHub Actions (see .github/workflows/update.yml); the app only reads the written file.
  python3 fetch_prices.py [out_dir]          env: REGIONS=eu (comma list: eu, na), WORKERS=4, DEADLINE_S=360
Official site: POST https://<region>-trade.naeu.playblackdesert.com/Trademarket/GetWorldMarketSubList  body {"keyType":0,"mainKey":<item id>}  header User-Agent: BlackDesert
Answer: {"resultCode":0,"resultMsg":"id-minEnh-maxEnh-basePrice-stock-totalTrades-hardCapMin-hardCapMax-lastSoldPrice-lastSoldTime|..."} (one entry per enchant level group; "0" = item not on the market).
Output per region (unchanged format, the app reads it): {"t": unix time of this update, "region": "eu", "p": {"<item id>": [cheapest listing (base price), last sale price]}, "n": [ids the market does not know], "z": counts, "zv": 2, "stale": [ids not fetched this time]}
An id that could not be fetched this time keeps its previous value (from the old file in out_dir); "stale" lists those ids.
Also writes limits-<region>.json: {"p": {"<item id>": [lowest allowed price, highest allowed price, stock, total trades]}} for the base enchant level (extra file, the app does not use it)."""
import json, os, sys, time, urllib.request, urllib.error, threading
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
HOSTS = {"eu": "https://eu-trade.naeu.playblackdesert.com", "na": "https://na-trade.naeu.playblackdesert.com"}
WORKERS = int(os.environ.get("WORKERS", 4))
DEADLINE = time.time() + float(os.environ.get("DEADLINE_S", 360))          # give up on slow requests after 6 minutes; ids not fetched keep their old price

def sublist(region, item_id, tries=4):
    """returns [base, last sold, stock, trades, capMin, capMax] of the base enchant level of one item, or None if the market does not know the item. Raises when it cannot be fetched."""
    req_body = json.dumps({"keyType": 0, "mainKey": int(item_id)}).encode()
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(HOSTS[region] + "/Trademarket/GetWorldMarketSubList", data=req_body, headers={"Content-Type": "application/json", "User-Agent": "BlackDesert"})
            with urllib.request.urlopen(req, timeout=20) as r:
                j = json.loads(r.read().decode("utf-8"))
            msg = j.get("resultMsg")
            if j.get("resultCode") != 0 or not isinstance(msg, str): raise ValueError("resultCode %s" % j.get("resultCode"))
            best = None
            for e in msg.split("|"):
                f = e.split("-")
                if len(f) < 10 or not f[0].isdigit() or int(f[0]) != int(item_id): continue
                if best is None or int(f[1]) < best[0]: best = (int(f[1]), [int(x) for x in f[3:10]])       # lowest enchant group = the base item
            if best is None: return None
            v = best[1]                                                # basePrice, stock, trades, capMin, capMax, lastSoldPrice, lastSoldTime
            return [v[0], v[5], v[1], v[2], v[3], v[4]]
        except Exception as e:
            last = e
            print("  request failed (%s): %s" % (type(e).__name__, str(e)[:120]), flush=True)
            if time.time() > DEADLINE: break
            time.sleep(1.5 * (i + 1))
    raise last

def price(e):
    base, last = float(e[0] or 0), float(e[1] or 0)
    if base <= 0 and last <= 0: return None
    return [int(base if base > 0 else last), int(last if last > 0 else base)]

def run(region, ids, out_dir):
    path = os.path.join(out_dir, "prices-%s.json" % region)
    old = {}
    try: old = json.load(open(path))
    except Exception: pass
    p, n, stale, zero, limits = {}, set(), [], set(), {}
    lock = threading.Lock()
    def one(i):
        if time.time() > DEADLINE:
            with lock: stale.append(i)
            return
        try: e = sublist(region, i)
        except Exception:
            with lock: stale.append(i)
            return
        pr = price(e) if e else None
        with lock:
            if pr:
                p[str(i)] = pr
                if e[5] > 0: limits[str(i)] = [e[4], e[5], e[2], e[3]]
            else: zero.add(i)          # no price in the answer: only counts as 'not on the market' after 3 passes in a row
    ids = sorted(ids, key=lambda i: (str(i) in (old.get("p") or {}), i in (old.get("n") or [])))   # items without a price yet go first
    with ThreadPoolExecutor(WORKERS) as ex: list(ex.map(one, ids))
    for i in stale:                                   # keep the last known value
        if str(i) in (old.get("p") or {}): p[str(i)] = old["p"][str(i)]
    oz = (old.get("z") or {}) if old.get("zv") == 2 else {}      # counts from older versions of this script are not trusted
    z = {}
    for i in zero:
        z[str(i)] = int(oz.get(str(i), 0)) + 1
        if str(i) in (old.get("p") or {}) and z[str(i)] < 3: p[str(i)] = old["p"][str(i)]   # keep the old price while the empty answer is not confirmed
        elif z[str(i)] >= 3: n.add(i)
    for i in stale:                                   # not fetched this pass: keep the count
        if str(i) in oz and int(oz[str(i)]) >= 3 and str(i) not in p: n.add(i); z[str(i)] = int(oz[str(i)])
    t = int(time.time())
    res = {"t": t, "region": region, "p": p, "n": sorted(n), "z": z, "zv": 2, "stale": sorted(i for i in stale if str(i) not in p and i not in n)}
    os.makedirs(out_dir, exist_ok=True)
    json.dump(res, open(path, "w"), separators=(",", ":"))
    json.dump({"t": t, "region": region, "fields": "id: [lowest allowed price, highest allowed price, stock, total trades]", "p": limits}, open(os.path.join(out_dir, "limits-%s.json" % region), "w"), separators=(",", ":"))
    print("%s: %d prices, %d not on the market, %d could not be fetched (%d kept from before)" % (region, len(p), len(n), len(stale), sum(1 for i in stale if str(i) in p)))
    return res

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")
    ids = json.load(open(os.path.join(HERE, "ids.json")))
    try: ids = sorted(set(ids) | set(json.load(open(os.path.join(HERE, "ids-extra.json")))))      # extra ids that must stay when ids.json is regenerated
    except FileNotFoundError: pass
    for region in os.environ.get("REGIONS", "eu").split(","):
        res = run(region.strip(), ids, out)
        if not res["p"]: sys.exit("no prices at all for " + region)
