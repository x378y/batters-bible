# Batters Bible

Every MLB plate appearance scored and graded S to F: quality, contact, power, discipline, grind,
run production, base stealing, clutch and consistency. How the scoring works: [SCORING.md](SCORING.md).

The site is a single page in `docs/` (served by GitHub Pages) that reads precomputed JSON in `docs/data/`.

## Rebuilding the data

Python 3 with `numpy` (and `certifi` on Macs without system certificates).

```bash
cd tools
python3 fetch_pbp.py 2021 2026      # play-by-play for every game, first to last season (skips saved games)
python3 fetch_wp.py 2021 2026       # win probability and leverage index per play
python3 calibrate.py > ../data/calibration.md   # fit point values on 2025-2026 -> data/weights.json
python3 build_site.py               # score every downloaded season with those values -> docs/data/
```

## Running locally

```bash
python3 -m http.server 8738 --directory docs
```

Data from the MLB Stats API.
