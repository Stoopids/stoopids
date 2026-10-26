# STOOPIDS — NCAA Stoopids Pool 2026-27

Static app (`index.html` + `data.js`) and a stdlib-only Python refresh script. No API keys, no pip installs.

## Run it
    python3 serve.py            # http://localhost:8765  (refreshes now and every 10 min; GET /refresh forces one)
    python3 refresh.py          # one-off refresh (rewrites data.js / data.json)
    python3 refresh.py --demo   # rebuild the demo (last season replay, open index.html?demo=1)
    python3 test_score.py       # tests (scoring rules, games view, odds parsing + record check vs ESPN's 365 team records)
    python3 test_bets.py        # tests for the side-bets ledger and sheet parser
    python3 test_shared.py      # shared ledger: JS tally/merge in index.html == Python (needs node), merge, validation, backup
    NODE_PATH=<dir with jsdom> node test_ui_jsdom.js   # optional UI test of index.html (npm i jsdom), fake store, no network
    python3 crosscheck.py 2026-03-05 2026-03-22   # ESPN vs ncaa.com score comparison

`index.html` also works opened straight from disk (file://) — it just shows whatever data.js was last built.

## Tabs
Standings · **Games** (recent results + upcoming games for rostered teams, WIB tip-offs, Vegas line, favorite/underdog, owners per side, pool-vs-pool highlighted, upset badge; NCAA tournament upsets are judged by seed, lower seed beating a better seed) · Rosters · **Side bets** (who-owes-who matrix, per-person totals, wager list, new-bet builder) · All teams · Bonus checklist · Upsets · Jan 20 redraft · Rules & sources.

## Side bets
- `bets.json` = live ledger: `people` (ids + aliases + optional `pool_owner`), `currency` (IDR, shown in K), `fines`, `bets`. Shorthand amounts: 100K, 1.5mil, 2juta, 250,000. Bet types: `versus` (one-vs-many, odds like 2:1 with a longshot side, per-game series, non-cash `stake_item`), `pool` (buy-in + payouts incl. runner-up money back).
- New bet: Side bets tab -> "New bet" -> Build, then **Save to shared ledger** (hosted site) or **Save to ledger** (`python3 serve.py`, localhost only or `--edit-token`: writes bets.json, unchanged). With no shared ledger / in demo mode it only shows the JSON to paste into bets.json.

## Shared ledger (hosted site: anyone with the link can add and settle bets)
GitHub Pages has no server, so new and settled side bets live in one small **anonymous JSON document** on a free no-signup store (currently textdb.dev; URL in `config.json` -> `shared_bets.url`). No account, no secrets, nothing sensitive in the repo.
- The page loads `{"bets":[...]}` from it (and re-checks every 45 s), merges it with the `bets.json` ledger bets and the 2025-26 import, and **recomputes the tally in the browser** (`index.html`, block `SHARED-BETS-CORE`, a port of `bets.py`; `test_shared.py` proves it matches the Python output).
- Saving = re-fetch the document, apply the change to that fresh copy (bets are matched by `id`/number), write the whole document back, read it back to verify (retries up to 3x). If a concurrent writer still overwrites your save, your page re-applies it on its next poll. New bets get the next free number.
- If the store is unreachable the Side bets tab becomes **read-only** with a clear message (it shows the last snapshot from the repo, `bets_shared_backup.json`, when it never managed to load). Demo mode (`?demo=1`) never touches the shared ledger. `serve.py` local mode is unchanged and ignores the shared ledger.
- **Export JSON backup** button (Side bets tab) downloads the current shared bets. `refresh.py` (so the 15-min Action) also fetches the document and writes `bets_shared_backup.json` (fail-soft: offline = file left as is; only recognised bet fields are copied; commits only when it changed), so git history is the backup. To restore: `curl -X POST -H 'Content-Type: text/plain' --data-binary @doc.json <shared_bets.url>` with a document like `{"schema":1,"bets":[...from the backup...]}`. `python3 bets.py tally --shared bets_shared_backup.json` prints the tally including shared bets.
- **Limitation (friends-pool grade):** no auth. The blob URL is not secret but is public in the repo/config, so anyone who has it can edit or wipe the ledger, last write wins, and the store is a free hobby service (no uptime promise). A backup snapshot exists in the repo (up to ~15 min old). To switch store: create a new document, put its URL (and `kind`: `textdb`, `jsonblob` or `npoint`) in `config.json`. To turn it off: `"enabled": false`.
- Payment details are never stored or read: a shared bet can only contain the same fields as a ledger bet (terms, people ids, stake, winner, ...).
- `python3 bets.py import-sheet` re-parses the sheet's "NEW BETS 25-26" tab into `bets_imported.json` (best effort; unparsed rows are flagged and excluded from the totals). Only the bet number, wager and outcome columns are read - never the payment-detail columns.
- `python3 test_bets.py` tests it.

## Files you edit
- `config.json` — points, rule toggles (upset scope/basis, First Four rules…), owners, **redraft date + each owner's 2 drops / 2 adds**, team-name aliases.
- `overrides.json` — manual corrections: force/deny a bonus per team (`flags`), force/deny a specific upset (`upset_events`), commissioner `adjustments`.
Rosters come live from the Google Sheet; before the redraft date a copy is saved to `roster_snapshot.json` so the pre-redraft rosters survive the sheet being edited.

## Sources (free, no key)
ESPN scoreboard/standings/odds/teams JSON (primary); ncaa.com data via https://ncaa-api.henrygd.me (fallback, scores+seeds only).

## Optional hosting
`.github/workflows/refresh.yml` runs `refresh.py` every 15 min on GitHub Actions and commits `data.js`, `data.json`, `roster_snapshot.json` and `bets_shared_backup.json` (site: GitHub Pages).
