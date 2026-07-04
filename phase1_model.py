#!/usr/bin/env python3
"""
================================================================
 JACKPOT PREDICTION SYSTEM — PHASE 1: ODDS MODEL  v6.0
 Converts bookmaker odds into true probabilities.

 WHY THIS IS BETTER THAN POISSON:
   Bookmaker odds already encode injuries, form, head-to-head,
   xG, motivation, weather — everything. Billions in market
   intelligence packed into 3 numbers. No model we build from
   season standings will beat them.

 INPUT FORMAT (matches CSV):
   Home,Away,Odds_1,Odds_X,Odds_2
   Fiorentina,Atalanta,2.75,3.55,2.50

 NO API key needed. NO internet needed. Instant.
================================================================
"""

import json
import argparse
import sys
import os
from datetime import datetime

class C:
    R="\033[0m"; B="\033[1m"; RE="\033[91m"; GR="\033[92m"
    YE="\033[93m"; CY="\033[96m"; WH="\033[97m"; GY="\033[90m"

def banner():
    print(f"""
{C.CY}{C.B}  ╔══════════════════════════════════════════════════════════╗
  ║  PHASE 1: ODDS MODEL  |  Market-Implied Probabilities   ║
  ╚══════════════════════════════════════════════════════════╝{C.R}
""")

def sep(t=""):
    if t: print(f"{C.CY}{C.B}  -- {t} {'-'*(54-len(t))}{C.R}")
    else: print(f"{C.GY}  {'-'*58}{C.R}")

# ── ODDS TO PROBABILITY CONVERSION ──────────────────────────

def odds_to_probs(odds_1: float, odds_x: float, odds_2: float) -> dict:
    """
    Convert decimal bookmaker odds to true probabilities by removing
    the overround (bookmaker margin).

    Step 1: Raw implied probability = 1 / odds
    Step 2: Sum of all three > 1.0 (the overround = profit margin)
    Step 3: Normalise by dividing each by the sum

    Example:
      Odds: 2.75 / 3.55 / 2.50
      Raw:  0.364 / 0.282 / 0.400 = 1.045 (4.5% overround)
      True: 0.348 / 0.270 / 0.383 (sum = 1.000)
    """
    # Guard against zero/negative odds
    odds_1 = max(odds_1, 1.01)
    odds_x = max(odds_x, 1.01)
    odds_2 = max(odds_2, 1.01)

    raw_1 = 1.0 / odds_1
    raw_x = 1.0 / odds_x
    raw_2 = 1.0 / odds_2

    total = raw_1 + raw_x + raw_2  # > 1.0 due to overround

    p_home = round(raw_1 / total, 4)
    p_draw = round(raw_x / total, 4)
    p_away = round(1.0 - p_home - p_draw, 4)  # ensure exact sum = 1

    return {
        "p_home": p_home,
        "p_draw": p_draw,
        "p_away": p_away,
        "overround": round((total - 1.0) * 100, 1),  # margin %
    }

# ── ALTERNATIVE RANKING ──────────────────────────────────────

def rank_alternatives(probs: dict, primary: str) -> list:
    m = {"1": probs["p_home"], "X": probs["p_draw"], "2": probs["p_away"]}
    ranked = sorted(m.items(), key=lambda x: x[1], reverse=True)
    return [o for o, _ in ranked if o != primary]

# ── MATCH ANALYSIS ───────────────────────────────────────────

