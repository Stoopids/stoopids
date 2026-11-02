"""STOOPIDS rank refresh wrapper (s30r design, rebuilt in s29d).

Called by refresh.py on every run; does real work at most once per ET day (3h retry after a failure).
Provider = Draft Room's ranks.get_ranks(cache_dir, today) -> (ranks{tid:{ap,net,kenpom,stoopid}}, meta{src:{status,...}}).
Rules:
  * per source, keep the last good values; a source that comes back short/invalid/stale-empty keeps the previous data.json values
  * KenPom: provider returns None, so ranks come from the kenpom_o.json snapshot (KENPOM_SNAPSHOT_DATE); a known rank is never blanked
  * STOOPID: hand-set values (STOOPIDS_STOOPID_SOURCE='current', the default). The blend is never used on STOOPIDS.
  * data/net.json rewritten only when the NET ranks actually change
Output: out['ranks'] = {'teams': {tid: {ap, net, kenpom, stoopid, stoopid_current}}, 'sources': {...}}; out['meta']['ranks_fetch'].
Stdlib only.
"""
import datetime as dt, json, os, re, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = ("ap", "net", "kenpom", "stoopid")
STOOPID_SOURCE = os.environ.get("STOOPIDS_STOOPID_SOURCE", "current")   # STOOPIDS stays 'current' (hand-set)
RETRY_HOURS = 3
KENPOM_SNAPSHOT = os.path.join(HERE, "kenpom_o.json")
KENPOM_SNAPSHOT_DATE = "2026-11-02"
KENPOM_ALIASES = {"connecticut": "41", "mississippi": "145", "n c state": "152", "seattle": "2547", "illinois chicago": "82",
                  "sam houston st": "2534", "east tennessee st": "2193", "queens": "2511", "texas a and m corpus chris": "357",
                  "cal baptist": "2856", "appalachian st": "2026", "cal st bakersfield": "2934", "southeastern louisiana": "2545",
                  "nebraska omaha": "2437", "southeast missouri": "2546", "tennessee martin": "2630", "grambling st": "2755",
                  "louisiana monroe": "2433", "albany": "399", "mississippi valley st": "2400"}
