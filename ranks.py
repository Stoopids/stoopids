"""STOOPIDS rank module: get_ranks(cache_dir, today) -> (ranks, meta). Stdlib only."""
import datetime as dt, json, os, re, time, unicodedata, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
AP_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/rankings"
NET_URL = "https://ncaa-api.henrygd.me/rankings/basketball-men/d1/ncaa-mens-basketball-net-rankings"
UA = "stoopids-ranks/1.0 (+stdlib urllib)"
DELAY = 1.0
SOURCES = ("ap", "net", "kenpom", "stoopid")
_last_req = [0.0]


def _get(url, timeout=25):
    wait = DELAY - (time.monotonic() - _last_req[0])
    if wait > 0:
        time.sleep(wait)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    finally:
        _last_req[0] = time.monotonic()


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace("'", "").replace(".", " ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def load_team_map(path=None):
    return json.load(open(path or os.path.join(HERE, "team_map.json"), encoding="utf-8"))["teams"]


# ---------------- parsers (pure; tested offline) -> {id: rank}
def parse_ap(j):
    polls = [p for p in j.get("rankings", []) if (p.get("type") == "ap" or "AP" in p.get("name", ""))]
    if not polls:
        raise ValueError("no AP poll in response")
    out = {}
    for r in polls[0].get("ranks", []):
        tid, rk = str(r.get("team", {}).get("id", "")), r.get("current")
        if tid and isinstance(rk, int):
            out[tid] = rk
    return out


def parse_net(j, tmap):
    idx = {}
    for tid, t in tmap.items():
        for nm in t.get("net_names", []):
            idx.setdefault(norm(nm), set()).add(tid)
    out, miss = {}, []
    for r in j.get("data", []):
        rk = str(r.get("Rank", "")).strip()
        ids = idx.get(norm(r.get("School", "")), set())
        if not rk.isdigit():
            continue
        if len(ids) == 1:
            out.setdefault(next(iter(ids)), int(rk))
        else:
            miss.append(r.get("School"))
    return out, miss


def stoopid_from_map(tmap):
    return {tid: t["stoopid"] for tid, t in tmap.items() if isinstance(t.get("stoopid"), int)}


# ---------------- validation before swap
def validate(src, ranks, n_teams):
    vals = list(ranks.values())
    if not all(isinstance(v, int) for v in vals):
        raise ValueError("%s: non-int rank" % src)
    lo, hi, top = {"ap": (20, 25, 25), "net": (300, n_teams, 400), "stoopid": (50, n_teams, n_teams)}.get(src, (1, n_teams, n_teams))
    if not lo <= len(vals) <= hi:
        raise ValueError("%s: count %d outside [%d,%d]" % (src, len(vals), lo, hi))
    if vals and (min(vals) < 1 or max(vals) > top):
        raise ValueError("%s: rank outside 1..%d" % (src, top))
    if vals and min(vals) != 1:
        raise ValueError("%s: no #1" % src)
    return True


# ---------------- cache
def _cpath(cache_dir, src, day):
    return os.path.join(cache_dir, "%s-%s.json" % (src, day))


def _latest(cache_dir, src):
    fs = sorted(f for f in os.listdir(cache_dir) if re.fullmatch(r"%s-\d{4}-\d{2}-\d{2}\.json" % src, f))
    for f in reversed(fs):
        try:
            return json.load(open(os.path.join(cache_dir, f), encoding="utf-8"))
        except Exception:
            continue
    return None


def _write(cache_dir, src, day, ranks):
    blob = {"source": src, "fetched_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "day": day, "ranks": ranks}
    p = _cpath(cache_dir, src, day)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(blob, f, sort_keys=True)
    os.replace(tmp, p)  # atomic swap
    return blob


def _source(cache_dir, src, day, fetch, n_teams):
    p = _cpath(cache_dir, src, day)
    if os.path.exists(p):
        try:
            b = json.load(open(p, encoding="utf-8"))
            return b["ranks"], {"source": src, "fetched_at": b["fetched_at"], "status": "cached"}
        except Exception:
            pass
    try:
        r = fetch()
        validate(src, r, n_teams)
        b = _write(cache_dir, src, day, r)
        return r, {"source": src, "fetched_at": b["fetched_at"], "status": "fresh"}
    except Exception as ex:
        b = _latest(cache_dir, src)
        if b:
            return b["ranks"], {"source": src, "fetched_at": b["fetched_at"], "status": "stale", "error": str(ex)[:200]}
        return {}, {"source": src, "fetched_at": None, "status": "stale", "error": str(ex)[:200]}


def get_ranks(cache_dir, today=None, team_map_path=None):
    today = today or dt.date.today()
    day = today.isoformat() if hasattr(today, "isoformat") else str(today)
    os.makedirs(cache_dir, exist_ok=True)
    tmap = load_team_map(team_map_path)
    n = len(tmap)
    got, meta = {}, {}

    def f_net():
        r, miss = parse_net(_get(NET_URL), tmap)
        if len(miss) > 5:
            raise ValueError("net: %d unmatched names e.g. %s" % (len(miss), miss[:5]))
        return r

    for src, fn in (("ap", lambda: parse_ap(_get(AP_URL))), ("net", f_net), ("stoopid", lambda: stoopid_from_map(tmap))):
        got[src], meta[src] = _source(cache_dir, src, day, fn, n)
    meta["kenpom"] = {"source": "kenpom", "fetched_at": None, "status": "stale",
                      "note": "always None: kenpom.com is behind a bot check; no permitted automated source"}
    ranks = {tid: {"ap": got["ap"].get(tid), "net": got["net"].get(tid), "kenpom": None, "stoopid": got["stoopid"].get(tid)} for tid in tmap}
    return ranks, meta


if __name__ == "__main__":
    import sys
    r, m = get_ranks(sys.argv[1] if len(sys.argv) > 1 else "./cache")
    print(json.dumps(m, indent=1))
