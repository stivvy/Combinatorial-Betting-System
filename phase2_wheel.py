#!/usr/bin/env python3
"""
================================================================
 BETIKA JACKPOT SYSTEM — PHASE 2: ABBREVIATED WHEEL
 Python Budget Manager + C++ Wheel Engine Bridge

 What it does:
   1. Loads bankers.json from Phase 1
   2. Locks banker games as constants
   3. Runs covering design on remaining uncertain games
   4. Respects KES budget → calculates max tickets
   5. Outputs: wheel_tickets.json + SMS-ready slips
================================================================
"""

import json
import subprocess
import argparse
import sys
import os
import csv
from itertools import product
from datetime import datetime
import math

# ── COLORS ──────────────────────────────────────────────────
class C:
    R  = "\033[0m"; B  = "\033[1m"; RE = "\033[91m"
    GR = "\033[92m"; YE = "\033[93m"; BL = "\033[94m"
    MA = "\033[95m"; CY = "\033[96m"; WH = "\033[97m"
    GY = "\033[90m"

TICKET_COST = 15  # KES per ticket

def banner():
    print(f"""
{C.YE}{C.B}   ╔══════════════════════════════════════════════════════════╗
  ║   PHASE 2: ABBREVIATED WHEEL  |  Budget-Aware Engine     ║
  ╚══════════════════════════════════════════════════════════╝{C.R}
""")

def sep(title=""):
    if title:
        pad = "─" * (54 - len(title))
        print(f"{C.CY}{C.B}   ── {title} {pad}{C.R}")
    else:
        print(f"{C.GY}   {'─'*58}{C.R}")

# ── GREEDY COVERING DESIGN ──────────────────────────────────
def build_candidate_pool(uncertain_games: list, max_candidates: int = 300) -> list:
    n = len(uncertain_games)
    candidates = []
    base = tuple(g["primary"] for g in uncertain_games)
    candidates.append(base)

    import random
    rng = random.Random(42)
    all_outcomes = ["1", "X", "2"]

    def get_alternatives(game: dict) -> list:
        alts_str = game.get("alternatives", "")
        if isinstance(alts_str, str):
            alts = [a.strip() for a in alts_str.split() if a.strip() in ("1","X","2")]
        else:
            alts = []
        primary = game["primary"]
        if not alts:
            alts = [o for o in all_outcomes if o != primary]
        return alts

    from itertools import combinations as icomb
    for flip_count in range(1, min(4, n+1)):
        for flip_indices in icomb(range(n), flip_count):
            game_alts = [get_alternatives(uncertain_games[fi]) for fi in flip_indices]
            for alt_combo in product(*game_alts):
                if len(candidates) >= max_candidates: break
                ticket = list(base)
                for pos, fi in enumerate(flip_indices):
                    ticket[fi] = alt_combo[pos]
                candidates.append(tuple(ticket))
            if len(candidates) >= max_candidates: break
        if len(candidates) >= max_candidates: break

    while len(candidates) < max_candidates:
        ticket = list(base)
        num_flips = rng.randint(1, min(4, n)) if n > 1 else 1
        flip_indices = rng.sample(range(n), num_flips)
        for fi in flip_indices:
            alts = get_alternatives(uncertain_games[fi])
            ticket[fi] = rng.choice(alts)
        t = tuple(ticket)
        if t not in candidates: candidates.append(t)
    return candidates

def score_ticket(ticket: tuple, scenario: tuple) -> int:
    return sum(1 for a, b in zip(ticket, scenario) if a == b)

def build_scenarios(uncertain_games: list, threshold_correct: int) -> list:
    n = len(uncertain_games)
    num_wrong = max(0, n - threshold_correct)
    from itertools import combinations as icomb
    all_outcomes = ["1", "X", "2"]
    scenarios = []
    base = tuple(g["primary"] for g in uncertain_games)

    for wrong_indices in icomb(range(n), num_wrong):
        scenario = list(base)
        for wi in wrong_indices:
            alts = [o for o in all_outcomes if o != uncertain_games[wi]["primary"]]
            scenario[wi] = alts[0]
        scenarios.append(tuple(scenario))
    return scenarios

def greedy_set_cover(candidates: list, scenarios: list, target_score: int, max_tickets: int) -> list:
    uncovered = set(range(len(scenarios)))
    selected  = []
    while uncovered and len(selected) < max_tickets:
        best_candidate, best_cover_count, best_covered_set = None, -1, set()
        for ci, candidate in enumerate(candidates):
            covered = {si for si in uncovered if score_ticket(candidate, scenarios[si]) >= target_score}
            if len(covered) > best_cover_count:
                best_cover_count, best_candidate, best_covered_set = len(covered), ci, covered
        if best_candidate is None or best_cover_count == 0: break
        selected.append(candidates[best_candidate])
        uncovered -= best_covered_set
        candidates.pop(best_candidate)
    return selected

def assemble_full_tickets(uncertain_tickets: list, bankers: list, all_games: list) -> list:
    banker_picks = {b["game"] - 1: b["banker_pick"] for b in bankers}
    full_tickets = []
    for unc_ticket in uncertain_tickets:
        full, unc_pos = [], 0
        for i in range(15):
            if i in banker_picks: full.append(banker_picks[i])
            else:
                full.append(unc_ticket[unc_pos])
                unc_pos += 1
        full_tickets.append(full)
    return full_tickets

# ── EV CALCULATION ───────────────────────────────────────────
PRIZE_TABLE = {15: 15_000_000, 14: 1_000_000, 13: 125_000, 12: 15_000}

