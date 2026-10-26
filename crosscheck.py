#!/usr/bin/env python3
"""Compare ESPN vs ncaa.com (relay) final scores for a date range. python3 crosscheck.py 2026-03-05 2026-03-22"""
import sys, os, json
import refresh as R
a, b = sys.argv[1], sys.argv[2]
raw = R.jload(os.path.join(R.HERE, "cache", "teams.json"))
tl = [x["team"] for x in raw["sports"][0]["leagues"][0]["teams"]]
idx = R.build_name_index(tl, R.jload(os.path.join(R.HERE, "config.json"))["team_aliases"])
tot = match = diff = only_ncaa = only_espn = 0
bad = []
for day in R.daterange(a, b):
    e = {}
    for g in R.jload(os.path.join(R.HERE, "cache", "sb", "2026", day.replace("-", "") + ".json"), {"games": []})["games"]:
        if g["status"] == "final":
            e[frozenset((g["home"]["id"], g["away"]["id"]))] = (g["home"]["id"], g["home"]["score"], g["away"]["score"], g["home"]["win"])
    try:
        n = R.fetch_ncaa_day(day, idx)
    except Exception as ex:
        print(day, "ncaa fetch failed", ex); continue
    for g in n:
        if g["status"] != "final" or not g["home"]["id"] or not g["away"]["id"]:
            continue
        k = frozenset((g["home"]["id"], g["away"]["id"]))
        tot += 1
        if k not in e:
            only_ncaa += 1; continue
        hid, hs, as_, hw = e[k]
        ns = (g["home"]["score"], g["away"]["score"]) if g["home"]["id"] == hid else (g["away"]["score"], g["home"]["score"])
        nw = g["home"]["win"] if g["home"]["id"] == hid else g["away"]["win"]
        if (hs, as_) == ns and hw == nw:
            match += 1
        else:
            diff += 1; bad.append((day, g["home"]["short"], g["away"]["short"], (hs, as_), ns))
    time_ = __import__("time").sleep(0.3)
print("ncaa.com final games with both teams name-matched:", tot, "| identical score+winner in ESPN:", match, "| differ:", diff, "| not in ESPN set:", only_ncaa)
print(bad[:10])
