#!/usr/bin/env python3
"""Batters Bible scoring engine. Implements SCORING.md (draft v7).

    from score import score_season
    pas = score_season(2026)               # list of scored plate appearances
    pas = score_season(2026, pitcher=False) # same, pitcher multiplier turned off

Reads data/pbp/<season>/*.json.gz written by tools/fetch_pbp.py.
"""
import gzip, json, math, os, glob, statistics as st

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

PA_EVENTS = {
    "single", "double", "triple", "home_run", "walk", "intent_walk", "hit_by_pitch", "strikeout",
    "strikeout_double_play", "strikeout_triple_play", "field_out", "force_out", "grounded_into_double_play",
    "grounded_into_triple_play", "double_play", "triple_play", "fielders_choice", "fielders_choice_out",
    "field_error", "sac_fly", "sac_fly_double_play", "sac_bunt", "sac_bunt_double_play", "catcher_interf",
}
K_EVENTS = {"strikeout", "strikeout_double_play", "strikeout_triple_play"}
OUT_EVENTS = K_EVENTS | {"field_out", "force_out", "grounded_into_double_play", "grounded_into_triple_play",
                         "double_play", "triple_play", "fielders_choice_out", "sac_fly", "sac_fly_double_play",
                         "sac_bunt", "sac_bunt_double_play"}
# Runner movements the batter caused (everything else - steals, wild pitches, pickoffs, errors - isn't his)
BATTER_WHY = {None, "r_adv_force", "r_adv_play", "r_adv_throw", "r_force_out", "r_doubled_off",
              "r_runner_out", "r_rundown"}
BASE = {"1B": 1, "2B": 2, "3B": 3, "score": 4}
WHIFF = {"S", "W", "M", "Q"}
FOUL = {"F", "T", "L", "R", "O"}
TAKEN_BALL = {"B", "*B", "P"}

HALF_W = 0.83        # half plate width + ball radius, feet
BALL_R = 0.12
EDGE = 0.25          # "just off the edge" = within 3 inches


# ---------- pitch location ----------
def where(p):
    """Return (distance outside zone in ft, in heart?) or (None, False) if location is missing."""
    px, pz, top, bot = p.get("px"), p.get("pz"), p.get("top"), p.get("bot")
    if px is None or pz is None or not top or not bot:
        return None, False
    dx = abs(px) - HALF_W
    dz = max((bot - BALL_R) - pz, pz - (top + BALL_R))
    dist = max(dx, dz, 0.0)
    mid, half_h = (top + bot) / 2, (top - bot) / 2
    heart = abs(px) <= 0.708 * 0.67 and abs(pz - mid) <= half_h * 0.67
    return dist, heart


def chase_cost(dist):
    if dist <= EDGE: return -0.2
    if dist <= 0.5: return -0.3
    if dist <= 1.0: return -0.4
    return -0.5


def loc_class(p):
    dist, heart = where(p)
    if dist is None: return "U"
    if heart: return "H"
    if dist == 0: return "Z"
    if dist <= EDGE: return "E"
    return "O" if dist <= 1.0 else "F"


def outcome_class(p):
    code = p.get("code")
    if p.get("ip"): return "X"
    if code in WHIFF: return "W"
    if code in FOUL: return "F"
    if code == "C": return "C"
    if p.get("b") or code in TAKEN_BALL or code == "H": return "B"
    return "C" if p.get("s") else "B"


def pitch_classes(pitches):
    """[balls, strikes, location class, outcome class] for every pitch, count = before the pitch."""
    out, prev = [], [0, 0]
    for p in pitches:
        out.append([prev[0], prev[1], loc_class(p), outcome_class(p)])
        prev = p["cnt"] or prev
    return out


