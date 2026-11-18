#!/usr/bin/env python3
"""Garmoth price feed: asks api.arsha.io for the central market price of every item in ids.json and writes prices-<region>.json.
Runs every 5 minutes on GitHub Actions (see .github/workflows/update.yml); the Garmoth app only reads the written file.
  python3 fetch_prices.py [out_dir]          env: REGIONS=eu (comma list), ARSHA_BASE=https://api.arsha.io
Output per region: {"t": unix time of this update, "region": "eu", "p": {"<item id>": [cheapest listing, last sale price]}, "n": [ids the market does not know]}
An id that could not be fetched this time keeps its previous value (from the old file in out_dir); "stale" lists those ids."""
import json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("ARSHA_BASE", "https://api.arsha.io").rstrip("/")
BATCH = 50
DEADLINE = time.time() + 6 * 60          # give up on slow requests after 6 minutes; ids not fetched keep their old price

def get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "garmoth-price-feed"}), timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404): raise
            last = e
        except Exception as e:
            last = e
        print("  request failed (%s): %s" % (type(last).__name__, str(last)[:120]), flush=True)
        if time.time() > DEADLINE: break
        time.sleep(1.5 * (i + 1))
    raise last

def entries(j):
    return j if isinstance(j, list) else (j.get("data") if isinstance(j, dict) and isinstance(j.get("data"), list) else ([j] if isinstance(j, dict) else []))

def eid(x):
    for k in ("id", "mainKey", "itemId"):
        if isinstance(x, dict) and x.get(k) is not None: return int(x[k])

def price(e):
    base, last = float(e.get("basePrice") or 0), float(e.get("lastSoldPrice") or 0)
    if base <= 0 and last <= 0: return None
    return [int(base if base > 0 else last), int(last if last > 0 else base)]

def run(region, ids, out_dir):
    path = os.path.join(out_dir, "prices-%s.json" % region)
    old = {}
    try: old = json.load(open(path))
    except Exception: pass
    p, n, stale = {}, set(), []
    def _unused(i):
        try:
            arr = entries(get("%s/v2/%s/GetWorldMarketSubList?id=%d&lang=en" % (BASE, region, i)))
            best = None
            for x in arr:
                if isinstance(x, dict) and (x.get("sid") in (None, 0) or x.get("minEnhance") == 0) and (eid(x) in (None, i)): best = best or x
            if best is None and arr and isinstance(arr[0], dict): best = arr[0]
            pr = price(best) if best else None
            if pr: p[str(i)] = pr
            else: n.add(i)
        except urllib.error.HTTPError as e:
            if e.code in (400, 404): n.add(i)
            else: stale.append(i)
        except Exception: stale.append(i)
    lock = threading.Lock()
    def setp(i, pr):
        with lock:
            if pr: p[str(i)] = pr
            else: n.add(i)
    def fetch(chunk, tries):
        """one request for the chunk; a server error (arsha.io is often 'blocked by Imperva' for part of a request) splits the chunk in halves, down to single ids"""
        if time.time() > DEADLINE:
            with lock: stale.extend(chunk)
            return
        try:
            arr = entries(get("%s/v2/%s/GetWorldMarketSubList?id=%s&lang=en" % (BASE, region, ",".join(map(str, chunk))), tries=tries))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404) and len(chunk) == 1: setp(chunk[0], None); return
            if len(chunk) > 1:
                m = len(chunk) // 2; fetch(chunk[:m], 1); fetch(chunk[m:], 1); return
            with lock: stale.append(chunk[0])
            return
        except Exception:
            if len(chunk) > 1:
                m = len(chunk) // 2; fetch(chunk[:m], 1); fetch(chunk[m:], 1); return
            with lock: stale.append(chunk[0])
            return
        got = {}
        for x in arr:
            i = eid(x)
            if i is None: continue
            if i not in got or (x.get("sid") in (None, 0) or x.get("minEnhance") == 0): got[i] = x
        for i in chunk:
            setp(i, price(got[i]) if i in got else None)
    chunks = [list(ids)[k:k + 10] for k in range(0, len(ids), 10)]
    with ThreadPoolExecutor(4) as ex: list(ex.map(lambda c: fetch(c, 2), chunks))
    for i in stale:                                   # keep the last known value
        if str(i) in (old.get("p") or {}): p[str(i)] = old["p"][str(i)]
        elif i in (old.get("n") or []): n.add(i)
    t = int(time.time())
    res = {"t": t, "region": region, "p": p, "n": sorted(n), "stale": sorted(i for i in stale if str(i) not in p and i not in n)}
    os.makedirs(out_dir, exist_ok=True)
    json.dump(res, open(path, "w"), separators=(",", ":"))
    print("%s: %d prices, %d not on the market, %d could not be fetched (%d kept from before)" % (region, len(p), len(n), len(stale), sum(1 for i in stale if str(i) in p)))
    return res

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")
    ids = json.load(open(os.path.join(HERE, "ids.json")))
    for region in os.environ.get("REGIONS", "eu").split(","):
        res = run(region.strip(), ids, out)
        if not res["p"]: sys.exit("no prices at all for " + region)
