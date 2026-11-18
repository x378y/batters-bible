#!/usr/bin/env python3
"""Download every MLB game's play-by-play for a season and save a compact copy.

Usage:  python3 tools/fetch_pbp.py 2026
        python3 tools/fetch_pbp.py 2025 2026

Writes data/pbp/<season>/<gamePk>.json.gz (only the fields the scoring needs)
plus data/pbp/<season>/games.json (game list) and data/season-<season>.json
(batter season totals and pitcher positions, for checks and filters).
Re-running skips games already saved.
"""
import json, os, ssl, sys, time, gzip, urllib.request, concurrent.futures as cf

API = "https://statsapi.mlb.com/api/v1"
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def get(url, tries=5):
    for t in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60, context=CTX) as r:
                return json.load(r)
        except Exception:
            time.sleep(1.5 * (t + 1))
    raise RuntimeError("failed: " + url)


def games(season):
    d = get(f"{API}/schedule?sportId=1&season={season}&gameType=R,F,D,L,W"
            "&fields=dates,games,gamePk,gameType,officialDate,status,codedGameState,teams,away,home,team,id")
    out = {}
    for dt in d.get("dates", []):
        for g in dt["games"]:
            if g["status"].get("codedGameState") != "F":
                continue
            out[g["gamePk"]] = dict(pk=g["gamePk"], type=g["gameType"], date=g["officialDate"],
                                    away=g["teams"]["away"]["team"]["id"], home=g["teams"]["home"]["team"]["id"])
    return out


def compact(j):
    plays = []
    for p in j.get("allPlays", []):
        ev = []
        for e in p.get("playEvents", []):
            if not e.get("isPitch"):
                continue
            pd, d, hd = e.get("pitchData") or {}, e.get("details") or {}, e.get("hitData")
            c = pd.get("coordinates") or {}
            x = dict(i=e.get("index"), code=(d.get("call") or {}).get("code") or d.get("code"),
                     b=d.get("isBall", False), s=d.get("isStrike", False), ip=d.get("isInPlay", False),
                     cnt=[e["count"]["balls"], e["count"]["strikes"]] if e.get("count") else None,
                     px=c.get("pX"), pz=c.get("pZ"), top=pd.get("strikeZoneTop"), bot=pd.get("strikeZoneBottom"))
            if hd:
                hc = hd.get("coordinates") or {}
                x["hit"] = dict(ev=hd.get("launchSpeed"), la=hd.get("launchAngle"), traj=hd.get("trajectory"),
                                hard=hd.get("hardness"), hx=hc.get("coordX"), hy=hc.get("coordY"))
            ev.append(x)
        run = []
        for r in p.get("runners", []):
            m, d = r["movement"], r["details"]
            run.append(dict(id=d["runner"]["id"], start=m.get("start"), end=m.get("end"), out=m.get("isOut", False),
                            why=d.get("movementReason"), pi=d.get("playIndex"), ev=d.get("eventType")))
        res, ab, mu = p.get("result", {}), p.get("about", {}), p.get("matchup", {})
        plays.append(dict(inn=ab.get("inning"), top=ab.get("isTopInning"), et=res.get("eventType"),
                          rbi=res.get("rbi", 0), a=res.get("awayScore"), h=res.get("homeScore"),
                          bat=(mu.get("batter") or {}).get("id"), pit=(mu.get("pitcher") or {}).get("id"),
                          side=(mu.get("batSide") or {}).get("code"), outs=(p.get("count") or {}).get("outs"),
                          pitches=ev, runners=run))
    return plays


def season_totals(season):
    rows = {}
    for gt in ("R",):
        d = get(f"{API}/stats?stats=season&group=hitting&season={season}&sportId=1&gameType={gt}"
                "&playerPool=all&limit=5000")
        for x in (d.get("stats") or [{}])[0].get("splits", []):
            s = x["stat"]
            rows[x["player"]["id"]] = dict(name=x["player"]["fullName"], team=(x.get("team") or {}).get("abbreviation", ""),
                                           pa=s.get("plateAppearances", 0), ops=float(s.get("ops") or 0),
                                           obp=float(s.get("obp") or 0), slg=float(s.get("slg") or 0))
    return rows


def positions(ids):
    out, ids = {}, list(ids)
    for i in range(0, len(ids), 150):
        d = get(f"{API}/people?personIds={','.join(map(str, ids[i:i + 150]))}&fields=people,id,fullName,primaryPosition,abbreviation")
        for p in d.get("people", []):
            out[p["id"]] = dict(name=p["fullName"], pos=(p.get("primaryPosition") or {}).get("abbreviation", ""))
    return out


def build(season):
    t0 = time.time()
    folder = os.path.join(ROOT, "pbp", str(season))
    os.makedirs(folder, exist_ok=True)
    gl = games(season)
    with open(os.path.join(folder, "games.json"), "w") as f:
        json.dump(list(gl.values()), f)
    todo = [pk for pk in gl if not os.path.exists(os.path.join(folder, f"{pk}.json.gz"))]
    print(f"{season}: {len(gl)} final games, {len(todo)} to download", flush=True)

    def one(pk):
        plays = compact(get(f"{API}/game/{pk}/playByPlay"))
        with gzip.open(os.path.join(folder, f"{pk}.json.gz"), "wt") as f:
            json.dump(dict(game=gl[pk], plays=plays), f, separators=(",", ":"))
        return pk

    done = 0
    with cf.ThreadPoolExecutor(16) as ex:
        for _ in ex.map(one, todo):
            done += 1
            if done % 250 == 0:
                print(f"{season}: {done}/{len(todo)} ({time.time() - t0:.0f}s)", flush=True)

    pitchers, batters = set(), set()
    for pk in gl:
        with gzip.open(os.path.join(folder, f"{pk}.json.gz"), "rt") as f:
            for p in json.load(f)["plays"]:
                pitchers.add(p["pit"]); batters.add(p["bat"])
    meta = dict(season=season, batting=season_totals(season), people=positions((pitchers | batters) - {None}))
    with open(os.path.join(ROOT, f"season-{season}.json"), "w") as f:
        json.dump(meta, f, separators=(",", ":"))
    print(f"{season}: done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    a = [int(x) for x in sys.argv[1:]] or [2026]
    for s in range(a[0], (a[1] if len(a) > 1 else a[0]) + 1):
        build(s)
