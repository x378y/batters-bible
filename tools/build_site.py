#!/usr/bin/env python3
"""Build the data files the Batters Bible site reads. Usage: python3 tools/build_site.py

Reads the downloaded play-by-play (tools/fetch_pbp.py, tools/fetch_wp.py) and weights
(tools/calibrate.py), scores every plate appearance, and writes:

  docs/data/index.json            seasons, scoring values, tiers, category definitions
  docs/data/season-<yr>.json      every batter's season line, grades and percentiles
  docs/data/p/<yr>/<id>.json      one batter's game log with every PA (pitch by pitch)
"""
import collections, json, os, shutil, statistics as st, time
from datetime import datetime, timezone
from calibrate import load, run_values
from score import load_weights, score_v8, people, ROOT
from grades import CATS, TIERS, MIN_PA, NON_CONTACT, grade, line, steal_counts
from fetch_pbp import get, API

SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "data")
MIN_SHOW = 15
HITS = {"single": "1B", "double": "2B", "triple": "3B", "home_run": "HR"}
NOT_AB = {"walk", "intent_walk", "hit_by_pitch", "catcher_interf", "sac_fly", "sac_bunt", "sac_fly_double_play",
          "sac_bunt_double_play"}


def r(v, n=2):
    return None if v is None else round(v, n)


def pct_of(vals, x):
    n = len(vals)
    return 50 if n < 2 else max(0, min(100, round(100 * sum(v < x for v in vals) / (n - 1))))


def game_line(xs):
    ab = sum(x["et"] not in NOT_AB for x in xs)
    h = [HITS[x["et"]] for x in xs if x["et"] in HITS]
    parts = [f"{len(h)}-{ab}"]
    for t in ("HR", "3B", "2B"):
        if h.count(t): parts.append(f"{h.count(t)} {t}" if h.count(t) > 1 else t)
    bb = sum(x["et"] in ("walk", "intent_walk") for x in xs)
    if bb: parts.append(f"{bb} BB" if bb > 1 else "BB")
    k = sum(x["et"].startswith("strikeout") for x in xs)
    if k: parts.append(f"{k} K" if k > 1 else "K")
    rbi = sum(x["rbi_lt2"] + x["rbi_2"] for x in xs)
    if rbi: parts.append(f"{rbi} RBI")
    return ", ".join(parts)


def pa_row(x):
    """One PA for the site. Zero / empty fields are left out to keep files small (the page fills them back in)."""
    h = x.get("hit") or {}
    full = dict(i=x["inn"], t=1 if x["top"] else 0, o=x["outs"], b=x["bmask"], mg=x["margin"], et=x["et"], ek=x["ek"],
                n=x["n"], p=r(x["pitch8"]), e=r(x["end8"]), lg=r(x["long8"]), fp=r(x["fphr8"]), ru=r(x["runner8"]),
                wo=1 if x["walkoff"] else 0, bs=r(x["base"]), m=r(x["m"]), s=r(x["score"]), li=x.get("li"),
                pc="".join(f"{b}{s}{l}{o}" for b, s, l, o in x["pc"]), ev=h.get("ev"), la=h.get("la"),
                rbi=x["rbi_lt2"] + x["rbi_2"], r2=x["rbi_2"], adv=x["adv_bases"], sr=x["str_reg"], s3=x["str3"],
                po=x["putout"], q=1 if x["qab"] else 0)
    return {k: v for k, v in full.items() if v not in (0, 0.0, None, "") or k in ("i", "n", "s")}


