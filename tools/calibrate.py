#!/usr/bin/env python3
"""Fit Batters Bible point values to real 2025-2026 run values. Writes data/weights.json.

Usage: python3 tools/calibrate.py            (prints the derivation as markdown)

Process
  1. Run expectancy: average runs scored from each of the 24 out/base states to the end of the inning.
  2. Run value of every PA = change in run expectancy + runs scored on the play.
  3. Ending values = average run value of each result type (contact graded by EV/LA group, not hit/out).
  4. Count values = average ending value of PAs that passed through each count.
  5. Pitch values = how much better/worse the count became than what usually happens on that same
     pitch location in that same count.
  6. Runner values = least-squares fit of PA run value on contact quality + runner outcomes.
  7. Scale: points = runs x S, with S chosen so a walk stays +1.5 points.
  8. Preference bonuses (long AB, first-pitch HR, walk-off) sized from the fitted values.
  9. Clutch = MLB's leverage index per PA (square-rooted, normalised to average exactly 1.0).
"""
import collections, json, os, statistics as st
import numpy as np
from score import raw_season, people, ROOT

SEASONS = (2025, 2026)
SKILL_CONTACT = {"barrel+impact": 4.8, "barrel": 4.0, "hard ld+impact": 3.6, "hard ld": 3.0, "hard fb+impact": 2.4,
                 "hard fb": 2.0, "hard gb": 1.0, "med ld": 1.0, "med": 0.0, "weak ld": 0.0, "weak gb": -0.5,
                 "weak fb": -1.0, "popup": -1.0}


def kind_of(x):
    et, k = x["et"], x["kind"]
    pc = x["pc"]
    last = pc[-1] if pc else None
    if et == "catcher_interf": return "ci"
    if k == "bb": return "bb30" if pc and len(pc) >= 1 and last[0] == 3 and last[1] == 0 else "bb"
    if k == "k":
        if last and last[3] == "C":
            return "k_look_out" if last[2] in ("E", "O", "F") else "k_look_in"
        return "k_swing"
    if k == "bunt": return "bunt_out" if x["batter_out"] else "bunt_hit"
    if k == "fallback":
        h = x.get("hit") or {}
        return f"fb:{h.get('traj')}:{h.get('hard')}"
    return k


def after_count(b, s, o):
    if o == "B": return (b + 1, s)
    if o in ("C", "W"): return (b, s + 1)
    if o == "F": return (b, min(2, s + 1))
    return None


def pitch_cat(b, s, loc, o):
    if loc == "U": return None
    if o == "B": return {"E": "take_ball_edge", "O": "take_ball_out", "F": "take_ball_far"}.get(loc, "ball_in_zone")
    if o == "C": return {"H": "called_heart", "Z": "called_zone"}.get(loc, "called_off_plate")
    if o == "W": return {"H": "whiff_heart", "Z": "whiff_zone", "E": "whiff_edge", "O": "whiff_out", "F": "whiff_far"}[loc]
    if o == "F":
        pre = "foul2_" if s == 2 else "foul_"
        return pre + {"H": "heart", "Z": "zone", "E": "edge", "O": "out", "F": "out"}[loc]
    return None


def load():
    pas = []
    for yr in SEASONS:
        ppl, _ = people(yr)
        wp = {}
        folder = os.path.join(ROOT, "wp", str(yr))
        for x in raw_season(yr):
            if ppl.get(x["pit"], {}).get("pos", "P") not in ("P", "TWP"):
                continue
            if x["pk"] not in wp:
                fn = os.path.join(folder, f"{x['pk']}.json")
                wp[x["pk"]] = {r[0]: r for r in json.load(open(fn))} if os.path.exists(fn) else {}
            r = wp[x["pk"]].get(x["k"])
            x["li"] = r[3] if r and r[3] is not None else None
            x["season"] = yr
            x["ek"] = kind_of(x)
            pas.append(x)
    return pas