MIN_COUNT = {"ap": 20, "net": 300, "kenpom": 300, "stoopid": 1}
ET = dt.timezone(dt.timedelta(hours=-5))   # schedule day boundary (EST; a 1h DST drift is harmless for once-a-day)


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace("'", "").replace(".", " ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t):
    return t.isoformat().replace("+00:00", "Z")


def et_day(now):
    return now.astimezone(ET).date().isoformat()


# ---------------- schedule
def should_fetch(state, now):
    """Once per ET day; after a failed attempt, retry no sooner than RETRY_HOURS later."""
    state = state or {}
    if state.get("ok_day") == et_day(now):
        return False, "already fetched today (ET)"
    last = state.get("attempt_at")
    if last and state.get("status") == "fail":
        try:
            t = dt.datetime.fromisoformat(last.replace("Z", "+00:00"))
            if now - t < dt.timedelta(hours=RETRY_HOURS):
                return False, "retry wait (%dh after failure)" % RETRY_HOURS
        except Exception:
            pass
    return True, "due"


# ---------------- sources
def kenpom_snapshot(team_map, path=None):
    rows = json.load(open(path or KENPOM_SNAPSHOT, encoding="utf-8"))
    idx = {}
    for tid, t in team_map.items():
        for n in list(t.get("net_names", [])) + [t.get("school", "")]:
            idx.setdefault(norm(n), set()).add(tid)
    out, miss = {}, []
    for r in rows:
        rk, nm = r.get("rank"), norm(r.get("team", ""))
        ids = idx.get(nm, set())
        tid = KENPOM_ALIASES.get(nm) or (next(iter(ids)) if len(ids) == 1 else None)
        if isinstance(rk, int) and tid:
            out.setdefault(tid, rk)
        else:
            miss.append(r.get("team"))
    return out, miss


def good(src, vals):
    """Reject short or invalid source results (Draft Room validates too; this is the wrapper's own floor)."""
    v = [x for x in vals.values() if x is not None]
    if not v or not all(isinstance(x, int) and x >= 1 for x in v):
        return False
    return len(v) >= MIN_COUNT[src] and min(v) == 1 if src != "stoopid" else True


def merge(prev_teams, new, tids):
    """Per source: take new values if the source is good, else keep previous. Never blank a known value."""
    prev_teams = prev_teams or {}
    used = {}
    teams = {}
    for src in SOURCES:
        col = {t: (new.get(t) or {}).get(src) for t in tids}
        ok = good(src, col)
        used[src] = "new" if ok else "kept"
        for t in tids:
            p = (prev_teams.get(t) or {}).get(src)
            v = col[t] if ok else p
            if v is None and src in ("kenpom", "stoopid"):
                v = p                      # a known KenPom / hand-set STOOPID rank is never blanked
            teams.setdefault(t, {})[src] = v
    for t in tids:
        teams[t]["stoopid_current"] = teams[t]["stoopid"]
    for t, r in prev_teams.items():        # teams no longer in the map keep their previous entry
        teams.setdefault(t, r)
    return teams, used


# ---------------- NET file
def net_rows(teams, team_map, old):
    keep = {r.get("tid"): r for r in (old or {}).get("rows", []) if r.get("tid")}
    rows = []
    for t, r in teams.items():
        n = r.get("net")
        if isinstance(n, int):
            o = keep.get(t, {})
            rows.append({"net": n, "school": o.get("school") or team_map.get(t, {}).get("school", t), "record": o.get("record", ""), "conf": o.get("conf", ""), "tid": t})
    return sorted(rows, key=lambda x: x["net"])


def write_net_if_changed(path, teams, team_map, fetched_at):
    old = None
    try:
        old = json.load(open(path, encoding="utf-8"))
    except Exception:
        pass
    rows = net_rows(teams, team_map, old)
    if len(rows) < MIN_COUNT["net"]:
        return False
    if old and {(r.get("tid"), r.get("net")) for r in old.get("rows", [])} == {(r["tid"], r["net"]) for r in rows}:
        return False
    blob = {"source": "https://www.ncaa.com/rankings/basketball-men/d1/ncaa-mens-basketball-net-rankings", "as_of": "Fetched " + fetched_at[:10],
            "season": "2026-27", "fetched_at": fetched_at, "rows": rows}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(blob, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)
    return True


# ---------------- entry point
def _default_provider(cache_dir, today):
    import ranks
    return ranks.get_ranks(cache_dir, today)


def apply(out, prev, out_dir=HERE, cache_dir=None, now=None, provider=None, team_map=None):
    """Fill out['ranks'] and out['meta']['ranks_fetch']. Never raises."""
    now = now or utcnow()
    cache_dir = cache_dir or os.path.join(out_dir, "cache", "ranks")
    prev_r = (prev or {}).get("ranks") or {}
    prev_meta = ((prev or {}).get("meta") or {}).get("ranks_fetch") or {}
    state = prev_meta.get("state") or {}
    fetch = {"provider": "draft-room ranks.py", "stoopid_source": STOOPID_SOURCE, "kenpom_snapshot": KENPOM_SNAPSHOT_DATE}
    try:
        if team_map is None:
            team_map = json.load(open(os.path.join(HERE, "team_map.json"), encoding="utf-8"))["teams"]
        due, why = should_fetch(state, now)
        teams = prev_r.get("teams") or {}
        sources = prev_r.get("sources") or {}
        if due or not teams:
            state = dict(state, attempt_at=iso(now))
            try:
                new, meta = (provider or _default_provider)(cache_dir, et_day(now))
                kp, miss = kenpom_snapshot(team_map)
                for t in team_map:
                    new.setdefault(t, {})
                    if new[t].get("kenpom") is None:
                        new[t]["kenpom"] = kp.get(t)
                teams, used = merge(teams, new, list(team_map))
                sources = {s: dict((meta or {}).get(s) or {}, used=used[s]) for s in SOURCES}
                sources["kenpom"].update(status="snapshot", as_of=KENPOM_SNAPSHOT_DATE, unmatched=len(miss))
                failed = [s for s in ("ap", "net") if used[s] != "new"]
                state.update(status="fail" if failed else "ok", **({} if failed else {"ok_day": et_day(now)}))
                fetch.update(called=True, reason=why, failed=failed)
                if used["net"] == "new":
                    fetch["net_json_written"] = write_net_if_changed(os.path.join(out_dir, "data", "net.json"), teams, team_map, iso(now))
            except Exception as ex:   # provider crashed: keep everything from the previous data.json
                state.update(status="fail")
                fetch.update(called=True, reason=why, error=str(ex)[:200])
        else:
            fetch.update(called=False, reason=why)
        if teams:
            out["ranks"] = {"teams": teams, "sources": sources}
    except Exception as ex:
        fetch["error"] = str(ex)[:200]
        if prev_r:
            out["ranks"] = prev_r
    fetch["state"] = state
    fetch["at"] = iso(now)
    out.setdefault("meta", {})["ranks_fetch"] = fetch
    return out
