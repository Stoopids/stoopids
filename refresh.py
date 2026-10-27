#!/usr/bin/env python3
"""STOOPIDS data refresh. Standard library only (Python 3.9+).

  python3 refresh.py                 # live 2026-27 season -> data.js / data.json
  python3 refresh.py --demo          # replay of last season (2025-26) with this year's rosters -> demo/data.js
  python3 refresh.py --offline       # rebuild from cache only (no network except none)

Sources (all free, no API key):
  PRIMARY  ESPN public JSON: scoreboard (scores/seeds/rounds), standings (conference champs),
           core odds API (pre-game Vegas line per game), teams (names, colors, logos).
  FALLBACK ncaa.com data via the free relay https://ncaa-api.henrygd.me (scores/seeds only, used for any day ESPN fails to load).
"""
import argparse, csv, io, json, os, re, sys, time, datetime as dt, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score as S
import bets as B

ESPN = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
ESPN_V2 = "https://site.api.espn.com/apis/v2/sports/basketball/mens-college-basketball"
CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball"
NCAA_RELAY = "https://ncaa-api.henrygd.me"
UA = {"User-Agent": "stoopids-pool/1.0 (+personal fantasy league)"}
ET = ZoneInfo("America/New_York")
WIB = ZoneInfo("Asia/Jakarta")


def log(*a):
    print(*a, file=sys.stderr)


def http_json(url, tries=3, timeout=30):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as ex:  # noqa
            last = ex
            time.sleep(1 + i)
    raise RuntimeError("fetch failed %s: %s" % (url, last))


def http_text(url, tries=3, timeout=30):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read().decode("utf-8")
        except Exception as ex:  # noqa
            last = ex
            time.sleep(1 + i)
    raise RuntimeError("fetch failed %s: %s" % (url, last))


def jload(p, default=None):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return default


def jsave(p, obj):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def deep_merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            deep_merge(a[k], v)
        else:
            a[k] = v
    return a


# ---------------------------------------------------------------- names
def norm(s):
    s = (s or "").lower().replace("&", "and").replace("\u2019", "'")
    s = re.sub(r"\bst\.?$", "state", s.strip())
    s = re.sub(r"\bst\.(?=\s)", "state", s)
    return re.sub(r"[^a-z0-9]", "", s)


def build_name_index(team_list, aliases):
    idx = {}
    for t in team_list:
        for n in (t["location"], t.get("shortDisplayName"), t.get("displayName"), t.get("abbreviation")):
            if n:
                idx.setdefault(norm(n), str(t["id"]))
        idx[norm(t["location"])] = str(t["id"])  # location always wins
    for k, v in aliases.items():
        if not k.startswith("_"):
            idx[norm(k)] = str(v)
    return idx


# ---------------------------------------------------------------- sheet
def parse_sheet(csv_text, cfg):
    rows = list(csv.reader(io.StringIO(csv_text)))
    owners = {}
    cur = None
    for i, r in enumerate(rows):
        if i < 2:
            continue
        c0 = (r[0] if r else "").strip()
        c1 = (r[1] if len(r) > 1 else "").strip()
        if c0.lower().startswith("live standings"):
            break
        if c0 and not c0.isdigit() and not c1:
            cur = None
            for o in cfg["owners"]:
                if o["sheet_header_match"].lower() in c0.lower():
                    cur = o["name"]
                    owners[cur] = {"header": c0, "teams": []}
            continue
        if cur and c0.isdigit() and c1:
            owners[cur]["teams"].append(c1)
    return owners


# ---------------------------------------------------------------- scoreboard
def status_of(e):
    n = e["status"]["type"]["name"]
    return {"STATUS_FINAL": "final", "STATUS_SCHEDULED": "scheduled", "STATUS_POSTPONED": "postponed",
            "STATUS_CANCELED": "canceled", "STATUS_SUSPENDED": "postponed", "STATUS_DELAYED": "live"}.get(n, "live" if "PROGRESS" in n or "HALF" in n or "END_" in n or "OVERTIME" in n else "other")


ROUNDS = ["First Four", "1st Round", "2nd Round", "Sweet 16", "Elite 8", "Final Four", "National Championship"]