def run_values(pas):
    halves = collections.defaultdict(list)
    for x in pas:
        if x["gtype"] == "R":
            halves[(x["pk"], x["inn"], x["top"])].append(x)
    re_runs = collections.defaultdict(list)
    for (pk, inn, top), xs in halves.items():
        xs.sort(key=lambda x: x["k"])
        if inn <= 8:
            final = xs[-1]["bat_after"]
            for x in xs:
                re_runs[(x["outs"], x["bmask"])].append(final - x["bs"])
    RE = {k: st.mean(v) for k, v in re_runs.items()}
    for xs in halves.values():
        for i, x in enumerate(xs):
            here = RE.get((x["outs"], x["bmask"]), 0)
            if i + 1 < len(xs):
                n = xs[i + 1]
                x["rv"] = RE.get((n["outs"], n["bmask"]), 0) - here + (n["bs"] - x["bs"])
            else:
                x["rv"] = -here + (x["bat_after"] - x["bs"])
    return RE


def main():
    pas = load()
    reg = [x for x in pas if x["gtype"] == "R"]
    RE = run_values(pas)
    reg = [x for x in reg if "rv" in x]
    W = dict(seasons=list(SEASONS), pas=len(reg))
    print(f"# Calibration — {len(reg):,} regular-season PAs, {', '.join(map(str, SEASONS))}\n")

    # 1. run expectancy
    print("## Step 1: run expectancy (avg runs from this state to end of inning)")
    print("| Runners | 0 outs | 1 out | 2 outs |\n|---|---|---|---|")
    names = {0: "Empty", 1: "1st", 2: "2nd", 3: "1st & 2nd", 4: "3rd", 5: "1st & 3rd", 6: "2nd & 3rd", 7: "Loaded"}
    for m in range(8):
        print(f"| {names[m]} | " + " | ".join(f"{RE.get((o, m), 0):.2f}" for o in range(3)) + " |")
    W["re"] = {f"{o}-{m}": RE.get((o, m), 0) for o in range(3) for m in range(8)}

    # 3. ending values
    groups = collections.defaultdict(list)
    for x in reg:
        groups[x["ek"]].append(x["rv"])
    EV = {k: st.mean(v) for k, v in groups.items() if len(v) >= 30}
    S = 1.5 / EV["bb"]
    W["scale"] = S
    for x in pas:
        x["E"] = EV.get(x["ek"], 0.0)

    # 4-5. count values and pitch values
    through = collections.defaultdict(list)
    for x in reg:
        for b, s, loc, o in x["pc"]:
            through[(b, s)].append(x["E"])
    CV = {k: st.mean(v) for k, v in through.items()}
    after_by = collections.defaultdict(list)
    rows = []
    for x in reg:
        pc = x["pc"]
        for i, (b, s, loc, o) in enumerate(pc):
            ra = x["E"] if i == len(pc) - 1 else CV.get(after_count(b, s, o), x["E"])
            after_by[(loc, b, s)].append(ra)
            if i < len(pc) - 1:
                rows.append((b, s, loc, o, ra))
    base = {k: st.mean(v) for k, v in after_by.items()}
    cats = collections.defaultdict(list)
    for b, s, loc, o, ra in rows:
        c = pitch_cat(b, s, loc, o)
        if c:
            cats[c].append(ra - base[(loc, b, s)])
    PV = {c: st.mean(v) for c, v in cats.items()}
    W["pitch_measured"] = {c: PV[c] * S for c in PV}
    W["pitch"] = {c: PV[c] * S for c in PV}
    # umpire's call, not the batter's decision: neutral
    for c in ("ball_in_zone", "called_off_plate"):
        W["pitch"][c] = 0.0
    W["pitch_n"] = {c: len(v) for c, v in cats.items()}

    print(f"\n## Step 2-3: ending values (scale: 1 run = {S:.2f} points, so a walk = +1.5)")
    print("| Result | PAs | Runs | Points |\n|---|---|---|---|")
    order = ["barrel+impact", "barrel", "hard ld+impact", "hard ld", "hard fb+impact", "hard fb", "hard gb", "med ld",
             "med", "weak ld", "weak gb", "weak fb", "popup", "bunt_hit", "bunt_out", "bb", "bb30", "ibb", "hbp", "ci",
             "k_swing", "k_look_in", "k_look_out"]
    for k in order + sorted(k for k in EV if k not in order):
        if k in EV:
            print(f"| {k} | {len(groups[k]):,} | {EV[k]:+.3f} | {EV[k] * S:+.2f} |")
    W["ending_measured"] = {k: v * S for k, v in EV.items()}
    W["ending"] = dict(W["ending_measured"])
    # Contact is graded on the repeatable skill (how hard / how well it was hit), not on run value,
    # which rewards luck (bloops, warning-track outs). Tested: predicts next-season OPS .358 vs .275.
    W["ending"].update(SKILL_CONTACT)
    # A walk is earned discipline; getting hit (or catcher's interference) isn't. Keep them below a walk.
    W["ending"]["hbp"] = W["ending"]["ci"] = 1.25

    print("\n## Step 4: count values (avg ending points of PAs that passed through each count)")
    print("| Balls \\ Strikes | 0 | 1 | 2 |\n|---|---|---|---|")
    for b in range(4):
        print(f"| {b} | " + " | ".join(f"{CV.get((b, s), 0) * S:+.2f}" for s in range(3)) + " |")

    print("\n## Step 5: pitch values (count change vs. what usually happens on that pitch, that count)")
    print("| Pitch | Pitches | Points |\n|---|---|---|")
    for c in sorted(PV, key=lambda c: -PV[c]):
        print(f"| {c} | {len(cats[c]):,} | {PV[c] * S:+.3f} |")

    # 6. runner regression
    feats = ["E", "rbi_lt2", "rbi_2", "adv_bases", "str_reg", "str3", "putout"]
    X = np.array([[x[f] for f in feats] + [1.0] for x in reg])
    y = np.array([x["rv"] for x in reg])
    free, *_ = np.linalg.lstsq(X, y, rcond=None)
    # Quality already gives full credit for the contact, so fit only what runners add on top of it
    X2 = X[:, 1:]
    coef, *_ = np.linalg.lstsq(X2, y - X[:, 0], rcond=None)
    W["runner"] = {f: float(c) * S for f, c in zip(feats[1:], coef[:-1])}
    W["runner_free_fit"] = {f: float(c) * S for f, c in zip(feats, free[:-1])}
    print("\n## Step 6: runner values (least-squares fit of what runners add beyond contact quality)")
    print(f"(Unconstrained fit gave contact a weight of {free[0]:.2f} and pushed the rest into RBIs; "
          "fixing contact at 1.0 stops a hit being counted twice.)\n")
    print("| Runner outcome | Runs | Points | Unconstrained fit |\n|---|---|---|---|")
    for f, c, u in zip(feats[1:], coef[:-1], free[1:-1]):
        print(f"| {f} | {c:+.3f} | {c * S:+.2f} | {u * S:+.2f} |")

    # 7b. what each ball-in-play RESULT is worth on its own (net of runner points, so a run isn't counted twice)
    runner_runs = lambda x: sum(c * x[f] for f, c in zip(feats[1:], coef[:-1]))
    res = collections.defaultdict(list)
    for x in reg:
        if x["ek"] in SKILL_CONTACT and x["et"] != "field_error":   # an error doesn't help the batter
            res[x["et"]].append(x["rv"] - runner_runs(x))
    W["result"] = {k: st.mean(v) * S for k, v in res.items() if len(v) >= 50}
    print("\n## Step 7: ball-in-play result values (net of runner points), used for half of the game score")
    print("| Result | Balls | Points |\n|---|---|---|")
    for k, v in sorted(W["result"].items(), key=lambda kv: -kv[1]):
        print(f"| {k} | {len(res[k]):,} | {v:+.2f} |")

    # 8. long AB and first-pitch HR bonuses, sized from the fitted values
    def pre_bonus(x):
        pts = sum(W["pitch"].get(pitch_cat(*p) or "", 0) for p in x["pc"][:-1])
        return pts + W["ending"].get(x["ek"], 0)
    k7 = st.mean(pre_bonus(x) for x in reg if x["ek"].startswith("k_") and x["n"] == 7)
    k8 = st.mean(pre_bonus(x) for x in reg if x["ek"].startswith("k_") and x["n"] == 8)
    b7 = round(-k7 + 0.25, 2)          # a 7-pitch strikeout nets about +0.25: working the count is a good AB
    step = round(max(0.25, -k8 + 0.5 - b7), 2)
    W["long"] = dict(at7=b7, per_extra=step)
    W["fphr"] = round(b7 + step, 2)
    W["walkoff"] = 1.0
    print("\n## Step 8: preference bonuses")
    print(f"Average 7-pitch strikeout before bonus: {k7:+.2f} → 7-pitch bonus {b7:+.2f} (nets about +0.25)")
    print(f"Average 8-pitch strikeout before bonus: {k8:+.2f} → +{step:.2f} per pitch after 7 (8-pitch K nets about +0.5)")
    print(f"First-pitch home run bonus = the 8-pitch bonus = +{W['fphr']:.2f} (attacking rewarded like grinding)")
    fp = [x for x in reg if x["et"] == "home_run" and x["n"] == 1]
    print(f"First-pitch HRs in the data: {len(fp):,} of {sum(x['et'] == 'home_run' for x in reg):,} HRs")

    # 9. clutch from leverage index
    lis = [x["li"] for x in reg if x["li"] is not None]
    norm = st.mean(v ** 0.5 for v in lis)
    W["clutch"] = dict(power=0.5, norm=norm, post=1.25)
    print("\n## Step 9: clutch multiplier = √(leverage index) ÷ league average")
    print(f"PAs with a leverage index: {len(lis):,} of {len(reg):,}. Average √LI = {norm:.3f}\n")
    buck = collections.defaultdict(list)
    for x in reg:
        if x["li"] is None: continue
        inn = "1–6" if x["inn"] <= 6 else "7–8" if x["inn"] <= 8 else "9" if x["inn"] == 9 else "10+"
        sc = "tied" if x["margin"] == 0 else "down 1" if x["margin"] == -1 else "up 1" if x["margin"] == 1 else \
            "within 2–3" if abs(x["margin"]) <= 3 else "4+ either way"
        buck[(inn, sc)].append(x["li"] ** 0.5 / norm)
    print("| Inning | Tied | Down 1 | Up 1 | Within 2–3 | 4+ either way |\n|---|---|---|---|---|---|")
    for inn in ("1–6", "7–8", "9", "10+"):
        print(f"| {inn} | " + " | ".join(f"×{st.mean(buck[(inn, sc)]):.2f}" if buck[(inn, sc)] else "–"
                                         for sc in ("tied", "down 1", "up 1", "within 2–3", "4+ either way")) + " |")
    ms = sorted(x["li"] ** 0.5 / norm for x in reg if x["li"] is not None)
    print(f"\nMultiplier spread: 10th pct ×{ms[len(ms) // 10]:.2f}, median ×{ms[len(ms) // 2]:.2f}, "
          f"90th ×{ms[9 * len(ms) // 10]:.2f}, 99th ×{ms[99 * len(ms) // 100]:.2f}, max ×{ms[-1]:.2f}")

    # 10. base stealing, from the run-expectancy table (one runner, averaged over 0/1/2 outs)
    re_ = lambda o, m: 0.0 if o >= 3 else RE.get((o, m), 0)
    avg = lambda f: st.mean(f(o) for o in range(3))
    SV = {"sb_2b": avg(lambda o: re_(o, 2) - re_(o, 1)), "sb_3b": avg(lambda o: re_(o, 4) - re_(o, 2)),
          "sb_home": avg(lambda o: 1 + re_(o, 0) - re_(o, 4)),
          "cs_2b": avg(lambda o: re_(o + 1, 0) - re_(o, 1)), "cs_3b": avg(lambda o: re_(o + 1, 0) - re_(o, 2)),
          "cs_home": avg(lambda o: re_(o + 1, 0) - re_(o, 4))}
    SV.update(po_1b=SV["cs_2b"], po_2b=SV["cs_3b"], po_3b=SV["cs_home"])
    W["steal"] = {k: v * S for k, v in SV.items()}
    print("\n## Step 10: base stealing (run-expectancy change, averaged over 0/1/2 outs)")
    print("| Event | Runs | Points |\n|---|---|---|")
    for k, v in SV.items():
        print(f"| {k} | {v:+.3f} | {v * S:+.2f} |")
    b = -SV["cs_2b"] / (SV["sb_2b"] - SV["cs_2b"])
    print(f"\nBreak-even success rate stealing 2nd: {100 * b:.0f}%")

    with open(os.path.join(ROOT, "weights.json"), "w") as f:
        json.dump(W, f, indent=1)


if __name__ == "__main__":
    main()
