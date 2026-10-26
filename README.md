# STOOPIDS — NCAA Stoopids Pool 2026-27

Static app (`index.html` + `data.js`) and a stdlib-only Python refresh script. No API keys, no pip installs.

## Run it
    python3 serve.py            # http://localhost:8765  (refreshes now and every 10 min; GET /refresh forces one)
    python3 refresh.py          # one-off refresh (rewrites data.js / data.json)
    python3 refresh.py --demo   # rebuild the demo (last season replay, open index.html?demo=1)
    python3 test_score.py       # tests (scoring rules, games view, odds parsing + record check vs ESPN's 365 team records)
    python3 test_bets.py        # tests for the side-bets ledger and sheet parser
    python3 crosscheck.py 2026-03-05 2026-03-22   # ESPN vs ncaa.com score comparison

`index.html` also works opened straight from disk (file://) — it just shows whatever data.js was last built.

## Tabs
Standings · **Games** (recent results + upcoming games for rostered teams, WIB tip-offs, Vegas line, favorite/underdog, owners per side, pool-vs-pool highlighted, upset badge) · Rosters · **Side bets** (who-owes-who matrix, per-person totals, wager list, new-bet builder) · All teams · Bonus checklist · Upsets · Jan 20 redraft · Rules & sources.

## Side bets
- `bets.json` = live ledger: `people` (ids + aliases + optional `pool_owner`), `currency` (IDR, shown in K), `fines`, `bets`. Shorthand amounts: 100K, 1.5mil, 2juta, 250,000. Bet types: `versus` (one-vs-many, odds like 2:1 with a longshot side, per-game series, non-cash `stake_item`), `pool` (buy-in + payouts incl. runner-up money back).
- New bet: Side bets tab -> "New bet" -> Build. With `python3 serve.py` (localhost only, or `--edit-token`) the Save/Settle buttons write bets.json; on a static host copy the JSON into bets.json.
- `python3 bets.py import-sheet` re-parses the sheet's "NEW BETS 25-26" tab into `bets_imported.json` (best effort; unparsed rows are flagged and excluded from the totals). Only the bet number, wager and outcome columns are read - never the payment-detail columns.
- `python3 test_bets.py` tests it.

## Files you edit
- `config.json` — points, rule toggles (upset scope/basis, First Four rules…), owners, **redraft date + each owner's 2 drops / 2 adds**, team-name aliases.
- `overrides.json` — manual corrections: force/deny a bonus per team (`flags`), force/deny a specific upset (`upset_events`), commissioner `adjustments`.
Rosters come live from the Google Sheet; before the redraft date a copy is saved to `roster_snapshot.json` so the pre-redraft rosters survive the sheet being edited.

## Sources (free, no key)
ESPN scoreboard/standings/odds/teams JSON (primary); ncaa.com data via https://ncaa-api.henrygd.me (fallback, scores+seeds only).

## Optional hosting
`.github/workflows/refresh.yml` is a ready recipe for GitHub Pages + scheduled refresh (requires a GitHub repo — not set up).
