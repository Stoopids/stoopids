#!/usr/bin/env python3
"""
archive_build.py  --  ONE-TIME builder for the STOOPIDS "Archive" tab.

Reads the past-season tabs of the public Google Sheet, extracts what each sheet
really shows (owners, team names, drafted teams + points, owner totals, final
order), and writes archive.json and archive.js (window.ARCHIVE=...).

* NOT part of the 15-minute refresh (refresh.py never calls this).
* Static output; the generated files are committed.
* Side bets / "STOOPID BETS" sections are ignored on purpose.
* Nothing is invented: every number is a cell from the sheet. Where the sheet is
  odd or incomplete we say so in the season's "notes".

Usage:  python3 archive_build.py            (downloads each tab; caches CSVs in archive_csv/)
        python3 archive_build.py --offline  (use cached CSVs only)
"""
import csv, io, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = "1LQKN3YAJdT3FoKDm7D21_0r7rmGVRhMyxdsBl__wC90"
URL = "https://docs.google.com/spreadsheets/d/%s/export?format=csv&gid=%s"
CACHE = os.path.join(HERE, "archive_csv")

# season -> (gid, tab name)   (2026-27 is the live season and is NOT archived)
TABS = [
    ("2025-26", 856705650, "2025-26"),
    ("2024-25", 1195070315, "2024-25"),
    ("2023-24", 867331452, "2023-24"),
    ("2022-23", 1267365739, "2022-23"),
    ("2021-22", 104589672, "2021-22 NCAA Pool"),
    ("2019-20", 438198393, "2019-20 NCAA Pool"),
    ("2018-19", 876434403, "2018-19 NCAA Pool"),
    ("2017-18", 0, "2017-18 NCAA Pool"),
    ("2016-17", 2122434198, "2016-17 NCAA Pool"),
    ("2015-16", 1280962798, "2015-16 NCAA Pool"),
    ("2014-15", 1899804842, "2014-15 NCAA Pool"),
]

# The sheet labels each owner's total with a first name ("KEN points"). In the
# 2025-26 tab those labels sit under the same team headers as config.json's
# owners (KENTUT/KEN, PEACOCK/JIM, KURMOJI/KURT, EN FUEGO/SCOTT, STOCK RISING/JAKE,
# POO PARTY/PAUL (the sheet's header; the owner is now "Paul"), MURFCOCK/NEAL, DRAYMOND/MARK), and the 2025-26 "Live standings"
# uses Stock/Burns/Murf/Mark/... for the same people. We use that as the bridge.
# "Matthew" (Michael Finley BBC) and "Mac" (Book Club) are not current owners.
PERSON_ALIASES = {  # lower-case label -> canonical person
    "ken": "Ken", "jim": "Jim", "kurt": "Kurt", "scott": "Scott", "burns": "Scott",
    "jake": "Jake", "paul": "Paul", "neal": "Neal", "murphy": "Neal", "murf": "Neal", "mark": "Mark",
    "matthew": "Matthew", "bee": "Matthew", "beenen": "Matthew", "mac": "Mac",
}
PERSON_TO_CURRENT = {  # canonical person -> config.json owner name
    "Mark": "Dirty Draymond", "Jake": "Stock", "Kurt": "Kurmoji", "Ken": "Kentut",
    "Neal": "Murf", "Paul": "Paul", "Jim": "Nasty", "Scott": "En Fuego",
}