def analyse_match(game_num: int, home: str, away: str,
                  odds_1: float, odds_x: float, odds_2: float,
                  threshold: float) -> dict:

    probs = odds_to_probs(odds_1, odds_x, odds_2)

    p_home = probs["p_home"]
    p_draw = probs["p_draw"]
    p_away = probs["p_away"]

    max_p = max(p_home, p_draw, p_away)
    if p_home == max_p:   primary = "1"
    elif p_draw == max_p: primary = "X"
    else:                  primary = "2"

    is_banker  = bool(max_p >= threshold)
    confidence = round(max_p * 100, 1)
    alts       = rank_alternatives(probs, primary)

    return {
        "game":         game_num,
        "home":         home,
        "away":         away,
        "odds_1":       odds_1,
        "odds_x":       odds_x,
        "odds_2":       odds_2,
        "p_home":       p_home,
        "p_draw":       p_draw,
        "p_away":       p_away,
        "overround":    probs["overround"],
        "primary":      primary,
        "alternatives": " ".join(alts),
        "confidence":   confidence,
        "banker":       is_banker,
        "banker_pick":  primary if is_banker else None,
        "data_source":  "odds",
        "warning":      None,
    }

# ── DISPLAY ──────────────────────────────────────────────────

def print_analysis(results, threshold):
    sep("MATCH ANALYSIS")
    print()
    print(C.GY + f"  {'#':<4}{'Home':<18}{'Away':<18}"
          f"{'1%':>5}{'X%':>5}{'2%':>5}  {'Odds':>14}  {'Pick':<5}{'Conf':>6}  Status" + C.R)
    sep()

    for r in results:
        p1 = f"{r['p_home']*100:.0f}"
        px = f"{r['p_draw']*100:.0f}"
        p2 = f"{r['p_away']*100:.0f}"
        odds_str = f"{r['odds_1']:.2f}/{r['odds_x']:.2f}/{r['odds_2']:.2f}"

        if r["banker"]:
            st = f"{C.GR}{C.B}* BANKER{C.R}"
            pk = f"{C.GR}{C.B}{r['primary']}{C.R}"
            cf = f"{C.GR}{r['confidence']}%{C.R}"
        else:
            st = f"{C.GY}uncertain alts:{r['alternatives'] or '-'}{C.R}"
            pk = f"{C.YE}{r['primary']}{C.R}"
            cf = f"{C.GY}{r['confidence']}%{C.R}"

        print(f"  {C.GY}{r['game']:<4}{C.R}{r['home'][:16]:<18}{r['away'][:16]:<18}"
              f"{p1:>5}{px:>5}{p2:>5}  {odds_str:>14}  {pk:<14}{cf:<10}  {st}")

    print()
    bankers   = [r for r in results if r["banker"]]
    uncertain = [r for r in results if not r["banker"]]

    sep("SUMMARY"); print()
    print(f"  {C.GR}* Bankers: {len(bankers)}/{len(results)}{C.R}")
    print(f"  {C.YE}? Uncertain: {len(uncertain)}/{len(results)}{C.R}")
    print(f"  {C.GY}  Threshold: {threshold*100:.0f}%{C.R}")

    avg_overround = sum(r["overround"] for r in results) / len(results) if results else 0
    print(f"  {C.GY}  Avg bookmaker margin: {avg_overround:.1f}%{C.R}")
    print()

    if bankers:
        print(f"  {C.GR}{C.B}LOCKED BANKERS:{C.R}")
        for b in bankers:
            print(f"  {C.GR}  G{b['game']:>2}: {b['home']:<20} vs {b['away']:<20} -> "
                  f"{C.B}{b['primary']}{C.R}{C.GR} ({b['confidence']}%){C.R}")

    if uncertain:
        print()
        print(f"  {C.YE}{C.B}UNCERTAIN (going to wheel):{C.R}")
        for u in uncertain:
            print(f"  {C.YE}  G{u['game']:>2}: {u['home']:<20} vs {u['away']:<20} -> "
                  f"Primary: {C.B}{u['primary']}{C.R}{C.YE}  "
                  f"Alts: {u['alternatives'] or '-'}{C.R}")
    print()

# ── SAVE ─────────────────────────────────────────────────────

