#!/usr/bin/env python3
"""Score a season with and without the pitcher multiplier and check whether it helps.

Usage: python3 tools/test_season.py 2026
Prints markdown tables. Needs this season and last season downloaded (tools/fetch_pbp.py).
"""
import sys, statistics as st, collections, json, os
from score import score_season, people, ROOT

MIN_PA = 300


def corr(a, b):
    return st.correlation(a, b) if len(a) > 2 else float("nan")


def by_batter(pas):
    out = collections.defaultdict(list)
    for x in pas:
        if x["gtype"] == "R":
            out[x["bat"]].append(x)
    return out


def summary(xs):
    games = collections.defaultdict(list)
    for x in xs:
        games[x["pk"]].append(x)
    g2 = [g for g in games.values() if len(g) >= 2]
    gq = [st.mean(x["quality"] for x in g) for g in g2]
    return dict(pa=len(xs), q=st.mean(x["quality"] for x in xs), raw=st.mean(x["raw"] for x in xs),
                s=st.mean(x["score"] for x in xs), qab=100 * st.mean(x["qab"] for x in xs),
                bad=100 * st.mean(x["bad"] for x in xs),
                cons=100 * st.mean(sum(x["qab"] for x in g) >= len(g) / 2 for g in g2) if g2 else 0,
                spread=st.pstdev(gq) if len(gq) > 1 else 0, opp=st.mean(x["ppct"] for x in xs))


def halves(xs, key):
    """Split a batter's games into odd/even by date, return mean of key in each half."""
    order = sorted({(x["date"], x["pk"]) for x in xs})
    odd = {pk for i, (_, pk) in enumerate(order) if i % 2}
    a = [x[key] for x in xs if x["pk"] in odd]
    b = [x[key] for x in xs if x["pk"] not in odd]
    return st.mean(a), st.mean(b)


def season(season, pitcher):
    pas = score_season(season, pitcher=pitcher)
    return pas, {b: summary(xs) for b, xs in by_batter(pas).items()}, by_batter(pas)


