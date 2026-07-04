#!/usr/bin/env python3
"""
================================================================
 JACKPOT PREDICTION SYSTEM — BACKTESTER v2
 Tests odds-based model against known past results.

 CSV format (6 columns):
   Home,Away,Odds_1,Odds_X,Odds_2,Actual_Result
   Fiorentina,Atalanta,2.75,3.55,2.50,X

 Usage:
   python backtest.py --matches past_jackpot.csv
   python backtest.py --matches past_jackpot.csv --budget 500
================================================================
"""

import json
import argparse
import sys
import os
import subprocess
from datetime import datetime

class C:
    R="\033[0m"; B="\033[1m"; RE="\033[91m"; GR="\033[92m"
    YE="\033[93m"; CY="\033[96m"; WH="\033[97m"; GY="\033[90m"

def banner():
    print(f"""
{C.CY}{C.B}  ╔══════════════════════════════════════════════════════════╗
  ║   BACKTESTER v2  |  Odds Model vs Past Results           ║
  ╚══════════════════════════════════════════════════════════╝{C.R}
""")

def sep(t=""):
    if t: print(f"{C.CY}{C.B}  -- {t} {'-'*(54-len(t))}{C.R}")
    else: print(f"{C.GY}  {'-'*58}{C.R}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--matches", required=True)
    p.add_argument("--threshold", type=float, default=0.55)
    p.add_argument("--budget", type=int, default=500)
    args = p.parse_args()

    banner()

    # Read file — extract odds AND actual results
    games = []
    model_lines = []

    with open(args.matches, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [x.strip() for x in line.split(",")]
            if parts[0].lower() in ("home", "home team"):
                continue
            if len(parts) < 6:
                print(f"{C.RE}  Need 6 columns: Home,Away,Odds_1,Odds_X,Odds_2,Result{C.R}")
                print(f"  Got: {line}")
                sys.exit(1)

            home, away = parts[0], parts[1]
            try:
                o1, ox, o2 = float(parts[2]), float(parts[3]), float(parts[4])
            except ValueError:
                print(f"{C.RE}  Bad odds in: {line}{C.R}")
                sys.exit(1)
            result = parts[5].upper()
            if result not in ("1", "X", "2"):
                print(f"{C.RE}  Bad result '{result}' — use 1, X, or 2{C.R}")
                sys.exit(1)

            games.append({"home": home, "away": away,
                          "o1": o1, "ox": ox, "o2": o2, "actual": result})
            # Write odds-format line for Phase 1 (5 columns, no result)
            model_lines.append(f"{home},{away},{o1},{ox},{o2}")

    num = len(games)
    print(f"  {C.CY}Loaded {num} games with odds + known results{C.R}\n")

    # Write temp CSV for Phase 1
    temp = "_backtest_input.csv"
    with open(temp, "w", encoding="utf-8") as f:
        for line in model_lines:
            f.write(line + "\n")

    # Run Phase 1
    sep("RUNNING PHASE 1 (odds model)")
    r1 = subprocess.run([sys.executable, "phase1_model.py",
                         "--matches", temp, "--threshold", str(args.threshold)])
    if r1.returncode != 0:
        print(f"{C.RE}  Phase 1 failed{C.R}"); sys.exit(1)

    # Load predictions
    with open("bankers.json", encoding="utf-8") as f:
        preds = json.load(f)
    all_preds = preds["all_results"]

    # Compare
    sep("MODEL vs REALITY")
    print()
    print(f"  {C.GY}{'#':<4}{'Home':<18}{'Away':<18}{'Pick':<6}{'Real':<6}{'Conf':>6}  Result{C.R}")
    sep()

    correct = 0
    details = []
    for i, (pred, game) in enumerate(zip(all_preds, games)):
        pick = pred["primary"]
        real = game["actual"]
        conf = pred["confidence"]
        hit = (pick == real)
        if hit: correct += 1
        icon = f"{C.GR}HIT{C.R}" if hit else f"{C.RE}MISS (was {real}){C.R}"
        print(f"  {C.GY}{i+1:<4}{C.R}{game['home'][:16]:<18}{game['away'][:16]:<18}"
              f"{pick:<6}{real:<6}{conf:>5.1f}%  {icon}")
        details.append({"game": i+1, "predicted": pick, "actual": real,
                        "correct": hit, "confidence": conf})

    # Accuracy
    print()
    sep("MODEL ACCURACY")
    print()
    pct = correct / num * 100 if num > 0 else 0
    col = C.GR if correct >= 12 else (C.YE if correct >= 10 else C.RE)
    print(f"  {col}{C.B}Correct: {correct}/{num} ({pct:.1f}%){C.R}\n")

    tiers = {15: "GRAND PRIZE (15/15)", 14: "Bonus 1 (14/15)",
             13: "Bonus 2 (13/15)", 12: "Bonus 3 (12/15)"}
    for t, name in sorted(tiers.items(), reverse=True):
        if correct >= t:
            print(f"  {C.GR}{C.B}  >> Model alone qualifies for: {name} <<{C.R}")
            break
    else:
        needed = 12 - correct
        print(f"  {C.YE}  Missed bonus by {needed} game(s). Need 12+ correct.{C.R}")
    print()

    # Detailed breakdown: where did the model get draws right?
    sep("DRAW ANALYSIS")
    print()
    actual_draws = [g for g in games if g["actual"] == "X"]
    predicted_draws = [p for p in all_preds if p["primary"] == "X"]
    draw_hits = sum(1 for p, g in zip(all_preds, games)
                    if p["primary"] == "X" and g["actual"] == "X")
    print(f"  Actual draws in results:    {len(actual_draws)}")
    print(f"  Model predicted draws:      {len(predicted_draws)}")
    print(f"  Draw predictions correct:   {draw_hits}")
    if actual_draws:
        print(f"\n  {C.GY}Draws that occurred:{C.R}")
        for i, (p, g) in enumerate(zip(all_preds, games)):
            if g["actual"] == "X":
                drew = "HIT" if p["primary"] == "X" else f"picked {p['primary']}"
                col = C.GR if p["primary"] == "X" else C.RE
                print(f"    G{i+1}: {g['home'][:16]} vs {g['away'][:16]}"
                      f"  draw%={p['p_draw']*100:.0f}%  {col}{drew}{C.R}")
    print()

    # Run Phase 2 and check wheel scores
    sep("WHEEL TICKET SCORES")
    r2 = subprocess.run([sys.executable, "phase2_wheel.py",
                         "--budget", str(args.budget), "--target", "12"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    best_score = 0
    best_slip = 0
    if os.path.exists("wheel_tickets.json"):
        with open("wheel_tickets.json", encoding="utf-8") as f:
            wheel = json.load(f)
        tickets = wheel.get("tickets", [])
        actual_str = [g["actual"] for g in games]

        scores = []
        for i, ticket in enumerate(tickets):
            score = sum(1 for t, a in zip(ticket, actual_str) if t == a)
            scores.append((i + 1, score, ticket))
            if score > best_score:
                best_score = score
                best_slip = i + 1

        scores.sort(key=lambda x: x[1], reverse=True)

        print()
        print(f"  Total tickets: {len(tickets)} | Cost: KES {len(tickets)*15}")
        col = C.GR if best_score >= 12 else (C.YE if best_score >= 10 else C.RE)
        print(f"  {col}{C.B}Best ticket: Slip {best_slip} scored {best_score}/{num}{C.R}\n")

        for t, name in sorted(tiers.items(), reverse=True):
            if best_score >= t:
                print(f"  {C.GR}{C.B}  >> Best ticket qualifies for: {name} <<{C.R}")
                break
        else:
            needed = 12 - best_score
            print(f"  {C.YE}  Closest ticket missed bonus by {needed} game(s){C.R}")

        print(f"\n  {C.GY}Top 5 tickets:{C.R}")
        for slip, score, ticket in scores[:5]:
            col = C.GR if score >= 12 else (C.YE if score >= 10 else C.GY)
            print(f"    Slip {slip:>3}: {''.join(ticket)}  {col}{score}/{num}{C.R}")
    print()

    # Cleanup
    try: os.remove(temp)
    except: pass

    # Save report
    with open("backtest_report.json", "w", encoding="utf-8") as f:
        json.dump({"generated": datetime.now().isoformat(),
                   "games": num, "model_correct": correct,
                   "model_pct": round(pct, 1), "best_ticket_score": best_score,
                   "actual_draws": len(actual_draws),
                   "predicted_draws": len(predicted_draws),
                   "details": details}, f, indent=2)
    print(f"  {C.GR}OK Report: backtest_report.json{C.R}\n")

if __name__ == "__main__":
    main()