def save_output(results, threshold):
    bankers   = [r for r in results if r["banker"]]
    uncertain = [r for r in results if not r["banker"]]
    out = {
        "generated":     datetime.now().isoformat(),
        "threshold":     threshold,
        "total_games":   len(results),
        "num_bankers":   len(bankers),
        "num_uncertain": len(uncertain),
        "bankers":       bankers,
        "uncertain":     uncertain,
        "all_results":   results,
    }
    with open("bankers.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"  {C.GR}OK bankers.json saved{C.R}")
    print(f"  {C.CY}  Next: python phase2_wheel.py --budget 500{C.R}\n")

# ── MAIN ─────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Phase 1: Convert bookmaker odds to probabilities"
    )
    p.add_argument("--matches", required=True,
                   help="CSV: Home,Away,Odds_1,Odds_X,Odds_2")
    p.add_argument("--threshold", type=float, default=0.55,
                   help="Banker probability threshold (default: 0.55)")
    # Keep these for backward compatibility with run_pipeline.py
    p.add_argument("--api-key", default=None, help="(ignored in odds mode)")
    p.add_argument("--no-scrape", "--skip-scrape", action="store_true",
                   help="(ignored in odds mode)")
    args = p.parse_args()

    banner()

    # ── Load matches CSV ──────────────────────────────────────
    try:
        results = []
        game_num = 0

        with open(args.matches, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = [x.strip() for x in line.split(",")]

                # Skip header row
                if parts[0].lower() in ("home", "home team"):
                    continue

                # Detect format: 5 columns = odds mode, 4 columns = league mode
                if len(parts) >= 5:
                    # Check if column 3 looks like a number (odds) or text (league)
                    try:
                        float(parts[2])
                        # It's a number -> odds format: Home,Away,O1,OX,O2
                        home   = parts[0]
                        away   = parts[1]
                        odds_1 = float(parts[2])
                        odds_x = float(parts[3])
                        odds_2 = float(parts[4])
                    except ValueError:
                        # It's text -> league format with result: Home,Away,HL,AL,Result
                        # (backtest mode) — use fallback odds
                        home   = parts[0]
                        away   = parts[1]
                        odds_1 = 2.50  # neutral default
                        odds_x = 3.30
                        odds_2 = 2.80
                        print(f"  {C.YE}  No odds for {home} vs {away} — using neutral defaults{C.R}")
                elif len(parts) >= 3:
                    try:
                        float(parts[2])
                        # Home,Away,O1 — incomplete odds
                        print(f"{C.RE}  Need 5 columns: Home,Away,Odds_1,Odds_X,Odds_2{C.R}")
                        sys.exit(1)
                    except ValueError:
                        # Home,Away,League — old format, use neutral odds
                        home   = parts[0]
                        away   = parts[1]
                        odds_1 = 2.50
                        odds_x = 3.30
                        odds_2 = 2.80
                        print(f"  {C.YE}  No odds for {home} vs {away} — using neutral defaults{C.R}")
                elif len(parts) >= 2:
                    home   = parts[0]
                    away   = parts[1]
                    odds_1 = 2.50
                    odds_x = 3.30
                    odds_2 = 2.80
                    print(f"  {C.YE}  No odds for {home} vs {away} — using neutral defaults{C.R}")
                else:
                    continue

                game_num += 1
                results.append(analyse_match(
                    game_num, home, away, odds_1, odds_x, odds_2, args.threshold
                ))

    except FileNotFoundError:
        print(f"{C.RE}  File not found: {args.matches}{C.R}")
        sys.exit(1)
    except Exception as e:
        print(f"{C.RE}  Error reading {args.matches}: {e}{C.R}")
        sys.exit(1)

    if not results:
        print(f"{C.RE}  No games found in file{C.R}")
        sys.exit(1)

    if len(results) != 15:
        print(f"{C.YE}  Warning: expected 15 games, got {len(results)}{C.R}\n")

    print_analysis(results, args.threshold)
    save_output(results, args.threshold)

if __name__ == "__main__":
    main()
