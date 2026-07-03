# JACKPOT PREDICTION SYSTEM v5.0
## Complete Technical Documentation

---

# 1. WHAT THIS SYSTEM IS

A three-phase pipeline for football jackpot betting (Betika 15-game format):

```
Phase 1 (MODEL)  →  Phase 2 (WHEEL)  →  Phase 3 (FILTER)
predict each game    build optimal        prune statistically
probabilistically    ticket set within    implausible tickets
                     budget
```

It combines two genuinely different disciplines:

1. **Probabilistic match modelling** — estimating P(home win), P(draw),
   P(away win) for each game from real data
2. **Combinatorial optimisation** — spending a fixed budget on the set
   of tickets that maximises the chance at least one hits a prize tier

**What it is NOT:** a prediction oracle. No mathematical method predicts
football outcomes reliably. The world's best models reach ~53-56% on single
match outcomes. What this system does is (a) make each individual prediction
as well-calibrated as the data allows, and (b) ensure your correct predictions
are never wasted by bad ticket structure. The realistic goal is raising your
average from ~8-9 correct to ~10-11 correct, which materially improves
**bonus tier** (12/13/14 correct) chances. The 15/15 grand prize remains a
long shot under any system.

---

# 2. PHASE 1 — THE MATCH MODEL

## 2.1 Data source

Live standings from the **football-data.org API** (free tier), including
the home-only and away-only sub-tables per team:

- Goals for / goals against, split by home and away venue
- Matches played (for shrinkage weighting)

## 2.2 Attack and defence ratings

For the home team we use their **home-venue** record; for the away team
their **away-venue** record. This matters because venue splits are large
in football — many teams are near-unbeatable at home and poor away.

Raw rates:

```
h_att = home_goals_scored_at_home / home_games_played
h_def = home_goals_conceded_at_home / home_games_played
a_att = away_goals_scored_away / away_games_played
a_def = away_goals_conceded_away / away_games_played
```

## 2.3 Bayesian shrinkage (small-sample correction)

Early in a season, raw rates are noisy: a team with 3 games and 9 goals
looks like a 3.0-goals-per-game side, which is almost certainly luck.
Every serious rating system (Elo, Dixon-Coles fits, bookmaker models)
regularises toward the mean. We use the standard shrinkage estimator:

```
weight w = n / (n + K),  K = 5

shrunk_rate = w · raw_rate + (1 − w) · league_average
```

With 3 games: w = 0.375 → rating pulled 62% toward league average.
With 30 games: w = 0.857 → rating mostly reflects the team's own data.

## 2.4 Expected goals (the λ parameters)

Strengths are normalised by the league's average goals per team per game
(`half_avg`), then attack is matched against the opponent's defence:

```
home_xg = (h_att / half_avg) · (a_def / half_avg) · half_avg + HOME_ADV
away_xg = (a_att / half_avg) · (h_def / half_avg) · half_avg

HOME_ADV = 0.25 goals   (empirical home-advantage constant)
```

League baselines differ (Bundesliga ≈ 3.10 total goals/game,
Serie A ≈ 2.75, Primeira Liga ≈ 2.50), so the same rating means
different things in different leagues — the normalisation handles this.

## 2.5 The Poisson score matrix

Goals in football are well-approximated by a Poisson process. Given the
two expected-goal parameters, the probability of an exact scoreline h–a is:

```
P(h, a) = Pois(h; home_xg) · Pois(a; away_xg) · τ(h, a)
```

where `Pois(k; λ) = λᵏ e^(−λ) / k!`. We evaluate the full matrix for
h, a ∈ {0, …, 8} and sum the cells:

```
P(home win) = Σ P(h,a) for h > a
P(draw)     = Σ P(h,a) for h = a
P(away win) = Σ P(h,a) for h < a
```

## 2.6 The Dixon-Coles correction τ(h, a)