# ---------- section 1: pitches before the last one ----------
def pitch_points(pitches, intentional):
    pts, detail = 0.0, dict(good=0, take=0, chase=0, heart=0)
    if intentional:
        return pts, detail
    prev = [0, 0]
    for p in pitches[:-1]:
        balls, strikes = prev
        prev = p["cnt"] or prev
        code = p.get("code")
        dist, heart = where(p)
        swing_miss, foul = code in WHIFF, code in FOUL
        mistake = 0.0
        if dist is not None:
            outside = dist > 0
            if (swing_miss or foul) and outside and strikes < 2:
                if not (foul and dist <= EDGE):
                    mistake = chase_cost(dist); detail["chase"] += 1
            elif heart and ((code == "C" and strikes < 2) or (swing_miss and strikes < 2) or foul):
                mistake = -0.3; detail["heart"] += 1
        if mistake:
            pts += mistake
            continue
        pts += 0.1; detail["good"] += 1
        if code in TAKEN_BALL and balls < 3:
            pts += 0.3 if (dist is not None and 0 < dist <= EDGE) else 0.2
            detail["take"] += 1
    return pts, detail


# ---------- section 2: how it ends ----------
def barrel(ev, la):
    if ev < 98: return False
    return max(8, 26 - (ev - 98)) <= la <= min(50, 30 + (ev - 98) * 1.2)


def pulled(hit, side):
    hx, hy = hit.get("hx"), hit.get("hy")
    if hx is None or hy is None or side not in ("L", "R"):
        return False
    ang = math.degrees(math.atan2(hx - 125.42, 198.27 - hy))
    return ang <= -15 if side == "R" else ang >= 15


FALLBACK = {("line_drive", "hard"): 3, ("fly_ball", "hard"): 2, ("ground_ball", "hard"): 1,
            ("line_drive", "medium"): 1, ("ground_ball", "medium"): 0, ("fly_ball", "medium"): 0,
            ("ground_ball", "soft"): -0.5, ("fly_ball", "soft"): -1, ("line_drive", "soft"): 0}


def contact(hit, side):
    ev, la = hit.get("ev"), hit.get("la")
    if ev is None or la is None:
        if hit.get("traj") == "popup": return -1.0, "popup"
        return float(FALLBACK.get((hit.get("traj"), hit.get("hard")), 0)), "fallback"
    if la > 50: return -1.0, "popup"
    if barrel(ev, la): g, kind = 4.0, "barrel"
    elif ev >= 95: g, kind = (1.0, "hard gb") if la < 10 else (3.0, "hard ld") if la < 25 else (2.0, "hard fb")
    elif ev >= 80: g, kind = (1.0, "med ld") if 10 <= la < 25 else (0.0, "med")
    else: g, kind = (-0.5, "weak gb") if la < 10 else (0.0, "weak ld") if la < 25 else (-1.0, "weak fb")
    if g > 0 and ev >= 95 and 15 <= la <= 35 and pulled(hit, side):
        g *= 1.2; kind += "+impact"
    return g, kind


def ending_points(play, pitches, batter_out):
    et = play["et"]
    n = len(pitches)
    last = pitches[-1] if pitches else {}
    pre = pitches[-2]["cnt"] if n >= 2 and pitches[-2].get("cnt") else [0, 0]
    if et == "intent_walk": return 1.0, "ibb"
    if et == "walk": return (1.0 if pre == [3, 0] else 1.5), "bb"
    if et in ("hit_by_pitch", "catcher_interf"): return 1.2, "hbp"
    if et in K_EVENTS:
        dist, _ = where(last)
        if last.get("code") == "C":
            pts = -0.75 if (dist or 0) > 0 else -1.5
        else:
            pts = -1.5 - min(1.0, dist or 0.0)
        if n >= 7: pts /= 2
        return pts, "k"
    hit = last.get("hit")
    bunt = et in ("sac_bunt", "sac_bunt_double_play") or (hit and str(hit.get("traj", "")).startswith("bunt"))
    if bunt: return (0.0 if batter_out else 1.0), "bunt"
    if hit: return contact(hit, play.get("side"))
    return 0.0, "none"


def long_ab(n):
    return 0.75 + 0.25 * (n - 7) if n >= 7 else 0.0


