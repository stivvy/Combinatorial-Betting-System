#!/usr/bin/env python3
"""
================================================================
 BETIKA JACKPOT SYSTEM — MASTER RUNNER
 Runs all 3 phases in sequence

 Usage:
   python run_pipeline.py --matches matches.csv --budget 500
   python run_pipeline.py --matches matches.csv --budget 300 --target 13
   python run_pipeline.py --help
================================================================
"""
import subprocess
import sys
import argparse
import os

class C:
    R="\033[0m"; B="\033[1m"; RE="\033[91m"
    GR="\033[92m"; YE="\033[93m"; CY="\033[96m"; WH="\033[97m"; GY="\033[90m"

def run(cmd: list, label: str):
    print(f"\n{C.CY}{C.B}{'═'*60}{C.R}")
    print(f"{C.YE}{C.B}  RUNNING: {label}{C.R}")
    print(f"{C.CY}{'═'*60}{C.R}\n")
    result = subprocess.run([sys.executable] + cmd)
    if result.returncode != 0:
        print(f"\n{C.RE}  ✗ {label} failed. Fix errors above and retry.{C.R}\n")
        sys.exit(result.returncode)
    print(f"\n{C.GR}  ✓ {label} complete{C.R}")

def main():
    parser = argparse.ArgumentParser(description="Betika Jackpot Full Pipeline")
    parser.add_argument("--matches",   required=True, help="Matches CSV file")
    parser.add_argument("--budget",    type=int, default=500, help="Budget in KES")
    parser.add_argument("--target",    type=int, default=12,  help="Target score (12-14)")
    parser.add_argument("--threshold", type=float, default=0.75,
                        help="Banker threshold 0-1 (default: 0.75)")
    parser.add_argument("--strict",    action="store_true", help="Use strict filters in Phase 3")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip FBref scraping")
    args = parser.parse_args()

    print(f"""
{C.YE}{C.B}  ╔══════════════════════════════════════════════════════════╗
  ║      BETIKA JACKPOT SYSTEM — FULL PIPELINE              ║
  ║      Phase 1: Scrape → Phase 2: Wheel → Phase 3: Filter ║
  ╚══════════════════════════════════════════════════════════╝{C.R}

  {C.CY}Matches file: {args.matches}
  Budget:       KES {args.budget}
  Target:       {args.target}/15
  Threshold:    {int(args.threshold*100)}% banker confidence{C.R}
""")

    # Phase 1
    p1_cmd = ["phase1_bankers.py", "--matches", args.matches,
               "--threshold", str(args.threshold)]
    if args.skip_scrape:
        p1_cmd.append("--no-scrape")
    run(p1_cmd, "Phase 1: FBref Scraper + Banker Detection")

    # Phase 2
    p2_cmd = ["phase2_wheel.py", "--budget", str(args.budget),
               "--target", str(args.target)]
    run(p2_cmd, "Phase 2: Abbreviated Wheel Engine")

    # Phase 3
    p3_cmd = ["phase3_filter.py"]
    if args.strict:
        p3_cmd.append("--strict")
    run(p3_cmd, "Phase 3: Heuristic Filter + Pattern Pruning")

    print(f"""
{C.GR}{C.B}  ╔══ PIPELINE COMPLETE ════════════════════════════════════╗
  ║  Your optimised Betika Jackpot slips are ready.        ║
  ╚════════════════════════════════════════════════════════╝{C.R}

  {C.WH}Key output files:{C.R}
    {C.GR}final_slips.txt{C.R}      ← SMS-ready slips, send to 29090
    {C.GR}final_slips.csv{C.R}      ← Spreadsheet view
    {C.GR}bankers.json{C.R}         ← Phase 1 analysis
    {C.GR}wheel_tickets.json{C.R}   ← Phase 2 raw wheel
    {C.GR}filtered_tickets.json{C.R}← Phase 3 final output
""")

if __name__ == "__main__":
    main()
