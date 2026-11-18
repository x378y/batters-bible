#!/usr/bin/env python3
"""Test the calibrated (v8) scoring on 2025-2026. Usage: python3 tools/test_v8.py"""
import collections, statistics as st, json, os
from calibrate import load, run_values
from score import load_weights, score_v8, people, ROOT

MIN_PA = 300
corr = lambda a, b: st.correlation(a, b)


def summarize(xs):
    games = collections.defaultdict(list)
    for x in xs:
        games[x["pk"]].append(x)
    g2 = [g for g in games.values() if len(g) >= 2]
    sm = sum(x["m"] for x in xs)
    base = st.mean(x["base"] for x in xs)
    return dict(pa=len(xs), q=st.mean(x["quality"] for x in xs), base=base, s=st.mean(x["score"] for x in xs),
                gap=sum(x["base"] * x["m"] for x in xs) / sm - base, qab=100 * st.mean(x["qab"] for x in xs),
                cons=100 * st.mean(sum(x["qab"] for x in g) >= len(g) / 2 for g in g2) if g2 else 0,
                hi=st.mean(x["base"] for x in xs if x["m"] >= 1.5) if any(x["m"] >= 1.5 for x in xs) else None,
                nhi=sum(x["m"] >= 1.5 for x in xs))


def split(xs):
    order = sorted({(x["date"], x["pk"]) for x in xs})
    odd = {pk for i, (_, pk) in enumerate(order) if i % 2}
    return [x for x in xs if x["pk"] in odd], [x for x in xs if x["pk"] not in odd]


def main():
    W = load_weights()
    pas = load()
    run_values(pas)
    for x in pas:
        score_v8(x, W)
    reg = [x for x in pas if x["gtype"] == "R"]
    by = {yr: collections.defaultdict(list) for yr in (2025, 2026)}
    for x in reg:
        by[x["season"]][x["bat"]].append(x)
    bat = {yr: people(yr)[1] for yr in (2025, 2026)}
    summ = {yr: {b: summarize(xs) for b, xs in by[yr].items()} for yr in by}
    q26 = [b for b, s in summ[2026].items() if s["pa"] >= MIN_PA and b in bat[2026]]
    name = lambda b: bat[2026].get(b, {}).get("name") or bat[2025].get(b, {}).get("name", str(b))

    r26 = [x for x in reg if x["season"] == 2026]
    m = lambda k, xs: st.mean(x[k] for x in xs)
    print("# v8 test\n\n## League per-PA averages, 2026")
    print("| Pitch | Ending | Long AB | 1st-pitch HR | Quality | Runner | Base | Clutch mult | Clutch score |")
    print("|---|---|---|---|---|---|---|---|---|")
    print(f"| {m('pitch8', r26):+.2f} | {m('end8', r26):+.2f} | {m('long8', r26):+.2f} | {m('fphr8', r26):+.3f} | "
          f"{m('quality', r26):+.2f} | {m('runner8', r26):+.2f} | {m('base', r26):+.2f} | ×{m('m', r26):.2f} | {m('score', r26):+.2f} |")

    print(f"\n## Reliability (odd vs even games, 2026, {len(q26)} batters {MIN_PA}+ PA) and match with 2026 OPS")
    print("| Metric | Odd vs even | vs 2026 OPS |\n|---|---|---|")
    ops = [bat[2026][b]["ops"] for b in q26]
    for label, key in (("Quality", "q"), ("Quality + runners", "base"), ("Clutch score", "s"), ("Clutch gap", "gap")):
        halves = [tuple(summarize(h)[key] for h in split(by[2026][b])) for b in q26]
        print(f"| {label} | {corr([a for a, _ in halves], [c for _, c in halves]):.3f} | "
              f"{corr([summ[2026][b][key] for b in q26], ops):.3f} |")

    both = [b for b in q26 if summ[2025].get(b, {}).get("pa", 0) >= MIN_PA and b in bat[2025]]
    nxt = [bat[2026][b]["ops"] for b in both]
    print(f"\n## Does 2025 predict 2026 OPS? ({len(both)} batters, {MIN_PA}+ PA both years)")
    print("| 2025 stat | Correlation |\n|---|---|")
    rows = [("2025 OPS (baseline)", [bat[2025][b]["ops"] for b in both]),
            ("Quality (v8)", [summ[2025][b]["q"] for b in both]),
            ("Quality + runners (v8)", [summ[2025][b]["base"] for b in both]),
            ("Clutch score (v8)", [summ[2025][b]["s"] for b in both])]
    for label, v in sorted(rows, key=lambda r: -corr(r[1], nxt)):
        print(f"| {label} | {corr(v, nxt):.3f} |")
    print("| *v7 Quality (old guessed values)* | *0.342* |\n| *v7 Clutch score* | *0.368* |")
    gy = corr([summ[2025][b]["gap"] for b in both], [summ[2026][b]["gap"] for b in both])
    print(f"\nClutch gap, 2025 vs 2026 for the same players: {gy:.3f}")

    print("\n## 2026 top 20 by Clutch score")
    print("| # | Player | PA | Clutch/PA | Quality/PA | +Runners/PA | Clutch gap | High-leverage PAs | QAB% | Consistency | OPS |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for i, b in enumerate(sorted(q26, key=lambda b: -summ[2026][b]["s"])[:20], 1):
        s = summ[2026][b]
        print(f"| {i} | {name(b)} | {s['pa']} | {s['s']:+.2f} | {s['q']:+.2f} | {s['base']:+.2f} | {s['gap']:+.2f} | "
              f"{s['nhi']} | {s['qab']:.0f}% | {s['cons']:.0f}% | {bat[2026][b]['ops']:.3f} |")

    gaps = sorted(q26, key=lambda b: -summ[2026][b]["gap"])
    print("\n## 2026 most and least clutch (Clutch gap)")
    print("| Player | Clutch gap | Score in high-leverage PAs (×1.5+) | Overall | High-leverage PAs |\n|---|---|---|---|---|")
    for b in gaps[:8] + gaps[-8:]:
        s = summ[2026][b]
        print(f"| {name(b)} | {s['gap']:+.2f} | {s['hi']:+.2f} | {s['base']:+.2f} | {s['nhi']} |")

    print("\n## Biggest single PAs, 2026 (incl. postseason)")
    print("| Player | Date | Inn | Event | Base | × Clutch | Score |\n|---|---|---|---|---|---|---|")
    for x in sorted((x for x in pas if x["season"] == 2026), key=lambda x: -x["score"])[:8]:
        print(f"| {name(x['bat'])} | {x['date']} | {x['inn']} | {x['et']} ({x['ek']}) | {x['base']:+.2f} | ×{x['m']:.2f} | {x['score']:+.2f} |")


if __name__ == "__main__":
    main()