# Seasons with a known quirk we want to flag (all verified against the CSVs).
SEASON_FLAGS = {
    "2019-20": dict(no_tournament=True, note="COVID: the NCAA tournament was cancelled, so this season only has regular-season wins and conference-champ bonuses (no NCAA points). Totals are as the sheet shows."),
}
# Owners whom the sheet itself leaves out of the ranking (partial entry, listed with 'x' or not at all).
UNRANKED = {
    ("2025-26", "Matthew"): "Michael Finley BBC isn't in the sheet's 2025-26 'Live standings'; the roster is joke teams with partial points, so it is shown unranked.",
    ("2024-25", "Matthew"): "Michael Finley BBC is listed with an 'x' instead of a rank in the sheet's 2024-25 standings (partial entry), so it is shown unranked.",
}
# The sheet's own standings tables (for cross-checking our ordering; not used as data).
SHEET_ORDER = {
    "2025-26": ["Neal", "Jim", "Ken", "Jake", "Kurt", "Scott", "Paul", "Mark"],
    "2024-25": ["Scott", "Kurt", "Jim", "Ken", "Mark", "Jake", "Neal", "Paul"],
    "2023-24": ["Neal", "Scott", "Kurt", "Mark", "Ken", "Paul", "Jim", "Jake", "Matthew"],
    "2022-23": ["Ken", "Neal", "Jim", "Mark", "Matthew", "Jake", "Scott", "Kurt"],
    "2021-22": ["Jim", "Jake", "Matthew", "Kurt", "Neal", "Ken", "Scott", "Mark"],
}


def fetch(season, gid):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, season + ".csv")
    if "--offline" not in sys.argv:
        try:
            req = urllib.request.Request(URL % (SHEET, gid), headers={"User-Agent": "stoopids-archive/1"})
            data = urllib.request.urlopen(req, timeout=60).read()
            open(path, "wb").write(data)
        except Exception as e:  # fall back to cache
            print("  fetch failed for", season, e, file=sys.stderr)
    return list(csv.reader(io.StringIO(open(path, encoding="utf-8").read())))


INT = re.compile(r"^-?\d+$")
EMOJI_STRIP = re.compile("[\U0001F947\U0001F948\U0001F949`*]")  # medals, stray marks


def num(s):
    s = (s or "").strip().replace(",", "")
    return int(s) if INT.match(s) else None


