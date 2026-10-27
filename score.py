"""STOOPIDS scoring engine. Pure functions, no network. Used by refresh.py and test_score.py.

Inputs are plain dicts (see refresh.py for how they are produced):
  games: normalized game list; lines: {event_id: odds line}; standings: {conf_id: {...}}
Output: everything the front end needs (leaderboard, per-team breakdown, checklist, upset audit).
"""
from collections import defaultdict

ROUND_ORDER = ["First Four", "1st Round", "2nd Round", "Sweet 16", "Elite 8", "Final Four", "National Championship"]
CAT_LABEL = {
    "win": "Wins", "conf_reg": "Conf regular-season champ", "conf_tourn": "Conf tournament champ",
    "ncaa_entry": "Made NCAA field", "playin_win": "Play-in win", "upset": "Upset (beat a better seed)",
    "ncaa_win": "NCAA tournament wins", "final4": "Final Four", "champ": "National champ",
    "missed_dance": "Missed the Big Dance", "adjust": "Commissioner adjustment",
}
FLAG_KEYS = ["conf_reg", "conf_tourn", "ncaa_entry", "final4", "champ", "missed_dance"]


def _in_window(w, day):
    if w.get("start") and day < w["start"]:
        return False
    if w.get("end") and day >= w["end"]:
        return False
    return True


def decide_upset(g, lines, cfg, ov):
    """Return dict(upset: True/False/None, basis, fallback: bool). Winner of final game g vs betting line."""
    rules = cfg["rules"]
    w, l = (g["home"], g["away"]) if g["home"].get("win") else (g["away"], g["home"])
    manual = (ov.get("upset_events") or {}).get(str(g["id"]))
    if isinstance(manual, bool):
        return {"upset": manual, "basis": "manual override", "fallback": False}
    ws, ls = w.get("seed"), l.get("seed")
    if g["kind"] == "ncaa" and rules.get("equal_seed_no_upset", True) and ws and ls and ws == ls:
        return {"upset": False, "basis": "equal seeds (no upset per pool rule)", "fallback": False}
    # NCAA tournament games: the pool judges an upset by SEED (lower seed beats a higher seed), not by Vegas.
    if g["kind"] == "ncaa" and rules.get("tournament_upset_basis", "seed") == "seed" and ws and ls:
        return {"upset": ws > ls, "basis": "seed (%s over %s)" % (ws, ls), "fallback": False}
    basis = rules.get("upset_basis", "vegas")
    line = (lines or {}).get(str(g["id"]))
    if basis == "vegas" and line:
        if line.get("underdog_id"):
            return {"upset": str(line["underdog_id"]) == str(w["id"]), "basis": "vegas line", "fallback": False}
        return {"upset": False, "basis": "vegas line: pick'em (no underdog)", "fallback": False}
    if g["kind"] == "ncaa" and ws and ls:
        return {"upset": ws > ls, "basis": "seed fallback (no odds available)", "fallback": True}
    return {"upset": None, "basis": "no odds and no seeds - cannot judge", "fallback": True}


def _short_by_id(g, tid):
    for side in (g["home"], g["away"]):
        if tid is not None and str(side.get("id")) == str(tid):
            return side.get("short")
    return None


def line_compact(g, ln, me_id=None):
    """Small, display-ready summary of a stored betting line for game g."""
    sp = ln.get("spread_home")
    return {"p": ln.get("provider"), "fav": ln.get("favorite_id"), "dog": ln.get("underdog_id"),
            "fav_name": _short_by_id(g, ln.get("favorite_id")), "dog_name": _short_by_id(g, ln.get("underdog_id")),
            "sp": abs(sp) if isinstance(sp, (int, float)) else None, "ou": ln.get("total"),
            "hml": ln.get("home_ml"), "aml": ln.get("away_ml"), "type": ln.get("line_type"),
            "we_dog": bool(me_id and ln.get("underdog_id") and str(ln["underdog_id"]) == str(me_id)),
            "we_fav": bool(me_id and ln.get("favorite_id") and str(ln["favorite_id"]) == str(me_id))}


