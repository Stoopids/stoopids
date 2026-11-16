"""Update published KenPom, AP, and NET ranks from public sources. Stdlib only. No secrets.

A source that fails, or a NET file that is still last season's final, keeps the ranks already in
data.json. Nothing is invented. KenPom stays on the checked-in snapshot when kenpom.com refuses
a login-free read. Exits 0 even when a source is kept, so one failure does not fail the run.
Writes data.json and data.js only when a rank or a real source date changed.
"""
import datetime as dt, json, os, re, sys, urllib.error, urllib.request

import ranks
import ranks_live

HERE = os.path.dirname(os.path.abspath(__file__))
KENPOM_URL = "https://kenpom.com/"


def utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t):
    return t.isoformat().replace("+00:00", "Z")


def poll_day(value):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(value or ""))
    return m.group(1) if m else ""


def fetch_ap(now):
    try:
        j = ranks._get(ranks.AP_URL)
        polls = [p for p in j.get("rankings", []) if p.get("type") == "ap" or "AP" in p.get("name", "")]
        if not polls:
            raise ValueError("no AP poll in response")
        day = poll_day(polls[0].get("date"))
        if not day:
            raise ValueError("AP poll had no date")
        parsed = ranks.parse_ap(j)
        ranks.validate("ap", parsed, 400)
        return {"ok": True, "ranks": parsed, "poll_date": day, "fetched_at": iso(now)}
    except Exception as ex:
        return {"ok": False, "error": str(ex)[:200]}


def fetch_net(team_map, now):
    try:
        j = ranks._get(ranks.NET_URL)
        parsed, miss = ranks.parse_net(j, team_map)
        if len(miss) > 5:
            raise ValueError("net: %d unmatched names e.g. %s" % (len(miss), miss[:5]))
        ranks.validate("net", parsed, len(team_map) or 400)
        updated = str(j.get("updated") or "")
        rows = [{"record": r.get("Record") or ""} for r in j.get("data") or []]
        last = ranks_live.looks_last_final(rows, now.month) or ("final" in updated.lower())
        feed = []
        if not last:
            idx = {}
            for tid, t in team_map.items():
                for nm in t.get("net_names", []):
                    idx.setdefault(ranks.norm(nm), set()).add(tid)
            for r in j.get("data") or []:
                ids = idx.get(ranks.norm(r.get("School", "")), set())
                rk = str(r.get("Rank", "")).strip()
                if len(ids) == 1 and rk.isdigit():
                    feed.append({"net": int(rk), "school": r.get("School") or "", "record": r.get("Record") or "",
                                  "conf": r.get("Conf") or "", "tid": next(iter(ids))})
        return {"ok": True, "ranks": parsed, "updated": updated, "last_season": bool(last),
                "rows": sorted(feed, key=lambda x: x["net"]), "fetched_at": iso(now)}
    except Exception as ex:
        return {"ok": False, "error": str(ex)[:200]}


def parse_kenpom_html(body):
    """Public ratings table and its data-through date. The page's link is YYYY-MM-DD, so no weekday is kept."""
    m = re.search(r"fanmatch\.php\?d=(\d{4}-\d{2}-\d{2})", body)
    pairs = re.findall(r'<td class="hard_left">(\d+)</td><td class="next_left"><a href="team\.php\?team=[^"]+">([^<]+)</a>', body)
    if not m or not pairs:
        raise RuntimeError("kenpom.com did not include a public ratings table with a data-through date")
    as_of = m.group(1)
    rows = [{"rank": int(a), "team": b} for a, b in pairs]
    return as_of, rows


