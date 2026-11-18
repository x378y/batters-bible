# Calibration — 365,218 regular-season PAs, 2025, 2026

## Step 1: run expectancy (avg runs from this state to end of inning)
| Runners | 0 outs | 1 out | 2 outs |
|---|---|---|---|
| Empty | 0.50 | 0.27 | 0.11 |
| 1st | 0.88 | 0.53 | 0.23 |
| 2nd | 1.17 | 0.66 | 0.32 |
| 1st & 2nd | 1.56 | 0.92 | 0.46 |
| 3rd | 1.46 | 0.94 | 0.36 |
| 1st & 3rd | 1.79 | 1.19 | 0.50 |
| 2nd & 3rd | 2.00 | 1.39 | 0.53 |
| Loaded | 2.48 | 1.61 | 0.74 |

## Step 2-3: ending values (scale: 1 run = 4.51 points, so a walk = +1.5)
| Result | PAs | Runs | Points |
|---|---|---|---|
| barrel+impact | 8,222 | +1.094 | +4.94 |
| barrel | 10,178 | +0.538 | +2.43 |
| hard ld+impact | 4,912 | +0.321 | +1.45 |
| hard ld | 17,966 | +0.285 | +1.29 |
| hard fb+impact | 1,422 | +0.665 | +3.00 |
| hard fb | 11,387 | -0.050 | -0.22 |
| hard gb | 42,043 | +0.045 | +0.20 |
| med ld | 16,339 | +0.230 | +1.04 |
| med | 58,106 | -0.140 | -0.63 |
| weak ld | 7,913 | +0.197 | +0.89 |
| weak gb | 30,216 | -0.158 | -0.72 |
| weak fb | 11,160 | -0.005 | -0.02 |
| popup | 24,428 | -0.261 | -1.18 |
| bunt_hit | 1,164 | +0.384 | +1.74 |
| bunt_out | 1,747 | -0.231 | -1.04 |
| bb | 25,428 | +0.332 | +1.50 |
| bb30 | 5,062 | +0.346 | +1.56 |
| ibb | 1,101 | +0.231 | +1.04 |
| hbp | 4,007 | +0.355 | +1.60 |
| ci | 169 | +0.360 | +1.63 |
| k_swing | 62,374 | -0.275 | -1.24 |
| k_look_in | 16,902 | -0.265 | -1.20 |
| k_look_out | 2,033 | -0.261 | -1.18 |
| fb:fly_ball:medium | 40 | +0.198 | +0.89 |
| fb:ground_ball:medium | 790 | -0.144 | -0.65 |
| fb:ground_ball:soft | 62 | -0.109 | -0.49 |
| fb:line_drive:medium | 39 | +0.334 | +1.51 |

## Step 4: count values (avg ending points of PAs that passed through each count)
| Balls \ Strikes | 0 | 1 | 2 |
|---|---|---|---|
| 0 | -0.01 | -0.20 | -0.45 |
| 1 | +0.15 | -0.07 | -0.36 |
| 2 | +0.43 | +0.16 | -0.18 |
| 3 | +0.94 | +0.64 | +0.25 |

## Step 5: pitch values (count change vs. what usually happens on that pitch, that count)
| Pitch | Pitches | Points |
|---|---|---|
| ball_in_zone | 25,424 | +0.329 |
| take_ball_edge | 101,731 | +0.220 |
| foul2_zone | 37,343 | +0.154 |
| take_ball_out | 265,291 | +0.118 |
| foul2_edge | 18,557 | +0.049 |
| take_ball_far | 83,188 | +0.003 |
| foul2_heart | 27,740 | -0.030 |
| foul2_out | 14,793 | -0.069 |
| called_zone | 115,690 | -0.095 |
| whiff_zone | 31,752 | -0.118 |
| foul_zone | 67,841 | -0.120 |
| called_heart | 75,990 | -0.150 |
| whiff_heart | 17,718 | -0.193 |
| foul_heart | 63,797 | -0.193 |
| whiff_edge | 21,467 | -0.263 |
| foul_edge | 25,035 | -0.271 |
| called_off_plate | 19,480 | -0.276 |
| whiff_out | 26,425 | -0.391 |
| foul_out | 12,076 | -0.402 |
| whiff_far | 1,928 | -0.474 |

## Step 6: runner values (least-squares fit of what runners add beyond contact quality)
(Unconstrained fit gave contact a weight of 0.49 and pushed the rest into RBIs; fixing contact at 1.0 stops a hit being counted twice.)

| Runner outcome | Runs | Points | Unconstrained fit |
|---|---|---|---|
| rbi_lt2 | +0.217 | +0.98 | +1.66 |
| rbi_2 | +0.395 | +1.78 | +2.39 |
| adv_bases | +0.162 | +0.73 | +0.70 |
| str_reg | -0.181 | -0.82 | -1.03 |
| str3 | -0.341 | -1.54 | -1.81 |
| putout | -0.528 | -2.39 | -2.52 |

## Step 7: ball-in-play result values (net of runner points), used for half of the game score
| Result | Balls | Points |
|---|---|---|
| home_run | 11,123 | +3.30 |
| triple | 1,297 | +2.90 |
| double | 15,116 | +1.97 |
| fielders_choice | 770 | +1.72 |
| single | 50,874 | +1.19 |
| force_out | 6,553 | +0.52 |
| field_out | 146,466 | -0.80 |
| grounded_into_double_play | 6,173 | -1.03 |
| fielders_choice_out | 582 | -1.14 |
| sac_fly | 2,551 | -1.57 |
| double_play | 750 | -1.71 |

## Step 8: preference bonuses
Average 7-pitch strikeout before bonus: -1.21 → 7-pitch bonus +1.46 (nets about +0.25)
Average 8-pitch strikeout before bonus: -1.16 → +0.25 per pitch after 7 (8-pitch K nets about +0.5)
First-pitch home run bonus = the 8-pitch bonus = +1.71 (attacking rewarded like grinding)
First-pitch HRs in the data: 2,122 of 11,136 HRs

## Step 9: clutch multiplier = √(leverage index) ÷ league average
PAs with a leverage index: 360,359 of 365,218. Average √LI = 0.910

| Inning | Tied | Down 1 | Up 1 | Within 2–3 | 4+ either way |
|---|---|---|---|---|---|
| 1–6 | ×1.13 | ×1.22 | ×1.08 | ×1.01 | ×0.61 |
| 7–8 | ×1.50 | ×1.64 | ×1.03 | ×0.98 | ×0.40 |
| 9 | ×1.77 | ×2.05 | ×0.94 | ×1.02 | ×0.29 |
| 10+ | ×2.07 | ×2.55 | ×1.16 | ×1.27 | ×0.52 |

Multiplier spread: 10th pct ×0.38, median ×1.00, 90th ×1.57, 99th ×2.35, max ×3.47

## Step 10: base stealing (run-expectancy change, averaged over 0/1/2 outs)
| Event | Runs | Points |
|---|---|---|
| sb_2b | +0.169 | +0.76 |
| sb_3b | +0.203 | +0.92 |
| sb_home | +0.373 | +1.68 |
| cs_2b | -0.422 | -1.90 |
| cs_3b | -0.591 | -2.67 |
| cs_home | -0.794 | -3.58 |
| po_1b | -0.422 | -1.90 |
| po_2b | -0.591 | -2.67 |
| po_3b | -0.794 | -3.58 |

Break-even success rate stealing 2nd: 71%
