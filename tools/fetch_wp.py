#!/usr/bin/env python3
"""Download MLB's win probability and leverage index for every play of a season.

Usage: python3 tools/fetch_wp.py 2025 2026
Writes data/wp/<season>/<gamePk>.json: [[atBatIndex, homeWinProb, homeWPA, leverageIndex], ...]
Needs data/pbp/<season>/games.json from tools/fetch_pbp.py. Re-running skips saved games.
"""
import json, os, sys, time, concurrent.futures as cf
from fetch_pbp import get, API, ROOT


def build(season):
    t0 = time.time()
    with open(os.path.join(ROOT, "pbp", str(season), "games.json")) as f:
        pks = [g["pk"] for g in json.load(f)]
    folder = os.path.join(ROOT, "wp", str(season))
    os.makedirs(folder, exist_ok=True)
    todo = [pk for pk in pks if not os.path.exists(os.path.join(folder, f"{pk}.json"))]
    print(f"{season}: {len(todo)} games to download", flush=True)

    def one(pk):
        d = get(f"{API}/game/{pk}/winProbability?fields=about,atBatIndex,homeTeamWinProbability,"
                "homeTeamWinProbabilityAdded,leverageIndex")
        rows = [[x["about"]["atBatIndex"], x.get("homeTeamWinProbability"), x.get("homeTeamWinProbabilityAdded"),
                 x.get("leverageIndex")] for x in d]
        with open(os.path.join(folder, f"{pk}.json"), "w") as f:
            json.dump(rows, f, separators=(",", ":"))

    with cf.ThreadPoolExecutor(16) as ex:
        for i, _ in enumerate(ex.map(one, todo), 1):
            if i % 500 == 0:
                print(f"{season}: {i}/{len(todo)} ({time.time() - t0:.0f}s)", flush=True)
    print(f"{season}: done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    a = [int(x) for x in sys.argv[1:]] or [2026]
    for s in range(a[0], (a[1] if len(a) > 1 else a[0]) + 1):
        build(s)