def clean_header(s):
    s = EMOJI_STRIP.sub("", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\s+-$", "", s)


def find_total_col(rows):
    for r in rows[:25]:
        for i, c in enumerate(r):
            if c.strip().upper() == "TOTAL":
                return i, r
    raise ValueError("no TOTAL header")


def parse_season(season, rows):
    tcol, hdr = find_total_col(rows)
    wcol = next(i for i, c in enumerate(hdr) if c.strip().lower().startswith("wins"))
    cell = lambda r, i: r[i] if i < len(r) else ""

    # owner blocks: a header row directly above a row whose first cell is "1"
    starts = []
    for i in range(1, len(rows) - 1):
        r = rows[i]
        if cell(rows[i + 1], 0).strip() != "1" or cell(r, 0).strip() == "" or INT.match(cell(r, 0).strip()):
            continue
        # must look like a real team table: 8+ numbered rows with a numeric TOTAL on row 1
        k = 0
        while i + 1 + k < len(rows) and INT.match(cell(rows[i + 1 + k], 0).strip()):
            k += 1
        if k >= 8 and num(cell(rows[i + 1], tcol)) is not None:
            starts.append(i)
    owners = []
    notes = []
    for si, h in enumerate(starts):
        end = starts[si + 1] if si + 1 < len(starts) else len(rows)
        block = rows[h + 1:end]
        picks = []
        for r in block:
            if not INT.match(cell(r, 0).strip()):
                break
            picks.append(r)
        # label like "KEN points" / "Mark's Points" / "SCOTT" sits in the column right after TOTAL
        label, lcol = None, tcol + 1
        for r in block[:14]:
            c = cell(r, lcol).strip()
            m = re.match(r"^(.*?)(?:'s)?\s+points$", c, re.I)
            if m:
                label = m.group(1).strip(); break
        if label is None and len(picks) >= 9:
            c = cell(picks[8], lcol).strip()
            if re.match(r"^[A-Za-z]+$", c) and c.lower() in PERSON_ALIASES:
                label = c
        sheet_total = None
        if label is not None:
            seen = False
            for r in block[:14]:
                c = cell(r, lcol).strip()
                if re.match(r"^(.*?)(?:'s)?\s+points$", c, re.I) or (c.lower() == (label or "").lower() and c):
                    seen = True; continue
                if seen and num(c) is not None:
                    sheet_total = num(c); break
        teams = []
        for r in picks:
            name = re.sub(r"\s+", " ", cell(r, 1)).strip()
            pts = num(cell(r, tcol))
            wins = num(cell(r, wcol))
            if re.match(r"^(X+|-)?$", name, re.I) and not pts:
                continue  # empty slot / placeholder like XXXXX
            t = {"pick": int(r[0]), "name": name or None, "pts": pts, "wins": wins}
            if not name:
                t["name"] = None
            adj = num(cell(r, 2))
            if adj is not None and adj < 0:
                t["redraft_add"] = True  # picks 9/10 carry a negative 'Jan 20 math' number = added at the redraft
            # redraft_drop is not in the CSV. apply_sheet_strikes() sets it from the xlsx font.
            teams.append(t)
        teamsum = sum(t["pts"] or 0 for t in teams)
        person = PERSON_ALIASES.get((label or "").lower().strip())
        hname = clean_header(rows[h][0])
        if person is None and "michael finley" in hname.lower():
            person = "Matthew"  # same club name every year with a MATTHEW/BEE/BEENEN label; 2025-26 label is '???'
        if person is None:
            person = label.title() if label and re.match(r"^[A-Za-z ]+$", label) else hname
        if person:
            hname = re.sub(r"^%s\s*-\s*" % re.escape(label), "", hname, flags=re.I).strip()
        o = {
            "person": person, "label": label, "team_name": hname,
            "current_owner": PERSON_TO_CURRENT.get(person),
            "total": sheet_total if sheet_total is not None else teamsum,
            "total_source": "sheet" if sheet_total is not None else "sum of team points",
            "teams": teams,
        }
        if sheet_total is not None and sheet_total != teamsum:
            o["team_sum"] = teamsum
            notes.append("%s: sheet total %d differs from the sum of team points %d (kept the sheet's total)." % (person, sheet_total, teamsum))
        if sheet_total is None:
            notes.append("%s: the sheet has no total cell; used the sum of team points (%d)." % (person or hname, teamsum))
        if any(t["name"] is None for t in teams):
            n = sum(1 for t in teams if t["name"] is None)
            o["unnamed_picks"] = n
            notes.append("%s (%s): %d pick%s in the sheet %s points but no team name." % (person, hname, n, "s" if n > 1 else "", "have" if n > 1 else "has"))
        owners.append(o)

    # ranking: highest total first; ties share a rank; unranked entries go last
    for o in owners:
        o["unranked"] = None
        key = (season, o["person"])
        if key in UNRANKED:
            o["unranked"] = UNRANKED[key]
            notes.append(UNRANKED[key])
    so = SHEET_ORDER.get(season)
    if so:  # the sheet has its own standings table: use its order (it also settles ties)
        ranked = sorted([o for o in owners if not o["unranked"]], key=lambda o: so.index(o["person"]))
    else:
        ranked = sorted([o for o in owners if not o["unranked"]], key=lambda o: -o["total"])
    prev, rk = None, 0
    for i, o in enumerate(ranked):
        o["tie"] = sum(1 for x in ranked if x["total"] == o["total"]) > 1
        if so:
            o["rank"] = i + 1  # sheet's own rank numbers
        else:
            if o["total"] != prev:
                rk = i + 1; prev = o["total"]
            o["rank"] = rk
    for o in owners:
        if o["unranked"]:
            o["rank"] = None; o["tie"] = False
    owners = ranked + [o for o in owners if o["unranked"]]
    top = ranked[0]["total"]
    champs = [o["person"] for o in ranked if o["total"] == top]
    for o in ranked:
        o["champ"] = o["total"] == top
    for o in owners:
        o.setdefault("champ", False)

    # cross-check: the sheet's own standings order must agree with the totals (ties aside)
    if so:
        tots = [o["total"] for o in ranked]
        if any(tots[i] < tots[i + 1] for i in range(len(tots) - 1)):
            print("  !! %s: the sheet's standings order disagrees with its totals: %s" % (season, tots), file=sys.stderr)
    s = {"season": season, "pool": True, "owners": owners, "champion": champs,
         "top_total": top, "sheet_has_standings_table": season in SHEET_ORDER, "notes": notes}
    f = SEASON_FLAGS.get(season)
    if f:
        s["no_tournament"] = f.get("no_tournament", False)
        s["notes"].insert(0, f["note"])
    if len(champs) > 1:
        s["notes"].append("Tie for first: " + ", ".join(champs) + ".")
    if season not in SHEET_ORDER:
        s["notes"].append("This tab has no standalone standings table, so the order is ranked from each owner's total as the sheet shows it.")
    return s


def _norm_team(s):
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).replace("\u00a0", " ")).strip().upper()


