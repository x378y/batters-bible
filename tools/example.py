#!/usr/bin/env python3
"""Show how one batter's score is built: season line, best game, and one PA pitch by pitch.

Usage: python3 tools/example.py "Yordan Alvarez" [2026] [YYYY-MM-DD]
"""
import collections, statistics as st, sys
from calibrate import load, run_values, pitch_cat
from score import load_weights, score_v8, people
from fetch_pbp import get, API

LOC = {"H": "heart", "Z": "in zone", "E": "just off edge", "O": "outside", "F": "way outside", "U": "?"}
OUT = {"B": "ball (taken)", "C": "called strike", "W": "whiff", "F": "foul", "X": "in play"}
BASES = {0: "empty", 1: "1st", 2: "2nd", 3: "1st & 2nd", 4: "3rd", 5: "1st & 3rd", 6: "2nd & 3rd", 7: "loaded"}


def main(name, yr=2026, day=None):
    W = load_weights()
    pas = load(); run_values(pas)
    _, bat = people(yr)
    pid = next(b for b, v in bat.items() if v["name"].lower() == name.lower())
    mine = [score_v8(x, W) for x in pas if x["bat"] == pid and x["season"] == yr]
    reg = [x for x in mine if x["gtype"] == "R"]
    teams = {t["id"]: t["abbreviation"] for t in get(f"{API}/teams?sportId=1&season={yr}")["teams"]}
    import json, os
    from score import ROOT
    games = {g["pk"]: g for g in json.load(open(os.path.join(ROOT, "pbp", str(yr), "games.json")))}

    sm = sum(x["m"] for x in reg)
    base = st.mean(x["base"] for x in reg)
    print(f"# {bat[pid]['name']}, {yr}\n")
    print("| PA | Clutch/PA | Quality/PA | Pitch | Ending | Long AB | 1st-pitch HR | Runners | Clutch gap | QAB% | OPS |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    m = lambda k: st.mean(x[k] for x in reg)
    print(f"| {len(reg)} | {m('score'):+.2f} | {m('quality'):+.2f} | {m('pitch8'):+.2f} | {m('end8'):+.2f} | {m('long8'):+.2f} | "
          f"{m('fphr8'):+.3f} | {m('runner8'):+.2f} | {sum(x['base'] * x['m'] for x in reg) / sm - base:+.2f} | "
          f"{100 * m('qab'):.0f}% | {bat[pid]['ops']:.3f} |")
    tot = collections.Counter()
    for x in reg:
        tot["Pitch points"] += x["pitch8"]; tot["Ending points"] += x["end8"]; tot["Long-AB bonus"] += x["long8"]
        tot["First-pitch HR bonus"] += x["fphr8"]; tot["Runner points"] += x["runner8"]; tot["Walk-offs"] += x["base"] - x["quality"] - x["runner8"]
        tot["Clutch adjustment"] += x["score"] - x["base"]
    print("\n**Season totals**\n\n| Part | Total points |\n|---|---|")
    for k, v in tot.items():
        print(f"| {k} | {v:+.1f} |")
    print(f"| **Clutch score total** | **{sum(x['score'] for x in reg):+.1f}** |")

    bygame = collections.defaultdict(list)
    for x in reg:
        bygame[x["pk"]].append(x)
    pk = next(p for p, xs in bygame.items() if xs[0]["date"] == day) if day else max(bygame, key=lambda p: sum(x["score"] for x in bygame[p]))
    xs = sorted(bygame[pk], key=lambda x: x["k"])
    g = games[pk]
    home = not xs[0]["top"]
    opp = teams.get(g["away"] if home else g["home"], "?")
    print(f"\n## Game: {g['date']} {'vs' if home else 'at'} {opp} — game score {sum(x['score'] for x in xs):+.2f}\n")
    print("| Inn | Situation | Pitches | Result | Pitch | Ending | Bonus | Runners | Base | × Clutch | Score |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for x in xs:
        sit = f"{x['outs']} out, {BASES[x['bmask']]}, {'tied' if x['margin'] == 0 else ('up ' if x['margin'] > 0 else 'down ') + str(abs(x['margin']))}"
        print(f"| {x['inn']} | {sit} | {x['n']} | {x['et'].replace('_', ' ')} ({x['ek']}) | {x['pitch8']:+.2f} | {x['end8']:+.2f} | "
              f"{x['long8'] + x['fphr8']:+.2f} | {x['runner8']:+.2f} | {x['base']:+.2f} | ×{x['m']:.2f} | {x['score']:+.2f} |")

    big = max(xs, key=lambda x: x["score"])
    print(f"\n## Biggest PA of that game, pitch by pitch (inning {big['inn']})\n")
    print("| # | Count | Location | What he did | Points |\n|---|---|---|---|---|")
    for i, (b, s, loc, o) in enumerate(big["pc"], 1):
        last = i == len(big["pc"])
        pts = "ending ↓" if last else f"{W['pitch'].get(pitch_cat(b, s, loc, o) or '', 0):+.2f}"
        print(f"| {i} | {b}-{s} | {LOC[loc]} | {OUT[o]} | {pts} |")
    h = big.get("hit") or {}
    if h:
        print(f"\nBall in play: {h.get('ev')} mph, {h.get('la')}° → **{big['ek']}**")
    f = big
    print(f"\n| Part | Points |\n|---|---|")
    print(f"| Pitch points (pitches before the last) | {f['pitch8']:+.2f} |")
    print(f"| Ending: {f['ek']} | {f['end8']:+.2f} |")
    if f["long8"]: print(f"| Long at-bat ({f['n']} pitches) | {f['long8']:+.2f} |")
    if f["fphr8"]: print(f"| First-pitch home run | {f['fphr8']:+.2f} |")
    r = W["runner"]
    for k, label in (("rbi_lt2", "RBI, 0–1 outs"), ("rbi_2", "RBI, 2 outs"), ("adv_bases", "Bases runners moved up"),
                     ("str_reg", "Runners stranded"), ("str3", "Stranded on 3rd, <2 outs"), ("putout", "Runner put out")):
        if f[k]: print(f"| {label} ({f[k]} × {r[k]:+.2f}) | {f[k] * r[k]:+.2f} |")
    if f["base"] - f["quality"] - f["runner8"]: print(f"| Walk-off | {f['base'] - f['quality'] - f['runner8']:+.2f} |")
    print(f"| **Base** | **{f['base']:+.2f}** |")
    print(f"| Clutch multiplier (leverage index {f['li']}) | ×{f['m']:.2f} |")
    print(f"| **Clutch score** | **{f['score']:+.2f}** |")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0] if a else "Yordan Alvarez", int(a[1]) if len(a) > 1 else 2026, a[2] if len(a) > 2 else None)