def norm_event(e, day):
    c = e["competitions"][0]
    stype = e.get("season", {}).get("type")
    if stype == 1:
        return None  # preseason / exhibition
    note = ((c.get("notes") or [{}])[0].get("headline") or "")
    rnd = ""
    if stype == 3:
        if note.startswith("NCAA Men's Basketball Championship"):
            kind = "ncaa"
            seg = note.split(" - ")[-1]
            rnd = seg if seg in ROUNDS else seg
        else:
            kind = "post"
    else:
        if c.get("tournamentId") and c.get("conferenceCompetition"):
            kind = "conf"
            rnd = note.split(" - ")[-1] if " - " in note else ""
        else:
            kind = "reg"
    comps = c.get("competitors") or []
    if len(comps) != 2:
        return None

    def side(x):
        t = x.get("team", {})
        seed = (x.get("curatedRank") or {}).get("current")
        sc = x.get("score")
        try:
            sc = int(sc)
        except Exception:
            sc = None
        return {"id": str(t.get("id")) if t.get("id") else None, "short": t.get("shortDisplayName") or t.get("location"),
                "name": t.get("location"), "score": sc, "win": bool(x.get("winner")), "conf": t.get("conferenceId"),
                "seed": seed if (kind == "ncaa" and seed and seed < 99) else None}
    home = next((x for x in comps if x.get("homeAway") == "home"), comps[0])
    away = next((x for x in comps if x.get("homeAway") == "away"), comps[1])
    h, a = side(home), side(away)
    return {"id": str(e["id"]), "day": day, "status": status_of(e), "kind": kind, "round": rnd, "headline": note,
            "neutral": bool(c.get("neutralSite")), "confId": h["conf"] if kind == "conf" else None,
            "home": h, "away": a, "src": "espn", "start": e.get("date")}


def fetch_espn_day(day):
    ds = day.replace("-", "")
    d = http_json("%s/scoreboard?dates=%s&groups=50&limit=500" % (ESPN, ds))
    out = []
    for e in d.get("events", []):
        g = norm_event(e, day)
        if g:
            out.append(g)
    return out, len(d.get("events", []))


NCAA_ROUND = {"First Four": "First Four", "First Round": "1st Round", "Second Round": "2nd Round", "Sweet 16": "Sweet 16",
              "Elite Eight": "Elite 8", "Final Four": "Final Four", "National Championship": "National Championship"}