def _pick_num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)) and v == int(v) and 1 <= int(v) <= 20:
        return int(v)
    if isinstance(v, str) and re.fullmatch(r"\d+", v.strip() or ""):
        n = int(v.strip())
        if 1 <= n <= 20:
            return n
    return None


def _sheet_team_name(ws, wf, r):
    v = ws.cell(r, 2).value
    f = wf.cell(r, 2).value
    if isinstance(f, str) and f.startswith("=HYPERLINK"):
        m = re.search(r',\s*"([^"]*)"\s*\)\s*$', f)
        if m and m.group(1).strip():
            return m.group(1).strip()
    if v is None:
        return None
    text = str(v).strip()
    return text or None


def apply_sheet_strikes(archive, xlsx_path):
    """Mark redraft_drop from strikethrough on the team-name cell in the public xlsx export.

    The CSV export has the same words and numbers but no font. A row is a drop only when
    that cell's font.strike is true, the row is a numbered pick on one owner roster, and
    the name matches exactly one archived team on that roster. Jan 20 adds stay unmarked.
    Points, wins, and totals are not changed. Raises if a struck roster name cannot be matched.
    """
    import openpyxl
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    wbf = openpyxl.load_workbook(xlsx_path, data_only=False)

    def blocks(sheet):
        ws, wf = wb[sheet], wbf[sheet]
        rows = []
        for r in range(1, (ws.max_row or 0) + 1):
            font = wf.cell(r, 2).font
            rows.append((r, _pick_num(ws.cell(r, 1).value), _sheet_team_name(ws, wf, r),
                         bool(font and font.strike), ws.cell(r, 1).value))
        starts = []
        for i in range(len(rows) - 1):
            if rows[i + 1][1] != 1 or rows[i][1] is not None:
                continue
            if rows[i][4] is None or str(rows[i][4]).strip() == "":
                continue
            k = 0
            while i + 1 + k < len(rows) and rows[i + 1 + k][1] is not None:
                k += 1
            if k >= 8:
                starts.append(i)
        out = []
        for si, h in enumerate(starts):
            end = starts[si + 1] if si + 1 < len(starts) else len(rows)
            teams = []
            for rec in rows[h + 1:end]:
                if rec[1] is None:
                    break
                teams.append({"row": rec[0], "pick": rec[1], "name": rec[2], "strike": rec[3]})
            out.append({"header": str(rows[h][4]).strip(), "teams": teams})
        return out

    flagged = []
    struck_adds = []
    unclassified = []
    for season in archive["seasons"]:
        if not season.get("pool"):
            continue
        sheet = season.get("tab")
        if sheet not in wb.sheetnames:
            raise SystemExit("archive tab %r is not in the xlsx" % sheet)
        blks = blocks(sheet)
        owners = season["owners"]
        cands = []
        for bi, b in enumerate(blks):
            bnames = {_norm_team(t["name"]) for t in b["teams"] if _norm_team(t["name"])}
            for oi, o in enumerate(owners):
                onames = [_norm_team(t["name"]) for t in o["teams"] if _norm_team(t["name"])]
                if not onames:
                    continue
                ov = sum(1 for n in onames if n in bnames)
                cands.append((ov, len(onames), bi, oi))
        cands.sort(reverse=True)
        taken_b, taken_o, assigned = set(), set(), {}
        for ov, olen, bi, oi in cands:
            if bi in taken_b or oi in taken_o:
                continue
            if ov < 6 or ov < 0.6 * olen:
                continue
            rivals = [c for c in cands if c[2] == bi and c[3] not in taken_o and c[3] != oi and c[0] >= ov - 1]
            if rivals:
                continue
            taken_b.add(bi)
            taken_o.add(oi)
            assigned[oi] = bi
        seen_rows = set()
        for oi, bi in assigned.items():
            o, b = owners[oi], blks[bi]
            by = {}
            for t in b["teams"]:
                by.setdefault(_norm_team(t["name"]), []).append(t)
            for t in o["teams"]:
                t.pop("redraft_drop", None)
                hits = by.get(_norm_team(t["name"]), []) if _norm_team(t["name"]) else []
                if len(hits) != 1:
                    continue
                h = hits[0]
                seen_rows.add(h["row"])
                if not h["strike"]:
                    continue
                if t.get("redraft_add"):
                    struck_adds.append((season["season"], o["person"], t["pick"], t["name"], h["row"]))
                    continue
                t["redraft_drop"] = True
                flagged.append((season["season"], o["person"], t["pick"], t["name"], h["row"], t.get("pts"), t.get("wins")))
        for b in blks:
            for t in b["teams"]:
                if not t["strike"] or t["row"] in seen_rows:
                    continue
                name = t["name"] or ""
                if re.match(r"^(X+|-)?$", name, re.I):
                    continue
                unclassified.append((season["season"], b["header"], t["pick"], t["name"], t["row"]))
    if unclassified:
        raise SystemExit("struck roster names were not matched:\n" + "\n".join(map(str, unclassified)))
    boundary = keep_matched_drops(archive)
    flagged = [row for row in flagged if _still_dropped(archive, row)]
    return {"flagged": flagged, "struck_adds": struck_adds, "boundary": boundary}