def main():
    t0 = time.time()
    W = load_weights()
    pas = load(); run_values(pas)
    for x in pas:
        score_v8(x, W)
    seasons = sorted({x["season"] for x in pas})
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(SITE)

    # game-score tiers from every regular-season player-game
    gsum = collections.defaultdict(float)
    for x in pas:
        if x["gtype"] == "R":
            gsum[(x["season"], x["pk"], x["bat"])] += x["score"]
    gs = sorted(gsum.values())
    game_cuts = [[g, round(gs[min(len(gs) - 1, round(c / 100 * (len(gs) - 1)))], 2)] for c, g in TIERS]

    out_seasons = []
    for yr in seasons:
        _, bat = people(yr)
        teams = {t["id"]: t["abbreviation"] for t in get(f"{API}/teams?sportId=1&season={yr}")["teams"]}
        games = {g["pk"]: g for g in json.load(open(os.path.join(ROOT, "pbp", str(yr), "games.json")))}
        steals = steal_counts(yr)
        mine = collections.defaultdict(list)
        for x in pas:
            if x["season"] == yr:
                mine[x["bat"]].append(x)
        reg = {b: [x for x in xs if x["gtype"] == "R"] for b, xs in mine.items()}
        lines = {b: line(xs, steals.get(b, {}), W) for b, xs in reg.items() if xs}
        qual = [l for l in lines.values() if l["pa"] >= MIN_PA]
        dist = {k: sorted(l[k] for l in qual) for k, _, _ in CATS}
        cuts = {k: [[g, r(dist[k][min(len(dist[k]) - 1, round(c / 100 * (len(dist[k]) - 1)))], 3)] for c, g in TIERS]
                for k, _, _ in CATS}

        def graded(l):
            o = dict(pa=l["pa"], total=r(l["total"], 1), sb=l["sb"], cs=l["cs"], po=l["po"])
            for k, _, _ in CATS:
                p = pct_of(dist[k], l[k])
                o[k] = r(l[k], 3); o[k + "_p"] = p; o[k + "_g"] = grade(p)
            return o

        players = []
        pdir = os.path.join(SITE, "p", str(yr))
        os.makedirs(pdir)
        for b, xs in mine.items():
            if b is None:
                continue
            xs.sort(key=lambda x: (x["date"], x["pk"], x["k"]))
            last = xs[-1]
            g = games[last["pk"]]
            team = teams.get(g["home"] if not last["top"] else g["away"], "")
            name = (bat.get(b) or {}).get("name") or people(yr)[0].get(b, {}).get("name", str(b))
            row = dict(id=b, name=name, team=team, ops=(bat.get(b) or {}).get("ops"))
            if b in lines and lines[b]["pa"] >= MIN_SHOW:
                row["reg"] = graded(lines[b])
            post = [x for x in xs if x["gtype"] != "R"]
            if post:
                pl = line(post, {}, W)
                pg = graded(pl)
                pg.pop("steal", None); pg.pop("steal_p", None); pg.pop("steal_g", None)
                row["post"] = pg
            if "reg" in row or "post" in row:
                players.append(row)
            # game log
            bygame = collections.defaultdict(list)
            for x in xs:
                bygame[x["pk"]].append(x)
            log = []
            for pk, gx in bygame.items():
                gm = games[pk]
                home = not gx[0]["top"]
                log.append(dict(pk=pk, d=gm["date"], post=1 if gm["type"] != "R" else 0,
                                opp=teams.get(gm["away"] if home else gm["home"], "?"), home=1 if home else 0,
                                s=r(sum(x["score"] for x in gx)), q=r(sum(x["quality"] for x in gx)),
                                ln=game_line(gx), pas=[pa_row(x) for x in gx]))
            log.sort(key=lambda g: (g["d"], g["pk"]))
            with open(os.path.join(pdir, f"{b}.json"), "w") as f:
                json.dump(dict(id=b, name=name, team=team, season=yr, games=log), f, separators=(",", ":"))
        players.sort(key=lambda p: -(p.get("reg") or {}).get("total", -1e9))
        lg_total = st.mean(l["total"] for l in qual)
        with open(os.path.join(SITE, f"season-{yr}.json"), "w") as f:
            json.dump(dict(season=yr, min_pa=MIN_PA, avg_total=r(lg_total, 1), qualified=len(qual), cuts=cuts,
                           players=players), f, separators=(",", ":"))
        out_seasons.append(yr)
        print(f"{yr}: {len(players)} batters, {len(qual)} qualified ({time.time() - t0:.0f}s)", flush=True)

    meta = dict(built=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), seasons=out_seasons,
                cats=[dict(key=k, label=l, fmt=f) for k, l, f in CATS], tiers=[[c, g] for c, g in TIERS],
                game_cuts=game_cuts, min_pa=MIN_PA, min_show=MIN_SHOW,
                weights=dict(scale=W["scale"], pitch=W["pitch"], ending=W["ending"], long=W["long"], fphr=W["fphr"],
                             runner=W["runner"], walkoff=W["walkoff"], clutch=W["clutch"], steal=W["steal"],
                             re=W["re"], pas=W["pas"], seasons=W["seasons"]))
    with open(os.path.join(SITE, "index.json"), "w") as f:
        json.dump(meta, f, separators=(",", ":"))
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
