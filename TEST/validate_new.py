#!/usr/bin/env python3
"""TEST ONLY: runs the new fetch_prices.py on a COPY of the live feed file (nothing is published) and compares."""
import json, os, sys, time, urllib.request
sys.path.insert(0, "."); import fetch_new as F
live = json.load(urllib.request.urlopen("https://raw.githubusercontent.com/DivinityB/bdd-centralmarket-prices/data/prices-eu.json"))
os.makedirs("results/validate-out", exist_ok=True); json.dump(live, open("results/validate-out/prices-eu.json", "w"))
ids = json.load(open("../ids.json")); ids = sorted(set(ids) | set(json.load(open("../ids-extra.json"))))
t = time.time(); new = F.run("eu", ids, "results/validate-out"); secs = round(time.time() - t)
same = diff = 0
for k, v in new["p"].items():
    o = live["p"].get(k)
    if o == v: same += 1
    else: diff += 1
print(json.dumps({"seconds": secs, "ids": len(ids), "keys_old": sorted(live), "keys_new": sorted(new), "prices_new": len(new["p"]), "prices_old": len(live["p"]), "same_as_live": same, "differ": diff,
                  "n_new": len(new["n"]), "n_old": len(live["n"]), "stale_new": len(new["stale"]), "only_in_old": len(set(live["p"]) - set(new["p"])), "only_in_new": len(set(new["p"]) - set(live["p"])),
                  "z_new_sample": dict(list(new["z"].items())[:3]), "limits": len(json.load(open("results/validate-out/limits-eu.json"))["p"])}))