def fetch_kenpom(team_map, now):
    """The ratings table on kenpom.com is public. A login wall or a short table keeps the snapshot."""
    try:
        req = urllib.request.Request(KENPOM_URL, headers={"User-Agent": "Mozilla/5.0 (compatible; stoopids-ranks/1.0)", "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
            code = getattr(r, "status", 200)
        if code != 200:
            raise RuntimeError("HTTP %s" % code)
        as_of, rows = parse_kenpom_html(body)
        if len(rows) < 300 or min(r["rank"] for r in rows) != 1:
            raise RuntimeError("kenpom.com table was short or had no #1 (%d rows)" % len(rows))
        tmp = os.path.join(HERE, ".kenpom-parse.json")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows, f)
        try:
            mapped, miss = ranks_live.kenpom_snapshot(team_map, tmp)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        if len(mapped) < 300 or len(miss) > 5:
            raise RuntimeError("kenpom.com names did not match the team list (%d unmatched)" % len(miss))
        return {"ok": True, "ranks": mapped, "as_of": as_of, "rows": rows, "fetched_at": iso(now)}
    except urllib.error.HTTPError as ex:
        return {"ok": False, "error": "kenpom.com requires a login and blocked the read (HTTP %s). Kept the checked-in snapshot." % ex.code}
    except Exception as ex:
        return {"ok": False, "error": str(ex)[:200]}


def apply_ap(data, ap):
    teams = data.get("ranks", {}).get("teams") or {}
    src = data.setdefault("ranks", {}).setdefault("sources", {}).setdefault("ap", {})
    if not ap or not ap.get("ok"):
        return {"status": "kept", "error": (ap or {}).get("error") or "no result"}
    ranks_in, day = ap["ranks"], ap["poll_date"]
    changed = 0
    for tid, row in teams.items():
        new = ranks_in.get(str(tid))
        if row.get("ap") != new:
            row["ap"] = new
            changed += 1
    if changed or src.get("poll_date") != day:
        src["poll_date"] = day
        src["fetched_at"] = ap.get("fetched_at")
        src["status"] = "fresh"
        src["used"] = "new" if changed else "same"
        return {"status": "updated", "changed": changed, "poll_date": day}
    return {"status": "unchanged", "changed": 0, "poll_date": day}


def apply_net(data, net, net_path):
    teams = data.get("ranks", {}).get("teams") or {}
    if not net or not net.get("ok"):
        return {"status": "kept", "error": (net or {}).get("error") or "no result"}
    if net.get("last_season"):
        return {"status": "kept", "updated": net.get("updated") or "",
                "reason": "public NET feed is still last season's final list, not the current season"}
    changed = 0
    for tid, row in teams.items():
        new = net["ranks"].get(str(tid))
        if row.get("net") != new:
            row["net"] = new
            changed += 1
    wrote = False
    if net.get("rows"):
        wrote = ranks_live.write_net_if_changed(net_path, teams, _team_map_from_rows(net["rows"]), net["fetched_at"])
    src = data.setdefault("ranks", {}).setdefault("sources", {}).setdefault("net", {})
    if changed or wrote:
        src["fetched_at"] = net.get("fetched_at")
        src["status"] = "fresh"
        src["used"] = "new"
        src["as_of"] = (net.get("fetched_at") or "")[:10]
        return {"status": "updated", "changed": changed, "as_of": src.get("as_of")}
    return {"status": "unchanged", "changed": 0}


def _team_map_from_rows(rows):
    return {r["tid"]: {"school": r.get("school") or ""} for r in rows}


def apply_kenpom(data, kp):
    if not kp or not kp.get("ok") or not kp.get("ranks") or not kp.get("as_of"):
        snap = ((data.get("meta") or {}).get("ranks_fetch") or {}).get("kenpom_snapshot")
        return {"status": "kept", "as_of": snap, "error": (kp or {}).get("error") or "no public KenPom rankings"}
    teams = data.get("ranks", {}).get("teams") or {}
    changed = 0
    for tid, row in teams.items():
        new = kp["ranks"].get(str(tid))
        if new is None:
            continue
        if row.get("kenpom") != new:
            row["kenpom"] = new
            changed += 1
    src = data.setdefault("ranks", {}).setdefault("sources", {}).setdefault("kenpom", {})
    if changed or src.get("as_of") != kp["as_of"]:
        src["as_of"] = kp["as_of"]
        src["status"] = "fresh"
        src["fetched_at"] = kp.get("fetched_at")
        meta = data.setdefault("meta", {}).setdefault("ranks_fetch", {})
        meta["kenpom_snapshot"] = kp["as_of"]
        return {"status": "updated", "changed": changed, "as_of": kp["as_of"]}
    return {"status": "unchanged", "as_of": kp["as_of"], "changed": 0}


def apply_ranks(data, ap, net, kenpom, net_path):
    return {"ap": apply_ap(data, ap), "net": apply_net(data, net, net_path), "kenpom": apply_kenpom(data, kenpom)}


def write_if_changed(path_json, path_js, before, data):
    after = json.dumps(data, ensure_ascii=False, indent=1)
    if after == before:
        return False
    tmp = path_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(after)
    os.replace(tmp, path_json)
    js = path_js + ".tmp"
    with open(js, "w", encoding="utf-8") as f:
        f.write("window.STOOPIDS_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    os.replace(js, path_js)
    return True


def main():
    now = utcnow()
    path = os.path.join(HERE, "data.json")
    with open(path, encoding="utf-8") as f:
        before = f.read()
    data = json.loads(before)
    team_map = ranks.load_team_map()
    kenpom = fetch_kenpom(team_map, now)
    summary = apply_ranks(data, fetch_ap(now), fetch_net(team_map, now), kenpom, os.path.join(HERE, "data", "net.json"))
    if summary["kenpom"].get("status") == "updated" and kenpom.get("rows"):
        kp_path = os.path.join(HERE, "kenpom_o.json")
        tmp = kp_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"as_of": kenpom["as_of"], "rows": kenpom["rows"]}, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, kp_path)
    wrote = write_if_changed(path, os.path.join(HERE, "data.js"), before, data)
    summary["wrote"] = wrote
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
