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

## Step 4 design fixes (4 Nov ~12:30-13:00 WIB, local only, not pushed)
Same CSS block `/*<SYNC7>*/` on both sites (STOOPIDS index.html, League css/sync-step1.css), same markup changes.
- Standings, laptop (>=700px): back to the old live row layout (rank | manager name + points | 2x4 pill grid on the right; old layout taken from origin/main). Kept from the new look: ALL CAPS manager team names, centred number + "Points", trophies inline ("Jake 🏆🏆"). Pills show the full school name (as live), now in caps, record underneath, AP rank badge kept on the right of the pill. Pills are always 4 across (League school-grid included); League phone now 4 across too (was 2 wide with 6-team rosters). Phone layout otherwise unchanged.
- Games, laptop (>=641px): filters on ONE compact row: Upcoming|Past, All owners (170px), Pool vs Pool, More, round ↻. New wrapper `.gfrow` around the existing rows (display:contents on laptop). Phone unchanged.
- New bet form (bet + pool form): bet-type toggle as a yellow segmented pill on the left, Select all / Clear as small outlined pills on the right, same line. Removed from the opponent grid (STOOPIDS) / the row under it (League). Phone labels "All" / "Clear". League's "N selected" counter is kept for screen readers only (STOOPIDS already did this).
- Data and bet logic untouched. Click check: Select all / Clear / Pool toggle work on both (7 selected / None selected).
- Shots: /workspace/compare/step4/ (old left, new right; raw/ has live-*, head-*, new-*). Verified like before: http.server / mock on localhost, Playwright with all non-GET to non-local hosts aborted.
- Tests: test_bets 19 OK, test_ranks 6 OK, test_ranks_live 11 OK, test_score 20 OK (1 skip), test_shared 7 OK, tests/test_autosettle.js 30 OK.
