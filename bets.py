#!/usr/bin/env python3
"""STOOPIDS side-bets ledger: data model, amount shorthand, entry builder, tally, and the best-effort parser
for the group's "NEW BETS 25-26" Google-Sheet tab.  Standard library only.

  python3 bets.py import-sheet [--csv FILE_OR_URL]   # parse the sheet tab -> bets_imported.json + coverage report
  python3 bets.py tally                              # print the who-owes-who matrix
  python3 bets.py selftest

Files
  bets.json           YOUR live ledger (people + aliases + currency + new bets + fines). Edit by hand or via the Side Bets tab.
  bets_imported.json  best-effort parse of the 25-26 sheet tab (re-generated; never hand-edit). Bets flagged 'unparsed' are NOT in the tally.
Privacy: the importer reads ONLY the bet number, wager text and outcome text columns of the 'NEW BETS' block.
It never touches the payment-details / contact columns of the sheet and nothing like that is stored.
"""
import csv, io, json, os, re, sys, urllib.request, itertools, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET_ID = "1LQKN3YAJdT3FoKDm7D21_0r7rmGVRhMyxdsBl__wC90"
BETS_GID = "289373838"
SHEET_URL = "https://docs.google.com/spreadsheets/d/%s/export?format=csv&gid=%s" % (SHEET_ID, BETS_GID)
UA = {"User-Agent": "stoopids-pool/1.0"}

# ------------------------------------------------------------------ amounts
_SUF = {"k": 1e3, "kk": 1e6, "m": 1e6, "mil": 1e6, "mill": 1e6, "million": 1e6, "juta": 1e6, "jt": 1e6, "mm": 1e6}