Plain independent Poisson systematically **underestimates draws** because
real match scores are not independent — 0-0 and 1-1 occur more often than
independence predicts. Dixon & Coles (1997, *Modelling Association Football
Scores and Inefficiencies in the Football Betting Market*) introduced a
correction to the four low-score cells:

```
τ(0,0) = 1 − λμρ        τ(0,1) = 1 + λρ
τ(1,0) = 1 + μρ         τ(1,1) = 1 − ρ
τ(h,a) = 1 otherwise

ρ = −0.13  (typical fitted value from league data)
```

Measured effect in this system: for an evenly-matched game the draw
probability rises from 0.258 (plain Poisson) to **0.290**, matching the
empirically observed ~28% draw rate for even matches. This is the single
most important accuracy correction in football Poisson modelling.

## 2.7 Banker classification

A game becomes a **banker** (locked, identical in every ticket) when its
highest outcome probability ≥ threshold (default 0.55). Everything else is
**uncertain** and goes to the wheel with its outcomes ranked by probability
(the ranked alternatives feed Phase 2's candidate generation).

---

# 3. PHASE 2 — THE COMBINATORIAL WHEEL

## 3.1 The problem, formally

A 15-game jackpot has 3¹⁵ = 14,348,907 possible outcome combinations.
Covering them all at KES 15/ticket costs ~KES 215M — absurd. The wheel
problem is:

> Given a budget of T tickets, choose the set of tickets that maximises
> the probability at least one scores ≥ target (e.g. 12/15).

This is a **covering design** problem — formally related to C(v, k, t)
covering designs and lottery wheel theory (see the La Jolla Covering
Repository for the academic catalogue). Exact optimal solutions are
NP-hard, so we use the standard greedy approximation.

## 3.2 Scenario construction

With B bankers locked and U = 15 − B uncertain games, needing target
score S means needing `need = S − B` uncertain games correct, i.e.
surviving up to `wrong = U − need` uncertain misses. We enumerate all
C(U, wrong) worst-case scenarios (each scenario = a specific set of
uncertain games going to their most likely alternative outcome).

Example: 5 bankers, target 12 → need 7/10 uncertain → wrong = 3 →
C(10,3) = 120 scenarios to cover.

## 3.3 Greedy set cover

The classic greedy algorithm (Chvátal 1979): repeatedly select the
candidate ticket covering the most still-uncovered scenarios, until all
scenarios are covered or the budget is exhausted. Greedy set cover is
provably within a ln(n) factor of optimal — the best achievable for any
polynomial-time algorithm.

A ticket "covers" a scenario if it would score ≥ `need` against it.

## 3.4 EV-weighted diversity fill

Greedy cover often terminates with few tickets (the guarantee is met
cheaply). The remaining budget is then filled by ranking leftover
candidates on a combined score:

```
score(ticket) = 0.5 · normalised_log_probability + 0.5 · diversity

log_probability = Σᵢ log P(pickᵢ correct)   (from Phase 1 probabilities)
diversity       = mean Hamming distance to already-selected tickets
```

This balances **plausibility** (tickets built from likely outcomes) with
**spread** (tickets covering different outcome combinations). Candidates
that would violate Phase 3's statistical bounds (too many home wins, zero
draws, over-long consecutive runs) are pre-filtered so the two phases
stay consistent.

## 3.5 Expected value

Each ticket's score distribution is computed by dynamic programming over
its 15 per-game correctness probabilities (a Poisson-binomial
distribution), then multiplied against the prize table:

```
dp[s] = P(exactly s correct)
EV    = Σ_ticket Σ_s dp[s] · prize(s)
```

---

# 4. PHASE 3 — THE STATISTICAL FILTER

## 4.1 Rationale

Out of all mathematically valid tickets, many describe jackpot results
that essentially never occur (15 home wins; zero draws in 15 games; nine
identical results in a row). Pruning these concentrates the budget on
outcomes that resemble the historical distribution of real jackpot results
(mean ≈ 6.2 home wins, 3.8 draws, 5.0 away wins per 15 games).

## 4.2 The six filters

