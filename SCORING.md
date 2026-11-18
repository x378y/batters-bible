# Batters Bible — Scoring (v9, calibrated on 2025–2026)

Every plate appearance (PA) gets a score:

```
Quality      = pitch points + ending points + long-AB bonus + first-pitch HR bonus   (skill only)
At-bat       = same, but a ball in play counts ½ contact grade + ½ what it became;
               a quality at-bat (section 3b) can't go below zero
Base         = At-bat + runner points + walk-off bonus
Clutch score = Base × clutch multiplier (leverage)
Season       = average per PA: Clutch score, Quality, Clutch gap, QAB%, Consistency
```

Scale: **1 run = 4.51 points**, chosen so a walk is still +1.5.
Numbers marked *data* were fitted on 365,218 regular-season PAs (2025–2026, `tools/calibrate.py`).
Numbers marked *choice* are deliberate design decisions, sized against the fitted values.

---

## 1. Every pitch before the last one (*data*)

Each pitch is worth how much better or worse the count got, compared with what usually happens on a
pitch in that same location and count. Location uses the batter's own strike zone.

| Pitch | Points | | Pitch | Points |
|---|---|---|---|---|
| Take a ball just off the edge (≤3 in) | +0.22 | | Called strike, edge of zone | −0.10 |
| Take a ball outside | +0.12 | | Whiff in the zone | −0.12 |
| Take a ball way outside (1 ft+) | 0.00 | | Foul in the zone, <2 strikes | −0.12 |
| 2-strike foul, in the zone | +0.15 | | Called strike, heart | −0.15 |
| 2-strike foul, just off the edge | +0.05 | | Whiff, heart | −0.19 |
| 2-strike foul, heart | −0.03 | | Foul, heart, <2 strikes | −0.19 |
| 2-strike foul, outside | −0.07 | | Whiff / foul just off the edge, <2 strikes | −0.26 / −0.27 |
| Umpire's miss (ball in zone, or strike off the plate) | 0 (*choice*) | | Whiff / foul outside, <2 strikes | −0.39 / −0.40 |
| | | | Whiff way outside | −0.47 |

## 2. How the PA ends

### Ball in play (*choice*, tested): graded on exit velocity and launch angle, not hit vs. out

| Contact | Points | Pulled (95+ mph, 15–35°) |
|---|---|---|
| Barrel | +4.0 | +4.8 |
| Hard line drive (95+, 10–25°) | +3.0 | +3.6 |
| Hard fly ball (95+, 25–50°) | +2.0 | +2.4 |
| Hard grounder (95+, <10°) | +1.0 | |
| Medium line drive (80–95) | +1.0 | |
| Medium grounder / fly ball | 0 | |
| Weak line drive (<80) | 0 | |
| Weak grounder | −0.5 | |
| Weak fly ball / any pop-up (>50°) | −1.0 | |

Why not use the fitted run values here: they reward luck (weak line drives +0.89 because bloops fall;
hard fly balls −0.22 because warning-track outs). Grading the skill predicts next-season OPS at .358,
grading the run value only .275.

### What it became (*data*, half of the game score and season total)

The Quality and Power grades use the contact grade alone. The game score and season total use
½ contact grade + ½ the value of the result, net of runner points so a run isn't counted twice:

| Result | Points |
|---|---|
| Home run | +3.30 |
| Triple | +2.90 |
| Double | +1.97 |
| Fielder's choice (batter safe) | +1.72 |
| Single | +1.19 |
| Force out | +0.52 (the runner put out is charged in runner points) |
| Out in play | −0.80 |
| Ground into double play | −1.03 (plus −2.39 for the runner) |
| Sac fly | −1.57 (runner points add back +0.98 RBI, +0.73 advance) |
| Reached on error | contact grade only: the error doesn't help |

Example: a hard line drive caught = ½ × 3.0 + ½ × −0.80 = **+1.10**. A pop-up out = ½ × −1.0 + ½ × −0.80 = **−0.90**.

### Other endings (*data*)