def main(yr):
    _, bat = people(yr)
    _, bat_prev = people(yr - 1)
    on, sum_on, raw_on = season(yr, True)
    off, sum_off, raw_off = season(yr, False)
    reg = [x for x in on if x["gtype"] == "R"]
    qual = [b for b, s in sum_on.items() if s["pa"] >= MIN_PA and b in bat]
    name = lambda b: bat.get(b, {}).get("name", str(b))
    team = lambda b: bat.get(b, {}).get("team", "")

    print(f"# {yr} test — {len(reg):,} regular-season PAs, {len(qual)} batters with {MIN_PA}+ PA\n")

    # league scale
    print("## League per-PA averages")
    print("| | Pitch | Ending | Long AB | Raw quality | Quality | Runner | Clutch mult | PA score |")
    print("|---|---|---|---|---|---|---|---|---|")
    m = lambda k, xs: st.mean(x[k] for x in xs)
    print(f"| With pitcher mult | {m('pitch', reg):.2f} | {m('end', reg):.2f} | {m('long', reg):.2f} | {m('raw', reg):.2f} "
          f"| {m('quality', reg):.2f} | {m('run', reg):.2f} | ×{m('cm', reg):.2f} | {m('score', reg):.2f} |")
    regoff = [x for x in off if x["gtype"] == "R"]
    print(f"| Without | | | | | {m('quality', regoff):.2f} | | | {m('score', regoff):.2f} |\n")

    # pitcher multiplier distribution
    pm = [x["pm"] for x in reg]
    buckets = collections.Counter()
    for v in pm:
        buckets["×0.90–0.95" if v < 0.95 else "×0.95–1.00" if v < 1.0 else "×1.00" if v == 1.0
                else "×1.00–1.10" if v <= 1.10 else "×1.10–1.20"] += 1
    print("## Pitcher multiplier — how often each range came up")
    print("| Range | Share of PAs |\n|---|---|")
    for k in ("×0.90–0.95", "×0.95–1.00", "×1.00", "×1.00–1.10", "×1.10–1.20"):
        print(f"| {k} | {100 * buckets[k] / len(pm):.1f}% |")
    capped = 100 * st.mean(x["capped"] for x in reg)
    print(f"\nPAs where pitcher × clutch hit the inning cap: {capped:.2f}%\n")

    # clutch distribution
    cb = collections.Counter()
    for x in reg:
        v = x["cm"]
        cb["≤×0.9" if v < 0.95 else "×0.95–1.05" if v <= 1.05 else "×1.05–1.3" if v <= 1.3
           else "×1.3–1.6" if v <= 1.6 else "×1.6–2.0" if v <= 2.0 else ">×2.0"] += 1
    print("## Clutch multiplier — how often each range came up")
    print("| Range | Share of PAs |\n|---|---|")
    for k in ("≤×0.9", "×0.95–1.05", "×1.05–1.3", "×1.3–1.6", "×1.6–2.0", ">×2.0"):
        print(f"| {k} | {100 * cb[k] / len(reg):.1f}% |")
    print()

    # reliability: odd vs even games
    print(f"## Does it measure something real? ({MIN_PA}+ PA)")
    print("| Metric | Odd vs even games (reliability) | vs same-season OPS |")
    print("|---|---|---|")
    ops = [bat[b]["ops"] for b in qual]
    for label, src, key in (("Quality, with pitcher mult", raw_on, "quality"), ("Quality, without", raw_off, "quality"),
                            ("Clutch score, with pitcher mult", raw_on, "score"), ("Clutch score, without", raw_off, "score")):
        h = [halves(src[b], key) for b in qual]
        r_half = corr([a for a, _ in h], [b for _, b in h])
        val = [st.mean(x[key] for x in src[b]) for b in qual]
        print(f"| {label} | {r_half:.3f} | {corr(val, ops):.3f} |")
    h = None
    print()

    # prediction: last season -> this season OPS
    prev_dir = os.path.join(ROOT, "pbp", str(yr - 1))
    if os.path.isdir(prev_dir) and bat_prev:
        _, ps_on, _ = season(yr - 1, True)
        _, ps_off, _ = season(yr - 1, False)
        both = [b for b in qual if b in ps_on and ps_on[b]["pa"] >= MIN_PA and b in bat_prev]
        nxt = [bat[b]["ops"] for b in both]
        print(f"## Does {yr - 1} predict {yr} OPS? ({len(both)} batters, {MIN_PA}+ PA both years)")
        print(f"| {yr - 1} stat | Correlation with {yr} OPS |\n|---|---|")
        rows = [(f"{yr - 1} OPS (baseline)", [bat_prev[b]["ops"] for b in both]),
                ("Quality, with pitcher mult", [ps_on[b]["q"] for b in both]),
                ("Quality, without", [ps_off[b]["q"] for b in both]),
                ("Clutch score, with pitcher mult", [ps_on[b]["s"] for b in both]),
                ("Clutch score, without", [ps_off[b]["s"] for b in both]),
                ("QAB%", [ps_on[b]["qab"] for b in both])]
        for label, v in sorted(rows, key=lambda r: -corr(r[1], nxt)):
            print(f"| {label} | {corr(v, nxt):.3f} |")
        print()

    # movers
    rank = lambda sm: {b: i + 1 for i, b in enumerate(sorted(qual, key=lambda b: -sm[b]["s"]))}
    r_on, r_off = rank(sum_on), rank(sum_off)
    mv = sorted(qual, key=lambda b: r_off[b] - r_on[b])
    print("## Biggest rank changes from the pitcher multiplier")
    print("| Player | Team | Rank without | Rank with | Avg opposing pitcher percentile |\n|---|---|---|---|---|")
    for b in mv[-6:][::-1] + mv[:6]:
        print(f"| {name(b)} | {team(b)} | {r_off[b]} | {r_on[b]} | {100 * sum_on[b]['opp']:.0f} |")
    print(f"\nRank correlation with vs without: {corr([r_on[b] for b in qual], [r_off[b] for b in qual]):.3f}\n")

    # leaderboard
    print(f"## {yr} top 20 (with pitcher multiplier)")
    print("| # | Player | Team | PA | Clutch/PA | Quality/PA | Clutch gap | QAB% | Consistency | OPS |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for i, b in enumerate(sorted(qual, key=lambda b: -sum_on[b]["s"])[:20]):
        s = sum_on[b]
        print(f"| {i + 1} | {name(b)} | {team(b)} | {s['pa']} | {s['s']:.2f} | {s['q']:.2f} | {s['s'] - s['q']:+.2f} "
              f"| {s['qab']:.0f}% | {s['cons']:.0f}% | {bat[b]['ops']:.3f} |")
    print()
    print("## Biggest single PAs")
    print("| Player | Date | Inn | Event | Score | Clutch × | Pitcher × |\n|---|---|---|---|---|---|---|")
    for x in sorted(on, key=lambda x: -x["score"])[:8]:
        print(f"| {name(x['bat'])} | {x['date']} | {x['inn']} | {x['et']} ({x['kind']}) | {x['score']:.2f} | ×{x['cm']:.2f} | ×{x['pm']:.2f} |")
    with open(os.path.join(ROOT, f"test-{yr}.json"), "w") as f:
        json.dump({str(b): dict(sum_on[b], name=name(b), team=team(b), ops=bat[b]["ops"], q_off=sum_off[b]["q"],
                                s_off=sum_off[b]["s"]) for b in qual}, f)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2026)