| Filter | Rule | Type |
|---|---|---|
| Draw count | within [min, max], banker-adjusted | hard reject |
| Home-win count | within [min, max], banker-adjusted | hard reject |
| Away-win count | within [min, max], banker-adjusted | hard reject |
| Consecutive runs | ≤ dynamic max (banker run + 1) | hard reject |
| Outcome balance | penalty for extreme skew | soft penalty |
| Alternation | penalty for 1X1X1X patterns | soft penalty |

**Banker adjustment** is essential: if the model locks 7 home-win bankers,
every ticket necessarily contains ≥ 7 home wins and possibly a long
consecutive run created by the bankers themselves. Bounds are recomputed
each run from the actual banker composition so the filter never rejects
what the wheel was forced to produce.

## 4.3 Market divergence

For non-banker coin-flip games (45% < p < 72%) where ≥ 85% of your
tickets agree with the public favourite, the filter warns you: if that
popular result lands and many players share it, the bonus pool splits
more ways. A contrarian pivot on one ticket reduces split-prize exposure.
This mirrors what betting syndicates call *value seeking* — the aim is
not just being right but being right where fewer others are.

---

# 5. HONEST LIMITS (READ THIS)

1. **Football is high-variance.** A red card, a deflection, a penalty —
   no model sees these coming. ~55% single-game accuracy is the realistic
   ceiling for any model, including this one.
2. **The model omits** injuries, suspensions, head-to-head history, cup
   fatigue, motivation, and weather. Your own research on these should
   override the model for specific games.
3. **Unknown leagues** (South American cups, Russian Cup, etc.) get no
   data — the model outputs near-coin-flips for them and cannot help.
4. **The wheel guarantee is conditional**: "if ≥ N of your uncertain picks
   are right, at least one ticket scores ≥ target." It cannot make the
   picks right.
5. **Expected value is negative overall.** Jackpots are pari-mutuel with
   heavy house margin. This system improves your odds relative to naive
   play; it does not create a positive-EV investment. Only stake money
   you are fully comfortable losing.

---

# 6. VERSION HISTORY OF THE MATHS

| Version | Model | Key flaw fixed |
|---|---|---|
| v1.0 | Linear PPG ratio + hardcoded team list | Everything — probabilities were arbitrary |
| v2.0 | Normalised PPG power model, Soccerway scraping | Scraper blocked by Cloudflare |
| v3.0 | Same model, football-data.org API | Reliable data; model still crude |
| v4.0 | Independent Poisson, home/away splits | Draws underestimated; small samples overweighted |
| **v5.0** | **Dixon-Coles Poisson + Bayesian shrinkage + EV-weighted constrained wheel fill** | current |

---

# 7. FILE MAP & COMMANDS

```
phase1_model.py       Dixon-Coles Poisson match model
phase2_wheel.py       greedy covering design + EV-weighted fill
phase3_filter.py      banker-adjusted statistical pruning
run_pipeline.py       orchestrates all three
matches_template.csv  weekly input: Home,Away,Home_League,Away_League
```

```bash
pip install requests pandas numpy scipy

# first run (key is saved to api_key.txt afterwards)
python run_pipeline.py --matches matches_template.csv --budget 500 --api-key YOUR_KEY

# subsequent runs
python run_pipeline.py --matches matches_template.csv --budget 500
python run_pipeline.py --matches matches_template.csv --budget 500 --threshold 0.50
python run_pipeline.py --matches matches_template.csv --budget 500 --relax
```

# 8. REFERENCES

- Dixon, M.J. & Coles, S.G. (1997). *Modelling Association Football Scores
  and Inefficiencies in the Football Betting Market.* JRSS Series C.
- Maher, M.J. (1982). *Modelling Association Football Scores.*
  Statistica Neerlandica — the original Poisson football model.
- Chvátal, V. (1979). *A Greedy Heuristic for the Set-Covering Problem.*
- La Jolla Covering Repository — catalogue of optimal covering designs
  C(v, k, t), the formal theory behind lottery/jackpot wheels.
