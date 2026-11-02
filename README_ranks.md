# STOOPIDS rank module

`ranks.py` — `get_ranks(cache_dir, today) -> (ranks, meta)`. Python 3 stdlib only (urllib, json). No secrets.

## Usage
```python
from ranks import get_ranks
ranks, meta = get_ranks("/path/to/cache", datetime.date.today())
ranks["150"]  # {'ap': 2, 'net': 2, 'kenpom': None, 'stoopid': 1}
meta["net"]   # {'source': 'net', 'fetched_at': '2026-11-02T02:40:00Z', 'status': 'fresh'}
```
CLI: `python3 ranks.py ./cache` prints meta. Tests: `python3 -m unittest test_ranks -v` (offline fixtures).

## Cadence
Daily is enough (AP is weekly, NET daily in season). It is safe to call every run: once today's cache file
(`<source>-YYYY-MM-DD.json`) exists, no network call is made.

## Field notes
- `ranks`: keyed by ESPN team id (string), every team in `team_map.json`; each field int or None (unranked / no data).
- `meta[source]`: `source`, `fetched_at` (ISO UTC, `Z`), `status`: `fresh` (fetched now), `cached` (today's file), `stale`
  (fetch or validation failed; last good cache used, `error` set). Requests are serial with a 1.0 s delay.
- Validation before swap: AP 20–25 rows, NET 300–N rows with ≤5 unmatched names, ranks 1..max and a #1. Writes are atomic (tmp + rename);
  bad data never replaces the last good file.
- **ap**: ESPN rankings API (`site.api.espn.com/.../mens-college-basketball/rankings`), the AP Top 25 poll.
- **net**: NCAA NET via the public ncaa-api.henrygd.me relay of NCAA.com; school names are matched via `net_names` in `team_map.json`.
- **kenpom**: always None. kenpom.com is behind a bot check and there is no permitted automated source, so this module does not fetch it.
- **stoopid**: the plain hand-set STOOPID rank, `meta.p` from the League's `assets/teams.js` (snapshot of
  `fantasy-bball-releases/s28f/assets/teams.js`, built 2026-10-28), bundled in `team_map.json` → `stoopid`. NOT the 50/50
  `blendRank` (that is only for mock-draft bots and grades). Only the ranked teams have one; others are None.
  To update, regenerate `team_map.json` from a new teams.js.
- `team_map.json`: `{id: {school, net_names[], stoopid}}`.