| Result | Points |
|---|---|
| Walk (any count — 3-0 walks were worth the same, +1.56) | +1.50 |
| Hit by pitch | +1.25 (*choice*: below a walk; data had +1.60) |
| Catcher's interference | +1.25 (*choice*, same as HBP) |
| Intentional walk | +1.04 |
| Bunt hit | +1.74 |
| Bunt out (runner points usually make up for it) | −1.04 |
| Strikeout swinging | −1.24, plus that pitch's whiff value (chasing strike three way outside ≈ −1.71) |
| Strikeout looking, in the zone | −1.20 |
| Strikeout looking, off the plate | −0.60 (*choice*: half, umpire's miss) |

## 3. Long at-bats (*choice*, sized from data)

| Pitches | Bonus |
|---|---|
| 1–6 | 0 |
| 7 | +1.46 (a 7-pitch strikeout averages about +0.25) |
| each pitch after 7 | +0.25 more (an 8-pitch strikeout averages about +0.5) |

## 3b. Good at-bats never count against him (*choice*)

A PA is a **quality at-bat (QAB)** if any of these is true:
- 7 or more pitches
- a ball in play hit 95+ mph
- a productive out (batter out, runner moved up)
- Quality of +0.5 or more

If a QAB's at-bat points (pitches + contact + bonuses) come out below zero, they count as **zero**.
Runner points still apply after that, so stranding runners still costs. About 6% of PAs get lifted.

Average points by type of at-bat (bases empty, 2026):

| At-bat | Points | | At-bat | Points |
|---|---|---|---|---|
| Home run | +5.23 | | Hard grounder out (95+) | +0.21 |
| Double | +2.20 | | Medium contact out | −0.36 |
| Walk | +2.08 | | Weak grounder out | −0.63 |
| Single, hard-hit | +1.58 | | Pop-up out | −0.73 |
| Hard line drive caught | +1.23 | | Strikeout, 3–4 pitches | −1.73 |
| Hard fly ball caught | +0.69 | | Strikeout, 5–6 pitches | −1.51 |
| Single, bloop (<80 mph) | +0.50 | | Strikeout, 7 pitches | +0.17 |
| | | | Strikeout, 8+ pitches | +0.55 |

## 4. First-pitch home run (*choice*)

**+1.71**, the same as an 8-pitch at-bat, so attacking and grinding are rewarded equally.
19% of home runs (2,122 of 11,136) came on the first pitch.

## 5. Runners (*data*: what each outcome adds beyond the contact quality)

| Outcome | Points | Old guess |
|---|---|---|
| RBI, 0–1 outs | +0.98 | +0.50 |
| RBI, 2 outs | +1.78 | +0.75 |
| Each base a runner moves up on the batter's play | +0.73 | +0.25 |
| Stranded: batter out, runner didn't move (any base) | −0.82 | −0.25 |
| Stranded on 3rd with fewer than 2 outs | −1.54 | −0.50 |
| Runner put out on the batter's play | −2.39 | −0.25 |

Rules unchanged: only movement the batter caused counts (no steals, wild pitches, pickoffs, errors);
base state is right before the final pitch; the automatic runner in extras isn't counted as stranded.

## 6. Walk-off (*choice*): +1.0

## 7. Clutch multiplier (*data*: MLB leverage index)

`multiplier = √(leverage index) ÷ 0.910`, so the average PA is exactly ×1.00.

MLB's leverage index for each PA already combines inning, score, outs and runners. Typical values:

| Inning | Tied | Down 1 | Up 1 | Within 2–3 | 4+ either way |
|---|---|---|---|---|---|
| 1–6 | ×1.13 | ×1.22 | ×1.08 | ×1.01 | ×0.61 |
| 7–8 | ×1.50 | ×1.64 | ×1.03 | ×0.98 | ×0.40 |
| 9 | ×1.77 | ×2.05 | ×0.94 | ×1.02 | ×0.29 |
| 10+ | ×2.07 | ×2.55 | ×1.16 | ×1.27 | ×0.52 |

- Spread: 10% of PAs are ×0.38 or less, median ×1.00, top 10% ×1.57+, top 1% ×2.35+.
- Inning caps (*choice*): ×2.0 through the 6th, ×2.1 7th, ×2.2 8th, ×2.3 9th, ×2.4 10th–11th, ×2.5 12th+.
- Floor ×0.25 (*choice*), so garbage time still counts a little.
- Postseason ×1.25 on top (*choice*).

**Clutch gap** = leverage-weighted average Base − plain average Base. 0 means he hit the same in big
spots as everywhere else.

## 8. Base stealing (*data*, separate category, not in the score)

Run-expectancy change for one runner, averaged over 0/1/2 outs:

| Event | Points |
|---|---|
| Steal 2nd / 3rd / home | +0.76 / +0.92 / +1.68 |
| Caught stealing 2nd / 3rd / home | −1.90 / −2.67 / −3.58 |
| Picked off 1st / 2nd / 3rd | −1.90 / −2.67 / −3.58 |

Break-even success rate stealing 2nd: 71%. Graded as steal points per 600 PA.
Pickoff errors (runner advances) don't count. Counts match MLB's official SB/CS totals.

## 8b. Grade categories

| Category | What it measures |
|---|---|
| Overall | Clutch score per PA |
| Quality | Quality per PA |
| Contact | Share of swings that make contact (bat-to-ball skill) |
| Power | Average contact grade per ball in play (barrels, hard-hit) |
| Discipline | Pitch points + walk/strikeout points per PA |
| Grind | Long-AB bonus per PA |
| Run production | Runner points per PA |
| Base stealing | Steal points per 600 PA |
| Clutch | Clutch gap |
| QAB% / Consistency | Section 9 |

Tiers (percentile among 300+ PA hitters that season): S 97+, A 85–96, B 65–84, C 40–64, D 20–39, E 8–19, F 0–7.

## 9. Consistency (separate stats)

- **QAB**: see section 3b (7+ pitches, 95+ mph contact, productive out, or Quality +0.5 or more).
- **QAB%**, **Bad AB%** (Quality −1 or worse), **Consistency %** (games with 2+ PA where at least half were QABs), **QAB streak**, **Game spread**.

## 10. Displays

- Season: Clutch score per PA, Quality per PA, Clutch gap, QAB%, Consistency %, Baserunning; rating 100 = league average.
- Grades by percentile: A+ 96–100, A 90–95, B+ 80–89, B 70–79, C+ 60–69, C 50–59, D+ 40–49, D 25–39, F 0–24.
- Regular season and postseason have separate leaderboards. Minimums: 15+ PA for season averages, 300 PA default leaderboard.
- Position players pitching: those PAs are dropped.

## 11. How well it works (2026 test, 300+ PA)

| Measure | Clutch score | Quality | Plain OPS |
|---|---|---|---|
| Matches same-season OPS | .659 | .592 | — |
| 2025 value predicts 2026 OPS | .350 | .353 | .425 |
| Same in odd vs even games | .320 | .542 | — |

Clutch gap repeats very little (2025 vs 2026: .086). It describes who delivered this year, not a skill
that carries over.

v9 traded a little prediction (.391 → .350) so the season total reflects what actually happened.

Removed in v8: pitcher multiplier (made scores less predictive at every strength tested), the 3-0 walk
reduction (data showed no difference), the hand-built clutch table (replaced by leverage index).