def build_games_view(cfg, ov, today, games, lines, windows, recent_days, ahead_days):
    """Games involving pool teams: finals from the last `recent_days` and unfinished games up to `ahead_days` ahead.
    Each item carries owners per side, the stored betting line, upset verdict, and head-to-head flags."""
    import datetime as _dt
    lo = (_dt.date.fromisoformat(today) - _dt.timedelta(recent_days)).isoformat()
    lo_up = (_dt.date.fromisoformat(today) - _dt.timedelta(1)).isoformat()
    hi = (_dt.date.fromisoformat(today) + _dt.timedelta(ahead_days)).isoformat()
    scope = set(cfg["rules"].get("upset_games", ["ncaa"]))
    pool = {str(w["tid"]) for ws in windows.values() for w in ws}

    def owners_for(tid, day):
        out = []
        for o, ws in windows.items():
            for w in ws:
                if str(w["tid"]) == str(tid) and _in_window(w, day) and o not in out:
                    out.append(o)
        return out
    items = []
    for g in games:
        if g["status"] in ("canceled",):
            continue
        hid, aid = str(g["home"].get("id")), str(g["away"].get("id"))
        if hid not in pool and aid not in pool:
            continue
        fin = g["status"] == "final"
        if fin and not (lo <= g["day"]):
            continue
        if not fin and not (lo_up <= g["day"] <= hi):
            continue
        sides = {}
        for k in ("home", "away"):
            sd = g[k]
            sides[k] = {"id": sd.get("id"), "short": sd.get("short"), "seed": sd.get("seed"), "score": sd.get("score"), "win": bool(sd.get("win")),
                        "pool": str(sd.get("id")) in pool, "owners": owners_for(sd.get("id"), g["day"]) if str(sd.get("id")) in pool else []}
        ho, ao = set(sides["home"]["owners"]), set(sides["away"]["owners"])
        h2h = bool(ho and ao and not (ho & ao))
        civil = bool(ho and ao and (ho & ao))
        ln = (lines or {}).get(str(g["id"]))
        up = None
        if fin:
            d = decide_upset(g, lines, cfg, ov)
            scored = bool(d["upset"]) and g["kind"] in scope and not (g["kind"] == "ncaa" and g["round"] == "First Four" and not cfg["rules"].get("upset_first_four"))
            up = {"is": d["upset"], "scored": scored, "basis": d["basis"], "fallback": d["fallback"]}
        items.append({"id": g["id"], "day": g["day"], "start": g.get("start"), "status": g["status"], "kind": g["kind"], "round": g.get("round", ""),
                      "neutral": g.get("neutral", False), "home": sides["home"], "away": sides["away"],
                      "line": line_compact(g, ln) if ln else None, "line_raw_spread_home": (ln or {}).get("spread_home"), "upset": up,
                      "h2h": h2h, "civil": civil, "src": g.get("src", "espn")})
    items.sort(key=lambda x: (x["start"] or x["day"], x["id"]))
    return items