def fetch_ncaa_day(day, name_index):
    y, m, d_ = day.split("-")
    j = http_json("%s/scoreboard/basketball-men/d1/%s/%s/%s/all-conf" % (NCAA_RELAY, y, m, d_))
    out = []
    for item in j.get("games", []):
        g = item["game"]
        st = {"final": "final", "pre": "scheduled", "live": "live"}.get(g.get("gameState"), "other")
        title = (g.get("championshipGame") or {}).get("round", {}).get("title", "")
        is_ncaa = title in NCAA_ROUND and day[5:7] in ("03", "04") and day[5:] >= "03-15"

        def side(x):
            nm = x["names"]["short"]
            tid = name_index.get(norm(nm))
            try:
                sc = int(x.get("score"))
            except Exception:
                sc = None
            seed = int(x["seed"]) if is_ncaa and str(x.get("seed", "")).isdigit() else None
            return {"id": tid, "short": nm, "name": nm, "score": sc, "win": bool(x.get("winner")), "conf": None, "seed": seed}
        out.append({"id": "ncaa-" + str(g["gameID"]), "day": day, "status": st, "kind": "ncaa" if is_ncaa else "reg",
                    "round": NCAA_ROUND.get(title, "") if is_ncaa else "", "headline": "", "neutral": False, "confId": None,
                    "home": side(g["home"]), "away": side(g["away"]), "src": "ncaa.com",
                    "start": (dt.datetime.fromtimestamp(int(g["startTimeEpoch"]), dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ") if str(g.get("startTimeEpoch", "")).isdigit() else None)})
    return out


def daterange(a, b):
    x = dt.date.fromisoformat(a)
    y = dt.date.fromisoformat(b)
    while x <= y:
        yield x.isoformat()
        x += dt.timedelta(1)


def load_games(cfg, cache_dir, today, offline, name_index, start=None, end=None):
    year = cfg["espn_season_year"]
    sd = start or cfg["season_start"]
    ed = min(end or cfg["season_end"], (dt.date.fromisoformat(today) + dt.timedelta(cfg["refresh"]["lookahead_days"])).isoformat())
    days = list(daterange(sd, ed)) if sd <= ed else []
    stats = {"days_total": len(days), "days_fetched": 0, "days_cached": 0, "days_espn_failed": 0, "days_ncaa_fallback": 0, "days_failed_both": 0, "probe": None}
    sbdir = os.path.join(cache_dir, "sb", str(year))
    os.makedirs(sbdir, exist_ok=True)
    cutoff = (dt.date.fromisoformat(today) - dt.timedelta(2)).isoformat()

    def one(day):
        p = os.path.join(sbdir, day.replace("-", "") + ".json")
        c = jload(p)
        if c is not None:
            stale = day >= cutoff or any(g["status"] in ("scheduled", "live", "other") for g in c["games"]) or c.get("src") != "espn"
            if offline or not stale:
                return day, c["games"], "cached"
        if offline:
            return day, [], "missing"
        try:
            games, _ = fetch_espn_day(day)
            jsave(p, {"fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "src": "espn", "games": games})
            return day, games, "fetched"
        except Exception as ex:
            log("ESPN failed", day, ex)
        try:
            games = fetch_ncaa_day(day, name_index)
            jsave(p, {"fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "src": "ncaa", "games": games})
            return day, games, "ncaa"
        except Exception as ex:
            log("NCAA fallback failed", day, ex)
            return day, (c["games"] if c else []), "failed"
    games = {}
    with ThreadPoolExecutor(8) as ex:
        for day, gl, how in ex.map(one, days):
            stats["days_fetched" if how == "fetched" else "days_cached" if how == "cached" else "days_ncaa_fallback" if how == "ncaa" else "days_failed_both"] += 1
            for g in gl:
                games[g["id"]] = g
    if not offline:  # connectivity probe so preseason still proves the feed is alive
        try:
            _, n = fetch_espn_day(today)
            stats["probe"] = {"day": today, "espn_ok": True, "events_listed": n}
        except Exception as ex:
            stats["probe"] = {"day": today, "espn_ok": False, "error": str(ex)[:120]}
    return list(games.values()), stats


# ---------------------------------------------------------------- odds
def _ml(x):
    try:
        return int(str(x["moneyLine"]["american"]).replace("+", "")) if isinstance(x.get("moneyLine"), dict) else None
    except Exception:
        return None


def pick_line(game, items, prefs):
    items = [it for it in items if "live" not in it.get("provider", {}).get("name", "").lower()]
    if not items:
        return None
    order = {n.lower(): i for i, n in enumerate(prefs)}
    items.sort(key=lambda it: order.get(it["provider"]["name"].lower(), 99))
    for it in items:
        h, a = it.get("homeTeamOdds") or {}, it.get("awayTeamOdds") or {}
        which = "close" if (h.get("close") and a.get("close")) else "current"
        hml = _ml(h.get(which) or {}) if isinstance(h.get(which), dict) else None
        aml = _ml(a.get(which) or {}) if isinstance(a.get(which), dict) else None
        if hml is None:
            hml = h.get("moneyLine")
        if aml is None:
            aml = a.get("moneyLine")
        side, how = None, None
        if hml is not None and aml is not None and hml != aml:
            side, how = ("away" if aml > hml else "home"), "moneyline"
        elif it.get("spread") not in (None, 0):
            side, how = ("away" if it["spread"] < 0 else "home"), "spread"   # spread is quoted from the home team's side
        elif h.get("underdog") != a.get("underdog") and (h.get("underdog") or a.get("underdog")):
            side, how = ("home" if h.get("underdog") else "away"), "espn underdog flag"
        if hml is None and aml is None and it.get("spread") is None and side is None:
            continue
        dog = game[side] if side else None
        fav = game["away" if side == "home" else "home"] if side else None
        return {"provider": it["provider"]["name"], "details": it.get("details"), "spread_home": it.get("spread"), "total": it.get("overUnder"),
                "home_ml": hml, "away_ml": aml, "line_type": which, "underdog_side": side, "underdog_id": dog["id"] if dog else None,
                "favorite_id": fav["id"] if fav else None, "decided_by": how, "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "source": "ESPN core odds API"}
    return None


def load_lines(cfg, games, pool_tids, cache_dir, offline, ov, today):
    """Fetch/cached pre-game lines. Needed for: (a) finished games that can earn the upset bonus,
    (b) every game involving a pool team in the Games-tab window (recent finals + upcoming)."""
    scope = set(cfg["rules"]["upset_games"])
    gv = cfg.get("games_view", {})
    lo = (dt.date.fromisoformat(today) - dt.timedelta(gv.get("recent_days", 14))).isoformat()
    hi = (dt.date.fromisoformat(today) + dt.timedelta(gv.get("upcoming_days", 10))).isoformat()
    need = {}
    for g in games:
        if g["src"] != "espn" or g["status"] in ("canceled", "postponed"):
            continue
        hit = str(g["home"]["id"]) in pool_tids or str(g["away"]["id"]) in pool_tids
        if not hit:
            continue
        if g["status"] == "final":
            if g["kind"] in scope and not (g["kind"] == "ncaa" and g["round"] == "First Four" and not cfg["rules"]["upset_first_four"]):
                need[g["id"]] = g          # scoring needs it
            if g["day"] >= lo:
                need[g["id"]] = g          # games tab shows it
        elif (dt.date.fromisoformat(today) - dt.timedelta(1)).isoformat() <= g["day"] <= hi:
            need[g["id"]] = g
    odir = os.path.join(cache_dir, "odds")
    os.makedirs(odir, exist_ok=True)
    lines, miss = {}, []
    ttl = cfg["refresh"].get("upcoming_line_ttl_minutes", 15)
    now = dt.datetime.now(dt.timezone.utc)

    def fresh(c):
        try:
            return (now - dt.datetime.fromisoformat(c["fetched"])).total_seconds() < ttl * 60
        except Exception:
            return False

    def one(g):
        p = os.path.join(odir, g["id"] + ".json")
        c = jload(p)
        final = g["status"] == "final"
        if c is not None:
            if final and c.get("final"):
                return g, c.get("line")       # closing line already stored: never changes
            if final and c.get("tried_final"):
                return g, c.get("line")       # legacy cache entries
            if offline or (not final and fresh(c)):
                return g, c.get("line")
        if offline:
            return g, None
        try:
            j = http_json("%s/events/%s/competitions/%s/odds" % (CORE, g["id"], g["id"]), tries=2)
            line = pick_line(g, j.get("items", []), cfg["refresh"]["odds_provider_preference"])
            jsave(p, {"final": final, "fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "line": line})
            return g, line
        except Exception as ex:
            log("odds failed", g["id"], ex)
            return g, (c or {}).get("line")
    with ThreadPoolExecutor(8) as ex:
        for g, line in ex.map(one, list(need.values())):
            if line:
                lines[g["id"]] = line
            else:
                miss.append(g["id"])
    return lines, {"games_needing_line": len(need), "lines_found": len(lines), "missing_line_ids": miss}


# ---------------------------------------------------------------- standings
def load_standings(cfg, cache_dir, offline):
    p = os.path.join(cache_dir, "standings_%s.json" % cfg["espn_season_year"])
    raw = None
    if not offline:
        try:
            raw = http_json("%s/standings?season=%s&level=3" % (ESPN_V2, cfg["espn_season_year"]))
            jsave(p, raw)
        except Exception as ex:
            log("standings failed", ex)
    raw = raw or jload(p)
    out = {}
    for ch in (raw or {}).get("children", []):
        teams = []
        for en in ch.get("standings", {}).get("entries", []):
            last = {}
            for s in en.get("stats", []):
                last[s["name"]] = s
            try:
                cw, cl = int(last["wins"]["value"]), int(last["losses"]["value"])
                seed = int(last["playoffSeed"]["value"])
            except Exception:
                continue
            teams.append({"tid": str(en["team"]["id"]), "name": en["team"]["displayName"], "cw": cw, "cl": cl, "seed": seed})
        out[str(ch["id"])] = {"name": ch["name"], "teams": teams}
    return out, bool(raw)


# ---------------------------------------------------------------- main
def _refresh():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="replay last season with this year's rosters")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--asof", help="pretend today is YYYY-MM-DD (ET)")
    ap.add_argument("--out", help="output dir")
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--overrides", default=os.path.join(HERE, "overrides.json"))
    a = ap.parse_args()

    cfg = jload(a.config)
    out_dir = a.out or HERE
    if a.demo:
        deep_merge(cfg, jload(os.path.join(HERE, "demo_config.json")))
        out_dir = a.out or os.path.join(HERE, "demo")
        cfg["_demo"] = True
    ov = jload(a.overrides, {})
    if a.demo:
        ov = jload(os.path.join(HERE, "demo_overrides.json"), {})
    cache_dir = os.path.join(HERE, "cache")
    os.makedirs(out_dir, exist_ok=True)
    today = a.asof or (cfg["season_end"] if a.demo else dt.datetime.now(ET).date().isoformat())
    now_utc = dt.datetime.now(dt.timezone.utc)

    # teams (colors/logos)
    tpath = os.path.join(cache_dir, "teams.json")
    raw = None
    if not a.offline:
        try:
            raw = http_json(ESPN + "/teams?limit=500&groups=50")
            jsave(tpath, raw)
        except Exception as ex:
            log("teams fetch failed", ex)
    raw = raw or jload(tpath) or jload(os.path.join(HERE, "teams.json"))
    team_list = [x["team"] for x in raw["sports"][0]["leagues"][0]["teams"]]
    by_id = {str(t["id"]): t for t in team_list}
    name_index = build_name_index(team_list, cfg["team_aliases"])

    # rosters from the sheet (live), with snapshot protection around the redraft
    sheet_ok, sheet_err = True, None
    spath = os.path.join(cache_dir, "sheet.csv")
    csv_text = None
    if not a.offline:
        try:
            csv_text = http_text(cfg["sheet_csv_url"])
            with open(spath, "w") as f:
                f.write(csv_text)
        except Exception as ex:
            sheet_ok, sheet_err = False, str(ex)[:150]
    if csv_text is None and os.path.exists(spath):
        csv_text = open(spath).read()
    sheet = parse_sheet(csv_text, cfg) if csv_text else {}
    rosters, unmatched = {}, []
    for o in cfg["owners"]:
        names = (sheet.get(o["name"]) or {}).get("teams", [])
        ids = []
        for n in names:
            tid = name_index.get(norm(n))
            if tid is None:
                unmatched.append({"owner": o["name"], "sheet_name": n})
            else:
                ids.append({"tid": tid, "sheet_name": n})
        rosters[o["name"]] = ids
    snap_path = os.path.join(out_dir, "roster_snapshot.json")
    redraft_date = cfg["redraft"]["date"]
    roster_source = "sheet (live)"
    if today < redraft_date and not a.demo and all(len(v) > 0 for v in rosters.values()):
        jsave(snap_path, rosters)
    elif today >= redraft_date and os.path.exists(snap_path):
        rosters = jload(snap_path)
        roster_source = "pre-redraft snapshot (roster_snapshot.json) + redraft moves from config"

    # windows
    windows = {o["name"]: [{"tid": r["tid"], "start": None, "end": None, "sheet_name": r["sheet_name"]} for r in rosters[o["name"]]] for o in cfg["owners"]}
    warnings = []
    for owner, mv in cfg["redraft"]["moves"].items():
        for nm in mv.get("drop", []):
            tid = name_index.get(norm(nm))
            ws = [w for w in windows.get(owner, []) if w["tid"] == tid and not w["end"]]
            if not ws:
                warnings.append("redraft drop not found on %s: %s" % (owner, nm))
            for w in ws:
                w["end"] = redraft_date
        for nm in mv.get("add", []):
            tid = name_index.get(norm(nm))
            if not tid:
                warnings.append("redraft add: unknown team %s" % nm)
                continue
            ws = [w for w in windows[owner] if w["tid"] == tid and not w["end"]]
            if ws:
                ws[0]["start"] = redraft_date
            else:
                windows[owner].append({"tid": tid, "start": redraft_date, "end": None, "sheet_name": nm})
    for u in unmatched:
        warnings.append("sheet team not matched to ESPN: %s / %s" % (u["owner"], u["sheet_name"]))
    pool_tids = {str(w["tid"]) for ws in windows.values() for w in ws}

    # games / odds / standings
    games, gstats = load_games(cfg, cache_dir, today, a.offline, name_index, start=cfg["season_start"], end=cfg["season_end"])
    lines, lstats = load_lines(cfg, games, pool_tids, cache_dir, a.offline, ov, today)
    standings, st_ok = load_standings(cfg, cache_dir, a.offline)

    for g in games:
        for side in (g["home"], g["away"]):
            side["d1"] = str(side.get("id")) in by_id
    resolve = lambda n: name_index.get(norm(n))  # noqa
    gv = cfg.get("games_view", {})
    view = S.build_games_view(cfg, ov, today, games, lines, windows, gv.get("recent_days", 14), gv.get("upcoming_days", 10))
    show_tids = set(pool_tids)
    for it in view:
        for k in ("home", "away"):
            if it[k].get("id"):
                show_tids.add(str(it[k]["id"]))
    teams_info = {}
    for tid in show_tids:
        t = by_id.get(tid, {})
        logos = t.get("logos") or []
        teams_info[tid] = {"name": t.get("location"), "short": t.get("shortDisplayName"), "abbr": t.get("abbreviation"),
                           "color": t.get("color"), "alt": t.get("alternateColor"),
                           "logo": (logos[0]["href"] if logos else None), "logo_dark": next((l["href"] for l in logos if "dark" in (l.get("rel") or [])), None),
                           "mascot": t.get("name"), "espn_id": tid}
    res = S.compute(cfg, ov, today, teams_info, windows, games, standings, lines, resolve=resolve)

    # missing assets report
    pool_info = [v for k, v in teams_info.items() if k in pool_tids]
    assets = {"missing_color": [v["name"] for v in pool_info if not v["color"]],
              "missing_alt_color": [v["name"] for v in pool_info if not v["alt"]],
              "missing_logo": [v["name"] for v in pool_info if not v["logo"]]}
    n_final = sum(1 for g in games if g["status"] == "final" and g["kind"] in ("reg", "conf"))
    mode = "demo" if a.demo else ("preseason" if n_final == 0 else ("live" if today <= cfg["season_end"] else "final"))
    meta = {
        "app": cfg["app_name"], "league": cfg["league_name"], "season": cfg["season_label"], "mode": mode, "today_et": today,
        "generated_at_utc": now_utc.isoformat(timespec="seconds"),
        "generated_at_wib": now_utc.astimezone(WIB).strftime("%a %d %b %Y, %H:%M WIB"),
        "games_loaded": len(games), "final_games": n_final, "roster_source": roster_source,
        "sheet_ok": sheet_ok, "sheet_error": sheet_err, "standings_ok": st_ok,
        "fetch": gstats, "odds": lstats, "assets": assets, "warnings": warnings,
        "sources": {"scores": "ESPN public scoreboard API (primary); ncaa.com via ncaa-api.henrygd.me relay (fallback)",
                    "odds": "ESPN core odds API (DraftKings closing line preferred)", "standings": "ESPN public standings API",
                    "rosters": "Google Sheet CSV (live)"},
        "points": cfg["points"], "rules": cfg["rules"], "redraft": {"date": redraft_date, "moves": cfg["redraft"]["moves"]},
        "overrides_active": {k: v for k, v in ov.items() if not k.startswith("_") and v and v != {} and not (isinstance(v, dict) and all(str(x).startswith("_") for x in v))},
        "field": res["field"],
        "games_view": {"recent_days": gv.get("recent_days", 14), "upcoming_days": gv.get("upcoming_days", 10), "n_games": len(view),
                       "n_upcoming": sum(1 for x in view if x["status"] != "final"), "n_with_line": sum(1 for x in view if x["line"]),
                       "n_upcoming_with_line": sum(1 for x in view if x["status"] != "final" and x["line"])},
    }
    out = {"meta": meta, "owners": res["owners"], "teams": teams_info, "records": res["records"], "team_games": res["team_games"],
           "checklist": res["checklist"], "upset_audit": res["upset_audit"], "conf_audit": res["conf_audit"],
           "bets": B.package(jload(os.path.join(HERE, "bets.json"), {"people": [], "bets": []}), jload(os.path.join(HERE, "bets_imported.json"))), "games": view, "cat_labels": S.CAT_LABEL, "windows": {k: [{kk: vv for kk, vv in w.items()} for w in v] for k, v in windows.items()}}
    # FAIL-SOFT: never replace the last good data.js/data.json with empty or partial data
    prev = load_good(out_dir)
    problems = sanity_problems(out, gstats, sheet_ok, rosters, a, prev)
    if problems:
        raise Hold("; ".join(problems))
    write_data(out_dir, out)
    if not a.demo and not a.offline:        # fail-soft backup of the shared side-bets ledger (repo keeps the history)
        try:
            log("shared bets:", B.backup_shared(cfg, os.path.join(out_dir, "bets_shared_backup.json")))
        except Exception as ex:
            log("shared bets: backup failed (%s) - ignored" % ex)
    log("OK mode=%s games=%d final=%d lines=%d/%d leader=%s %s" % (mode, len(games), n_final, lstats["lines_found"], lstats["games_needing_line"], res["owners"][0]["name"], res["owners"][0]["total"]))
    if warnings:
        log("WARNINGS:\n  " + "\n  ".join(warnings))
    return 0


# ---------------------------------------------------------------- FAIL-SOFT refresh (separate change, see failsoft-refresh.diff)
class Hold(Exception):
    """A refresh problem that must NOT overwrite the last good data (reported, exit 0)."""


def load_good(out_dir):
    """The previously published data.json if it looks usable, else None."""
    d = jload(os.path.join(out_dir, "data.json"))
    if isinstance(d, dict) and isinstance(d.get("meta"), dict) and d["meta"].get("generated_at_utc") and d.get("owners"):
        return d
    return None


def write_data(out_dir, out):
    """Write data.json + data.js via temp files so a crash never leaves a half-written file."""
    jp, sp = os.path.join(out_dir, "data.json"), os.path.join(out_dir, "data.js")
    jsave(jp, out)
    with open(sp + ".tmp", "w") as f:
        f.write("window.STOOPIDS_DATA = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    os.replace(sp + ".tmp", sp)


def sanity_problems(out, gstats, sheet_ok, rosters, a, prev):
    """Reasons the freshly built data must not replace the last good data (empty / partial / not actually refreshed)."""
    p = []
    if a.offline:
        return p          # offline rebuild is an explicit manual action
    if gstats["days_total"] and gstats["days_fetched"] + gstats["days_ncaa_fallback"] == 0:
        p.append("no fresh scoreboard data from ESPN or NCAA (network down?) - data is not actually refreshed")
    empty = [o for o, v in rosters.items() if not v]
    if empty:
        p.append("no teams found in the sheet for %s%s" % (", ".join(empty), "" if sheet_ok else " (sheet fetch failed)"))
    if not out["games"] and not out["owners"]:
        p.append("built data is empty")
    if prev:
        pg = prev["meta"].get("games_loaded") or 0
        if pg and out["meta"]["games_loaded"] == 0:
            p.append("0 games loaded (previous run had %d)" % pg)
        elif gstats["days_failed_both"] and out["meta"]["games_loaded"] < pg:
            p.append("%d day(s) failed on both ESPN and NCAA and games dropped %d -> %d" % (gstats["days_failed_both"], pg, out["meta"]["games_loaded"]))
    return p


def record_refresh_error(out_dir, msg):
    """Keep the last good data; only add meta.refresh_error + a warning. generated_at_utc is NOT touched.
    Idempotent: repeating the same message rewrites nothing (no commit noise)."""
    prev = load_good(out_dir)
    if not prev:
        return False
    m = prev["meta"]
    if (m.get("refresh_error") or {}).get("message") == msg:
        return True
    tag = "REFRESH FAILED (showing last good data from %s): %s" % (m["generated_at_utc"], msg)
    m["warnings"] = [w for w in m.get("warnings", []) if not w.startswith("REFRESH FAILED")] + [tag]
    m["refresh_error"] = {"message": msg, "first_seen_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "last_good_utc": m["generated_at_utc"]}
    write_data(out_dir, prev)
    return True


def main():
    try:
        return _refresh()
    except SystemExit:
        raise
    except Exception as ex:  # noqa - Hold, network, parse, anything uncaught
        if not isinstance(ex, Hold):
            import traceback
            traceback.print_exc()
        msg = (str(ex) if isinstance(ex, Hold) else "%s: %s" % (type(ex).__name__, ex)).replace("\n", " ")[:300]
        ap = argparse.ArgumentParser(add_help=False)
        ap.add_argument("--out")
        ap.add_argument("--demo", action="store_true")
        known, _ = ap.parse_known_args()
        out_dir = known.out or (os.path.join(HERE, "demo") if known.demo else HERE)
        try:
            kept = record_refresh_error(out_dir, msg)
        except Exception as ex2:  # noqa
            log("could not record refresh error:", ex2)
            kept = bool(load_good(out_dir))
        if kept:
            log("REFRESH SOFT-FAIL (kept last good data, exit 0): " + msg)
            return 0
        log("REFRESH FATAL (no previous good data): " + msg)
        return 1


if __name__ == "__main__":
    sys.exit(main())