# ---------- section 7: clutch ----------
def clutch(inn, gtype, margin, bases):
    on = len(bases)
    deficit = -margin
    if margin <= 0 and deficit <= on + 1: sc = 1.25
    elif abs(margin) <= 2: sc = 1.10
    elif abs(margin) >= 5: sc = 0.80
    else: sc = 1.0
    ic = 1.5 if inn >= 12 else 1.4 if inn >= 10 else 1.3 if inn == 9 else 1.15 if inn >= 7 else 1.0
    rc = 1.2 if on == 3 else 1.1 if ("2B" in bases or "3B" in bases) else 1.0
    gc = 1.25 if gtype != "R" else 1.0
    cap = 2.5 if inn >= 12 else 2.4 if inn >= 10 else 2.3 if inn == 9 else 2.2 if inn == 8 else 2.1 if inn == 7 else 2.0
    return min(cap, max(0.8, sc * ic * rc * gc)), cap


# ---------- walk through one game ----------
def game_pas(g):
    game, plays = g["game"], g["plays"]
    out, half, bases, outs, score, auto = [], None, {}, 0, [0, 0], set()

    AUTO = -1  # placeholder for the automatic runner until a play names him

    def resolve(seg, bases):
        # the API doesn't list the automatic runner until he moves; swap the placeholder for his real id
        if seg["start"] == "2B" and bases.get("2B") == AUTO and seg["id"] not in bases.values():
            bases["2B"] = seg["id"]; auto.add(seg["id"])

    def apply(seg, bases):
        resolve(seg, bases)
        rid = seg["id"]
        for b in [b for b, r in bases.items() if r == rid]:
            del bases[b]
        if not seg["out"] and seg["end"] in ("1B", "2B", "3B"):
            bases[seg["end"]] = rid

    for k, p in enumerate(plays):
        if (p["inn"], p["top"]) != half:
            half, bases, outs, auto = (p["inn"], p["top"]), {}, 0, {AUTO}
            if game["type"] == "R" and p["inn"] >= 10:
                bases["2B"] = AUTO
        pitches = p["pitches"]
        F = pitches[-1]["i"] if pitches else None
        pre_segs = [s for s in p["runners"] if F is not None and s["pi"] is not None and s["pi"] < F]
        fin_segs = [s for s in p["runners"] if s not in pre_segs]
        for s in fin_segs:
            resolve(s, bases)
        runs_pre = 0
        for s in pre_segs:
            apply(s, bases)
            if s["out"]: outs += 1
            elif s["end"] == "score": runs_pre += 1
        bat_home = not p["top"]
        bs, os_ = (score[1], score[0]) if bat_home else (score[0], score[1])
        bs += runs_pre
        snap, outs_before = dict(bases), outs

        if p["et"] in PA_EVENTS and p["bat"] is not None:
            bseg = [s for s in fin_segs if s["id"] == p["bat"]]
            if any(s["out"] for s in bseg): batter_out = True
            elif any(s["end"] for s in bseg): batter_out = False
            else: batter_out = p["et"] in OUT_EVENTS
            # runner points
            on_base = {rid: b for b, rid in snap.items()}
            adv, put_out, own_out = {}, set(), set()
            for s in fin_segs:
                rid = s["id"]
                if rid not in on_base or s["start"] is None:
                    continue
                mine = s["why"] in BATTER_WHY
                if s["out"]:
                    (put_out if mine else own_out).add(rid)
                elif mine and s["end"] in BASE and s["start"] in BASE:
                    adv[rid] = adv.get(rid, 0) + BASE[s["end"]] - BASE[s["start"]]
            rbi = p.get("rbi") or 0
            run_pts = rbi * (0.75 if outs_before == 2 else 0.5) + 0.25 * sum(max(0, v) for v in adv.values())
            stranded, str3, str_reg = 0, 0, 0
            for rid, b in on_base.items():
                if rid in put_out:
                    run_pts -= 0.25; stranded += 1
                elif batter_out and rid not in auto and adv.get(rid, 0) <= 0 and rid not in own_out:
                    run_pts -= 0.5 if (b == "3B" and outs_before < 2) else 0.25; stranded += 1
                    if b == "3B" and outs_before < 2: str3 += 1
                    else: str_reg += 1
            facts = dict(rbi_lt2=rbi if outs_before < 2 else 0, rbi_2=rbi if outs_before == 2 else 0,
                         adv_bases=sum(max(0, v) for v in adv.values()), str3=str3, str_reg=str_reg,
                         putout=len(put_out), pc=pitch_classes(pitches),
                         hit=(pitches[-1].get("hit") if pitches else None), side=p.get("side"),
                         bmask=(1 if "1B" in snap else 0) | (2 if "2B" in snap else 0) | (4 if "3B" in snap else 0),
                         bs=bs, bat_after=(p["h"] if bat_home else p["a"]) or 0, k=k, top=p["top"],
                         walkoff_flag=None)
            pp, det = pitch_points(pitches, p["et"] == "intent_walk")
            ep, kind = ending_points(p, pitches, batter_out)
            la = long_ab(len(pitches))
            # walk-off
            a_after, h_after = p["a"] or 0, p["h"] or 0
            walkoff = 1.0 if (bat_home and p["inn"] >= 9 and k == len(plays) - 1 and h_after > a_after
                              and score[1] <= score[0] and p["et"] not in OUT_EVENTS - {"sac_fly"}) else 0.0
            cm, cap = clutch(p["inn"], game["type"], bs - os_, snap)
            out.append(dict(pk=game["pk"], date=game["date"], gtype=game["type"], bat=p["bat"], pit=p["pit"],
                            et=p["et"], kind=kind, n=len(pitches), pitch=pp, end=ep, long=la, raw=pp + ep + la,
                            run=run_pts, walkoff=walkoff, cm=cm, cap=cap, outs=outs_before, on=len(snap),
                            batter_out=batter_out, adv=sum(adv.values()), stranded=stranded, inn=p["inn"],
                            margin=bs - os_, **det, **facts))
        for s in fin_segs:
            apply(s, bases)
        outs = p["outs"] if p["outs"] is not None else outs
        score = [p["a"] if p["a"] is not None else score[0], p["h"] if p["h"] is not None else score[1]]
    return out