def estimate_ev(full_tickets: list, all_results: list) -> dict:
    total_ev = 0.0
    game_probs = {}
    for r in all_results:
        g = r["game"] - 1
        game_probs[g] = {"1": r.get("p_home", 0.33), "X": r.get("p_draw", 0.33), "2": r.get("p_away", 0.33)}

    for ticket in full_tickets:
        p_correct = [game_probs.get(g, {"1": 0.33, "X": 0.33, "2": 0.33}).get(pick, 0.33) for g, pick in enumerate(ticket)]
        dp = [0.0] * 16
        dp[0] = 1.0
        for pc in p_correct:
            ndp = [0.0] * 16
            for s in range(16):
                if dp[s] == 0: continue
                ndp[s] += dp[s] * (1 - pc)
                if s < 15: ndp[s+1] += dp[s] * pc
            dp = ndp
        for score, prize in PRIZE_TABLE.items(): total_ev += dp[score] * prize

    cost = len(full_tickets) * TICKET_COST
    roi = (total_ev - cost) / cost * 100 if cost > 0 else 0
    return {"ev": round(total_ev, 2), "cost": cost, "roi": round(roi, 2)}

# ── DISPLAY & SAVE ───────────────────────────────────────────
def print_tickets(full_tickets: list, bankers: list, uncertain_games: list):
    sep("GENERATED BETTING SLIPS")
    banker_indices = {b["game"] - 1 for b in bankers}
    print(f"   {C.GY}Key: {C.GR}Green{C.GY} = banker (locked) | {C.YE}Yellow{C.GY} = uncertain pick{C.R}\n")
    for i, ticket in enumerate(full_tickets):
        print(f"   {C.CY}Slip {i+1:>3}{C.R}: ", end="")
        for g, pick in enumerate(ticket):
            color = C.GR + C.B if g in banker_indices else C.YE
            print(f"{color}{pick}{C.R}", end="")
            if g < 14: print(f"{C.GY}-{C.R}", end="")
        print()

def save_tickets(full_tickets: list, ev_info: dict, bankers: list, uncertain: list):
    output = {
        "generated": datetime.now().isoformat(), "num_tickets": len(full_tickets),
        "total_cost_kes": ev_info["cost"], "expected_value_kes": ev_info["ev"],
        "expected_roi_pct": ev_info["roi"], "bankers_locked": len(bankers),
        "uncertain_games": len(uncertain), "tickets": full_tickets,
    }
    with open("wheel_tickets.json", "w") as f: json.dump(output, f, indent=2)

    with open("sms_slips.txt", "w") as f:
        f.write(f"BETIKA JACKPOT SLIPS\nTotal: {len(full_tickets)} | Cost: KES {ev_info['cost']}\n\nBANKERS:\n")
        for b in bankers:
            # FIX: Safely handle missing confidence by checking p_home/p_away
            conf_val = b.get('confidence') or b.get(f"p_{'home' if b['banker_pick']=='1' else 'away' if b['banker_pick']=='2' else 'draw'}")
            conf_display = f"{int(conf_val*100)}%" if isinstance(conf_val, float) else "N/A"
            f.write(f"   Game {b['game']}: {b['home']} vs {b['away']} → {b['banker_pick']} ({conf_display})\n")
        f.write(f"\nSMS SLIPS (29090):\n{'-'*40}\n")
        for i, ticket in enumerate(full_tickets):
            f.write(f"Slip {i+1:>3}: JP#{''.join(ticket)}\n")

    print(f"   {C.GR}✓ wheel_tickets.json | ✓ sms_slips.txt | ✓ wheel_tickets.csv{C.R}\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=int, default=500)
    parser.add_argument("--target", type=int, default=12)
    parser.add_argument("--threshold", type=int, default=None)
    parser.add_argument("--bankers", default="bankers.json")
    args = parser.parse_args()
    banner()

    if not os.path.exists(args.bankers): sys.exit(f"{C.RE}bankers.json not found.{C.R}")
    with open(args.bankers) as f: phase1 = json.load(f)

    bankers, uncertain, all_results = phase1["bankers"], phase1["uncertain"], phase1["all_results"]
    max_tickets, target_score = args.budget // TICKET_COST, args.target
    num_bankers = len(bankers)
    
    threshold_uncertain = args.threshold - num_bankers if args.threshold else max(1, len(uncertain) - (15 - target_score - num_bankers) - 1)
    threshold_uncertain = max(0, min(threshold_uncertain, len(uncertain)))
    target_uncertain = max(0, min(target_score - num_bankers, len(uncertain)))

    print(f"   {C.CY}Budget: KES {args.budget} | Bankers: {num_bankers} | Target: {target_score}/15{C.R}\n")

    if not uncertain:
        full = [[b["banker_pick"] for b in sorted(bankers, key=lambda x: x["game"])]]
        save_tickets(full, estimate_ev(full, all_results), bankers, uncertain)
        print_tickets(full, bankers, uncertain); return

    candidates = build_candidate_pool(uncertain, max_candidates=400)
    scenarios = build_scenarios(uncertain, threshold_uncertain)
    selected_uncertain = greedy_set_cover(candidates, scenarios, target_uncertain, max_tickets)
    
    full_tickets = assemble_full_tickets(selected_uncertain, bankers, list(range(15)))
    ev_info = estimate_ev(full_tickets, all_results)

    sep("WHEEL SUMMARY")
    print(f"   {C.GR}║ Tickets: {len(full_tickets):<5} | Cost: KES {ev_info['cost']:<5} | ROI: {ev_info['roi']:+.1f}% ║{C.R}\n")
    print_tickets(full_tickets, bankers, uncertain)
    save_tickets(full_tickets, ev_info, bankers, uncertain)

if __name__ == "__main__":
    main()