# sync-step1 (local only, nothing pushed/deployed)
Branch `sync-step1` in /workspace/stoopids-sync (copy of /tmp/s). All changes in index.html, marked `/*<SYNC1>*/`.

Done (ported from /workspace/mockreal patch.py + mock.css as real code):
- Small one-row tabs (laptop), 2x4 phone tabs; main/banner/nav/footer share --nav-max (1080px); Games grid 3 across >=900px.
- 🏠 (non-neutral home) + W-L record inside the pill as separate spans; long name ellipsizes (phone overlap fixed; measured 0 overlaps).
- Larger owner pills; Copy + Quick bet stacked top-right (qbHtml split into qbBtn + picker; picker logic unchanged).
- Footnote "· DraftKings"; neutral-site label dropped (as in mockup).
- Green outline `.gbet` from real 2026-27 ledger: non-void bets whose b.rd matches a game via the existing S25.match/s29Sb (same matcher as auto-settle). Applied to upcoming and final cards.
- Games row: Upcoming/Past + "Refresh Live Games" (calls existing lvManual, synced by lvUI; old #lvB hidden, #live keeps error text).
- "Pool vs Pool" label; new Team dropdown (gTeam) that filters the list.
- Standings: League/Breakdown + "Updated X ago" (genDate = D.meta.generated_at_utc, ticks via freshTick) + Refresh (reloads data.js via load()).
- Centered points; phone standings show 4-letter ESPN abbr (.cab); Bets hint line removed; tight bottom gap.
- Data and bet logic untouched.

Verification: served with python http.server on 127.0.0.1:8812; Playwright with all non-GET requests aborted (it blocked presence POSTs to textdb.dev, so nothing live was written). Screenshots in out/ (1280x800 + 390x844: standings, games, bets27, rosters, teams, + quickbet, past-bet, bottom).
Tests: test_bets, test_ranks, test_ranks_live, test_score (1 skip), test_shared all OK. test_ui_jsdom not run (npm install of jsdom failed: "idealTree already exists"). test_shared_js is a stdin helper used by test_shared.py.

Open / to review: Team dropdown lists every team in the current view (~388, long); Standings Refresh reloads data.js (no server refresh); only 1 bet currently matches a game (a final). Not committed upstream; local commit only.

## Session 2 (4 Nov ~10:05-10:35 WIB)
- Team dropdown = pool-owned teams only (any game where the team has an owner; 64 teams) + "Search teams" box (gTeamFind hides non-matching options, no re-render). Same in /workspace/league-sync (48 teams in the seeded league).
- League phone overlap fix ported: 🏠 is now its own .ghome span outside .cn (was inside the name), name ellipsizes; measured 0 overlaps, 0 🏠-in-name on both sites/sizes.
- /workspace/compare/<tab>-<laptop|phone>.png: STOOPIDS left, League right, 7 tabs (Archive is STOOPIDS-only; Rules = #about vs #rules). Raw shots in compare/raw/. All non-GET to non-localhost blocked (presence POSTs aborted).
- jsdom installed in /tmp/jsdomR8CW; test_ui_jsdom.js run with /tmp/noLiveWrites.js preload (blocks live writes): FAILS at line 47 (/Shared ledger/) on branch AND on untouched /tmp/s copy -> pre-existing stale spec (legacy bets view). Logs out/jsdom-branch.log, out/jsdom-baseline.log.

## Step 2 + 3 (4 Nov ~10:10-10:45 WIB, local only)
- SYNC2 (same code both sites): commissioner accent picker (6 presets, auto ink; STOOPIDS=localStorage `stoopids_accent` on the ?admin device, League=league store key fbn1-<id>-accent, commissioner-only), LIVE outline+pulsing dot on Games tab and Upcoming when a pool game is live (tested with faked live), bet form Amount|Odds (5,10,20,25,50,Custom / Even..5-1,Custom), Copy+Quick bet on the time row, no Moneyline on card face (kept in Copy and opened finals), opened FINAL card = ESPN summary (halves/OT, PTS/REB/AST leaders, spread + O/U result, box score link; fetched on open, cached), Standings pills (logo | abbr over record | rank right), team names uppercase, trophies inline after manager, "Points", Team dropdown removed (owner + Pool vs Pool = h2h only).
- Header line: STOOPIDS cron */15 -> "Bragging rights are checked every 15 minutes." League has no such line (its cron is every 30 min, :15/:45).
- SYNC3: tighter spacing (cards/gaps/header/banner/tabs), empty spacer rows hidden, ranked grid rank|movement slot|name|points (no movement data exists yet, slot reserved), bet form Amount/Odds stacked on phone, phone taps >=36px, Games filters v2 (toggle + round refresh; owner | Pool vs Pool | More; More = Month, Day, team search, dot when active).
- League: tap-size specs changed 44 -> 36 (tests/*, Paul approved); All teams numbers 14px = STOOPIDS.
- Shots: /workspace/compare/step2/, /workspace/compare/step3/ (before|after per site).
