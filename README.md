# Price feed (central market)

Keeps a ready-made file of central market prices so the app never has to wait for the market.

- `fetch_prices.py` asks the **official Black Desert web market** (eu-trade.naeu.playblackdesert.com) for every item in `ids.json` + `ids-extra.json` and writes `prices-eu.json`. Details of the requests are in the header of the script. It is gentle on purpose: the site blocks an address after about 100 requests a minute, so a run is one request at a time with pauses (about 90 seconds). Per run: base price of all items (one request per 50 items), plus the last sale price of the 50 items not refreshed for the longest time (a full round takes about 47 runs, roughly 4 hours; in between an item keeps its last known sale price).
- `.github/workflows/update.yml` runs it every 5 minutes on GitHub Actions and publishes the files to the `data` branch (one commit, no history). The previous files are fetched first, so a request that fails keeps the old value.
- The app reads `https://raw.githubusercontent.com/DivinityB/bdd-centralmarket-prices/data/prices-<region>.json` every ~5 minutes (`lsprices.js`, constant `FEED`). Format (unchanged): `{"t","region","p":{id:[cheapest listing, last sale price]},"n":[ids the market does not know],"z","zv":2,"stale"}`.
- `limits-eu.json` (same branch, extra, the app does not use it): per item the lowest and highest price a listing may have, stock and total trades, plus `ts` (when each item's last sale price was refreshed).
- Only market prices are in the repo (no personal data), so it can be a public repo: GitHub Actions is free and unlimited there.
- `ids.json` = every item of the Crafting data that is sold on the central market (regenerate it after `build_crafting.py`).
- To add a region, add it to `REGIONS` in the workflow (comma list). The script knows `eu` and `na`; only `eu` has been tested.
- `ids-extra.json` = more ids that are always fetched in addition to `ids.json`: the items that farming nodes give (worker yields in the Better Black Desert app, 94 ids added 2026-11-20). Items that are not sold on the market end up in `n` after 3 empty answers; that is expected. This file is NOT overwritten when `ids.json` is regenerated.
- History: until 2026-11-22 the prices came from api.arsha.io, a cache in front of the same market that was blocked by the market's bot filter most of the time; it was replaced because the official site answered every request in the tests (see bdd-database GAPS G-44, G-45).
