#!/usr/bin/env python3
"""Season totals and S-F letter grades for every category. Usage: python3 tools/grades.py [2026]

Grades are percentiles among qualified hitters (300+ PA) in that season:
  S 97-100 · A 85-96 · B 65-84 · C 40-64 · D 20-39 · E 8-19 · F 0-7
Writes data/grades-<season>.json.
"""
import collections, glob, gzip, json, os, statistics as st, sys
from calibrate import load, run_values
from score import load_weights, score_v8, people, ROOT

MIN_PA = 300
TIERS = [(97, "S"), (85, "A"), (65, "B"), (40, "C"), (20, "D"), (8, "E"), (0, "F")]
NON_CONTACT = {"bb", "bb30", "ibb", "hbp", "ci", "k_swing", "k_look_in", "k_look_out"}
CATS = [  # key, label, format
    ("clutch", "Overall", "{:+.2f}"), ("quality", "Quality", "{:+.2f}"), ("contact", "Contact", "{:.1f}%"),
    ("power", "Power", "{:+.2f}"), ("results", "Results", "{:+.2f}"), ("discipline", "Discipline", "{:+.2f}"), ("grind", "Grind", "{:+.2f}"),
    ("runs", "Run production", "{:+.2f}"), ("steal", "Base stealing", "{:+.1f}"),
    ("gap", "Clutch", "{:+.2f}"), ("qab", "QAB%", "{:.0f}%"), ("cons", "Consistency", "{:.0f}%"),
]


def grade(p):
    return next(g for cut, g in TIERS if p >= cut)


def steal_key(why):
    """Map an MLB runner movement reason to a steal value key (None if it isn't a steal event)."""
    w = why or ""
    if "error" in w: return None
    base = "2b" if w.endswith("2b") else "3b" if w.endswith("3b") else "home" if w.endswith("home") else "1b"
    if "stolen_base" in w: return "sb_" + base
    if "caught_stealing" in w: return "cs_" + base
    if w.startswith("r_pickoff_"): return "po_" + base
    return None


def steal_counts(yr):
    """Per runner: Counter of steal events in regular-season games (deduplicated)."""
    out = collections.defaultdict(collections.Counter)
    for fn in glob.glob(os.path.join(ROOT, "pbp", str(yr), "*.json.gz")):
        with gzip.open(fn, "rt") as f:
            g = json.load(f)
        if g["game"]["type"] != "R": continue
        seen = set()
        for p in g["plays"]:
            for s in p["runners"]:
                k = steal_key(s["why"])
                key = (s["id"], s["why"], p["inn"], p["top"], s["start"], s["end"], s["out"])
                if k and key not in seen:
                    seen.add(key); out[s["id"]][k] += 1
    return out


def line(xs, steals, W):
    bip = [x for x in xs if x["ek"] not in NON_CONTACT]
    games = collections.defaultdict(list)
    for x in xs:
        games[x["pk"]].append(x)
    g2 = [g for g in games.values() if len(g) >= 2]
    sm = sum(x["m"] for x in xs)
    base = st.mean(x["base"] for x in xs)
    swings = sum(o in "WFX" for x in xs for (_, _, _, o) in x["pc"])
    whiffs = sum(o == "W" for x in xs for (_, _, _, o) in x["pc"])
    st_pts = sum(W["steal"][k] * n for k, n in steals.items())
    sb = sum(n for k, n in steals.items() if k.startswith("sb"))
    cs = sum(n for k, n in steals.items() if k.startswith("cs"))
    return dict(
        pa=len(xs), total=sum(x["score"] for x in xs), sb=sb, cs=cs, po=sum(n for k, n in steals.items() if k.startswith("po")),
        steal=600 * st_pts / len(xs), steal_total=st_pts,
        contact=100 * (1 - whiffs / swings) if swings else 0.0,
        power=st.mean(x["end8"] for x in bip) if bip else 0.0,
        results=st.mean(x["result8"] for x in bip if x.get("result8") is not None) if any(x.get("result8") is not None for x in bip) else 0.0,
        clutch=st.mean(x["score"] for x in xs), quality=st.mean(x["quality"] for x in xs),
        discipline=st.mean(x["pitch8"] + (x["end8"] if x["ek"] in NON_CONTACT else 0) for x in xs),
        grind=st.mean(x["long8"] for x in xs), runs=st.mean(x["runner8"] for x in xs),
        gap=sum(x["base"] * x["m"] for x in xs) / sm - base,
        qab=100 * st.mean(x["qab"] for x in xs),
        cons=100 * st.mean(sum(x["qab"] for x in g) >= len(g) / 2 for g in g2) if g2 else 0.0)