def raw_season(season):
    cache = os.path.join(ROOT, f"raw-{season}.json.gz")
    if os.path.exists(cache):
        with gzip.open(cache, "rt") as f:
            return json.load(f)
    pas = []
    for fn in sorted(glob.glob(os.path.join(ROOT, "pbp", str(season), "*.json.gz"))):
        with gzip.open(fn, "rt") as f:
            pas.extend(game_pas(json.load(f)))
    with gzip.open(cache, "wt") as f:
        json.dump(pas, f, separators=(",", ":"))
    return pas


def people(season):
    fn = os.path.join(ROOT, f"season-{season}.json")
    if not os.path.exists(fn):
        return {}, {}
    with open(fn) as f:
        m = json.load(f)
    return {int(k): v for k, v in m["people"].items()}, {int(k): v for k, v in m["batting"].items()}


def pitcher_percentiles(pas):
    """Section 3: regressed quality allowed -> percentile (1 = best pitcher)."""
    lg = st.mean(x["raw"] for x in pas)
    tot = {}
    for x in pas:
        t = tot.setdefault(x["pit"], [0, 0.0]); t[0] += 1; t[1] += x["raw"]
    rating = {pid: ((s + 200 * lg) / (n + 200), n) for pid, (n, s) in tot.items()}
    import bisect
    elig = sorted(r for r, n in rating.values() if n >= 100)  # ascending: tough pitchers first
    N = len(elig)
    pct = {}
    for pid, (r, n) in rating.items():
        # share of eligible pitchers who allow better at-bats than he does (1 = best pitcher)
        pct[pid] = 0.5 if n < 100 or N < 2 else (N - bisect.bisect_right(elig, r)) / (N - 1)
    return pct, rating, lg


def pitcher_mult(raw, p):
    if raw > 0:
        return 1 + 0.2 * (p - 0.5) if p < 0.5 else 1 + 0.4 * (p - 0.5)
    if raw < 0:
        return 1 + 0.2 * (0.5 - p)
    return 1.0