def compute(cfg, ov, today, teams, windows, games, standings, lines, resolve=lambda n: None):
    pts = cfg["points"]
    rules = cfg["rules"]
    ov = ov or {}
    final = [g for g in games if g["status"] == "final"]

    # ---- team records (reg season + conference tournament only) ----
    rec = defaultdict(lambda: {"w": 0, "l": 0, "conf_w": 0, "conf_l": 0})
    team_games = defaultdict(list)
    for g in games:
        if g["status"] in ("postponed", "canceled"):
            continue
        for me, op in ((g["home"], g["away"]), (g["away"], g["home"])):
            if not me.get("id"):
                continue
            row = {"id": g["id"], "day": g["day"], "kind": g["kind"], "round": g.get("round", ""), "status": g["status"],
                   "opp": op.get("short") or op.get("name"), "oppId": op.get("id"), "oppSeed": op.get("seed"),
                   "seed": me.get("seed"), "site": "N" if g.get("neutral") else ("H" if me is g["home"] else "A"),
                   "us": me.get("score"), "them": op.get("score"), "src": g.get("src", "espn"), "start": g.get("start")}
            if g["status"] == "final":
                row["res"] = "W" if me.get("win") else "L"
            ln = (lines or {}).get(str(g["id"]))
            if ln:
                row["ln"] = line_compact(g, ln, str(me.get("id")))
                if g["status"] == "final" and ln.get("underdog_id"):
                    row["upset"] = bool(me.get("win")) and row["ln"]["we_dog"]
            team_games[str(me["id"])].append(row)
            if g["status"] == "final" and g["kind"] in ("reg", "conf"):
                r = rec[str(me["id"])]
                if me.get("win"):
                    r["w"] += 1
                else:
                    r["l"] += 1

    # ---- ownership windows ----
    tw = defaultdict(list)  # tid -> [(owner, window)]
    for owner, ws in windows.items():
        for w in ws:
            tw[str(w["tid"])].append((owner, w))

    events = []  # per-team scoring events (before ownership credit)

    def ev(tid, cat, p, day, note, auto=True, game=None, **kw):
        e = {"tid": str(tid), "cat": cat, "pts": p, "day": day, "note": note, "auto": auto, "game": game}
        e.update(kw)
        events.append(e)

    for g in final:
        if g["kind"] in ("reg", "conf"):
            w = g["home"] if g["home"].get("win") else g["away"]
            l = g["away"] if w is g["home"] else g["home"]
            if w.get("id") and (rules.get("count_non_d1_wins", True) or l.get("d1", True)):
                ev(w["id"], "win", pts["win"], g["day"], "W vs %s (%s-%s)" % (l.get("short") or l.get("name"), w.get("score"), l.get("score")), game=g["id"])

    # ---- NCAA tournament ----
    ncaa = [g for g in games if g["kind"] == "ncaa" and g["status"] != "canceled"]
    ncaa_ids = set()
    entry_day = {}
    reached = defaultdict(dict)  # tid -> {round: day}
    for g in ncaa:
        for side in (g["home"], g["away"]):
            if side.get("id") and not str(side["id"]).startswith("tbd"):
                ncaa_ids.add(str(side["id"]))
                reached[str(side["id"])].setdefault(g["round"], g["day"])
    for g in ncaa:
        for side in (g["home"], g["away"]):
            tid = str(side.get("id"))
            if tid in reached and g["round"] == "1st Round":
                entry_day.setdefault(tid, g["day"])
    for g in ncaa:
        if g["status"] != "final":
            continue
        w = g["home"] if g["home"].get("win") else g["away"]
        l = g["away"] if w is g["home"] else g["home"]
        tid = str(w.get("id"))
        if g["round"] == "First Four":
            ev(tid, "playin_win", pts["playin_win"], g["day"], "First Four win vs %s" % (l.get("short") or l.get("name")), game=g["id"])
            entry_day.setdefault(tid, g["day"])
        else:
            ev(tid, "ncaa_win", pts["ncaa_win"], g["day"], "%s win vs %s (%s-%s)" % (g["round"], l.get("short") or l.get("name"), w.get("score"), l.get("score")), game=g["id"])
            if g["round"] == "National Championship":
                ev(tid, "champ", pts["champ"], g["day"], "National champion!", game=g["id"], flag="champ")
    lock_override = ov.get("field_locked")
    field_locked = bool(lock_override) if lock_override is not None else len(ncaa_ids) >= rules.get("field_locked_min_teams", 64)
    for tid, d in entry_day.items():
        ev(tid, "ncaa_entry", pts["ncaa_entry"], d, "Made the NCAA field", game=None, flag="ncaa_entry")
    for tid, rr in reached.items():
        if "Final Four" in rr:
            ev(tid, "final4", pts["final4"], rr["Final Four"], "Made the Final Four", flag="final4")

    # ---- conference tournament champs (the 'Final' game of a conf tournament) ----
    for g in final:
        if g["kind"] == "conf" and g.get("round") == "Final":
            w = g["home"] if g["home"].get("win") else g["away"]
            ev(w["id"], "conf_tourn", pts["conf_tourn"], g["day"], "Won the %s" % (g.get("headline", "").split(" - ")[0] or "conference tournament"), game=g["id"], flag="conf_tourn")

    # ---- conference regular-season champs (from standings; needs the conf tournament to have started) ----
    conf_first_day = {}
    for g in games:
        if g["kind"] == "conf" and g.get("confId") and g["status"] != "canceled" and g["day"] <= today:
            c = str(g["confId"])
            conf_first_day[c] = min(conf_first_day.get(c, "9999"), g["day"])
    conf_audit = []
    conf_reg_pending = {}
    for cid, c in (standings or {}).items():
        started = cid in conf_first_day
        leaders = [t for t in c["teams"] if t.get("seed") == 1]
        row = {"conf": c["name"], "id": cid, "tournament_started": started,
               "leader": None, "status": "waiting for conference tournament to start"}
        if started and len(leaders) == 1:
            t = leaders[0]
            row.update(leader=t["name"], status="awarded (conf record %s-%s)" % (t["cw"], t["cl"]))
            ev(t["tid"], "conf_reg", pts["conf_reg"], conf_first_day[cid], "Regular-season champ of the %s (top seed, %s-%s in conf)" % (c["name"], t["cw"], t["cl"]), flag="conf_reg")
        elif started:
            row["status"] = "NEEDS MANUAL CALL (no single top seed in standings) - use overrides.json"
            conf_reg_pending[cid] = [t["tid"] for t in c["teams"] if t.get("seed") in (1, 2)]
        conf_audit.append(row)

    # ---- upsets ----
    upset_scope = set(rules.get("upset_games", ["ncaa"]))
    audit = []
    pool_tids = set(tw.keys())
    for g in final:
        if g["kind"] not in upset_scope:
            continue
        if g["kind"] == "ncaa" and g["round"] == "First Four" and not rules.get("upset_first_four"):
            continue
        w = g["home"] if g["home"].get("win") else g["away"]
        l = g["away"] if w is g["home"] else g["home"]
        if str(w.get("id")) not in pool_tids and str(l.get("id")) not in pool_tids:
            continue
        d = decide_upset(g, lines, cfg, ov)
        line = (lines or {}).get(str(g["id"]))
        audit.append({"id": g["id"], "day": g["day"], "kind": g["kind"], "round": g.get("round", ""),
                      "winner": w.get("short"), "winnerId": w.get("id"), "winnerSeed": w.get("seed"), "winnerScore": w.get("score"),
                      "loser": l.get("short"), "loserId": l.get("id"), "loserSeed": l.get("seed"), "loserScore": l.get("score"),
                      "line": line, "upset": d["upset"], "basis": d["basis"], "fallback": d["fallback"]})
        if d["upset"]:
            ev(w["id"], "upset", pts["upset"], g["day"], "Upset: beat %s (%s)" % (l.get("short"), d["basis"]), game=g["id"], fallback=d["fallback"])

    # ---- manual flag overrides ----
    names_cache = {}
    flags_ov = {k: v for k, v in (ov.get("flags") or {}).items() if not k.startswith("_") and isinstance(v, dict)}
    flag_dates = {k: v for k, v in (ov.get("flag_dates") or {}).items() if not k.startswith("_")}
    manual_flag = defaultdict(dict)
    for name, d in flags_ov.items():
        tid = resolve(name) or (name if name in teams else None)
        if not tid:
            continue
        for k, v in d.items():
            if k in FLAG_KEYS and isinstance(v, bool):
                manual_flag[str(tid)][k] = v
    flagcat = {"conf_reg": "conf_reg", "conf_tourn": "conf_tourn", "ncaa_entry": "ncaa_entry", "final4": "final4", "champ": "champ", "missed_dance": "missed_dance"}
    # missed dance (auto)
    if field_locked:
        for tid in pool_tids:
            if tid not in ncaa_ids:
                ev(tid, "missed_dance", pts["missed_dance"], today, "Did not make the NCAA field", flag="missed_dance")
        if rules.get("first_four_loser_penalty"):
            for g in final:
                if g["kind"] == "ncaa" and g["round"] == "First Four":
                    l = g["away"] if g["home"].get("win") else g["home"]
                    ev(l["id"], "missed_dance", pts["missed_dance"], g["day"], "Lost the play-in (penalty rule ON)", flag="missed_dance")
    # apply overrides: remove auto events for denied flags; add events for forced flags
    auto_flag = defaultdict(set)
    for e in events:
        if e.get("flag"):
            auto_flag[e["tid"]].add(e["flag"])
    for tid, d in manual_flag.items():
        for k, v in d.items():
            tname = (teams.get(tid) or {}).get("short", tid)
            if v is False:
                events[:] = [e for e in events if not (e["tid"] == tid and e.get("flag") == k)]
            elif v is True and k not in auto_flag[tid]:
                day = flag_dates.get(tname) if isinstance(flag_dates.get(tname), str) else today
                if isinstance(flag_dates.get(tname), dict):
                    day = flag_dates[tname].get(k, today)
                ev(tid, k, pts[k], day, "Manual override (overrides.json)", auto=False, flag=k)
    # manual upset flags for games outside the audit list are handled by upset_events in decide_upset only.
    for a in (ov.get("adjustments") or []):
        if not isinstance(a, dict) or "pts" not in a:
            continue
        tid = resolve(a.get("team", "")) if a.get("team") else None
        events.append({"tid": str(tid) if tid else None, "owner": a.get("owner"), "cat": "adjust", "pts": a["pts"],
                       "day": a.get("date", today), "note": a.get("note", "manual adjustment"), "auto": False, "game": None})

    # ---- checklist ----
    team_conf = {}
    for g in games:
        for side in (g["home"], g["away"]):
            if side.get("conf") and side.get("id"):
                team_conf[str(side["id"])] = str(side["conf"])
    conf_final_done = {str(g["confId"]) for g in final if g["kind"] == "conf" and g.get("round") == "Final" and g.get("confId")}
    f4_set = any(g["round"] == "Final Four" for g in ncaa)
    champ_done = any(g["round"] == "National Championship" and g["status"] == "final" for g in ncaa)
    checklist = {}
    for tid in pool_tids:
        evs = [e for e in events if e["tid"] == tid]
        have = {e["cat"] for e in evs}
        man = manual_flag.get(tid, {})

        def flag(k, decided=True):
            if k in man:
                return {"v": man[k], "src": "manual"}
            if k in have:
                return {"v": True, "src": "auto"}
            return {"v": False if decided else None, "src": "auto" if decided else "pending"}
        cid = None
        for g in team_games.get(tid, []):
            pass
        cl = {}
        tc = team_conf.get(tid)
        cl["conf_reg"] = flag("conf_reg", decided=bool(tc and tc in conf_first_day))
        cl["conf_tourn"] = flag("conf_tourn", decided=bool(tc and tc in conf_final_done))
        cl["ncaa_entry"] = flag("ncaa_entry", decided=field_locked)
        cl["missed_dance"] = flag("missed_dance", decided=field_locked)
        cl["final4"] = flag("final4", decided=f4_set)
        cl["champ"] = flag("champ", decided=champ_done)
        cl["playin_win"] = {"v": "playin_win" in have, "src": "auto"}
        cl["ncaa_wins"] = sum(1 for e in evs if e["cat"] == "ncaa_win")
        cl["upsets"] = sum(1 for e in evs if e["cat"] == "upset")
        cl["upset_fallback"] = any(e.get("fallback") for e in evs if e["cat"] == "upset")
        checklist[tid] = cl

    # ---- credit owners by window ----
    owners_out = []
    for o in cfg["owners"]:
        name = o["name"]
        tl = []
        total = 0
        cat_tot = defaultdict(int)
        for w in windows.get(name, []):
            tid = str(w["tid"])
            items = []
            for e in events:
                if e["tid"] != tid or e["cat"] == "adjust":
                    continue
                if not _in_window(w, e["day"]):
                    continue
                if w.get("end") and not rules.get("dropped_keep_points", True):
                    continue
                items.append(e)
            for e in events:
                if e["cat"] == "adjust" and e.get("owner") == name and e["tid"] == tid:
                    items.append(e)
            by = defaultdict(int)
            for e in items:
                by[e["cat"]] += e["pts"]
            t_total = sum(by.values())
            wins_counted = sum(1 for e in items if e["cat"] == "win")
            status = "active"
            if w.get("end"):
                status = "dropped"
            elif w.get("start") and w["start"] > cfg.get("season_start", ""):
                status = "added"
            tl.append({"tid": tid, "window": {"start": w.get("start"), "end": w.get("end")}, "status": status,
                       "wins_counted": wins_counted, "by": dict(by), "total": t_total,
                       "items": sorted(({k: e[k] for k in ("cat", "pts", "day", "note", "auto", "game")} | ({"fallback": True} if e.get("fallback") else {}) for e in items), key=lambda x: x["day"])})
            total += t_total
            for k, v in by.items():
                cat_tot[k] += v
        for e in events:
            if e["cat"] == "adjust" and e.get("owner") == name and not e["tid"]:
                total += e["pts"]
                cat_tot["adjust"] += e["pts"]
        tl.sort(key=lambda t: (t["status"] == "dropped", -t["total"]))
        owners_out.append({"name": name, "team_name": o.get("team_name"), "emoji": o.get("emoji", ""), "total": total,
                           "by_cat": dict(cat_tot), "teams": tl})
    owners_out.sort(key=lambda o: -o["total"])
    # competition ranking
    last = None
    for i, o in enumerate(owners_out):
        o["rank"] = i + 1 if o["total"] != last else owners_out[i - 1]["rank"]
        last = o["total"]

    return {
        "owners": owners_out,
        "records": {t: dict(r) for t, r in rec.items()},
        "team_games": {t: sorted(v, key=lambda x: x["day"]) for t, v in team_games.items() if t in pool_tids},
        "checklist": checklist,
        "upset_audit": sorted(audit, key=lambda a: a["day"]),
        "conf_audit": sorted(conf_audit, key=lambda a: a["conf"]),
        "field": {"locked": field_locked, "teams_seen": len(ncaa_ids)},
    }
