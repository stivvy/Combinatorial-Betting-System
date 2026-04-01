# BETIKA JACKPOT SYSTEM — COMPLETE GUIDE
## 3-Phase Pipeline: Scrape → Wheel → Filter

---

## SETUP

### Requirements
- Python 3.9+
- Libraries: `pip install requests beautifulsoup4 pandas numpy scipy`

### File Structure
```
your_folder/
├── phase1_bankers.py      ← FBref scraper + Poisson model
├── phase2_wheel.py        ← Abbreviated wheel engine
├── phase3_filter.py       ← Heuristic filter
├── run_pipeline.py        ← Master runner (runs all 3)
└── matches_template.csv   ← Your weekly match input
```

---

## WEEKLY WORKFLOW

### Step 1 — Edit your matches file
Open `matches_template.csv` and replace with this week's 15 Betika games:
```
Man City,Burnley,Premier League
Arsenal,Wolves,Premier League
...
```
Format: `Home Team, Away Team, League`

### Step 2 — Run the full pipeline
```bash
python run_pipeline.py --matches matches.csv --budget 500
```

### Step 3 — Check your slips
Open `final_slips.txt` and SMS each line to **29090**

---

## INDIVIDUAL PHASE COMMANDS

### Phase 1 only (banker analysis)
```bash
python phase1_bankers.py --matches matches.csv
python phase1_bankers.py --matches matches.csv --threshold 0.72   # lower = more bankers
python phase1_bankers.py --matches matches.csv --no-scrape        # skip FBref, use cache
```

### Phase 2 only (wheel generation)
```bash
python phase2_wheel.py --budget 500
python phase2_wheel.py --budget 300 --target 13    # aim for 13/15 bonus
```

### Phase 3 only (filter)
```bash
python phase3_filter.py
python phase3_filter.py --strict      # tighter pattern filters
python phase3_filter.py --relax       # if too many tickets rejected
```

---

## PARAMETERS EXPLAINED

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `--budget` | 500 | KES to spend. Tickets = budget ÷ 15 |
| `--target` | 12 | Minimum score to guarantee (12/15, 13/15, 14/15) |
| `--threshold` | 0.75 | Probability needed to call a game a "banker" |
| `--strict` | off | Tighter historical pattern filters |

---

## HOW EACH PHASE WORKS

### Phase 1: Banker Detection
1. Scrapes FBref for team xG (expected goals scored) and xGA (expected goals conceded) per game
2. Uses **Poisson distribution** to calculate 1/X/2 probabilities for each match
3. Flags games where one outcome exceeds your threshold (default 75%) as **BANKERS**
4. These get locked — they never change across tickets
5. Outputs: `bankers.json`, `uncertain_games.csv`

**Poisson Model logic:**
- Home goals expected = (home xG / league avg) × (away xGA / league avg) × avg × home advantage
- Simulates every scoreline 0-0 to 8-8 to derive exact probabilities

### Phase 2: Abbreviated Wheel
1. Loads bankers — these are fixed in all tickets
2. Runs **Greedy Set Cover** on remaining uncertain games
3. Given your budget → max tickets = budget ÷ 15
4. Generates candidate pool by flipping low-confidence game picks to alternatives
5. Picks minimum tickets that guarantee ≥ target/15 if enough uncertain picks are right
6. Outputs: `wheel_tickets.json`, `sms_slips.txt`

**The Math:**
If 7 bankers locked + 8 uncertain games:
- You need 12/15 → need 5/8 uncertain games right
- Wheel generates ~8-15 tickets structured so at least one always catches 5+/8

### Phase 3: Heuristic Filter
Runs 6 statistical filters per ticket:

| Filter | Rule | Based on |
|--------|------|----------|
| Draw frequency | Reject if <2 or >7 draws | Historical jackpot results |
| Home win count | Reject if <3 or >10 | Historical distribution |
| Away win count | Reject if <2 or >9 | Historical distribution |
| Consecutive runs | Reject if >4 same in a row | Pattern analysis |
| Outcome balance | Penalise extreme skew | Statistical scoring |
| Market divergence | Warn if too similar to public | Payout optimisation |

---

## OUTPUT FILES

| File | Contents |
|------|----------|
| `bankers.json` | Full Phase 1 analysis, probabilities, bankers |
| `uncertain_games.csv` | Uncertain games for Phase 2 input |
| `wheel_tickets.json` | Raw wheel output |
| `sms_slips.txt` | SMS-ready slips |
| `filtered_tickets.json` | Final filtered output |
| `final_slips.txt` | Final SMS slips with quality scores |
| `final_slips.csv` | Spreadsheet view |
| `fbref_cache.json` | Cached FBref data (valid 3 days) |

---

## FBref SCRAPING NOTES

- FBref rate-limits aggressively — the scraper adds 4-second delays
- Data is cached for 3 days in `fbref_cache.json`
- If a team isn't found, it falls back to league average xG
- You'll see: `●` = full data, `◑` = partial, `○` = fallback

**If scraping fails:**
1. Check your internet connection
2. Try `--no-scrape` to use cached data
3. Manually edit xG values in `overrides.json`:
```json
{
  "3": {"home_xg": 1.8, "away_xg": 0.9, "data_source": "manual"},
  "7": {"home_xg": 1.2, "away_xg": 1.4}
}
```

---

## HONEST ASSESSMENT

**What the system guarantees mathematically:**
- If your analysis correctly identifies the bankers AND enough uncertain games are right,
  the wheel structure GUARANTEES at least one ticket hits the bonus threshold.

**What the system cannot do:**
- It cannot predict football results
- Bankers can still lose (upsets happen)
- The Poisson model is an approximation — real games have variance

**Where the edge comes from:**
1. Better data (xG vs xGA is more accurate than raw odds)
2. Optimal ticket structure (wheel) vs random tickets
3. Statistical filtering removes historically "impossible" patterns
4. Market divergence warnings reduce split-prize risk

---

## COST GUIDE

| Budget | Max Tickets | Best Target |
|--------|-------------|-------------|
| KES 150 | 10 tickets | 12/15 |
| KES 300 | 20 tickets | 12/15 or 13/15 |
| KES 500 | 33 tickets | 13/15 |
| KES 750 | 50 tickets | 13/15 or 14/15 |
| KES 1,200 | 80 tickets | 14/15 |