def parse_amount(s, default_k=False):
    """'100K' -> 100000, '2juta' -> 2e6, '1.5mil' -> 1.5e6, '250,000' -> 250000, '500' -> 500 (or 500K if default_k)."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip().lower().replace(" ", "").replace("_", "")
    m = re.fullmatch(r"(\d[\d,]*(?:\.\d+)?)(k|kk|m|mm|mil|mill|million|juta|jt)?", t)
    if not m:
        return None
    num = float(m.group(1).replace(",", ""))
    if m.group(2):
        return num * _SUF[m.group(2)]
    return num * 1000 if default_k and num < 1000 else num


def fmt_amount(v, cur):
    unit, suf = cur.get("display_unit", 1000), cur.get("suffix", "K")
    x = v / unit
    s = ("%.2f" % x).rstrip("0").rstrip(".")
    return "%s%s%s" % (cur.get("prefix", ""), s, suf)


# ------------------------------------------------------------------ people / aliases
def alias_table(people):
    t = {}
    for p in people:
        for a in [p["id"], p["name"]] + list(p.get("aliases", [])):
            t[a.lower().strip()] = p["id"]
    return t


def name_regex(table):
    keys = sorted(table, key=len, reverse=True)
    return re.compile(r"(?<![\w@])(" + "|".join(re.escape(k) for k in keys) + r")(?![\w])", re.I)


# ------------------------------------------------------------------ building entries from structured specs
def build_entries(bet, cur=None):
    """Turn a bet's spec into ledger entries [{from,to,amount|item,note,paid}]. Types:
       versus: side_a:[ids], side_b:[ids], stake:'100K'|number|None, stake_item:'steak dinner', odds:'2.5:1', longshot:'a'|'b',
               winner:'a'|'b'|'wash'|None, games:{a:2,b:1} (per-game stakes: net games won x stake), each pair is a separate wager.
       pool:   participants:[ids], buy_in:'250K', payouts:{id: total_received}  (open until payouts present)
       direct: entries:[...] given explicitly (imports, fines paid in kind, anything odd)."""
    t = bet.get("type", "direct")
    if t == "direct":
        return [dict(e) for e in bet.get("entries", [])]
    out = []
    if t == "versus":
        w = bet.get("winner")
        stake = parse_amount(bet.get("stake"), default_k=True) if bet.get("stake") not in (None, "") else None
        item = bet.get("stake_item")
        games = bet.get("games")
        if games:
            diff = (games.get("a", 0) or 0) - (games.get("b", 0) or 0)
            if diff == 0 or stake is None:
                return []
            w = "a" if diff > 0 else "b"
            stake = stake * abs(diff)
        if w not in ("a", "b"):
            return []
        odds = None
        if bet.get("odds"):
            m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?::|-|to)\s*(\d+(?:\.\d+)?)\s*", str(bet["odds"]))
            if m:
                odds = float(m.group(1)) / float(m.group(2))
        for x in bet.get("side_a", []):
            for y in bet.get("side_b", []):
                winner, loser = (x, y) if w == "a" else (y, x)
                amt = stake
                if amt is not None and odds and bet.get("longshot") == w:
                    amt = stake * odds           # longshot side is paid at the odds when it wins
                e = {"from": loser, "to": winner}
                if amt is not None:
                    e["amount"] = round(amt, 2)
                elif item:
                    e["item"] = item
                else:
                    continue
                out.append(e)
        return out
    if t == "pool":
        pay = bet.get("payouts") or {}
        parts = bet.get("participants", [])
        bi = parse_amount(bet.get("buy_in"), default_k=True)
        if not pay or bi is None:
            return []
        net = {p: pay.get(p, 0) - bi for p in parts}
        debt = {p: -v for p, v in net.items() if v < 0}
        cred = {p: v for p, v in net.items() if v > 0}
        tot = sum(cred.values()) or 1
        for d, dv in debt.items():
            for c, cv in cred.items():
                out.append({"from": d, "to": c, "amount": round(dv * cv / tot, 2)})
        return out
    return out


def bet_status(bet, entries):
    if bet.get("status"):
        return bet["status"]
    t = bet.get("type")
    if t == "versus" and bet.get("winner") == "wash":
        return "wash"
    return "settled" if entries else "open"


# ------------------------------------------------------------------ tally
def tally(people, bets, hide_paid=False):
    ids = [p["id"] for p in people]
    M = {a: {b: 0.0 for b in ids} for a in ids}
    items = []
    cnt = {i: 0 for i in ids}
    lost, won = {i: 0.0 for i in ids}, {i: 0.0 for i in ids}
    for b in bets:
        ents = b.get("_entries", [])
        parts = set(b.get("participants", []))
        for e in ents:
            parts |= {e.get("from"), e.get("to")}
        for i in parts:
            if i in cnt:
                cnt[i] += 1
        for e in ents:
            if e.get("from") not in M or e.get("to") not in M or e["from"] == e["to"]:
                continue
            if hide_paid and e.get("paid"):
                continue
            if "amount" in e:
                M[e["from"]][e["to"]] += e["amount"]
                lost[e["from"]] += e["amount"]
                won[e["to"]] += e["amount"]
            else:
                items.append({"bet": b.get("n"), "from": e["from"], "to": e["to"], "item": e.get("item", ""), "paid": bool(e.get("paid"))})
    return {"ids": ids, "matrix": M, "lost": lost, "won": won, "net": {i: won[i] - lost[i] for i in ids}, "bets": cnt, "items": items}


# ------------------------------------------------------------------ the sheet importer (best effort)
ITEM_RE = re.compile(r"\b(t-?shirt|tee shirt|shirt|hoodie|gift|dinner|steak|beers?|round of golf|golf|jersey|lunch|pizza)\b")
AMT = "\u00a7"   # marker for parsed amounts inside a sentence


def _split_names(s, rx, table):
    out = []
    for m in rx.finditer(s):
        pid = table[m.group(1).lower()]
        if pid not in out:
            out.append(pid)
    return out


_NAMES = r"((?:@\w+[\s,]*(?:and\s+)?)+)"
_OWE = re.compile(_NAMES + r"\s*(?:(?:all|each)\s+)?(?:still\s+)?(?:owes?|owed)\s*(?:to\s+)?((?:@\w+[\s,]*(?:and\s+)?)*)\s*(" + AMT + r"\d+)?")
_WINS = re.compile(r"(?:^|\W)(@\w+)\s+(?:wins?|collects?|gets?)\s+(?:" + AMT + r"(\d+)\s+from\s+)?" + _NAMES + r"\s*(?:each\s+)?(?:pay|pays|owe|owes)\s*(" + AMT + r"\d+)?")
_PAYTO = re.compile(_NAMES + r"\s*(?:pay|pays)\s*(" + AMT + r"\d+)?\s*(?:each|ea)?\s*(?:to\s+)" + _NAMES)
_PAYS = re.compile(_NAMES + r"\s*(?:pay|pays)\s+" + _NAMES + r"\s*(" + AMT + r"\d+)")


def parse_outcome(outcome, wager, people, table=None, rx=None):
    """Return dict(status, entries, notes). status: open | settled | wash | unparsed.
    Never guesses silently: every assumption lands in notes; anything not understood -> 'unparsed' (excluded from the tally)."""
    table = table or alias_table(people)
    rx = rx or name_regex(table)
    out = (outcome or "").strip()
    if not out:
        return {"status": "open", "entries": [], "notes": ["no outcome written yet"]}
    low = out.lower()
    sents = [x.strip() for x in re.split(r"\.+(?=\s|$)|[\n;]+", out) if x.strip()]
    if re.search(r"\bwash\b", sents[-1], re.I) or (re.search(r"\bwash\b", low) and not re.search(r"\bowes?\b", low)):
        return {"status": "wash", "entries": [], "notes": []}
    entries, bad, notes = [], [], []
    wager_amts = sorted({int(a) for a in (parse_amount(x.replace(" ", "")) for x in re.findall(r"(?<![\w\.])\d[\d,]*(?:\.\d+)?\s?(?:k|K|mil|juta)\b", wager or "")) if a})
    for s0 in sents:
        if not re.search(r"\b(owes?|owed|pays?|payed|collects?)\b|\bwins?\s+\d[\d,\.]*\s?(?:k|mil|mill|juta)\b", s0, re.I):
            continue                                   # pure game-result text
        paid = bool(re.search(r"\bpaid\b", s0, re.I))
        t = rx.sub(lambda m: "@" + table[m.group(1).lower()], s0)
        t = re.sub(r"(?<![\w@])(\d[\d,]*(?:\.\d+)?)\s?(kk|mil|mill|million|juta|jt|k)\b", lambda m: AMT + "%d" % parse_amount(m.group(1) + m.group(2)), t, flags=re.I)
        t = re.sub(r"(?<![\w@\u00a7\.])(\d{1,3}(?:,\d{3})+)\b", lambda m: AMT + "%d" % parse_amount(m.group(1)), t)
        # bare 2-3 digit number right after owes/pay(s) ... = thousands in this ledger; recorded as an assumption
        _bare = r"((?:owes?|pays?)\s+(?:@\w+[\s,]*(?:and\s+)?)*)(\d{2,3})\b(?!\s*[-:/])"
        bare_k = bool(re.search(_bare, t))
        t = re.sub(_bare, lambda m: m.group(1) + AMT + "%d" % (int(m.group(2)) * 1000), t)
        t = t.replace("&", " and ")
        tl = t.lower()
        each = bool(re.search(r"\b(each|ea|all)\b", tl))
        names = lambda frag: re.findall(r"@(\w+)", frag)
        verbs = len(re.findall(r"\b(owes?|owed)\b", tl))
        groups = []   # (debtors, creditors, amount|None)
        for m in _OWE.finditer(tl):
            d, c = names(m.group(1)), names(m.group(2))
            if c or m.group(3):
                groups.append((d, c, int(m.group(3)[1:]) if m.group(3) else None))
        if verbs and len(groups) < verbs:
            groups = [g for g in groups]  # partial
        if not groups:
            m = _WINS.search(tl)
            if m:
                groups.append((names(m.group(3)), names(m.group(1)), int((m.group(2) or (m.group(4) or "  ")[1:]) or 0) or None))
            else:
                m = _PAYS.search(tl)
                if m:
                    groups.append((names(m.group(1)), names(m.group(2)), int(m.group(3)[1:])))
                else:
                    m = _PAYTO.search(tl)
                    if m:
                        groups.append((names(m.group(1)), names(m.group(3)), int(m.group(2)[1:]) if m.group(2) else None))
        pay_verbs = len(re.findall(r"\b(owes?|owed|pay|pays)\b", tl))
        if not groups or (verbs and len(groups) < verbs and not re.search(r"\b(pay|pays)\b", tl)):
            unk = re.findall(r"\b([A-Za-z][\w']+)\s+owes?\b", s0)
            grp = re.search(r"\b(everyone|all the guys|the guys|boys|all)\b", s0, re.I)
            unk = [u for u in unk if u.lower() not in table and u.lower() not in ("who", "he", "she", "it", "they", "everyone", "all", "boys", "and", "guys")]
            if grp and not unk:
                bad.append("group payers named only as 'everyone/boys/all': %r" % s0[:70])
            elif unk:
                bad.append("unknown name %r - add it as an alias in bets.json 'people'" % unk[0])
            elif re.search(r"\b(owes?|owed|pays?|collects?)\b", s0, re.I) and "@" in t:
                bad.append("could not read all payment clauses: %r" % s0[:80])
            elif re.search(r"\b(everyone|all the guys|the guys|boys)\b", s0, re.I):
                bad.append("group payers named only as 'everyone/boys/all the guys': %r" % s0[:70])
            else:
                bad.append("payment wording without a clear payer/receiver: %r" % s0[:70])
            continue
        for deb, cred, amount in groups:
            assumed = []
            item = None
            if amount is None:
                im = ITEM_RE.search(tl)
                if im:
                    item = im.group(1)
            if amount is None and item is None:
                if len(wager_amts) == 1:
                    amount = wager_amts[0]; assumed.append("amount taken from wager text (%dK)" % (amount / 1000))
                else:
                    bad.append("no amount in outcome and none/ambiguous in wager: %r" % s0[:70]); continue
            if bare_k and amount:
                assumed.append("bare number read as thousands (K)")
            if amount is not None and amount < 1000:
                bad.append("amount %s: unit unclear in %r" % (amount, s0[:60])); continue
            if len(deb) > 1 and not each and amount:
                assumed.append("several debtors without 'each': assumed %dK each" % (amount / 1000))
            if len(cred) > 1 and amount:
                assumed.append("several creditors: assumed %dK to each" % (amount / 1000))
            for d in deb:
                for c in cred:
                    if d == c:
                        continue
                    e = {"from": d, "to": c}
                    if item:
                        e["item"] = item
                    else:
                        e["amount"] = amount
                    if paid and s0.lower().find("paid") >= 0 and len(sents) >= 1 and re.search(r"\bpaid\b", s0, re.I):
                        e["paid"] = True
                    entries.append(e)
            notes += assumed
    if bad:
        return {"status": "unparsed", "entries": [], "notes": bad[:3]}
    if not entries:
        return {"status": "unparsed", "entries": [], "notes": ["outcome text has no payment wording I understand (result only?)"]}
    seen, uniq = set(), []
    for e in entries:
        k = (e["from"], e["to"], e.get("amount"), e.get("item"))
        if k in seen:
            continue
        seen.add(k); uniq.append(e)
    return {"status": "settled", "entries": uniq, "notes": sorted(set(notes))}


def mentioned(text, people, table=None, rx=None):
    table = table or alias_table(people)
    rx = rx or name_regex(table)
    return _split_names(text or "", rx, table)


def import_sheet(csv_text, people):
    rows = list(csv.reader(io.StringIO(csv_text)))
    i0 = next((i for i, r in enumerate(rows) if r and "NEW BETS START" in (r[0] or "").upper()), None)
    if i0 is None:
        raise SystemExit("could not find the 'NEW BETS START HERE' marker row")
    table = alias_table(people)
    rx = name_regex(table)
    bets = []
    for r in rows[i0 + 1:]:
        # ONLY these three columns are read: bet number (A), wager text (B), outcome text (J).  Nothing else.
        n = (r[0] if len(r) > 0 else "").strip()
        wager = (r[1] if len(r) > 1 else "").strip()
        outcome = (r[9] if len(r) > 9 else "").strip()
        if not n and not wager:
            continue
        res = parse_outcome(outcome, wager, people, table, rx)
        parts = mentioned(wager + " " + outcome, people, table, rx)
        bets.append({"n": n, "season": "2025-26", "type": "direct", "text": wager, "outcome": outcome, "participants": parts,
                     "entries": res["entries"], "parse": {"status": res["status"], "notes": res["notes"]}, "source": "sheet:NEW BETS 25-26"})
    return bets


def coverage(bets):
    c = {"total": len(bets), "settled": 0, "settled_with_assumptions": 0, "wash": 0, "open": 0, "unparsed": 0, "with_money": 0, "with_items": 0}
    for b in bets:
        st = b["parse"]["status"]
        if st == "settled":
            c["settled"] += 1
            if b["parse"]["notes"]:
                c["settled_with_assumptions"] += 1
            if any("amount" in e for e in b["entries"]):
                c["with_money"] += 1
            if any("item" in e for e in b["entries"]):
                c["with_items"] += 1
        else:
            c[st] += 1
    return c


# ------------------------------------------------------------------ load + derive
def load_people_ledger(path=None):
    return json.load(open(path or os.path.join(HERE, "bets.json")))


def derive(ledger, imported=None, scope="all"):
    """Return everything the UI needs: bets with derived entries/status, tally, coverage."""
    people = ledger["people"]
    cur = ledger.get("currency", {})
    allb = []
    for b in ledger.get("bets", []):
        e = build_entries(b, cur)
        b2 = dict(b); b2["_entries"] = e; b2["_status"] = bet_status(b, e); b2["_src"] = "ledger"
        allb.append(b2)
    for b in (imported or {}).get("bets", []):
        b2 = dict(b); b2["_entries"] = b["entries"]; b2["_status"] = b["parse"]["status"]; b2["_src"] = "imported"
        allb.append(b2)
    return allb


def package(ledger, imported):
    """Everything the front end needs for the Side Bets tab (pre-computed tallies for each scope)."""
    people = ledger["people"]
    allb = derive(ledger, imported)
    fines = {p["id"]: 0.0 for p in people}
    for f in ledger.get("fines", []):
        if f.get("person") in fines:
            amt = parse_amount(f.get("amount"), default_k=True)
            fines[f["person"]] += amt or 0
    tallies = {}
    for scope, pred in (("all", lambda b: True), ("ledger", lambda b: b["_src"] == "ledger"), ("imported", lambda b: b["_src"] == "imported")):
        sel = [b for b in allb if pred(b) and b["_status"] in ("settled",)]
        tallies[scope] = {"all": tally(people, sel, False), "unpaid": tally(people, sel, True)}
    out_bets = []
    for b in allb:
        o = {"n": str(b.get("n", "")), "season": b.get("season", ""), "src": b["_src"], "status": b["_status"], "type": b.get("type", "direct"),
             "text": b.get("text", ""), "outcome": b.get("outcome", ""), "entries": b["_entries"], "participants": b.get("participants", []),
             "notes": (b.get("parse") or {}).get("notes", [])}
        if b["_src"] == "ledger":
            o["spec"] = {k: v for k, v in b.items() if not k.startswith("_")}
        out_bets.append(o)
    return {"currency": ledger.get("currency", {}), "people": people, "bets": out_bets, "tallies": tallies, "fines": fines,
            "coverage": (imported or {}).get("coverage"), "imported_at": (imported or {}).get("generated")}


# ------------------------------------------------------------------ ledger edits (used by serve.py and the CLI)
ALLOWED = {"versus": {"type", "n", "text", "date", "season", "side_a", "side_b", "stake", "stake_item", "odds", "longshot", "winner", "games", "outcome"},
           "pool": {"type", "n", "text", "date", "season", "participants", "buy_in", "payouts", "outcome"}}
PATCHABLE = {"winner", "games", "payouts", "outcome", "text", "stake", "odds", "longshot"}


def _save(path, led):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(led, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def validate_bet(bet, people):
    ids = {p["id"] for p in people}
    t = bet.get("type")
    if t not in ALLOWED:
        raise ValueError("type must be 'versus' or 'pool'")
    extra = set(bet) - ALLOWED[t]
    if extra:
        raise ValueError("unexpected fields: %s" % sorted(extra))
    if not str(bet.get("text", "")).strip():
        raise ValueError("write the wager terms in 'text'")
    for k in ("side_a", "side_b", "participants"):
        for i in bet.get(k, []):
            if i not in ids:
                raise ValueError("unknown person id %r (add them to 'people' first)" % i)
    if t == "versus":
        if not bet.get("side_a") or not bet.get("side_b"):
            raise ValueError("both sides need at least one person")
        if set(bet["side_a"]) & set(bet["side_b"]):
            raise ValueError("a person can't be on both sides")
        if bet.get("stake") not in (None, "") and parse_amount(bet["stake"], default_k=True) is None:
            raise ValueError("can't read stake %r (try 100K, 1.5mil, 2juta, 250,000)" % bet["stake"])
        if not bet.get("stake") and not bet.get("stake_item"):
            raise ValueError("give a stake (100K) or a non-cash stake_item")
        if bet.get("winner") not in (None, "a", "b", "wash"):
            raise ValueError("winner must be a, b, wash or empty (open)")
        if bet.get("odds") and not re.fullmatch(r"\s*\d+(?:\.\d+)?\s*(?::|-|to)\s*\d+(?:\.\d+)?\s*", str(bet["odds"])):
            raise ValueError("odds look like 2:1 or 3.5:1")
        if bet.get("odds") and bet.get("longshot") not in ("a", "b"):
            raise ValueError("odds need 'longshot' = a or b (which side is paid at the odds)")
    else:
        if len(bet.get("participants", [])) < 2:
            raise ValueError("a pool needs 2+ participants")
        if parse_amount(bet.get("buy_in"), default_k=True) is None:
            raise ValueError("pool needs a buy_in like 250K")
        pay = bet.get("payouts") or {}
        if pay:
            bi = parse_amount(bet["buy_in"], default_k=True)
            tot = sum(parse_amount(v, default_k=True) or 0 for v in pay.values())
            if abs(tot - bi * len(bet["participants"])) > 1:
                raise ValueError("payouts add up to %s but the pot is %s" % (tot, bi * len(bet["participants"])))
    return True


def add_bet(bet, path=None):
    path = path or os.path.join(HERE, "bets.json")
    with open(path) as _f:
        led = json.load(_f)
    bet = dict(bet)
    validate_bet(bet, led["people"])
    if isinstance(bet.get("payouts"), dict):
        bet["payouts"] = {k: parse_amount(v, default_k=True) for k, v in bet["payouts"].items()}
    nums = [int(b["n"]) for b in led.get("bets", []) if str(b.get("n", "")).isdigit()]
    if not bet.get("n"):
        bet["n"] = str(max(nums + [0]) + 1)
    if any(str(b.get("n")) == str(bet["n"]) for b in led.get("bets", [])):
        raise ValueError("bet number %s already exists" % bet["n"])
    bet.setdefault("season", "2026-27")
    bet.setdefault("date", dt.date.today().isoformat())
    led.setdefault("bets", []).append(bet)
    _save(path, led)
    return bet["n"]


def update_bet(n, patch, path=None):
    path = path or os.path.join(HERE, "bets.json")
    with open(path) as _f:
        led = json.load(_f)
    for b in led.get("bets", []):
        if str(b.get("n")) == str(n):
            bad = set(patch) - PATCHABLE
            if bad:
                raise ValueError("can't patch %s" % sorted(bad))
            nb = dict(b); nb.update(patch)
            if isinstance(nb.get("payouts"), dict):
                nb["payouts"] = {k: parse_amount(v, default_k=True) for k, v in nb["payouts"].items()}
            validate_bet(nb, led["people"])
            b.update({k: nb[k] for k in patch if k in nb})
            if isinstance(b.get("payouts"), dict):
                b["payouts"] = nb["payouts"]
            _save(path, led)
            return True
    raise ValueError("no ledger bet numbered %s (imported sheet bets are read-only)" % n)


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("import-sheet", "tally", "selftest"):
        print(__doc__); return 1
    if a[0] == "import-sheet":
        src = a[a.index("--csv") + 1] if "--csv" in a else SHEET_URL
        text = open(src).read() if os.path.exists(src) else urllib.request.urlopen(urllib.request.Request(src, headers=UA), timeout=30).read().decode("utf-8")
        led = load_people_ledger()
        bets = import_sheet(text, led["people"])
        cov = coverage(bets)
        with open(os.path.join(HERE, "bets_imported.json"), "w") as _o:
          json.dump({"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "note": "Best-effort parse of the 25-26 sheet tab. Re-generated by `bets.py import-sheet`; do not hand-edit. 'unparsed' bets are excluded from the tally.",
                   "coverage": cov, "bets": bets}, _o, indent=1, ensure_ascii=False)
        print(json.dumps(cov, indent=1))
        return 0
    if a[0] == "tally":
        led = load_people_ledger()
        imp = json.load(open(os.path.join(HERE, "bets_imported.json"))) if os.path.exists(os.path.join(HERE, "bets_imported.json")) else None
        bs = derive(led, imp)
        t = tally(led["people"], bs)
        ids = t["ids"]
        print("%-8s" % "owes>" + "".join("%8s" % i[:7] for i in ids) + "    lost     won     net  bets")
        for r in ids:
            print("%-8s" % r[:7] + "".join("%8.0f" % (t["matrix"][r][c] / 1000) for c in ids) + "%8.0f%8.0f%8.0f%6d" % (t["lost"][r] / 1000, t["won"][r] / 1000, t["net"][r] / 1000, t["bets"][r]))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
