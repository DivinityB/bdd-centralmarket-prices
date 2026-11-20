# Garmoth price feed

Keeps a ready-made file of central market prices so the Garmoth app never has to wait for the market API.

- `fetch_prices.py` asks api.arsha.io for every item in `ids.json` (batches of 50, falls back to single requests, keeps the old value of an item that fails) and writes `prices-eu.json`.
- `.github/workflows/update.yml` runs it every 5 minutes on GitHub Actions and publishes the file to the `data` branch (one commit, no history).
- The app reads `https://raw.githubusercontent.com/DivinityB/bdd-centralmarket-prices/data/prices-<region>.json` every ~5 minutes (`lsprices.js`, constant `FEED`). If the file is missing or older than 30 minutes, the app asks api.arsha.io itself.
- Only market prices are in the repo (no personal data), so it can be a public repo: GitHub Actions is free and unlimited there. In a private repo a run every 5 minutes would use up the free minutes.
- `ids.json` = every item of the Crafting data that is sold on the central market (regenerate it after `build_crafting.py`).
- To add a region, add it to `REGIONS` in the workflow (comma list, e.g. `eu,na`).
- `ids-extra.json` = more ids that are always fetched in addition to `ids.json`: the items that farming nodes give (worker yields in the Better Black Desert app, 94 ids added 2026-11-20). Items that are not sold on the market (NPC-only) end up in `n` after 3 empty answers; that is expected. This file is NOT overwritten when `ids.json` is regenerated from the Crafting data.