def _still_dropped(archive, row):
    season, person, pick, name = row[0], row[1], row[2], row[3]
    for s in archive["seasons"]:
        if s.get("season") != season:
            continue
        for o in s.get("owners") or []:
            if o.get("person") != person:
                continue
            for t in o.get("teams") or []:
                if t.get("pick") == pick and t.get("name") == name:
                    return bool(t.get("redraft_drop"))
    return False


def keep_matched_drops(archive):
    """A source strikethrough is a Jan 20 drop only when that roster's struck originals
    equal its plain replacements (redraft_add). A sheet that strikes most of the original
    list, or a different count than the adds, is decoration: those names stay plain.
    Points and totals are not touched. Returns the rosters left unlabeled.
    """
    boundary = []
    for season in archive.get("seasons") or []:
        for o in season.get("owners") or []:
            teams = o.get("teams") or []
            drops = [t for t in teams if t.get("redraft_drop")]
            adds = [t for t in teams if t.get("redraft_add")]
            if drops and len(drops) == len(adds):
                continue
            for t in drops:
                t.pop("redraft_drop", None)
            if drops:
                boundary.append({
                    "season": season.get("season"),
                    "person": o.get("person"),
                    "struck": [(t.get("pick"), t.get("name")) for t in drops],
                    "adds": len(adds),
                })
    return boundary


def write_archive(out):
    json.dump(out, open(os.path.join(HERE, "archive.json"), "w"), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, "archive.js"), "w").write(
        "window.ARCHIVE=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")