def score_season(season, pitcher=True):
    pas = raw_season(season)
    ppl, _ = people(season)
    # drop position players pitching
    pas = [x for x in pas if ppl.get(x["pit"], {}).get("pos", "P") in ("P", "TWP")]
    pool = list(pas)
    prev = os.path.join(ROOT, "pbp", str(season - 1))
    if os.path.isdir(prev):
        pp, _ = people(season - 1)
        pool += [x for x in raw_season(season - 1) if pp.get(x["pit"], {}).get("pos", "P") in ("P", "TWP")]
    pct, _, _ = pitcher_percentiles(pool)
    for x in pas:
        p = pct.get(x["pit"], 0.5)
        pm = pitcher_mult(x["raw"], p) if pitcher else 1.0
        x["ppct"], x["pm"] = p, pm
        x["quality"] = x["raw"] * pm
        both = min(pm * x["cm"], x["cap"])
        x["capped"] = pm * x["cm"] > x["cap"]
        x["score"] = x["raw"] * both + (x["run"] + x["walkoff"]) * x["cm"]
        x["qab"] = x["quality"] >= 0.5 or (x["batter_out"] and x["adv"] > 0)
        x["bad"] = x["quality"] <= -1
    return pas


# ======================================================================
# v8: data-calibrated scoring (weights from tools/calibrate.py)
# ======================================================================
def load_weights():
    with open(os.path.join(ROOT, "weights.json")) as f:
        return json.load(f)


def inning_cap(inn):
    return 2.5 if inn >= 12 else 2.4 if inn >= 10 else 2.3 if inn == 9 else 2.2 if inn == 8 else 2.1 if inn == 7 else 2.0


def score_v8(x, W):
    """Score one PA (needs x['ek'] and x['li'] from calibrate.load)."""
    from calibrate import pitch_cat
    pc = x["pc"]
    pitch = sum(W["pitch"].get(pitch_cat(*p) or "", 0) for p in pc[:-1])
    end = W["ending"].get(x["ek"], 0.0)
    if x["ek"] == "k_look_out":
        end = W["ending"].get("k_look_in", end) / 2          # umpire's miss: half a strikeout
    if x["ek"] == "k_swing" and pc:
        end += W["pitch"].get(pitch_cat(pc[-1][0], 1, pc[-1][2], "W") or "", 0)  # chasing strike three costs extra
    n = x["n"]
    long = W["long"]["at7"] + W["long"]["per_extra"] * (n - 7) if n >= 7 else 0.0
    fphr = W["fphr"] if (x["et"] == "home_run" and n == 1) else 0.0
    quality = pitch + end + long + fphr            # skill only: how good the at-bat was
    # Game/season score: contact is half how hard it was hit, half what it turned into (hit or out)
    bip = x["ek"] in SKILL_CONTACT
    contact = 0.5 * end + 0.5 * W["result"].get(x["et"], end) if bip and "result" in W else end
    hard = bip and (x.get("hit") or {}).get("ev") is not None and x["hit"]["ev"] >= 95
    qab = quality >= 0.5 or n >= 7 or hard or (x["batter_out"] and x["adv_bases"] > 0)
    at_bat = pitch + contact + long + fphr
    if qab:
        at_bat = max(0.0, at_bat)                  # a good at-bat never counts against him
    r = W["runner"]
    runner = sum(r[f] * x[f] for f in r)
    walkoff = W["walkoff"] if x["walkoff"] else 0.0
    base = at_bat + runner + walkoff
    c = W["clutch"]
    m = (x["li"] ** c["power"] / c["norm"]) if x.get("li") is not None else 1.0
    if x["gtype"] != "R":
        m *= c["post"]
    m = max(0.25, min(m, inning_cap(x["inn"])))  # floor: even garbage time counts a little
    x.update(pitch8=pitch, end8=end, contact8=contact, ab8=at_bat, long8=long, fphr8=fphr, quality=quality,
             runner8=runner, base=base, m=m, score=base * m, qab=qab, bad=quality <= -1)
    return x


SKILL_CONTACT = {"barrel+impact", "barrel", "hard ld+impact", "hard ld", "hard fb+impact", "hard fb", "hard gb",
                 "med ld", "med", "weak ld", "weak gb", "weak fb", "popup"}
