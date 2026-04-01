#!/usr/bin/env python3
"""
================================================================
 BETIKA JACKPOT SYSTEM — PHASE 3: HEURISTIC FILTER
 Statistical Pruning + Pattern Analysis + Market Divergence

 FIXED: ZeroDivisionError & Relaxed Draw Frequency for Wheels
================================================================
"""

import json
import argparse
import sys
import os
import csv
from collections import Counter
from datetime import datetime
from itertools import groupby

# ── COLORS ──────────────────────────────────────────────────
class C:
    R  = "\033[0m"; B  = "\033[1m"; RE = "\033[91m"
    GR = "\033[92m"; YE = "\033[93m"; BL = "\033[94m"
    MA = "\033[95m"; CY = "\033[96m"; WH = "\033[97m"
    GY = "\033[90m"

def banner():
    print(f"""
{C.YE}{C.B}  ╔══════════════════════════════════════════════════════════╗
  ║   PHASE 3: HEURISTIC FILTER  |  Pattern + Pruning       ║
  ╚══════════════════════════════════════════════════════════╝{C.R}
""")

def sep(title=""):
    if title:
        pad = "─" * (54 - len(title))
        print(f"{C.CY}{C.B}  ── {title} {pad}{C.R}")
    else:
        print(f"{C.GY}  {'─'*58}{C.R}")

# ── HISTORICAL JACKPOT PATTERN STATS ────────────────────────
HISTORICAL_PATTERNS = {
    "avg_home_wins":   6.2,
    "avg_draws":       3.8,
    "avg_away_wins":   5.0,
    "std_home_wins":   1.8,
    "std_draws":       1.5,
    "std_away_wins":   1.7,
    # FIXED: Lowered min_draws to 1 to accommodate budget-aware wheels
    "min_draws":       0,      
    "max_draws":       7,      
    "min_home_wins":   2,      
    "max_home_wins":   12,     
    "min_away_wins":   1,      
    "max_away_wins":   9,      
    "max_consecutive": 5,      
}

HISTORICAL_PATTERNS_STRICT = {
    **HISTORICAL_PATTERNS,
    "min_draws":       0,
    "max_draws":       6,
    "min_home_wins":   4,
    "max_home_wins":   9,
    "max_consecutive": 3,
}

HISTORICAL_PATTERNS_RELAXED = {
    **HISTORICAL_PATTERNS,
    "min_draws":       0,
    "max_draws":       9,
    "min_home_wins":   1,
    "max_home_wins":   13,
    "max_consecutive": 6,
}

# ── FILTER FUNCTIONS ─────────────────────────────────────────

class FilterResult:
    def __init__(self, passed: bool, reason: str = "", penalty: float = 0.0):
        self.passed  = passed
        self.reason  = reason
        self.penalty = penalty

def check_draw_frequency(ticket: list, patterns: dict) -> FilterResult:
    draws = ticket.count("X")
    if draws < patterns["min_draws"]:
        return FilterResult(False, f"Too few draws: {draws} (min {patterns['min_draws']})")
    if draws > patterns["max_draws"]:
        return FilterResult(False, f"Too many draws: {draws} (max {patterns['max_draws']})")
    avg = patterns["avg_draws"]
    deviation = abs(draws - avg)
    penalty = max(0, deviation - 1) * 0.1
    return FilterResult(True, f"{draws} draws", penalty)

def check_home_win_count(ticket: list, patterns: dict) -> FilterResult:
    homes = ticket.count("1")
    if homes < patterns["min_home_wins"]:
        return FilterResult(False, f"Too few home wins: {homes} (min {patterns['min_home_wins']})")
    if homes > patterns["max_home_wins"]:
        return FilterResult(False, f"Too many home wins: {homes} (max {patterns['max_home_wins']})")
    avg = patterns["avg_home_wins"]
    penalty = max(0, abs(homes - avg) - 2) * 0.08
    return FilterResult(True, f"{homes} home wins", penalty)

def check_away_win_count(ticket: list, patterns: dict) -> FilterResult:
    aways = ticket.count("2")
    if aways < patterns["min_away_wins"]:
        return FilterResult(False, f"Too few away wins: {aways} (min {patterns['min_away_wins']})")
    if aways > patterns["max_away_wins"]:
        return FilterResult(False, f"Too many away wins: {aways} (max {patterns['max_away_wins']})")
    avg = patterns["avg_away_wins"]
    penalty = max(0, abs(aways - avg) - 2) * 0.08
    return FilterResult(True, f"{aways} away wins", penalty)

def check_consecutive_runs(ticket: list, patterns: dict) -> FilterResult:
    max_run = 0
    for key, group in groupby(ticket):
        run = len(list(group))
        if run > max_run:
            max_run = run
    max_allowed = patterns["max_consecutive"]
    if max_run > max_allowed:
        return FilterResult(False, f"Run of {max_run} consecutive same results (max {max_allowed})")
    penalty = max(0, max_run - 3) * 0.05
    return FilterResult(True, f"Max run: {max_run}", penalty)