def main(yr):
    W = load_weights()
    pas = load(); run_values(pas)
    _, bat = people(yr)
    by = collections.defaultdict(list)
    for x in pas:
        if x["season"] == yr and x["gtype"] == "R":
            by[x["bat"]].append(score_v8(x, W))
    steals = steal_counts(yr)
    rows = {b: line(xs, steals.get(b, {}), W) for b, xs in by.items() if b in bat}
    qual = {b: r for b, r in rows.items() if r["pa"] >= MIN_PA}
    for key, _, _ in CATS:
        vals = sorted(r[key] for r in qual.values())
        n = len(vals)
        for r in rows.values():
            below = sum(v < r[key] for v in vals)
            r[key + "_pct"] = round(100 * below / (n - 1)) if n > 1 else 50
            r[key + "_pct"] = max(0, min(100, r[key + "_pct"]))
            r[key + "_grade"] = grade(r[key + "_pct"])
    for b, r in rows.items():
        r.update(name=bat[b]["name"], ops=bat[b]["ops"])

    tot_q = [r["total"] for r in qual.values()]
    all_pa = [x for xs in by.values() for x in xs]
    print(f"# {yr} season totals\n")
    print(f"- Qualified hitters ({MIN_PA}+ PA): {len(qual)}")
    print(f"- Average season total: {st.mean(tot_q):+.1f}  (median {st.median(tot_q):+.1f})")
    print(f"- Average PA for qualified hitters: {st.mean(r['pa'] for r in qual.values()):.0f}")
    print(f"- Whole league per PA: {st.mean(x['score'] for x in all_pa):+.3f} → per 600 PA: {600 * st.mean(x['score'] for x in all_pa):+.1f}")
    top = sorted(qual.values(), key=lambda r: -r["total"])
    print(f"- Highest total: {top[0]['name']} {top[0]['total']:+.1f}; lowest: {top[-1]['name']} {top[-1]['total']:+.1f}")
    print("\n## Season-total spread (qualified)")
    print("| Percentile | Total |\n|---|---|")
    s = sorted(tot_q)
    for p in (99, 90, 75, 50, 25, 10, 1):
        print(f"| {p}th | {s[min(len(s) - 1, p * len(s) // 100)]:+.1f} |")
    print("\n## Category cut lines (value needed for each grade, qualified hitters)")
    print("| Grade | " + " | ".join(l for _, l, _ in CATS) + " |")
    print("|---|" + "---|" * len(CATS))
    for cut, g in TIERS:
        cells = []
        for key, _, fmt in CATS:
            vals = sorted(r[key] for r in qual.values())
            cells.append(fmt.format(vals[min(len(vals) - 1, round(cut / 100 * (len(vals) - 1)))]))
        print(f"| {g} ({cut}+) | " + " | ".join(cells) + " |")
    with open(os.path.join(ROOT, f"grades-{yr}.json"), "w") as f:
        json.dump(dict(season=yr, min_pa=MIN_PA, cats=[[k, l, fm] for k, l, fm in CATS], tiers=TIERS,
                       avg_total=st.mean(tot_q), players={str(b): r for b, r in rows.items()}), f)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2026)