def main():
    seasons = []
    for season, gid, tab in TABS:
        print("season", season, "gid", gid)
        s = parse_season(season, fetch(season, gid))
        s["tab"] = tab
        seasons.append(s)
        print("   owners=%d champion=%s top=%s notes=%d" % (len(s["owners"]), s["champion"], s["top_total"], len(s["notes"])))
    seasons.append({"season": "2020-21", "pool": False, "owners": [], "champion": [], "top_total": None,
                    "notes": ["The sheet has no 2020-21 tab (COVID year), so there is nothing to show."]})
    seasons.sort(key=lambda s: s["season"], reverse=True)

    # all-time, computed only from the parsed seasons
    people = {}
    for s in seasons:
        if not s["pool"]:
            continue
        for o in s["owners"]:
            p = people.setdefault(o["person"], {"person": o["person"], "current_owner": o["current_owner"],
                                                "titles": 0, "titles_no_tourney": 0, "title_seasons": [],
                                                "seasons": 0, "team_names": []})
            p["seasons"] += 1
            if o["team_name"] not in p["team_names"]:
                p["team_names"].append(o["team_name"])
            if o["champ"] and len(s["champion"]) == 1:
                p["titles"] += 1
                p["title_seasons"].append(s["season"])
                if s.get("no_tournament"):
                    p["titles_no_tourney"] += 1
    alltime = sorted(people.values(), key=lambda p: (-p["titles"], -p["seasons"], p["person"]))
    out = {
        "source": "https://docs.google.com/spreadsheets/d/%s" % SHEET,
        "built_by": "archive_build.py (one-time; not part of refresh.py)",
        "excludes": "all side-bet tabs and sections",
        "seasons_played": sum(1 for s in seasons if s["pool"]),
        "seasons": seasons, "alltime": alltime,
    }
    xlsx = os.path.join(CACHE, "_strike.xlsx")
    try:
        req = urllib.request.Request("https://docs.google.com/spreadsheets/d/%s/export?format=xlsx" % SHEET,
                                     headers={"User-Agent": "stoopids-archive/1"})
        open(xlsx, "wb").write(urllib.request.urlopen(req, timeout=90).read())
        rep = apply_sheet_strikes(out, xlsx)
        print("   redraft_drop=%d struck Jan 20 adds left plain=%d" % (len(rep["flagged"]), len(rep["struck_adds"])))
    except Exception as e:
        print("  xlsx strike pass failed; redraft_drop not applied:", e, file=sys.stderr)
        raise
    finally:
        if os.path.exists(xlsx):
            os.remove(xlsx)
    write_archive(out)
    print("wrote archive.json / archive.js")


if __name__ == "__main__":
    if "--keep-matched" in sys.argv:
        out = json.load(open(os.path.join(HERE, "archive.json"), encoding="utf-8"))
        before_pts = [(s.get("season"), o.get("person"), o.get("total"), [(t.get("pick"), t.get("name"), t.get("pts")) for t in (o.get("teams") or [])]) for s in out["seasons"] for o in (s.get("owners") or [])]
        boundary = keep_matched_drops(out)
        after_pts = [(s.get("season"), o.get("person"), o.get("total"), [(t.get("pick"), t.get("name"), t.get("pts")) for t in (o.get("teams") or [])]) for s in out["seasons"] for o in (s.get("owners") or [])]
        if after_pts != before_pts:
            raise SystemExit("keep-matched changed a name, pick, point, or total")
        write_archive(out)
        n=sum(1 for s in out["seasons"] for o in (s.get("owners") or []) for t in (o.get("teams") or []) if t.get("redraft_drop"))
        print("redraft_drop=%d unlabeled_rosters=%d" % (n, len(boundary)))
        for b in boundary:
            print("  unlabeled %s %s struck=%s adds=%s" % (b["season"], b["person"], b["struck"], b["adds"]))
    elif "--strike-only" in sys.argv:
        src = sys.argv[sys.argv.index("--strike-only") + 1]
        out = json.load(open(os.path.join(HERE, "archive.json"), encoding="utf-8"))
        before = json.dumps(out, ensure_ascii=False, sort_keys=True)
        rep = apply_sheet_strikes(out, src)
        def scrub(s):
            return re.sub(r',?\s*"redraft_drop"\s*:\s*true', "", s)
        if scrub(json.dumps(out, ensure_ascii=False, sort_keys=True)) != scrub(before):
            raise SystemExit("strike pass changed something other than redraft_drop")
        write_archive(out)
        print("redraft_drop=%d struck Jan 20 adds left plain=%d unlabeled_rosters=%d" % (len(rep["flagged"]), len(rep["struck_adds"]), len(rep.get("boundary") or [])))
        for row in rep["flagged"]:
            print("  drop %s %s #%s %s row %s pts %s wins %s" % row)
        for b in rep.get("boundary") or []:
            print("  unlabeled %s %s struck=%s adds=%s" % (b["season"], b["person"], b["struck"], b["adds"]))
        for row in rep["struck_adds"]:
            print("  add-kept-plain %s %s #%s %s row %s" % row)
    else:
        main()