def check_outcome_balance(ticket: list, patterns: dict) -> FilterResult:
    counts = Counter(ticket)
    home = counts.get("1", 0)
    draw = counts.get("X", 0)
    away = counts.get("2", 0)
    total = home + draw + away
    penalty = 0.0
    if home / total > 0.8: penalty += 0.2
    if draw / total > 0.6: penalty += 0.15
    if away / total > 0.7: penalty += 0.15
    return FilterResult(True, f"Balance: {home}H/{draw}X/{away}A", penalty)

def check_alternating_pattern(ticket: list) -> FilterResult:
    n = len(ticket)
    alternating = sum(1 for i in range(n-1) if ticket[i] != ticket[i+1])
    ratio = alternating / (n - 1)
    penalty = max(0, ratio - 0.85) * 0.3
    return FilterResult(True, f"Alternation ratio: {ratio:.2f}", penalty)

# ── MARKET DIVERGENCE ────────────────────────────────────────
def warn_market_divergence(tickets: list, all_results: list) -> list:
    warnings = []
    # FIXED: Added check to prevent ZeroDivisionError if no tickets survive filters
    if not tickets or not all_results:
        return warnings

    for i, r in enumerate(all_results):
        p_home = r.get("p_home") or 0.33
        p_draw = r.get("p_draw") or 0.33
        p_away = r.get("p_away") or 0.33

        public_pick = "1" if p_home == max(p_home, p_draw, p_away) else (
                      "X" if p_draw == max(p_home, p_draw, p_away) else "2")
        public_prob = max(p_home, p_draw, p_away)

        agree_count = sum(1 for t in tickets if t[i] == public_pick)
        agree_pct   = (agree_count / len(tickets)) * 100

        if agree_pct >= 85 and 0.45 < public_prob < 0.70:
            ranked = sorted([("1", p_home), ("X", p_draw), ("2", p_away)], key=lambda x: x[1], reverse=True)
            alt = ranked[1][0]
            warnings.append({
                "game": i + 1,
                "message": f"Game {i+1}: {round(agree_pct)}% agreement on '{public_pick}'. Consider a pivot to '{alt}'."
            })
    return warnings

# ── TICKET SCORER ────────────────────────────────────────────
def score_ticket(ticket: list, patterns: dict) -> dict:
    checks = [
        check_draw_frequency(ticket, patterns),
        check_home_win_count(ticket, patterns),
        check_away_win_count(ticket, patterns),
        check_consecutive_runs(ticket, patterns),
        check_outcome_balance(ticket, patterns),
        check_alternating_pattern(ticket),
    ]

    for check in checks:
        if not check.passed:
            return {"passed": False, "reason": check.reason, "score": 0.0}

    total_penalty = sum(c.penalty for c in checks if c.passed)
    score = max(0.0, 1.0 - total_penalty)

    return {
        "passed": True, "reason": "", "score": round(score, 4),
        "draws": ticket.count("X"), "home_wins": ticket.count("1"), "away_wins": ticket.count("2"),
    }

# ── DISPLAY & SAVE ──────────────────────────────────────────
def save_filtered(scored: list, warnings: list, original_meta: dict):
    output = {
        "generated": datetime.now().isoformat(),
        "filtered_tickets": len(scored),
        "tickets": [t for t, sc in scored]
    }
    with open("filtered_tickets.json", "w") as f: json.dump(output, f, indent=2)
    
    with open("final_slips.txt", "w") as f:
        f.write("BETIKA JACKPOT — FINAL SMS SLIPS\n\n")
        for i, (ticket, sc) in enumerate(scored):
            f.write(f"Slip {i+1:>3}: JP#{''.join(ticket)}\n")
    print(f"  {C.GR}✓ final_slips.txt generated.{C.R}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickets", default="wheel_tickets.json")
    parser.add_argument("--bankers", default="bankers.json")
    args = parser.parse_args()

    banner()

    if not os.path.exists(args.tickets):
        print(f"{C.RE}  wheel_tickets.json not found.{C.R}"); sys.exit(1)

    with open(args.tickets) as f:
        phase2 = json.load(f)
    
    tickets = phase2["tickets"]
    all_results = []
    if os.path.exists(args.bankers):
        with open(args.bankers) as f: all_results = json.load(f).get("all_results", [])

    patterns = HISTORICAL_PATTERNS
    sep("APPLYING FILTERS")
    
    surviving = []
    scored = []
    rejection_reasons = Counter()

    for ticket in tickets:
        result = score_ticket(ticket, patterns)
        if result["passed"]:
            surviving.append(ticket)
            scored.append((ticket, result))
        else:
            rejection_reasons[result["reason"]] += 1

    if rejection_reasons:
        print(f"  {C.RE}Rejected:{C.R}")
        for r, c in rejection_reasons.items(): print(f"    {c}x {r}")

    warnings = warn_market_divergence(surviving, all_results)
    
    sep("FINAL RESULTS")
    print(f"  Original: {len(tickets)} | Surviving: {len(surviving)}")
    
    for i, (ticket, sc) in enumerate(scored):
        print(f"  Slip {i+1:>2}: {C.WH}JP#{''.join(ticket)}{C.R} (Score: {sc['score']})")

    save_filtered(scored, warnings, phase2)
    sep("DONE")

if __name__ == "__main__":
    main()